<!-- Liste déroulante. options = [{ valeur, libelle }] ou simple liste de textes. -->
<script setup lang="ts">
import { computed } from 'vue'
import type { Option } from '@/types'

const modele = defineModel<string | number | boolean | null>()
const props = defineProps<{
  options: (Option | string)[]
  placeholder?: string
  invalide?: boolean
  desactive?: boolean
}>()

// null et '' affichent tous deux l'option vide (placeholder)
const valeur = computed({
  get: () => modele.value ?? '',
  set: (v) => (modele.value = v),
})

const liste = computed<Option[]>(() =>
  props.options.map((o) => (typeof o === 'string' ? { valeur: o, libelle: o } : o)),
)
</script>

<template>
  <select v-model="valeur" class="saisie" :aria-invalid="invalide || undefined" :disabled="desactive">
    <option v-if="placeholder !== undefined" :value="''">{{ placeholder }}</option>
    <option v-for="option in liste" :key="option.valeur" :value="option.valeur">{{ option.libelle }}</option>
  </select>
</template>
