<!-- Entoure une case quand quelqu'un d'autre est en train de la modifier (sans la bloquer). -->
<script setup lang="ts">
import type { PresenceFeuille } from '@/types'

defineProps<{ occupant: PresenceFeuille['employe'] | null }>()
</script>

<template>
  <span class="zone" :class="{ occupee: occupant }" :title="occupant ? `${occupant.identifiant} modifie cette case` : undefined">
    <span v-if="occupant" class="qui">{{ occupant.identifiant }}</span>
    <slot />
  </span>
</template>

<style scoped>
.zone { position: relative; display: inline-flex; border-radius: var(--rayon); }
.zone.occupee { box-shadow: 0 0 0 2px var(--rouge); }
.qui {
  position: absolute;
  top: -9px;
  left: 4px;
  z-index: 2;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--rouge);
  color: #fff;
  font-size: 0.625rem;
  font-weight: 700;
  line-height: 16px;
  white-space: nowrap;
  animation: apparait 200ms ease;
}
@keyframes apparait { from { opacity: 0; transform: translateY(2px); } }
</style>
