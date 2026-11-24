<!--
  Enveloppe d'un champ : libellé, aide et message d'erreur.
  <UiChamp libelle="Nom" requis :erreur="erreurs.nom"><UiSaisie v-model="nom" /></UiChamp>
-->
<script setup lang="ts">
import { useId } from 'vue'

defineProps<{ libelle?: string; aide?: string; erreur?: string | string[]; requis?: boolean }>()
const id = useId()
</script>

<template>
  <div class="champ">
    <label v-if="libelle" class="champ-libelle" :for="id">
      {{ libelle }}<span v-if="requis" class="requis" aria-hidden="true">*</span>
    </label>
    <slot :id="id" :invalide="!!erreur" />
    <span v-if="erreur" class="champ-erreur" role="alert">{{ Array.isArray(erreur) ? erreur[0] : erreur }}</span>
    <span v-else-if="aide" class="champ-aide">{{ aide }}</span>
  </div>
</template>
