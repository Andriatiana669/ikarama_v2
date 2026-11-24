<!-- Cadre de l'application : menu latéral + barre du haut + contenu de la page. -->
<script setup lang="ts">
import { onMounted } from 'vue'
import { useTempsReel } from '@/composables/useTempsReel'
import Footer from './Footer.vue'
import Navbar from './Navbar.vue'
import Sidebar from './Sidebar.vue'

// Temps réel (WebSocket) : une seule connexion pour tout l'onglet, ouverte une fois connecté
onMounted(() => useTempsReel().demarrer())
</script>

<template>
  <div class="cadre">
    <Sidebar />
    <div class="colonne">
      <Navbar />
      <main id="contenu" class="contenu">
        <slot />
      </main>
      <Footer />
    </div>
  </div>
</template>

<style scoped>
.cadre { display: flex; min-height: 100vh; }
.colonne { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.contenu { flex: 1; }
</style>
