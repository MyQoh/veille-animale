"""Brique 1 : questions écrites de l'Assemblée nationale classées par thèmes.

Transposition à logique identique du carnet reference/aspirateur_questions_ecrites_v13.ipynb
(version 13, gelée). Chaque bloc « Cellule » reprend la cellule du même numéro.

Seuls changements par rapport au carnet, sans effet sur les résultats :
- archives rangées dans donnees_brutes/an/ ; sorties écrites dans un nouveau dossier
  sorties/AAAA-MM-JJ_HHhMM_brique1/ (jamais d'écrasement) ;
- retrait de ce qui est propre à Colab (installation de ijson, files.download, display) ;
- option --legislatures pour tester sur un échantillon (par exemple 17) ;
- option --date-reference pour fixer « aujourd'hui » et comparer avec une exécution passée.

Usage :
    python scripts/brique1_questions_ecrites.py
    python scripts/brique1_questions_ecrites.py --legislatures 17 --date-reference 2026-09-25
"""
import argparse

from commun import DONNEES_BRUTES, console_utf8, date_reference, dossier_sortie

console_utf8()
parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--legislatures", type=int, nargs="+", default=[14, 15, 16, 17],
                    help="législatures à traiter (par défaut toutes : 14 15 16 17)")
parser.add_argument("--date-reference", default=None, help="date du jour à utiliser, AAAA-MM-JJ")
ARGS = parser.parse_args()

# ---------------------------------------------------------------------------
# Cellule 1. Réglages et téléchargement
import io, json, re, zipfile, unicodedata, urllib.request
from collections import Counter
import pandas as pd

BASE = "https://data.assemblee-nationale.fr/static/openData/repository"
# législature, fichier, date de fin (None = en cours)
SOURCES = [
    (14, f"{BASE}/14/questions/questions_ecrites/Questions_ecrites_XIV.json.zip", "2017-06-20"),
    (15, f"{BASE}/15/questions/questions_ecrites/Questions_ecrites_XV.json.zip", "2022-06-21"),
    (16, f"{BASE}/16/questions/questions_ecrites/Questions_ecrites.json.zip", "2024-06-09"),
    (17, f"{BASE}/17/questions/questions_ecrites/Questions_ecrites.json.zip", None),
]
SOURCES = [s for s in SOURCES if s[0] in ARGS.legislatures]   # ajout script : échantillon éventuel
DELAI_LEGAL_MOIS = 2          # art. 135 al. 6 du règlement de l'Assemblée nationale
DELAI_SIGNALEMENT_JOURS = 10  # art. 135 al. 7
REFORME_REGLEMENT_2014 = pd.Timestamp("2014-11-28")   # résolution n° 437 : délai de 2 mois et règle des 10 jours
RECONNAISSANCE_SENSIBILITE = pd.Timestamp("2015-02-16")  # loi n° 2015-177, art. 515-14 du Code civil

# Rubriques prises en entier
RUBRIQUES_ENTIERES = ["animaux", "chasse et peche"]
# Rubriques larges : on ne garde que les questions qui parlent du sort des animaux
RUBRIQUES_FILTREES = ["elevage", "agriculture", "environnement", "aquaculture et peche professionnelle"]

import os, time, hashlib, requests

DOSSIER = os.path.join(DONNEES_BRUTES, "an")
os.makedirs(DOSSIER, exist_ok=True)
# Empreintes MD5 publiées par l'Assemblée pour les archives figées (vérification d'intégrité)
MD5_OFFICIELS = {14: "c765e31d47c3f4be213b0c982ff9f749", 15: "fd1c7027fb32c917d9be62b85f574b8e",
                 16: "0cbeecec01c74f9318385c809a4d1573"}

def md5_fichier(chemin):
    h = hashlib.md5()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()

def fichier_valide(chemin, md5):
    if not os.path.exists(chemin) or not zipfile.is_zipfile(chemin):
        return False
    return md5 is None or md5_fichier(chemin) == md5

