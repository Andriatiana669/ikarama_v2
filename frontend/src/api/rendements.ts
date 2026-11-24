// src/api/rendements.ts
// Paramètres > Rendement & Note : réglages des formules des feuilles.
import apiClient from './client'
import { telecharger } from './ressource'
import type { ParametresRendement } from '@/types'

export const parametresRendementApi = {
  lire: async (): Promise<ParametresRendement> => (await apiClient.get('/rendements/parametres/')).data,
  enregistrer: async (donnees: Partial<ParametresRendement>): Promise<ParametresRendement> =>
    (await apiClient.put('/rendements/parametres/', donnees)).data,
  reinitialiser: async (): Promise<ParametresRendement> => (await apiClient.post('/rendements/parametres/reinitialiser/')).data,
}

// ------------------------------------------------------------------
// Page Rendement
// ------------------------------------------------------------------
export interface FiltresRendement {
  affaires?: string
  prestations?: string
  projets?: string
  taches?: string
  statut?: string
  debut?: string
  fin?: string
  granularite?: 'jour' | 'mois'
}

/** Une barre : un élément du niveau en dessous de la sélection (prestation, projet ou description) */
export interface BarreRendement {
  cle: string
  nom: string
  unite: string
  quantite: number
  heures: number
  rendement: number | null
  objectif: number
}

export interface AnalyseRendement {
  heures_par_jour: number
  granularite: 'jour' | 'mois'
  /** null : aucune affaire cochée */
  niveau: 'prestations' | 'projets' | 'descriptions' | null
  /** Unité commune, ou null si les prestations ont des unités différentes */
  unite: string | null
  unites: string[]
  barres: BarreRendement[]
  /** Global de la sélection (rendement et objectif seulement avec une unité commune) */
  equipes: { quantite: number; heures: number; rendement: number | null; objectif: number | null } | null
  periodes: string[]
  personnes: { id: number; nom_affiche: string; identifiant: string; code_barre: string
    quantite: number; heures: number; rendement: number | null; evolution: number[] }[]
  rentabilites: unknown[]
}

export interface OptionsRendement {
  affaires: { id: number; nom: string }[]
  prestations: { id: number; nom: string }[]
  projets: { id: number; nom: string; affaire: string }[]
  taches: { id: number; nom: string }[]
  statuts: { id: number; nom: string; couleur: string }[]
  /** Commentaires complets des lignes de la sélection (« __sans__ » = Sans commentaire) */
  commentaires?: { id: string; nom: string }[]
  commentaires_controle?: { id: string; nom: string }[]
}

export const analyseRendementApi = {
  analyser: async (f: FiltresRendement): Promise<AnalyseRendement> => (await apiClient.get('/rendements/analyse/', { params: f })).data,
  options: async (f: FiltresRendement): Promise<OptionsRendement> => (await apiClient.get('/rendements/analyse/options/', { params: f })).data,
  exporter: async (f: FiltresRendement): Promise<void> => {
    const { data } = await apiClient.get('/rendements/analyse/exporter/', { params: f, responseType: 'blob' })
    telecharger(data, 'Rendement.xlsx')
  },
}

// ------------------------------------------------------------------
// Rendement > Globale (par employé)
// ------------------------------------------------------------------
export interface EmployeGlobale {
  id: number
  nom_affiche: string
  identifiant: string
  code_barre: string
  quantite: number
  heures: number
  /** Moyenne de ses rendements par description (null si unités différentes ou pas de temps) */
  rendement: number | null
  objectif: number | null
  rentabilite: number | null
  descriptions: { id: number; nom: string; prestation_id: number; unite: string; quantite: number; heures: number
    rendement: number | null; objectif: number }[]
}

export interface DonneesGlobale {
  /** 'pointages' (normal), 'feuilles' ou 'pointages_seuls' (source « Pointages » : graphiques en heures) */
  source?: string
  heures_par_jour: number
  unite: string | null
  unites: string[]
  employes: EmployeGlobale[]
  /** Objectif par prestation (tableau « Rendement objectif ») */
  objectifs: { id: number; nom: string; unite: string; objectif: number }[]
  temps_par_tache: { id: number; nom: string; heures: number }[]
  /** Tâches cochées « Dans le camembert du temps » (Marchés > Tâches) ; vide = toutes */
  taches_camembert: { id: number; nom: string }[]
  liste_employes: { id: number; nom: string; identifiant: string }[]
  /** Mois (AAAA-MM) des dates de début de la sélection, du plus récent au plus ancien */
  mois_disponibles: string[]
}

export const globaleRendementApi = {
  charger: async (f: Record<string, string>): Promise<DonneesGlobale> => (await apiClient.get('/rendements/globale/', { params: f })).data,
  exporter: async (f: Record<string, string>): Promise<void> => {
    const { data } = await apiClient.get('/rendements/globale/exporter/', { params: f, responseType: 'blob' })
    telecharger(data, 'Rendement_globale.xlsx')
  },
}

// ------------------------------------------------------------------
// Rendement > Evolution et Paramètres > Graphiques
// ------------------------------------------------------------------
export interface CourbeEvolution {
  nom: string
  couleur: string
  taches: { id: number; nom: string }[]
  /** Rendement / j pour chaque date de « dates » (null : rien pointé ce jour-là avec ces tâches) */
  valeurs: (number | null)[]
}
export interface DonneesEvolution extends DonneesGlobale {
  dates: string[]
  courbes: CourbeEvolution[]
  objectif: number | null
}
export const evolutionRendementApi = {
  charger: async (f: Record<string, string>): Promise<DonneesEvolution> => (await apiClient.get('/rendements/evolution/', { params: f })).data,
  exporter: async (f: Record<string, string>): Promise<void> => {
    const { data } = await apiClient.get('/rendements/evolution/exporter/', { params: f, responseType: 'blob' })
    telecharger(data, 'Rendement_evolution.xlsx')
  },
}

