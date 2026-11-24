<!--
  Cellule modifiable directement dans le tableau (texte, nombre, pourcentage).
  Enregistre en quittant le champ ou avec Entrée ; Échap annule.
-->
<script setup lang="ts">
import { ref, watch } from 'vue'
import UiProgression from '@/components/ui/UiProgression.vue'

const props = withDefaults(
  defineProps<{
    valeur: string | number | null
    type?: 'texte' | 'nombre' | 'pourcentage'
    desactive?: boolean
    libelle: string
  }>(),
  { type: 'texte' },
)
/** edition : la personne commence (true) ou arrête (false) de modifier la case */
const emit = defineEmits<{ enregistrer: [valeur: string]; edition: [enCours: boolean] }>()

const edition = ref(false)
const texte = ref('')
const champ = ref<HTMLInputElement | null>(null)
watch(() => props.valeur, () => !edition.value && (texte.value = props.valeur == null ? '' : String(props.valeur)), { immediate: true })

function ouvrir() {
  if (props.desactive) return
  edition.value = true
  emit('edition', true)
  setTimeout(() => {
    champ.value?.focus()
    champ.value?.select()
  }, 0)
}
function valider() {
  if (!edition.value) return
  edition.value = false
  emit('edition', false)
  const actuelle = props.valeur == null ? '' : String(props.valeur)
  if (texte.value.trim() !== actuelle) emit('enregistrer', texte.value.trim())
}
function annuler() {
  edition.value = false
  emit('edition', false)
  texte.value = props.valeur == null ? '' : String(props.valeur)
}
</script>

<template>
  <input
    v-if="edition"
    ref="champ"
    v-model="texte"
    class="saisie cellule-champ"
    :class="{ large: type === 'texte' }"
    type="text"
    :inputmode="type === 'texte' ? 'text' : 'decimal'"
    :aria-label="libelle"
    @blur="valider"
    @keydown.enter.prevent="valider"
    @keydown.esc.prevent="annuler"
  />
  <button v-else type="button" class="cellule-affichage" :disabled="desactive" :aria-label="`${libelle} : ${valeur ?? 'vide'}`" @click="ouvrir">
    <UiProgression v-if="type === 'pourcentage'" :valeur="Number(valeur) || 0" />
    <span v-else-if="valeur !== null && valeur !== ''" :class="{ tronquer: type === 'texte' }">{{ type === 'nombre' ? String(valeur).replace('.', ',') : valeur }}</span>
    <span v-else class="vide">{{ desactive ? '—' : '…' }}</span>
  </button>
</template>

<style scoped>
.cellule-affichage {
  display: inline-flex; align-items: center; width: 100%; min-height: 30px; max-width: 260px;
  padding: 3px 6px; border: 1px solid transparent; border-radius: var(--rayon); background: none; cursor: text; text-align: left; font-size: inherit;
}
.cellule-affichage:hover:not(:disabled) { border-color: var(--bordure); background: var(--surface); }
.cellule-affichage:disabled { cursor: default; }
.cellule-champ { height: 30px; width: 90px; padding: 0 6px; font-size: var(--taille-s); }
.cellule-champ.large { width: 220px; }
.vide { color: var(--texte-leger); }
</style>
