// src/api/gsheets.ts
import apiClient from './client'
import { creerRessource } from './ressource'
import type { AffaireDisponible, EmployeResume, Feuille, Identifiant, LigneFeuille, ModificationLigne, SuiviFeuille } from '@/types'

export interface SaisieFeuille {
  nom: string
  utiliser_criteres: boolean
  perimetres_saisis: { affaire: Identifiant; prestation: Identifiant }[]
  /** Un commentaire par critère de CTRL, dans l'ordre */
  criteres_saisis: string[]
}

const feuilles = creerRessource<Feuille, SaisieFeuille>('/gsheets/feuilles/')
export const feuillesApi = {
  ...feuilles,
  /** Affaires dont je suis responsable, avec leurs prestations cochées */
  /** feuille : en modification, ses propres prestations ne sont pas signalées « déjà dans une feuille » */
  affairesDisponibles: async (feuille?: Identifiant | null): Promise<AffaireDisponible[]> =>
    (await apiClient.get('/gsheets/feuilles/affaires-disponibles/', { params: { feuille: feuille ?? undefined } })).data,
  /** Responsables et membres de chaque affaire : { id d'affaire : personnes } */
  personnes: (id: Identifiant) => feuilles.action<Record<string, EmployeResume[]>>(id, 'personnes', {}, 'get'),
}

export type SaisieLigne = Partial<
  Pick<LigneFeuille, 'employe' | 'controleur' | 'employe_reprise' | 'statut' | 'statut_controle' | 'avancement' | 'commentaires'
    | 'commentaires_controle' | 'commentaires_reprise' | 'nb_reprises'>
> & {
  notes_saisies?: Record<string, string | null>
  /** Valeurs vues avant la modification (détection des conflits) : { avancement: 40, note_12: '3.5' } */
  attendu?: Record<string, unknown>
}

/** Lignes d'une feuille : toujours lister avec { feuille: id } */
const lignes = creerRessource<LigneFeuille, SaisieLigne>('/gsheets/lignes/')
export const lignesFeuilleApi = {
  ...lignes,
  /** Suivi en direct : signale la case en cours de modification, renvoie les changements depuis « depuis » */
  suivi: async (feuille: Identifiant, depuis: string | null, edition: { ligne: Identifiant; champ: string } | null): Promise<SuiviFeuille> =>
    (await apiClient.post('/gsheets/lignes/suivi/', { feuille, depuis, edition })).data,
}

/** Historique des modifications : lister avec { feuille: id } (et éventuellement { ligne: id }) */
export const historiqueFeuilleApi = creerRessource<ModificationLigne>('/gsheets/historique/')

// Paramètres > Temps Estimatif
export interface ParametresTempsEstimatif {
  unite: 'heures' | 'jours'
  /** Marge avant le rouge, en % : orange dès (100 − marge) % du Temps Estimatif */
  marge: number
  couleur_rouge: string
  couleur_orange: string
  /** Lecture seule (Paramètres > Rendement & Note) */
  heures_par_jour?: number
}
export const tempsEstimatifApi = {
  lire: async (): Promise<ParametresTempsEstimatif> => (await apiClient.get('/gsheets/temps-estimatif/')).data,
  enregistrer: async (d: ParametresTempsEstimatif): Promise<ParametresTempsEstimatif> => (await apiClient.put('/gsheets/temps-estimatif/', d)).data,
}

/** « Import ancienne donnée » : colonnes des anciens fichiers, crée projets / communes et descriptions (?feuille=) */
export const ancienneDonneeApi = creerRessource<{ id: Identifiant }>('/gsheets/import-ancien/')

/** Responsables et membres de chaque affaire d'une feuille (bouton « œil » de Mes feuilles) */
export interface EquipeAffaire {
  id: Identifiant
  num_affaire: string
  nom: string
  responsables: EmployeResume[]
  membres: EmployeResume[]
}
export const equipeFeuilleApi = async (id: Identifiant): Promise<EquipeAffaire[]> => (await apiClient.get(`/gsheets/feuilles/${id}/equipe/`)).data

/** Profil : lignes où je suis « Employé », par affaire et prestation, et moyennes des notes */
export interface ResumeProfil {
  nb_lignes: number
  note_rendement: number | null
  note_qualite: number | null
  nb_notes_rendement: number
  nb_notes_qualite: number
  groupes: { affaire: string; prestation: string; unite: string; nb_lignes: number; quantite: number
    note_rendement: number | null; note_qualite: number | null; nb_notes_rendement: number; nb_notes_qualite: number }[]
}
export const monResumeApi = async (): Promise<ResumeProfil> => (await apiClient.get('/gsheets/mon-resume/')).data

/** Statuts proposés dans les feuilles (lecture pour tous ; le catalogue se gère dans Marchés > Statuts) */
export const statutsFeuilleApi = async (): Promise<{ id: Identifiant; nom: string; couleur: string }[]> =>
  (await apiClient.get('/gsheets/statuts/')).data
