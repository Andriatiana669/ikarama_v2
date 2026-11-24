<script setup lang="ts">
import UiEtatVide from '@/components/ui/UiEtatVide.vue'
</script>

<template>
  <div class="page">
    <div class="carte">
      <UiEtatVide icone="signpost-split" titre="Cette page n'existe pas" texte="Vérifiez l'adresse ou revenez au menu.">
        <RouterLink to="/" class="btn btn-primaire">Retour à l'accueil</RouterLink>
      </UiEtatVide>
    </div>
  </div>
</template>
