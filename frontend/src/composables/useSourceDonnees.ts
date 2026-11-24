// src/composables/useSourceDonnees.ts
// Source des données des onglets du Rendement (état commun, store selectionRendement) :
//   ''          normale : pointages + feuilles
//   'feuilles'  données des feuilles (anciennes données sans pointage)        si Paramètres > Graphiques l'autorise
//   'pointages' données des pointages (affaires pointées sans feuille)         si Paramètres > Graphiques l'autorise
import { computed } from 'vue'
import { parametresGraphiquesApi } from '@/api'
import { useSelectionRendement } from '@/store/selectionRendement'

export function useSourceDonnees() {
  const store = useSelectionRendement()
  if (store.sourcesAutorisees === null) {
    parametresGraphiquesApi.lire()
      .then((p) => {
        store.sourcesAutorisees = { feuilles: p.donnees_feuilles, pointages: !!p.donnees_pointages }
        store.actif = !!p.synchronisation   // Synchronisation des données : réglée dans Paramètres > Graphiques
      })
      .catch(() => (store.sourcesAutorisees = { feuilles: false, pointages: false }))
  }
  const autorisees = computed(() => store.sourcesAutorisees ?? { feuilles: false, pointages: false })
  /** Au moins une autre source que la normale est proposée */
  const autorise = computed(() => autorisees.value.feuilles || autorisees.value.pointages)
  /** Source effective (une source retirée dans les paramètres revient à la normale) */
  const valeur = computed<'' | 'feuilles' | 'pointages'>(() => (store.source && autorisees.value[store.source] ? store.source : ''))
  const choisir = (v: '' | 'feuilles' | 'pointages') => (store.source = v)
  return { autorise, autorisees, valeur, choisir }
}
