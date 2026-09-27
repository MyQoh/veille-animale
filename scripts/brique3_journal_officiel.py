"""Brique 3, version 1 : textes du Journal officiel qui concernent les animaux.

Source : jeu JORF de la DILA (données ouvertes, echanges.dila.gouv.fr/OPENDATA/JORF/) : une archive complète
(Freemium_jorf_global_*.tar.gz, 1,6 Go), puis deux mises à jour par jour (JORF_AAAAMMJJ-HHMMSS.tar.gz).
Chaque texte y figure en XML : nature, NOR, dates de signature et de publication, titre, ministère, visas,
articles, et liens vers les textes qu'il cite, modifie ou applique.

Sélection (règles transparentes, même esprit que la brique 1) :
- natures retenues : loi, ordonnance, décret, arrêté ; publiés depuis le 1er janvier 2012 ;
- le titre doit parler d'animaux (mots d'ancrage ci-dessous) ; un texte qui n'en parle que dans son contenu
  n'est pas retenu en version 1 (textes fourre-tout : loi de finances, codes, diplômes...) ;
- et relever d'au moins un des thèmes de la brique 1 (mêmes règles : scripts/regles_themes.py) ;
- sont écartés et comptés : textes de personnel (nominations, retraites, concours...) ; hygiène et commerce des
  denrées, signes de qualité, accords entre professionnels.
Chaque texte retenu garde le mot qui l'a fait entrer (ancrage) et ceux qui ont déclenché ses thèmes.

Le lien « APPLICATION » du Journal officiel indique, pour un décret ou un arrêté, la loi et l'article qu'il
applique : c'est le pont entre une loi (brique 2) et ses textes d'application (colonne lois_appliquees).
Ce lien n'est pas toujours renseigné (par exemple pour le décret frelon de décembre 2025) : les lois citées
par le texte, notamment dans ses visas, sont donc gardées à part (colonne lois_citees), lien plus faible.

Fonctionnement « une archive, une analyse » : chaque archive (la complète puis chaque mise à jour) n'est analysée
qu'une fois ; le résultat est gardé dans donnees_brutes/jorf/extraits/, avec l'empreinte des règles. Si les règles
changent, tout est réanalysé. Le résultat final réunit toutes les analyses (la version la plus récente d'un texte
l'emporte).

Usage :
    python scripts/brique3_journal_officiel.py                          # historique complet depuis 2012 + mises à jour
    python scripts/brique3_journal_officiel.py --periodes 2026-08-15:2026-09-26   # échantillon : mises à jour seules
"""
import argparse, glob, hashlib, inspect, os, re, tarfile, time
import xml.etree.ElementTree as ET
from collections import Counter

import pandas as pd
import requests

import regles_themes
from commun import DONNEES_BRUTES, console_utf8, dossier_sortie
from regles_themes import classer, sans_accents

console_utf8()
p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--periodes", nargs="+", help="échantillon : périodes AAAA-MM-JJ:AAAA-MM-JJ (mises à jour seules)")
p.add_argument("--depuis", default="2012-01-01", help="date de publication minimale (historique complet)")
A = p.parse_args()

BASE = "https://echanges.dila.gouv.fr/OPENDATA/JORF/"
DOSSIER = os.path.join(DONNEES_BRUTES, "jorf")
EXTRAITS = os.path.join(DOSSIER, "extraits")
for d in ("maj", "extraits"):
    os.makedirs(os.path.join(DOSSIER, d), exist_ok=True)
NATURES = {"LOI", "ORDONNANCE", "DECRET", "ARRETE"}

# Mots d'ancrage : le titre doit parler d'animaux (sans accents, minuscules)
ANCRES = re.compile(r"\b(?:" + "|".join([
    r"animal", r"animaux", r"animales?", r"faune", r"gibiers?", r"chasse", r"chasseurs?", r"cynegetiques?",
    r"elevages?", r"eleveurs?", r"betail", r"cheptels?", r"bovins?", r"bovines?", r"ovins?", r"caprins?", r"porcins?",
    r"volailles?", r"avicoles?", r"equides?", r"chevaux", r"chiens?", r"chats?", r"abeilles?", r"apicoles?",
    r"loups?", r"ours", r"lynx", r"frelons?", r"oiseaux", r"rapaces?", r"cetaces?", r"veterinaires?", r"zoonoses?",
    r"epizooties?", r"abattoirs?", r"abattage", r"influenza aviaire", r"peste porcine", r"tuberculose bovine",
    r"fievre catarrhale", r"dermatose nodulaire", r"especes? protegees?", r"especes? sauvages?",
    r"especes? exotiques envahissantes", r"susceptibles? d.occasionner des degats", r"cirques?", r"delphinariums?",
    r"zoos?", r"experimentation animale", r"piegeage"]) + r")\b")
