"""Brique 2, version 4 : échéanciers d'application des lois qui concernent les animaux (DOLE).

CHANGELOG version 4
- Une loi n'est « Loi suivie » que si au moins une de ses mesures concerne les animaux
  (colonne concerne_animaux). Sinon elle devient « Texte lié ». Sans cette règle, la loi de 2005
  sur les territoires ruraux (75 mesures, aucune animale) et la loi 2015-177 (11 mesures, aucune
  animale) étaient suivies. Les statistiques de délai ne changent pas : elles portaient déjà
  uniquement sur les mesures qui concernent les animaux.
- Fichiers produits : echeanciers_lois_animaux_v4.csv et lois_animaux_v4.csv.

Version 3 (gelée) : transposition à logique identique du carnet reference/brique2_echeanciers_v3.ipynb,
vérifiée cellule par cellule contre les sorties Colab. Chaque bloc « Cellule » reprend la cellule
du même numéro.

Seuls changements par rapport au carnet, sans effet sur les résultats :
- archive rangée dans donnees_brutes/dole/ ; sorties écrites dans un nouveau dossier
  sorties/AAAA-MM-JJ_HHhMM_brique2/ (jamais d'écrasement) ;
- le CSV de la brique 1 est pris dans la dernière sortie de la brique 1 (ou via --questions),
  au lieu d'être déposé à la main dans Colab ;
- retrait de ce qui est propre à Colab (files.download) ;
- option --date-reference pour fixer « aujourd'hui » et comparer avec une exécution passée.

Usage :
    python scripts/brique2_echeanciers.py
    python scripts/brique2_echeanciers.py --questions reference/sorties_colab/questions_ecrites_animaux_2012_2026_v13.csv
"""
import argparse, glob

from commun import DONNEES_BRUTES, SORTIES, console_utf8, date_reference, dossier_sortie

console_utf8()
parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--questions", default=None,
                    help="CSV de la brique 1 (par défaut : le plus récent dans sorties/*_brique1/)")
parser.add_argument("--date-reference", default=None, help="date du jour à utiliser, AAAA-MM-JJ")
ARGS = parser.parse_args()
if ARGS.questions is None:
    candidats = sorted(glob.glob(f"{SORTIES}/*_brique1/questions_ecrites_animaux_2012_2026_v14.csv"))
    ARGS.questions = candidats[-1] if candidats else "questions_ecrites_animaux_2012_2026_v14.csv"

# ---------------------------------------------------------------------------
# Cellule 1. Téléchargement de l'archive DOLE (reprise automatique après coupure)
import os, re, time, tarfile, io, requests
import xml.etree.ElementTree as ET
from collections import Counter
import pandas as pd

BASE_DOLE = "https://echanges.dila.gouv.fr/OPENDATA/DOLE/"
DOSSIER = os.path.join(DONNEES_BRUTES, "dole")
os.makedirs(DOSSIER, exist_ok=True)

# Lois les plus citées dans les questions écrites animales (colonne lois_citees de la brique 1)
# Second filet : lois citées dans au moins 3 questions écrites animales (brique 1, V13).
# Si le CSV de la brique 1 est présent, la liste est recalculée ; sinon on garde celle-ci.
SEUIL_CITATIONS = 3
LOIS_REPEREES = ["2021-1539", "2025-237", "2016-1087", "2018-938", "2015-177", "2005-157", "2008-1545"]
try:
    _qe = pd.read_csv(ARGS.questions, sep=";", encoding="utf-8-sig", dtype=str).fillna("")
    _s = _qe["lois_citees"].str.split(", ").explode()
    _vc = _s[_s != ""].value_counts()
    LOIS_REPEREES = sorted(set(_vc[_vc >= SEUIL_CITATIONS].index))
    print("CSV de la brique 1 lu :", ARGS.questions)
    print("Lois citées au moins", SEUIL_CITATIONS, "fois (recalculé) :", LOIS_REPEREES)
except FileNotFoundError:
    print("CSV de la brique 1 absent : liste de lois citées par défaut", LOIS_REPEREES)
# Exclusions décidées : lois sans rapport avec le sort des animaux malgré leurs citations ou leur titre
LOIS_EXCLUES = {"2023-1322": "loi de finances pour 2024, sans mesure d'application animale",
                "2016-1086": "loi organique sur la présidence de l'Agence française pour la biodiversité"}

