"""Publication : transforme les sorties des briques en fichiers publiés (le « frigo »).

Ne modifie aucune donnée des briques : traduit le vocabulaire (publication/lexique.json), met en forme,
ajoute dates et clés de lecture, contrôle (publication/controles.json), puis écrit un dossier prêt à
publier sur GitHub Pages. Si un contrôle échoue, rien n'est écrit et le script s'arrête en erreur.

Usage :
    python scripts/publier.py                       # dernières sorties des briques dans sorties/
    python scripts/publier.py --precedent https://myqoh.github.io/veille-animale/dernier
Le dossier écrit contient :
    site/                  à publier tel quel (index.html, dernier/...)
    release/               fichiers à joindre à une nouvelle version datée (si les données ont changé)
    resultat.json          { "nouvelle_version": true/false, "version": "AAAA-MM-JJ", ... }
"""
import argparse, glob, hashlib, json, os, re, shutil, sys, unicodedata
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

import pandas as pd
import requests

from commun import DONNEES_BRUTES, RACINE, SORTIES, console_utf8, dossier_sortie
from fiches import ErreurFiche, toutes_les_fiches
from regles_themes import famille_ministere

console_utf8()
p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--brique1", help="dossier de sortie de la brique 1 (par défaut le plus récent)")
p.add_argument("--brique2", help="dossier de sortie de la brique 2 (par défaut le plus récent)")
p.add_argument("--brique3", help="dossier de sortie de la brique 3 (par défaut le plus récent)")
p.add_argument("--precedent", help="adresse ou dossier de la version publiée précédente (dossier dernier/)")
p.add_argument("--adresse", default="https://myqoh.github.io/veille-animale", help="adresse publique du site")
A = p.parse_args()

LEXIQUE = json.load(open(os.path.join(RACINE, "publication", "lexique.json"), encoding="utf-8"))
CONTROLES = json.load(open(os.path.join(RACINE, "publication", "controles.json"), encoding="utf-8"))
MAINTENANT = datetime.now(timezone.utc)
AUJOURDHUI = MAINTENANT.date().isoformat()
FORMAT = "0.2"
SOURCE_AN = "Assemblée nationale, données ouvertes (data.assemblee-nationale.fr), questions écrites"
SOURCE_DOLE = "DILA, dossiers législatifs de Légifrance (jeu DOLE, echanges.dila.gouv.fr)"
SOURCE_JO = "DILA, Journal officiel de la République française (jeu JORF, echanges.dila.gouv.fr)"


def dernier_dossier(motif):
    trouves = sorted(glob.glob(os.path.join(SORTIES, motif)))
    if not trouves:
        sys.exit(f"Aucune sortie trouvée pour {motif} : lancer d'abord les briques.")
    return os.path.dirname(trouves[-1])


