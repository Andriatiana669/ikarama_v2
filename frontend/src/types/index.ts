// src/types/index.ts
// Types partagés par toute l'application (miroir des serializers Django).

/** Réponse paginée de l'API (ikarama/pagination.py) */
export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type Identifiant = number

export interface EmployeResume {
  id: Identifiant
  code_barre: string | null
  nom: string
  prenom: string
  prenom_usuel: string | null
  nom_affiche: string
  /** « PR00123_Jean » : matricule + prénom usuel */
  identifiant: string
}

export interface EmployePoste {
  id: Identifiant
  pole_id: number | null
  pole: string | null
  poste_nom: string | null
  poste_statut: string | null
}

export interface Employe extends EmployeResume {
  external_id: number | null
  civilite: string | null
  email: string | null
  chef: EmployeResume | null
  postes: EmployePoste[]
  nb_subordonnes?: number
  a_un_compte: boolean
  /** CONNECTE | AUTORISE (jamais connecté) | RETIRE (accès retiré) */
  statut_acces: 'CONNECTE' | 'AUTORISE' | 'RETIRE' | 'REFUSE'
  derniere_synchro: string | null
}

export interface UtilisateurConnecte {
  id: Identifiant
  username: string
  email: string
  prenom: string
  nom: string
  est_administrateur: boolean
  /** Faux : la personne ne respecte pas les règles d'accès au site */
  acces_site: boolean
  employe: Employe | null
  /** Paramètres > Autorisation : {module: [actions permises]} (seulement les modules gérés par les rôles) */
  autorisations: Record<string, string[]>
  /** Responsable d'au moins une affaire en cours */
  est_responsable?: boolean
}

/**
 * Équipe = un responsable (N+1) et ses collaborateurs directs, calculée depuis l'API RH.
 * L'id de l'équipe est l'id de son responsable.
 */
export interface Equipe {
  id: Identifiant
  responsable: EmployeResume
  pole: string | null
  poste: string | null
  nb_membres: number
  /** Seulement dans « mes équipes » */
  mon_role?: 'RESPONSABLE' | 'MEMBRE'
}

export interface EquipeDetail extends Equipe {
  membres: Employe[]
}

export interface PoleRH {
  pole: string
  nb_employes: number
  nb_equipes: number
}

/** Nœud de l'organigramme : un employé et ses collaborateurs directs */
export interface NoeudHierarchie extends EmployeResume {
  poste: string | null
  pole: string | null
  nb_membres: number
  enfants: NoeudHierarchie[]
}

export type EffetRegle = 'AUTORISER' | 'REFUSER'
export type CritereRegle = 'POLE' | 'POSTE' | 'MATRICULE' | 'N1'

export interface RegleAcces {
  id: Identifiant
  effet: EffetRegle
  effet_libelle: string
  critere: CritereRegle
  critere_libelle: string
  pole: string
  poste: string
  employe: Identifiant | null
  employe_details: EmployeResume | null
  portee: 'DIRECT' | 'HIERARCHIE' | ''
  portee_libelle: string
  actif: boolean
  commentaire: string
  description: string
  nb_personnes: number
}

export interface ExplicationAcces {
  acces: boolean
  mode_ouvert: boolean
  regles: { id: Identifiant; effet: EffetRegle; description: string }[]
}

export interface ApercuAcces {
  mode_ouvert: boolean
  nb_autorises: number
  nb_employes: number
  nb_regles_actives: number
  moi: ExplicationAcces | null
}

// ------------------------------------------------------------------
// Marché
// ------------------------------------------------------------------
/** Statut calculé d'un niveau du Marché (description, projet, prestation, affaire) */
export interface StatutSuivi {
  id: Identifiant
  nom: string
  couleur: string
  /** Tout le niveau a le statut qui active la note de rendement */
  final: boolean
  /** En cours : nombre de descriptions au statut final sur le total */
  progression?: { au_statut: number; total: number }
}

export interface Rendement {
  id: Identifiant
  valeur: string
}

export interface Prestation {
  id: Identifiant
  nom: string
  unite: string
  rendements: Rendement[]
  /** Heures cumulées dans l'affaire choisie (?affaire=) */
  temps: string | null
  /** Temps de la tâche choisie dans la page (?tache=) */
  temps_tache?: string | null
  statut: StatutSuivi | null
  /** Seulement quand une affaire est choisie */
  cochee?: boolean
  nb_projets?: number
  cree_par_details: EmployeResume | null
  cree_le: string
}

