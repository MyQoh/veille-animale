# Veille animale : dossier de passation

Ce document résume un projet mené jusqu'ici dans une conversation claude.ai. Il sert de point de départ pour Claude Code. Le lire en entier avant toute action.

## Le projet en une phrase

Un site qui montre, faits et dates à l'appui, ce que l'État dit et fait sur les animaux, lisible par n'importe qui, sans leçon de morale.

## Pour qui

- **Georges**, 56 ans, pas intéressé par la politique, qui se pose une question concrète (« je ne vois plus de renards ») et veut une réponse claire, sans se faire culpabiliser.
- **Les associations, journalistes et citoyens engagés**, qui veulent la même base en version complète : sources, délais, exports, méthode.

Même base de données, deux profondeurs de lecture.

## Principes non négociables

1. **Sources officielles uniquement** pour les données automatiques. Toute source secondaire est marquée comme telle et ne s'affiche pas comme un fait établi.
2. **Neutralité** : aucun classement d'élus, aucune note, aucun adjectif qui juge. Le mot « retard » est interdit dans l'interface : on écrit « échéance dépassée », « répondue après le délai ».
3. **Honnêteté sur les limites** : chaque donnée garde sa date de mise à jour, chaque chiffre fragile est accompagné de sa clé de lecture, chaque classement indique le mot qui l'a déclenché.
4. **Jamais d'écrasement** : chaque version produit des fichiers nouveaux. On teste sur un échantillon avant de généraliser.
5. **Ligne d'arrivée par brique** : chaque brique a des critères de fin explicites. Une brique validée est gelée.

## La propriétaire du projet

Marylène travaille par itérations serrées, une couche validée avant la suivante. Elle ne code pas mais comprend la technique, relit les résultats avec rigueur et veut voir les sources. Ne pas extrapoler sans le dire. Préférer une limite documentée à un chiffre qui sonne bien. Écrire en français, sans tiret long (quadratin).

## Architecture visée

- **Cuisine** : scripts Python lancés chaque nuit par GitHub Actions. Ils téléchargent les données officielles, les classent, calculent les délais.
- **Frigo** : fichiers de sortie (CSV complets, JSON légers) publiés à une adresse stable, par exemple dans le dépôt ou via GitHub Pages.
- **Salle** : le site, prévu dans Figma Make, qui lit le frigo. Un test a validé que Figma Make sait lire un JSON publié en ligne. Les crédits Figma Make sont limités : ne pas compter dessus pour itérer.

## Brique 1 : questions écrites de l'Assemblée nationale (gelée, version 13)

Carnet de référence : `reference/aspirateur_questions_ecrites_v13.ipynb`. C'est la logique à transposer telle quelle en script.

