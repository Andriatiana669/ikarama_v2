// src/composables/useSuiviFeuille.ts
/**
 * Suivi en direct d'une feuille :
 *  - envoie la case que je suis en train de modifier (les autres me voient) ;
 *  - reçoit les lignes modifiées par les autres et qui modifie quoi.
 * Avec le temps réel (WebSocket), la page relit AUSSITÔT qu'un changement est signalé, et n'interroge
 * plus que toutes les 15 s (pour renouveler ma présence) ; sans lui, elle interroge toutes les 4 s comme avant.
 * Le suivi se met en pause quand l'onglet du navigateur est caché.
 */
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useTempsReel } from '@/composables/useTempsReel'
import { useDocumentVisibility } from '@vueuse/core'
import { lignesFeuilleApi } from '@/api'
import type { Identifiant, LigneFeuille, PresenceFeuille } from '@/types'

const INTERVALLE_MS = 4000          // sans temps réel
const INTERVALLE_TEMPS_REEL_MS = 15_000   // avec temps réel : seulement pour renouveler ma présence

export function useSuiviFeuille(
  feuilleId: () => Identifiant,
  options: { surLignes: (lignes: LigneFeuille[]) => void; surRechargement: () => void },
) {
  const presences = shallowRef<PresenceFeuille[]>([])
  const edition = shallowRef<{ ligne: Identifiant; champ: string } | null>(null)
  const nbLignes = ref<number | null>(null)
  const derniereMaj = ref<Date | null>(null)
  const horsLigne = ref(false)
  const visibilite = useDocumentVisibility()
  let depuis: string | null = null
  let minuteur: number | undefined
  let enCours = false

  async function interroger() {
    if (enCours || visibilite.value === 'hidden') return
    enCours = true
    try {
      const r = await lignesFeuilleApi.suivi(feuilleId(), depuis, edition.value)
      if (r.recharger) options.surRechargement()
      else if (r.lignes.length) options.surLignes(r.lignes)
      depuis = r.maintenant
      presences.value = r.presences
      nbLignes.value = r.nb_lignes
      derniereMaj.value = new Date()
      horsLigne.value = false
    } catch {
      horsLigne.value = true // on réessaiera au prochain tour
    } finally {
      enCours = false
    }
  }

  /** Je commence (ou j'arrête) de modifier une case : prévenir les autres tout de suite */
  function signalerEdition(valeur: { ligne: Identifiant; champ: string } | null) {
    edition.value = valeur
    interroger()
  }

  /** La personne qui modifie cette case (autre que moi), s'il y en a une */
  const occupant = (ligne: Identifiant, champ: string) =>
    presences.value.find((p) => p.ligne === ligne && p.champ === champ)?.employe ?? null
  /** Les personnes qui modifient une case de cette ligne */
  const occupantsLigne = (ligne: Identifiant) => presences.value.filter((p) => p.ligne === ligne)

  // --- Temps réel : relire dès qu'un changement est signalé (regroupé sur 250 ms) ---
  const tempsReel = useTempsReel()
  let attente: number | undefined
  const relireBientot = (e: { feuille?: Identifiant }) => {
    if (e.feuille !== undefined && String(e.feuille) !== String(feuilleId())) return
    window.clearTimeout(attente)
    attente = window.setTimeout(interroger, 250)
  }
  const desabonnements = [tempsReel.ecouter('feuille', relireBientot), tempsReel.ecouter('presence', relireBientot)]
  function programmer() {
    window.clearInterval(minuteur)
    minuteur = window.setInterval(interroger, tempsReel.connecte.value ? INTERVALLE_TEMPS_REEL_MS : INTERVALLE_MS)
  }
  watch(tempsReel.connecte, (oui) => {
    programmer()
    if (oui) interroger()   // reconnecté : rattraper ce qui a pu changer
  })

  onMounted(() => {
    interroger()
    tempsReel.suivreFeuille(feuilleId())
    programmer()
  })
  onBeforeUnmount(() => {
    window.clearInterval(minuteur)
    window.clearTimeout(attente)
    desabonnements.forEach((d) => d())
    tempsReel.quitterFeuille()
    // Libère ma présence en partant
    lignesFeuilleApi.suivi(feuilleId(), null, null).catch(() => {})
  })

  return { presences, nbLignes, derniereMaj, horsLigne, signalerEdition, occupant, occupantsLigne, interroger, tempsReel: tempsReel.connecte }
}
