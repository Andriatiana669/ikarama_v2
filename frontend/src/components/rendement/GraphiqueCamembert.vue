<!-- Camembert (anneau) : une part par élément, avec la valeur et le pourcentage dans la légende. -->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ parts: { nom: string; valeur: number }[]; unite: string; decimales?: number }>()

const COULEURS = ['#24497A', '#E94242', '#1E8A5A', '#B7791F', '#6D28D9', '#0E7490', '#BE185D', '#4D7C0F', '#64748B', '#C2410C']
const total = computed(() => props.parts.reduce((s, p) => s + p.valeur, 0))
const R = 80, r = 48, C = 100

const tranches = computed(() => {
  let angle = -Math.PI / 2
  return props.parts.map((p, i) => {
    const part = total.value ? p.valeur / total.value : 0
    const debut = angle
    angle += part * 2 * Math.PI
    return { ...p, part, couleur: COULEURS[i % COULEURS.length]!, d: arc(debut, angle) }
  })
})
function arc(a1: number, a2: number) {
  if (a2 - a1 >= 2 * Math.PI - 1e-6) a2 = a1 + 2 * Math.PI - 1e-4   // part unique : anneau complet
  const p = (rayon: number, a: number) => `${C + rayon * Math.cos(a)},${C + rayon * Math.sin(a)}`
  const grand = a2 - a1 > Math.PI ? 1 : 0
  return `M${p(R, a1)} A${R},${R} 0 ${grand} 1 ${p(R, a2)} L${p(r, a2)} A${r},${r} 0 ${grand} 0 ${p(r, a1)} Z`
}
const n = (v: number) => v.toLocaleString('fr-FR', { maximumFractionDigits: props.decimales ?? 0 })
const pct = (v: number) => `${(v * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`
</script>

<template>
  <div class="camembert">
    <svg viewBox="0 0 200 200" class="anneau" role="img" :aria-label="`Répartition, total ${n(total)} ${unite}`">
      <path v-for="t in tranches" :key="t.nom" :d="t.d" :fill="t.couleur">
        <title>{{ t.nom }} : {{ n(t.valeur) }} {{ unite }} ({{ pct(t.part) }})</title>
      </path>
      <text x="100" y="96" text-anchor="middle" class="total">{{ n(total) }}</text>
      <text x="100" y="114" text-anchor="middle" class="unite">{{ unite }}</text>
    </svg>
    <ul class="legende">
      <li v-for="t in tranches" :key="t.nom">
        <span class="pastille" :style="{ background: t.couleur }" />
        <span class="nom" :title="t.nom">{{ t.nom }}</span>
        <span class="valeur">{{ n(t.valeur) }}</span>
        <span class="pct">{{ pct(t.part) }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.camembert { display: flex; align-items: center; gap: var(--e4); flex-wrap: wrap; }
.anneau { width: 180px; height: 180px; flex: none; }
.total { font-size: 20px; font-weight: 700; fill: var(--marine); }
.unite { font-size: 11px; fill: var(--texte-doux); }
.legende { list-style: none; flex: 1; min-width: 180px; display: flex; flex-direction: column; gap: 4px; font-size: var(--taille-s); }
.legende li { display: grid; grid-template-columns: 12px 1fr auto 56px; align-items: center; gap: var(--e2); }
.pastille { width: 12px; height: 12px; border-radius: 3px; }
.nom { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.valeur { font-weight: 700; color: var(--marine); font-variant-numeric: tabular-nums; }
.pct { text-align: right; color: var(--texte-doux); font-variant-numeric: tabular-nums; }
</style>
