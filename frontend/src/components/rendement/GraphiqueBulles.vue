<!--
  Carte du mois (Analyse) : une bulle par affaire / prestation.
  X = part du temps du mois, Y = rentabilité (rendement ÷ objectif), taille = heures, couleur = zone.
  Ligne verticale : seuil « beaucoup de temps » ; ligne horizontale : rentabilité 1 (objectif atteint).
-->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  points: { nom: string; part: number; rentabilite: number; heures: number; zone: string; detail: string }[]
  seuilTemps: number
}>()

const COULEURS: Record<string, string> = { garder: '#1E8A5A', revoir: '#E94242', potentiel: '#24497A', ponctuel: '#B7791F' }
const L = 420, H = 300, G = 40, D = 34, HAUT = 30, BAS = 34
const lu = L - G - D, hu = H - HAUT - BAS
const maxY = computed(() => Math.max(2, Math.ceil(Math.max(...props.points.map((p) => p.rentabilite), 0) * 1.15 * 2) / 2))
const x = (part: number) => G + part * lu
const y = (r: number) => HAUT + hu - (Math.min(r, maxY.value) / maxY.value) * hu
const maxHeures = computed(() => Math.max(1, ...props.points.map((p) => p.heures)))
const rayon = (h: number) => 7 + 15 * Math.sqrt(h / maxHeures.value)
const graduationsY = computed(() => Array.from({ length: Math.round(maxY.value / 0.5) + 1 }, (_, i) => i * 0.5).filter((v) => v % 1 === 0 || maxY.value <= 3))
const f = (v: number) => v.toLocaleString('fr-FR', { maximumFractionDigits: 2 })
const court = (t: string) => (t.length > 14 ? `${t.slice(0, 13)}…` : t)
/** Étiquette gardée dans le cadre (pas coupée sur les bords) */
const xEtiquette = (part: number) => Math.min(Math.max(x(part), G + 34), L - 34)
</script>

<template>
  <svg :viewBox="`0 0 ${L} ${H}`" class="bulles" role="img" aria-label="Part du temps et rentabilité par affaire et prestation">
    <!-- Zones -->
    <rect :x="x(seuilTemps / 100)" :y="HAUT" :width="x(1) - x(seuilTemps / 100)" :height="y(1) - HAUT" class="z garder" />
    <rect :x="x(seuilTemps / 100)" :y="y(1)" :width="x(1) - x(seuilTemps / 100)" :height="HAUT + hu - y(1)" class="z revoir" />
    <rect :x="G" :y="HAUT" :width="x(seuilTemps / 100) - G" :height="y(1) - HAUT" class="z potentiel" />
    <rect :x="G" :y="y(1)" :width="x(seuilTemps / 100) - G" :height="HAUT + hu - y(1)" class="z ponctuel" />
    <text :x="x(1) - 6" :y="HAUT + 14" text-anchor="end" class="zone-texte" fill="#1E8A5A">À garder</text>
    <text :x="x(1) - 6" :y="HAUT + hu - 6" text-anchor="end" class="zone-texte" fill="#E94242">À revoir</text>
    <text :x="G + 6" :y="HAUT + 14" class="zone-texte" fill="#24497A">Potentiel</text>
    <text :x="G + 6" :y="HAUT + hu - 6" class="zone-texte" fill="#B7791F">Ponctuel</text>

    <g v-for="v in graduationsY" :key="v">
      <text :x="G - 6" :y="y(v) + 4" class="axe" text-anchor="end">{{ f(v) }}</text>
    </g>
    <text v-for="p in [0, 25, 50, 75, 100]" :key="p" :x="x(p / 100)" :y="H - BAS + 16" class="axe" text-anchor="middle">{{ p }} %</text>
    <line :x1="G" :x2="x(1)" :y1="y(1)" :y2="y(1)" class="seuil" />
    <line :x1="x(seuilTemps / 100)" :x2="x(seuilTemps / 100)" :y1="HAUT" :y2="HAUT + hu" class="seuil" />
    <line :x1="G" :x2="G" :y1="HAUT" :y2="HAUT + hu" class="axe-ligne" />
    <line :x1="G" :x2="x(1)" :y1="HAUT + hu" :y2="HAUT + hu" class="axe-ligne" />
    <text :x="x(0.5)" :y="H - 4" class="axe titre-axe" text-anchor="middle">Part du temps de la période</text>

    <g v-for="p in points" :key="p.nom">
      <title>{{ p.nom }} : {{ f(p.part * 100) }} % du temps, rentabilité {{ f(p.rentabilite) }} – {{ p.detail }}</title>
      <circle :cx="x(p.part)" :cy="y(p.rentabilite)" :r="rayon(p.heures)" :fill="COULEURS[p.zone] ?? '#64748B'" fill-opacity="0.55"
        :stroke="COULEURS[p.zone] ?? '#64748B'" stroke-width="2" />
      <text :x="xEtiquette(p.part)" :y="Math.max(10, y(p.rentabilite) - rayon(p.heures) - 4)" class="nom" text-anchor="middle">{{ court(p.nom) }}</text>
    </g>
  </svg>
</template>

<style scoped>
.bulles { width: 100%; height: auto; }
.z { opacity: 0.07; }
.z.garder { fill: #1e8a5a; } .z.revoir { fill: #e94242; } .z.potentiel { fill: #24497a; } .z.ponctuel { fill: #b7791f; }
.zone-texte { font-size: 10px; font-weight: 700; opacity: 0.8; }
.axe { fill: var(--texte-doux); font-size: 9.5px; }
.titre-axe { font-size: 10px; font-style: italic; }
.axe-ligne { stroke: var(--marine); stroke-width: 1.5; }
.seuil { stroke: var(--texte-leger); stroke-width: 1; stroke-dasharray: 4 4; }
.nom { fill: var(--marine); font-size: 9.5px; font-weight: 600; }
</style>
