// src/composables/useColonnes.ts
// Colonnes affichées d'un tableau, mémorisées dans le navigateur (bouton « Colonnes »).
import { computed, ref, watch } from 'vue'
import type { Colonne } from '@/types'

export function useColonnes(cleStockage: string, colonnes: () => Colonne[]) {
  const cle = `ika_colonnes_${cleStockage}`
  const lire = (): string[] | null => {
    try {
      return JSON.parse(localStorage.getItem(cle) || 'null')
    } catch {
      return null
    }
  }
  const masquees = ref<string[]>(lire() ?? colonnes().filter((c) => c.masqueeParDefaut).map((c) => c.cle))
  watch(masquees, (valeur) => localStorage.setItem(cle, JSON.stringify(valeur)), { deep: true })

  const visibles = computed(() => colonnes().filter((c) => !masquees.value.includes(c.cle)))

  function basculer(cleColonne: string) {
    if (masquees.value.includes(cleColonne)) masquees.value = masquees.value.filter((c) => c !== cleColonne)
    else if (visibles.value.length > 1) masquees.value = [...masquees.value, cleColonne] // au moins une colonne
  }

  const reinitialiser = () => (masquees.value = colonnes().filter((c) => c.masqueeParDefaut).map((c) => c.cle))

  return { masquees, visibles, basculer, reinitialiser }
}