export interface ParametresGraphiques {
  taches_camembert: number[]
  courbe1_nom: string
  courbe1_couleur: string
  courbe1_taches: number[]
  courbe2_nom: string
  courbe2_couleur: string
  courbe2_taches: number[]
  barre1_nom: string
  barre1_couleur: string
  barre1_taches: number[]
  barre2_nom: string
  barre2_couleur: string
  barre2_taches: number[]
  analyse_seuil_temps: number
  analyse_seuil_aide: number
  analyse_mois_adaptation: number
  analyse_seuil_baisse: number
  /** Autorise le bouton « Données des feuilles » dans les onglets du Rendement */
  donnees_feuilles: boolean
  /** Autorise la source « Données des pointages » (affaires pointées sans feuille) */
  donnees_pointages?: boolean
  /** Synchronisation des données : mêmes Affaires et Prestations dans les onglets du Rendement */
  synchronisation?: boolean
}
export const parametresGraphiquesApi = {
  lire: async (): Promise<ParametresGraphiques> => (await apiClient.get('/rendements/graphiques/')).data,
  enregistrer: async (d: ParametresGraphiques): Promise<ParametresGraphiques> => (await apiClient.put('/rendements/graphiques/', d)).data,
}

// ------------------------------------------------------------------
// Rendement > Réel vs Objectif (deux barres par employé)
// ------------------------------------------------------------------
export interface DonneesReelObjectif {
  source?: string
  heures_par_jour: number
  unite: string | null
  unites: string[]
  objectifs: DonneesGlobale['objectifs']
  liste_employes: DonneesGlobale['liste_employes']
  mois_disponibles: string[]
  /** Barre 1 : le réel (ses tâches) ; barre 2 : le Rendement objectif */
  barres: { nom: string; couleur: string; taches: { id: number; nom: string }[]; objectif: boolean }[]
  employes: EmployeGlobale[]
}
export const reelObjectifApi = {
  charger: async (f: Record<string, string>): Promise<DonneesReelObjectif> => (await apiClient.get('/rendements/reel-objectif/', { params: f })).data,
  exporter: async (f: Record<string, string>): Promise<void> => {
    const { data } = await apiClient.get('/rendements/reel-objectif/exporter/', { params: f, responseType: 'blob' })
    telecharger(data, 'Rendement_reel_vs_objectif.xlsx')
  },
}

// ------------------------------------------------------------------
// Rendement > Evaluation Employé (une barre par mois de pointage)
// ------------------------------------------------------------------
export interface MoisEvaluation {
  /** AAAA-MM */
  mois: string
  rendement: number | null
  /** Heures pointées du mois (graphique en heures de la source « Pointages ») */
  heures?: number
  employes: { id: number; identifiant: string; rendement: number; objectifs: { prestation_id: number; objectif: number }[] }[]
}
export interface DonneesEvaluation extends DonneesGlobale {
  mois: MoisEvaluation[]
}
export const evaluationRendementApi = {
  charger: async (f: Record<string, string>): Promise<DonneesEvaluation> => (await apiClient.get('/rendements/evaluation/', { params: f })).data,
  exporter: async (f: Record<string, string>): Promise<void> => {
    const { data } = await apiClient.get('/rendements/evaluation/exporter/', { params: f, responseType: 'blob' })
    telecharger(data, 'Rendement_evaluation_employe.xlsx')
  },
}

// ------------------------------------------------------------------
// Rendement > Analyse (employés comparés, mois par mois)
// ------------------------------------------------------------------
export type ZoneAnalyse = 'garder' | 'revoir' | 'potentiel' | 'ponctuel' | 'aide' | null
export interface CaseAnalyse {
  heures: number
  heures_aide: number
  /** Part du temps de l'employé dans le mois (0 à 1) */
  part: number
  rendement: number | null
  objectif: number | null
  rentabilite: number | null
  zone: ZoneAnalyse
  zone_libelle: string
  /** Carte de la période : mois où le signal est apparu */
  badges: { code: 'aide' | 'adaptation' | 'baisse'; libelle: string; mois?: string[] }[]
}
export interface EmployeAnalyse {
  id: number
  identifiant: string
  nom_affiche: string
  code_barre: string
  heures_mois: number
  carte: (CaseAnalyse & { cle: string; affaire: string; prestation: string; unite: string })[]
  suivi: { mois: string[]; lignes: { cle: string; affaire: string; prestation: string; unite: string; cases: Record<string, CaseAnalyse> }[] }
}
export interface DonneesAnalyse {
  heures_par_jour: number
  seuils: { temps: number; aide: number; adaptation: number; baisse: number }
  liste_employes: { id: number; nom: string; identifiant: string }[]
  mois_disponibles: string[]
  /** Mois analysés (cochés) ; vide = tous */
  mois: string[]
  employes: EmployeAnalyse[]
}
export const analyseEmployesApi = {
  charger: async (f: Record<string, string>): Promise<DonneesAnalyse> => (await apiClient.get('/rendements/analyse-employes/', { params: f })).data,
  exporter: async (f: Record<string, string>): Promise<void> => {
    const { data } = await apiClient.get('/rendements/analyse-employes/exporter/', { params: f, responseType: 'blob' })
    telecharger(data, 'Rendement_analyse.xlsx')
  },
}