def telecharger(url, chemin, md5=None, echecs_max=10, essais_max=80):
    """Téléchargement par morceaux, sur disque, avec reprise après coupure.
    On abandonne seulement après `echecs_max` coupures consécutives sans aucun progrès."""
    echecs = 0
    for essai in range(1, essais_max + 1):
        deja = os.path.getsize(chemin) if os.path.exists(chemin) else 0
        entetes = {"Range": f"bytes={deja}-"} if deja else {}
        avant = deja
        try:
            with requests.get(url, headers=entetes, stream=True, timeout=(30, 120)) as r:
                if r.status_code != 416:          # 416 = déjà complet
                    r.raise_for_status()
                    reprise = r.status_code == 206
                    total = int(r.headers.get("Content-Length", 0)) + (deja if reprise else 0)
                    recu = deja if reprise else 0
                    avant = recu
                    palier = recu * 10 // total if total else 0
                    with open(chemin, "ab" if reprise else "wb") as f:
                        for bloc in r.iter_content(chunk_size=1 << 20):
                            f.write(bloc)
                            recu += len(bloc)
                            if total and recu * 10 // total > palier:
                                palier = recu * 10 // total
                                print(f"    {palier * 10} % ({recu / 1e6:.0f} Mo / {total / 1e6:.0f} Mo)")
            if fichier_valide(chemin, md5):
                return
            if md5 and os.path.exists(chemin) and zipfile.is_zipfile(chemin):
                print("    empreinte non conforme, on repart de zéro")
                os.remove(chemin)
        except (requests.RequestException, IOError) as e:
            actuel = os.path.getsize(chemin) if os.path.exists(chemin) else 0
            echecs = 0 if actuel > avant else echecs + 1
            print(f"    coupure à {actuel / 1e6:.0f} Mo, reprise ({'progrès' if echecs == 0 else f'sans progrès {echecs}/{echecs_max}'})")
            if echecs >= echecs_max:
                break
        time.sleep(min(3 + 2 * echecs, 30))
    raise RuntimeError(f"Téléchargement impossible : {url}. Relancer le script, le téléchargement reprendra où il s'est arrêté.")

import ijson   # installé par requirements.txt (le carnet l'installait à la volée)

def questions_de(zf, noms):
    """Rend chaque question, que l'archive contienne un fichier par question (17e)
    ou un seul gros fichier pour toutes (archives anciennes), lu alors au fil de l'eau."""
    if len(noms) > 1:
        for n in noms:
            try:
                yield json.loads(zf.read(n)).get("question", {})
            except Exception:
                yield None
        return
    # un seul fichier : on repère d'abord où sont rangées les questions (chemin de la clé "uid")
    with zf.open(noms[0]) as f:
        prefixe = None
        for pref, evt, val in ijson.parse(f):
            if evt == "map_key" and val == "uid":
                prefixe = pref
                break
    if prefixe is None:
        raise ValueError("Structure inconnue : aucune question repérée dans " + noms[0])
    with zf.open(noms[0]) as f:
        for q in ijson.items(f, prefixe, use_float=True):
            yield q

archives = {}
for leg, url, fin in SOURCES:
    chemin = os.path.join(DOSSIER, f"questions_ecrites_{leg}.json.zip")
    md5 = MD5_OFFICIELS.get(leg)
    # législature en cours : on retélécharge si le fichier a plus de 12 heures
    perime = fin is None and os.path.exists(chemin) and time.time() - os.path.getmtime(chemin) > 12 * 3600
    if perime:
        os.remove(chemin)
    if fichier_valide(chemin, md5):
        print(f"{leg}e législature : fichier déjà présent et vérifié")
    else:
        print(f"Téléchargement {leg}e législature...")
        telecharger(url, chemin, md5)
        print("    vérifié" + (" (empreinte MD5 officielle conforme)" if md5 else ""))
    zf = zipfile.ZipFile(chemin)
    noms = [n for n in zf.namelist() if n.lower().endswith(".json")]
    archives[leg] = (zf, noms, fin)
    premiere = next(q for q in questions_de(zf, noms) if q)
    rangement = "un fichier par question" if len(noms) > 1 else "un seul fichier, lecture au fil de l'eau"
    print(f"  {os.path.getsize(chemin)/1e6:.1f} Mo, {rangement}")
    print("  champs :", list(premiere.keys()))
    print("  extrait brut :", json.dumps(premiere, ensure_ascii=False, default=str)[:700])

# ---------------------------------------------------------------------------
# Cellule 2. Règles de classement (à affiner au fil des revues)
# Écrire sans accents et en minuscules. "s?" = pluriel facultatif.
EPIZOOTIES = [r"epizooties?", r"influenza aviaire", r"grippe aviaire", r"fievre catarrhale", r"fco",
    r"dermatose nodulaire", r"dncb?", r"tuberculose bovine", r"peste porcine", r"fievre porcine", r"besnoitiose",
    r"clavelee", r"maladie hemorragique epizootique", r"mhe", r"iahp", r"tuberculose", r"rhinotracheite", r"ibr", r"mortalites? anormales?", r"vaccins? avicoles?", r"canards? vaccines?", r"mise a l.abri", r"abattages? sanitaires?", r"abattage (?:total|des troupeaux)", r"depeuplement"]
SEUIL_PORTE_TEXTE = 3   # mentions minimales dans le texte pour entrer depuis une rubrique large
SEUIL_THEME_TEXTE = 2   # mentions minimales dans le texte pour attribuer un thème

