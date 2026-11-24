// src/composables/useConfirmation.ts
/**
 * Boîte de confirmation, utilisable comme un simple `await` :
 *
 *   if (await confirmer({ titre: 'Désactiver cette équipe ?', libelleConfirmer: 'Désactiver', danger: true })) { ... }
 */
import { reactive } from 'vue'

export interface OptionsConfirmation {
  titre: string
  message?: string
  libelleConfirmer?: string
  libelleAnnuler?: string
  danger?: boolean
}

const etat = reactive({
  ouverte: false,
  options: { titre: '' } as OptionsConfirmation,
  resoudre: null as ((reponse: boolean) => void) | null,
})

export function useConfirmation() {
  function confirmer(options: OptionsConfirmation): Promise<boolean> {
    etat.options = options
    etat.ouverte = true
    return new Promise((resolve) => (etat.resoudre = resolve))
  }

  function repondre(reponse: boolean) {
    etat.ouverte = false
    etat.resoudre?.(reponse)
    etat.resoudre = null
  }

  return { etat, confirmer, repondre }
}
