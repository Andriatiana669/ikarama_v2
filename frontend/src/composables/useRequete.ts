// src/composables/useRequete.ts
/**
 * Exécute un appel API en gérant chargement et erreur.
 *
 *   const { donnees, chargement, erreur, executer } = useRequete(() => equipesApi.mesEquipes(), [])
 *   onMounted(executer)
 */
import { ref, shallowRef, type Ref } from 'vue'
import { messageErreur } from '@/api/client'

export function useRequete<T, A extends unknown[] = []>(fonction: (...args: A) => Promise<T>, valeurInitiale: T) {
  const donnees = shallowRef(valeurInitiale) as Ref<T>
  const chargement = ref(false)
  const erreur = ref<string | null>(null)

  async function executer(...args: A): Promise<T | undefined> {
    chargement.value = true
    erreur.value = null
    try {
      donnees.value = await fonction(...args)
      return donnees.value
    } catch (e) {
      erreur.value = messageErreur(e)
      return undefined
    } finally {
      chargement.value = false
    }
  }

  return { donnees, chargement, erreur, executer }
}