THEMES = {
    "Animaux de compagnie": [r"chiens?", r"chiots?", r"chats?", r"chatons?", r"felins?", r"animaux de compagnie",
        r"animal de compagnie", r"animaux domestiques", r"fourrieres?", r"refuges?", r"abandons?", r"identification",
        r"icad", r"sterilisation", r"errants?", r"animaleries?", r"nac", r"adoptions?", r"cession d.animaux",
        r"equides?", r"chevaux", r"equitation", r"lapins?", r"cynophiles?", r"permis de detention",
        r"associations? protectrices?", r"vente d.animaux", r"animaux en ligne", r"canines?", r"pet sitting",
        r"colliers? electriques?", r"equine", r"acaced", r"attestations? de connaissances?"],
    "Animaux d'élevage": [r"abattage", r"abattoirs?", r"transports? (?:des |d.)animaux", r"animaux vivants", r"betaillers?", r"navires? (?:betaillers?|de transport d.animaux)", r"alimentation animale", r"elevages? intensifs?", r"cages?",
        r"poules? pondeuses?", r"broyage", r"poussins?", r"castration", r"gavage", r"foie gras", r"mutilations?",
        r"etourdissement", r"caudectomie", r"hippophagie", r"ovosexage", r"apicoles?", r"apiculture", r"apiculteurs?", r"abeilles?", r"ruchers?", r"ruches?",
        r"varroa", r"tropilaelaps", r"animaux d.elevage", r"ultra.intensifs?", r"fermes?.usines?", r"usines? (?:a|de) (?:bovins|poulets|porcs|volailles|vaches)",
        r"conditions? des animaux", r"transport equin", r"transport des equides", r"sacrifices?", r"abattage rituel", r"bien.etre (?:des animaux d.elevage|en elevage)"],
    "Chasse et pêche de loisir": [r"chasse", r"chasseurs?", r"gibiers?", r"venerie", r"battues?", r"peche de loisir",
        r"pecheurs? amateurs?", r"deterrage", r"piegeage", r"peche au vif", r"pecheurs? de loisirs?",
        r"peche a pied", r"peche recreative", r"empoissonnement", r"civelles?", r"permis de chasser", r"tenderie",
        r"gardes? particuliers?", r"piegeurs?", r"cynegetiques?", r"venaison",
        r"taxidermistes?", r"guides? de peche", r"droit de peche", r"federations? (?:departementales? )?des chasseurs"],
    "Faune sauvage": [r"loups?", r"ours", r"lynx", r"predations?", r"grands predateurs", r"especes? protegees?",
        r"esod", r"faune sauvage", r"corbeaux?", r"cormorans?", r"renards?", r"blaireaux?", r"sangliers?", r"oiseaux",
        r"rapaces?", r"cetaces?", r"dauphins?", r"phoques?", r"tortues?", r"collisions?",
        r"especes? sauvages?", r"animaux sauvages", r"carnivores?", r"mammiferes? marins?", r"cigognes?",
        r"pastoralisme", r"nuisibles?", r"goelands?", r"etourneaux", r"cerfs?", r"crabes?", r"ecrevisses?", r"meduses?", r"ragondins?", r"castors?", r"especes? menacees?", r"ivoire", r"braconnage",
        r"commerce illicite", r"trafic", r"outardes?", r"grenouilles?", r"poissons? migrateurs?", r"truites?",
        r"saumons?", r"anguilles?", r"corvides?", r"biodiversite", r"corneilles?", r"cormorans?", r"louvetiers?", r"regulation des especes", r"especes? nuisibles?", r"trafic d.especes"],
    "Captivité et spectacle": [r"cirques?", r"delphinariums?", r"marineland", r"zoos?", r"parcs? zoologiques?",
        r"captivite", r"aquariums?", r"animaux sauvages captifs", r"animaux non domestiques", r"liste positive",
        r"sanctuaires?", r"itinerants?", r"itinerance", r"tournages?", r"spectacles?", r"fauconnerie",
        r"combats? de vaches", r"animaux non.domestiques", r"corridas?", r"tauromachie", r"combats? de coqs"],
    "Maltraitance et justice": [r"maltraitances?", r"sevices", r"cruaute", r"vols? (?:de chiens|d.animaux)", r"zoophilie",
        r"fichier national", r"penale?s?", r"condamnations?", r"tortures?", r"crushing",
        r"videos? (?:de|d.)(?:torture|cruaute|maltraitance|violence)", r"vols? animaux", r"animaux saisis", r"saisies?"],
    "Santé animale et vétérinaires": [r"veterinaires?", r"zoonoses?", r"maladies? animales?", r"osteopathie animale",
        r"maillage veterinaire", r"sante animale"],
    "Épizooties et abattages sanitaires": EPIZOOTIES,
    "Nuisibles et espèces invasives": [r"frelons?", r"moustiques?", r"termites?", r"fourmis?", r"cochenilles?",
        r"especes? invasives?", r"especes? exotiques envahissantes", r"rats?", r"rongeurs?", r"punaises?",
        r"pigeons?", r"chenilles? processionnaires?", r"chenilles? urticantes?", r"campagnols?", r"pieges? a colle", r"charancons?", r"infestations?"],
    # NB (repéré à la transposition, conservé tel quel) : r"dissequ\\w*" cherche une barre oblique littérale,
    # donc « disséquer » n'est jamais reconnu. À corriger dans une version ultérieure, après validation.
    "Expérimentation animale": [r"experimentation animale", r"animaux de laboratoire", r"vivisection",
        r"tests? sur les animaux", r"recherche animale", r"fins scientifiques", r"dissequ\\w*", r"dissections?", r"cancer animal"],
    "Condition animale (général)": [r"bien.etre animal", r"condition animale", r"souffrance animale", r"protection animale",
        r"statut juridique", r"etres? sensibles?", r"cause animale", r"l214", r"protection des animaux", r"associations? de protection animale", r"protection : associations", r"animalistes?", r"statut de l.animal"],
}
# Porte d'entrée pour les rubriques larges : la question doit parler du sort des animaux
PORTE_RUBRIQUES_LARGES = [r"bien.etre animal", r"condition animale", r"souffrance animale", r"protection animale",
    r"maltraitances?", r"abattage", r"abattoirs?", r"transports? (?:des |d.)animaux", r"animaux vivants", r"betaillers?", r"navires? (?:betaillers?|de transport d.animaux)", r"alimentation animale", r"cages?", r"gavage", r"broyage",
    r"castration", r"mutilations?", r"etourdissement", r"elevages? intensifs?", r"loups?", r"ours", r"lynx",
    r"predations?", r"especes? protegees?", r"esod", r"faune sauvage", r"chasse", r"gibiers?", r"cetaces?", r"dauphins?",
    r"experimentation animale", r"cirques?", r"zoos?", r"captures? accidentelles?", r"abeilles?", r"apicoles?",
    r"animaux sauvages", r"especes? sauvages?", r"bien.etre (?:des animaux|en elevage)"]

