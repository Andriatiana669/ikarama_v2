// src/composables/useListe.ts
/**
 * Liste paginée + recherche + filtres d'une ressource (api/ressource.ts).
 * Recharge automatiquement quand la recherche, un filtre ou la page change.
 *
 *   const liste = useListe(xxxApi, { filtres: { type: '' } })
 *   liste.recherche.value = 'saisie'      // relance la recherche
 *   liste.filtres.type = 'A'              // relance avec le filtre
 */
import { reactive, ref, shallowRef, watch, type Ref } from 'vue'
import { messageErreur } from '@/api/client'
import type { Parametres } from '@/api/ressource'
import type { Page } from '@/types'

interface SourceListe<T> {
  lister: (parametres?: Parametres) => Promise<Page<T>>
}

export function useListe<T>(
  source: SourceListe<T>,
  options: { filtres?: Parametres; taillePage?: number; tri?: string; immediat?: boolean } = {},
) {
  const lignes = shallowRef<T[]>([]) as Ref<T[]>
  const total = ref(0)
  const page = ref(1)
  const taillePage = ref(options.taillePage ?? 25)
  const recherche = ref('')
  const tri = ref(options.tri ?? '')
  const filtres = reactive<Parametres>({ ...(options.filtres ?? {}) })
  const chargement = ref(false)
  const erreur = ref<string | null>(null)
  let numeroAppel = 0

  async function charger() {
    const appel = ++numeroAppel // ignore les réponses d'une recherche dépassée
    chargement.value = true
    erreur.value = null
    try {
      const resultat = await source.lister({
        page: page.value,
        page_size: taillePage.value,
        search: recherche.value,
        ordering: tri.value,
        ...filtres,
      })
      if (appel !== numeroAppel) return
      lignes.value = resultat.results
      total.value = resultat.count
    } catch (e) {
      if (appel === numeroAppel) erreur.value = messageErreur(e)
    } finally {
      if (appel === numeroAppel) chargement.value = false
    }
  }

  watch([recherche, tri, () => ({ ...filtres })], () => {
    if (page.value !== 1) page.value = 1 // le watch de page relancera le chargement
    else charger()
  })
  watch([page, taillePage], charger)

  if (options.immediat !== false) charger()

  return { lignes, total, page, taillePage, recherche, tri, filtres, chargement, erreur, charger }
}
