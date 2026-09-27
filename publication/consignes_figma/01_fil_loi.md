# Consigne Figma Make n° 1 : le fil d'une loi, « de l'intention au résultat »

À coller dans Figma Make, avec la notice générale : https://myqoh.github.io/veille-animale/notice_figma.md

---

Crée une page web qui affiche le fil d'une loi, de l'intention au résultat, à partir de ce fichier JSON publié
en ligne (le lire à l'ouverture de la page, ne rien recopier en dur) :

https://myqoh.github.io/veille-animale/dernier/vues/fils/2021-1539.json

La liste de toutes les lois disponibles est ici (pour un sélecteur de loi, en option) :
https://myqoh.github.io/veille-animale/dernier/vues/fils/index.json

## Ce que la page raconte

Pour une loi : ce qui a été demandé, voté, promis, appliqué, et ce qui ne l'est pas encore. Des faits et des
dates, sans aucun jugement. Très peu de texte : le fil guide l'œil.

## Structure

1. **En-tête** : titre de la loi (`loi.titre`), date de promulgation (`loi.promulgation`), lien vers Légifrance
   (`loi.lien`).
2. **Le fil, en cinq étapes, de gauche à droite** (ou de haut en bas sur mobile), dans l'ordre de `etapes` :
   Demandé, Voté, Promis, Appliqué, Pas encore appliqué. Pour chaque étape : son libellé (`libelle`), un grand
   chiffre (`nombre`), une ligne d'explication (`detail`). Le fil s'amincit de l'intention au résultat.
   Si `disponible` vaut `false`, afficher « non disponible » à la place du chiffre, jamais 0.
3. **Les mesures promises en rangée de points** : un point par élément de `etapes.promis.elements`. Point plein
   si son `statut` est « Décret publié », point vide sinon.
   Au survol d'un point : l'objet de la mesure (`objet`), l'article, le décret et sa date, ou le statut.
4. **Une frise horizontale en trois couloirs, sur un vrai axe du temps** (de la promulgation à aujourd'hui) :
   - couloir **Parlement** : les questions des députés (`etapes.demande.elements`, par `date`) ;
   - couloir **Décrets et arrêtés** : `etapes.applique.decrets_de_l_echeancier` (par `decret_date`) et
     `etapes.applique.textes_journal_officiel` (par `date`) ;
   - couloir **Application** : les mesures en attente (`etapes.en_attente.elements`), avec leur date annoncée
     (`publication_annoncee`) quand elle existe.
   Un trait vertical pointillé marque aujourd'hui. Un clic sur un élément ouvre son détail et son lien officiel.
5. **« Voir les données »** (bouton qui déplie) : les listes complètes de chaque étape, avec dates, statuts et
   liens ; les textes qui citent seulement la loi (`etapes.applique.textes_qui_citent_la_loi`), présentés à part
   avec leur note ; les clés de lecture (`meta.cles_de_lecture`) ; la date de mise à jour (`meta.genere_le`) et
   celle de l'échéancier (`loi.echeancier_mis_a_jour`).

## Direction artistique

- **Ambiance « nuit, galaxie pastel »** : fond bleu nuit `#0f1122` (cartes `#161931`, `#1b1e36`), texte
  principal `#e9e7f7`, texte secondaire `#a6a8c4`, filets `rgba(255,255,255,.12)`.
- **Couleurs des couloirs, en pastel** : Parlement lavande `#c3b6f2`, Décrets et arrêtés bleu `#9fcbef`,
  Application menthe `#9ee3c6` ; accents jaune `#eadb9a` et pêche `#f3c3a0` si besoin. Fonds de couloir en
  transparence légère (environ 20 %).
- **Un seul ton vif, corail `#ff7a66`** : il marque seulement une date dépassée, un fait. Jamais de rouge
  d'alerte, jamais de vif ailleurs.
- **Typographie** : titres en Newsreader, texte en IBM Plex Sans, dates et chiffres en JetBrains Mono.
- **Légende, toujours visible** : ● publié · ○ attendu · | échéance fixée par le texte · ━ temps écoulé après
  l'échéance, sans texte publié.
- Lueur (glow) discrète sur les points publiés, pas plus. Beaucoup d'air, peu de texte.

## Règles à respecter

- Aucun adjectif qui juge, aucun classement. Le mot « retard » n'apparaît jamais : afficher les libellés tels
  qu'ils sont dans le fichier.
- Toujours afficher la date de mise à jour et, près des chiffres, un lien « comment lire ces chiffres » vers les
  clés de lecture.
- « Non disponible » n'est jamais 0.
- Chaque élément est cliquable vers sa source officielle (`lien`).
- Pied de page : « Sources : Assemblée nationale, Journal officiel, dossiers législatifs (DILA). Données sous
  Licence Ouverte 2.0. » avec un lien vers https://myqoh.github.io/veille-animale/
