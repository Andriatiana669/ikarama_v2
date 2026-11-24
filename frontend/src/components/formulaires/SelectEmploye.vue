<!--
  Choix d'un employé avec recherche (matricule, nom, prénom).
  <SelectEmploye v-model="chefId" :employe-initial="equipe.chef_details" />
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { onClickOutside, watchDebounced } from '@vueuse/core'
import { utilisateursApi } from '@/api'
import type { EmployeResume, Identifiant } from '@/types'
import { nomEmploye } from '@/utils/format'

const modele = defineModel<Identifiant | null>()
const props = defineProps<{
  employeInitial?: EmployeResume | null
  placeholder?: string
  invalide?: boolean
  id?: string
  /** Source de la recherche ; par défaut, les employés visibles dans l'application */
  rechercher?: (texte: string) => Promise<EmployeResume[]>
  /** Le champ se vide après chaque choix (ajout de plusieurs personnes) */
  viderApresChoix?: boolean
}>()
const emit = defineEmits<{ choisi: [employe: EmployeResume | null] }>()
const chercher = (texte: string) => (props.rechercher ?? utilisateursApi.rechercher)(texte)

const racine = ref<HTMLElement | null>(null)
const ouvert = ref(false)
const texte = ref('')
const resultats = ref<EmployeResume[]>([])
const chargement = ref(false)
const choisi = ref<EmployeResume | null>(props.employeInitial ?? null)
const indexActif = ref(0)

watch(() => props.employeInitial, (e) => (choisi.value = e ?? null))
watch(modele, async (id) => {
  if (!id) choisi.value = null
  else if (choisi.value?.id !== id) choisi.value = await utilisateursApi.lire(id)
})

watchDebounced(
  texte,
  async (valeur) => {
    if (!ouvert.value) {
      if (!valeur) return
      ouvert.value = true   // texte saisi sans passer par le clavier (collé…) : on ouvre quand même
    }
    chargement.value = true
    try {
      resultats.value = await chercher(valeur)
      indexActif.value = 0
    } finally {
      chargement.value = false
    }
  },
  { debounce: 250 },
)

const affichage = computed(() => (choisi.value ? `${nomEmploye(choisi.value)} (${choisi.value.code_barre ?? '—'})` : ''))

function ouvrir() {
  if (ouvert.value) return
  ouvert.value = true
  texte.value = ''
  chercher('').then((r) => (resultats.value = r))
}

function choisir(employe: EmployeResume | null) {
  ouvert.value = false
  emit('choisi', employe)
  if (props.viderApresChoix) {
    texte.value = ''
    return
  }
  choisi.value = employe
  modele.value = employe?.id ?? null
}

function clavier(evenement: KeyboardEvent) {
  if (!ouvert.value) return ouvrir()
  if (evenement.key === 'ArrowDown') indexActif.value = Math.min(indexActif.value + 1, resultats.value.length - 1)
  else if (evenement.key === 'ArrowUp') indexActif.value = Math.max(indexActif.value - 1, 0)
  else if (evenement.key === 'Enter') choisir(resultats.value[indexActif.value] ?? null)
  else if (evenement.key === 'Escape') ouvert.value = false
  else return
  evenement.preventDefault()
}

onClickOutside(racine, () => (ouvert.value = false))
</script>

<template>
  <div ref="racine" class="select-employe">
    <input
      :id="id"
      class="saisie"
      role="combobox"
      :aria-expanded="ouvert"
      :aria-invalid="invalide || undefined"
      autocomplete="off"
      :placeholder="ouvert ? 'Matricule, nom ou prénom…' : placeholder || 'Choisir un employé'"
      :value="ouvert ? texte : affichage"
      @focus="ouvrir"
      @input="texte = ($event.target as HTMLInputElement).value"
      @keydown="clavier"
    />
    <button v-if="choisi && !ouvert" class="effacer" type="button" aria-label="Retirer l'employé" @click="choisir(null)">
      <i class="bi bi-x-circle-fill" aria-hidden="true" />
    </button>
    <ul v-if="ouvert" class="liste carte" role="listbox">
      <li v-if="chargement" class="info">Recherche…</li>
      <li v-else-if="!resultats.length" class="info">Aucun employé ne correspond.</li>
      <li
        v-for="(employe, index) in resultats"
        v-else
        :key="employe.id"
        role="option"
        :aria-selected="index === indexActif"
        :class="{ actif: index === indexActif }"
        @mousedown.prevent="choisir(employe)"
        @mouseenter="indexActif = index"
      >
        <span>{{ nomEmploye(employe) }}</span>
        <span class="code">{{ employe.code_barre }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.select-employe { position: relative; }
.effacer {
  position: absolute; right: var(--e2); top: 50%; transform: translateY(-50%);
  border: none; background: none; color: var(--texte-leger); cursor: pointer;
}
.liste {
  position: absolute; z-index: 20; top: calc(100% + 4px); left: 0; right: 0;
  max-height: 260px; overflow-y: auto; list-style: none; padding: var(--e1) 0; box-shadow: var(--ombre-haute);
}
.liste li { display: flex; justify-content: space-between; gap: var(--e3); padding: var(--e2) var(--e3); cursor: pointer; font-size: var(--taille-s); }
.liste li.actif { background: var(--marine-pale); }
.liste li.info { color: var(--texte-doux); cursor: default; }
</style>
