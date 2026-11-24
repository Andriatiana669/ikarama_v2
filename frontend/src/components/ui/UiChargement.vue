<!-- Indicateur de chargement. -->
<script setup lang="ts">
withDefaults(defineProps<{ texte?: string }>(), { texte: 'Chargement…' })
</script>

<template>
  <div class="chargement" role="status">
    <span class="barre" aria-hidden="true" />
    <span class="texte-doux texte-petit">{{ texte }}</span>
  </div>
</template>

<style scoped>
.chargement { display: flex; flex-direction: column; align-items: center; gap: var(--e3); padding: var(--e6); }
.barre {
  width: 120px;
  height: 3px;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--marine-pale) 0%, var(--marine) 50%, var(--marine-pale) 100%);
  background-size: 200% 100%;
  animation: defile 1.1s linear infinite;
}
@keyframes defile { from { background-position: 200% 0; } to { background-position: 0 0; } }
</style>
