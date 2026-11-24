<!--
  Filtres « Commentaires » et « Commentaires contrôle » des onglets du Rendement :
  avec / sans commentaire, et / ou le commentaire contient un texte. Seules les lignes concernées comptent.
-->
<script setup lang="ts">
export interface ChoixCommentaires {
  commentaires_etat: '' | 'avec' | 'sans'
  commentaires_texte: string
  commentaires_controle_etat: '' | 'avec' | 'sans'
  commentaires_controle_texte: string
}
const choix = defineModel<ChoixCommentaires>({ required: true })
const COLONNES = [
  { etat: 'commentaires_etat', texte: 'commentaires_texte', libelle: 'Commentaires' },
  { etat: 'commentaires_controle_etat', texte: 'commentaires_controle_texte', libelle: 'Commentaires contrôle' },
] as const
</script>

<template>
  <div class="filtres-commentaires">
    <div v-for="c in COLONNES" :key="c.etat" class="filtre" role="group" :aria-label="c.libelle">
      <span class="mini-titre"><i class="bi bi-chat-left-text" aria-hidden="true" /> {{ c.libelle }}</span>
      <select v-model="choix[c.etat]" class="saisie" :aria-label="`${c.libelle} : avec ou sans`">
        <option value="">Tous</option>
        <option value="avec">Avec commentaire</option>
        <option value="sans">Sans commentaire</option>
      </select>
      <input v-model="choix[c.texte]" class="saisie" type="search" :placeholder="'Contient…'" :disabled="choix[c.etat] === 'sans'"
        :aria-label="`${c.libelle} : contient`" />
    </div>
  </div>
</template>

<style scoped>
.filtres-commentaires { display: flex; flex-wrap: wrap; gap: var(--e3); width: 100%; }
.filtre { display: grid; grid-template-columns: 160px 170px minmax(140px, 1fr); align-items: center; gap: var(--e2); flex: 1; min-width: 360px; }
.mini-titre { font-size: var(--taille-xs); color: var(--texte-doux); font-weight: 600; white-space: nowrap; }
</style>
