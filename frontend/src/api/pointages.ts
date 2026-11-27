// src/api/pointages.ts
// Pointages > Mon temps : uniquement mes pointages.
import apiClient from './client'
import { creerRessource, telecharger } from './ressource'
import type { AffairePointable, ArborescenceAffaire, EmployeResume, Identifiant, Page, Pointage, ResumePointage, TacheResume } from '@/types'

export interface CreneauxJour {
  date: string
  ouvrable: boolean
  occupes: [string, string][]
  /** Créneaux non pointés entre 07:30 et 16:30 */
  libres: [string, string][]
  /** Heures proposées : premier créneau libre, sinon après le dernier pointage (fin vide) */
  suggestion: { debut: string; fin: string | null }
}

export interface SaisiePointage {
  date: string
  heure_debut: string
  heure_fin: string
  /** Retire 1 h (une fois par jour ouvrable, obligatoire) */
  pause: boolean
  /** Plusieurs descriptions : tâche « Plusieurs descriptions », même projet (temps au prorata des quantités) */
  descriptions: Identifiant[]
  tache: Identifiant
  commentaire: string
  /** Nouvelles quantités des descriptions choisies { id: valeur } (historique dans la feuille) */
  quantites?: Record<string, string>
  /** Report DT : nouvelles quantités linéaires { id: valeur } (les Quantités du projet sont recalculées) */
  quantites_lineaires?: Record<string, string>
}

const ressource = creerRessource<Pointage, SaisiePointage>('/pointages/')
export const pointagesApi = {
  ...ressource,
  /** Créer pour une autre personne (Dupliquer dans Pointages > Suivi : droit « Modifier » du Suivi sur elle) */
  creerPour: async (d: SaisiePointage, employe: Identifiant): Promise<Pointage> =>
    (await apiClient.post('/pointages/', d, { params: { employe } })).data,
  /** Totaux et erreurs de pointage de la période */
  resume: (debut: string, fin: string) => ressource.action<ResumePointage>(undefined, 'resume', { debut, fin }, 'get'),
  /** Mes affaires (ou celles de ?employe= pour un administrateur), dans l'ordre de priorité */
  affaires: (search: string, employe?: Identifiant | null) =>
    ressource.action<Page<AffairePointable>>(undefined, 'affaires', { search, page_size: 50, employe: employe ?? undefined }, 'get'),
  /** Prestations > Projets > Descriptions d'une affaire, avec la ligne de feuille de chaque description */
  arborescence: (affaire: Identifiant, employe?: Identifiant | null) =>
    ressource.action<ArborescenceAffaire>(undefined, 'arborescence', { affaire, employe: employe ?? undefined }, 'get'),
  taches: () => ressource.action<TacheResume[]>(undefined, 'taches', {}, 'get'),
  /** Créneaux non pointés de 07h30–16h30 d'un jour, et heures proposées pour un nouveau pointage */
  creneaux: (date: string, options: { employe?: Identifiant | null; sauf?: Identifiant | null } = {}) =>
    ressource.action<CreneauxJour>(undefined, 'creneaux', { date, employe: options.employe ?? undefined, sauf: options.sauf ?? undefined }, 'get'),
}

// ------------------------------------------------------------------
// Pointages > Suivi et Vérification (superadmins)
// ------------------------------------------------------------------
const suivi = creerRessource<Pointage, SaisiePointage>('/pointages/tous/')
/** Pointages de toutes les personnes ayant accès au site */
export const suiviPointagesApi = {
  ...suivi,
  resume: (parametres: Record<string, unknown>) =>
    suivi.action<ResumePointage & { nb_personnes: number }>(undefined, 'resume', parametres, 'get'),
}

export interface LigneVerification {
  id: number
  date: string
  employe: EmployeResume
  /** Heures pointées (H_Durée) et manque par rapport aux 8 h, en heures */
  heures: number
  manque: number
}
/** Une ligne par personne et par jour pointé */
export const verificationApi = creerRessource<LigneVerification>('/pointages/verification/')

// ------------------------------------------------------------------
// Affichage Everwin : une semaine en grille (lecture seule)
// ------------------------------------------------------------------
export interface DetailEverwin {
  heure_debut: string
  heure_fin: string
  minutes: number
  minutes_hs: number
  pause: boolean
  tache: string
  prestation: string
  projet: string
  descriptions: string[]
  commentaire: string
}

export interface GrilleEverwin {
  employe: EmployeResume
  chef: EmployeResume | null
  /** Un rôle donne l'affichage d'autres personnes (Paramètres > Autorisation) */
  peut_choisir?: boolean
  jours: { date: string; nom: string; ouvrable: boolean }[]
  /** Une ligne par affaire et par tâche */
  affaires: {
    /** « idAffaire-idTâche » */
    id: string
    affaire_id: Identifiant
    num_affaire: string
    nom: string
    tache: string
    taches: string[]
    total_minutes: number
    jours: Record<string, { minutes: number; details: DetailEverwin[] }>
  }[]
  /** Par jour : tout le temps pointé, la H_Durée, et « incomplet » (rouge) si la H_Durée < 8 h */
  totaux: Record<string, { minutes: number; minutes_normales: number; incomplet: boolean }>
  total_minutes: number
}

export const everwinApi = {
  /** semaine : n'importe quel jour de la semaine ; employe : une personne du périmètre (Affichage Everwin) */
  semaine: async (semaine: string, employe?: Identifiant | null): Promise<GrilleEverwin> =>
    (await apiClient.get('/pointages/everwin/', { params: { semaine, employe: employe ?? undefined } })).data,
  exporter: async (semaine: string, employe?: Identifiant | null): Promise<void> => {
    const { data } = await apiClient.get('/pointages/everwin/exporter/', {
      params: { semaine, employe: employe ?? undefined }, responseType: 'blob',
    })
    telecharger(data, `Everwin_${semaine}.xlsx`)
  },
  /** Recherche parmi les personnes dont on peut voir l'affichage */
  personnes: async (recherche: string): Promise<EmployeResume[]> =>
    (await apiClient.get('/pointages/everwin/personnes/', { params: { recherche } })).data,
}
