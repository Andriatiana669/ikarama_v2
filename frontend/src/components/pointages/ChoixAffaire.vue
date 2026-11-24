<!--
  Choix d'une de mes affaires (« Num affaire - Nom affaire »), avec recherche.
  Ordre : affaires où je suis placé (statut prioritaire d'abord), puis celles avec le statut prioritaire,
  celles présentes dans une feuille, puis toutes mes autres affaires.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { pointagesApi } from '@/api'
import type { AffairePointable, Identifiant } from '@/types'
import UiMenuDeroulant from '@/components/ui/UiMenuDeroulant.vue'

const modele = defineModel<Identifiant | null>({ default: null })
const props = defineProps<{
  libelleInitial?: string
  invalide?: boolean
  id?: string
  /** Affaires de cette personne (administrateur, page Suivi) ; par défaut les miennes */
  employe?: Identifiant | null
}>()

const ouvert = ref(false)
const ancre = ref<HTMLElement | null>(null)
const recherche = ref('')
const affaires = ref<AffairePointable[]>([])
const chargement = ref(false)
const libelle = ref(props.libelleInitial ?? '')
watch(() => props.libelleInitial, (l) => (libelle.value = l ?? ''))

const nomAffaire = (a: { num_affaire: string; nom: string }) => (a.num_affaire ? `${a.num_affaire} - ${a.nom}` : a.nom)

async function charger() {
  chargement.value = true
  try {
    affaires.value = (await pointagesApi.affaires(recherche.value, props.employe)).results
  } finally {
    chargement.value = false
  }
}
watch(ouvert, (o) => o && charger())
watchDebounced(recherche, charger, { debounce: 250 })

const groupes = computed(() => [
  { titre: 'Mes lignes dans les feuilles', liste: affaires.value.filter((a) => a.place) },
  { titre: 'Dans une feuille', liste: affaires.value.filter((a) => !a.place && a.dans_feuille) },
  { titre: 'Mes autres affaires (hors feuille)', liste: affaires.value.filter((a) => !a.dans_feuille) },
].filter((g) => g.liste.length))

function choisir(a: AffairePointable, fermer: () => void) {
  modele.value = a.id
  libelle.value = nomAffaire(a)
  recherche.value = ''
  fermer()
}
defineExpose({ nomAffaire })
</script>

<template>
  <button
    :id="id"
    ref="ancre"
    type="button"
    class="saisie choix"
    :aria-invalid="invalide || undefined"
    :aria-expanded="ouvert"
    @click="ouvert = !ouvert"
  >
    <span v-if="modele" class="gras tronquer">{{ libelle }}</span>
    <span v-else class="vide">Choisir une affaire…</span>
    <i class="bi bi-chevron-down" aria-hidden="true" />
  </button>
  <UiMenuDeroulant v-model="ouvert" :ancre="ancre" :largeur-min="420">
    <template #default="{ fermer }">
      <div class="recherche"><input v-model="recherche" class="saisie" placeholder="N° ou nom d'affaire…" aria-label="Rechercher une affaire" /></div>
      <p v-if="chargement && !affaires.length" class="info">Chargement…</p>
      <p v-else-if="!affaires.length" class="info">Aucune affaire : vous devez en être responsable ou membre.</p>
      <template v-for="g in groupes" :key="g.titre">
        <p class="groupe">{{ g.titre }}</p>
        <button
          v-for="a in g.liste"
          :key="a.id"
          type="button"
          class="option"
          role="option"
          :aria-selected="a.id === modele"
          @click="choisir(a, fermer)"
        >
          <span class="tronquer">{{ nomAffaire(a) }}</span>
          <span class="indicateurs">
            <span v-if="a.prioritaire" class="badge badge-attention" title="Une ligne a le statut prioritaire au pointage"><i class="bi bi-star-fill" aria-hidden="true" /></span>
            <span v-if="a.place" class="badge badge-marine">Placé</span>
          </span>
        </button>
      </template>
    </template>
  </UiMenuDeroulant>
</template>

<style scoped>
.choix { display: flex; align-items: center; gap: var(--e2); text-align: left; cursor: pointer; }
.choix .bi { margin-left: auto; font-size: 0.7rem; color: var(--texte-doux); }
.vide { color: var(--texte-leger); }
.recherche { padding: var(--e1) var(--e2) var(--e2); }
.recherche .saisie { height: 32px; }
.groupe { padding: var(--e1) var(--e3); background: var(--surface-douce); font-size: var(--taille-xs); font-weight: 700; color: var(--texte-doux); text-transform: uppercase; letter-spacing: 0.03em; }
.option { display: flex; align-items: center; gap: var(--e2); width: 100%; padding: var(--e2) var(--e3); border: none; background: none; text-align: left; cursor: pointer; font-size: var(--taille-s); }
.option:hover, .option[aria-selected='true'] { background: var(--marine-pale); }
.indicateurs { margin-left: auto; display: flex; gap: 4px; }
.info { padding: var(--e3); font-size: var(--taille-s); color: var(--texte-doux); }
</style>
