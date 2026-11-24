// src/api/equipes.ts
// Équipes calculées depuis les fiches employés (lecture seule).
import { creerRessource } from './ressource'
import type { Equipe, EquipeDetail, Identifiant, NoeudHierarchie, PoleRH } from '@/types'

const ressource = creerRessource<Equipe>('/equipes/')

export const equipesApi = {
  lister: ressource.lister,
  /** Équipe et membres ; id = id du responsable */
  lire: (id: Identifiant) => ressource.lire(id) as unknown as Promise<EquipeDetail>,
  mesEquipes: () => ressource.action<Equipe[]>(undefined, 'mes-equipes', {}, 'get'),
  poles: () => ressource.action<PoleRH[]>(undefined, 'poles', {}, 'get'),
  organigramme: (pole?: string) => ressource.action<NoeudHierarchie[]>(undefined, 'organigramme', { pole }, 'get'),
}
