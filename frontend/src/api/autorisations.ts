// src/api/autorisations.ts
// Paramètres > Accès au site (administrateurs).
import apiClient from './client'
import { creerRessource } from './ressource'
import type { ApercuAcces, EmployeResume, ExplicationAcces, Identifiant, RegleAcces } from '@/types'

const CHEMIN = '/autorisations/regles/'
const ressource = creerRessource<RegleAcces>(CHEMIN)
/** ?confirmer=1 : accepter une modification qui retire son propre accès */
const suffixe = (confirmer: boolean) => (confirmer ? '?confirmer=1' : '')

export const reglesAccesApi = {
  lister: ressource.lister,
  creer: async (donnees: Partial<RegleAcces>, confirmer = false): Promise<RegleAcces> =>
    (await apiClient.post(`${CHEMIN}${suffixe(confirmer)}`, donnees)).data,
  modifier: async (id: Identifiant, donnees: Partial<RegleAcces>, confirmer = false): Promise<RegleAcces> =>
    (await apiClient.patch(`${CHEMIN}${id}/${suffixe(confirmer)}`, donnees)).data,
  supprimer: async (id: Identifiant, confirmer = false): Promise<void> => {
    await apiClient.delete(`${CHEMIN}${id}/${suffixe(confirmer)}`)
  },
}

export const accesApi = {
  apercu: async (): Promise<ApercuAcces> => (await apiClient.get('/autorisations/acces/apercu/')).data,
  verifier: async (employe: Identifiant): Promise<ExplicationAcces & { employe: EmployeResume; statut: string }> =>
    (await apiClient.get('/autorisations/acces/verifier/', { params: { employe } })).data,
  /** Recherche parmi TOUS les employés, y compris ceux qui n'ont pas accès */
  employes: async (texte: string): Promise<EmployeResume[]> =>
    (await apiClient.get('/autorisations/acces/employes/', { params: { search: texte } })).data,
  valeurs: async (): Promise<{ poles: string[]; postes: string[] }> =>
    (await apiClient.get('/autorisations/acces/valeurs/')).data,
}

// ------------------------------------------------------------------
// Paramètres > Autorisation : rôles (droits Autoriser / Refuser par module, action et périmètre)
// ------------------------------------------------------------------
export type Effet = 'AUTORISER' | 'REFUSER'
export interface ModuleDroits {
  code: string
  libelle: string
  aide: string
  cible: 'personnes' | 'affaires' | null
  actions: string[]
  perimetres: Record<string, string>
  /** Droit de base de chaque action (null : aucun) */
  base: Record<string, { condition: string; perimetre: string; libelle: string } | null>
}
export interface CatalogueDroits { actions: Record<string, string>; modules: ModuleDroits[] }
export interface DroitRole {
  id?: Identifiant
  effet: Effet
  module: string
  action: string
  perimetre: string
  valeur: string
  employe: Identifiant | null
  employe_details?: EmployeResume | null
  affaire: Identifiant | null
  affaire_nom?: string | null
}
export interface Role {
  id: Identifiant
  nom: string
  description: string
  actif: boolean
  nb_droits: number
  nb_attributions: number
  droits: DroitRole[]
}
export interface AttributionRole {
  id: Identifiant
  role: Identifiant
  critere: 'MATRICULE' | 'POSTE' | 'POLE'
  employe: Identifiant | null
  employe_details?: EmployeResume | null
  poste: string
  pole: string
  actif: boolean
  description: string
}
export interface ResultatTest { autorise: boolean; resume: string; raisons: string[]; roles?: string[] }

const roles = creerRessource<Role>('/autorisations/roles/')
export const rolesApi = {
  ...roles,
  catalogue: async (): Promise<CatalogueDroits> => (await apiClient.get('/autorisations/catalogue/')).data,
  enregistrerDroits: async (id: Identifiant, droits: DroitRole[]): Promise<Role> =>
    (await apiClient.put(`/autorisations/roles/${id}/droits/`, { droits })).data,
  personnes: async (id: Identifiant): Promise<{ nombre: number; personnes: EmployeResume[] }> =>
    (await apiClient.get(`/autorisations/roles/${id}/personnes/`)).data,
  attributions: async (role: Identifiant): Promise<AttributionRole[]> =>
    (await apiClient.get('/autorisations/attributions/', { params: { role } })).data,
  ajouterAttribution: async (a: Partial<AttributionRole>): Promise<AttributionRole> => (await apiClient.post('/autorisations/attributions/', a)).data,
  modifierAttribution: async (id: Identifiant, a: Partial<AttributionRole>): Promise<AttributionRole> =>
    (await apiClient.patch(`/autorisations/attributions/${id}/`, a)).data,
  retirerAttribution: async (id: Identifiant): Promise<void> => {
    await apiClient.delete(`/autorisations/attributions/${id}/`)
  },
  tester: async (d: { employe: Identifiant; module: string; action: string; cible_employe?: Identifiant | null; cible_affaire?: Identifiant | null }): Promise<ResultatTest> =>
    (await apiClient.post('/autorisations/tester/', d)).data,
  journal: async (): Promise<{ date: string; auteur: string; texte: string }[]> => (await apiClient.get('/autorisations/journal/')).data,
  /** Postes et pôles connus (API RH) pour les listes avec recherche */
  valeurs: async (): Promise<{ postes: string[]; poles: string[] }> => (await apiClient.get('/autorisations/valeurs/')).data,
}
