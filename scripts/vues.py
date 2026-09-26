"""Vues prêtes à afficher (pour le site dessiné dans Figma) : le fil « de l'intention au résultat ».

Tout est calculé automatiquement à partir des liens déjà présents dans les données :
- une question écrite cite une loi (colonne lois_citees, brique 1) ;
- l'échéancier d'une loi liste les mesures d'application promises (brique 2) ;
- le Journal officiel indique lui-même quel décret ou arrêté applique quelle loi (lien « application », brique 3).

Vues produites (format fixe : une étape sans source branchée est marquée « non disponible », jamais vide) :
- fils/<loi>.json : pour une loi, les cinq étapes du fil ;
- fils/index.json : la liste des lois qui ont un fil ;
- matrice.json : pour chaque thème, le nombre d'événements à chaque étape ;
- themes_par_an.json : pour chaque thème, le nombre d'événements par an et par type (petits graphiques).
Utilisé par scripts/publier.py.
"""
from collections import Counter, defaultdict

ETAPES = [
    {"cle": "demande", "libelle": "Demandé", "detail": "Questions écrites des députés qui citent la loi"},
    {"cle": "vote", "libelle": "Voté", "detail": "Promulgation de la loi"},
    {"cle": "promis", "libelle": "Promis", "detail": "Mesures d'application prévues par l'échéancier de la loi"},
    {"cle": "applique", "libelle": "Appliqué", "detail": "Décrets et arrêtés publiés qui appliquent la loi"},
    {"cle": "en_attente", "libelle": "Pas encore appliqué", "detail": "Mesures prévues sans texte d'application publié"},
]


# Lois exclues en brique 2 (V3) : sans rapport avec le sort des animaux malgré leurs citations
LOIS_EXCLUES = {"2023-1322", "2016-1086"}