SEUIL_ANCRES_TEXTE = 3   # sert seulement au comptage de contrôle : en version 1, le titre doit parler d'animaux
# Titres qui contiennent un mot d'ancrage sans parler du sort des animaux : hygiène et commerce des denrées,
# signes de qualité (labels, appellations), accords entre professionnels. Le titre entier est alors écarté.
HORS_PERIMETRE_TITRE = re.compile(r"d.origine animale|denrees? (?:alimentaires? )?(?:d.origine )?animales?|"
                                  r"produits? (?:d.origine )?animaux|sous.produits? animaux|proteines? animales?|"
                                  r"cahier des charges|label rouge|appellation d.origine|indication geographique|"
                                  r"accord interprofessionnel|convention collective|extension (?:d.un |de l.)?(?:accord|avenant)|"
                                  # arts du cirque, courses hippiques, pêche et élevages marins, aides économiques
                                  r"arts? du cirque|professeur de cirque|ecoles? de cirque|courses (?:de chevaux|hippiques)|"
                                  r"calendrier des courses|paris hippiques|elevages? marins|conchylic\w*|aquacoles?|"
                                  r"peches? maritimes?|comites? (?:\w+ )?des peches|aide a l.importation|restructuration|"
                                  # règle du 27/09/2026 : l'économie et l'organisation des filières restent dehors,
                                  # sauf quand l'argent sert directement le sort des animaux (indemnisation, protection)
                                  r"organismes? de selection|stud.book|livres? genealogiques?|commercialisation du betail|"
                                  r"certificats? de specialisation|carcasses|visceres|"
                                  r"(?:statuts?|ressources|charges|aide financiere|cotisations?)\b.{0,60}federations?|"
                                  r"federations?.{0,60}\b(?:statuts?|ressources|aide financiere|cotisations?)\b|"
                                  # noms de lieux contenant un nom d'animal (La Colle-sur-Loup...)
                                  r"\w+.sur.loup|saint.loup|chanteloup|station de tourisme|classement de la commune|"
                                  # sites géographiques, épargne salariale, financements entre organismes publics
                                  r"parmi les sites|sites? classes?|epargne salariale|agences? de l.eau|contribution financiere")
# « code rural et de la pêche maritime » : nom d'un code, retiré avant de chercher « pêche maritime » ci-dessus
CODE_RURAL = re.compile(r"code rural et de la peche maritime")
# Textes individuels et de personnel : écartés (ils citeraient « vétérinaire » ou « chasse » sans concerner les animaux)
PERSONNEL = re.compile(r"\b(?:nomination|nommes?|cessation de fonctions|tableau d.avancement|admission a la retraite|"
                       r"concours|examen professionnel|liste d.aptitude|jury|titularisation|delegation de signature|"
                       r"medailles?|inscription au tableau|"
                       # carrières, formations et organisation de la profession (surtout vétérinaire)
                       r"radiation des cadres|integration dans le corps|detachement|emplois? offerts?|nombre d.emplois|"
                       r"recrutement|corps des|grades?|academie|elections?|statuts? de l.association|association reconnue|"
                       r"diplomes?|enseignement|ecoles?|etudes|scolarite|internat|classes? preparatoires|classes accessibles|"
                       r"licence|master|doctorat|specialites? veterinaires|exercice de la (?:profession|medecine) veterinaire|"
                       r"ordre des veterinaires|entrepots? douaniers|"
                       # rémunérations, statuts et conditions de travail des agents
                       r"demission|radiation|echelonnement indiciaire|statuts? particuliers?|cadres? d.emplois|"
                       r"conditions de travail|comites? d.hygiene|remunerations?|indemnites? (?:de|des|allouees?)|primes?|"
                       # organisation de la profession vétérinaire (règle du 27/09/2026)
                       r"integration|section professionnelle|caisses? (?:autonomes? )?de retraite|deontologie|"
                       r"exercice (?:professionnel|de la profession)|telemedecine)\b")
