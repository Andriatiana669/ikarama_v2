<!-- Menu « Temps de la tâche » : ajoute une colonne avec le temps de cette tâche dans Affaires, Prestations et Projets. -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { pointagesApi } from '@/api'
import type { ElementCatalogue, Identifiant } from '@/types'

const modele = defineModel<Identifiant | null>({ default: null })
const emit = defineEmits<{ tache: [tache: { id: Identifiant; nom: string } | null] }>()

const taches = ref<ElementCatalogue[]>([])
onMounted(async () => {
  // Liste des tâches du pointage (le catalogue Marchés > Tâches peut être réservé)
  taches.value = (await pointagesApi.taches()) as unknown as ElementCatalogue[]
  signaler(modele.value)
})
function signaler(id: Identifiant | null) {
  const t = taches.value.find((x) => x.id === id)
  emit('tache', t ? { id: t.id, nom: t.nom } : null)
}
function changer(e: Event) {
  const valeur = (e.target as HTMLSelectElement).value
  const id = valeur ? Number(valeur) : null
  modele.value = id
  signaler(id) // la valeur du parent n'est pas encore à jour à cet instant
}
</script>

<template>
  <label class="choix-tache">
    <i class="bi bi-stopwatch" aria-hidden="true" />
    <span>Temps de la tâche</span>
    <select class="saisie" :value="modele ?? ''" @change="changer">
      <option value="">Aucune</option>
      <option v-for="t in taches" :key="t.id" :value="t.id">{{ t.nom }}</option>
    </select>
  </label>
</template>

<style scoped>
.choix-tache { display: inline-flex; align-items: center; gap: var(--e2); font-size: var(--taille-s); font-weight: 600; color: var(--marine); white-space: nowrap; }
.choix-tache .saisie { width: auto; min-width: 180px; height: 34px; font-weight: 400; }
</style>
