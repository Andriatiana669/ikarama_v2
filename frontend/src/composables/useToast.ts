// src/composables/useToast.ts
/**
 * Messages éphémères en bas d'écran.
 *   const toast = useToast()
 *   toast.succes('Équipe enregistrée')
 *   toast.erreur(e)            // accepte directement une erreur API
 */
import { reactive } from 'vue'
import { messageErreur } from '@/api/client'

export type TonToast = 'succes' | 'erreur' | 'info'
export interface Toast {
  id: number
  ton: TonToast
  message: string
}

const etat = reactive({ toasts: [] as Toast[] })
let compteur = 0

function afficher(ton: TonToast, message: string, duree = ton === 'erreur' ? 7000 : 4000) {
  const id = ++compteur
  etat.toasts.push({ id, ton, message })
  window.setTimeout(() => fermer(id), duree)
}

function fermer(id: number) {
  const index = etat.toasts.findIndex((t) => t.id === id)
  if (index >= 0) etat.toasts.splice(index, 1)
}

export function useToast() {
  return {
    toasts: etat.toasts,
    fermer,
    succes: (message: string) => afficher('succes', message),
    info: (message: string) => afficher('info', message),
    erreur: (erreur: unknown) => afficher('erreur', typeof erreur === 'string' ? erreur : messageErreur(erreur)),
  }
}
