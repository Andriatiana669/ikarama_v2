<!-- Filtre à choix multiples compact : un bouton (avec le nombre choisi) qui ouvre une liste à cocher avec recherche. -->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const choix = defineModel<(string | number)[]>({ default: () => [] })
const props = defineProps<{ libelle: string; options: { id: string | number; nom: string }[]; icone?: string }>()
const ouvert = ref(false)
const recherche = ref('')
const racine = ref<HTMLElement | null>(null)
const filtrees = computed(() => {
  const q = recherche.value.trim().toLowerCase()
  return props.options.filter((o) => !q || o.nom.toLowerCase().includes(q))
})
function basculer(id: string | number) {
  choix.value = choix.value.includes(id) ? choix.value.filter((x) => x !== id) : [...choix.value, id]
}
const fermer = (e: MouseEvent) => {
  if (racine.value && !racine.value.contains(e.target as Node)) ouvert.value = false
}
onMounted(() => document.addEventListener('mousedown', fermer))
onBeforeUnmount(() => document.removeEventListener('mousedown', fermer))
</script>

<template>
  <div ref="racine" class="filtre-multi">
    <button type="button" class="declencheur" :class="{ actif: choix.length }" :aria-expanded="ouvert" @click="ouvert = !ouvert">
      <i v-if="icone" :class="`bi bi-${icone}`" aria-hidden="true" /> {{ libelle }}
      <span v-if="choix.length" class="compte">{{ choix.length }}</span>
      <i class="bi bi-chevron-down" aria-hidden="true" />
    </button>
    <div v-if="ouvert" class="panneau" role="dialog" :aria-label="libelle">
      <input v-model="recherche" class="saisie" type="search" placeholder="Rechercher" :aria-label="`Rechercher : ${libelle}`" />
      <ul>
        <li v-for="o in filtrees" :key="o.id">
          <label><input type="checkbox" :checked="choix.includes(o.id)" @change="basculer(o.id)" /> {{ o.nom }}</label>
        </li>
        <li v-if="!filtrees.length" class="vide">Aucun choix</li>
      </ul>
      <button v-if="choix.length" type="button" class="effacer" @click="choix = []">Tout décocher</button>
    </div>
  </div>
</template>

<style scoped>
.filtre-multi { position: relative; }
.declencheur { display: inline-flex; align-items: center; gap: 6px; height: 34px; padding: 0 10px; border: 1px solid var(--bordure-forte); border-radius: var(--rayon); background: var(--surface); font-size: var(--taille-s); font-weight: 600; color: var(--texte); cursor: pointer; white-space: nowrap; }
.declencheur.actif { border-color: var(--marine); color: var(--marine); background: var(--marine-pale); }
.compte { min-width: 18px; padding: 0 5px; border-radius: 999px; background: var(--rouge); color: #fff; font-size: 0.68rem; line-height: 18px; text-align: center; }
.panneau { position: absolute; z-index: 40; top: calc(100% + 4px); left: 0; width: 280px; padding: var(--e2); border: 1px solid var(--bordure-forte); border-radius: var(--rayon); background: var(--surface); box-shadow: 0 8px 24px rgba(0, 0, 0, 0.14); }
.panneau .saisie { width: 100%; margin-bottom: var(--e2); }
ul { list-style: none; max-height: 260px; overflow-y: auto; }
li label { display: flex; align-items: center; gap: 8px; padding: 4px 6px; border-radius: 4px; font-size: var(--taille-s); cursor: pointer; }
li label:hover { background: var(--surface-douce); }
.vide { padding: 6px; color: var(--texte-doux); font-size: var(--taille-s); }
.effacer { margin-top: var(--e2); border: none; background: none; color: var(--rouge); font-size: var(--taille-xs); font-weight: 700; cursor: pointer; }
</style>
