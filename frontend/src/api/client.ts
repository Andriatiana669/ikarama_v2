// src/api/client.ts
/**
 * Client HTTP UNIQUE de l'application. Tous les appels au backend passent par ici.
 *
 *  - ajoute le jeton (Authorization: Bearer ...) à chaque requête ;
 *  - après un refus 401, renouvelle le jeton et rejoue la requête une fois ;
 *  - transforme toute erreur en ApiErreur avec un message lisible (champ « detail » de Django).
 *
 * Ne pas utiliser axios directement ailleurs : passer par les fichiers src/api/*.ts.
 */
import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
import { ENV } from '@/config/environnement'
import { forcerRenouvellement, obtenirJeton, reconnecter } from '@/services/session'

export class ApiErreur extends Error {
  statut: number | null
  /** Erreurs par champ : { code: ["Ce code existe déjà."] } */
  erreurs: Record<string, string[] | string>
  /** Code machine renvoyé par Django (ex. « acces_refuse », « perte_acces ») */
  code: string | null

  constructor(
    message: string,
    statut: number | null = null,
    erreurs: Record<string, string[] | string> = {},
    code: string | null = null,
  ) {
    super(message)
    this.name = 'ApiErreur'
    this.statut = statut
    this.erreurs = erreurs
    this.code = code
  }
}

const MESSAGES_PAR_STATUT: Record<number, string> = {
  400: 'Les informations envoyées sont incomplètes ou invalides.',
  401: 'Votre session a expiré. Reconnexion en cours…',
  403: "Vous n'avez pas l'autorisation d'effectuer cette action.",
  404: "L'élément demandé est introuvable.",
  413: 'Le fichier envoyé est trop volumineux.',
  500: 'Le serveur a rencontré une erreur. Réessayez dans un instant.',
  502: 'Un service externe ne répond pas. Réessayez dans un instant.',
  503: 'Le serveur est momentanément indisponible.',
}

function versApiErreur(erreur: unknown): ApiErreur {
  if (erreur instanceof ApiErreur) return erreur
  const e = erreur as AxiosError<any>
  if (!e.response) return new ApiErreur('Le serveur est injoignable. Vérifiez votre connexion réseau.')
  const { status, data } = e.response
  const message = (typeof data?.detail === 'string' && data.detail) || MESSAGES_PAR_STATUT[status] || 'Erreur inattendue.'
  const erreurs = data?.erreurs && typeof data.erreurs === 'object' ? data.erreurs : {}
  return new ApiErreur(message, status, erreurs, typeof data?.code === 'string' ? data.code : null)
}

export const apiClient = axios.create({
  baseURL: ENV.apiUrl,
  headers: { Accept: 'application/json' },
  timeout: 60_000,
})

apiClient.interceptors.request.use(async (config) => {
  const jeton = await obtenirJeton()
  if (jeton) config.headers.Authorization = `Bearer ${jeton}`
  return config
})

apiClient.interceptors.response.use(undefined, async (erreur: AxiosError) => {
  const requete = erreur.config as (AxiosRequestConfig & { _rejouee?: boolean }) | undefined
  if (erreur.response?.status === 401 && requete && !requete._rejouee) {
    requete._rejouee = true
    if (await forcerRenouvellement()) return apiClient(requete)
    await reconnecter()
  }
  const apiErreur = versApiErreur(erreur)
  // Accès au site retiré pendant la session : on affiche la page dédiée
  if (apiErreur.code === 'acces_refuse' && window.location.pathname !== '/acces-refuse') {
    window.location.replace('/acces-refuse')
  }
  return Promise.reject(apiErreur)
})

/** Message à afficher pour n'importe quelle erreur (réseau, API, code). */
export const messageErreur = (erreur: unknown) =>
  erreur instanceof ApiErreur ? erreur.message : erreur instanceof Error ? erreur.message : 'Erreur inattendue.'

export default apiClient
