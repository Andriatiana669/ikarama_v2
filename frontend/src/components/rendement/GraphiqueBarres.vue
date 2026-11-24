<!--
  Histogramme du rendement / j : une barre par élément (prestation, projet ou description), précédée
  éventuellement d'une barre « Global ». Repère pointillé de l'objectif (une ligne si tous les objectifs
  sont égaux) ; barre verte si l'objectif est atteint, rouge sinon. Chaque barre garde son unité.
-->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  /** Heures pointées (source « Pointages ») : pas d'objectif, barres neutres, valeurs en heures */
  heures?: boolean
  /** Noms de l'axe X à la verticale (noms d'employés : évite qu'ils se chevauchent) */
  verticales?: boolean
  barres: { nom: string; valeur: number | null; objectif: number; detail: string; unite: string; global?: boolean }[]
}>()

const L = 680, G = 56, D = 70, HAUT = 20
// Noms à la verticale : plus de place en bas, même hauteur utile pour les barres
const BAS = props.verticales ? 128 : 56
const H = 284 + BAS
const largeurUtile = L - G - D
const hauteurUtile = H - HAUT - BAS

const max = computed(() => {
  const valeurs = props.barres.flatMap((b) => (props.heures ? [b.valeur ?? 0] : [b.valeur ?? 0, b.objectif]))
  const brut = Math.max(1, ...valeurs) * 1.15
  const pas = 10 ** Math.floor(Math.log10(brut))
  return Math.ceil(brut / pas) * pas
})
const y = (v: number) => HAUT + hauteurUtile - (v / max.value) * hauteurUtile
const graduations = computed(() => Array.from({ length: 6 }, (_, i) => (max.value / 5) * i))
const pas = computed(() => largeurUtile / Math.max(1, props.barres.length))
const largeurBarre = computed(() => Math.min(56, pas.value * 0.6))
const x = (i: number) => G + pas.value * i + pas.value / 2
const objectifUnique = computed(() => {
  if (props.heures) return null
  const objectifs = new Set(props.barres.map((b) => b.objectif))
  const unites = new Set(props.barres.map((b) => b.unite))
  return objectifs.size === 1 && unites.size === 1 ? [...objectifs][0]! : null
})
const uniteUnique = computed(() => props.barres[0]?.unite ?? '')
const n = (v: number) => v.toLocaleString('fr-FR', { maximumFractionDigits: Math.abs(v) < 10 ? 2 : Math.abs(v) < 100 ? 1 : 0 })
const valeur = (v: number) => (props.heures ? `${n(v)} h` : n(v))
const court = (t: string) => (t.length > 14 ? `${t.slice(0, 13)}…` : t)
</script>

<template>
  <svg :viewBox="`0 0 ${L} ${H}`" class="graphique" role="img" aria-label="Rendement par jour, comparé à l'objectif">
    <defs>
      <pattern id="hachures" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" stroke-width="2" stroke-opacity="0.25" />
      </pattern>
    </defs>
    <g v-for="g in graduations" :key="g">
      <line :x1="G" :x2="L - D" :y1="y(g)" :y2="y(g)" class="grille" />
      <text :x="G - 8" :y="y(g) + 4" class="axe" text-anchor="end">{{ n(g) }}</text>
    </g>
    <line :x1="G" :x2="G" :y1="HAUT - 6" :y2="H - BAS" class="axe-ligne" />
    <line :x1="G" :x2="L - D + 10" :y1="H - BAS" :y2="H - BAS" class="axe-ligne" />

    <line v-if="objectifUnique !== null" :x1="G" :x2="L - D" :y1="y(objectifUnique)" :y2="y(objectifUnique)" class="objectif" />
    <text v-if="objectifUnique !== null" :x="L - D + 4" :y="y(objectifUnique) + 4" class="objectif-texte">{{ n(objectifUnique) }} {{ uniteUnique }}</text>

    <g v-for="(b, i) in barres" :key="i">
      <title v-if="heures">{{ b.nom }} : {{ b.valeur === null ? 'pas de temps pointé' : `${n(b.valeur)} h pointées (H_Durée + HS)` }} – {{ b.detail }}</title>
      <title v-else>{{ b.nom }} : {{ b.valeur === null ? 'pas de temps pointé' : `${n(b.valeur)} ${b.unite} / j` }} (objectif {{ n(b.objectif) }} {{ b.unite }}) – {{ b.detail }}</title>
      <rect
        v-if="b.valeur !== null"
        :x="x(i) - largeurBarre / 2" :y="y(b.valeur)" :width="largeurBarre" :height="Math.max(1, y(0) - y(b.valeur))"
        rx="5" :class="[heures ? 'neutre' : b.valeur >= b.objectif ? 'atteint' : 'manque', { global: b.global }]"
      />
      <rect v-if="b.valeur !== null && b.global" :x="x(i) - largeurBarre / 2" :y="y(b.valeur)" :width="largeurBarre"
        :height="Math.max(1, y(0) - y(b.valeur))" rx="5" fill="url(#hachures)" :class="b.valeur >= b.objectif ? 'trait-ok' : 'trait-manque'" />
      <line v-if="objectifUnique === null && !heures" :x1="x(i) - largeurBarre / 2 - 6" :x2="x(i) + largeurBarre / 2 + 6" :y1="y(b.objectif)" :y2="y(b.objectif)" class="objectif" />
      <text v-if="b.valeur !== null" :x="x(i)" :y="y(b.valeur) - 6" class="valeur" text-anchor="middle">{{ valeur(b.valeur) }}</text>
      <text v-if="verticales" :transform="`translate(${x(i) + 3}, ${H - BAS + 8}) rotate(-90)`" class="axe" :class="{ gras: b.global }"
        text-anchor="end">{{ b.nom.length > 22 ? `${b.nom.slice(0, 21)}…` : b.nom }}</text>
      <text v-else :x="x(i)" :y="H - BAS + 18" class="axe" :class="{ gras: b.global }" text-anchor="middle">{{ court(b.nom) }}</text>
      <text v-if="objectifUnique === null && !verticales && !heures" :x="x(i)" :y="H - BAS + 32" class="axe unite" text-anchor="middle">{{ b.unite }}</text>
    </g>
  </svg>
</template>

<style scoped>
.graphique { width: 100%; height: auto; }
.grille { stroke: var(--bordure); stroke-width: 1; }
.axe { fill: var(--texte-doux); font-size: 11px; }
.axe-ligne { stroke: var(--marine); stroke-width: 2; }
.objectif { stroke: var(--rouge); stroke-width: 1.5; stroke-dasharray: 8 6; }
.objectif-texte { fill: var(--rouge); font-size: 11px; font-weight: 600; }
.neutre { fill: color-mix(in srgb, var(--marine) 14%, transparent); stroke: var(--marine); stroke-width: 2; }
.atteint { fill: color-mix(in srgb, var(--succes) 14%, transparent); stroke: var(--succes); stroke-width: 2; }
.manque { fill: color-mix(in srgb, var(--rouge) 12%, transparent); stroke: var(--rouge); stroke-width: 2; }
.global { stroke-width: 3; }
.trait-ok { color: var(--succes); }
.trait-manque { color: var(--rouge); }
.gras { font-weight: 700; fill: var(--marine); }
.unite { font-size: 10px; font-style: italic; }
.valeur { fill: var(--marine); font-size: 11px; font-weight: 700; }
</style>
