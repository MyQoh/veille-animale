"""Brique 3, version 1 : textes du Journal officiel qui concernent les animaux.

Source : jeu JORF de la DILA (données ouvertes, echanges.dila.gouv.fr/OPENDATA/JORF/) : une archive complète
(Freemium_jorf_global_*.tar.gz), puis deux mises à jour par jour (JORF_AAAAMMJJ-HHMMSS.tar.gz).
Chaque texte y figure en XML : nature, NOR, dates de signature et de publication, titre, ministère, visas,
articles, et liens vers les textes qu'il cite, modifie ou applique.

Sélection (règles transparentes, même esprit que la brique 1) :
- natures retenues : loi, ordonnance, décret, arrêté ;
- le texte doit parler d'animaux : un mot d'ancrage animal dans le titre, ou au moins trois dans le texte ;
- et relever d'au moins un des thèmes de la brique 1 (mêmes règles : scripts/regles_themes.py) ;
- les textes individuels et de personnel (nominations, concours, avancements...) sont écartés, et comptés.
Chaque texte retenu garde le mot qui l'a fait entrer (ancrage) et ceux qui ont déclenché ses thèmes.

Le lien « APPLICATION » du Journal officiel indique, pour un décret ou un arrêté, la loi et l'article qu'il
applique : c'est le pont entre une loi (brique 2) et ses textes d'application.

Version 1 : lecture des mises à jour quotidiennes, sur des périodes choisies (--periodes). La lecture de
l'archive complète viendra quand la sélection sera validée sur échantillon.

Usage :
    python scripts/brique3_journal_officiel.py --periodes 2026-08-15:2026-09-26
"""
import argparse, io, os, random, re, tarfile, time
import xml.etree.ElementTree as ET
from collections import Counter

import pandas as pd
import requests

from commun import DONNEES_BRUTES, console_utf8, dossier_sortie
from regles_themes import classer, sans_accents

console_utf8()
p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--periodes", nargs="+", required=True, help="périodes AAAA-MM-JJ:AAAA-MM-JJ (dates des mises à jour)")
A = p.parse_args()

BASE = "https://echanges.dila.gouv.fr/OPENDATA/JORF/"
DOSSIER = os.path.join(DONNEES_BRUTES, "jorf", "maj")
os.makedirs(DOSSIER, exist_ok=True)
NATURES = {"LOI", "ORDONNANCE", "DECRET", "ARRETE"}

# Mots d'ancrage : le texte doit parler d'animaux (sans accents, minuscules)
ANCRES = re.compile(r"\b(?:" + "|".join([
    r"animal", r"animaux", r"animales?", r"faune", r"gibiers?", r"chasse", r"chasseurs?", r"cynegetiques?",
    r"elevages?", r"eleveurs?", r"betail", r"cheptels?", r"bovins?", r"bovines?", r"ovins?", r"caprins?", r"porcins?",
    r"volailles?", r"avicoles?", r"equides?", r"chevaux", r"chiens?", r"chats?", r"abeilles?", r"apicoles?",
    r"loups?", r"ours", r"lynx", r"frelons?", r"oiseaux", r"rapaces?", r"cetaces?", r"veterinaires?", r"zoonoses?",
    r"epizooties?", r"abattoirs?", r"abattage", r"influenza aviaire", r"peste porcine", r"tuberculose bovine",
    r"fievre catarrhale", r"dermatose nodulaire", r"especes? protegees?", r"especes? sauvages?",
    r"especes? exotiques envahissantes", r"susceptibles? d.occasionner des degats", r"cirques?", r"delphinariums?",
    r"zoos?", r"experimentation animale", r"piegeage"]) + r")\b")
