"""Fiches sujet : un modèle fixe, un sujet décrit dans publication/sujets/<id>.json vient s'y couler.

Chaque fiche a deux profondeurs :
- « georges » : l'essentiel en un écran. Trois points clés et trois chiffres au maximum, uniquement de
  source officielle, jamais un élément à vérifier ; plus la dernière avancée et la prochaine échéance.
- « inities » : tout le reste. Frise complète, questions écrites avec délais et point de comparaison,
  lois et mesures liées, règle du sujet affichée en clair, glossaire, sources.

La couche automatique est recalculée chaque nuit. La couche éditoriale vient du fichier du sujet (relu).
Tout élément marqué bloquant_publication n'est publié nulle part : seul leur nombre est indiqué.
Utilisé par scripts/publier.py.
"""
import glob, json, os, re, unicodedata

import pandas as pd

MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def sans_accents(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower().replace("’", "'"))


def date_affichee(d):
    t = pd.Timestamp(d)
    return f"{t.day}{'er' if t.day == 1 else ''} {MOIS[t.month - 1]} {t.year}"


def pourcent(x):
    return f"{round(x * 100)} %"


class ErreurFiche(Exception):
    pass


def questions_du_sujet(sujet, q):
    """Questions retenues par la règle du sujet, avec les décisions manuelles."""
    r = sujet["regle"]
    titre = q["titre"].map(sans_accents)
    texte = (titre + " " + q["texte_question"].map(sans_accents))
    inclure = re.compile(r"\b(?:" + "|".join(r["inclure"]) + r")")
    # Comme pour les thèmes de la brique 1 : le titre suffit ; sinon le texte doit insister (mentions_min_dans_le_texte)
    n_min = r.get("mentions_min_dans_le_texte", 1)
    garde = titre.str.contains(inclure) | (q["texte_question"].map(sans_accents).str.count(inclure) >= n_min)
    if r.get("exclure"):
        garde &= ~texte.str.contains(re.compile(r"\b(?:" + "|".join(r["exclure"]) + r")"))
    garde |= q["uid"].isin(r.get("questions_ajoutees", []))
    garde &= ~q["uid"].isin(r.get("questions_retirees", []))
    return q[garde]


def comparaison_ponderee(sq, delais_toutes):
    """Taux de réponse dans le délai de l'ensemble des questions écrites, pondéré comme le sujet :
    même répartition des questions répondues entre législatures. Évite de comparer des périodes différentes."""
    ref = delais_toutes[delais_toutes["annee"] == "toutes"].set_index("legislature")
    rep = sq[sq["date_reponse"] != ""].groupby("legislature").size()
    poids = sum(int(n) for n in rep.values)
    if not poids:
        return None
    return sum(int(n) * float(ref.loc[leg, "part_dans_le_delai_parmi_repondues"]) for leg, n in rep.items()) / poids


def statistiques(sq, delais_toutes):
    rep = sq[sq["date_reponse"] != ""]
    delais = pd.to_numeric(rep["delai_jours"], errors="coerce")
    dans = (rep["statut"] == "Répondue dans le délai").mean() if len(rep) else None
    # Questions en série : plusieurs députés posent la même question, le ministre répond d'un même texte.
    # On compte les textes de réponse distincts (espaces normalisés), pour ne pas lire 30 réponses identiques comme 30 réponses.
    textes = rep["texte_reponse"].str.replace(r"\s+", " ", regex=True).str.strip()
    textes = textes[textes != ""]
    return {
        "questions": len(sq),
        "par_legislature": {int(k): int(v) for k, v in sq["legislature"].value_counts().sort_index().items()},
        "repondues": len(rep),
        "reponses_au_texte_distinct": int(textes.nunique()),
        "part_dans_le_delai_parmi_repondues": round(dans, 4) if dans is not None else None,
        "reference_toutes_questions_meme_repartition": round(comparaison_ponderee(sq, delais_toutes), 4) if len(rep) else None,
        "delai_median_jours_repondues": float(delais.median()) if len(rep) else None,
        "closes_sans_reponse": int(sq["statut"].str.startswith("Close sans réponse").sum()),
        "en_attente": int(sq["statut"].str.startswith("En attente").sum()),
        "premiere_question": sq["date_question"].min()[:10] if len(sq) else None,
        "derniere_question": sq["date_question"].max()[:10] if len(sq) else None,
    }


