<!-- Pied de page discret. -->
<script setup lang="ts">
const annee = new Date().getFullYear()
</script>

<template>
  <footer class="pied texte-xs texte-doux">Copyright © PARERA Madagascar – {{ annee }}</footer>
</template>

<style scoped>
.pied { padding: var(--e4) var(--e6); border-top: 1px solid var(--bordure); text-align: center;}
</style>
