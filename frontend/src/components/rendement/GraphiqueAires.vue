<!-- Évolution du rendement dans le temps : une aire par personne, et la ligne d'objectif des équipes. -->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  periodes: string[]
  series: { nom: string; valeurs: number[] }[]
  objectif: number | null
  unite: string
  granularite: 'jour' | 'mois'
}>()

const COULEURS = ['#24497A', '#E94242', '#1E8A5A', '#B7791F', '#6D28D9', '#0E7490', '#BE185D', '#4D7C0F']
const L = 680, H = 340, G = 56, D = 70, HAUT = 20, BAS = 56
const largeurUtile = L - G - D
const hauteurUtile = H - HAUT - BAS

const max = computed(() => {
  const brut = Math.max(1, props.objectif ?? 0, ...props.series.flatMap((s) => s.valeurs)) * 1.15
  const pas = 10 ** Math.floor(Math.log10(brut))
  return Math.ceil(brut / pas) * pas
})
const y = (v: number) => HAUT + hauteurUtile - (v / max.value) * hauteurUtile
const x = (i: number) => G + (props.periodes.length <= 1 ? largeurUtile / 2 : (largeurUtile * i) / (props.periodes.length - 1))
const graduations = computed(() => Array.from({ length: 6 }, (_, i) => (max.value / 5) * i))
const chemin = (valeurs: number[]) => {
  if (!valeurs.length) return ''
  const points = valeurs.map((v, i) => `${x(i)},${y(v)}`)
  return `M${x(0)},${y(0)} L${points.join(' L')} L${x(valeurs.length - 1)},${y(0)} Z`
}
const ligne = (valeurs: number[]) => valeurs.map((v, i) => `${i ? 'L' : 'M'}${x(i)},${y(v)}`).join(' ')
const n = (v: number) => v.toLocaleString('fr-FR', { maximumFractionDigits: 0 })
const etiquette = (p: string) =>
  props.granularite === 'mois'
    ? new Date(`${p}-01T12:00:00`).toLocaleDateString('fr-FR', { month: 'short', year: '2-digit' })
    : new Date(`${p}T12:00:00`).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })
// Pas plus d'une dizaine d'étiquettes sur l'axe horizontal
const tousLes = computed(() => Math.max(1, Math.ceil(props.periodes.length / 10)))
</script>

<template>
  <div>
    <svg :viewBox="`0 0 ${L} ${H}`" class="graphique" role="img" :aria-label="`Évolution du rendement par personne, en ${unite} par jour`">
      <g v-for="g in graduations" :key="g">
        <line :x1="G" :x2="L - D" :y1="y(g)" :y2="y(g)" class="grille" />
        <text :x="G - 8" :y="y(g) + 4" class="axe" text-anchor="end">{{ n(g) }}</text>
      </g>
      <line :x1="G" :x2="G" :y1="HAUT - 6" :y2="H - BAS" class="axe-ligne" />
      <line :x1="G" :x2="L - D + 10" :y1="H - BAS" :y2="H - BAS" class="axe-ligne" />
      <g v-for="(s, i) in series" :key="s.nom">
        <path :d="chemin(s.valeurs)" :fill="COULEURS[i % COULEURS.length]" fill-opacity="0.14" />
        <path :d="ligne(s.valeurs)" :stroke="COULEURS[i % COULEURS.length]" stroke-width="2" fill="none" />
        <circle v-for="(v, j) in s.valeurs" :key="j" :cx="x(j)" :cy="y(v)" r="3" :fill="COULEURS[i % COULEURS.length]">
          <title>{{ s.nom }}, {{ etiquette(periodes[j]!) }} : {{ n(v) }} {{ unite }} / j</title>
        </circle>
      </g>
      <line v-if="objectif" :x1="G" :x2="L - D" :y1="y(objectif)" :y2="y(objectif)" class="objectif" />
      <text v-if="objectif" :x="L - D + 4" :y="y(objectif) + 4" class="objectif-texte">{{ n(objectif) }} {{ unite }}</text>
      <template v-for="(p, i) in periodes" :key="p">
        <text v-if="i % tousLes === 0" :x="x(i)" :y="H - BAS + 18" class="axe" text-anchor="middle">{{ etiquette(p) }}</text>
      </template>
    </svg>
    <ul class="legende">
      <li v-for="(s, i) in series" :key="s.nom"><span class="pastille" :style="{ background: COULEURS[i % COULEURS.length] }" />{{ s.nom }}</li>
    </ul>
  </div>
</template>

<style scoped>
.graphique { width: 100%; height: auto; }
.grille { stroke: var(--bordure); stroke-width: 1; }
.axe { fill: var(--texte-doux); font-size: 11px; }
.axe-ligne { stroke: var(--marine); stroke-width: 2; }
.objectif { stroke: var(--rouge); stroke-width: 1.5; stroke-dasharray: 8 6; }
.objectif-texte { fill: var(--rouge); font-size: 11px; font-weight: 600; }
.legende { list-style: none; display: flex; flex-wrap: wrap; gap: var(--e1) var(--e4); font-size: var(--taille-xs); color: var(--texte-doux); }
.legende li { display: inline-flex; align-items: center; gap: 6px; }
.pastille { width: 10px; height: 10px; border-radius: 3px; }
</style>
