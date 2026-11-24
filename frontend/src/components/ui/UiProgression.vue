<!-- Barre de progression en pourcentage (0 à 100). -->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ valeur: number | null | undefined }>()
const pourcentage = computed(() => Math.max(0, Math.min(100, Math.round(props.valeur ?? 0))))
const couleur = computed(() => (pourcentage.value >= 100 ? 'var(--succes)' : pourcentage.value > 0 ? 'var(--marine-clair)' : 'var(--bordure-forte)'))
</script>

<template>
  <span class="progression" role="progressbar" :aria-valuenow="pourcentage" aria-valuemin="0" aria-valuemax="100">
    <span class="barre"><span class="rempli" :style="{ width: `${pourcentage}%`, background: couleur }" /></span>
    <span class="valeur">{{ pourcentage }} %</span>
  </span>
</template>

<style scoped>
.progression { display: inline-flex; align-items: center; gap: var(--e2); min-width: 110px; }
.barre { flex: 1; height: 6px; border-radius: 3px; background: var(--surface-douce); border: 1px solid var(--bordure); overflow: hidden; }
.rempli { display: block; height: 100%; border-radius: 3px; transition: width var(--transition); }
.valeur { font-size: var(--taille-xs); color: var(--texte-doux); width: 38px; text-align: right; }
</style>