def chiffre_questions(stats):
    if not stats["questions"]:
        return None
    lecture = (f"{stats['repondues']} ont reçu une réponse, dont {pourcent(stats['part_dans_le_delai_parmi_repondues'])} "
               f"dans le délai de deux mois. Pour comparaison, sur la même période, toutes questions écrites confondues : "
               f"{pourcent(stats['reference_toutes_questions_meme_repartition'])}.")
    if stats["closes_sans_reponse"]:
        lecture += f" {stats['closes_sans_reponse']} questions ont été closes sans réponse à la fin d'une législature."
    if stats["repondues"] and stats["reponses_au_texte_distinct"] < 0.8 * stats["repondues"]:
        lecture += (f" Certaines questions sont posées à l'identique par plusieurs députés et reçoivent la même réponse : "
                    f"{stats['reponses_au_texte_distinct']} réponses au texte différent pour {stats['repondues']} questions répondues.")
    return {
        "valeur": str(stats["questions"]),
        "libelle": f"Questions écrites de députés sur ce sujet depuis {stats['premiere_question'][:4]}",
        "lecture": lecture,
        "source": {"libelle": "Assemblée nationale, questions écrites (calcul automatique, règle du sujet publiée)",
                   "url": "https://data.assemblee-nationale.fr", "type": "officiel"},
        "calcule_automatiquement": True,
    }


def verifier_officiel(element, ou):
    src = element.get("source") or {}
    if src.get("type") != "officiel" or not src.get("url"):
        raise ErreurFiche(f"{ou} : l'écran de Georges n'accepte que des éléments de source officielle, avec un lien")
    if element.get("bloquant_publication") or element.get("a_verifier"):
        raise ErreurFiche(f"{ou} : un élément à vérifier ne peut pas figurer sur l'écran de Georges")


