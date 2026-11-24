// src/store/selectionRendement.ts
// « Synchronisation des données » du Rendement : quand elle est activée, les Affaires et Prestations cochées
// (et le texte de leurs recherches) sont partagées entre Globale, Evolution, Réel vs Objectif et Evaluation Employé.
// Gardé dans le navigateur (localStorage) : la sélection reste après un rechargement.
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const CLE = 'ikarama.rendement.synchronisation'

interface Etat {
  /** Source des données des onglets du Rendement (état commun) : '' normale, 'feuilles', 'pointages' */
  source: '' | 'feuilles' | 'pointages'
  /** Ancien réglage (avant le choix des trois sources) */
  sourceFeuilles?: boolean
  actif: boolean
  affaires: number[]
  prestations: number[]
  rechercheAffaires: string
  recherchePrestations: string
}

function lire(): Etat {
  const vide: Etat = { source: '', actif: false, affaires: [], prestations: [], rechercheAffaires: '', recherchePrestations: '' }
  try {
    const lu = { ...vide, ...JSON.parse(localStorage.getItem(CLE) || '{}') }
    if (!lu.source && lu.sourceFeuilles) lu.source = 'feuilles'   // reprise de l'ancien bouton
    return lu
  } catch {
    return vide
  }
}

export const useSelectionRendement = defineStore('selectionRendement', () => {
  const depart = lire()
  const actif = ref(depart.actif)
  const source = ref<Etat['source']>(depart.source)
  /** Sources autorisées dans Paramètres > Graphiques (lues une fois) */
  const sourcesAutorisees = ref<{ feuilles: boolean; pointages: boolean } | null>(null)
  const affaires = ref<number[]>(depart.affaires)
  const prestations = ref<number[]>(depart.prestations)
  const rechercheAffaires = ref(depart.rechercheAffaires)
  const recherchePrestations = ref(depart.recherchePrestations)

  watch([actif, source, affaires, prestations, rechercheAffaires, recherchePrestations], () => {
    try {
      localStorage.setItem(CLE, JSON.stringify({
        actif: actif.value, source: source.value, affaires: affaires.value, prestations: prestations.value,
        rechercheAffaires: rechercheAffaires.value, recherchePrestations: recherchePrestations.value,
      }))
    } catch {
      // stockage indisponible : la synchronisation vaut seulement pour la session
    }
  }, { deep: true })

  return { actif, source, sourcesAutorisees, affaires, prestations, rechercheAffaires, recherchePrestations }
})
