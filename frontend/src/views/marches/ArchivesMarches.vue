<!-- Marchés > Archives : affaires archivées, avec la possibilité de les désarchiver. -->
<script setup lang="ts">
import EnTetePage from '@/components/ui/EnTetePage.vue'
import PanneauAffaires from '@/components/marches/PanneauAffaires.vue'
</script>

<template>
  <div class="page">
    <EnTetePage
      titre="Archives"
      description="Les affaires archivées ne sont plus proposées. Désarchivez une affaire pour la retrouver dans « Ajouter un marché » et « Mes marchés »."
    />
    <PanneauAffaires mode="archives" />
  </div>
</template>
