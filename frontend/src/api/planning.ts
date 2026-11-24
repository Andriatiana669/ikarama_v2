// src/api/planning.ts — Planning Projet
import apiClient from './client'
import { telecharger } from './ressource'
import type { EmployeResume, Identifiant } from '@/types'

export interface ProjetPlanning { projet_id: Identifiant; projet: string; affaire: string; num_affaire: string; prestation: string; affaire_id?: Identifiant }
/** Échéance d'un projet : date de livraison, avancement moyen de ses lignes, état */
export interface Echeance { date_livraison: string | null; avancement: number; etat: 'retard' | 'proche' | 'ok' | 'termine' }
export interface CasePlanning {
  /** Passé et aujourd'hui : projets pointés (minutes) */
  pointe: (ProjetPlanning & { minutes: number })[]
  /** Aujourd'hui et l'avenir : projets planifiés */
  prevu: (ProjetPlanning & { id: Identifiant; commentaire: string })[]
}
export interface LignePlanning {
  employe: EmployeResume
  cases: Record<string, CasePlanning>
  en_cours: (ProjetPlanning & { description: string })[]
  /** Jours ouvrables des 14 prochains jours sans rien de pointé ni de planifié */
  jours_libres: string[]
  poles: string[]
  postes: string[]
  /** Responsables successifs (N+1, N+2…) : filtre « Équipe de » */
  chefs: Identifiant[]
  planifiable: boolean
}
export interface SemainePlanning {
  debut: string
  fin: string
  aujourdhui: string
  semaines: { numero: number; annee: number; debut: string }[]
  jours: { date: string; nom: string; ouvrable: boolean; passe: boolean; aujourdhui: boolean }[]
  statut_en_cours: { id: Identifiant; nom: string; couleur: string } | null
  /** Projets livrés dans la plage, par date de livraison */
  echeances: Record<string, (ProjetPlanning & Echeance)[]>
  lignes: LignePlanning[]
  droits: { creer: boolean; modifier: boolean; supprimer: boolean; exporter: boolean }
}

export const planningApi = {
  /** Plusieurs semaines à partir du lundi de « debut » */
  plage: async (debut: string, semaines: number): Promise<SemainePlanning> =>
    (await apiClient.get('/planning/semaine/', { params: { debut, semaines } })).data,
  exporter: async (debut: string, semaines: number): Promise<void> => {
    const { data } = await apiClient.get('/planning/semaine/exporter/', { params: { debut, semaines }, responseType: 'blob' })
    telecharger(data, `Planning_${debut}.xlsx`)
  },
  projets: async (recherche = ''): Promise<(ProjetPlanning & Echeance)[]> =>
    (await apiClient.get('/planning/projets/', { params: { recherche } })).data,
  planifier: async (d: { employe: Identifiant; date: string; projet: Identifiant }) => (await apiClient.post('/planning/affectations/', d)).data,
  deplacer: async (id: Identifiant, d: { employe?: Identifiant; date?: string }) => (await apiClient.patch(`/planning/affectations/${id}/`, d)).data,
  retirer: async (id: Identifiant) => {
    await apiClient.delete(`/planning/affectations/${id}/`)
  },
}
