// src/main.ts — point d'entrée de l'application
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'bootstrap-icons/font/bootstrap-icons.css'
import './style.css'

import App from './App.vue'
import router from './router'
import { ApiErreur, messageErreur } from './api/client'
import { ENV } from './config/environnement'
import { demarrerSession } from './services/session'
import { useAuthStore } from './store/auth'

async function demarrer() {
  const app = createApp(App)
  app.use(createPinia())

  // 1. Obtenir un jeton Keycloak. Redirige vers la page de connexion si besoin.
  const cheminRetour = await demarrerSession()

  // 2. Charger l'utilisateur connecté depuis le backend
  await useAuthStore().charger()

  // 3. Ouvrir l'application
  app.use(router)
  if (cheminRetour) await router.replace(cheminRetour)
  await router.isReady()
  app.mount('#app')
}

demarrer().catch((erreur) => {
  // Écran d'erreur minimal, sans dépendre de Vue
  const zone = document.getElementById('demarrage')
  if (zone) {
    zone.innerHTML = `
      <p class="demarrage-titre">Impossible d'ouvrir Ikarama</p>
      <p class="demarrage-texte"></p>
      <button type="button" onclick="location.reload()">Réessayer</button>`
    // Sans réponse du serveur : on affiche l'adresse appelée pour aider au diagnostic
    const sansReponse = erreur instanceof ApiErreur && erreur.statut === null
    zone.querySelector('.demarrage-texte')!.textContent = sansReponse
      ? `Le serveur ne répond pas à l'adresse ${ENV.apiUrl}. Vérifiez que Django est lancé et que cette page est autorisée (CORS_ALLOWED_ORIGINS).`
      : messageErreur(erreur)
  }
  console.error(erreur)
})