# Empreinte des règles : si elles changent (ici ou dans regles_themes.py), ou si le contenu des analyses change
# (FORMAT_EXTRAIT), toutes les archives sont réanalysées
FORMAT_EXTRAIT = "2"   # 2 : ajout des lois citées (lois_citees)
REGLES = hashlib.sha256((FORMAT_EXTRAIT + ANCRES.pattern + HORS_PERIMETRE_TITRE.pattern + CODE_RURAL.pattern + PERSONNEL.pattern + str(SEUIL_ANCRES_TEXTE)
                         + inspect.getsource(regles_themes)).encode("utf-8")).hexdigest()[:10]
# Textes cherchés à la main le 26/09/2026 : la brique doit les retrouver seule (test d'acceptation)
ATTENDUS = {
    "JORFTEXT000054728726": "Arrêté du 10 août 2026, liste des espèces susceptibles d'occasionner des dégâts",
    "JORFTEXT000054842308": "Arrêté du 9 septembre 2026, plan national de lutte contre le frelon asiatique",
    "JORFTEXT000053555244": "Arrêté du 23 février 2026, statut de protection du loup",
    "JORFTEXT000053555329": "Arrêté du 23 février 2026, plafond de destruction des loups",
    "JORFTEXT000053201550": "Décret n° 2025-1377 du 29 décembre 2025, plans de lutte contre le frelon asiatique",
}


def telecharger(nom, dossier):
    """Par morceaux, avec reprise après coupure (l'archive complète fait 1,6 Go)."""
    chemin = os.path.join(dossier, nom)
    if os.path.exists(chemin) and tarfile.is_tarfile(chemin):
        return chemin
    echecs = 0
    while True:
        deja = os.path.getsize(chemin) if os.path.exists(chemin) else 0
        entetes = {"Range": f"bytes={deja}-"} if deja else {}
        try:
            with requests.get(BASE + nom, headers=entetes, stream=True, timeout=(30, 300)) as r:
                if r.status_code != 416:
                    r.raise_for_status()
                    reprise = r.status_code == 206
                    with open(chemin, "ab" if reprise else "wb") as f:
                        for bloc in r.iter_content(chunk_size=1 << 20):
                            f.write(bloc)
            if tarfile.is_tarfile(chemin):
                return chemin
        except requests.RequestException as e:
            actuel = os.path.getsize(chemin) if os.path.exists(chemin) else 0
            echecs = 0 if actuel > deja else echecs + 1
            print(f"    coupure ({e.__class__.__name__}) à {actuel / 1e6:.0f} Mo, reprise")
            if echecs >= 10:
                raise RuntimeError(f"Téléchargement impossible : {nom}. Relancer : il reprendra où il s'est arrêté.")
        time.sleep(min(3 + 2 * echecs, 30))


def texte_de(el):
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def lire_version(r):
    appliquees = [{"texte": texte_de(l), "nature": l.get("naturetexte"), "numero": l.get("numtexte"), "article": l.get("num")}
                  for l in r.iter("LIEN") if l.get("typelien") == "APPLICATION" and l.get("sens") == "source"]
    # Lois citées par le texte (visas notamment) : lien plus faible que « application », présenté à part
    visees = sorted({l.get("numtexte") for l in r.iter("LIEN") if l.get("typelien") == "CITATION"
                     and l.get("sens") == "source" and l.get("naturetexte") == "LOI" and l.get("numtexte")})
    return {
        "visees": visees,
        "cid": texte_de(r.find(".//META_COMMUN/ID")),
        "nature": texte_de(r.find(".//META_COMMUN/NATURE")),
        "numero": texte_de(r.find(".//META_TEXTE_CHRONICLE/NUM")),
        "nor": texte_de(r.find(".//META_TEXTE_CHRONICLE/NOR")),
        "date_texte": texte_de(r.find(".//META_TEXTE_CHRONICLE/DATE_TEXTE")),
        "date_publication": texte_de(r.find(".//META_TEXTE_CHRONICLE/DATE_PUBLI")),
        "parution": texte_de(r.find(".//META_TEXTE_CHRONICLE/ORIGINE_PUBLI")),
        "titre": texte_de(r.find(".//META_TEXTE_VERSION/TITREFULL")),
        "ministere": texte_de(r.find(".//META_TEXTE_VERSION/MINISTERE")),
        "visas": texte_de(r.find("VISAS")),
        "applique": appliquees,
    }


