<!-- Fil de la sélection en cours : Affaire › Prestation › Projet, avec une croix pour retirer chaque choix. -->
<script setup lang="ts">
import type { Affaire, Prestation, Projet } from '@/types'

defineProps<{ affaire: Affaire | null; prestation: Prestation | null; projet: Projet | null }>()
const emit = defineEmits<{ retirer: [niveau: 'affaire' | 'prestation' | 'projet'] }>()
</script>

<template>
  <nav class="fil carte" aria-label="Sélection en cours">
    <span class="etape" :class="{ vide: !affaire }">
      <i class="bi bi-briefcase" aria-hidden="true" />
      <template v-if="affaire">
        <span class="gras">{{ affaire.num_affaire ? `${affaire.num_affaire} – ` : '' }}{{ affaire.nom }}</span>
        <button type="button" aria-label="Retirer l'affaire choisie" @click="emit('retirer', 'affaire')"><i class="bi bi-x" aria-hidden="true" /></button>
      </template>
      <template v-else>Aucune affaire choisie</template>
    </span>
    <i class="bi bi-chevron-right sep" aria-hidden="true" />
    <span class="etape" :class="{ vide: !prestation }">
      <i class="bi bi-clipboard-check" aria-hidden="true" />
      <template v-if="prestation">
        <span class="gras">{{ prestation.nom }}</span>
        <button type="button" aria-label="Retirer la prestation choisie" @click="emit('retirer', 'prestation')"><i class="bi bi-x" aria-hidden="true" /></button>
      </template>
      <template v-else>Prestation</template>
    </span>
    <i class="bi bi-chevron-right sep" aria-hidden="true" />
    <span class="etape" :class="{ vide: !projet }">
      <i class="bi bi-geo-alt" aria-hidden="true" />
      <template v-if="projet">
        <span class="gras">{{ projet.numero }}. {{ projet.nom }}</span>
        <button type="button" aria-label="Retirer le projet choisi" @click="emit('retirer', 'projet')"><i class="bi bi-x" aria-hidden="true" /></button>
      </template>
      <template v-else>Projet / Commune</template>
    </span>
  </nav>
</template>

<style scoped>
.fil { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; padding: var(--e2) var(--e4); margin-bottom: var(--e4); font-size: var(--taille-s); }
.etape { display: inline-flex; align-items: center; gap: var(--e2); padding: var(--e1) var(--e2); border-radius: var(--rayon); background: var(--marine-pale); color: var(--marine); }
.etape.vide { background: none; color: var(--texte-leger); }
.etape button { border: none; background: none; color: inherit; cursor: pointer; display: grid; place-items: center; }
.sep { color: var(--texte-leger); font-size: 0.7rem; }
</style>
