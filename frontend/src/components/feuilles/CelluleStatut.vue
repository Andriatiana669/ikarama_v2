<!-- Cellule « Statut » : liste des statuts du Marché, chacun sur sa couleur. -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Identifiant, StatutResume } from '@/types'
import { couleurTexte } from '@/utils/format'
import UiMenuDeroulant from '@/components/ui/UiMenuDeroulant.vue'

const props = defineProps<{ valeur: StatutResume | null; options: StatutResume[]; desactive?: boolean }>()
const emit = defineEmits<{ choisir: [id: Identifiant | null]; edition: [enCours: boolean] }>()

const ancre = ref<HTMLElement | null>(null)
const ouvert = ref(false)
watch(ouvert, (valeur) => emit('edition', valeur))
function choisir(id: Identifiant | null, fermer: () => void) {
  fermer()
  if (id !== (props.valeur?.id ?? null)) emit('choisir', id)
}
</script>

<template>
  <button ref="ancre" type="button" class="cellule-statut" :disabled="desactive" :aria-label="`Statut : ${valeur?.nom ?? 'aucun'}`" @click="ouvert = !ouvert">
    <span v-if="valeur" class="pastille" :style="{ background: valeur.couleur, color: couleurTexte(valeur.couleur) }">{{ valeur.nom }}</span>
    <span v-else class="vide">{{ desactive ? '—' : 'Choisir…' }}</span>
  </button>
  <UiMenuDeroulant v-model="ouvert" :ancre="ancre" :largeur-min="180">
    <template #default="{ fermer }">
      <button type="button" class="option" @click="choisir(null, fermer)"><span class="vide">Aucun statut</span></button>
      <button v-for="s in options" :key="s.id" type="button" class="option" role="option" :aria-selected="s.id === valeur?.id" @click="choisir(s.id, fermer)">
        <span class="pastille" :style="{ background: s.couleur, color: couleurTexte(s.couleur) }">{{ s.nom }}</span>
      </button>
      <p v-if="!options.length" class="texte-doux texte-xs aucun">Ajoutez des statuts dans Marchés > Ajouter un marché.</p>
    </template>
  </UiMenuDeroulant>
</template>

<style scoped>
.cellule-statut { padding: 3px 4px; border: 1px solid transparent; border-radius: var(--rayon); background: none; cursor: pointer; min-width: 100px; text-align: left; }
.cellule-statut:hover:not(:disabled) { border-color: var(--bordure); background: var(--surface); }
.cellule-statut:disabled { cursor: default; }
.pastille { display: inline-block; padding: 2px 10px; border-radius: 999px; font-weight: 600; font-size: var(--taille-xs); white-space: nowrap; }
.vide { color: var(--texte-leger); }
.option { display: block; width: 100%; padding: var(--e2) var(--e3); border: none; background: none; cursor: pointer; text-align: left; }
.option:hover { background: var(--surface-douce); }
.aucun { padding: var(--e2) var(--e3); max-width: 220px; }
</style>
