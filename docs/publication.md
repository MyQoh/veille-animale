# Publication des données (étape 4a)

Statut : **validé le 26/09/2026** (licences comprises), mis en œuvre par `scripts/publier.py`,
`publication/lexique.json`, `publication/controles.json` et le workflow `.github/workflows/nocturne.yml`.
La publication démarre quand ce workflow est sur la branche principale.

## Adresse

Tout est publié sur GitHub Pages : `https://myqoh.github.io/veille-animale/`

- `dernier/` : la dernière version, mise à jour chaque nuit. **C'est l'adresse stable** que lit le site.
- Les versions précédentes sont conservées dans les « Releases » du dépôt (voir Historique).

## Fichiers publiés dans `dernier/`

| Fichier | Pour qui | Contenu |
|---|---|---|
| `index.json` | le site, les robots | Manifeste : date de génération, version du format, liste des fichiers, et pour chaque source sa date de mise à jour (archive de l'Assemblée, archive DOLE, dates des échéanciers). |
| `questions_ecrites.json` | le site | Une entrée par question, champs légers, au format « événements » (voir ci-dessous). Sans les textes intégraux. |
| `questions_ecrites.csv` | associations, journalistes | Toutes les colonnes de la brique 1, textes compris, avec le vocabulaire neutre. |
| `themes.json` | le site | Pour chaque thème et chaque année : nombre de questions, part dans l'ensemble des questions écrites, réponses dans le délai, délai médian, questions closes sans réponse. Avec le point de comparaison « toutes questions écrites » (voir plus bas). |
| `lois.json` et `lois.csv` | le site, les initiés | Les 26 textes de la brique 2 (V4), avec rôle, date de mise à jour de l'échéancier. |
| `mesures.json` et `mesures.csv` | le site, les initiés | Les 199 mesures d'application, avec statut, décret, délai, date de l'échéancier. |
| `volumes_par_mois.csv` | les initiés | Toutes les questions écrites par mois (dénominateur des parts). |
| `flux/<thème>.xml` | quiconque veut suivre un sujet | Flux RSS par thème : les 50 dernières questions et réponses, avec lien vers la source. Plus un flux `flux/tout.xml`. |
| `journal.json` | tout le monde | Journal des mises à jour : pour chaque version, ce qui a changé (nouvelles questions, nouvelles réponses, mesures modifiées). |
| `LICENCE.txt` | tout le monde | Licence et attribution des sources. |

## Format « événements » : de la v0.1 à la v0.2

La v0.1, validée avec Figma Make (`reference/test_evenements.json`), est conservée telle quelle. La v0.2 **ajoute** des champs, sans en retirer ni en renommer, pour que ce qui marche déjà continue de marcher :

| Champ ajouté | Pourquoi |
|---|---|
| `titre_source` | « officiel » ou « extrait du texte » (15e législature) |
| `declencheurs` | liste de { thème, mot, où (titre ou texte), nombre } : alimente « Pourquoi dans ce thème ? » |
| `jours_apres_echeance` | remplace, pour l'affichage, la colonne `retard_jours` de la brique 1 |
| `statut_signalement`, `date_signalement` | règle des dix jours, avec « non disponible » pour la 14e et la 15e |
| `lois_citees` | pont vers les lois (brique 2) |
| `mis_a_jour_le` | date de la donnée, sur chaque entrée |

## Vocabulaire neutre (règle dure, dès maintenant)

Les CSV bruts des briques ne changent pas. La traduction se fait au moment de publier, dans un lexique rangé dans le dépôt (`publication/lexique.json`) :

| Brique 1 | Publié |
|---|---|
| statut « Répondue en retard » | « Répondue après le délai » |
| colonne `retard_jours` | `jours_apres_echeance` |

Un contrôle automatique bloque la publication si le mot « retard » apparaît dans un fichier publié, hors textes officiels cités (texte des questions et des réponses, titres). La passe complète de vocabulaire (étapes, libellés) viendra en finition.

## Point de comparaison « toutes questions écrites »

Pour que « 24 % de réponses dans le délai » ne se lise pas comme propre aux animaux, `themes.json` donne le même taux pour l'ensemble des questions écrites, par législature et par année.

Cela demande une **version 14 de la brique 1** : elle calcule, pour chacune des 186 922 questions lues, la date de réponse et le statut, et les résume dans un nouveau fichier `delais_toutes_questions.csv`. **Rien d'autre ne change** : on vérifiera que les fichiers de la V13 restent identiques.

## Clés de lecture publiées avec les chiffres

- Délai médian : « calculé sur les questions répondues ; X % des questions sont closes sans réponse et n'y figurent pas ».
- 14e et 15e législatures : « signalements non disponibles dans les archives » (jamais zéro).
- 15e législature : « titres extraits du texte des questions ; les comptes par thème ne sont pas strictement comparables avec les autres législatures ».
- Échéanciers : « à la date de leur dernière mise à jour » ; archive DOLE datée.

## Historique (jamais d'écrasement)

`dernier/` est remplacé chaque nuit ; c'est son rôle. L'historique est gardé ailleurs :

- Une **Release datée** est créée quand les données changent vraiment : nouvelle question, nouvelle réponse, changement de statut ou de mesure. Les compteurs qui avancent d'un jour chaque nuit (délais des questions en attente) ne suffisent pas à créer une version.
- Chaque Release contient tous les fichiers publiés et les CSV bruts des briques.
- `journal.json` liste les versions et ce qui a changé.

## Contrôles avant publication (sinon rien n'est publié, et une alerte part)

1. Les 14e, 15e et 16e législatures sont figées : leurs nombres de questions retenues doivent rester 1 245, 1 247 et 658. Tout écart bloque (sauf nouvelle version des règles, validée).
2. La 17e ne peut pas baisser de plus de 1 % d'une nuit à l'autre.
3. Toutes les colonnes attendues sont présentes et non vides là où elles doivent l'être.
4. Lexique : aucun mot interdit dans les champs publiés.
5. Brique 2 : 26 textes et 199 mesures tant que l'archive DOLE ne change pas.

## Licence (choisie)

- **Données publiées** : Licence Ouverte 2.0 (Etalab), la même que les sources, avec attribution « Assemblée nationale » et « DILA, Légifrance » (`publication/LICENCE.txt`).
- **Code** : licence MIT (`LICENSE`).
- **Couche éditoriale** (fiches, registre) : Licence Ouverte 2.0, à confirmer quand elle sera publiée (étape 4b).

## Limites connues, à traiter plus tard

- `questions_ecrites.json` pèse environ 4,5 Mo. Pour le site, un découpage par thème ou par législature sera sans doute utile.
- Les lois ne sont repérées que sous la forme « loi n° AAAA-NNN » (règle de la brique 1). Par exemple, la question n° 3629 (17e) cite « la loi n°1539 du 30 novembre 2021 » sans l'année dans le numéro : elle n'est pas reliée à la loi 2021-1539.