def construire(sujet, q, evenements, lois_json, mesures_json, delais_toutes, aujourdhui):
    ed = sujet["editorial"]
    publiables = [c for c in ed["chronologie"] if not c.get("bloquant_publication")]
    en_verification = len(ed["chronologie"]) - len(publiables)

    sq = questions_du_sujet(sujet, q)
    stats = statistiques(sq, delais_toutes)
    ids = set(sq["uid"])
    evts = sorted((e for e in evenements if e["lien"].rsplit("/", 1)[-1] in ids), key=lambda e: e["date"] or "", reverse=True)

    # Frise : éléments éditoriaux publiables + lois liées + décrets publiés des mesures liées au sujet
    frise = [{"date": c["date"], "date_affichee": c.get("date_affichee") or date_affichee(c["date"]), "statut": c["statut"],
              "texte": c["texte"], "source": c["source"], "origine": "rédigé et sourcé"} for c in publiables]
    chiffres_ed = [{k: v for k, v in c.items() if k != "a_relire"} for c in ed.get("chiffres", [])]
    glossaire = [{k: v for k, v in g.items() if k != "a_relire"} for g in ed.get("glossaire", [])]
    motif = re.compile(r"\b(?:" + "|".join(sujet["regle"]["inclure"]) + r")")
    for loi in lois_json["lois"]:
        if loi["loi_numero"] in sujet.get("lois_liees", []) and loi["promulgation"]:
            if not any(f["date"] == loi["promulgation"] and loi["loi_numero"] in f["source"].get("libelle", "") for f in frise):
                frise.append({"date": loi["promulgation"], "date_affichee": date_affichee(loi["promulgation"]), "statut": "fait",
                              "texte": f"Promulgation : {loi['loi_titre']}.",
                              "source": {"libelle": "Légifrance", "url": loi["lien_legifrance"], "type": "officiel"},
                              "origine": "automatique"})
    mesures_liees = [m for m in mesures_json["mesures"] if m["loi_numero"] in sujet.get("lois_liees", [])
                     and motif.search(sans_accents((m["objet"] or "") + " " + (m["base_legale"] or "")))]
    for m in mesures_liees:
        if m["statut"] == "Décret publié" and m["decret_date"]:
            frise.append({"date": m["decret_date"], "date_affichee": date_affichee(m["decret_date"]), "statut": "fait",
                          "texte": f"Texte d'application publié : {m['decret']} ({m['objet']}).",
                          "source": {"libelle": "Légifrance", "url": m["decret_lien"], "type": "officiel"},
                          "origine": "automatique"})
    frise.sort(key=lambda f: f["date"])

    passes = [f for f in frise if f["date"] <= aujourdhui and f["statut"] in ("fait", "evalue")]
    a_venir = [f for f in frise if f["date"] > aujourdhui and f["statut"] == "attendu"]
    derniere, prochaine = (passes[-1] if passes else None), (a_venir[0] if a_venir else None)

    # Écran de Georges
    g = sujet["georges"]
    if len(g["points_cles"]) > 3 or len(g["chiffres"]) > 3:
        raise ErreurFiche(f"{sujet['id']} : trois points clés et trois chiffres au maximum pour Georges")
    points = []
    for i, p in enumerate(g["points_cles"]):
        verifier_officiel(p, f"{sujet['id']}, point clé {i + 1}")
        point = {"texte": p["texte"], "source": p["source"], "relu": not p.get("a_relire")}
        if p.get("source_complementaire"):
            verifier_officiel({"source": p["source_complementaire"]}, f"{sujet['id']}, point clé {i + 1}, source complémentaire")
            point["source_complementaire"] = p["source_complementaire"]
        points.append(point)
    chiffres = []
    for i, c in enumerate(g["chiffres"]):
        if c.get("depuis") == "editorial":
            ch = {k: v for k, v in ed["chiffres"][c["index"]].items() if k != "a_relire"}
        elif c.get("depuis") == "automatique":
            ch = chiffre_questions(stats)
            if ch is None:
                continue
        else:
            ch = {k: c[k] for k in ("valeur", "libelle", "lecture", "source")}
        verifier_officiel(ch, f"{sujet['id']}, chiffre {i + 1}")
        ch["relu"] = not c.get("a_relire")
        chiffres.append(ch)
    # La couche éditoriale (frise, chiffres, glossaire) doit aussi être relue : un élément marqué a_relire bloque la fiche
    editorial_a_relire = sum(1 for cle in ("chronologie", "chiffres", "glossaire") for x in ed.get(cle, []) if x.get("a_relire"))
    tout_relu = all(p["relu"] for p in points) and all(c["relu"] for c in chiffres) and not editorial_a_relire

    def moment(f):
        return None if f is None else {k: f[k] for k in ("date", "date_affichee", "texte", "source")}

    a_trancher = {k: v for k, v in sujet["regle"].get("a_trancher", {}).items() if not k.startswith("_") and v}
    publiable = tout_relu and not a_trancher
    return {
        "meta": {"format": "veille-animale/fiche", "version_format": "0.1", "id": sujet["id"], "genere_le": aujourdhui,
                 "publiable": publiable,
                 "en_attente": ([] if tout_relu else ["relecture de l'écran de Georges et de la couche éditoriale"])
                               + ([f"{sum(len(v) for v in a_trancher.values())} questions à trancher dans la règle du sujet"] if a_trancher else []),
                 "derniere_verification_editoriale": ed.get("derniere_verification"),
                 "relecture": "complète" if tout_relu else "en attente : certains éléments de l'écran de Georges n'ont pas encore été relus"},
        "georges": {
            "titre": sujet["titre"],
            "points_cles": points,
            "chiffres": chiffres,
            "derniere_avancee": moment(derniere),
            "prochaine_echeance": moment(prochaine),
        },
        "inities": {
            "en_bref": ed.get("en_bref"),
            "frise": frise,
            "elements_en_verification_non_publies": en_verification,
            "questions_ecrites": {
                "regle": {"perimetre": sujet["regle"]["perimetre"], "mots_recherches": sujet["regle"]["inclure"],
                          "questions_ajoutees_a_la_main": sujet["regle"].get("questions_ajoutees", []),
                          "questions_retirees_a_la_main": sujet["regle"].get("questions_retirees", []),
                          "decisions": sujet["regle"].get("decisions", [])},
                "statistiques": stats,
                "cles_de_lecture": [
                    "Délai médian calculé sur les seules questions répondues.",
                    "Point de comparaison : taux de réponse dans le délai de l'ensemble des questions écrites, avec la même répartition entre législatures que les questions de ce sujet.",
                    "Questions en série : plusieurs députés posent souvent la même question, et le ministre y répond d'un même texte. reponses_au_texte_distinct compte les réponses différentes ; le nombre de questions ne mesure donc pas le nombre de sujets distincts soulevés.",
                ],
                "liste": [{k: e[k] for k in ("id", "legislature", "date", "titre", "titre_source", "ministere", "date_reponse",
                                             "delai_jours", "statut", "signalee", "lien")} for e in evts],
            },
            "lois_liees": [l for l in lois_json["lois"] if l["loi_numero"] in sujet.get("lois_liees", [])],
            "mesures_liees": mesures_liees,
            "chiffres": chiffres_ed,
            "glossaire": glossaire,
            "sources_principales": ed.get("sources_principales", []),
        },
    }


def toutes_les_fiches(dossier_sujets, **donnees):
    fiches = {}
    for chemin in sorted(glob.glob(os.path.join(dossier_sujets, "*.json"))):
        with open(chemin, encoding="utf-8") as f:
            sujet = json.load(f)
        fiche = construire(sujet, **donnees)
        fiche["meta"]["_voir_aussi_demande"] = sujet.get("voir_aussi", [])
        fiches[sujet["id"]] = fiche
    # « Voir aussi » : seulement vers des fiches publiées ; un lien vers une fiche absente reste en attente, sans erreur
    for fiche in fiches.values():
        demandes = fiche["meta"].pop("_voir_aussi_demande")
        fiche["voir_aussi"] = [{"id": i, "titre": fiches[i]["georges"]["titre"]} for i in demandes
                               if i in fiches and fiches[i]["meta"]["publiable"]]
    return fiches
