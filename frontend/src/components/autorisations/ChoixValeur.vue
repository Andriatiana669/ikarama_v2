<!--
  Choix d'une valeur dans une liste, avec recherche (ex. un poste, un pôle) : on tape quelques lettres
  et on choisit dans les propositions, comme pour une personne.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const modele = defineModel<string>({ default: '' })
const props = withDefaults(defineProps<{ options: string[]; placeholder?: string; libelle?: string }>(), { placeholder: 'Rechercher…' })

const saisie = ref(modele.value)
const ouvert = ref(false)
const actif = ref(0)
watch(modele, (v) => (saisie.value = v))

const sansAccents = (t: string) => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
const propositions = computed(() => {
  const q = sansAccents(saisie.value.trim())
  return props.options.filter((o) => !q || sansAccents(o).includes(q)).slice(0, 50)
})
function choisir(valeur: string) {
  modele.value = valeur
  saisie.value = valeur
  ouvert.value = false
}
function clavier(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    ouvert.value = true
    actif.value = Math.min(actif.value + 1, propositions.value.length - 1)
    e.preventDefault()
  } else if (e.key === 'ArrowUp') {
    actif.value = Math.max(actif.value - 1, 0)
    e.preventDefault()
  } else if (e.key === 'Enter' && ouvert.value && propositions.value[actif.value]) {
    choisir(propositions.value[actif.value]!)
    e.preventDefault()
  } else if (e.key === 'Escape') {
    ouvert.value = false
  }
}
function quitter() {
  // Une valeur hors de la liste n'est pas gardée : on revient à la dernière valeur choisie
  window.setTimeout(() => {
    ouvert.value = false
    if (!props.options.includes(saisie.value)) saisie.value = modele.value
  }, 150)
}
</script>

<template>
  <div class="choix-valeur">
    <input v-model="saisie" class="saisie" :placeholder="placeholder" :aria-label="libelle ?? placeholder" role="combobox"
      :aria-expanded="ouvert" autocomplete="off" @focus="ouvert = true; actif = 0" @input="ouvert = true; actif = 0" @keydown="clavier" @blur="quitter" />
    <ul v-if="ouvert" class="propositions" role="listbox">
      <li v-for="(o, i) in propositions" :key="o" role="option" :aria-selected="i === actif" :class="{ actif: i === actif }"
        @mousedown.prevent="choisir(o)">{{ o }}</li>
      <li v-if="!propositions.length" class="vide">Aucun résultat</li>
    </ul>
  </div>
</template>

<style scoped>
.choix-valeur { position: relative; min-width: 200px; }
.choix-valeur .saisie { width: 100%; }
.propositions { position: absolute; z-index: 30; top: calc(100% + 2px); left: 0; right: 0; max-height: 240px; overflow-y: auto; list-style: none;
  border: 1px solid var(--bordure-forte); border-radius: var(--rayon); background: var(--surface); box-shadow: var(--ombre-m, 0 6px 18px rgba(0,0,0,.12)); }
.propositions li { padding: 6px 10px; font-size: var(--taille-s); cursor: pointer; }
.propositions li.actif, .propositions li:hover { background: var(--marine-pale); }
.propositions li.vide { color: var(--texte-doux); cursor: default; }
</style>
