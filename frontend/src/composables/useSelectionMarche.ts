// src/composables/useSelectionMarche.ts
/**
 * Sélection en cascade du Marché, gardée dans l'adresse de la page :
 *   ?affaire=<id>&prestation=<id>&projet=<id>
 * Choisir un niveau remet à zéro les niveaux en dessous.
 * Utilisé par les pages « Ajouter un marché » et « Mes marchés ».
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { affairesApi, prestationsApi, projetsApi } from '@/api'
import type { Affaire, Identifiant, Prestation, Projet } from '@/types'

export function useSelectionMarche() {
  const route = useRoute()
  const router = useRouter()

  const lireId = (cle: string): Identifiant | null => {
    const valeur = Number(route.query[cle])
    return Number.isInteger(valeur) && valeur > 0 ? valeur : null
  }
  const ecrire = (modifs: Record<string, Identifiant | null>) =>
    router.replace({
      query: Object.fromEntries(
        Object.entries({ ...route.query, ...modifs }).filter(([, v]) => v !== null && v !== undefined && v !== ''),
      ) as Record<string, string>,
    })

  const affaireId = computed({
    get: () => lireId('affaire'),
    set: (id: Identifiant | null | undefined) => ecrire({ affaire: id ?? null, prestation: null, projet: null }),
  })
  const prestationId = computed({
    get: () => lireId('prestation'),
    set: (id: Identifiant | null | undefined) => ecrire({ prestation: id ?? null, projet: null }),
  })
  const projetId = computed({
    get: () => lireId('projet'),
    set: (id: Identifiant | null | undefined) => ecrire({ projet: id ?? null }),
  })

  /** Tâche dont le temps est affiché à côté du Temps total (?tache=) */
  const tacheId = computed({
    get: () => lireId('tache'),
    set: (id: Identifiant | null | undefined) => ecrire({ tache: id ?? null }),
  })

  const affaire = ref<Affaire | null>(null)
  const prestation = ref<Prestation | null>(null)
  const projet = ref<Projet | null>(null)

  async function chargerAffaire() {
    affaire.value = affaireId.value ? await affairesApi.lire(affaireId.value).catch(() => null) : null
  }
  async function chargerPrestation() {
    const p =
      prestationId.value && affaireId.value
        ? await prestationsApi.lire(prestationId.value, { affaire: affaireId.value }).catch(() => null)
        : null
    prestation.value = p?.cochee ? p : null
  }
  async function chargerProjet() {
    projet.value = projetId.value ? await projetsApi.lire(projetId.value).catch(() => null) : null
  }
  watch(affaireId, chargerAffaire, { immediate: true })
  watch([affaireId, prestationId], chargerPrestation, { immediate: true })
  watch(projetId, chargerProjet, { immediate: true })

  return { affaireId, prestationId, projetId, tacheId, affaire, prestation, projet, chargerAffaire, chargerPrestation, chargerProjet }
}