**Sources** : archives JSON de data.assemblee-nationale.fr, 14e à 17e législature (2012 à aujourd'hui). La 14e et la 15e sont un seul gros fichier lu en flux (ijson) ; la 16e et la 17e ont un fichier par question. Téléchargement par morceaux avec reprise, vérification MD5 officielle pour les archives figées (valeurs dans le carnet).

**Périmètre décidé** : le sort des animaux eux-mêmes (traitement, statut, gestion de leurs populations), pas l'économie des filières.
- Rubriques « animaux » et « chasse et pêche » prises en entier.
- Rubriques élevage, agriculture, environnement, aquaculture : admises seulement si le titre parle du sort des animaux, ou si le texte y revient au moins trois fois. Une question d'une rubrique large sans aucun thème est écartée.
- Exceptions assumées : les épizooties (tout, y compris l'indemnisation) et l'apiculture (rattachée à l'élevage).
- Nuisibles venus des rubriques agricoles : admis seulement si la question parle de la méthode de lutte (pesticides, piégeage, régulation), pas seulement des dégâts.
- Filière équestre : l'économie est écartée, le bien-être des chevaux reste.

**Thèmes** (une question peut en avoir plusieurs) : Animaux de compagnie, Animaux d'élevage, Épizooties et abattages sanitaires, Chasse et pêche de loisir, Faune sauvage, Captivité et spectacle, Maltraitance et justice, Santé animale et vétérinaires, Nuisibles et espèces invasives, Expérimentation animale, Condition animale (général). Règles de mots-clés dans le carnet, transparentes : le titre suffit, le texte doit insister (au moins deux mentions).

**Délais** : deux mois (article 135 du règlement de l'Assemblée). Avant la résolution du 28 novembre 2014, un mois prolongeable d'un mois : on retient le maximum de deux mois. Signalement : réponse attendue sous dix jours, règle non appliquée avant 2014. Questions sans réponse à la fin d'une législature : closes (caduques), compteur arrêté à la date de fin.

**Particularités documentées** :
- La 15e législature n'a aucun titre officiel dans l'archive : titre extrait du texte (« attire l'attention de... sur... »), colonne `titre_source`.
- Aucun signalement enregistré dans les archives de la 14e et de la 15e : à afficher comme « non disponible », jamais comme zéro.
- Comparaison avant / après la loi du 16 février 2015 (reconnaissance de la sensibilité animale) : toujours en part de l'ensemble des questions écrites, jamais en volume brut (1,11 % avant, 1,42 % après, au sein de la 14e législature).

**Résultats de référence (V13)** : 3 902 questions retenues sur 186 922 lues. Réponses dans le délai : 42 % (14e), 31 % (15e), 38 % (16e), 24 % (17e, en cours). Délai médian de 70 à 116 jours. Moins de 5 % de questions à classer par législature.

## Brique 2 : échéanciers d'application des lois (gelée, version 3)

Carnet de référence : `reference/brique2_echeanciers_v3.ipynb`.

**Source** : jeu DOLE de la DILA (dossiers législatifs de Légifrance), archive `Freemium_dole_global_*.tar.gz` sur https://echanges.dila.gouv.fr/OPENDATA/DOLE/. Chaque dossier : `/DOSSIER_LEGISLATIF/CONTENU/ECHEANCIER` (attribut `derniere_maj`) avec des `LIGNE` : NUMERO_ORDRE, ARTICLE, BASE_LEGALE, OBJET, DECRET, CID_LOI_CIBLE, DATE_PREVUE.

**Pièges identifiés** : le champ DECRET contient parfois une annonce (« Publication envisagée en décembre 2022 »), un renvoi (« déjà appliquée par arrêté ») ou une explication (« pas nécessaire »). Statuts : Décret publié, Publication annoncée, Publication annoncée avec date dépassée à la mise à jour de l'échéancier, Appliquée par un texte existant, Sans objet. Les échéanciers cessent d'être mis à jour : toujours afficher leur date.

**Sélection des lois** : titre parlant d'animaux, ou loi citée dans au moins trois questions écrites (colonne `lois_citees` de la brique 1). Exclues : loi de finances pour 2024 (2023-1322), loi organique AFB (2016-1086). Rôle « Loi suivie » ou « Texte lié » (ordonnances, projets, propositions de loi, lois sans échéancier). Chaque mesure est classée avec les thèmes de la brique 1 (colonne `concerne_animaux`).

**Correction à intégrer** : une loi n'est « suivie » que si au moins une de ses mesures concerne les animaux (sinon la loi de 2005 sur les territoires ruraux, 75 mesures, aucune animale, fausse les chiffres).

**Résultats de référence** : 57 mesures concernant les animaux, 49 appliquées par décret, délai médian de 198 jours entre la loi et son décret.

## Couche éditoriale (manuelle, sourcée)

- `reference/registre_verifications_v1.csv` : vérifications manuelles des mesures annoncées et jamais confirmées dans les échéanciers (liste positive des animaux sauvages de compagnie, décret frelon, agrainage du sanglier, dérogations cirques, fichier du permis de chasser). À terme, l'API Légifrance (gratuite sur inscription, via PISTE) pourra automatiser ces contrôles.
- `reference/fiche_chats_errants.json` : fiche pilote sourcée, deux profondeurs (En bref, chronologie typée, chiffres avec clé de lecture, glossaire, questions écrites). Les éléments `a_verifier` et `bloquant_publication` ne doivent pas s'afficher comme établis.
- `reference/test_evenements.json` : format commun « événements » v0.1, validé avec Figma Make.

## Suite proposée, dans l'ordre

1. Créer la structure du dépôt et transposer les briques 1 et 2 en scripts Python, **à logique strictement identique** aux carnets de référence. Vérifier sur un échantillon que les sorties correspondent aux résultats de référence ci-dessus.
2. Intégrer la correction « loi suivie ».
3. Écrire le workflow GitHub Actions nocturne, avec mise en cache des archives figées (14e, 15e, 16e, DOLE) pour ne pas les retélécharger chaque nuit.
4. Publier les sorties : CSV complets pour les associations, JSON légers pour le site, et la fiche chats errants régénérée automatiquement à partir des données.
5. Plus tard : API Légifrance pour le registre, Sénat, Journal officiel.

Avant chaque étape : présenter le plan à Marylène et attendre sa validation.
