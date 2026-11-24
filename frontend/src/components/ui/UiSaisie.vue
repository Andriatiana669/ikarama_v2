<!-- Zone de saisie texte / nombre / date / zone multiligne. -->
<script setup lang="ts">
const modele = defineModel<string | number | null>()
withDefaults(
  defineProps<{
    type?: 'text' | 'number' | 'date' | 'time' | 'email' | 'search'
    multiligne?: boolean
    placeholder?: string
    invalide?: boolean
    desactive?: boolean
  }>(),
  { type: 'text' },
)
</script>

<template>
  <textarea
    v-if="multiligne"
    v-model="modele as any"
    class="saisie"
    :placeholder="placeholder"
    :aria-invalid="invalide || undefined"
    :disabled="desactive"
  />
  <input
    v-else
    v-model="modele"
    class="saisie"
    :type="type"
    :placeholder="placeholder"
    :aria-invalid="invalide || undefined"
    :disabled="desactive"
  />
</template>