export interface Affaire {
  id: Identifiant
  num_affaire: string
  nom: string
  /** Heures cumulées (prod + contrôle + reprise) */
  temps: string | null
  /** Temps de la tâche choisie dans la page (?tache=) */
  temps_tache?: string | null
  statut: StatutSuivi | null
  responsables: Identifiant[]
  responsables_details: EmployeResume[]
  membres: Identifiant[]
  membres_details: EmployeResume[]
  nb_prestations: number
  /** Rôle de la personne connectée dans l'affaire */
  mon_role: 'RESPONSABLE' | 'MEMBRE' | null
  actif: boolean
  cree_par_details: EmployeResume | null
  cree_le: string
  modifie_le: string
  /** Suivie au pointage sans feuille (non signalée dans les Contrôles de cohérence) */
  pointage_seul?: boolean
  /** Report DT : Quantité = Quantité linéaire × Surface ÷ Linéaire total */
  report_dt?: boolean
}

export interface Projet {
  id: Identifiant
  numero: number
  affaire: Identifiant
  prestation: Identifiant
  prestation_nom: string
  nom: string
  quantite: string | null
  unite: string
  rendement: Identifiant
  rendement_valeur: string
  date_livraison: string
  temps: string | null
  /** Temps de la tâche choisie dans la page (?tache=) */
  temps_tache?: string | null
  statut: StatutSuivi | null
  nb_descriptions: number
  cree_par_details: EmployeResume | null
  cree_le: string
  /** Report DT : surface (m²) saisie et linéaire total (ML) calculé */
  surface_m2?: string | null
  lineaire_total?: string | null
}

/** Élément d'un catalogue commun (Tâches, Statuts) */
export interface ElementCatalogue {
  id: Identifiant
  nom: string
  /** Statuts : couleur de fond (#RRGGBB) */
  couleur?: string
  /** Statuts : donné aux nouvelles lignes des feuilles */
  par_defaut?: boolean
  /** Statuts : ses affaires sont proposées en premier au pointage */
  prioritaire_pointage?: boolean
  /** Statuts : la Note de rendement apparaît quand tout le projet a ce statut */
  active_note_rendement?: boolean
  /** Statuts : donné automatiquement quand l'avancement atteint 100 % */
  avancement_complet?: boolean
  /** Planning Projet : les lignes à ce statut disent ce que fait la personne */
  en_train_de_faire?: boolean
  /** Contrôles de cohérence : description à ce statut non signalée « sans quantité » (plusieurs statuts) */
  ignorer_sans_quantite?: boolean
  /** Tâches : relie le temps pointé à une colonne des feuilles */
  type?: TypeTache
  type_libelle?: string
  /** Tâches : le pointage peut viser plusieurs descriptions d'un même projet */
  plusieurs_descriptions?: boolean
  /** Tâches : son temps s'ajoute au Temps du Projet / Commune */
  temps_projet?: boolean
  cree_par_details: EmployeResume | null
  cree_le: string
}

/** Description d'un Projet / Commune */
export interface DescriptionProjet {
  id: Identifiant
  numero: number
  projet: Identifiant
  nom: string
  quantite: string | null
  unite: string
  temps: string | null
  /** Temps de la tâche choisie dans la page (?tache=) */
  temps_tache?: string | null
  statut: StatutSuivi | null
  cree_par_details: EmployeResume | null
  cree_le: string
  /** Report DT : quantité linéaire (ML) ; la Quantité en est calculée */
  quantite_lineaire?: string | null
}

// ------------------------------------------------------------------
// Feuilles (Google Sheet)
// ------------------------------------------------------------------
export interface PerimetreFeuille {
  affaire: Identifiant
  num_affaire: string
  nom_affaire: string
  prestation: Identifiant
  nom_prestation: string
}

export interface CritereControle {
  id: Identifiant
  numero: number
  commentaire: string
}

export interface Feuille {
  id: Identifiant
  nom: string
  /** Avec critères : Note de qualité = moyenne des critères ; sans : d'après le temps de reprise */
  utiliser_criteres: boolean
  perimetres: PerimetreFeuille[]
  criteres: CritereControle[]
  nb_lignes: number
  avancement_moyen: number | null
  peut_gerer: boolean
  /** Droits sur cette feuille (Paramètres > Autorisation) */
  droits?: { modifier: boolean; supprimer: boolean; importer_donnees: boolean }
  mon_role: 'RESPONSABLE' | 'MEMBRE' | null
  cree_par_details: EmployeResume | null
  cree_le: string
  modifie_le: string
  /** Statuts de ses lignes avec leur nombre */
  statuts?: { id: Identifiant | null; nom: string; couleur: string; nombre: number }[]
}

