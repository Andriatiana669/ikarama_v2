<!-- Onglets : <UiOnglets v-model="onglet" :onglets="[{ valeur: 'equipes', libelle: 'Équipes', icone: 'people' }]" /> -->
<script setup lang="ts">
const actif = defineModel<string>({ required: true })
defineProps<{ onglets: { valeur: string; libelle: string; icone?: string; compteur?: number }[] }>()
</script>

<template>
  <div class="onglets" role="tablist">
    <button
      v-for="onglet in onglets"
      :key="onglet.valeur"
      class="onglet"
      role="tab"
      type="button"
      :aria-selected="actif === onglet.valeur"
      @click="actif = onglet.valeur"
    >
      <i v-if="onglet.icone" :class="`bi bi-${onglet.icone}`" aria-hidden="true" />
      {{ onglet.libelle }}
      <span v-if="onglet.compteur !== undefined" class="badge">{{ onglet.compteur }}</span>
    </button>
  </div>
</template>
