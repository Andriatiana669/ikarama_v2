<!-- Pied de page discret. -->
<script setup lang="ts">
const annee = new Date().getFullYear()
</script>

<template>
  <footer class="pied texte-xs texte-doux">Ikarama, suivi des pointages – {{ annee }}</footer>
</template>

<style scoped>
.pied { padding: var(--e4) var(--e6); border-top: 1px solid var(--bordure); }
</style>