export interface AffaireDisponible {
  id: Identifiant
  num_affaire: string
  nom: string
  prestations: {
    id: Identifiant
    nom: string
    unite?: string
    nb_projets?: number
    /** Nombre de descriptions : autant de lignes dans la feuille */
    nb_descriptions?: number
    /** Nom de la feuille qui contient déjà cette prestation de l'affaire */
    deja_dans?: string | null
  }[]
}

/** Informations reprises du Marché pour une ligne */
export interface MarcheLigne {
  affaire_id: Identifiant
  num_affaire: string
  nom_affaire: string
  prestation: string
  unite: string
  projet: string
  description: string
  quantite: string | null
  rendement_objectif: string
  date_livraison: string
}

export interface StatutResume {
  id: Identifiant
  nom: string
  couleur: string
}

export interface LigneFeuille {
  id: Identifiant
  numero: number
  feuille: Identifiant
  marche: MarcheLigne
  retiree: boolean
  employe: Identifiant | null
  employe_details: EmployeResume | null
  controleur: Identifiant | null
  controleur_details: EmployeResume | null
  employe_reprise: Identifiant | null
  employe_reprise_details: EmployeResume | null
  statut: Identifiant | null
  statut_details: StatutResume | null
  statut_controle?: Identifiant | null
  /** Statut de contrôle : même liste de statuts, valeur à part */
  statut_controle_details?: StatutResume | null
  avancement: number
  commentaires: string
  commentaires_controle: string
  commentaires_reprise: string
  nb_reprises: number
  /** { id du critère : note } */
  notes: Record<string, string | null>
  /** Employé, Statut, Avancement, Commentaires, Contrôleur, Employé reprise (responsables et membres) */
  peut_modifier: boolean
  /** Nombre de reprises et critères (responsables) */
  peut_saisir_controle: boolean
  /** Temps Estimatif en heures (Quantité ÷ Rendement objectif × heures par jour) */
  temps_estimatif: string | null
  /** Couleur de la ligne : Temps de prod ≥ estimatif (rouge) ou proche (orange) ; null au statut final */
  alerte_temps: 'rouge' | 'orange' | null
  /** Colonnes de personnes verrouillées car du temps y a été pointé : 'employe' | 'controleur' | 'employe_reprise' */
  colonnes_verrouillees: string[]
  /** Rempli par le Pointage (heures) */
  temps_prod: string | null
  temps_controle: string | null
  temps_reprise: string | null
  date_debut: string | null
  /** Dernière modification */
  modifie_par_details: EmployeResume | null
  modifie_le: string
  /** Calculés (Paramètres > Rendement & Note) */
  rendement_prod: string | null
  rendement_total: string | null
  note_rendement: string | null
  note_qualite: string | null
}

/** Quelqu'un est en train de modifier une case */
export interface PresenceFeuille {
  ligne: Identifiant
  champ: string
  employe: Pick<EmployeResume, 'id' | 'nom_affiche' | 'identifiant' | 'code_barre'>
}

export interface SuiviFeuille {
  maintenant: string
  lignes: LigneFeuille[]
  recharger: boolean
  nb_lignes: number
  presences: PresenceFeuille[]
}

export interface ModificationLigne {
  id: Identifiant
  ligne: Identifiant
  numero_ligne: number
  description: string
  champ: string
  libelle: string
  ancienne_valeur: string
  nouvelle_valeur: string
  auteur_details: EmployeResume | null
  date: string
}

export interface TrancheReprise {
  /** Limite haute en % (exclue) ; null pour la dernière tranche (« et plus ») */
  jusqua: string | number | null
  note: string | number
}

export interface ParametresRendement {
  heures_par_jour: string
  note_objectif: string
  note_max: string
  note_critere_min: string
  note_critere_max: string
  tranches_reprise: TrancheReprise[]
  modifie_le: string
}

/** Résultat d'un import Excel (aperçu ou import réel) */
export interface RapportImport {
  simulation: boolean
  total: number
  crees: number
  modifies: number
  /** Lignes identiques à ce qui existe déjà */
  inchanges: number
  erreurs: number
  lignes: { numero: number; action: 'creation' | 'modification' | 'inchange' | 'erreur'; libelle: string; messages: string[] }[]
}

// ------------------------------------------------------------------
// Pointage
// ------------------------------------------------------------------
export type TypeTache = 'PRODUCTION' | 'CONTROLE' | 'REPRISE' | 'AUTRE'

export interface TacheResume {
  id: Identifiant
  nom: string
  type: TypeTache
  type_libelle: string
  plusieurs_descriptions: boolean
}

