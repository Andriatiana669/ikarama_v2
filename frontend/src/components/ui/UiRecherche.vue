<!-- Champ de recherche avec délai (ne lance la recherche qu'après une pause de frappe). -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'

const modele = defineModel<string>({ default: '' })
withDefaults(defineProps<{ placeholder?: string }>(), { placeholder: 'Rechercher…' })

const texte = ref(modele.value)
watch(modele, (valeur) => (texte.value = valeur))
watchDebounced(texte, (valeur) => (modele.value = valeur.trim()), { debounce: 300 })
</script>

<template>
  <div class="recherche">
    <i class="bi bi-search" aria-hidden="true" />
    <input v-model="texte" class="saisie" type="search" :placeholder="placeholder" :aria-label="placeholder" />
  </div>
</template>

<style scoped>
.recherche { position: relative; min-width: 240px; flex: 1 1 260px; max-width: 380px; }
.recherche .bi { position: absolute; left: var(--e3); top: 50%; transform: translateY(-50%); color: var(--texte-leger); }
.recherche .saisie { padding-left: 2.1rem; }
</style>
