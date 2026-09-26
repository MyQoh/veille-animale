# Veille animale

Ce que l'État dit et fait sur les animaux, faits et dates à l'appui, à partir des données officielles.

Le projet, ses principes et ses décisions sont décrits dans [CLAUDE.md](CLAUDE.md).

## Contenu du dépôt

| Dossier | Contenu |
|---|---|
| `scripts/` | Les scripts qui téléchargent les données officielles, les classent et calculent les délais. |
| `reference/` | Les carnets Colab d'origine (versions gelées), leurs sorties, et la couche éditoriale manuelle. Jamais modifié. |
| `donnees_brutes/` | Archives officielles téléchargées. Non publié (retéléchargeable). |
| `sorties/AAAA-MM-JJ_HHhMM_<brique>/` | Résultats d'une exécution. Un nouveau dossier à chaque fois, rien n'est écrasé. Non publié pour l'instant. |

## Les scripts

| Script | Source | Carnet d'origine |
|---|---|---|
| `brique1_questions_ecrites.py` | Questions écrites de l'Assemblée nationale, 14e à 17e législature | `aspirateur_questions_ecrites_v13.ipynb` |
| `brique2_echeanciers.py` (V4) | Échéanciers d'application des lois (DOLE, DILA) | `brique2_echeanciers_v3.ipynb` |
| `comparer.py` | Compare une sortie à une sortie de référence, ligne par ligne | |

Les deux briques reprennent la logique des carnets **à l'identique**, cellule par cellule, ce qui a été vérifié
contre les sorties Colab. Les seules différences sont listées en tête de chaque script : emplacement des fichiers,
retrait de ce qui est propre à Colab, et deux options de test (`--legislatures` pour un échantillon,
`--date-reference` pour fixer la date du jour).

Depuis, la brique 2 est passée en version 4 : une loi n'est « Loi suivie » que si au moins une de ses mesures
concerne les animaux (changelog en tête du script).

La brique 2 utilise le CSV de la brique 1 (lois citées dans au moins trois questions) : toujours lancer la brique 1 d'abord.

## Lancer les scripts

Il faut Python 3 et les bibliothèques de `requirements.txt`.

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\brique1_questions_ecrites.py
.venv\Scripts\python scripts\brique2_echeanciers.py
```

Vérifier une sortie contre la référence Colab :

```
.venv\Scripts\python scripts\comparer.py reference\sorties_colab\questions_ecrites_animaux_2012_2026_v13.csv sorties\AAAA-MM-JJ_HHhMM_brique1\questions_ecrites_animaux_2012_2026_v13.csv --cle uid
```

## Lancement automatique chaque nuit

Le fichier `.github/workflows/nocturne.yml` lance la brique 1 puis la brique 2 chaque nuit sur GitHub Actions,
à 1 h UTC (3 h à Paris en été, 2 h en hiver). On peut aussi le lancer à la main : onglet « Actions »,
« Lancement nocturne », bouton « Run workflow ».

- Les archives figées (14e, 15e, 16e législatures, et DOLE tant que la DILA n'en publie pas de nouvelle) sont gardées
  en cache et ne sont pas retéléchargées. Seule la 17e législature l'est chaque nuit.
- Le serveur de l'Assemblée coupe parfois les connexions : la brique 1 est retentée jusqu'à 5 fois, la brique 2 jusqu'à 3 fois.
- Les sorties de chaque exécution sont téléchargeables pendant 90 jours depuis la page de l'exécution (« Artifacts »).
- Les versions des bibliothèques sont fixées dans `requirements.txt` : ce sont celles qui ont reproduit Colab à l'identique.

## Points repérés pendant la transposition, conservés tels quels

Ils seront traités dans une version ultérieure, après validation :

- les statuts et une colonne des données utilisent le mot « retard » (« Répondue en retard », `retard_jours`) ; à reformuler avant tout affichage sur le site ;
- le motif `dissequ\\w*` (thème Expérimentation animale) ne reconnaît jamais « disséquer » ;
- dans la brique 2, la sélection des lois utilise une version simplifiée du nettoyage des titres.
