# Guide de l'employé

Ce guide explique comment pointer son temps et suivre son travail dans Ikarama.

## Se connecter

Ouvrez l'adresse d'Ikarama : la connexion passe par votre compte habituel (Keycloak). Vous arrivez sur l'**Accueil**.

Si la page « Accès non autorisé » s'affiche, votre accès n'a pas encore été ouvert : adressez-vous à votre responsable ou à l'administrateur.

## L'accueil

L'accueil résume votre situation :

- **le bandeau** : votre photo, la date, le numéro de semaine, le bouton **Pointer** et des raccourcis (Mon temps, Mes feuilles, Planning…) ;
- **les chiffres clés** : heures d'aujourd'hui (sur 8 h) et de la semaine, avec une jauge, le nombre d'erreurs de pointage et de lignes à surveiller ;
- **Ma semaine** : une barre par jour (verte dès 8 h, avec le repère des 8 h) et vos erreurs de pointage ;
- **Mon planning** : ce qui est planifié pour vous les 7 prochains jours ;
- **Mes lignes à surveiller** : les lignes de feuille dont vous êtes l'Employé et qui approchent (orange) ou dépassent (rouge) leur Temps Estimatif.

## Pointer son temps (Pointages > Mon temps)

### Ajouter un pointage

1. Cliquez sur **Ajouter**.
2. La date et les heures sont proposées automatiquement : le premier créneau libre de la journée (07:30–16:30). Vous pouvez les changer, ou cliquer sur un créneau libre affiché sous les heures.
3. Cochez **Pause (−1 h)** sur un seul pointage par jour ouvrable (voir plus bas).
4. Choisissez l'**Affaire** : celles où vous êtes déjà placé dans une feuille apparaissent en premier.
5. La **Prestation** et le **Projet / Commune** se remplissent seuls s'il n'y a qu'un choix.
6. Choisissez la **Tâche**, puis la ou les **Descriptions**. Certaines tâches permettent de cocher plusieurs descriptions : le temps est alors partagé au prorata des quantités.
7. Ajoutez un **commentaire** si besoin, puis **Enregistrer**.

Sous les heures, l'aperçu affiche la **H_Durée** et les **HS** exactes du pointage.

### H_Durée, HS et pause

| Terme | Signification |
|---|---|
| **H_Durée** | Temps entre 07h30 et 16h30, du lundi au vendredi, moins 1 h si la pause est cochée |
| **HS** | Temps avant 07h30 ou après 16h30, et tout le temps du samedi et du dimanche |
| **Pause (−1 h)** | À cocher sur **un** pointage par jour ouvrable ; sinon le jour est en erreur « pause non cochée » |

Exemple, pause cochée : 08:00 → 16:30 donne 7,5 h ; 07:30 → 16:30 donne 8 h.

### Les erreurs de pointage

En bas de Mon temps, la carte **Erreurs de pointage** liste :

- les jours ouvrables avec **moins de 8 h** pointées ;
- les jours ouvrables pointés **sans pause**.

Chaque jour affiche aussi ses créneaux **non pointés** (par exemple « Non pointé : 12:00–13:00 ») : c'est une simple information.

### Le lien avec les feuilles

Quand vous pointez une description présente dans une feuille :

- vous êtes placé automatiquement dans la colonne de la tâche (**Employé** pour la production, **Contrôleur** pour le contrôle, **Employé reprise** pour la reprise), si elle était vide ;
- le temps est ajouté dans la colonne correspondante (Temps de prod, de contrôle, de reprise) ;
- votre commentaire est ajouté dans la colonne de commentaires de la tâche ;
- la case de la personne est **verrouillée** : elle ne peut plus être changée tant que du temps y est pointé.

Si quelqu'un d'autre occupe déjà la colonne de la tâche, le pointage est refusé et le formulaire l'indique.

Supprimer un pointage retire son temps et son commentaire de la feuille, et vous retire de la colonne si vous n'avez plus d'autre pointage de ce type sur la ligne.

### Importer des pointages

Le bouton **Importer** de Mon temps accepte un fichier Excel. Téléchargez d'abord le **modèle** : il contient les bonnes colonnes, un onglet « Aide », la liste de vos descriptions (avec leur **ID**) et des tâches. L'import montre un **aperçu** ligne par ligne avant d'enregistrer.

## Les feuilles (Google Sheet)

**Google Sheet > Mes feuilles** liste les feuilles de vos affaires, avec leurs statuts et leur nombre de lignes. L'icône **œil** affiche les responsables et membres de chaque affaire.

Dans une feuille :

- vous pouvez modifier les colonnes autorisées (Employé, Contrôleur, **Statut de contrôle**, Employé reprise, Statut, Avancement, Commentaires…) ; chaque modification est enregistrée aussitôt ;
- les modifications des autres apparaissent **en direct**, et une case en cours de modification par quelqu'un d'autre est encadrée avec son nom ;
- la colonne **Temps Estimatif** indique le temps prévu pour la quantité ; la ligne devient **orange** quand le Temps de prod en approche, **rouge** quand il l'atteint ou le dépasse ;
- le bouton **Historique** retrace qui a modifié quoi et quand ;
- l'en-tête du tableau reste visible quand on descend.

## Affichage Everwin

La grille de votre semaine, une ligne par affaire et par tâche (celle d'autres personnes seulement si un rôle vous le permet). Naviguez avec **Semaine précédente / suivante**. L'icône message d'une case affiche le détail des pointages. Un total de jour ouvrable est **rouge** quand sa H_Durée n'atteint pas 8 h.

## Planning Projet

Votre propre planning : ce que vous avez pointé, et ce qui est planifié pour vous. La page se met à jour **en direct**
(pastille « En direct ») : une planification apparaît aussitôt, sans actualiser.

## Les notifications

La **cloche** en haut de l'écran affiche le nombre de notifications non lues : rappels de pointage incomplet, ligne qui dépasse son Temps Estimatif, pointage modifié par un administrateur, ajout à une affaire… Cliquez sur une notification pour ouvrir la page concernée.

Chaque soir, un **e-mail récapitulatif** reprend vos notifications non lues (s'il y en a).

## Votre profil

**Profil** affiche vos informations, votre équipe et **Mon résumé** : les affaires et prestations où vous êtes Employé, avec la moyenne de vos **Notes de rendement** et **Notes de qualité**.
