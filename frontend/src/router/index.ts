// src/router/index.ts
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/store/auth'

declare module 'vue-router' {
  interface RouteMeta {
    titre?: string
    /** Libellé de l'onglet parent dans le menu (fil d'Ariane) */
    section?: string
    module?: string
    /** Droit demandé sur le module (par défaut « voir ») */
    verbe?: string
    administrateur?: boolean
    /** Page pas encore développée : affiche la page « en préparation » */
    enPreparation?: boolean
    public?: boolean
    /** Page affichée sans le menu ni la barre du haut */
    sansCadre?: boolean
  }
}

const EnPreparation = () => import('@/views/commun/EnPreparation.vue')

/** Route d'une page qui reste à développer */
// Toutes les pages du menu sont développées ; gardé pour les prochaines.
export const aDevelopper = (path: string, titre: string, section?: string, module?: string): RouteRecordRaw => ({
  path,
  component: EnPreparation,
  meta: { titre, section, module, enPreparation: true },
})

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/accueil' },
  {
    path: '/planning-projet',
    component: () => import('@/views/planning/PlanningProjet.vue'),
    meta: { titre: 'Planning Projet', module: 'planning_projet' },
  },
  {
    path: '/aide',
    component: () => import('@/views/aide/Aide.vue'),
    meta: { titre: 'Aide' },
  },
  {
    path: '/accueil',
    component: () => import('@/views/accueil/Accueil.vue'),
    meta: { titre: 'Accueil' },
  },
  {
    path: '/parametres/verification-droits',
    component: () => import('@/views/parametres/VerificationDroits.vue'),
    meta: { titre: 'Vérification des droits', section: 'Paramètres', administrateur: true },
  },
  {
    path: '/parametres/configurations-responsables',
    component: () => import('@/views/parametres/ConfigurationsResponsables.vue'),
    meta: { titre: 'Configurations Responsables', section: 'Paramètres', administrateur: true },
  },
  {
    path: '/parametres/controles',
    component: () => import('@/views/parametres/Controles.vue'),
    meta: { titre: 'Contrôles de cohérence', section: 'Paramètres', module: 'parametres_controles' },
  },

  // Pointages
  {
    path: '/pointages/mon-temps',
    component: () => import('@/views/pointages/MonTemps.vue'),
    meta: { titre: 'Mon temps', section: 'Pointages', module: 'pointages' },
  },
  {
    path: '/pointages/suivi',
    component: () => import('@/views/pointages/Suivi.vue'),
    meta: { titre: 'Suivi', section: 'Pointages', module: 'pointages_suivi' },
  },
  {
    path: '/pointages/verification',
    component: () => import('@/views/pointages/Verification.vue'),
    meta: { titre: 'Vérification', section: 'Pointages', module: 'pointages_verification' },
  },

  // Google Sheet
  {
    path: '/google-sheet/mes-feuilles',
    component: () => import('@/views/feuilles/MesFeuilles.vue'),
    meta: { titre: 'Mes feuilles', section: 'Google Sheet', module: 'gsheets' },
  },
  {
    path: '/google-sheet/nouvelle',
    component: () => import('@/views/feuilles/FormulaireFeuille.vue'),
    meta: { titre: 'Créer une nouvelle feuille', section: 'Google Sheet', module: 'gsheets_feuilles', verbe: 'creer' },
  },
  {
    path: '/google-sheet/feuilles/:id(\\d+)',
    component: () => import('@/views/feuilles/Feuille.vue'),
    meta: { titre: 'Feuille', section: 'Google Sheet', module: 'gsheets' },
  },
  {
    path: '/google-sheet/feuilles/:id(\\d+)/modifier',
    component: () => import('@/views/feuilles/FormulaireFeuille.vue'),
    meta: { titre: 'Modifier la feuille', section: 'Google Sheet', module: 'gsheets' },
  },

  // Marchés
  { path: '/marches', redirect: '/marches/ajouter' },
  {
    path: '/marches/ajouter',
    component: () => import('@/views/marches/AjouterMarche.vue'),
    meta: { titre: 'Ajouter un marché', section: 'Marchés', module: 'marches_affaires' },
  },
  {
    path: '/marches/mes-marches',
    component: () => import('@/views/marches/MesMarches.vue'),
    meta: { titre: 'Mes marchés', section: 'Marchés', module: 'marches' },
  },
  {
    path: '/marches/archives',
    component: () => import('@/views/marches/ArchivesMarches.vue'),
    meta: { titre: 'Archives', section: 'Marchés', module: 'marches_archives' },
  },
  {
    path: '/marches/duree-estimative',
    component: () => import('@/views/marches/DureeEstimative.vue'),
    meta: { titre: 'Durée estimatif', section: 'Marchés', module: 'marches_duree' },
  },
  { path: '/rendement', redirect: '/rendement/globale' },
  {
    path: '/rendement/globale',
    component: () => import('@/views/rendement/Globale.vue'),
    meta: { titre: 'Globale', section: 'Rendement', module: 'rendements' },
  },
  {
    path: '/rendement/evolution',
    component: () => import('@/views/rendement/Evolution.vue'),
    meta: { titre: 'Evolution', section: 'Rendement', module: 'rendements' },
  },
  {
    path: '/rendement/analyse',
    component: () => import('@/views/rendement/Analyse.vue'),
    meta: { titre: 'Analyse', section: 'Rendement', module: 'rendements' },
  },
  {
    path: '/rendement/reel-objectif',
    component: () => import('@/views/rendement/ReelObjectif.vue'),
    meta: { titre: 'Réel vs Objectif', section: 'Rendement', module: 'rendements' },
  },
  {
    path: '/rendement/evaluation-employe',
    component: () => import('@/views/rendement/Evaluation.vue'),
    meta: { titre: 'Evaluation Employé', section: 'Rendement', module: 'rendements' },
  },
  {
    path: '/affichage-everwin',
    component: () => import('@/views/affichage/AffichageEverwin.vue'),
    meta: { titre: 'Affichage Everwin', module: 'affichage_everwin' },
  },
  {
    path: '/parametres/autorisations',
    component: () => import('@/views/parametres/Autorisation.vue'),
    meta: { titre: 'Autorisation', section: 'Paramètres', administrateur: true },
  },
  {
    path: '/parametres/temps-estimatif',
    component: () => import('@/views/parametres/TempsEstimatif.vue'),
    meta: { titre: 'Temps Estimatif', section: 'Paramètres', administrateur: true },
  },
  {
    path: '/parametres/graphiques',
    component: () => import('@/views/parametres/Graphiques.vue'),
    meta: { titre: 'Graphiques', section: 'Paramètres', administrateur: true },
  },
  {
    path: '/parametres/rendement-note',
    component: () => import('@/views/parametres/RendementNote.vue'),
    meta: { titre: 'Rendement & Note', section: 'Paramètres', administrateur: true },
  },
  {
    path: '/parametres/acces-site',
    component: () => import('@/views/parametres/AccesSite.vue'),
    meta: { titre: 'Accès au site', section: 'Paramètres', administrateur: true },
  },

  // Personnes qui ne respectent pas les règles d'accès
  {
    path: '/acces-refuse',
    component: () => import('@/views/commun/AccesRefuse.vue'),
    meta: { titre: 'Accès non autorisé', public: true, sansCadre: true },
  },

  // Pages développées
  {
    path: '/utilisateurs',
    component: () => import('@/views/utilisateurs/Utilisateurs.vue'),
    meta: { titre: 'Utilisateurs', administrateur: true },
  },
  {
    path: '/equipes',
    component: () => import('@/views/equipes/Equipes.vue'),
    meta: { titre: 'Équipes', administrateur: true },
  },
  {
    path: '/profil',
    component: () => import('@/views/profil/Profil.vue'),
    meta: { titre: 'Mon profil', module: 'profils' },
  },

  { path: '/:chemin(.*)*', component: () => import('@/views/commun/PageIntrouvable.vue'), meta: { titre: 'Page introuvable' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  // Règles d'accès au site : la seule page possible est « Accès non autorisé »
  if (!auth.aAcces) return to.path === '/acces-refuse' ? true : '/acces-refuse'
  if (to.path === '/acces-refuse') return '/'
  if (to.meta.public) return true
  // Page non autorisée (Paramètres > Autorisation) : retour à l'accueil
  if (to.meta.administrateur && !auth.estAdministrateur) return '/accueil'
  if (to.meta.module && !auth.peut(to.meta.verbe ?? 'voir', to.meta.module)) return '/accueil'
  return true
})

router.afterEach((to) => {
  document.title = to.meta.titre ? `${to.meta.titre} – Ikarama` : 'Ikarama'
})

export default router