def decision(t, corps_n):
    """Retenu ou raison d'écart, pour un texte dont on a la fiche et le contenu."""
    titre_n = sans_accents(t["titre"])
    ancre_titre = sorted(set(ANCRES.findall(titre_n)))
    if not ancre_titre:
        return ("mention_dans_le_contenu" if len(ANCRES.findall(corps_n)) >= SEUIL_ANCRES_TEXTE else None), None
    if HORS_PERIMETRE_TITRE.search(CODE_RURAL.sub("code rural", titre_n)):
        return "denrees_commerce", None
    if PERSONNEL.search(titre_n):
        return "personnel", None
    themes, declencheurs = classer(titre_n, corps_n)
    if not themes:
        return "sans_theme", None
    return "retenu", {
        **{k: t[k] for k in ("cid", "nature", "numero", "nor", "date_texte", "date_publication", "parution", "titre", "ministere")},
        "themes": " | ".join(themes), "declencheurs": " ; ".join(declencheurs),
        "ancrage": f"titre : {', '.join(ancre_titre[:4])}",
        "applique": " ; ".join(x["texte"] + (f" (art. {x['article']})" if x["article"] and "art." not in x["texte"] else "")
                               for x in t["applique"]),
        "lois_appliquees": ", ".join(sorted({x["numero"] for x in t["applique"] if x["nature"] == "LOI" and x["numero"]})),
        "lois_citees": ", ".join(t["visees"]),
        "lien": f"https://www.legifrance.gouv.fr/jorf/id/{t['cid']}",
    }


def analyser(chemin, depuis):
    """Analyse une archive. Deux passages : les fiches des textes, puis les articles des seuls textes candidats
    (titre parlant d'animaux), pour ne pas garder en mémoire les millions d'articles de l'archive complète."""
    fiches, lus = {}, Counter()
    with tarfile.open(chemin, "r:gz") as tar:
        for m in tar:
            if m.name.endswith(".xml") and "/texte/version/" in m.name and "JORFTEXT" in m.name:
                t = lire_version(ET.fromstring(tar.extractfile(m).read()))
                lus[t["nature"]] += 1
                # date fictive « 2999-01-01 » dans certaines fiches : écartée (publication future impossible)
                if t["nature"] in NATURES and depuis <= t["date_publication"] <= "2100-01-01":
                    fiches[t["cid"]] = t
    candidats = {cid for cid, t in fiches.items() if ANCRES.search(sans_accents(t["titre"]))}
    corps = {}
    with tarfile.open(chemin, "r:gz") as tar:
        for m in tar:
            if m.name.endswith(".xml") and "/article/" in m.name and "JORFARTI" in m.name:
                r = ET.fromstring(tar.extractfile(m).read())
                ctx = r.find(".//CONTEXTE/TEXTE")
                if ctx is not None and ctx.get("cid") in candidats:
                    corps.setdefault(ctx.get("cid"), []).append(texte_de(r.find("BLOC_TEXTUEL")))
    lignes = []
    for cid, t in fiches.items():
        # le comptage « mention dans le contenu » n'est fait que pour les candidats (sinon il faudrait tout garder en mémoire)
        etat, ligne = decision(t, sans_accents(t["visas"] + " " + " ".join(corps.get(cid, []))))
        if etat:
            lignes.append({"etat": etat, **(ligne or {"cid": cid, "nature": t["nature"], "titre": t["titre"],
                                                    "date_publication": t["date_publication"]})})
    return lignes, sum(lus.values()), len(fiches)


# ---------------------------------------------------------------------------
# 1. Archives à analyser
index = requests.get(BASE, timeout=60).text
maj = sorted(set(re.findall(r'href="(JORF_(\d{8})-\d{6}\.tar\.gz)"', index)))
complete = sorted(set(re.findall(r'href="(Freemium_jorf_global_(\d{8})-\d{6}\.tar\.gz)"', index)))
if A.periodes:
    periodes = [tuple(x.replace("-", "") for x in per.split(":")) for per in A.periodes]
    archives = [(nom, "maj") for nom, jour in maj if any(d <= jour <= f for d, f in periodes)]
    depuis = min(f"{d[:4]}-{d[4:6]}-{d[6:]}" for d, _ in periodes)
else:
    if not complete:
        raise RuntimeError("Archive complète du Journal officiel introuvable : la page de la DILA a peut-être changé.")
    nom_complete, jour_complete = complete[-1]
    archives = [(nom_complete, "complete")] + [(nom, "maj") for nom, jour in maj if jour >= jour_complete]
    depuis = A.depuis
print(f"Règles {REGLES} ; {len(archives)} archives à réunir (depuis le {depuis})")