FAMILLES_MINISTERES = [("agriculture", "Agriculture"), ("transition ecologique", "Écologie"), ("ecologie", "Écologie"),
    ("biodiversite", "Écologie"), ("justice", "Justice"), ("interieur", "Intérieur"), ("culture", "Culture"),
    ("sante", "Santé"), ("travail", "Travail et solidarités"), ("economie", "Économie"), ("outre-mer", "Outre-mer"),
    ("education", "Éducation"), ("enseignement superieur", "Enseignement supérieur et recherche"),
    ("armees", "Armées"), ("affaires etrangeres", "Affaires étrangères"), ("sports", "Sports"), ("environnement", "Écologie"), ("de la mer", "Mer"),
    ("collectivites", "Territoires"), ("amenagement du territoire", "Territoires"), ("premier ministre", "Premier ministre")]

def sans_accents(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower().replace("’", "'"))

def motif(liste):
    return re.compile(r"\b(?:" + "|".join(liste) + r")\b")

MOTIFS = {t: motif(l) for t, l in THEMES.items()}
MOTIF_PORTE = motif(PORTE_RUBRIQUES_LARGES)
MOTIF_EPIZOOTIES = motif(EPIZOOTIES)
# Pour entrer depuis une rubrique large, un mot de filière ne suffit pas (économie ≠ bien-être) :
# les chevaux n'entrent que si la question parle aussi de leur sort (bien-être, maltraitance, transport, abattage...)
MOTS_FILIERE = {r"equides?", r"chevaux", r"equitation", r"equine"}
MOTIFS_ADMISSION = {t: motif([p for p in l if p not in MOTS_FILIERE]) for t, l in THEMES.items()
                    if t != "Nuisibles et espèces invasives"}
# Nuisibles venus des rubriques agricoles : admis seulement si la question parle de la méthode de lutte,
# pas uniquement des dégâts (décision : le sort des animaux, pas l'économie des cultures)
MOTIF_NUISIBLES = motif(THEMES["Nuisibles et espèces invasives"])
MOTIF_LUTTE = motif([r"lutte", r"pesticides?", r"insecticides?", r"biocides?", r"piegeage", r"pieges?", r"regulation",
                     r"destruction", r"traitements?", r"eradication", r"produits? phytosanitaires?", r"neonicotinoides?"])

