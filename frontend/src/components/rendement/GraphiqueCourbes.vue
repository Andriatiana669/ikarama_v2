<!--
  Evolution : courbes superposées (une par groupe de tâches) avec leur aire, une graduation par date pointée
  et le nom du mois sous chaque groupe de dates ; ligne pointillée de l'objectif.
  ecarts : écarts en % à afficher (calculés par la page, tolérance déjà appliquée).
-->
<script setup lang="ts">
import { computed } from 'vue'
import { formatPct as pct, type Ecart } from '@/utils/rendement'

const props = defineProps<{
  dates: string[]
  courbes: { nom: string; couleur: string; valeurs: (number | null)[]; detail?: string }[]
  objectif: number | null
  unite: string
  /** Écarts à afficher entre les deux courbes (voir utils/rendement.ts) */
  ecarts?: Ecart[]
}>()

const L = 760, H = 360, G = 56, D = 80, HAUT = 20, BAS = 64
const largeurUtile = L - G - D
const hauteurUtile = H - HAUT - BAS

const max = computed(() => {
  const brut = Math.max(1, props.objectif ?? 0, ...props.courbes.flatMap((c) => c.valeurs.map((v) => v ?? 0))) * 1.15
  const pas = 10 ** Math.floor(Math.log10(brut))
  return Math.ceil(brut / pas) * pas
})
const y = (v: number) => HAUT + hauteurUtile - (v / max.value) * hauteurUtile
const x = (i: number) => G + (props.dates.length <= 1 ? largeurUtile / 2 : (largeurUtile * i) / (props.dates.length - 1))
const graduations = computed(() => Array.from({ length: 6 }, (_, i) => (max.value / 5) * i))

/** Segments continus (une date sans valeur coupe la courbe) */
function segments(valeurs: (number | null)[]) {
  const liste: { i: number; v: number }[][] = []
  let courant: { i: number; v: number }[] = []
  valeurs.forEach((v, i) => {
    if (v === null) {
      if (courant.length) liste.push(courant)
      courant = []
    } else courant.push({ i, v })
  })
  if (courant.length) liste.push(courant)
  return liste
}
const ligne = (s: { i: number; v: number }[]) => s.map((p, k) => `${k ? 'L' : 'M'}${x(p.i)},${y(p.v)}`).join(' ')
const aire = (s: { i: number; v: number }[]) =>
  `M${x(s[0]!.i)},${y(0)} ${s.map((p) => `L${x(p.i)},${y(p.v)}`).join(' ')} L${x(s[s.length - 1]!.i)},${y(0)} Z`

/** Groupes de dates par mois : position de l'étiquette et séparations */
const mois = computed(() => {
  const groupes: { cle: string; debut: number; fin: number }[] = []
  props.dates.forEach((d, i) => {
    const cle = d.slice(0, 7)
    const dernier = groupes[groupes.length - 1]
    if (dernier && dernier.cle === cle) dernier.fin = i
    else groupes.push({ cle, debut: i, fin: i })
  })
  return groupes.map((g) => {
    const t = new Date(`${g.cle}-01T12:00:00`).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
    return { ...g, nom: t.charAt(0).toUpperCase() + t.slice(1), centre: (x(g.debut) + x(g.fin)) / 2 }
  })
})
const tousLes = computed(() => Math.max(1, Math.ceil(props.dates.length / 24)))
const ecarts = computed(() => props.ecarts ?? [])
const n = (v: number) => v.toLocaleString('fr-FR', { maximumFractionDigits: 0 })
const jour = (d: string) => d.slice(8, 10)
const dateLongue = (d: string) => new Date(`${d}T12:00:00`).toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'long' })
</script>

