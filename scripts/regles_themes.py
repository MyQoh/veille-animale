"""Règles de thèmes de la brique 1 (version 14), extraites automatiquement de scripts/brique1_questions_ecrites.py.

Ne pas modifier ici : ce fichier est une copie exacte de la cellule 2 de la brique 1, pour que les autres briques
classent avec exactement les mêmes règles. Pour le régénérer : python scripts/extraire_regles_themes.py
"""
import re, unicodedata

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

