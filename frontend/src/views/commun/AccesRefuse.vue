<!-- Page des personnes qui ne respectent pas les règles d'accès au site (Paramètres > Accès au site). -->
<script setup lang="ts">
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
</script>

<template>
  <main class="refus">
    <div class="boite">
      <div class="logos">
        <img src="/logo_gauche.svg" alt="" class="logo-icone" />
        <img src="/Logo_lalamby_2.svg" alt="Lalamby Ikarama" class="logo" />
      </div>

      <i class="bi bi-shield-lock icone" aria-hidden="true" />
      <h1>Vous n'avez pas accès à Ikarama</h1>
      <p>
        Votre compte
        <strong v-if="auth.utilisateur">{{ auth.utilisateur.username }}</strong>
        n'est pas autorisé à utiliser cette application.
      </p>
      <p class="aide">
        Si vous pensez qu'il s'agit d'une erreur, contactez votre responsable ou l'administrateur d'Ikarama
        en indiquant votre matricule.
      </p>

      <button type="button" class="deconnexion" @click="auth.seDeconnecter">
        <i class="bi bi-box-arrow-right" aria-hidden="true" />Se déconnecter
      </button>
    </div>
  </main>
</template>

<style scoped>
.refus {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--e5);
  background: var(--marine);
  color: #fff;
}
.boite { max-width: 520px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: var(--e3); }
.logos { display: flex; align-items: center; gap: var(--e3); margin-bottom: var(--e6); }
.logo-icone { width: 36px; height: 36px; }
.logo { height: 30px; }
.icone { font-size: 2.5rem; color: var(--rouge); }
h1 { color: #fff; font-size: var(--taille-xl); }
p { color: rgba(255, 255, 255, 0.85); }
.aide { font-size: var(--taille-s); color: rgba(255, 255, 255, 0.65); max-width: 44ch; }
.deconnexion {
  display: inline-flex;
  align-items: center;
  gap: var(--e2);
  margin-top: var(--e5);
  padding: var(--e2) var(--e5);
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: var(--rayon);
  background: transparent;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.deconnexion:hover { background: rgba(255, 255, 255, 0.1); }
</style>
