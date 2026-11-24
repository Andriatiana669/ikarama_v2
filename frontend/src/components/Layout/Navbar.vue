<!-- Barre du haut : fil d'Ariane à gauche ; administration et déconnexion à droite. -->
<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { authApi } from '@/api'
import { ENV } from '@/config/environnement'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/store/auth'
import { useInterfaceStore } from '@/store/interface'
import UiBouton from '@/components/ui/UiBouton.vue'
import Cloche from '@/components/notifications/Cloche.vue'

const route = useRoute()
const auth = useAuthStore()
const ui = useInterfaceStore()
const toast = useToast()
const ouvertureAdmin = ref(false)

async function ouvrirAdministration() {
  const fenetre = window.open('', '_blank') // ouverte tout de suite pour éviter le bloqueur de fenêtres
  ouvertureAdmin.value = true
  try {
    const { url } = await authApi.ouvrirSessionAdmin()
    if (fenetre) fenetre.location.href = `${ENV.backendUrl}${url}`
  } catch (e) {
    fenetre?.close()
    toast.erreur(e)
  } finally {
    ouvertureAdmin.value = false
  }
}
</script>

<template>
  <header class="barre">
    <button type="button" class="btn btn-fantome btn-icone burger" aria-label="Ouvrir le menu" @click="ui.ouvrirMenuMobile">
      <i class="bi bi-list" aria-hidden="true" />
    </button>

    <div class="position">
      <span v-if="route.meta.section" class="section">{{ route.meta.section }}</span>
      <i v-if="route.meta.section" class="bi bi-chevron-right separateur" aria-hidden="true" />
      <span class="titre">{{ route.meta.titre }}</span>
    </div>

    <div class="actions">
      <Cloche />
      <UiBouton v-if="auth.estAdministrateur" icone="sliders" aria-label="Administration Django" :chargement="ouvertureAdmin" @click="ouvrirAdministration">
        <span class="texte-bouton">Administration Django</span>
      </UiBouton>
      <UiBouton variante="fantome" icone="box-arrow-right" class="deconnexion" aria-label="Se déconnecter" @click="auth.seDeconnecter">
        <span class="texte-bouton">Se déconnecter</span>
      </UiBouton>
    </div>
  </header>
</template>

<style scoped>
.barre {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: var(--e3);
  height: var(--hauteur-barre);
  padding: 0 var(--e6);
  background: var(--surface);
  border-bottom: 1px solid var(--bordure);
}
.burger { display: none; }
.position { display: flex; align-items: center; gap: var(--e2); min-width: 0; font-size: var(--taille-s); }
.section { color: var(--texte-doux); }
.separateur { font-size: 0.7rem; color: var(--texte-leger); }
.titre { font-weight: 600; color: var(--marine); }
.actions { display: flex; align-items: center; gap: var(--e2); margin-left: auto; }
.deconnexion { color: var(--danger); }
.deconnexion:hover:not(:disabled) { background: var(--danger-pale); color: var(--danger); }

@media (max-width: 900px) {
  .barre { padding: 0 var(--e4); }
  .burger { display: inline-flex; }
  .texte-bouton { display: none; } /* icônes seules sur mobile */
}
</style>
