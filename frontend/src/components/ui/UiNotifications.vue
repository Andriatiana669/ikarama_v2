<!-- Affiche les toasts (useToast) et la boîte de confirmation (useConfirmation). Monté une fois dans App.vue. -->
<script setup lang="ts">
import { useConfirmation } from '@/composables/useConfirmation'
import { useToast } from '@/composables/useToast'
import UiBouton from './UiBouton.vue'
import UiModale from './UiModale.vue'

const { toasts, fermer } = useToast()
const { etat, repondre } = useConfirmation()

const icones = { succes: 'check-circle-fill', erreur: 'exclamation-octagon-fill', info: 'info-circle-fill' }
</script>

<template>
  <div class="toasts" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="toast in toasts" :key="toast.id" class="toast" :class="`toast-${toast.ton}`" role="status">
        <i :class="`bi bi-${icones[toast.ton]}`" aria-hidden="true" />
        <span>{{ toast.message }}</span>
        <button class="fermer" type="button" aria-label="Fermer le message" @click="fermer(toast.id)">
          <i class="bi bi-x" aria-hidden="true" />
        </button>
      </div>
    </TransitionGroup>
  </div>

  <UiModale :model-value="etat.ouverte" :titre="etat.options.titre" taille="petite" bloquante>
    <p v-if="etat.options.message">{{ etat.options.message }}</p>
    <template #pied>
      <UiBouton @click="repondre(false)">{{ etat.options.libelleAnnuler || 'Annuler' }}</UiBouton>
      <UiBouton :variante="etat.options.danger ? 'danger' : 'primaire'" @click="repondre(true)">
        {{ etat.options.libelleConfirmer || 'Confirmer' }}
      </UiBouton>
    </template>
  </UiModale>
</template>

<style scoped>
.toasts {
  position: fixed;
  right: var(--e5);
  bottom: var(--e5);
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: var(--e2);
  max-width: min(420px, calc(100vw - 2rem));
}
.toast {
  display: flex;
  align-items: flex-start;
  gap: var(--e3);
  padding: var(--e3) var(--e4);
  border-radius: var(--rayon);
  background: var(--marine-fonce);
  color: #fff;
  font-size: var(--taille-s);
  box-shadow: var(--ombre-haute);
  border-left: 4px solid var(--marine-clair);
}
.toast-succes { border-left-color: #4cc38a; }
.toast-erreur { border-left-color: var(--rouge); }
.toast span { flex: 1; }
.fermer { border: none; background: none; color: inherit; opacity: 0.7; cursor: pointer; }
.fermer:hover { opacity: 1; }
.toast-enter-active, .toast-leave-active { transition: opacity 160ms ease, transform 160ms ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(6px); }
</style>
