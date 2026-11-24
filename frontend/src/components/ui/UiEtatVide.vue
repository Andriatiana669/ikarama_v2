<!-- Message quand une liste est vide, avec une action possible dans le slot. -->
<script setup lang="ts">
withDefaults(defineProps<{ titre: string; texte?: string; icone?: string }>(), { icone: 'inbox' })
</script>

<template>
  <div class="vide">
    <i :class="`bi bi-${icone}`" aria-hidden="true" />
    <p class="gras">{{ titre }}</p>
    <p v-if="texte" class="texte-doux texte-petit">{{ texte }}</p>
    <div v-if="$slots.default" class="action"><slot /></div>
  </div>
</template>

<style scoped>
.vide { display: flex; flex-direction: column; align-items: center; gap: var(--e1); padding: var(--e6) var(--e4); text-align: center; }
.vide .bi { font-size: 1.75rem; color: var(--texte-leger); margin-bottom: var(--e2); }
.vide .texte-petit { max-width: 46ch; }
.action { margin-top: var(--e3); }
</style>
