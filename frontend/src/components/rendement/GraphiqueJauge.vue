<!--
  Jauge : valeur comparée à l'objectif. Échelle de 0 à « maximum » (par défaut 2 × l'objectif), pour que
  plusieurs jauges partagent la même échelle ; zone rouge sous l'objectif, verte au-dessus ; aiguille sur
  la valeur ; au centre la valeur et le % de l'objectif (sauf « sansComparaison », pour la jauge de l'objectif).
-->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  titre: string
  couleur: string
  valeur: number | null
  objectif: number | null
  unite: string
  detail?: string
  /** Échelle commune à plusieurs jauges */
  maximum?: number
  sansComparaison?: boolean
}>()

const C = 110, CY = 110, R = 86, EP = 18
const maximum = computed(() => props.maximum ?? Math.max((props.objectif ?? 0) * 2, (props.valeur ?? 0) * 1.05, 1))
const angle = (v: number) => Math.PI * (1 - Math.min(1, Math.max(0, v / maximum.value)))
const point = (a: number, r = R) => `${C + r * Math.cos(a)},${CY - r * Math.sin(a)}`
const arc = (de: number, a: number) => {
  const a1 = angle(de), a2 = angle(a)
  return `M${point(a1)} A${R},${R} 0 0 1 ${point(a2)}`
}
const aiguille = computed(() => (props.valeur === null ? null : angle(props.valeur)))
const pctObjectif = computed(() => (props.valeur !== null && props.objectif ? (props.valeur / props.objectif) * 100 : null))
const n = (v: number) => v.toLocaleString('fr-FR', { maximumFractionDigits: 0 })
</script>

<template>
  <figure class="jauge">
    <figcaption class="titre"><span class="pastille" :style="{ background: couleur }" />{{ titre }}</figcaption>
    <svg viewBox="0 0 220 130" role="img" :aria-label="`${titre} : ${valeur === null ? 'aucune valeur' : `${n(valeur)} ${unite} par jour`}, objectif ${objectif ? n(objectif) : '—'}`">
      <path :d="arc(0, maximum)" class="fond" :stroke-width="EP" />
      <template v-if="objectif">
        <path :d="arc(0, objectif)" class="zone-rouge" :stroke-width="EP" />
        <path :d="arc(objectif, maximum)" class="zone-verte" :stroke-width="EP" />
        <line :x1="C + (R - EP / 2 - 4) * Math.cos(angle(objectif))" :y1="CY - (R - EP / 2 - 4) * Math.sin(angle(objectif))"
          :x2="C + (R + EP / 2 + 4) * Math.cos(angle(objectif))" :y2="CY - (R + EP / 2 + 4) * Math.sin(angle(objectif))" class="repere" />
      </template>
      <path v-if="valeur !== null" :d="arc(0, valeur)" :stroke="couleur" :stroke-width="EP / 2.4" fill="none" stroke-linecap="round" />
      <template v-if="aiguille !== null">
        <line :x1="C" :y1="CY" :x2="C + (R - 6) * Math.cos(aiguille)" :y2="CY - (R - 6) * Math.sin(aiguille)" class="aiguille" />
        <circle :cx="C" :cy="CY" r="6" class="pivot" />
      </template>
      <text x="22" y="126" class="borne">0</text>
      <text x="198" y="126" class="borne" text-anchor="end">{{ n(maximum) }}</text>
    </svg>
    <div class="chiffres">
      <strong>{{ valeur === null ? '—' : n(valeur) }}</strong> <span class="texte-xs texte-doux">{{ unite }} / j</span>
      <template v-if="!sansComparaison">
        <span v-if="pctObjectif !== null" class="pct" :class="pctObjectif >= 100 ? 'ok' : 'ko'">{{ n(pctObjectif) }} % de l'objectif</span>
        <span class="texte-xs texte-doux">Objectif : {{ objectif ? n(objectif) : '—' }} {{ unite }}</span>
      </template>
      <span v-if="detail" class="texte-xs texte-doux">{{ detail }}</span>
    </div>
  </figure>
</template>

<style scoped>
.jauge { display: flex; flex-direction: column; align-items: center; gap: var(--e1); margin: 0; }
.titre { display: inline-flex; align-items: center; gap: 6px; font-weight: 700; color: var(--marine); }
.pastille { width: 12px; height: 12px; border-radius: 3px; }
svg { width: 100%; max-width: 260px; }
.fond { stroke: var(--bordure); fill: none; }
.zone-rouge { stroke: color-mix(in srgb, var(--rouge) 28%, transparent); fill: none; }
.zone-verte { stroke: color-mix(in srgb, var(--succes) 28%, transparent); fill: none; }
.repere { stroke: var(--rouge); stroke-width: 2.5; }
.aiguille { stroke: var(--marine); stroke-width: 3; stroke-linecap: round; }
.pivot { fill: var(--marine); }
.borne { fill: var(--texte-doux); font-size: 9px; }
.chiffres { display: flex; flex-direction: column; align-items: center; gap: 2px; text-align: center; }
.chiffres strong { font-size: var(--taille-xl); color: var(--marine); }
.pct { padding: 1px 10px; border-radius: 999px; font-size: var(--taille-xs); font-weight: 700; }
.pct.ok { background: color-mix(in srgb, var(--succes) 15%, transparent); color: var(--succes); }
.pct.ko { background: color-mix(in srgb, var(--rouge) 12%, transparent); color: var(--rouge); }
</style>
