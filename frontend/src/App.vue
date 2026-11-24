<!-- Composant racine : le cadre de l'application + les notifications globales. -->
<script setup lang="ts">
import { useRoute } from 'vue-router'
import AppLayout from '@/components/Layout/AppLayout.vue'
import UiNotifications from '@/components/ui/UiNotifications.vue'

const route = useRoute()
</script>

<template>
  <RouterView v-if="route.meta.sansCadre" />
  <AppLayout v-else>
    <RouterView />
  </AppLayout>
  <UiNotifications />
</template>