def construire(q_pub, evenements, textes_officiels, lois_json, mesures_json, aujourdhui, adresse):
    # ---- Lois qui ont un fil : lois suivies (brique 2), lois appliquées par un texte retenu (brique 3),
    #      lois citées dans au moins trois questions écrites (brique 1)
    citations = Counter(x for v in q_pub["lois_citees"] for x in v.split(", ") if x)
    appliquee_par, visee_par = defaultdict(list), defaultdict(list)
    for t in textes_officiels:
        for n in t["lois_appliquees"]:
            appliquee_par[n].append(t)
        for n in t.get("lois_visees", []):
            if n not in t["lois_appliquees"] and n != t.get("numero"):
                visee_par[n].append(t)
    lois_par_num = {}
    for l in lois_json["lois"]:
        if l["loi_numero"] and l["type"] == "LOI_PUBLIEE":
            lois_par_num[l["loi_numero"]] = l
    textes_loi = {t["numero"]: t for t in textes_officiels if t["nature"] == "Loi" and t["numero"]}
    numeros = sorted((set(lois_par_num) | set(appliquee_par) | {n for n, c in citations.items() if c >= 3}) - LOIS_EXCLUES)

    fils = {}
    for n in numeros:
        loi = lois_par_num.get(n)
        texte_loi = textes_loi.get(n)
        titre = (loi or {}).get("loi_titre") or (texte_loi or {}).get("titre") or f"Loi n° {n}"
        promulgation = (loi or {}).get("promulgation") or ((texte_loi or {}).get("date_signature"))
        lien = (loi or {}).get("lien_legifrance") or (texte_loi or {}).get("lien")
        questions = [e for e in evenements if n in e.get("lois_citees", [])]
        mesures = [m for m in mesures_json["mesures"] if m["loi_numero"] == n]
        mesures_animales = [m for m in mesures if m["concerne_animaux"]]
        publiees = [m for m in mesures_animales if m["statut"] == "Décret publié"]
        attente = [m for m in mesures_animales if m["statut"] in ("Aucune mention", "Publication annoncée",
                   "Publication annoncée, date dépassée à la mise à jour de l'échéancier", "À examiner")]
        textes_app = sorted(appliquee_par.get(n, []), key=lambda t: t["date"])
        textes_vis = sorted(visee_par.get(n, []), key=lambda t: t["date"])
        echeancier = loi is not None and loi.get("echeancier_present")

        def q_court(e):
            return {k: e.get(k) for k in ("id", "date", "titre", "statut", "date_reponse", "ministere", "lien")}

        def m_court(m):
            return {k: m.get(k) for k in ("numero_ordre", "article", "objet", "statut", "decret", "decret_date", "decret_lien",
                                          "publication_annoncee", "delai_jours", "echeancier_mis_a_jour", "themes")}

        fils[n] = {
            "meta": {"format": "veille-animale/fil", "version_format": "0.1", "genere_le": aujourdhui,
                     "cles_de_lecture": [
                         "Demandé : questions écrites qui citent la loi sous la forme « loi n° AAAA-NNN ». Une question qui la cite autrement n'est pas comptée.",
                         "Promis et Pas encore appliqué : d'après l'échéancier de la loi, à la date de sa dernière mise à jour ; seules les mesures qui concernent les animaux sont retenues.",
                         "Appliqué : textes du Journal officiel dont le titre parle d'animaux et que le Journal officiel déclare comme application de la loi, plus les décrets indiqués dans l'échéancier. Les textes qui citent seulement la loi (visas) sont listés à part et ne sont pas comptés.",
                         "Une étape « non disponible » signifie que la source ne renseigne pas l'information pour cette loi, pas qu'il ne s'est rien passé."]},
            "loi": {"numero": n, "titre": titre, "promulgation": promulgation, "lien": lien,
                    "role": (loi or {}).get("role"), "echeancier_mis_a_jour": (loi or {}).get("echeancier_mis_a_jour")},
            "etapes": {
                "demande": {**ETAPES[0], "disponible": True, "nombre": len(questions),
                            "avant_la_loi": sum(1 for e in questions if promulgation and e["date"] and e["date"] < promulgation),
                            "apres_la_loi": sum(1 for e in questions if promulgation and e["date"] and e["date"] >= promulgation),
                            "elements": [q_court(e) for e in sorted(questions, key=lambda e: e["date"] or "")]},
                "vote": {**ETAPES[1], "disponible": bool(promulgation), "date": promulgation, "lien": lien},
                "promis": {**ETAPES[2], "disponible": bool(echeancier), "nombre": len(mesures_animales) if echeancier else None,
                           "echeancier_mis_a_jour": (loi or {}).get("echeancier_mis_a_jour"),
                           "elements": [m_court(m) for m in mesures_animales] if echeancier else []},
                "applique": {**ETAPES[3], "disponible": True, "nombre": len(textes_app) + len(publiees),
                             "textes_journal_officiel": [{k: t[k] for k in ("id", "date", "titre", "nature", "etape", "lien")} for t in textes_app],
                             "decrets_de_l_echeancier": [m_court(m) for m in publiees],
                             # lien plus faible : le texte cite la loi (souvent dans ses visas) sans déclarer l'appliquer
                             "textes_qui_citent_la_loi": {"nombre": len(textes_vis),
                                                          "note": "Textes publiés dont le titre parle d'animaux et qui citent la loi, sans que le Journal officiel les déclare comme application de la loi. Non comptés dans « Appliqué ».",
                                                          "elements": [{k: t[k] for k in ("id", "date", "titre", "nature", "lien")} for t in textes_vis]}},
                "en_attente": {**ETAPES[4], "disponible": bool(echeancier), "nombre": len(attente) if echeancier else None,
                               "elements": [m_court(m) for m in attente] if echeancier else []},
            },
        }

    index = {"format": "veille-animale/fils", "genere_le": aujourdhui, "etapes": ETAPES, "fils": [
        {"loi": n, "titre": f["loi"]["titre"], "promulgation": f["loi"]["promulgation"],
         "compte_par_etape": {k: v.get("nombre") if v["disponible"] else None for k, v in f["etapes"].items() if k != "vote"},
         "adresse": f"{adresse}/dernier/vues/fils/{n}.json"} for n, f in fils.items()]}

    # ---- Matrice thèmes × types d'événements, et séries par an (petits graphiques)
    colonnes = ["Questions écrites", "Réponses des ministres", "Lois et ordonnances", "Textes d'application d'une loi",
                "Autres textes réglementaires"]
    matrice, par_an = defaultdict(Counter), defaultdict(lambda: defaultdict(Counter))
    for e in evenements:
        for t in e["themes"]:
            matrice[t]["Questions écrites"] += 1
            par_an[t][(e["date"] or "")[:4]]["Questions écrites"] += 1
            if e.get("date_reponse"):
                matrice[t]["Réponses des ministres"] += 1
                par_an[t][e["date_reponse"][:4]]["Réponses des ministres"] += 1
    for e in textes_officiels:
        col = {"Loi ou ordonnance": "Lois et ordonnances", "Texte d'application d'une loi": "Textes d'application d'une loi"}.get(
            e["etape"], "Autres textes réglementaires")
        for t in e["themes"]:
            matrice[t][col] += 1
            par_an[t][e["date"][:4]][col] += 1
    matrice_json = {"format": "veille-animale/matrice", "genere_le": aujourdhui, "colonnes": colonnes,
                    "cles_de_lecture": ["Un événement peut relever de plusieurs thèmes : il est compté dans chacun.",
                                        "Questions écrites : depuis juin 2012 (14e législature). Textes du Journal officiel : depuis janvier 2012.",
                                        "Les textes publiés et les questions ne se comparent pas en volume : un arrêté et une question n'ont pas le même poids."],
                    "lignes": [{"theme": t, **{c: matrice[t][c] for c in colonnes}} for t in sorted(matrice)]}
    themes_par_an = {"format": "veille-animale/themes-par-an", "genere_le": aujourdhui, "series": colonnes,
                     "reperes": [{"date": "2015-02-16", "libelle": "Les animaux reconnus « êtres vivants doués de sensibilité » (Code civil)"}],
                     "cles_de_lecture": ["Année en cours incomplète.",
                                         "Pour comparer des années, préférer les parts de themes.json aux volumes bruts : le nombre total de questions écrites varie beaucoup d'une année à l'autre."],
                     "themes": [{"theme": t, "annees": [{"annee": a, **{c: par_an[t][a][c] for c in colonnes}}
                                                          for a in sorted(x for x in par_an[t] if x)]} for t in sorted(par_an)]}
    return fils, index, matrice_json, themes_par_an
