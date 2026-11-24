import apiClient from './client'
// src/api/marches.ts
import { creerRessource, telecharger } from './ressource'
import type { Affaire, DescriptionProjet, ElementCatalogue, Identifiant, Prestation, Projet } from '@/types'

const affaires = creerRessource<Affaire>('/marches/affaires/')
export const affairesApi = {
  ...affaires,
  /** Coche / décoche une prestation pour l'affaire */
  cocherPrestation: (affaire: Identifiant, prestation: Identifiant, coche: boolean) =>
    affaires.action<{ coche: boolean }>(affaire, 'prestations', { prestation, coche }),
  /** Réservé aux responsables de l'affaire (et aux administrateurs) */
  modifierMembres: (affaire: Identifiant, membres: Identifiant[]) => affaires.action<Affaire>(affaire, 'membres', { membres }),
  desarchiver: (affaire: Identifiant) => affaires.action<Affaire>(affaire, 'desarchiver'),
  /** Suppression définitive (refusée s'il reste des prestations cochées, projets ou descriptions) */
  supprimerDefinitivement: (affaire: Identifiant) => affaires.action<void>(affaire, 'supprimer'),
}

export const prestationsApi = creerRessource<Prestation>('/marches/prestations/')

/** La quantité d'un projet est calculée : somme des quantités de ses descriptions */
export const projetsApi = creerRessource<Projet>('/marches/projets/')

export const tachesApi = creerRessource<ElementCatalogue>('/marches/taches/')
export const statutsApi = creerRessource<ElementCatalogue>('/marches/statuts/')

/** Descriptions d'un projet : toujours lister avec { projet: id } */
export const descriptionsApi = creerRessource<DescriptionProjet>('/marches/descriptions/')

// ------------------------------------------------------------------
// Marchés > Durée estimatif (temps par Projet / Commune, réparti sur les ressources disponibles)
// ------------------------------------------------------------------
export interface ProjetDuree {
  id: Identifiant
  nom: string
  affaire: string
  num_affaire: string
  prestation: string
  unite: string
  rendement_objectif: number | null
  nb_descriptions: number
  quantite: number
  quantite_restante: number
  /** Temps estimatif d'une personne seule (heures) : quantité ÷ objectif × heures par jour */
  temps_heures: number | null
  temps_restant_heures: number | null
  date_livraison: string | null
}
type Option = { id: Identifiant; nom: string; detail?: string }
export interface DureeEstimative {
  heures_par_jour: number
  projets: ProjetDuree[]
  options: { affaires: Option[]; prestations: Option[]; rendements: Option[]; descriptions: Option[]; statuts: Option[] }
}
export const dureeEstimativeApi = {
  charger: async (filtres: Record<string, string>): Promise<DureeEstimative> =>
    (await apiClient.get('/marches/duree-estimative/', { params: filtres })).data,
  exporter: async (filtres: Record<string, string>, ressources: Record<string, number>, unite: 'jours' | 'heures') => {
    const { data } = await apiClient.get('/marches/duree-estimative/exporter/', {
      params: { ...filtres, ressources: JSON.stringify(ressources), unite }, responseType: 'blob' })
    telecharger(data, 'Duree_estimatif.xlsx')
  },
}

// Paramètres > Configurations Responsables : groupes de personnes ajoutés d'un coup dans le champ Responsables
export interface ConfigurationResponsables {
  id: Identifiant
  nom: string
  personnes: Identifiant[]
  personnes_details: import('@/types').EmployeResume[]
  par_defaut: boolean
  modifie_le?: string
}
export const configurationsResponsablesApi = creerRessource<ConfigurationResponsables>('/marches/configurations-responsables/')
