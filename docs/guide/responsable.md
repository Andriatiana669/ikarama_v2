# Guide du responsable

Ce guide s'adresse aux **responsables d'affaire** et aux **responsables N+1**. Il complète le guide de l'employé.

## L'accueil

En plus de vos propres blocs, l'accueil affiche :

- **Mon équipe : pointages incomplets** (si un rôle vous donne la Vérification) : combien de personnes de votre périmètre n'ont pas tout pointé cette semaine, et pour chacune ses heures manquantes (les 8 plus gros manques, « Voir les … » pour tous) ;
- **Mes affaires** : les lignes qui approchent ou dépassent leur Temps Estimatif, et l'avancement de vos feuilles.

## Le Marché (Marchés)

### Ajouter un marché

La page **Marchés > Ajouter un marché** se lit de gauche à droite :

1. **Affaires** : choisissez ou créez l'affaire (Num affaire, nom, responsables, membres). Dans Responsables et Membres,
   **« Ajouter l'équipe de… »** ajoute d'un coup tous les subordonnés d'une personne (sous-équipes comprises), sans elle.
   Dans Responsables, **« Ajouter une configuration… »** ajoute un groupe préparé dans Paramètres > Configurations
   Responsables, et la configuration par défaut est déjà remplie pour une nouvelle affaire.
   Cochez **« Pointage seulement (pas de feuille) »** pour une affaire suivie au pointage sans feuille : les Contrôles de
   cohérence ne la signalent plus (on peut quand même lui créer une feuille).
2. **Prestations** : cochez les prestations de l'affaire.
3. **Projets / Communes** : créez les projets de la prestation choisie (rendement objectif, date de livraison).
4. **Descriptions** : créez les descriptions du projet avec leur quantité. La quantité du projet est la somme de ses descriptions.

Les colonnes **Temps** et **Statut** sont calculées en direct depuis les feuilles. Le menu **Temps de la tâche** ajoute une colonne avec le temps d'une tâche précise.

Les catalogues se gèrent en bas de page :

- **Tâches** : leur type (Production, Contrôle, Reprise, Autre) décide de la colonne de la feuille qui reçoit le temps ; « Plusieurs descriptions » et « Ajouter au temps du projet » se règlent ici.
- **Statuts** : couleur et rôles (par défaut, prioritaire au pointage, active la note de rendement, avancement 100 %, en train de faire).

### Durée estimatif

**Marchés > Durée estimatif** (module « Marchés > Durée estimatif » de Paramètres > Autorisation : Voir, Exporter) donne, pour chaque Projet / Commune,
le temps nécessaire pour le traiter :

- **temps estimatif** = quantité de ses descriptions ÷ rendement objectif par jour × heures par jour
  (Paramètres > Rendement & Note) ;
- **ressources disponibles** : le nombre de personnes qui le traiteront (− / +, ou « Ressources pour tous ») ;
  c'est une simulation, rien n'est enregistré ;
- **durée totale** et **durée restante** (d'après l'Avancement des lignes de feuille) = temps ÷ ressources,
  en **jours** ou en **heures** ; « soit … pour 1 personne » rappelle le temps d'une seule personne.

Filtres : **Statut** (seules les descriptions dont la ligne a ce statut), **Descriptions**, **Affaires**,
**Prestations**, **Choix des Rendements Objectifs** (seulement les projets qui les ont). L'export Excel reprend les
ressources saisies.

### Mes marchés et Archives

**Mes marchés** liste les affaires dont vous êtes responsable ou membre ; un responsable y gère les membres. **Archives** permet de désarchiver ou de supprimer définitivement une affaire vide.

## Les feuilles

### Créer une feuille

