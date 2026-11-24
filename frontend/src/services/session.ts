// src/services/session.ts
/**
 * Gestion du jeton de connexion Keycloak
 * (flux « Authorization Code », avec PKCE quand le navigateur le permet).
 *
 * Le reste de l'application n'appelle que :
 *   demarrerSession()  au démarrage (main.ts)
 *   obtenirJeton()     avant chaque requête (api/client.ts)
 *   forcerRenouvellement()  après un refus 401 (api/client.ts)
 *   deconnecter()
 *
 * Les jetons Keycloak sont gardés en sessionStorage : ils disparaissent à la fermeture de l'onglet.
 */
import { ENV } from '@/config/environnement'

const STOCKAGE = sessionStorage
const CLES = {
  acces: 'ika_jeton_acces',
  rafraichissement: 'ika_jeton_rafraichissement',
  identite: 'ika_jeton_identite',
  verificateur: 'ika_pkce',
  etat: 'ika_etat',
  retour: 'ika_retour',
}
const MARGE_SECONDES = 30

let renouvellementEnCours: Promise<boolean> | null = null

// ------------------------------------------------------------------
// Outils
// ------------------------------------------------------------------
const urlKeycloak = (chemin: string) =>
  `${ENV.keycloak.url}/realms/${ENV.keycloak.realm}/protocol/openid-connect/${chemin}`

const urlRetour = () => `${window.location.origin}/`

/** Lit le contenu d'un JWT (sans le vérifier : c'est le rôle du backend). */
export function lireJeton(jeton?: string | null): Record<string, any> | null {
  try {
    const partie = jeton?.split('.')[1]
    if (!partie) return null
    const base64 = partie.replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
        .join(''),
    )
    return JSON.parse(json)
  } catch {
    return null
  }
}

const secondesRestantes = (jeton?: string | null) => {
  const exp = lireJeton(jeton)?.exp
  return exp ? exp - Math.floor(Date.now() / 1000) : -1
}

const estValide = (jeton?: string | null) => secondesRestantes(jeton) > MARGE_SECONDES

const aleatoire = (taille = 32) => {
  const octets = crypto.getRandomValues(new Uint8Array(taille))
  return Array.from(octets, (o) => o.toString(16).padStart(2, '0')).join('')
}

async function defiPkce(verificateur: string): Promise<string | null> {
  if (!window.crypto?.subtle) return null // site en http hors localhost : PKCE indisponible
  const empreinte = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verificateur))
  return btoa(String.fromCharCode(...new Uint8Array(empreinte)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

function enregistrerJetons(donnees: { access_token: string; refresh_token?: string; id_token?: string }) {
  STOCKAGE.setItem(CLES.acces, donnees.access_token)
  if (donnees.refresh_token) STOCKAGE.setItem(CLES.rafraichissement, donnees.refresh_token)
  if (donnees.id_token) STOCKAGE.setItem(CLES.identite, donnees.id_token)
}

function effacerJetons() {
  Object.values(CLES).forEach((cle) => STOCKAGE.removeItem(cle))
}

async function demanderJetons(parametres: Record<string, string>) {
  const reponse = await fetch(urlKeycloak('token'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_id: ENV.keycloak.clientId, ...parametres }).toString(),
  })
  const donnees = await reponse.json().catch(() => ({}))
  return { ok: reponse.ok && !!donnees.access_token, donnees }
}

// ------------------------------------------------------------------
// Keycloak
// ------------------------------------------------------------------
async function redirigerVersKeycloak(): Promise<never> {
  if (!ENV.keycloak.url || !ENV.keycloak.realm || !ENV.keycloak.clientId) {
    throw new Error('Keycloak n’est pas configuré (VITE_KEYCLOAK_BASE_URL, VITE_KEYCLOAK_REALM, VITE_KEYCLOAK_CLIENT_ID).')
  }
  const etat = aleatoire(16)
  const verificateur = aleatoire(48)
  const defi = await defiPkce(verificateur)
  STOCKAGE.setItem(CLES.etat, etat)
  STOCKAGE.setItem(CLES.retour, window.location.pathname + window.location.search + window.location.hash)
  if (defi) STOCKAGE.setItem(CLES.verificateur, verificateur)

  const parametres = new URLSearchParams({
    client_id: ENV.keycloak.clientId,
    redirect_uri: urlRetour(),
    response_type: 'code',
    scope: 'openid profile email',
    state: etat,
    ...(defi ? { code_challenge: defi, code_challenge_method: 'S256' } : {}),
  })
  window.location.assign(`${urlKeycloak('auth')}?${parametres}`)
  return new Promise<never>(() => {}) // la page change : on n'ira pas plus loin
}

