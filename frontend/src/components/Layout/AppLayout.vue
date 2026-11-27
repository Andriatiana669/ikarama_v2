<!-- Cadre de l'application : menu latéral + barre du haut + contenu de la page. -->
<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTempsReel } from '@/composables/useTempsReel'
import { useAuthStore } from '@/store/auth'
import Footer from './Footer.vue'
import Navbar from './Navbar.vue'
import Sidebar from './Sidebar.vue'

// Temps réel (WebSocket) : une seule connexion pour tout l'onglet, ouverte une fois connecté
const tempsReel = useTempsReel()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

// Droits relus dès qu'un rôle, un droit, une attribution ou une règle d'accès change (sans F5) ;
// sans temps réel : au retour sur l'onglet, au plus une fois par minute.
let attente: number | undefined
let derniereLecture = Date.now()
async function relireDroits() {
  derniereLecture = Date.now()
  try {
    await auth.charger()
    // La page ouverte n'est plus permise : retour à l'Accueil
    const meta = route.meta as { module?: string; verbe?: string; administrateur?: boolean }
    const interdite = (meta.administrateur && !auth.estAdministrateur) || (meta.module && !auth.peut(meta.verbe ?? 'voir', meta.module))
    if (interdite) router.replace('/accueil').catch(() => undefined)
  } catch {
    // session expirée ou serveur injoignable : géré par le client HTTP
  }
}
const desabonner = tempsReel.ecouter('droits', () => {
  window.clearTimeout(attente)
  attente = window.setTimeout(relireDroits, 500)
})
function auRetour() {
  if (document.visibilityState === 'visible' && !tempsReel.connecte.value && Date.now() - derniereLecture > 60_000) relireDroits()
}
onMounted(() => {
  tempsReel.demarrer()
  document.addEventListener('visibilitychange', auRetour)
})
onBeforeUnmount(() => {
  desabonner()
  document.removeEventListener('visibilitychange', auRetour)
  window.clearTimeout(attente)
})
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
