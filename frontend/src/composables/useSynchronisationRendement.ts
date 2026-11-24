// src/composables/useSynchronisationRendement.ts
// Branche une page du Rendement sur la « Synchronisation des données » (store selectionRendement),
// activée pour tout le monde dans Paramètres > Graphiques.
import { reactive, watch } from 'vue'
import { useSelectionRendement } from '@/store/selectionRendement'

/**
 * choix : l'objet réactif des filtres de la page (avec affaires et prestations).
 * Renvoie les recherches des listes Affaires / Prestations (à passer en v-model:recherche) et l'action du bouton.
 */
export function useSynchronisationRendement(choix: { affaires: number[]; prestations: number[] }) {
  const store = useSelectionRendement()
  const recherches = reactive({ affaires: '', prestations: '' })

  // À l'ouverture de la page : reprendre la sélection commune
  if (store.actif) {
    choix.affaires = [...store.affaires]
    choix.prestations = [...store.prestations]
    recherches.affaires = store.rechercheAffaires
    recherches.prestations = store.recherchePrestations
  }

  // Page -> sélection commune (seulement quand la synchronisation est active)
  watch(() => [choix.affaires, choix.prestations, recherches.affaires, recherches.prestations], () => {
    if (!store.actif) return
    store.affaires = [...choix.affaires]
    store.prestations = [...choix.prestations]
    store.rechercheAffaires = recherches.affaires
    store.recherchePrestations = recherches.prestations
  }, { deep: true })

  // Le réglage (Paramètres > Graphiques) arrive après l'ouverture de la page : reprendre alors la sélection commune
  watch(() => store.actif, (actif) => {
    if (actif && (store.affaires.length || store.prestations.length)) {
      choix.affaires = [...store.affaires]
      choix.prestations = [...store.prestations]
      recherches.affaires = store.rechercheAffaires
      recherches.prestations = store.recherchePrestations
    }
  })

  return { store, recherches }
}
