<!--
  Fenêtre modale. Se ferme avec Échap ou le fond (sauf si `bloquante`).
  <UiModale v-model="ouverte" titre="Nouvelle équipe"> ... <template #pied>...</template></UiModale>
-->
<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { onKeyStroke } from '@vueuse/core'

const ouverte = defineModel<boolean>({ default: false })
const props = withDefaults(
  defineProps<{ titre: string; sousTitre?: string; taille?: 'petite' | 'moyenne' | 'grande'; bloquante?: boolean }>(),
  { taille: 'moyenne' },
)

const boite = ref<HTMLElement | null>(null)
let focusPrecedent: HTMLElement | null = null

const fermer = () => {
  if (!props.bloquante) ouverte.value = false
}

onKeyStroke('Escape', () => ouverte.value && fermer())

watch(ouverte, async (valeur) => {
  document.body.style.overflow = valeur ? 'hidden' : ''
  if (valeur) {
    focusPrecedent = document.activeElement as HTMLElement
    await nextTick()
    const premier = boite.value?.querySelector<HTMLElement>('input, select, textarea, button:not(.fermer)')
    ;(premier ?? boite.value)?.focus()
  } else {
    focusPrecedent?.focus?.()
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modale">
      <div v-if="ouverte" class="voile" @mousedown.self="fermer">
        <section
          ref="boite"
          class="boite carte"
          :class="`boite-${taille}`"
          role="dialog"
          aria-modal="true"
          :aria-label="titre"
          tabindex="-1"
        >
          <header class="carte-entete">
            <div>
              <h2>{{ titre }}</h2>
              <p v-if="sousTitre" class="texte-doux texte-petit">{{ sousTitre }}</p>
            </div>
            <button v-if="!bloquante" class="btn btn-fantome btn-icone fermer" type="button" aria-label="Fermer" @click="fermer">
              <i class="bi bi-x-lg" aria-hidden="true" />
            </button>
          </header>
          <div class="corps"><slot /></div>
          <footer v-if="$slots.pied" class="pied"><slot name="pied" /></footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.voile {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: start center;
  padding: 8vh var(--e4) var(--e4);
  background: rgba(15, 36, 64, 0.45);
  overflow-y: auto;
}
.boite { width: 100%; box-shadow: var(--ombre-haute); }
.boite:focus { outline: none; }
.boite-petite { max-width: 440px; }
.boite-moyenne { max-width: 640px; }
.boite-grande { max-width: 960px; }
.corps { padding: var(--e5); }
.pied {
  display: flex;
  justify-content: flex-end;
  gap: var(--e2);
  padding: var(--e4) var(--e5);
  border-top: 1px solid var(--bordure);
  background: var(--surface-douce);
  border-radius: 0 0 var(--rayon-l) var(--rayon-l);
}
.modale-enter-active, .modale-leave-active { transition: opacity 140ms ease; }
.modale-enter-active .boite, .modale-leave-active .boite { transition: transform 140ms ease; }
.modale-enter-from, .modale-leave-to { opacity: 0; }
.modale-enter-from .boite { transform: translateY(8px); }
</style>