SEUIL_ANCRES_TEXTE = 3   # sert seulement au fichier de contrôle : en version 1, le titre doit parler d'animaux
# Expressions qui contiennent un mot d'ancrage sans parler du sort des animaux (hygiène et commerce des denrées)
# Expressions qui contiennent un mot d'ancrage sans parler du sort des animaux : hygiène et commerce des denrées,
# signes de qualité (labels, appellations), accords entre professionnels. Le titre entier est alors écarté.
HORS_PERIMETRE_TITRE = re.compile(r"d.origine animale|denrees? (?:alimentaires? )?(?:d.origine )?animales?|"
                                  r"produits? (?:d.origine )?animaux|sous.produits? animaux|proteines? animales?|"
                                  r"cahier des charges|label rouge|appellation d.origine|indication geographique|"
                                  r"accord interprofessionnel|convention collective|extension (?:d.un |de l.)?(?:accord|avenant)")
# Textes individuels et de personnel : écartés (ils citeraient « vétérinaire » ou « chasse » sans concerner les animaux)
PERSONNEL = re.compile(r"\b(?:nomination|nommes?|cessation de fonctions|tableau d.avancement|admission a la retraite|"
                       r"concours|examen professionnel|liste d.aptitude|jury|titularisation|delegation de signature|"
                       r"medailles?|inscription au tableau)\b")
# Textes cherchés à la main le 26/09/2026 : la brique doit les retrouver seule (test d'acceptation)
ATTENDUS = {
    "JORFTEXT000054728726": "Arrêté du 10 août 2026, liste des espèces susceptibles d'occasionner des dégâts",
    "JORFTEXT000054842308": "Arrêté du 9 septembre 2026, plan national de lutte contre le frelon asiatique",
    "JORFTEXT000053555244": "Arrêté du 23 février 2026, statut de protection du loup",
    "JORFTEXT000053555329": "Arrêté du 23 février 2026, plafond de destruction des loups",
    "JORFTEXT000053201550": "Décret n° 2025-1377 du 29 décembre 2025, plans de lutte contre le frelon asiatique",
}


def telecharger(nom):
    chemin = os.path.join(DOSSIER, nom)
    if os.path.exists(chemin) and tarfile.is_tarfile(chemin):
        return chemin
    for essai in range(5):
        try:
            r = requests.get(BASE + nom, timeout=(30, 300))
            r.raise_for_status()
            with open(chemin, "wb") as f:
                f.write(r.content)
            if tarfile.is_tarfile(chemin):
                return chemin
        except requests.RequestException as e:
            print(f"    coupure ({e.__class__.__name__}), nouvel essai")
        time.sleep(5 + 10 * essai)
    raise RuntimeError(f"Téléchargement impossible : {nom}")


def texte_de(el):
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


# ---------------------------------------------------------------------------
# 1. Mises à jour à lire
index = requests.get(BASE, timeout=60).text
toutes = sorted(set(re.findall(r'href="(JORF_(\d{8})-\d{6}\.tar\.gz)"', index)))
periodes = [tuple(x.replace("-", "") for x in per.split(":")) for per in A.periodes]
a_lire = [nom for nom, jour in toutes if any(d <= jour <= f for d, f in periodes)]
print(f"{len(toutes)} mises à jour disponibles ; {len(a_lire)} à lire pour les périodes {A.periodes}")

