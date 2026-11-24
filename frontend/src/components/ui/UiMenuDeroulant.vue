<!--
  Menu flottant rattaché à un élément (ancre). Affiché au-dessus de tout (Teleport),
  il n'est donc pas coupé par un tableau qui défile. Se ferme au clic dehors, à Échap ou au défilement.
  <button ref="ancre" @click="ouvert = !ouvert">…</button>
  <UiMenuDeroulant v-model="ouvert" :ancre="ancre"> … </UiMenuDeroulant>
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { onClickOutside, onKeyStroke } from '@vueuse/core'

const ouvert = defineModel<boolean>({ default: false })
const props = withDefaults(defineProps<{ ancre: HTMLElement | null; largeurMin?: number }>(), { largeurMin: 220 })

const menu = ref<HTMLElement | null>(null)
const position = ref({ top: 0, left: 0, minWidth: 0 })

function placer() {
  if (!props.ancre) return
  const r = props.ancre.getBoundingClientRect()
  const hauteur = menu.value?.offsetHeight ?? 260
  const enBas = window.innerHeight - r.bottom > hauteur + 8 || r.top < hauteur
  position.value = {
    top: enBas ? r.bottom + 4 : r.top - hauteur - 4,
    left: Math.min(r.left, window.innerWidth - Math.max(props.largeurMin, r.width) - 8),
    minWidth: Math.max(props.largeurMin, r.width),
  }
}

const fermer = () => (ouvert.value = false)
watch(ouvert, async (valeur) => {
  if (!valeur) return
  placer()
  await nextTick()
  placer()
})
const ancreRef = computed(() => props.ancre)
onClickOutside(menu, fermer, { ignore: [ancreRef] })
onKeyStroke('Escape', () => ouvert.value && fermer())
// Au défilement (page ou tableau), le menu suit son ancre ; il se ferme si l'ancre sort de l'écran
function surDefilement(e: Event) {
  if (!ouvert.value || menu.value?.contains(e.target as Node) || !props.ancre) return
  const r = props.ancre.getBoundingClientRect()
  if (r.bottom < 0 || r.top > window.innerHeight || r.right < 0 || r.left > window.innerWidth) fermer()
  else placer()
}
window.addEventListener('scroll', surDefilement, true)
window.addEventListener('resize', fermer)
onBeforeUnmount(() => {
  window.removeEventListener('scroll', surDefilement, true)
  window.removeEventListener('resize', fermer)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="ouvert"
      ref="menu"
      class="menu-deroulant carte"
      role="listbox"
      :style="{ top: `${position.top}px`, left: `${position.left}px`, minWidth: `${position.minWidth}px` }"
    >
      <slot :fermer="fermer" />
    </div>
  </Teleport>
</template>

<style scoped>
.menu-deroulant {
  position: fixed;
  z-index: 150;
  max-height: 280px;
  overflow-y: auto;
  padding: var(--e1) 0;
  box-shadow: var(--ombre-haute);
}
</style>