def admis_rubrique_large(titre_n, texte_n):
    if MOTIF_NUISIBLES.search(titre_n) and MOTIF_LUTTE.search(titre_n + " " + texte_n):
        return True
    if MOTIF_PORTE.search(titre_n) or any(m.search(titre_n) for m in MOTIFS_ADMISSION.values()) or MOTIF_EPIZOOTIES.search(titre_n + " " + texte_n):
        return True
    return len(MOTIF_PORTE.findall(texte_n)) >= SEUIL_PORTE_TEXTE

def classer(titre_n, texte_n):
    themes, declencheurs = [], []
    for t, m in MOTIFS.items():
        dans_titre = sorted(set(x.group(0) for x in m.finditer(titre_n)))
        dans_texte = [x.group(0) for x in m.finditer(texte_n)]
        if dans_titre:
            themes.append(t)
            declencheurs.append(f"{t} (titre) : {', '.join(dans_titre[:4])}")
        elif len(dans_texte) >= SEUIL_THEME_TEXTE:
            themes.append(t)
            declencheurs.append(f"{t} (texte x{len(dans_texte)}) : {', '.join(sorted(set(dans_texte))[:4])}")
    return themes, declencheurs

def normaliser_loi(num):
    a, b = num.split("-")
    return f"{b}-{a}" if int(a) < 1900 and 1900 <= int(b) <= 2100 else num   # corrige "1539-2021" en "2021-1539"

def famille_ministere(nom):
    n = sans_accents(nom)
    for cle, fam in FAMILLES_MINISTERES:
        if cle in n:
            return fam
    return nom or "(non renseigné)"

# ---------------------------------------------------------------------------
# Cellule 3. Outils de lecture
def get(d, *chemin):
    for cle in chemin:
        if isinstance(d, list):
            d = d[-1] if d else None
        if not isinstance(d, dict):
            return None
        d = d.get(cle)
    return d

def trouver(obj, cle):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == cle:
                out.append(v)
            out += trouver(v, cle)
    elif isinstance(obj, list):
        for v in obj:
            out += trouver(v, cle)
    return out

def texte(x):
    if x is None:
        return ""
    if isinstance(x, list):
        return " / ".join(t for t in (texte(i) for i in x) if t)
    if isinstance(x, dict):
        return str(x.get("#text", "") or "")
    return str(x)

def dates_dans(obj):
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out += dates_dans(v)
    elif isinstance(obj, list):
        for v in obj:
            out += dates_dans(v)
    elif isinstance(obj, str):
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", obj) or None
        if m:
            out.append(obj[:10])
        else:
            m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", obj)
            if m:
                out.append(f"{m.group(3)}-{m.group(2)}-{m.group(1)}")
    return out

def premiere_date(q, bloc_liste, bloc):
    blocs = get(q, bloc_liste, bloc)
    blocs = blocs if isinstance(blocs, list) else [blocs]
    dates = [get(b, "infoJO", "dateJO") for b in blocs if b]
    dates = [d for d in (dates_dans(x) for x in dates if x) for d in d]
    if not dates:   # structure différente (archives anciennes) : toute date trouvée dans le bloc
        dates = dates_dans(get(q, bloc_liste))
    return min(dates) if dates else None

import html as _html
def nettoyer_html(s):
    # balises retirées, puis entités décodées (&#339; devient œ, &amp; devient &...)
    return _html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()

# ---------------------------------------------------------------------------
# Cellule 4. Aspiration, filtre et classement
import re as _re
def objet_depuis_texte(txt, longueur=140):
    """Objet d'une question, extrait de la formule « attire l'attention de ... sur ... »."""
    t = _re.sub(r"\s+", " ", txt or "").strip()
    m = _re.search(r"(?:attire|appelle|interroge|alerte|sollicite|prie|questionne).{0,300}?\b(?:sur|concernant|quant à)\s+(.+?)(?:\.\s|\.$|[;?!]|$)", t, _re.I)
    objet = m.group(1).strip() if m else t
    if len(objet) > longueur:
        objet = objet[:longueur].rsplit(" ", 1)[0] + "…"
    return objet[:1].upper() + objet[1:] if objet else ""

entieres = set(RUBRIQUES_ENTIERES); rubriques_filtrees = set(RUBRIQUES_FILTREES)
lignes, ecartees, illisibles = [], [], 0

total_lues = Counter()
volumes = Counter()
def toutes_questions():
    for leg, (zf, noms, fin) in archives.items():
        print(f"Lecture {leg}e législature...")
        for q in questions_de(zf, noms):
            yield leg, fin, q