<template>
  <div>
    <svg :viewBox="`0 0 ${L} ${H}`" class="graphique" role="img" :aria-label="`Évolution du rendement en ${unite} par jour`">
      <g v-for="g in graduations" :key="g">
        <line :x1="G" :x2="L - D" :y1="y(g)" :y2="y(g)" class="grille" />
        <text :x="G - 8" :y="y(g) + 4" class="axe" text-anchor="end">{{ n(g) }}</text>
      </g>
      <!-- Séparations entre les mois -->
      <line v-for="m in mois.slice(1)" :key="`s${m.cle}`" :x1="(x(m.debut) + x(m.debut - 1)) / 2" :x2="(x(m.debut) + x(m.debut - 1)) / 2"
        :y1="HAUT" :y2="H - BAS + 40" class="separation" />
      <line :x1="G" :x2="G" :y1="HAUT - 6" :y2="H - BAS" class="axe-ligne" />
      <line :x1="G" :x2="L - D + 10" :y1="H - BAS" :y2="H - BAS" class="axe-ligne" />

      <g v-for="c in courbes" :key="c.nom">
        <path v-for="(s, k) in segments(c.valeurs)" :key="`a${k}`" :d="aire(s)" :fill="c.couleur" fill-opacity="0.13" />
        <path v-for="(s, k) in segments(c.valeurs)" :key="`l${k}`" :d="ligne(s)" :stroke="c.couleur" stroke-width="2.2" fill="none" />
        <template v-for="(v, i) in c.valeurs" :key="i">
          <circle v-if="v !== null" :cx="x(i)" :cy="y(v)" r="3.2" :fill="c.couleur">
            <title>{{ c.nom }}, {{ dateLongue(dates[i]!) }} : {{ n(v) }} {{ unite }} / j</title>
          </circle>
        </template>
      </g>

      <!-- Écart entre les deux courbes -->
      <g v-for="e in ecarts" :key="`e${e.i}`" class="ecart">
        <title>{{ dateLongue(dates[e.i]!) }} : écart {{ pct(e.pct) }} ({{ courbes[1]!.nom }} par rapport à {{ courbes[0]!.nom }})</title>
        <line :x1="x(e.i)" :x2="x(e.i)" :y1="y(e.haut)" :y2="y(e.bas)" class="trait-ecart" />
        <rect :x="x(e.i) - 28" :y="y(e.haut) - 24" width="56" height="16" rx="8" class="fond-ecart" />
        <text :x="x(e.i)" :y="y(e.haut) - 12.5" text-anchor="middle" class="texte-ecart">{{ pct(e.pct) }}</text>
      </g>

      <line v-if="objectif" :x1="G" :x2="L - D" :y1="y(objectif)" :y2="y(objectif)" class="objectif" />
      <text v-if="objectif" :x="L - D + 4" :y="y(objectif) + 4" class="objectif-texte">{{ n(objectif) }} {{ unite }}</text>

      <template v-for="(d, i) in dates" :key="d">
        <text v-if="i % tousLes === 0" :x="x(i)" :y="H - BAS + 16" class="axe jour" text-anchor="middle">{{ jour(d) }}</text>
      </template>
      <text v-for="m in mois" :key="m.cle" :x="m.centre" :y="H - BAS + 36" class="mois" text-anchor="middle">{{ m.nom }}</text>
    </svg>
    <ul class="legende">
      <li v-for="c in courbes" :key="c.nom"><span class="pastille" :style="{ background: c.couleur }" /><span class="gras">{{ c.nom }}</span>
        <span v-if="c.detail" class="texte-doux"> ({{ c.detail }})</span></li>
      <li v-if="objectif"><span class="pointille" /> Objectif</li>

    </ul>
  </div>
</template>

<style scoped>
.graphique { width: 100%; height: auto; }
.grille { stroke: var(--bordure); stroke-width: 1; }
.separation { stroke: var(--bordure-forte); stroke-width: 1; stroke-dasharray: 2 4; }
.axe { fill: var(--texte-doux); font-size: 10px; }
.mois { fill: var(--marine); font-size: 12px; font-weight: 700; }
.axe-ligne { stroke: var(--marine); stroke-width: 2; }
.objectif { stroke: var(--rouge); stroke-width: 1.5; stroke-dasharray: 8 6; }
.objectif-texte { fill: var(--rouge); font-size: 11px; font-weight: 600; }
.legende { list-style: none; display: flex; flex-wrap: wrap; gap: var(--e1) var(--e4); font-size: var(--taille-s); }
.legende li { display: inline-flex; align-items: center; gap: 6px; }
.pastille { width: 12px; height: 12px; border-radius: 3px; }
.trait-ecart { stroke: var(--texte-doux); stroke-width: 1; stroke-dasharray: 2 2; }
.fond-ecart { fill: var(--surface); stroke: var(--bordure-forte); stroke-width: 1; }
.texte-ecart { fill: var(--marine); font-size: 9.5px; font-weight: 700; font-variant-numeric: tabular-nums; }
.pointille { width: 18px; border-top: 2px dashed var(--rouge); }
</style>
