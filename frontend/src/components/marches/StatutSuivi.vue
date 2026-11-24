<!--
  Statut calculé d'un niveau du Marché :
  statut final (coche) · statut commun · progression « Terminé 3/5 » · « — ».
-->
<script setup lang="ts">
import type { StatutSuivi } from '@/types'
import { couleurTexte } from '@/utils/format'

defineProps<{ statut: StatutSuivi | null }>()
</script>

<template>
  <span v-if="!statut" class="texte-doux">—</span>
  <span
    v-else-if="statut.progression"
    class="progression"
    :style="{ borderColor: statut.couleur }"
    :title="`${statut.progression.au_statut} description(s) sur ${statut.progression.total} au statut « ${statut.nom} »`"
  >
    <span class="point" :style="{ background: statut.couleur }" />
    {{ statut.nom }} {{ statut.progression.au_statut }}/{{ statut.progression.total }}
  </span>
  <span v-else class="pastille" :style="{ background: statut.couleur, color: couleurTexte(statut.couleur) }">
    <i v-if="statut.final" class="bi bi-check-circle-fill" aria-hidden="true" />{{ statut.nom }}
  </span>
</template>

<style scoped>
.pastille { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; border-radius: 999px; font-weight: 600; font-size: var(--taille-xs); white-space: nowrap; }
.progression { display: inline-flex; align-items: center; gap: 6px; padding: 1px 9px; border: 1px solid; border-radius: 999px; font-size: var(--taille-xs); font-weight: 600; color: var(--texte-doux); white-space: nowrap; }
.point { width: 8px; height: 8px; border-radius: 50%; }
</style>