/** Colonnes reprises du Marché pour un pointage (+ la feuille, s'il y en a une) */
export interface InfosLigne {
  affaire_id: Identifiant
  prestation_id: Identifiant
  projet_id: Identifiant
  /** Une ou plusieurs descriptions (même projet) */
  description_ids: Identifiant[]
  num_affaire: string
  nom_affaire: string
  prestation: string
  projet: string
  description: string
  quantite: string | null
  unite: string
  /** Feuille(s) qui reçoivent le temps ; vide si aucune description n'est dans une feuille */
  feuille: string | null
}

/** Une description pointée et sa part du temps */
export interface PartPointage {
  description_id: Identifiant
  description: string
  quantite: string | null
  /** Entre 0 et 1 */
  part: string
  minutes: number
  feuille: string | null
  numero_ligne: number | null
}

export interface Pointage {
  id: Identifiant
  employe: Identifiant
  employe_details: EmployeResume
  date: string
  heure_debut: string
  heure_fin: string
  /** Case « Pause (−1 h) » : une fois par jour ouvrable */
  pause: boolean
  parts: PartPointage[]
  tache: Identifiant
  tache_details: TacheResume
  marche: InfosLigne
  commentaire: string
  /** H_Durée et HS, en minutes */
  minutes_normales: number
  minutes_hs: number
}

/** Une de mes affaires, dans l'ordre de priorité du formulaire de pointage */
export interface AffairePointable {
  id: Identifiant
  num_affaire: string
  nom: string
  dans_feuille: boolean
  /** Je suis placé (Employé / Contrôleur / Reprise) sur une de ses lignes */
  place: boolean
  /** Une de ses lignes a le statut « prioritaire au pointage » */
  prioritaire: boolean
}

export interface LigneDeDescription {
  id: Identifiant
  feuille: string
  numero: number
  statut: { nom: string; couleur: string } | null
  mes_roles: TypeTache[]
  occupants: Record<'PRODUCTION' | 'CONTROLE' | 'REPRISE', string | null>
}

/** Affaire > Prestations cochées > Projets > Descriptions */
export interface ArborescenceAffaire {
  id: Identifiant
  num_affaire: string
  nom: string
  /** Report DT : Quantité = Quantité linéaire × Surface ÷ Linéaire total */
  report_dt?: boolean
  prestations: {
    id: Identifiant
    nom: string
    unite: string
    projets: {
      id: Identifiant
      nom: string
      surface_m2?: string | null
      lineaire_total?: string | null
      /** quantite_modifiable : droit « Pointages > Quantité des descriptions » sur l'affaire */
      descriptions: { id: Identifiant; nom: string; quantite: string | null; quantite_modifiable?: boolean
        /** Report DT : quantité linéaire (ML) ; la Quantité en est calculée */
        quantite_lineaire?: string | null; ligne: LigneDeDescription | null }[]
    }[]
  }[]
}

export interface ResumePointage {
  debut: string
  fin: string
  nb_lignes: number
  minutes_normales: number
  minutes_hs: number
  erreurs: { date: string; type: string; message: string }[]
}

/** Option d'une liste déroulante */
export interface Option {
  valeur: string | number
  libelle: string
}

/** Colonne d'un tableau (components/ui/UiTableau.vue) */
export interface Colonne {
  cle: string
  libelle: string
  largeur?: string
  alignement?: 'gauche' | 'centre' | 'droite'
  triable?: boolean
  /** Donnée à exporter si elle diffère de `cle` (ex. 'responsables_details') ; false = jamais exportée */
  cleExport?: string | false
  /** Colonne masquée tant que l'utilisateur ne l'affiche pas (bouton « Colonnes ») */
  masqueeParDefaut?: boolean
}

/** Champ d'un formulaire généré (components/formulaires/FormulaireModale.vue) */
export interface ChampFormulaire {
  cle: string
  libelle: string
  type: 'texte' | 'nombre' | 'zone' | 'select' | 'employe' | 'employes' | 'nombres' | 'date' | 'couleur' | 'case'
  requis?: boolean
  aide?: string
  placeholder?: string
  options?: Option[]
  chargerOptions?: () => Promise<Option[]>
  /** Type « employes » : bouton « Tout le monde » (toutes les personnes ayant accès au site) */
  boutonTous?: boolean
  /** Champ de personnes : « Ajouter une configuration… » (Paramètres > Configurations Responsables), et la
   *  configuration par défaut préremplit le champ quand il est vide */
  configurations?: boolean
  /** Type « employe » : source de la recherche (par défaut, les employés visibles) */
  rechercherEmploye?: (texte: string) => Promise<EmployeResume[]>
  /** Affiché seulement si la fonction renvoie vrai (selon les autres valeurs du formulaire) */
  visible?: (valeurs: Record<string, any>) => boolean
  pleineLargeur?: boolean
}