for leg, fin_leg, q in toutes_questions():
    if not q:
        illisibles += 1
        continue
    total_lues[leg] += 1
    dq_tous = premiere_date(q, "textesQuestion", "texteQuestion")
    if dq_tous:
        volumes[(leg, dq_tous[:7])] += 1   # toutes rubriques confondues : dénominateur pour les comparaisons
    rub = (texte(get(q, "indexationAN", "rubrique")) or texte(trouver(q, "rubrique")[:1])).strip()
    rub_n = sans_accents(rub)
    if rub_n not in entieres and rub_n not in rubriques_filtrees:
        continue
    tete = texte(trouver(q, "teteAnalyse")).strip()      # recherche dans toute la question :
    analyse = texte(trouver(q, "analyse")).strip()       # les archives ne rangent pas toutes ces champs au même endroit
    titre = _html.unescape(" : ".join(t for t in [tete, analyse] if t and t.lower() != rub.lower()))
    txt_q = nettoyer_html(texte(get(q, "textesQuestion", "texteQuestion", "texte")))
    titre_source = "officiel" if titre else "extrait du texte"
    if not titre:
        titre = objet_depuis_texte(txt_q)
    titre_n, texte_n = sans_accents(titre), sans_accents(txt_q)
    corpus = titre_n + " " + texte_n
    if rub_n in rubriques_filtrees and not admis_rubrique_large(titre_n, texte_n):
        ecartees.append((rub, titre))
        continue
    themes, declencheurs = classer(titre_n, texte_n)
    if rub_n in rubriques_filtrees and not themes:
        ecartees.append((rub, titre))   # rubrique large sans aucun thème : hors périmètre
        continue
    lois = sorted(set(normaliser_loi(x) for x in re.findall(r"\bloi n\W{0,3}\s*(\d{4}-\d{2,4})\b", corpus)))  # numéros de lois cités (ex. 2021-1539)
    sig = q.get("signalement") or next((x for x in trouver(q, "signalement") if x), None)
    dates_sig = dates_dans(sig) if sig else []
    uid = texte(q.get("uid"))
    min_attr = texte(get(q, "minAttribs", "minAttrib", "denomination", "developpe"))
    lignes.append({
        "uid": uid,
        "legislature": leg,
        "fin_legislature": fin_leg,
        "numero": texte(get(q, "identifiant", "numero")),
        "titre": titre,
        "titre_source": titre_source,
        "themes": " | ".join(themes) if themes else ("Chasse et pêche de loisir" if rub_n == "chasse et peche" else "À classer"),
        "declencheurs": " ; ".join(declencheurs),
        "lois_citees": ", ".join(lois),
        "rubrique_AN": rub,
        "ministere": famille_ministere(min_attr),
        "ministere_intitule_officiel": min_attr,
        "groupe_auteur": texte(get(q, "auteur", "groupe", "abrege")),
        "date_question": premiere_date(q, "textesQuestion", "texteQuestion"),
        "date_reponse": premiere_date(q, "textesReponse", "texteReponse"),
        "cloture": texte(get(q, "cloture", "libelleCloture")),
        "signalee": bool(sig),
        "date_signalement": min(dates_sig) if dates_sig else None,
        "texte_question": txt_q,
        "texte_reponse": nettoyer_html(texte(get(q, "textesReponse", "texteReponse", "texte"))),
        "lien": f"https://www.assemblee-nationale.fr/dyn/{leg}/questions/{uid}" if uid else "",
    })

df = pd.DataFrame(lignes)
print("Questions lues par législature :", dict(total_lues))
print(f"{len(df)} questions retenues sur {sum(total_lues.values())}, {len(ecartees)} écartées par le filtre, {illisibles} fichiers illisibles")

# Contrôle et déduplication : les valeurs vides ne sont jamais comptées comme doublons.
def masque_doublons(colonnes):
    presentes = df[colonnes].notna().all(axis=1)
    for c in colonnes:
        presentes &= df[c].astype(str).str.strip().ne("")
    return presentes & df.duplicated(colonnes, keep=False)

doublons_uid = masque_doublons(["uid"])
doublons_numero = masque_doublons(["numero"])
doublons_leg_numero = masque_doublons(["legislature", "numero"])
print("\nContrôle des doublons (lignes concernées, doublon compris) :")
print(f"  uid : {int(doublons_uid.sum())}")
print(f"  numéro : {int(doublons_numero.sum())}")
print(f"  (législature, numéro) : {int(doublons_leg_numero.sum())}")

