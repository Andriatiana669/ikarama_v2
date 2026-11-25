# Guide de l'administrateur

Ce guide s'adresse aux **superadmins**. Il complète les guides de l'employé et du responsable.

## L'accueil

L'accueil ajoute le nombre de problèmes des **Contrôles de cohérence** et l'**activité récente** des feuilles.

## Suivre les pointages de tout le monde

- **Pointages > Suivi** : les pointages de toutes les personnes ayant accès au site, avec des filtres (période, employé, pôle, tâche). Vous pouvez modifier ou supprimer une ligne : les règles de la personne pointée s'appliquent (ses affaires, ses horaires), et elle est prévenue par une notification.
- **Pointages > Vérification** : une ligne par personne et par jour pointé, avec les **heures pointées** (H_Durée) et le **manque** par rapport à 8 h. Le filtre « Seulement les manques » isole les jours incomplets.
- **Import pour d'autres** : dans Mon temps, la colonne **Matricule** du modèle d'import permet de pointer à la place d'une personne.

## Paramètres

| Page | Rôle |
|---|---|
| **Accès au site** | Qui peut entrer : règles Autoriser / Refuser par pôle, poste, matricule ou responsable N+1. Un refus l'emporte toujours |
| **Rendement & Note** | Heures par jour, note objectif, note maximale, tranches de la note de qualité |
| **Graphiques** | Sources autorisées du Rendement (Feuilles, Pointages), Synchronisation des données (mêmes affaires et prestations dans les onglets, pour tout le monde), camembert du temps, courbes d'Evolution, barres de Réel vs Objectif, seuils de l'Analyse |
| **Temps Estimatif** | Unité par défaut, marge avant le rouge, couleurs des lignes |
| **Configurations Responsables** | Des groupes de personnes nommés, ajoutés d'un coup dans le champ Responsables d'une affaire ; la configuration « par défaut » préremplit les Responsables d'une nouvelle affaire |
| **Contrôles de cohérence** | Les données incomplètes ou incohérentes, avec un lien pour corriger chacune (aussi visible par un rôle : module « Paramètres > Contrôles de cohérence ») |
| **Autorisation** | Le moindre privilège : droits de base, rôles qui autorisent ou refusent une action, « Tester un accès », journal |

### Autorisation

**Les trois couches** : l'**Accès au site** décide qui entre ; les **droits de base** décident ce que chacun peut faire
sans rôle ; les **rôles** ajoutent ou retirent des droits. Le superadmin a tous les droits.

**Pages du menu** : tout le monde voit les pages, sauf

- **Paramètres**, **Utilisateurs**, **Équipes** : superadmin seulement ;
- **Marchés > Ajouter un marché** et **Marchés > Archives** : **seulement par un rôle**. Dans Ajouter un marché, chaque
  panneau a son module : **Affaires**, **Prestations**, **Projets / Communes**, **Descriptions**, **Tâches**, **Statuts**
  (Tâches et Statuts : réservés au superadmin, même pour voir, sauf rôle) ;
- **Marchés > Mes marchés** reste en consultation pour les responsables et membres de leurs affaires (le responsable y gère les membres) ;
- **Pointages > Suivi**, **Pointages > Vérification** : **seulement par un rôle** (un responsable n'y a pas accès sans rôle) ;
- **Créer une nouvelle feuille** : droit « Créer » de Google Sheet > Mes feuilles, **seulement par un rôle**.

**Google Sheet > Mes feuilles** : chacun voit les feuilles de ses affaires (responsable ou membre). Voir d'autres affaires,
créer, modifier, supprimer une feuille, importer des feuilles, exporter la liste : seulement par un rôle.
Ces droits portent sur **la feuille**, pas sur **ses données** : les membres et responsables saisissent toujours dans les
lignes, et le créateur ou un responsable importe les données de la feuille.

**Planning Projet** : chacun voit et exporte son propre planning ; voir l'équipe et planifier (Créer, Modifier, Supprimer)
passent par un rôle (module « Planning Projet »). Le statut qui signifie « en train de faire » se coche dans
Marchés > Statuts (rôle « En train de faire »).

**Affichage Everwin** : chacun voit et exporte son propre affichage ; celui des autres seulement par un rôle (module
« Affichage Everwin », périmètre de personnes). Le choix de la personne n'apparaît qu'avec ce droit.

**Accueil > Mon équipe** affiche les pointages incomplets de la **semaine en cours** (du lundi au dimanche, jours
ouvrables jusqu'à aujourd'hui) pour les personnes du périmètre « Voir » de **Pointages > Vérification**.

**Un rôle**, c'est une grille : pour chaque module et chaque action (Voir, Créer, Modifier, Supprimer, Importer,
Exporter, Archiver, Désarchiver), une liste **Autoriser sur…** et une liste **Refuser sur…**, avec **autant de
périmètres que nécessaire** :

| Le module porte sur | Périmètres |
|---|---|
| des personnes (Suivi, Vérification) | Tout le monde, un pôle (le sien par défaut), un poste, une personne, ma hiérarchie, mes N-1, **équipe de… (une personne et toute sa hiérarchie)**, les membres de mes affaires, moi |
| des affaires (feuilles, affaires, projets, descriptions, archives) | Toutes les affaires, mes affaires (responsable), mes affaires (responsable ou membre), une affaire précise, **affaires de l'équipe de…** (un responsable ou un membre en fait partie) |
| un catalogue (prestations, tâches, statuts) | Tout |

Les postes et pôles se choisissent dans une liste avec recherche (ceux connus par l'API RH), comme les personnes.

- **Un refus l'emporte toujours**, sur la base comme sur les autres rôles. Refuser sur « Tout » retire complètement le droit.
- Un rôle s'attribue à **une personne**, à **un poste** ou à **un pôle** (automatique, selon l'API RH).
- **Tester un accès** répond « Oui / Non » pour une personne, un module, une action (et une cible), avec les raisons.
- Le **Journal** garde qui a changé quels rôles, droits et attributions.

Les règles métier restent vraies même avec un rôle : par exemple, une case pointée reste verrouillée et une description qui a des données ne se supprime pas.

### Contrôles de cohérence

Le contrôle « Réglages manquants » signale aussi une vérification des certificats HTTPS désactivée (`CA_BUNDLE=desactive`
dans le fichier .env du serveur). Les affaires cochées « Pointage seulement » ne sont pas signalées comme « pointées hors feuille ». Chaque contrôle indique son nombre de problèmes, sa gravité (À corriger, À vérifier, Information) et la liste des éléments avec un lien **Corriger** : descriptions pointées hors feuille, lignes avec du temps sans Employé ou sans Date de début, personnes hors de l'équipe de l'affaire, projets sans description, descriptions sans quantité, prestations sans rendement objectif, affaires sans responsable, jours pointés sans pause, réglages manquants.

Relancez les contrôles après vos corrections.

## Notifications et e-mails

Les rappels de pointage et l'e-mail récapitulatif partent par des **tâches planifiées** sur le serveur (voir le guide de déploiement). Chaque commande accepte `--simulation` pour vérifier ce qu'elle ferait.

## En cas de blocage

Si plus personne ne peut entrer (règle d'accès trop stricte) :

- `/admin/` avec un compte créé par `createsuperuser`, puis **Règles d'accès au site** ;
- ou, sur le serveur : `python manage.py acces_site --verifier MATRICULE`, `--autoriser MATRICULE` ou `--tout-desactiver`.
