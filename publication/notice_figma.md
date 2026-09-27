# Veille animale : notice pour dessiner le site

Ce site montre, faits et dates à l'appui, ce que l'État dit et fait sur les animaux. Toutes les données sont
publiées chaque nuit, automatiquement, à cette adresse :

**https://myqoh.github.io/veille-animale/dernier/**

Le site ne fait que lire ces fichiers et les mettre en forme. Il ne calcule rien lui-même. Les fichiers gardent
toujours la même forme : quand une nouvelle source est branchée, ils se remplissent, sans rien changer au site.

## Deux lecteurs, deux profondeurs

- **Le grand public** : il arrive par un sujet ou une question. Il veut l'essentiel en un coup d'œil, des chiffres
  sûrs, des dates, sans jargon ni leçon de morale. Visuels simples.
- **Les initiés** (associations, journalistes, citoyens engagés) : même page, en dessous, un bouton « voir les
  données » qui déplie tout : listes complètes, sources, délais, téléchargement.

## Quel fichier pour quel écran

| Écran | Fichier(s) | Ce qu'on y trouve |
|---|---|---|
| Accueil : petits graphiques par thème | `vues/themes_par_an.json` | Pour chaque thème, par année : questions des députés, réponses des ministres, lois, textes d'application, autres textes. Repère du 16 février 2015 dans `reperes`. |
| Accueil : chiffres de comparaison | `themes.json` | Par thème et par législature : part des questions sur les animaux, réponses dans le délai, délai médian, **et le même calcul pour toutes les questions écrites** (`reference_toutes_questions`). Ne jamais afficher un taux sans son point de comparaison. |
| Le fil d'une loi, « de l'intention au résultat » | `vues/fils/index.json`, puis `vues/fils/<numéro>.json` | Pour chaque loi, cinq étapes : **Demandé** (questions des députés), **Voté**, **Promis** (mesures prévues), **Appliqué** (textes publiés), **Pas encore appliqué**. Chaque étape a un nombre et la liste de ses éléments, avec liens. |
| Carte des sujets (thèmes × étapes) | `vues/matrice.json` | Une ligne par thème, une colonne par type d'événement, avec le nombre d'événements. |
| Ce qui a bougé, au fil des jours | `evenements.json` | Tous les événements datés, du plus récent au plus ancien : questions écrites (`type: question_ecrite`) et textes du Journal officiel (`type: texte_officiel`). |
| Page d'une question écrite | `questions_ecrites.json` | Détail de chaque question : dates, statut, ministère, délai, et « pourquoi dans ce thème » (`declencheurs` : le mot trouvé et où). |
| Page d'un texte publié | `textes_officiels.json` | Détail de chaque texte : nature, dates, ministère, thèmes, loi appliquée, lien Légifrance. |
| Fiche sujet (« J'ai une question sur… ») | `fiches/index.json`, puis `fiches/<id>.json` | `georges` : l'essentiel (3 points clés, 3 chiffres, dernière avancée, prochaine échéance). `inities` : tout le reste. |
| Suivre un sujet | `flux/<thème>.xml` | Flux RSS par thème, à proposer en bouton « suivre ». |
| Pied de page | `index.json` | Date de mise à jour, sources et leurs dates, licence. |

## Règles à respecter sur toutes les pages

1. **Aucun jugement.** Pas d'adjectif, pas de classement d'élus. Le mot « retard » n'apparaît jamais : on écrit
   « échéance dépassée », « répondue après le délai ». Les données sont déjà écrites ainsi : les afficher telles quelles.
2. **Toujours la date.** Chaque page montre la date de mise à jour (`genere_le`, ou `mis_a_jour_le`), et chaque
   échéancier sa propre date (`echeancier_mis_a_jour`).
3. **Toujours la clé de lecture.** Chaque fichier contient `cles_de_lecture` : les afficher près des chiffres
   (en petit, ou dans un « comment lire ce chiffre »).
4. **« Non disponible » n'est pas zéro.** Quand `disponible` vaut `false`, ou qu'une valeur est vide, écrire
   « non disponible », jamais 0.
5. **Toujours la source.** Chaque élément a un `lien` vers le texte officiel : le rendre cliquable.
6. **Couleurs neutres.** Un fait publié et une échéance dépassée se distinguent par la forme (plein, vide, trait),
   pas par un rouge d'alerte.

## Sources et licence

Assemblée nationale (questions écrites), DILA : Journal officiel et dossiers législatifs de Légifrance.
Données réutilisables sous Licence Ouverte 2.0, en citant les sources. Méthode et code :
https://github.com/MyQoh/veille-animale
