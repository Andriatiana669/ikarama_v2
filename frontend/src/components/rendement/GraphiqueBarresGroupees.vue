<!-- Réel vs Objectif : par employé, une barre par série (le réel, puis l'objectif), chacune de sa couleur. -->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  groupes: { nom: string; couleur: string }[]
  employes: { nom: string; valeurs: (number | null)[]; detail: string }[]
  unite: string
}>()

const L = 760, G = 56, D = 70, HAUT = 20, BAS = 128   // noms d'employés à la verticale
const H = 284 + BAS
const largeurUtile = L - G - D
const hauteurUtile = H - HAUT - BAS
const max = computed(() => {
  const brut = Math.max(1, ...props.employes.flatMap((e) => e.valeurs.map((v) => v ?? 0))) * 1.15
  const pas = 10 ** Math.floor(Math.log10(brut))
  return Math.ceil(brut / pas) * pas
})
const y = (v: number) => HAUT + hauteurUtile - (v / max.value) * hauteurUtile
const graduations = computed(() => Array.from({ length: 6 }, (_, i) => (max.value / 5) * i))
const pas = computed(() => largeurUtile / Math.max(1, props.employes.length))
const largeurBarre = computed(() => Math.min(34, (pas.value * 0.7) / Math.max(1, props.groupes.length)))
const xGroupe = (i: number) => G + pas.value * i + pas.value / 2
const xBarre = (i: number, g: number) => xGroupe(i) + (g - (props.groupes.length - 1) / 2) * (largeurBarre.value + 4)
const n = (v: number) => v.toLocaleString('fr-FR', { maximumFractionDigits: Math.abs(v) < 10 ? 2 : Math.abs(v) < 100 ? 1 : 0 })
const court = (t: string) => (t.length > 22 ? `${t.slice(0, 21)}…` : t)
</script>

<template>
  <div>
    <svg :viewBox="`0 0 ${L} ${H}`" class="graphique" role="img" :aria-label="`Rendement par employé et par groupe de tâches, en ${unite} par jour`">
      <g v-for="g in graduations" :key="g">
        <line :x1="G" :x2="L - D" :y1="y(g)" :y2="y(g)" class="grille" />
        <text :x="G - 8" :y="y(g) + 4" class="axe" text-anchor="end">{{ n(g) }}</text>
      </g>
      <line :x1="G" :x2="G" :y1="HAUT - 6" :y2="H - BAS" class="axe-ligne" />
      <line :x1="G" :x2="L - D + 10" :y1="H - BAS" :y2="H - BAS" class="axe-ligne" />
      <g v-for="(e, i) in employes" :key="e.nom">
        <template v-for="(groupe, gi) in groupes" :key="gi">
          <g v-if="e.valeurs[gi] !== null && e.valeurs[gi] !== undefined">
            <title>{{ e.nom }}, {{ groupe.nom }} : {{ n(e.valeurs[gi]!) }} {{ unite }} / j – {{ e.detail }}</title>
            <rect :x="xBarre(i, gi) - largeurBarre / 2" :y="y(e.valeurs[gi]!)" :width="largeurBarre"
              :height="Math.max(1, y(0) - y(e.valeurs[gi]!))" rx="4" :fill="groupe.couleur" fill-opacity="0.85" />
            <text :x="xBarre(i, gi)" :y="y(e.valeurs[gi]!) - 5" class="valeur" text-anchor="middle">{{ n(e.valeurs[gi]!) }}{{ unite === 'h' ? ' h' : '' }}</text>
          </g>
        </template>
        <text :transform="`translate(${xGroupe(i) + 3}, ${H - BAS + 8}) rotate(-90)`" class="axe nom" text-anchor="end">{{ court(e.nom) }}</text>
      </g>
    </svg>
    <ul class="legende">
      <li v-for="g in groupes" :key="g.nom"><span class="pastille" :style="{ background: g.couleur }" />{{ g.nom }}</li>
    </ul>
  </div>
</template>

<style scoped>
.graphique { width: 100%; height: auto; }
.grille { stroke: var(--bordure); stroke-width: 1; }
.axe { fill: var(--texte-doux); font-size: 11px; }
.nom { font-weight: 600; fill: var(--marine); }
.axe-ligne { stroke: var(--marine); stroke-width: 2; }
.valeur { fill: var(--marine); font-size: 10px; font-weight: 700; }
.legende { list-style: none; display: flex; flex-wrap: wrap; gap: var(--e1) var(--e4); font-size: var(--taille-s); }
.legende li { display: inline-flex; align-items: center; gap: 6px; }
.pastille { width: 12px; height: 12px; border-radius: 3px; }
</style>
