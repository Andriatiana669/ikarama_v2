// src/api/auth.ts
import apiClient from './client'
import type { UtilisateurConnecte } from '@/types'

export const authApi = {
  /** Utilisateur connecté, sa fiche employé et ses autorisations */
  moi: async (): Promise<UtilisateurConnecte> => (await apiClient.get('/auth/moi/')).data,
  /** Ticket d'entrée automatique dans /admin/ (valable 60 s, une seule fois) */
  ouvrirSessionAdmin: async (): Promise<{ url: string }> => (await apiClient.post('/auth/session-admin/')).data,
}