/** Retour de Keycloak : ?code=...&state=... dans l'URL. Renvoie le chemin à rouvrir. */
async function traiterRetourKeycloak(): Promise<string | null> {
  const parametres = new URLSearchParams(window.location.search)
  const code = parametres.get('code')
  if (!code) return null

  const etatAttendu = STOCKAGE.getItem(CLES.etat)
  const retour = STOCKAGE.getItem(CLES.retour) || '/'
  const verificateur = STOCKAGE.getItem(CLES.verificateur)
  STOCKAGE.removeItem(CLES.etat)
  STOCKAGE.removeItem(CLES.verificateur)
  window.history.replaceState({}, document.title, '/')

  if (!etatAttendu || parametres.get('state') !== etatAttendu) return null // réponse non sollicitée

  const { ok, donnees } = await demanderJetons({
    grant_type: 'authorization_code',
    code,
    redirect_uri: urlRetour(),
    ...(verificateur ? { code_verifier: verificateur } : {}),
  })
  if (!ok) return null
  enregistrerJetons(donnees)
  return retour
}

function renouveler(): Promise<boolean> {
  if (renouvellementEnCours) return renouvellementEnCours
  renouvellementEnCours = (async () => {
    const rafraichissement = STOCKAGE.getItem(CLES.rafraichissement)
    if (!rafraichissement) return false
    try {
      const { ok, donnees } = await demanderJetons({ grant_type: 'refresh_token', refresh_token: rafraichissement })
      if (ok) {
        enregistrerJetons(donnees)
        return true
      }
      if (donnees.error === 'invalid_grant') effacerJetons() // session Keycloak terminée
      return false
    } catch {
      return false // réseau indisponible : on réessaiera à la prochaine requête
    } finally {
      renouvellementEnCours = null
    }
  })()
  return renouvellementEnCours
}

// ------------------------------------------------------------------
// API publique
// ------------------------------------------------------------------

/**
 * À appeler une fois au démarrage. Résout quand un jeton est disponible
 * (sinon redirige vers Keycloak). Renvoie le chemin à ouvrir après un retour de Keycloak.
 */
export async function demarrerSession(): Promise<string | null> {
  const retour = await traiterRetourKeycloak()
  if (retour) return retour
  if (await obtenirJeton()) return null
  return redirigerVersKeycloak()
}

/** Jeton valide à envoyer au backend (renouvelé si besoin), ou null. */
export async function obtenirJeton(): Promise<string | null> {
  const acces = STOCKAGE.getItem(CLES.acces)
  if (estValide(acces)) return acces
  if (await renouveler()) return STOCKAGE.getItem(CLES.acces)
  return null
}

/** Après un refus 401 : tente d'obtenir un nouveau jeton. Faux = il faut se reconnecter. */
export async function forcerRenouvellement(): Promise<boolean> {
  return renouveler()
}

export function reconnecter() {
  effacerJetons()
  return redirigerVersKeycloak()
}

export function deconnecter() {
  const identite = STOCKAGE.getItem(CLES.identite)
  effacerJetons()
  if (!ENV.keycloak.url) {
    window.location.assign('/')
    return
  }
  const parametres = new URLSearchParams({
    client_id: ENV.keycloak.clientId,
    post_logout_redirect_uri: urlRetour(),
    ...(identite ? { id_token_hint: identite } : {}),
  })
  window.location.assign(`${urlKeycloak('logout')}?${parametres}`)
}