index = requests.get(BASE_DOLE, timeout=60).text
archives = sorted(set(re.findall(r'href="([^"]*[Ff]reemium[^"]*\.tar\.gz)"', index)))
print("Archives complètes disponibles :", archives)
if not archives:
    raise RuntimeError("Aucune archive complète trouvée : la page a peut-être changé de forme.")
nom_archive = archives[-1]
chemin = os.path.join(DOSSIER, nom_archive)

def telecharger(url, chemin, echecs_max=10):
    echecs = 0
    while True:
        deja = os.path.getsize(chemin) if os.path.exists(chemin) else 0
        entetes = {"Range": f"bytes={deja}-"} if deja else {}
        try:
            with requests.get(url, headers=entetes, stream=True, timeout=(30, 120)) as r:
                if r.status_code == 416:
                    return
                r.raise_for_status()
                reprise = r.status_code == 206
                total = int(r.headers.get("Content-Length", 0)) + (deja if reprise else 0)
                recu, palier = (deja if reprise else 0), 0
                with open(chemin, "ab" if reprise else "wb") as f:
                    for bloc in r.iter_content(chunk_size=1 << 20):
                        f.write(bloc); recu += len(bloc)
                        if total and recu * 10 // total > palier:
                            palier = recu * 10 // total
                            print(f"    {palier * 10} % ({recu / 1e6:.0f} Mo / {total / 1e6:.0f} Mo)")
                if not total or recu >= total:
                    return
        except requests.RequestException as e:
            actuel = os.path.getsize(chemin) if os.path.exists(chemin) else 0
            echecs = 0 if actuel > deja else echecs + 1
            print(f"    coupure à {actuel / 1e6:.0f} Mo, reprise ({echecs}/{echecs_max} sans progrès)")
            if echecs >= echecs_max:
                raise RuntimeError("Téléchargement interrompu : relancer le script, il reprendra où il s'est arrêté.")
            time.sleep(min(3 + 2 * echecs, 30))

if os.path.exists(chemin) and tarfile.is_tarfile(chemin):
    print("Archive déjà présente :", nom_archive)
else:
    print("Téléchargement de", nom_archive)
    telecharger(BASE_DOLE + nom_archive, chemin)
print(f"{os.path.getsize(chemin) / 1e6:.0f} Mo sur le disque")

