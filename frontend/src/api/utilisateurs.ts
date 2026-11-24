// src/api/utilisateurs.ts
import { creerRessource } from './ressource'
import type { Employe, EmployeResume, Identifiant } from '@/types'

const ressource = creerRessource<Employe>('/utilisateurs/')

export interface ResumeSynchro {
  total: number
  crees: number
  mis_a_jour: number
  chefs_lies: number
  erreurs: string[]
}

export const utilisateursApi = {
  ...ressource,
  /** Recherche courte pour les listes déroulantes */
  rechercher: async (texte: string, taille = 20): Promise<EmployeResume[]> =>
    (await ressource.lister({ search: texte, format_court: true, page_size: taille })).results as unknown as EmployeResume[],
  subordonnes: (id: Identifiant, niveau: 'direct' | 'hierarchie' = 'direct') =>
    ressource.action<EmployeResume[]>(id, 'subordonnes', { niveau }, 'get'),
  valeursFiltres: () =>
    ressource.action<{ poles: string[]; postes: string[]; statuts: string[] }>(undefined, 'valeurs-filtres', {}, 'get'),
  synchroniser: () => ressource.action<ResumeSynchro>(undefined, 'synchroniser'),
}
