<!--
  Marchés > Mes marchés : les affaires dont je suis responsable ou membre, et tout leur contenu
  (prestations cochées, projets / communes, descriptions), en consultation.
  Un responsable peut modifier les membres de son affaire (bouton « Membres »).
-->
<script setup lang="ts">
import { ref } from 'vue'
import { useSelectionMarche } from '@/composables/useSelectionMarche'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import ChoixTacheTemps from '@/components/marches/ChoixTacheTemps.vue'
import FilSelection from '@/components/marches/FilSelection.vue'
import PanneauAffaires from '@/components/marches/PanneauAffaires.vue'
import PanneauDescriptions from '@/components/marches/PanneauDescriptions.vue'
import PanneauPrestations from '@/components/marches/PanneauPrestations.vue'
import PanneauProjets from '@/components/marches/PanneauProjets.vue'

const s = useSelectionMarche()
const { affaireId, prestationId, projetId, tacheId, affaire, prestation, projet } = s
/** Tâche dont le temps est affiché dans Affaires, Prestations et Projets */
const tacheTemps = ref<{ id: number; nom: string } | null>(null)
const retirer = (niveau: 'affaire' | 'prestation' | 'projet') =>
  niveau === 'affaire' ? (affaireId.value = null) : niveau === 'prestation' ? (prestationId.value = null) : (projetId.value = null)
</script>

<template>
  <div class="page page-large">
    <EnTetePage
      titre="Mes marchés"
      description="Les affaires dont vous êtes responsable ou membre. En tant que responsable, vous pouvez en modifier les membres."
    />
    <div class="barre-selection">
      <FilSelection :affaire="affaire" :prestation="prestation" :projet="projet" @retirer="retirer" />
      <ChoixTacheTemps v-model="tacheId" @tache="tacheTemps = $event" />
    </div>

    <div class="marche">
      <div class="zone-affaires"><PanneauAffaires v-model:selection="affaireId" :tache="tacheTemps" mode="mes" @modifie="s.chargerAffaire" /></div>
      <div class="zone-prestations"><PanneauPrestations v-model:selection="prestationId" :tache="tacheTemps" :affaire="affaire" lecture /></div>
      <div class="zone-projets"><PanneauProjets v-model:selection="projetId" :tache="tacheTemps" :affaire="affaire" :prestation="prestation" lecture /></div>
      <div class="zone-descriptions"><PanneauDescriptions :affaire="affaire" :prestation="prestation" :projet="projet" lecture /></div>
    </div>
  </div>
</template>

<style scoped>
.page-large { max-width: none; }
.barre-selection { display: flex; align-items: center; gap: var(--e3); flex-wrap: wrap; margin-bottom: var(--e4); }
.barre-selection > :first-child { flex: 1; margin-bottom: 0; }
.marche {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  grid-template-areas:
    'affaires prestations'
    'affaires projets'
    'descriptions descriptions';
  gap: var(--e4);
  align-items: start;
}
.marche > div { min-width: 0; }
.zone-affaires { grid-area: affaires; }
.zone-prestations { grid-area: prestations; }
.zone-projets { grid-area: projets; }
.zone-descriptions { grid-area: descriptions; }
@media (max-width: 1200px) {
  .marche { grid-template-columns: 1fr; grid-template-areas: 'affaires' 'prestations' 'projets' 'descriptions'; }
}
</style>