# Un numéro peut légitimement réapparaître dans des législatures différentes.
# La déduplication statistique repose donc sur uid, puis sur (législature, numéro).
avant_dedup = len(df)
uid_present = df["uid"].notna() & df["uid"].astype(str).str.strip().ne("")
df = df[~(uid_present & df.duplicated("uid", keep="first"))].copy()
cle_present = df[["legislature", "numero"]].notna().all(axis=1) & df["numero"].astype(str).str.strip().ne("")
df = df[~(cle_present & df.duplicated(["legislature", "numero"], keep="first"))].copy()
print(f"Questions uniques conservées pour les statistiques : {len(df)} (doublons retirés : {avant_dedup - len(df)})")

# ---------------------------------------------------------------------------
# Cellule 5. Délais : règle des deux mois et règle des dix jours après signalement
aujourdhui = date_reference(ARGS.date_reference)   # carnet : pd.Timestamp.today().normalize()
for c in ["date_question", "date_reponse", "date_signalement"]:
    df[c] = pd.to_datetime(df[c], errors="coerce")
df["echeance_legale"] = df["date_question"] + pd.DateOffset(months=DELAI_LEGAL_MOIS)

def statut(l):
    if pd.isna(l.date_question):
        return "Date manquante"
    if pd.notna(l.date_reponse):
        return "Répondue dans le délai" if l.date_reponse <= l.echeance_legale else "Répondue en retard"
    if l.cloture and "fin de mandat" in sans_accents(l.cloture):
        return "Close sans réponse (fin de mandat)"
    if l.cloture and "reponse" not in sans_accents(l.cloture):
        return "Close sans réponse"
    if pd.notna(l.fin_legislature):
        return "Close sans réponse (fin de législature)"
    return "En attente, délai dépassé" if aujourdhui > l.echeance_legale else "En attente, dans le délai"

df["fin_legislature"] = pd.to_datetime(df["fin_legislature"], errors="coerce")
df["statut"] = df.apply(statut, axis=1)
# le compteur s'arrête à la réponse, sinon à la fin de la législature, sinon aujourd'hui
fin = df["date_reponse"].fillna(df["fin_legislature"]).fillna(aujourdhui)
df["delai_jours"] = (fin - df["date_question"]).dt.days
df["retard_jours"] = (fin - df["echeance_legale"]).dt.days.clip(lower=0)
ferme = df["statut"].str.startswith("Close sans réponse")
df.loc[ferme, ["delai_jours", "retard_jours"]] = None

df["echeance_signalement"] = df["date_signalement"] + pd.Timedelta(days=DELAI_SIGNALEMENT_JOURS)
def statut_sig(l):
    if pd.notna(l.date_signalement) and l.date_signalement < REFORME_REGLEMENT_2014:
        return "Signalée avant 2014, règle des 10 jours non applicable"
    if pd.isna(l.date_signalement):
        return "Signalée, date introuvable" if l.signalee else ""
    if pd.notna(l.date_reponse):
        return "Réponse sous 10 jours" if l.date_reponse <= l.echeance_signalement else "Réponse après 10 jours"
    if pd.notna(l.fin_legislature):
        return "Sans réponse, close en fin de législature"
    return "Sans réponse, délai dépassé" if aujourdhui > l.echeance_signalement else "Sans réponse, dans le délai"
df["statut_signalement"] = df.apply(statut_sig, axis=1)
df["regle_delai"] = df["date_question"].map(lambda d: "1 mois + 1 sur demande (maximum retenu : 2 mois)"
    if pd.notna(d) and d < REFORME_REGLEMENT_2014 else "2 mois")
df["periode_2015"] = df["date_question"].map(lambda d: "" if pd.isna(d) else
    ("Avant la reconnaissance de 2015" if d < RECONNAISSANCE_SENSIBILITE else "Après la reconnaissance de 2015"))
df = df.sort_values("date_question", ascending=False)

# ---------------------------------------------------------------------------
# Cellule 5 bis. Harmonisations finales (ajout, ne modifie aucune cellule existante)
aujourdhui = date_reference(ARGS.date_reference)   # carnet : pd.Timestamp.now().normalize()

# Les questions closes en fin de mandat ou de législature n'ont pas de délai à mesurer
fermees = df["statut"].str.startswith("Close sans réponse", na=False)
df.loc[fermees, ["delai_jours", "retard_jours"]] = None

# Échéance de signalement jamais avant la date de la question
df.loc[df["echeance_signalement"] < df["date_question"], "echeance_signalement"] = pd.NaT

print("Harmonisations appliquées :", fermees.sum(), "questions closes sans délai à mesurer")

