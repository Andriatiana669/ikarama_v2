// src/composables/useTempsReel.ts
/**
 * Connexion temps réel (WebSocket /ws/), UNIQUE pour tout l'onglet du navigateur.
 *  - authentification par le premier message (le jeton n'apparaît jamais dans l'adresse) ;
 *  - reconnexion automatique (2 s, 4 s… jusqu'à 30 s) ;
 *  - les pages s'abonnent aux événements : « feuille », « presence », « notification », « planning ».
 * Les événements sont de simples signaux : la page relit ce qui a changé par l'API.
 * Si le WebSocket ne passe pas, `connecte` reste faux et les pages continuent d'interroger l'API comme avant.
 */
import { ref } from 'vue'
import { ENV } from '@/config/environnement'
import { obtenirJeton } from '@/services/session'
import type { Identifiant } from '@/types'

type Evenement = { type: string; feuille?: Identifiant; message?: string }
type Ecouteur = (e: Evenement) => void

const connecte = ref(false)
let socket: WebSocket | null = null
let delai = 2000
let demarre = false
let feuilleSuivie: Identifiant | null = null
let planningSuivi = false
const ecouteurs = new Map<string, Set<Ecouteur>>()

/** Adresse du WebSocket : VITE_WS_URL, sinon celle du serveur (http -> ws, https -> wss) */
function adresse() {
  const configuree = (import.meta.env.VITE_WS_URL as string | undefined)?.replace(/\/+$/, '')
  if (configuree) return `${configuree}/ws/`
  const base = ENV.backendUrl || window.location.origin
  return `${base.replace(/^http/, 'ws')}/ws/`
}

function envoyer(message: Record<string, unknown>) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message))
}

async function ouvrir() {
  if (socket && socket.readyState <= WebSocket.OPEN) return
  let ws: WebSocket
  try {
    ws = new WebSocket(adresse())
  } catch {
    planifier()
    return
  }
  socket = ws
  ws.onopen = async () => {
    const jeton = await obtenirJeton()
    if (!jeton) return ws.close()
    envoyer({ type: 'authentifier', jeton })
  }
  ws.onmessage = (message) => {
    let evenement: Evenement
    try {
      evenement = JSON.parse(message.data)
    } catch {
      return
    }
    if (evenement.type === 'pret') {
      connecte.value = true
      delai = 2000
      if (feuilleSuivie !== null) envoyer({ type: 'suivre_feuille', feuille: feuilleSuivie })
      if (planningSuivi) envoyer({ type: 'suivre_planning' })
    }
    ecouteurs.get(evenement.type)?.forEach((f) => f(evenement))
  }
  ws.onclose = () => {
    connecte.value = false
    if (socket === ws) socket = null
    planifier()
  }
  ws.onerror = () => ws.close()
}

function planifier() {
  if (!demarre) return
  window.setTimeout(ouvrir, delai)
  delai = Math.min(delai * 2, 30_000)
}

export function useTempsReel() {
  return {
    connecte,
    /** À appeler une fois l'utilisateur connecté (mise en page de l'application) */
    demarrer() {
      if (demarre) return
      demarre = true
      ouvrir()
    },
    arreter() {
      demarre = false
      socket?.close()
    },
    /** S'abonne à un type d'événement ; renvoie la fonction de désabonnement */
    ecouter(type: string, fonction: Ecouteur) {
      if (!ecouteurs.has(type)) ecouteurs.set(type, new Set())
      ecouteurs.get(type)!.add(fonction)
      return () => ecouteurs.get(type)?.delete(fonction)
    },
    suivreFeuille(id: Identifiant) {
      feuilleSuivie = id
      envoyer({ type: 'suivre_feuille', feuille: id })
    },
    quitterFeuille() {
      feuilleSuivie = null
      envoyer({ type: 'quitter_feuille' })
    },
    /** Planning Projet : être prévenu de chaque changement (planification, pointage, statut d'une ligne) */
    suivrePlanning() {
      planningSuivi = true
      envoyer({ type: 'suivre_planning' })
    },
    quitterPlanning() {
      planningSuivi = false
      envoyer({ type: 'quitter_planning' })
    },
  }
}