(Il faut le droit « Créer » de Google Sheet > Mes feuilles, donné par un rôle.)
**Google Sheet > Créer une nouvelle feuille** se fait en trois étapes, avec un **récapitulatif** à droite
(nombre d'affaires, de prestations, de **lignes créées** et de critères) :

1. **le nom** de la feuille ;
2. **les affaires et prestations** : chaque prestation indique son nombre de projets et de lignes ; une prestation déjà
   dans une autre feuille est verrouillée (« déjà dans … ») ; « Tout cocher » prend toutes les prestations libres ;
3. **les critères de contrôle** (interrupteur « Utiliser les critères ») : choisissez leur nombre avec − / +, puis
   décrivez chacun (notes de 1 à 5).

La feuille se tient à jour toute seule : une ligne par description, ajoutée ou retirée avec le Marché.

### Importer

- **Importer des feuilles** (Mes feuilles) : créer ou mettre à jour des feuilles depuis Excel.
- **Importer les données** (dans une feuille) : le modèle est prérempli avec les lignes actuelles ; modifiez puis réimportez.
- **Import ancienne donnée** (dans une feuille) : pour vos anciens fichiers, avec leurs propres colonnes. Les projets / communes et descriptions manquants sont créés ; l'affaire et la prestation doivent exister.

### Notes

- **Note de rendement** : selon le rendement total par rapport au rendement objectif. Elle n'apparaît que lorsque toutes les descriptions du projet ont le statut qui l'active.
- **Note de qualité** : moyenne des critères, ou selon le temps de reprise par rapport au temps de prod.

## Le Planning Projet

**Planning Projet** se met à jour **en direct** (pastille « En direct ») : une planification, un pointage ou un
changement de statut apparaît aussitôt chez tous ceux qui ont la page ouverte. Il montre une ligne par personne de votre périmètre (photo et identifiant) (module « Planning Projet » de Paramètres >
Autorisation ; sans rôle, vous ne voyez que vous-même). Les semaines **défilent de gauche à droite** (la colonne
Employé et les en-têtes restent figés) ; les semaines précédentes et suivantes se chargent en arrivant au bord,
et **Aujourd'hui** ramène au jour courant.

- **passé et aujourd'hui** : les projets / communes **pointés**, avec les heures ;
- **aujourd'hui et à venir** : les projets **planifiés** (cadre en pointillés) ;
- sous l'identifiant : ce que la personne **est en train de faire** (lignes de feuille au statut qui a le rôle
  « En train de faire » dans Marchés > Statuts).

**Échéances** : une rangée « Échéances » sous les jours montre un drapeau le jour de livraison de chaque projet
(rouge : en retard, orange : livraison dans 7 jours ou moins, vert : terminé). Dans la liste des Projets / Communes,
chaque projet indique sa livraison (« En retard de 2 jour(s) », « Livraison dans 3 jour(s) ») et son avancement.

**Filtres** : une personne, **Équipe de** (afficher seulement une équipe, sous-équipes comprises),
**Masquer l'équipe de**, pôle, poste, affaires, contenu (pointé, planifié, en train de faire), seulement les
personnes disponibles, masquer les lignes vides.

**Planifier** (droit « Créer ») : le panneau de droite reste visible quand on descend. **Glissez** un projet sur une
case, ou **cliquez** le projet puis la case. Un projet planifié se déplace en le glissant (« Modifier ») et se retire
avec la croix (« Supprimer »). La personne planifiée est prévenue. La liste « Employés et leurs disponibilités »
montre les jours ouvrables des 14 prochains jours sans rien de pointé ni de planifié.

## Le Rendement

Les sous-onglets partagent les mêmes filtres (affaires, prestations, tâches, employés, statut, période sur la Date de début).
**Aucune affaire cochée = toutes** les affaires que vous pouvez voir : cocher seulement une prestation suffit pour un graphique.
Sous **Rentabilités**, les listes à cocher **Commentaires** et **Commentaires contrôle** proposent chaque commentaire
tel qu'écrit dans les feuilles, plus « Sans commentaire » : seules les lignes cochées comptent (aucune cochée : toutes). Si l'administrateur a activé la **Synchronisation des données** (Paramètres > Graphiques), les mêmes affaires et
prestations restent cochées d'un onglet à l'autre.

| Onglet | Ce qu'il montre |
|---|---|
| **Globale** | Rendement moyen par employé, quantités par employé, temps par tâche, rentabilités |
| **Evolution** | Deux courbes de rendement par date pointée (groupes de tâches), avec l'écart en % et sa tolérance |
| **Analyse** | Par employé et par mois : part du temps et rentabilité par affaire / prestation, zones (À garder, À revoir, Potentiel, Ponctuel) et signaux (Aide, En adaptation, Baisse soudaine) |
| **Réel vs Objectif** | Par employé, le réel face à son rendement objectif, et deux jauges |
| **Evaluation Employé** | Rendement moyen des employés mois par mois |

- La **rentabilité** vaut rendement ÷ objectif : 1,00 = objectif atteint, 2,00 = le double.
- Le tableau **Rendement objectif** se modifie pour un **aperçu** : rien n'est enregistré.
- Le choix **Source** (si l'administrateur l'a autorisé) : **Pointages + Feuilles** (normal), **Feuilles** (anciennes
  données sans pointage) ou **Pointages** (toutes les descriptions pointées, même sans feuille : la quantité revient à la
  personne qui a pointé le plus de Production, et seul son temps compte ; la période porte sur le premier jour pointé).
  Avec cette source, les histogrammes de Globale, Réel vs Objectif et Evaluation Employé montrent les **heures
  pointées** (H_Durée + HS) au lieu du rendement.

Les signaux de l'Analyse aident à poser une question ; ils ne remplacent pas un échange avec la personne.