# ---------------------------------------------------------------------------
# 2. Lecture : fiche de chaque texte (version) et texte de ses articles
textes, articles = {}, {}
lus = Counter()
for i, nom in enumerate(a_lire, 1):
    chemin = telecharger(nom)
    with tarfile.open(chemin, "r:gz") as tar:
        for m in tar:
            if not m.name.endswith(".xml"):
                continue
            if "/texte/version/" in m.name and "JORFTEXT" in m.name:
                r = ET.fromstring(tar.extractfile(m).read())
                nature = texte_de(r.find(".//META_COMMUN/NATURE"))
                lus[nature] += 1
                if nature not in NATURES:
                    continue
                cid = texte_de(r.find(".//META_COMMUN/ID"))
                appliquees = [{"texte": texte_de(l), "cid": l.get("cidtexte"), "nature": l.get("naturetexte"),
                               "numero": l.get("numtexte"), "article": l.get("num")}
                              for l in r.iter("LIEN") if l.get("typelien") == "APPLICATION" and l.get("sens") == "source"]
                textes[cid] = {
                    "cid": cid, "nature": nature,
                    "numero": texte_de(r.find(".//META_TEXTE_CHRONICLE/NUM")),
                    "nor": texte_de(r.find(".//META_TEXTE_CHRONICLE/NOR")),
                    "date_texte": texte_de(r.find(".//META_TEXTE_CHRONICLE/DATE_TEXTE")),
                    "date_publication": texte_de(r.find(".//META_TEXTE_CHRONICLE/DATE_PUBLI")),
                    "parution": texte_de(r.find(".//META_TEXTE_CHRONICLE/ORIGINE_PUBLI")),
                    "titre": texte_de(r.find(".//META_TEXTE_VERSION/TITREFULL")),
                    "ministere": texte_de(r.find(".//META_TEXTE_VERSION/MINISTERE")),
                    "visas": texte_de(r.find("VISAS")),
                    "applique": appliquees,
                    "mise_a_jour": nom,
                }
            elif "/article/" in m.name and "JORFARTI" in m.name:
                r = ET.fromstring(tar.extractfile(m).read())
                ctx = r.find(".//CONTEXTE/TEXTE")
                if ctx is None or ctx.get("nature") not in NATURES:
                    continue
                aid = texte_de(r.find(".//META_COMMUN/ID"))
                articles.setdefault(ctx.get("cid"), {})[aid] = texte_de(r.find("BLOC_TEXTUEL"))
    if i % 10 == 0 or i == len(a_lire):
        print(f"  {i}/{len(a_lire)} mises à jour lues, {len(textes)} textes (loi, ordonnance, décret, arrêté)")

# ---------------------------------------------------------------------------
# 3. Sélection et classement
# Seuls les textes publiés pendant les périodes lues : les mises à jour renvoient aussi d'anciens textes modifiés
periodes_dates = [(f"{d[:4]}-{d[4:6]}-{d[6:]}", f"{f[:4]}-{f[4:6]}-{f[6:]}") for d, f in periodes]
lignes, personnel, quasi, mention_texte, hors_perimetre = [], [], [], [], []
anciens = 0
for cid, t in textes.items():
    if not any(d <= t["date_publication"] <= f for d, f in periodes_dates):
        anciens += 1
        continue
    titre_n = sans_accents(t["titre"])
    corps_n = sans_accents(t["visas"] + " " + " ".join(articles.get(cid, {}).values()))
    ancre_titre = [] if HORS_PERIMETRE_TITRE.search(titre_n) else sorted(set(ANCRES.findall(titre_n)))
    ancres_texte = ANCRES.findall(corps_n)
    if not ancre_titre:
        if len(ancres_texte) >= SEUIL_ANCRES_TEXTE:   # en parle dans son contenu seulement : contrôle, pas retenu en version 1
            mention_texte.append((t["nature"], t["titre"], len(ancres_texte)))
        if ANCRES.search(titre_n):
            hors_perimetre.append((t["nature"], t["titre"]))
        continue
    themes, declencheurs = classer(titre_n, corps_n)
    if PERSONNEL.search(titre_n):
        personnel.append((t["nature"], t["titre"]))
        continue
    if not themes:
        quasi.append((t["titre"], ", ".join(ancre_titre)))
        continue
    lignes.append({
        **{k: t[k] for k in ("cid", "nature", "numero", "nor", "date_texte", "date_publication", "parution", "titre", "ministere")},
        "themes": " | ".join(themes),
        "declencheurs": " ; ".join(declencheurs),
        "ancrage": f"titre : {', '.join(ancre_titre[:4])}",
        "applique": " ; ".join(f"{x['texte']}" + (f" (art. {x['article']})" if x["article"] and "art." not in x["texte"] else "")
                               for x in t["applique"]),
        "lois_appliquees": ", ".join(sorted({x["numero"] for x in t["applique"] if x["nature"] == "LOI" and x["numero"]})),
        "lien": f"https://www.legifrance.gouv.fr/jorf/id/{cid}",
        "source_mise_a_jour": t["mise_a_jour"],
    })