B1 = A.brique1 or dernier_dossier("*_brique1/questions_ecrites_animaux_2012_2026_v14.csv")
B2 = A.brique2 or dernier_dossier("*_brique2/lois_animaux_v5.csv")
lire = lambda chemin: pd.read_csv(chemin, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
q = lire(os.path.join(B1, "questions_ecrites_animaux_2012_2026_v14.csv"))
volumes = lire(os.path.join(B1, "volumes_questions_ecrites_par_mois.csv"))
delais_toutes = lire(os.path.join(B1, "delais_toutes_questions.csv"))
lois = lire(os.path.join(B2, "lois_animaux_v5.csv"))
mesures = lire(os.path.join(B2, "echeanciers_lois_animaux_v5.csv"))
B3 = A.brique3 or dernier_dossier("*_brique3/textes_jo_animaux_v1.csv")
textes_jo = lire(os.path.join(B3, "textes_jo_animaux_v1.csv"))
print("Brique 3 :", B3)
archives_dole = sorted(os.path.basename(x) for x in glob.glob(os.path.join(DONNEES_BRUTES, "dole", "*.tar.gz")))
ARCHIVE_DOLE = archives_dole[-1] if archives_dole else ""
m = re.search(r"(\d{4})(\d{2})(\d{2})", ARCHIVE_DOLE)
DATE_DOLE = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
print("Brique 1 :", B1, "\nBrique 2 :", B2, "\nArchive DOLE :", ARCHIVE_DOLE or "inconnue")


# ---------------------------------------------------------------------------
# Version précédente (pour les contrôles d'évolution et le journal)
def charger_precedent(nom):
    if not A.precedent:
        return None
    try:
        if A.precedent.startswith("http"):
            r = requests.get(f"{A.precedent.rstrip('/')}/{nom}", timeout=60)
            return r.json() if r.status_code == 200 else None
        with open(os.path.join(A.precedent, nom), encoding="utf-8") as f:
            return json.load(f)
    except (requests.RequestException, OSError, ValueError):
        return None


prec_index = charger_precedent("index.json")
prec_questions = charger_precedent("questions_ecrites.json")
prec_mesures = charger_precedent("mesures.json")
prec_journal = charger_precedent("journal.json") or {"versions": []}
print("Version précédente :", prec_index["version"] if prec_index else "aucune")

# ---------------------------------------------------------------------------
# Contrôles (avant toute écriture)
erreurs = []
for leg, attendu in CONTROLES["questions_retenues_legislatures_figees"].items():
    n = int((q["legislature"] == leg).sum())
    if n != attendu:
        erreurs.append(f"{leg}e législature : {n} questions retenues au lieu de {attendu} (législature figée)")
n17 = int((q["legislature"] == "17").sum())
if prec_index:
    n17_avant = prec_index.get("compteurs", {}).get("questions_17e")
    if n17_avant and n17 < n17_avant * (1 - CONTROLES["baisse_max_17e"]):
        erreurs.append(f"17e législature : {n17} questions retenues contre {n17_avant} à la version précédente")
for nom, table, attendues in (("brique 1", q, CONTROLES["colonnes_brique1"]),
                              ("brique 2, mesures", mesures, CONTROLES["colonnes_brique2_mesures"]),
                              ("brique 2, lois", lois, CONTROLES["colonnes_brique2_lois"])):
    manquantes = [c for c in attendues if c not in table.columns]
    if manquantes:
        erreurs.append(f"{nom} : colonnes manquantes {manquantes}")
for c in CONTROLES["colonnes_non_vides_brique1"]:
    if c in q.columns and (q[c].str.strip() == "").any():
        erreurs.append(f"brique 1 : {int((q[c].str.strip() == '').sum())} valeurs vides dans {c}")
manquants_jo = [c for c in CONTROLES["textes_jo_attendus"] if c not in set(textes_jo["cid"])]
if manquants_jo:
    erreurs.append(f"brique 3 : textes du Journal officiel attendus absents : {manquants_jo}")
if prec_index and prec_index.get("compteurs", {}).get("textes_officiels"):
    avant_jo = prec_index["compteurs"]["textes_officiels"]
    if len(textes_jo) < avant_jo * (1 - CONTROLES["baisse_max_17e"]):
        erreurs.append(f"brique 3 : {len(textes_jo)} textes du Journal officiel contre {avant_jo} à la version précédente")
# Brique 2 (V5, archive complète + mises à jour) : jamais moins que le minimum vérifié
attendu_b2 = CONTROLES["brique2_minimum"]
if len(lois) < attendu_b2["textes"] or len(mesures) < attendu_b2["mesures"]:
    erreurs.append(f"brique 2 : {len(lois)} textes et {len(mesures)} mesures, moins que le minimum vérifié "
                   f"({attendu_b2['textes']} et {attendu_b2['mesures']})")
if erreurs:
    print("\nCONTRÔLES EN ÉCHEC, rien n'est publié :")
    for e in erreurs:
        print("  -", e)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Vocabulaire neutre
def neutraliser(table):
    t = table.rename(columns=LEXIQUE["colonnes"]).copy()
    for col, correspondances in LEXIQUE["valeurs"].items():
        if col in t.columns:
            t[col] = t[col].replace(correspondances)
    return t


q_pub, lois_pub, mesures_pub = neutraliser(q), neutraliser(lois), neutraliser(mesures)


def entier(x):
    try:
        return int(float(x)) if str(x).strip() != "" else None
    except ValueError:
        return None


def date10(x):
    return str(x)[:10] if str(x).strip() else None


def lire_declencheurs(ligne):
    """« Thème (titre) : a, b ; Thème (texte x3) : c » -> liste structurée, pour « Pourquoi dans ce thème ? »."""
    out = []
    for morceau in filter(None, ligne["declencheurs"].split(" ; ")):
        m = re.match(r"^(.*) \((titre|texte x(\d+))\) : (.*)$", morceau)
        if m:
            out.append({"theme": m.group(1), "ou": "titre" if m.group(2) == "titre" else "texte",
                        "mentions_dans_le_texte": int(m.group(3)) if m.group(3) else None,
                        "mots": m.group(4).split(", ")})
    if not out and ligne["themes"] != "À classer":   # thème donné par la rubrique de l'Assemblée (chasse et pêche)
        out.append({"theme": ligne["themes"], "ou": "rubrique", "mentions_dans_le_texte": None,
                    "mots": [ligne["rubrique_AN"]]})
    return out


SIGNALEMENTS_ABSENTS = {"14", "15"}   # aucun signalement enregistré dans ces archives : « non disponible », jamais zéro
evenements = []
for _, l in q_pub.iterrows():
    sans_sig = l["legislature"] in SIGNALEMENTS_ABSENTS
    evenements.append({
        # champs de la v0.1, inchangés
        "id": f"AN-QE-{l['legislature']}-{l['numero']}",
        "type": "question_ecrite",
        "source": "Assemblée nationale",
        "date": date10(l["date_question"]),
        "titre": l["titre"],
        "themes": l["themes"].split(" | "),
        "ministere": l["ministere"],
        "ministere_intitule_officiel": l["ministere_intitule_officiel"],
        "legislature": int(l["legislature"]),
        "echeance": date10(l["echeance_legale"]),
        "date_reponse": date10(l["date_reponse"]),
        "delai_jours": entier(l["delai_jours"]),
        "statut": l["statut"],
        "signalee": None if sans_sig else l["signalee"] == "True",
        "lien": l["lien"],
        # ajouts de la v0.2
        "titre_source": l["titre_source"],
        "declencheurs": lire_declencheurs(l),
        "jours_apres_echeance": entier(l["jours_apres_echeance"]),
        "statut_signalement": "Non disponible dans les archives de cette législature" if sans_sig else (l["statut_signalement"] or None),
        "date_signalement": date10(l["date_signalement"]),
        "lois_citees": [x for x in l["lois_citees"].split(", ") if x],
        "mis_a_jour_le": AUJOURDHUI,
    })

CLES_QUESTIONS = [
    "Délai légal de réponse : deux mois (article 135 du règlement de l'Assemblée). Avant le 28 novembre 2014 : un mois, prolongeable d'un mois ; on retient le maximum de deux mois.",
    "Le délai médian est calculé sur les seules questions répondues. Les questions closes sans réponse (fin de législature ou de mandat) n'ont pas de délai mesuré et n'y figurent pas.",
    "Pour lire un taux de réponse dans le délai, le comparer au même taux pour l'ensemble des questions écrites (themes.json, reference_toutes_questions).",
    "14e et 15e législatures : aucun signalement n'est enregistré dans les archives. La valeur est « non disponible », jamais zéro.",
    "15e législature : l'archive ne contient aucun titre officiel ; le titre est extrait du texte de la question (titre_source). Les comptes par thème ne sont pas strictement comparables avec les autres législatures.",
    "Une question peut relever de plusieurs thèmes. Chaque thème indique le mot qui l'a déclenché et où il a été trouvé (declencheurs).",
    "Comparaisons dans le temps : toujours en part de l'ensemble des questions écrites de la période, jamais en volume brut.",
]


# ---------------------------------------------------------------------------
# Textes du Journal officiel (brique 3) : même format daté, type « texte_officiel »
NATURE_AFFICHEE = {"LOI": "Loi", "ORDONNANCE": "Ordonnance", "DECRET": "Décret", "ARRETE": "Arrêté"}


def declencheurs_structures(chaine):
    out = []
    for morceau in filter(None, chaine.split(" ; ")):
        m = re.match(r"^(.*) \((titre|texte x(\d+))\) : (.*)$", morceau)
        if m:
            out.append({"theme": m.group(1), "ou": "titre" if m.group(2) == "titre" else "texte",
                        "mentions_dans_le_texte": int(m.group(3)) if m.group(3) else None, "mots": m.group(4).split(", ")})
    return out


def etape_du_fil(t):
    """Étape dans le fil « de l'intention au résultat ». Le lien « application » vient du Journal officiel lui-même."""
    if t["nature"] in ("LOI", "ORDONNANCE"):
        return "Loi ou ordonnance"
    if t["lois_appliquees"]:
        return "Texte d'application d'une loi"
    return "Autre texte réglementaire"


textes_officiels = []
for _, t in textes_jo.iterrows():
    textes_officiels.append({
        "id": f"JO-{t['cid']}",
        "type": "texte_officiel",
        "source": "Journal officiel",
        "date": t["date_publication"],
        "date_signature": t["date_texte"] or None,
        "titre": t["titre"],
        "nature": NATURE_AFFICHEE.get(t["nature"], t["nature"]),
        "numero": t["numero"] or None,
        "nor": t["nor"] or None,
        "parution": t["parution"],
        "themes": t["themes"].split(" | "),
        "declencheurs": declencheurs_structures(t["declencheurs"]),
        "ancrage": t["ancrage"],
        "ministere": famille_ministere(t["ministere"]) if t["ministere"] else "(non renseigné)",
        "ministere_intitule_officiel": t["ministere"] or None,
        "etape": etape_du_fil(t),
        "applique": [x for x in t["applique"].split(" ; ") if x],
        "lois_appliquees": [x for x in t["lois_appliquees"].split(", ") if x],
        "statut": "Publié au Journal officiel",
        "lien": t["lien"],
        "mis_a_jour_le": AUJOURDHUI,
    })
textes_officiels.sort(key=lambda e: e["date"], reverse=True)
CLES_JO = [
    "Textes publiés au Journal officiel depuis le 1er janvier 2012 : lois, ordonnances, décrets et arrêtés dont le titre parle d'animaux et qui relèvent d'au moins un thème. Chaque texte indique le mot qui l'a fait entrer (ancrage) et ceux qui ont déclenché ses thèmes.",
    "Ne sont pas retenus : les textes de personnel (nominations, retraites, concours), l'hygiène et le commerce des denrées, les signes de qualité et les accords entre professionnels, et les textes qui ne parlent d'animaux que dans leur contenu (loi de finances, codes...).",
    "Étape : « Texte d'application d'une loi » quand le Journal officiel indique lui-même la loi appliquée (lien « application »). Un texte sans ce lien peut malgré tout appliquer une loi : l'information n'est alors pas renseignée par la source.",
]
# Tous les événements datés, toutes sources confondues : la base commune que lisent le site, les flux et les fiches
evenements_tous = sorted(evenements + textes_officiels, key=lambda e: e["date"] or "", reverse=True)

# ---------------------------------------------------------------------------
# Statistiques par thème, avec le point de comparaison « toutes questions écrites »
q_stat = q.assign(theme=q["themes"].str.split(r" \| "), annee=q["date_question"].str[:4])
q_stat = pd.concat([q_stat.explode("theme"), q.assign(theme="Ensemble des questions retenues", annee=q["date_question"].str[:4])])
q_stat["delai"] = pd.to_numeric(q_stat["delai_jours"], errors="coerce")
vol = volumes.assign(n=volumes["questions_toutes_rubriques"].astype(int), annee=volumes["mois"].str[:4])
tot_leg, tot_annee = vol.groupby("legislature")["n"].sum(), vol.groupby("annee")["n"].sum()


def resume(g, total):
    rep = g[g["date_reponse"] != ""]
    return {
        "questions": len(g),
        "part_de_toutes_les_questions_ecrites": round(len(g) / total, 5) if total else None,
        "repondues": len(rep),
        "part_dans_le_delai_parmi_repondues": round((rep["statut"] == "Répondue dans le délai").mean(), 4) if len(rep) else None,
        "delai_median_jours_repondues": float(rep["delai"].median()) if len(rep) else None,
        "closes_sans_reponse": int(g["statut"].str.startswith("Close sans réponse").sum()),
        "en_attente": int(g["statut"].str.startswith("En attente").sum()),
    }


par_legislature = [dict(theme=t, legislature=int(leg), **resume(g, int(tot_leg.get(leg, 0))))
                   for (t, leg), g in q_stat.groupby(["theme", "legislature"])]
par_annee = [dict(theme=t, annee=int(an), **resume(g, int(tot_annee.get(an, 0))))
             for (t, an), g in q_stat[q_stat["annee"] != ""].groupby(["theme", "annee"])]


def nombre(x):
    if x == "":
        return None
    f = float(x)
    return int(f) if f.is_integer() else f


reference = [{k: (nombre(v) if k not in ("annee",) else v) for k, v in r.items()} for r in delais_toutes.to_dict("records")]
themes_json = {
    "meta": {"format": "veille-animale/themes", "version_format": FORMAT, "genere_le": AUJOURDHUI, "source": SOURCE_AN,
             "cles_de_lecture": CLES_QUESTIONS + [
                 "part_de_toutes_les_questions_ecrites : nombre de questions du thème divisé par le nombre de questions écrites de la même période, toutes rubriques confondues (questions datées).",
                 "reference_toutes_questions : mêmes règles de statut et de délai, appliquées à toutes les questions écrites lues."]},
    "par_legislature": par_legislature,
    "par_annee": par_annee,
    "reference_toutes_questions": reference,
}


# ---------------------------------------------------------------------------
# Lois et mesures (brique 2, V4)
def lignes_json(table, dates=(), entiers=(), booleens=()):
    out = []
    for r in table.to_dict("records"):
        for k in list(r):
            if k in dates:
                r[k] = date10(r[k])
            elif k in entiers:
                r[k] = entier(r[k])
            elif k in booleens:
                r[k] = r[k] == "True"
            elif r[k] == "":
                r[k] = None
        out.append(r)
    return out


CLES_LOIS = [
    "Un échéancier décrit l'état des mesures d'application à la date de sa dernière mise à jour (echeancier_mis_a_jour), pas forcément aujourd'hui.",
    f"Données DOLE : archive complète {ARCHIVE_DOLE or 'inconnue'}{' (publiée le ' + DATE_DOLE + ')' if DATE_DOLE else ''}, puis mises à jour quotidiennes de la DILA.",
    "La loi fixe rarement une date limite aux décrets : le délai mesuré (delai_jours) est un délai constaté entre la loi et le décret, pas un dépassement.",
    "Loi suivie : loi publiée avec un échéancier dont au moins une mesure concerne les animaux. Texte lié : ordonnance, projet, proposition de loi, loi sans échéancier, ou loi sans mesure animale.",
    "Les rapports au Parlement ne figurent pas dans les échéanciers.",
]
meta_b2 = {"version_format": FORMAT, "genere_le": AUJOURDHUI, "source": SOURCE_DOLE, "archive": ARCHIVE_DOLE,
           "archive_publiee_le": DATE_DOLE, "cles_de_lecture": CLES_LOIS}
lois_json = {"meta": {"format": "veille-animale/lois", **meta_b2},
             "lois": lignes_json(lois_pub, dates=("promulgation", "echeancier_mis_a_jour"), entiers=("mesures",),
                                 booleens=("citee_dans_questions", "loi_entierement_animale", "echeancier_present", "proposition_non_adoptee"))}
mesures_json = {"meta": {"format": "veille-animale/mesures", **meta_b2},
                "mesures": lignes_json(mesures_pub, dates=("loi_promulgation", "decret_date", "publication_annoncee", "echeancier_mis_a_jour"),
                                       entiers=("delai_jours", "jours_depuis_promulgation"), booleens=("citee_dans_questions", "concerne_animaux"))}

# ---------------------------------------------------------------------------
# Fiches sujet (publication/sujets/*.json coulés dans le modèle de scripts/fiches.py)
DOSSIER_SUJETS = os.path.join(RACINE, "publication", "sujets")
try:
    fiches = toutes_les_fiches(DOSSIER_SUJETS, q=q_pub, evenements=evenements, lois_json=lois_json,
                               mesures_json=mesures_json, delais_toutes=delais_toutes, aujourdhui=AUJOURDHUI)
except ErreurFiche as e:
    print("\nCONTRÔLE DES FICHES EN ÉCHEC, rien n'est publié :\n  -", e)
    sys.exit(1)
print(f"{len(fiches)} fiche(s) sujet : {', '.join(fiches)}")

# ---------------------------------------------------------------------------
# Contrôle du vocabulaire sur tout ce qui sera publié (hors textes officiels cités)
INTERDITS = re.compile(r"\b(?:" + "|".join(LEXIQUE["mots_interdits"]) + r")", re.I)
CITES = set(LEXIQUE["champs_cites"]) | {"themes_texte"}


def mots_interdits(obj, chemin=""):
    trouves = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if INTERDITS.search(str(k)):
                trouves.append(f"{chemin}.{k} (nom de champ)")
            if k not in CITES:
                trouves += mots_interdits(v, f"{chemin}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            trouves += mots_interdits(v, f"{chemin}[{i}]")
    elif isinstance(obj, str) and INTERDITS.search(obj):
        trouves.append(f"{chemin} : « {obj[:80]} »")
    return trouves


probleme = []
for nom, obj in (("questions_ecrites.json", evenements), ("themes.json", themes_json), ("lois.json", lois_json),
                 ("mesures.json", mesures_json), ("textes_officiels.json", textes_officiels)) + tuple((f"fiches/{k}.json", v) for k, v in fiches.items()):
    probleme += [f"{nom}{x}" for x in mots_interdits(obj)]
for nom, table in (("questions_ecrites.csv", q_pub), ("lois.csv", lois_pub), ("mesures.csv", mesures_pub),
                   ("textes_officiels.csv", textes_jo)):
    for c in table.columns:
        if INTERDITS.search(c):
            probleme.append(f"{nom} : colonne {c}")
        elif c not in CITES and table[c].str.contains(INTERDITS, na=False).any():
            probleme.append(f"{nom} : valeurs de la colonne {c}")
if probleme:
    print("\nCONTRÔLE DU VOCABULAIRE EN ÉCHEC, rien n'est publié :")
    for x in probleme[:20]:
        print("  -", x)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Empreinte des données stables (sans les compteurs qui avancent d'un jour chaque nuit) et journal
STABLES_Q = ["uid", "statut", "date_question", "date_reponse", "themes", "titre", "cloture", "signalee",
             "date_signalement", "statut_signalement", "ministere", "lois_citees"]
STABLES_M = ["loi_titre", "numero_ordre", "article", "statut", "decret", "decret_date", "echeancier_mis_a_jour", "concerne_animaux"]
STABLES_L = ["loi_titre", "type", "role", "mesures", "echeancier_mis_a_jour"]
STABLES_JO = ["cid", "date_publication", "titre", "themes", "lois_appliquees"]
h = hashlib.sha256()
for table, cols in ((q_pub, STABLES_Q), (mesures_pub, STABLES_M), (lois_pub, STABLES_L), (textes_jo, STABLES_JO)):
    # fins de ligne fixées : même empreinte sous Windows et sous Linux
    h.update(table[cols].sort_values(cols).to_csv(index=False, lineterminator="\n").encode("utf-8"))
EMPREINTES_FICHES = {}
for chemin in sorted(glob.glob(os.path.join(DOSSIER_SUJETS, "*.json"))):   # une fiche publiée modifiée = nouvelle version
    if not fiches.get(os.path.basename(chemin)[:-5], {}).get("meta", {}).get("publiable"):
        continue
    contenu = open(chemin, "rb").read()
    h.update(contenu)
    EMPREINTES_FICHES[os.path.basename(chemin)[:-5]] = hashlib.sha256(contenu).hexdigest()[:16]
EMPREINTE = h.hexdigest()[:16]
nouvelle = not prec_index or prec_index.get("empreinte") != EMPREINTE


def cle_mesure(r):
    return (r["loi_titre"], r["numero_ordre"], r["article"])


changements = {}
if nouvelle and prec_questions:
    avant = {e["id"]: e for e in prec_questions["evenements"]}
    apres = {e["id"]: e for e in evenements}
    changements["nouvelles_questions"] = sorted(set(apres) - set(avant))
    changements["questions_retirees"] = sorted(set(avant) - set(apres))
    communs = set(avant) & set(apres)
    changements["nouvelles_reponses"] = sorted(i for i in communs if apres[i]["date_reponse"] and not avant[i]["date_reponse"])
    changements["statuts_modifies"] = sorted(i for i in communs if apres[i]["statut"] != avant[i]["statut"]
                                             and i not in changements["nouvelles_reponses"])
    if prec_mesures:
        av = {}
        for r in prec_mesures["mesures"]:
            av.setdefault(cle_mesure(r), []).append(r["statut"])
        ap = {}
        for r in mesures_json["mesures"]:
            ap.setdefault(cle_mesure(r), []).append(r["statut"])
        changements["mesures_modifiees"] = sum(1 for k in set(av) | set(ap) if sorted(av.get(k, [])) != sorted(ap.get(k, [])))
if nouvelle and prec_index is not None:
    prec_textes = charger_precedent("textes_officiels.json")
    if prec_textes is not None:
        changements["nouveaux_textes_officiels"] = sorted({e["id"] for e in textes_officiels} - {e["id"] for e in prec_textes["evenements"]})
    else:
        changements["nouveaux_textes_officiels"] = f"première publication : {len(textes_officiels)} textes"
if nouvelle and prec_index is not None:
    avant_fiches = prec_index.get("empreintes_fiches", {})
    changements["fiches_ajoutees_ou_modifiees"] = sorted(k for k, v in EMPREINTES_FICHES.items() if avant_fiches.get(k) != v)
    changements["fiches_retirees"] = sorted(set(avant_fiches) - set(EMPREINTES_FICHES))
if nouvelle:
    deja = {v["version"] for v in prec_journal["versions"]}
    VERSION, n = AUJOURDHUI, 2
    while VERSION in deja:
        VERSION, n = f"{AUJOURDHUI}-{n}", n + 1
    resume_changements = {k: (len(v) if isinstance(v, list) else v) for k, v in changements.items()}
    entree = {"version": VERSION, "publiee_le": MAINTENANT.isoformat(timespec="seconds"), "empreinte": EMPREINTE,
              "changements": resume_changements or "première version publiée",
              "exemples": {k: v[:20] for k, v in changements.items() if isinstance(v, list) and v},
              "telechargement": f"https://github.com/MyQoh/veille-animale/releases/tag/donnees-{VERSION}"}
    journal = {"meta": {"format": "veille-animale/journal", "cles_de_lecture": [
        "Une version est créée quand les données changent : nouvelle question, nouvelle réponse, changement de statut, de mesure ou de loi. Les délais des questions en attente, qui avancent d'un jour chaque nuit, ne suffisent pas à créer une version.",
        "Chaque version est téléchargeable en entier (lien telechargement)."]},
               "versions": [entree] + prec_journal["versions"]}
else:
    VERSION = prec_index["version"]
    journal = prec_journal
print(f"Empreinte {EMPREINTE} : {'nouvelle version ' + VERSION if nouvelle else 'données inchangées, version ' + VERSION}")

# ---------------------------------------------------------------------------
# Écriture
SORTIE = dossier_sortie("publication")
SITE = os.path.join(SORTIE, "site")
DERNIER = os.path.join(SITE, "dernier")
os.makedirs(os.path.join(DERNIER, "flux"))
os.makedirs(os.path.join(DERNIER, "fiches"))


def ecrire_json(nom, obj):
    with open(os.path.join(DERNIER, nom), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def ecrire_csv(nom, table):
    table.to_csv(os.path.join(DERNIER, nom), index=False, encoding="utf-8-sig", sep=";")


ecrire_json("questions_ecrites.json", {"meta": {"format": "veille-animale/evenements", "version_format": FORMAT,
                                                "genere_le": AUJOURDHUI, "contenu": f"{len(evenements)} questions écrites sur les animaux, 14e à 17e législature",
                                                "source": SOURCE_AN, "cles_de_lecture": CLES_QUESTIONS},
                                       "evenements": evenements})
ecrire_json("textes_officiels.json", {"meta": {"format": "veille-animale/evenements", "version_format": FORMAT,
                                               "genere_le": AUJOURDHUI, "contenu": f"{len(textes_officiels)} textes du Journal officiel sur les animaux, depuis 2012",
                                               "source": SOURCE_JO, "cles_de_lecture": CLES_JO},
                                      "evenements": textes_officiels})
# La base commune : tous les événements datés, allégés (sans textes intégraux), pour le site, les frises et les fils
CHAMPS_COMMUNS = ["id", "type", "source", "date", "titre", "themes", "ministere", "statut", "lien", "etape", "nature",
                  "legislature", "date_reponse", "lois_appliquees", "lois_citees"]
ecrire_json("evenements.json", {"meta": {"format": "veille-animale/evenements", "version_format": FORMAT, "genere_le": AUJOURDHUI,
                                         "contenu": f"{len(evenements_tous)} événements datés : questions écrites et textes du Journal officiel",
                                         "sources": [SOURCE_AN, SOURCE_JO], "cles_de_lecture": CLES_QUESTIONS + CLES_JO,
                                         "detail": "Détail complet de chaque type : questions_ecrites.json et textes_officiels.json (même identifiant)."},
                                "evenements": [{k: e[k] for k in CHAMPS_COMMUNS if k in e} for e in evenements_tous]})
ecrire_json("themes.json", themes_json)
ecrire_json("lois.json", lois_json)
ecrire_json("mesures.json", mesures_json)
ecrire_json("journal.json", journal)
ecrire_csv("questions_ecrites.csv", q_pub)
ecrire_csv("textes_officiels.csv", textes_jo)
ecrire_csv("lois.csv", lois_pub)
ecrire_csv("mesures.csv", mesures_pub)
ecrire_csv("volumes_par_mois.csv", volumes)
ecrire_csv("delais_toutes_questions.csv", delais_toutes)
shutil.copy(os.path.join(RACINE, "publication", "LICENCE.txt"), os.path.join(DERNIER, "LICENCE.txt"))
# Une fiche n'est publiée qu'une fois relue et sa règle tranchée ; sinon elle est seulement annoncée « en préparation ».
for id_fiche, fiche in fiches.items():
    if fiche["meta"]["publiable"]:
        ecrire_json(f"fiches/{id_fiche}.json", fiche)
    else:
        print(f"Fiche {id_fiche} non publiée : en attente de {', '.join(fiche['meta']['en_attente'])}")
ecrire_json("fiches/index.json", {"format": "veille-animale/fiches", "genere_le": AUJOURDHUI, "fiches": [
    {"id": k, "titre": v["georges"]["titre"], "statut": "publiée" if v["meta"]["publiable"] else "en préparation",
     "adresse": f"{A.adresse}/dernier/fiches/{k}.json" if v["meta"]["publiable"] else None} for k, v in fiches.items()]})


# Flux RSS : un par thème, plus un flux général ; les 50 derniers événements (textes publiés, questions, réponses)
def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def items_de(evts):
    items = []
    for e in evts:
        if e["type"] == "texte_officiel":
            items.append((e["date"], "texte", e))
            continue
        items.append((e["date"], "question", e))
        if e["date_reponse"]:
            items.append((e["date_reponse"], "reponse", e))
    return sorted((i for i in items if i[0]), key=lambda i: i[0], reverse=True)[:50]


def ecrire_flux(nom_fichier, titre, evts):
    lignes = []
    for d, genre, e in items_de(evts):
        if genre == "texte":
            titre_item = f"Publié au Journal officiel : {e['titre']}"
            desc = f"{e['nature']}. Thèmes : {', '.join(e['themes'])}. Ministère : {e['ministere']}. Source : Journal officiel."
        else:
            quoi = "Question écrite" if genre == "question" else "Réponse à la question écrite"
            titre_item = f"{quoi} n° {e['id'].split('-')[-1]} ({e['legislature']}e législature) : {e['titre']}"
            desc = (f"Thèmes : {', '.join(e['themes'])}. Ministère : {e['ministere']}. Statut : {e['statut']}. "
                    f"Source : Assemblée nationale.")
        date_rss = format_datetime(datetime.fromisoformat(d).replace(tzinfo=timezone.utc))
        lignes.append(f"<item><title>{escape(titre_item)}</title><link>{escape(e['lien'])}</link>"
                      f"<guid isPermaLink=\"false\">{e['id']}-{genre}</guid><pubDate>{date_rss}</pubDate>"
                      f"<description>{escape(desc)}</description></item>")
    xml = (f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<rss version=\"2.0\"><channel>"
           f"<title>{escape('Veille animale : ' + titre)}</title><link>{A.adresse}/</link>"
           f"<description>{escape('Textes publiés au Journal officiel, questions écrites des députés et réponses des ministres, d’après les données officielles.')}</description>"
           f"<language>fr</language><lastBuildDate>{format_datetime(MAINTENANT)}</lastBuildDate>"
           + "".join(lignes) + "</channel></rss>\n")
    with open(os.path.join(DERNIER, "flux", nom_fichier), "w", encoding="utf-8") as f:
        f.write(xml)


flux = [{"theme": "Tous les thèmes", "adresse": f"{A.adresse}/dernier/flux/tout.xml"}]
ecrire_flux("tout.xml", "tous les thèmes", evenements_tous)
for t in sorted({t for e in evenements_tous for t in e["themes"]}, key=slug):   # tri sans accents : « À classer » à sa place
    ecrire_flux(f"{slug(t)}.xml", t, [e for e in evenements_tous if t in e["themes"]])
    flux.append({"theme": t, "adresse": f"{A.adresse}/dernier/flux/{slug(t)}.xml"})

fichiers = sorted([os.path.relpath(os.path.join(r, f), DERNIER).replace("\\", "/")
                   for r, _, fs in os.walk(DERNIER) for f in fs] + ["index.json"])
index = {
    "format": "veille-animale/index", "version_format": FORMAT, "version": VERSION, "empreinte": EMPREINTE,
    "genere_le": MAINTENANT.isoformat(timespec="seconds"),
    "empreintes_fiches": EMPREINTES_FICHES,
    "sources": [
        {"nom": SOURCE_AN, "legislatures": "14e à 17e", "lue_le": AUJOURDHUI,
         "note": "Archives des 14e, 15e et 16e législatures figées (empreintes MD5 officielles vérifiées) ; 17e législature téléchargée à chaque mise à jour."},
        {"nom": SOURCE_DOLE, "archive": ARCHIVE_DOLE, "archive_publiee_le": DATE_DOLE,
         "note": "Chaque échéancier a sa propre date de mise à jour (echeancier_mis_a_jour)."},
        {"nom": SOURCE_JO, "depuis": "2012-01-01", "lue_le": AUJOURDHUI,
         "note": "Archive complète puis mises à jour quotidiennes ; dernier texte retenu publié le "
                 + (max(e["date"] for e in textes_officiels) if textes_officiels else "(aucun)") + "."},
    ],
    "compteurs": {"questions": len(evenements), "questions_17e": n17, "textes_officiels": len(textes_officiels),
                  "lois": len(lois), "mesures": len(mesures),
                  "mesures_concernant_animaux": int((mesures["concerne_animaux"] == "True").sum())},
    "fichiers": [{"fichier": f, "adresse": f"{A.adresse}/dernier/{f}"} for f in fichiers],
    "flux": flux,
    "licence": "Données : Licence Ouverte 2.0 (Etalab), sources à citer. Voir LICENCE.txt.",
    "methode": "https://github.com/MyQoh/veille-animale",
}
ecrire_json("index.json", index)
shutil.copy(os.path.join(RACINE, "publication", "index.html"), os.path.join(SITE, "index.html"))

# Fichiers d'une nouvelle version datée : tout le dossier dernier/ et les CSV bruts des briques
if nouvelle:
    REL = os.path.join(SORTIE, "release")
    os.makedirs(REL)
    for f in fichiers:   # index.json compris (il est écrit avant cette copie)
        if not f.startswith("flux/"):
            shutil.copy(os.path.join(DERNIER, f), os.path.join(REL, f.replace("/", "_")))
    for src in glob.glob(os.path.join(B1, "*.csv")) + glob.glob(os.path.join(B2, "*.csv")) + glob.glob(os.path.join(B3, "*.csv")):
        if "echantillon" not in src:
            shutil.copy(src, os.path.join(REL, "brut_" + os.path.basename(src)))

resultat = {"nouvelle_version": nouvelle, "version": VERSION, "empreinte": EMPREINTE, "dossier": SORTIE,
            "changements": journal["versions"][0]["changements"] if nouvelle else None}
with open(os.path.join(SORTIE, "resultat.json"), "w", encoding="utf-8") as f:
    json.dump(resultat, f, ensure_ascii=False, indent=1)
print(json.dumps(resultat, ensure_ascii=False, indent=1))