# ---------------------------------------------------------------------------
# Cellule 6. Rapport de contrôle du filtre et du classement
print("Questions retenues par législature :")
print(df["legislature"].value_counts().sort_index().to_string())
print("\nStatuts par législature :")
print(pd.crosstab(df["statut"], df["legislature"]).to_string())
print("\nAvant / après la loi du 16 février 2015 (14e législature uniquement, mêmes députés) :")
q14 = df[df["legislature"] == 14]
if len(q14):
    duree = {"Avant la reconnaissance de 2015": (RECONNAISSANCE_SENSIBILITE - pd.Timestamp("2012-06-20")).days / 365.25,
             "Après la reconnaissance de 2015": (pd.Timestamp("2017-06-20") - RECONNAISSANCE_SENSIBILITE).days / 365.25}
    vol14 = pd.Series({m: n for (l, m), n in volumes.items() if l == 14})
    tot = {"Avant la reconnaissance de 2015": vol14[vol14.index < "2015-02"].sum() + vol14.get("2015-02", 0) * 15 / 28,
           "Après la reconnaissance de 2015": vol14[vol14.index > "2015-02"].sum() + vol14.get("2015-02", 0) * 13 / 28}
    for p, n in q14["periode_2015"].value_counts().items():
        part = n / tot[p] if tot[p] else float("nan")
        print(f"  {p} : {n} questions, soit {n / duree[p]:.0f} par an, et {part:.2%} de toutes les questions écrites de la période")
    ex14 = q14.assign(theme=q14["themes"].str.split(" \\| ")).explode("theme").reset_index(drop=True)
    print(pd.crosstab(ex14["theme"], ex14["periode_2015"]).to_string())
print("\nQuestions retenues par rubrique d'origine :")
print(df["rubrique_AN"].value_counts().to_string())
print("\nQuestions par thème (une question peut en avoir plusieurs) :")
print(df["themes"].str.split(" \\| ").explode().value_counts().to_string())

print("\n--- Échantillon écarté des rubriques larges (vérifier qu'aucune ne parle du sort des animaux) ---")
for rub, titre in pd.Series(ecartees).sample(min(20, len(ecartees)), random_state=1):
    print(f"  [{rub}] {titre}")

print("\n--- Échantillon retenu des rubriques larges (vérifier qu'elles parlent bien du sort des animaux) ---")
larges = df[df["rubrique_AN"].map(sans_accents).isin(rubriques_filtrees)]
for _, l in larges.sample(min(20, len(larges)), random_state=1).iterrows():
    print(f"  [{l.rubrique_AN}] {l.titre}  ->  {l.declencheurs[:90]}")

a_classer = df[df["themes"] == "À classer"]
print(f"\n--- À classer : {len(a_classer)} questions ---")
for t in a_classer["titre"].head(25):
    print("  " + t)

print("\nLois les plus citées (pont vers la brique décrets d'application) :")
print(df["lois_citees"].str.split(", ").explode().replace("", None).dropna().value_counts().head(10).to_string())
print("\nSignalements :")
print(df.loc[df["signalee"], "statut_signalement"].value_counts().to_string())

# ---------------------------------------------------------------------------
# Cellule 7. Synthèse des délais par thème et par ministère
rep = df[df["date_reponse"].notna()]
print(f"Réponses dans le délai légal : {(rep['statut']=='Répondue dans le délai').mean():.0%} ; délai médian {rep['delai_jours'].median():.0f} jours")
ex = df.assign(theme=df["themes"].str.split(" \\| ")).explode("theme")
synth = ex.groupby("theme").agg(questions=("numero", "count"),
    en_attente_hors_delai=("statut", lambda s: (s == "En attente, délai dépassé").sum()),
    delai_median_jours=("delai_jours", "median")).sort_values("questions", ascending=False)
print(synth.to_string())
print(df.groupby("ministere")["statut"].value_counts().unstack(fill_value=0).to_string())

# ---------------------------------------------------------------------------
# Cellule 8. Export (dans un nouveau dossier daté, jamais d'écrasement)
SORTIE = dossier_sortie("brique1")
vol = pd.DataFrame([(l, m, n) for (l, m), n in sorted(volumes.items())], columns=["legislature", "mois", "questions_toutes_rubriques"])
vol.to_csv(os.path.join(SORTIE, "volumes_questions_ecrites_par_mois.csv"), index=False, encoding="utf-8-sig", sep=";")
nom = "questions_ecrites_animaux_2012_2026_v13.csv"
df.to_csv(os.path.join(SORTIE, nom), index=False, encoding="utf-8-sig", sep=";")
print(f"Fichier écrit : {os.path.join(SORTIE, nom)}")

# Cellule 9. Échantillon pour révision
df.sample(20, random_state=42).to_csv(os.path.join(SORTIE, "echantillon_pour_revision.csv"), index=False)
print("Échantillon de 20 lignes écrit, prêt pour la révision")
