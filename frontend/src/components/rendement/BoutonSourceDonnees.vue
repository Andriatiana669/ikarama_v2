<!--
  Source des données des onglets du Rendement (état commun) : Pointages + Feuilles (normale), Feuilles, Pointages.
  Seules les sources autorisées dans Paramètres > Graphiques sont proposées.
-->
<script setup lang="ts">
const props = defineProps<{ valeur: '' | 'feuilles' | 'pointages'; autorisees: { feuilles: boolean; pointages: boolean } }>()
defineEmits<{ choisir: [v: '' | 'feuilles' | 'pointages'] }>()
const OPTIONS = [
  { v: '' as const, libelle: 'Pointages + Feuilles', icone: 'intersect', aide: 'Normal : temps des pointages, Employé, Date de début et statut des feuilles.' },
  { v: 'feuilles' as const, libelle: 'Feuilles', icone: 'file-earmark-spreadsheet', aide: 'Seulement les feuilles (anciennes données sans pointage).' },
  { v: 'pointages' as const, libelle: 'Pointages', icone: 'stopwatch', aide: 'Seulement les pointages (affaires pointées sans feuille).' },
]
const proposees = () => OPTIONS.filter((o) => !o.v || props.autorisees[o.v])
</script>

<template>
  <div class="source" role="radiogroup" aria-label="Source des données">
    <span class="etiquette">Source</span>
    <button v-for="o in proposees()" :key="o.v || 'normale'" type="button" role="radio" :aria-checked="valeur === o.v" :class="{ actif: valeur === o.v }"
      :title="o.aide" @click="$emit('choisir', o.v)">
      <i :class="`bi bi-${o.icone}`" aria-hidden="true" /> {{ o.libelle }}
    </button>
  </div>
</template>

<style scoped>
.source { display: inline-flex; align-items: center; height: 36px; border: 1px solid var(--bordure-forte); border-radius: var(--rayon); overflow: hidden; background: var(--surface); }
.etiquette { padding: 0 10px; font-size: var(--taille-xs); font-weight: 700; color: var(--texte-doux); text-transform: uppercase; letter-spacing: 0.03em; }
button { display: inline-flex; align-items: center; gap: 5px; height: 100%; padding: 0 12px; border: none; border-left: 1px solid var(--bordure); background: none; font-size: var(--taille-s); font-weight: 600; color: var(--texte-doux); cursor: pointer; white-space: nowrap; }
button.actif { background: var(--marine); color: #fff; }
</style>
