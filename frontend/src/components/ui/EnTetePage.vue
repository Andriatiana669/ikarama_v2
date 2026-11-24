<!-- En-tête de page : titre, description et boutons d'action. -->
<script setup lang="ts">
defineProps<{ titre: string; description?: string }>()
</script>

<template>
  <header class="entete-page">
    <div class="textes">
      <h1>{{ titre }}</h1>
      <p v-if="description" class="texte-doux">{{ description }}</p>
    </div>
    <div v-if="$slots.default" class="ligne"><slot /></div>
  </header>
</template>

<style scoped>
.entete-page {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--e4);
  flex-wrap: wrap;
  margin-bottom: var(--e5);
}
.textes p { margin-top: var(--e1); max-width: 70ch; }
</style>