df = pd.DataFrame(lignes).sort_values("date_publication", ascending=False) if lignes else pd.DataFrame()

# ---------------------------------------------------------------------------
# 4. Contrôle
print("\nTextes lus par nature (toutes natures) :", dict(lus.most_common()))
print(f"Lois, ordonnances, décrets, arrêtés lus : {len(textes)}, dont {anciens} publiés hors des périodes (anciens textes modifiés, ignorés)")
print(f"Retenus (titre parlant d'animaux, avec au moins un thème) : {len(df)}")
print(f"Écartés : textes de personnel {len(personnel)} ; titre parlant d'animaux sans thème {len(quasi)} ; "
      f"hygiène et commerce des denrées {len(hors_perimetre)} ; animaux mentionnés seulement dans le contenu {len(mention_texte)} (contrôle)")
if len(df):
    print("\nPar nature :", df["nature"].value_counts().to_dict())
    print("Par thème :")
    print(df["themes"].str.split(r" \| ").explode().value_counts().to_string())
    print("\nAvec un lien « applique » vers une loi :", int((df["lois_appliquees"] != "").sum()))
print("\n--- Test d'acceptation : textes cherchés à la main, retrouvés seuls ? ---")
for cid, libelle in ATTENDUS.items():
    etat = "RETROUVÉ" if len(df) and cid in set(df["cid"]) else ("lu mais écarté" if cid in textes else "hors des périodes lues")
    print(f"  {etat:22s} {libelle}")
random.seed(1)
print("\n--- Échantillon retenu (vérifier qu'ils concernent bien les animaux) ---")
for _, l in df.sample(min(25, len(df)), random_state=1).iterrows():
    print(f"  [{l.nature}] {l.titre[:110]}  ->  {l.themes} ; {l.ancrage}")
print("\n--- Parlent d'animaux mais sans thème (écartés : vérifier qu'aucun ne manque) ---")
for titre, a in random.sample(quasi, min(20, len(quasi))):
    print(f"  {titre[:110]}  [{a}]")
print("\n--- Écartés comme textes de personnel (échantillon) ---")
for nature, titre in random.sample(personnel, min(8, len(personnel))):
    print(f"  [{nature}] {titre[:110]}")
print("\n--- Écartés comme hygiène et commerce des denrées (tous) ---")
for nature, titre in hors_perimetre:
    print(f"  [{nature}] {titre[:110]}")
print("\n--- Animaux mentionnés seulement dans le contenu (échantillon, non retenus en version 1) ---")
for nature, titre, n in random.sample(mention_texte, min(15, len(mention_texte))):
    print(f"  [{nature}] x{n} {titre[:110]}")

SORTIE = dossier_sortie("brique3")
df.to_csv(os.path.join(SORTIE, "textes_jo_animaux_v1.csv"), index=False, encoding="utf-8-sig", sep=";")
pd.DataFrame(quasi, columns=["titre", "ancrage"]).to_csv(os.path.join(SORTIE, "controle_sans_theme.csv"), index=False, encoding="utf-8-sig", sep=";")
pd.DataFrame(personnel, columns=["nature", "titre"]).to_csv(os.path.join(SORTIE, "controle_personnel.csv"), index=False, encoding="utf-8-sig", sep=";")
pd.DataFrame(hors_perimetre, columns=["nature", "titre"]).to_csv(os.path.join(SORTIE, "controle_denrees.csv"), index=False, encoding="utf-8-sig", sep=";")
pd.DataFrame(mention_texte, columns=["nature", "titre", "mentions"]).to_csv(os.path.join(SORTIE, "controle_mention_dans_le_contenu.csv"), index=False, encoding="utf-8-sig", sep=";")
print("\nFichiers écrits dans", SORTIE)
