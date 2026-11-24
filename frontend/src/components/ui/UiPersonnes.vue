<!-- Plusieurs personnes en pastilles superposées (3 au plus, puis « +n »). Les noms s'affichent au survol. -->
<script setup lang="ts">
import { computed } from 'vue'
import type { EmployeResume } from '@/types'
import UiAvatar from './UiAvatar.vue'

const props = withDefaults(defineProps<{ personnes: EmployeResume[]; max?: number }>(), { max: 3 })
const visibles = computed(() => props.personnes.slice(0, props.max))
const noms = computed(() => props.personnes.map((p) => p.nom_affiche).join(', '))
</script>

<template>
  <span v-if="personnes.length" class="personnes" :title="noms">
    <UiAvatar v-for="p in visibles" :key="p.id" :nom="p.nom_affiche" :matricule="p.code_barre" />
    <span v-if="personnes.length > max" class="avatar plus">+{{ personnes.length - max }}</span>
    <span class="masque-visuel">{{ noms }}</span>
  </span>
  <span v-else class="texte-doux">—</span>
</template>

<style scoped>
.personnes { display: inline-flex; align-items: center; }
.personnes :deep(.avatar) { width: 26px; height: 26px; font-size: 0.6rem; border: 2px solid var(--surface); }
.personnes :deep(.avatar + .avatar) { margin-left: -8px; }
.plus { background: var(--surface-douce); color: var(--texte-doux); }
</style>
