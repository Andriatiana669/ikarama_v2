<!-- Bouton « Synchronisation des données » des onglets du Rendement (Affaires et Prestations partagées). -->
<script setup lang="ts">
defineProps<{ actif: boolean }>()
defineEmits<{ basculer: [] }>()
</script>

<template>
  <button
    type="button"
    class="synchro"
    :class="{ actif }"
    :aria-pressed="actif"
    :title="actif
      ? 'Activée : les Affaires et Prestations cochées (et leurs recherches) sont les mêmes dans Globale, Evolution, Réel vs Objectif et Evaluation Employé. Cliquer pour désactiver.'
      : 'Désactivée : chaque onglet garde ses propres choix. Cliquer pour partager les Affaires et Prestations entre les onglets.'"
    @click="$emit('basculer')"
  >
    <i class="bi" :class="actif ? 'bi-link-45deg' : 'bi-arrow-repeat'" aria-hidden="true" />
    Synchronisation des données
    <span class="etat">{{ actif ? 'Activée' : 'Désactivée' }}</span>
  </button>
</template>

<style scoped>
.synchro { display: inline-flex; align-items: center; gap: var(--e2); height: 36px; padding: 0 var(--e3); border: 1px solid var(--bordure-forte); border-radius: var(--rayon); background: var(--surface); color: var(--texte); font-size: var(--taille-s); font-weight: 600; cursor: pointer; }
.synchro:hover { border-color: var(--marine-clair); }
.synchro .bi { font-size: 1.05rem; }
.etat { padding: 1px 8px; border-radius: 999px; background: var(--surface-douce); color: var(--texte-doux); font-size: var(--taille-xs); }
.synchro.actif { border-color: var(--marine); background: var(--marine); color: #fff; }
.synchro.actif .etat { background: rgba(255, 255, 255, 0.2); color: #fff; }
</style>
