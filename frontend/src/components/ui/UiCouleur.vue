<!-- Choix d'une couleur de fond : palette rapide + sélecteur libre, avec aperçu. v-model = « #RRGGBB ». -->
<script setup lang="ts">
import { couleurTexte } from '@/utils/format'

const modele = defineModel<string | null>()
withDefaults(defineProps<{ apercu?: string; id?: string }>(), { apercu: 'Aperçu' })

// Tons doux et vifs accordés à la charte (marine / rouge)
const PALETTE = ['#E8EEF6', '#18355D', '#24497A', '#E5F4EC', '#1E8A5A', '#FBF2E1', '#B7791F', '#FDECEC', '#E94242', '#EDE9FE', '#6D28D9', '#E5E7EB']
</script>

<template>
  <div class="couleur">
    <div class="palette" role="radiogroup" aria-label="Couleurs proposées">
      <button
        v-for="c in PALETTE"
        :key="c"
        type="button"
        class="pastille"
        role="radio"
        :aria-checked="modele?.toUpperCase() === c"
        :aria-label="c"
        :style="{ background: c }"
        @click="modele = c"
      />
      <label class="libre" title="Autre couleur">
        <input :id="id" type="color" :value="modele || '#E8EEF6'" @input="modele = ($event.target as HTMLInputElement).value.toUpperCase()" />
        <i class="bi bi-eyedropper" aria-hidden="true" />
      </label>
    </div>
    <span class="apercu" :style="{ background: modele || '#E8EEF6', color: couleurTexte(modele || '#E8EEF6') }">{{ apercu }}</span>
  </div>
</template>

<style scoped>
.couleur { display: flex; align-items: center; gap: var(--e4); flex-wrap: wrap; }
.palette { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.pastille { width: 24px; height: 24px; border-radius: 50%; border: 1px solid var(--bordure-forte); cursor: pointer; }
.pastille[aria-checked='true'] { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--marine); }
.libre { position: relative; display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; border: 1px dashed var(--bordure-forte); cursor: pointer; color: var(--texte-doux); }
.libre input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.apercu { padding: 3px 12px; border-radius: 999px; font-size: var(--taille-s); font-weight: 600; }
</style>