# ---------------------------------------------------------------------------
# Cellule 2. Sélection des lois : les plus citées dans les questions, et toutes celles dont le titre parle d'animaux
import unicodedata
# NB (repéré à la transposition, conservé tel quel) : cette première version de sans_accents ne réduit pas
# les espaces et ne remplace pas l'apostrophe courbe. Elle sert à la sélection des lois ; la cellule 2 bis
# la remplace ensuite par la version complète de la brique 1, utilisée pour tout le reste.
def sans_accents(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
MOTS_TITRE = re.compile(r"\b(animal|animaux|animale|animales|bien-etre animal|maltraitance animale|chasse|faune|especes? sauvages?|frelon|abeilles?|elevage|biodiversite)\b")

def texte_complet(el):
    return re.sub(r"\s+", " ", "".join(el.itertext()).replace("&#xD;", " ")).strip() if el is not None else ""

dossiers = []
with tarfile.open(chemin, "r:gz") as tar:
    for m in tar:
        if not (m.isfile() and m.name.lower().endswith(".xml")):
            continue
        brut = tar.extractfile(m).read()
        try:
            racine = ET.fromstring(brut)
        except ET.ParseError:
            continue
        titre = texte_complet(racine.find(".//META_DOSSIER_LEGISLATIF/TITRE"))
        type_ = texte_complet(racine.find(".//META_DOSSIER_LEGISLATIF/TYPE"))
        num = re.search(r"n°\s*(\d{4}-\d{1,4})", titre)
        num = num.group(1) if num else ""
        if num in LOIS_EXCLUES:
            continue
        citee = num in LOIS_REPEREES
        if not (citee or MOTS_TITRE.search(sans_accents(titre))):
            continue
        dossiers.append({"racine": racine, "titre": titre, "type": type_, "numero": num, "citee_questions": citee})
print(f"{len(dossiers)} dossiers retenus")
for d in sorted(dossiers, key=lambda d: d["titre"])[:60]:
    print(f"  {'*' if d['citee_questions'] else ' '} [{d['type']}] {d['titre'][:130]}")
print("(* = loi citée dans les questions écrites)")

# ---------------------------------------------------------------------------
# Cellule 2 bis. Règles de thèmes de la brique 1 (reprises telles quelles)
import re, unicodedata
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
    # NB : même motif r"dissequ\\w*" inopérant que dans la brique 1, conservé tel quel.
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
# Cellule 3. Extraction des échéanciers
MOIS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
def date_loi(titre):
    m = re.search(r"du (1er|\d{1,2}) (\w+) (\d{4})", sans_accents(titre))
    if not m or m.group(2) not in MOIS:
        return None
    jour = 1 if m.group(1) == "1er" else int(m.group(1))
    return pd.Timestamp(int(m.group(3)), MOIS[m.group(2)], jour)

# Qualification de chaque mesure : le champ DECRET contient parfois un décret, parfois une annonce ou une explication
MOIS_NUM = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
            "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
LOI_ANIMALE = re.compile(r"\b(animal|animaux|animale|maltraitance|chasse|chasseurs|faune|frelon|apicole|abeilles?)\b")

def dates_textuelles(t):
    t = sans_accents(t)
    out = []
    for j, m, a in re.findall(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", t):
        a = int(a) + (2000 if len(a) == 2 else 0)
        out.append(pd.Timestamp(a, int(m), int(j)))
    for j, m, a in re.findall(r"(1er|\d{1,2}) (" + "|".join(MOIS_NUM) + r") (\d{4})", t):
        out.append(pd.Timestamp(int(a), MOIS_NUM[m], 1 if j == "1er" else int(j)))
    return out

def annonce_date(t):
    """Date annoncée dans « Publication envisagée en décembre 2022 », « fin 2019 », « le 15/01/2020 »..."""
    t = sans_accents(t)
    d = dates_textuelles(t)
    if d:
        return d[0]
    m = re.search(r"(" + "|".join(MOIS_NUM) + r") (\d{4})", t)
    if m:
        return pd.Timestamp(int(m.group(2)), MOIS_NUM[m.group(1)], 1) + pd.offsets.MonthEnd(0)
    m = re.search(r"fin (\d{4})", t)
    if m:
        return pd.Timestamp(int(m.group(1)), 12, 31)
    return None

def qualifier(decret, maj):
    t = sans_accents(decret)
    if not t:
        return "Aucune mention", None, None
    if re.search(r"deja appliquee|voir le decret|appliquee par", t):
        return "Appliquée par un texte existant", None, None
    if re.search(r"pas necessaire|n.est plus|base legale a ete modifiee|sans objet", t):
        return "Sans objet", None, None
    if "envisagee" in t:
        a = annonce_date(t)
        maj_ts = pd.Timestamp(maj) if maj else None
        if a is not None and maj_ts is not None and a < maj_ts:
            return "Publication annoncée, date dépassée à la mise à jour de l'échéancier", None, a
        return "Publication annoncée", None, a
    if re.match(r"\s*(decret|arrete|ordonnance)", t):
        d = dates_textuelles(t)
        return "Décret publié", (min(d) if d else None), None
    return "À examiner", None, None

aujourdhui = date_reference(ARGS.date_reference)   # carnet : pd.Timestamp.today().normalize()
lignes, lois = [], []
for d in dossiers:
    r = d["racine"]
    promulgation = date_loi(d["titre"])
    d["loi_animale"] = bool(LOI_ANIMALE.search(sans_accents(d["titre"])))
    ech = r.find(".//ECHEANCIER")
    maj = ech.get("derniere_maj") if ech is not None else None
    mesures = ech.findall("LIGNE") if ech is not None else []
    mesures_animales = 0   # V4 : sert à décider si la loi est suivie
    for l in mesures:
        decret = texte_complet(l.find("DECRET"))
        objet = texte_complet(l.find("OBJET"))
        statut, date_decret, annonce = qualifier(decret, maj)
        cid = texte_complet(l.find("CID_LOI_CIBLE"))
        publie = statut == "Décret publié"
        themes = classer(sans_accents(objet + " " + texte_complet(l.find("BASE_LEGALE"))), "")[0]
        mesures_animales += bool(d["loi_animale"] or themes)
        lignes.append({
            "loi_numero": d["numero"], "loi_titre": d["titre"], "loi_promulgation": promulgation,
            "citee_dans_questions": d["citee_questions"],
            "numero_ordre": texte_complet(l.find("NUMERO_ORDRE")),
            "article": texte_complet(l.find("ARTICLE")),
            "base_legale": texte_complet(l.find("BASE_LEGALE")),
            "objet": objet,
            "themes": " | ".join(themes),
            "concerne_animaux": d["loi_animale"] or bool(themes),
            "decret": decret, "decret_date": date_decret,
            "decret_lien": f"https://www.legifrance.gouv.fr/jorf/id/{cid}" if cid.startswith("JORFTEXT") else "",
            "date_prevue": texte_complet(l.find("DATE_PREVUE")),
            "statut": statut,
            "publication_annoncee": annonce,
            "delai_jours": (date_decret - promulgation).days if (publie and date_decret is not None and promulgation is not None) else None,
            "jours_depuis_promulgation": (aujourdhui - promulgation).days if (statut.startswith("Publication annoncée") and promulgation is not None) else None,
            "echeancier_mis_a_jour": maj,
        })
    lois.append({"loi_numero": d["numero"], "loi_titre": d["titre"], "type": d["type"], "promulgation": promulgation,
                 "citee_dans_questions": d["citee_questions"], "mesures": len(mesures),
                 "loi_entierement_animale": d["loi_animale"],
                 "echeancier_present": len(mesures) > 0,
                 # loi suivie = loi publiée avec un échéancier dont au moins une mesure concerne les animaux (V4) ;
                 # texte lié = ordonnance, projet, proposition, loi sans échéancier, ou loi sans mesure animale
                 "role": "Loi suivie" if (d["type"] == "LOI_PUBLIEE" and mesures_animales > 0) else "Texte lié",
                 "proposition_non_adoptee": d["type"] == "PROPOSITION_LOI",
                 "echeancier_mis_a_jour": maj,
                 "lien_legifrance": f"https://www.legifrance.gouv.fr/jorf/id/{texte_complet(r.find('.//ID_TEXTE_1'))}"})

SORTIE = dossier_sortie("brique2")
ech = pd.DataFrame(lignes)
lois_df = pd.DataFrame(lois).sort_values("promulgation", ascending=False)
ech.to_csv(os.path.join(SORTIE, "echeanciers_lois_animaux_v4.csv"), index=False, encoding="utf-8-sig", sep=";")
lois_df.to_csv(os.path.join(SORTIE, "lois_animaux_v4.csv"), index=False, encoding="utf-8-sig", sep=";")
print(f"{len(lois_df)} lois, {len(ech)} mesures d'application")
print("Fichiers écrits dans", SORTIE)

# ---------------------------------------------------------------------------
# Cellule 4. Contrôle
print("Lois citées dans les questions :")
print(lois_df[["loi_numero", "type", "role", "citee_dans_questions", "mesures", "echeancier_mis_a_jour"]].to_string(index=False))
if len(ech):
    print("\nStatut des mesures :")
    print(pd.crosstab(ech["statut"], ech["concerne_animaux"]).to_string())
    ech_a = ech[ech["concerne_animaux"]]
    pub = ech_a[ech_a["delai_jours"].notna()]
    if len(pub):
        print(f"\nDélai médian entre promulgation et décret : {pub['delai_jours'].median():.0f} jours")
        print(f"Part des décrets publiés sous six mois (183 jours) : {(pub['delai_jours'] <= 183).mean():.0%}")
    print("\nContrôle loi 2021-1539 :")
    t = ech[ech["loi_numero"] == "2021-1539"][["numero_ordre", "article", "decret", "delai_jours", "statut", "publication_annoncee"]]
    print(t.to_string(index=False))
print("\nMesures dont la publication était annoncée :")
print(ech[ech["statut"].str.startswith("Publication annoncée")][["loi_numero", "numero_ordre", "publication_annoncee", "echeancier_mis_a_jour", "objet"]].to_string(index=False))
