<!-- Page commune aux onglets pas encore développés. -->
<script setup lang="ts">
import { useRoute } from 'vue-router'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'

const route = useRoute()
</script>

<template>
  <div class="page">
    <EnTetePage :titre="route.meta.titre ?? ''" :description="route.meta.section" />
    <div class="carte">
      <UiEtatVide
        icone="cone-striped"
        titre="Cette page arrive bientôt"
        texte="Ses fonctionnalités seront ajoutées dans une prochaine version d'Ikarama."
      />
    </div>
  </div>
</template>