# ---------------------------------------------------------------------------
# 2. Analyse (une seule fois par archive et par version des règles), puis réunion
resultats, total_lus, total_natures = [], 0, 0
for i, (nom, genre) in enumerate(archives, 1):
    extrait = os.path.join(EXTRAITS, f"{nom[:-7]}__{REGLES}__{depuis}.csv")
    if not os.path.exists(extrait):
        debut = time.time()
        chemin = telecharger(nom, DOSSIER if genre == "complete" else os.path.join(DOSSIER, "maj"))
        lignes, lus, gardes = analyser(chemin, depuis)
        pd.DataFrame(lignes).assign(archive=nom, textes_lus=lus, textes_depuis=gardes).to_csv(
            extrait, index=False, encoding="utf-8-sig", sep=";")
        print(f"  analysée : {nom} ({lus} textes, {len(lignes)} lignes, {time.time() - debut:.0f} s)")
    r = pd.read_csv(extrait, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    if len(r):
        total_lus += int(r["textes_lus"].iloc[0])
        resultats.append(r.assign(ordre=i))
    if i % 50 == 0:
        print(f"  {i}/{len(archives)} archives réunies")

tout = pd.concat(resultats) if resultats else pd.DataFrame(columns=["cid", "etat", "ordre"])
# Un texte peut revenir dans plusieurs archives (corrections). Une mise à jour peut renvoyer sa fiche sans ses
# articles : réanalysé sans contenu, il perdrait ses thèmes. On garde donc la plus récente des analyses qui l'ont
# retenu, et à défaut la plus récente tout court.
tout = (tout.assign(_retenu=(tout["etat"] == "retenu").astype(int))
            .sort_values(["_retenu", "ordre"]).drop_duplicates("cid", keep="last").drop(columns="_retenu"))
if A.periodes:
    fins = [f"{f[:4]}-{f[4:6]}-{f[6:]}" for _, f in periodes]
    debuts = [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d, _ in periodes]
    tout = tout[tout["date_publication"].map(lambda x: any(d <= x <= f for d, f in zip(debuts, fins)))]
df = tout[tout["etat"] == "retenu"].drop(columns=["etat", "ordre", "archive", "textes_lus", "textes_depuis"], errors="ignore")
df = df.sort_values("date_publication", ascending=False)

# ---------------------------------------------------------------------------
# 3. Contrôle
print(f"\nTextes retenus : {len(df)} (publiés depuis le {depuis})")
print("Écartés :", tout[tout["etat"] != "retenu"]["etat"].value_counts().to_dict())
if len(df):
    print("Par nature :", df["nature"].value_counts().to_dict())
    print("Par année de publication :", df["date_publication"].str[:4].value_counts().sort_index().to_dict())
    print("Par thème :")
    print(df["themes"].str.split(r" \| ").explode().value_counts().to_string())
    print("Avec un lien « applique » vers une loi :", int((df["lois_appliquees"] != "").sum()))
print("\n--- Test d'acceptation : textes cherchés à la main, retrouvés seuls ? ---")
for cid, libelle in ATTENDUS.items():
    etat = tout.loc[tout["cid"] == cid, "etat"]
    print(f"  {'RETROUVÉ' if (etat == 'retenu').any() else ('écarté : ' + etat.iloc[0] if len(etat) else 'hors des archives lues'):24s} {libelle}")
print("\n--- Échantillon retenu (vérifier qu'ils concernent bien les animaux) ---")
for _, l in df.sample(min(30, len(df)), random_state=1).iterrows():
    print(f"  {l.date_publication} [{l.nature}] {l.titre[:105]}  ->  {l.themes} ; {l.ancrage}")
for etat in ("sans_theme", "denrees_commerce", "personnel", "mention_dans_le_contenu"):
    e = tout[tout["etat"] == etat]
    print(f"\n--- Écartés « {etat} » : {len(e)} (échantillon) ---")
    for _, l in e.sample(min(10, len(e)), random_state=1).iterrows():
        print(f"  {l.date_publication} [{l.nature}] {l.titre[:110]}")

SORTIE = dossier_sortie("brique3")
df.to_csv(os.path.join(SORTIE, "textes_jo_animaux_v1.csv"), index=False, encoding="utf-8-sig", sep=";")
tout[tout["etat"] != "retenu"][["etat", "cid", "nature", "date_publication", "titre"]].to_csv(
    os.path.join(SORTIE, "controle_ecartes.csv"), index=False, encoding="utf-8-sig", sep=";")
print("\nFichiers écrits dans", SORTIE)
