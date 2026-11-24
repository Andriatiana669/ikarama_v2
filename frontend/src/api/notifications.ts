// src/api/notifications.ts
// Notifications (cloche), page d'accueil et Contrôles de cohérence.
import apiClient from './client'
import type { EmployeResume, Identifiant, Page } from '@/types'

export interface NotificationApp {
  id: Identifiant
  type: 'rappel_pointage' | 'temps_estimatif' | 'pointage_modifie' | 'import' | 'affaire'
  titre: string
  message: string
  /** Page de l'application à ouvrir */
  lien: string
  lu: boolean
  cree_le: string
}

export const notificationsApi = {
  lister: async (page = 1): Promise<Page<NotificationApp>> => (await apiClient.get('/notifications/', { params: { page, page_size: 15 } })).data,
  compte: async (): Promise<number> => (await apiClient.get('/notifications/compte/')).data.non_lues,
  lire: async (id: Identifiant): Promise<number> => (await apiClient.post(`/notifications/${id}/lire/`)).data.non_lues,
  toutLire: async (): Promise<number> => (await apiClient.post('/notifications/tout-lire/')).data.non_lues,
}

export interface LigneAlerte {
  alerte: 'rouge' | 'orange'
  feuille: string
  feuille_id: Identifiant
  numero: number
  description: string
  affaire: string
  employe: string | null
  temps_prod: number
}
interface Alertes { nombre: number; rouges: number; lignes: LigneAlerte[] }
interface ErreurPointage { date: string; type: 'INCOMPLET' | 'PAUSE'; message: string; minutes: number }

export interface Accueil {
  employe: EmployeResume | null
  date: string
  moi?: {
    /** Mon planning : les 7 prochains jours */
    planning: { date: string; ouvrable: boolean; projets: { projet: string; affaire: string; prestation: string }[] }[]
    semaine: { date: string; minutes: number; ouvrable: boolean; futur: boolean }[]
    minutes_aujourdhui: number
    minutes_semaine: number
    erreurs: ErreurPointage[]
    alertes: Alertes
  }
  /** Mon équipe : seulement avec le droit « Voir » de Pointages > Vérification (semaine en cours) */
  equipe?: {
    nb_equipe: number
    periode: { debut: string; fin: string }
    manques: { employe: EmployeResume; jours: number; manque_minutes: number; detail: string[] }[]
    nb_manques: number
  }
  responsable?: {
    nb_affaires: number
    alertes: Alertes
    feuilles: { id: Identifiant; nom: string; avancement: number; nb_lignes: number }[]
  }
  administrateur?: {
    controles: { code: string; titre: string; gravite: Gravite; nombre: number }[]
    total_controles: number
    activite: { date: string; auteur: string; feuille: string; feuille_id: Identifiant; ligne: number | null; libelle: string; nouvelle_valeur: string }[]
  }
}
export const accueilApi = async (): Promise<Accueil> => (await apiClient.get('/accueil/')).data

export type Gravite = 'erreur' | 'attention' | 'info'
export interface Controle {
  code: string
  titre: string
  explication: string
  gravite: Gravite
  nombre: number
  elements: { libelle: string; detail: string; lien: string }[]
}
export const controlesApi = async (): Promise<{ total: number; controles: Controle[] }> => (await apiClient.get('/controles/')).data
