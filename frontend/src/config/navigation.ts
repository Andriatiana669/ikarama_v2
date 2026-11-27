// src/config/navigation.ts
/**
 * Menu latéral : SEULE source de vérité pour les onglets et sous-onglets.
 * Ajouter une entrée ici + la route correspondante dans router/index.ts.
 *
 * Visibilité (Paramètres > Autorisation) : l'entrée est masquée si l'utilisateur n'a pas le droit `verbe`
 * (« voir » par défaut) sur `module` (store/auth.ts > peut()), ou si elle est réservée au superadmin.
 */
export interface EntreeMenu {
  libelle: string
  icone: string // classe Bootstrap Icons, sans le préfixe « bi- »
  route?: string
  module?: string
  /** Droit demandé sur le module (par défaut « voir ») */
  verbe?: string
  administrateur?: boolean // visible seulement pour les superadmins
  enfants?: EntreeMenu[]
}

export const NAVIGATION: EntreeMenu[] = [
  { libelle: 'Accueil', icone: 'house', route: '/accueil' },
  {
    libelle: 'Pointages',
    icone: 'clock-history',
    module: 'pointages',
    enfants: [
      { libelle: 'Mon temps', icone: 'stopwatch', route: '/pointages/mon-temps' },
      { libelle: 'Suivi', icone: 'list-check', route: '/pointages/suivi', module: 'pointages_suivi' },
      { libelle: 'Vérification', icone: 'patch-check', route: '/pointages/verification', module: 'pointages_verification' },
    ],
  },
  {
    libelle: 'Google Sheet',
    icone: 'file-earmark-spreadsheet',
    module: 'gsheets',
    enfants: [
      { libelle: 'Mes feuilles', icone: 'files', route: '/google-sheet/mes-feuilles' },
      { libelle: 'Créer une nouvelle feuille', icone: 'plus-square', route: '/google-sheet/nouvelle', module: 'gsheets_feuilles', verbe: 'creer' },
    ],
  },
  {
    libelle: 'Marchés',
    icone: 'briefcase',
    module: 'marches',
    enfants: [
      { libelle: 'Ajouter un marché', icone: 'plus-square', route: '/marches/ajouter', module: 'marches_affaires' },
      { libelle: 'Mes marchés', icone: 'person-workspace', route: '/marches/mes-marches' },
      { libelle: 'Archives', icone: 'archive', route: '/marches/archives', module: 'marches_archives' },
      { libelle: 'Durée estimatif', icone: 'hourglass-split', route: '/marches/duree-estimative', module: 'marches_duree' },
    ],
  },
  {
    libelle: 'Rendement',
    icone: 'graph-up-arrow',
    module: 'rendements',
    enfants: [
      { libelle: 'Globale', icone: 'grid-1x2', route: '/rendement/globale' },
      { libelle: 'Evolution', icone: 'graph-up', route: '/rendement/evolution' },
      { libelle: 'Analyse', icone: 'search', route: '/rendement/analyse' },
      { libelle: 'Réel vs Objectif', icone: 'bullseye', route: '/rendement/reel-objectif' },
      { libelle: 'Evaluation Employé', icone: 'person-check', route: '/rendement/evaluation-employe' },
    ],
  },
  { libelle: 'Planning Projet', icone: 'calendar-week', route: '/planning-projet', module: 'planning_projet' },
  { libelle: 'Affichage Everwin', icone: 'display', route: '/affichage-everwin', module: 'affichage_everwin' },
  {
    libelle: 'Paramètres',
    icone: 'gear',
    // Visible dès qu'une de ses pages est permise (Contrôles de cohérence peut l'être par un rôle)
    enfants: [
      { libelle: 'Autorisation', icone: 'shield-lock', route: '/parametres/autorisations', administrateur: true },
      { libelle: 'Vérification des droits', icone: 'shield-check', route: '/parametres/verification-droits', administrateur: true },
      { libelle: 'Accès au site', icone: 'door-open', route: '/parametres/acces-site', administrateur: true },
      { libelle: 'Rendement & Note', icone: 'speedometer2', route: '/parametres/rendement-note', administrateur: true },
      { libelle: 'Graphiques', icone: 'bar-chart-line', route: '/parametres/graphiques', administrateur: true },
      { libelle: 'Temps Estimatif', icone: 'hourglass-split', route: '/parametres/temps-estimatif', administrateur: true },
      { libelle: 'Configurations Responsables', icone: 'collection', route: '/parametres/configurations-responsables', administrateur: true },
      { libelle: 'Contrôles de cohérence', icone: 'clipboard2-check', route: '/parametres/controles', module: 'parametres_controles' },
    ],
  },
  { libelle: 'Utilisateurs', icone: 'people', route: '/utilisateurs', administrateur: true },
  { libelle: 'Équipes', icone: 'diagram-3', route: '/equipes', administrateur: true },
  { libelle: 'Profil', icone: 'person-circle', route: '/profil', module: 'profils' },
  { libelle: 'Aide', icone: 'question-circle', route: '/aide' },
]
