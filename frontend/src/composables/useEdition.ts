// src/composables/useEdition.ts
/**
 * Création / modification / suppression d'un élément, avec messages et confirmation.
 * À combiner avec <FormulaireModale> :
 *
 *   const edition = useEdition(tachesApi, { nom: 'tâche', feminin: true }, () => tableau.value?.recharger())
 *   <FormulaireModale v-model="edition.ouvert.value" :titre="edition.titre.value"
 *                     :valeurs-initiales="edition.valeursInitiales.value" :enregistrer="edition.enregistrer" ... />
 *   edition.ouvrir()            // création
 *   edition.ouvrir(ligne)       // modification
 *   edition.supprimer(ligne)    // avec confirmation
 */
import { computed, ref, shallowRef } from 'vue'
import type { Identifiant } from '@/types'
import { useConfirmation } from './useConfirmation'
import { useToast } from './useToast'

interface Source<T> {
  creer: (d: any) => Promise<T>
  modifier: (id: Identifiant, d: any) => Promise<T>
  supprimer: (id: Identifiant) => Promise<void>
}

export interface OptionsEdition<T> {
  /** Nom de l'élément, ex. « affaire » */
  nom: string
  feminin?: boolean
  /** Verbe de la suppression (« supprimer » par défaut, « archiver »…) */
  verbeSupprimer?: string
  /** Valeurs ajoutées à chaque création (ex. l'affaire et la prestation choisies) */
  valeursCreation?: () => Record<string, unknown>
  /** Explication affichée dans la confirmation de suppression */
  messageSuppression?: string
  /** Prépare les valeurs du formulaire à partir d'une ligne (modification) */
  preparer?: (ligne: T) => Record<string, unknown>
}

export function useEdition<T extends { id: Identifiant }>(source: Source<T>, options: OptionsEdition<T>, apres: () => void) {
  const toast = useToast()
  const { confirmer } = useConfirmation()
  const ouvert = ref(false)
  const enCours = shallowRef<T | null>(null)

  const nom = options.nom
  const e = options.feminin ? 'e' : ''
  const verbe = options.verbeSupprimer ?? 'supprimer'
  const majuscule = (t: string) => t.charAt(0).toUpperCase() + t.slice(1)

  const titre = computed(() =>
    enCours.value ? `Modifier ${options.feminin ? 'la' : 'le'} ${nom}` : `Nouve${options.feminin ? 'lle' : 'au'} ${nom}`,
  )
  const valeursInitiales = computed(() =>
    enCours.value ? (options.preparer ? { ...enCours.value, ...options.preparer(enCours.value) } : enCours.value) : null,
  )

  function ouvrir(ligne: T | null = null) {
    enCours.value = ligne
    ouvert.value = true
  }

  async function enregistrer(valeurs: Record<string, unknown>) {
    const resultat = enCours.value
      ? await source.modifier(enCours.value.id, valeurs)
      : await source.creer({ ...valeurs, ...(options.valeursCreation?.() ?? {}) })
    toast.succes(`${majuscule(nom)} enregistré${e}`)
    apres()
    return resultat
  }

  async function supprimer(ligne: T, libelle?: string) {
    const ok = await confirmer({
      titre: `${majuscule(verbe)} ${libelle ? `« ${libelle} »` : `cet${options.feminin ? 'te' : ''} ${nom}`} ?`,
      message: options.messageSuppression,
      libelleConfirmer: majuscule(verbe),
      danger: true,
    })
    if (!ok) return
    try {
      await source.supprimer(ligne.id)
      toast.succes(`${majuscule(nom)} ${verbe === 'archiver' ? 'archivé' : 'supprimé'}${e}`)
      apres()
    } catch (err) {
      toast.erreur(err)
    }
  }

  return { ouvert, enCours, titre, valeursInitiales, ouvrir, enregistrer, supprimer }
}
