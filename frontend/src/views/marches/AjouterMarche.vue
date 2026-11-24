<!--
  Marchés > Ajouter un marché : configuration complète.
  Sélection en cascade : Affaire > Prestation (cochée) > Projet/Commune > Descriptions.
-->
<script setup lang="ts">
import { useAuthStore } from '@/store/auth'
import { ref } from 'vue'
import { statutsApi, tachesApi } from '@/api'
import { useSelectionMarche } from '@/composables/useSelectionMarche'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import ChoixTacheTemps from '@/components/marches/ChoixTacheTemps.vue'
import FilSelection from '@/components/marches/FilSelection.vue'
import PanneauAffaires from '@/components/marches/PanneauAffaires.vue'
import PanneauCatalogue from '@/components/marches/PanneauCatalogue.vue'
import PanneauDescriptions from '@/components/marches/PanneauDescriptions.vue'
import PanneauPrestations from '@/components/marches/PanneauPrestations.vue'
import PanneauProjets from '@/components/marches/PanneauProjets.vue'

const s = useSelectionMarche()
const { affaireId, prestationId, projetId, tacheId, affaire, prestation, projet } = s
/** Tâche dont le temps est affiché dans Affaires, Prestations et Projets */
const tacheTemps = ref<{ id: number; nom: string } | null>(null)
// Rôles des statuts (un seul statut par rôle)
const ROLES_STATUT = [
  { cle: 'par_defaut', colonne: 'Par défaut', libelle: 'Par défaut (donné aux nouvelles lignes des feuilles)', role: 'par défaut' },
  { cle: 'prioritaire_pointage', colonne: 'Prioritaire au pointage', libelle: 'Prioritaire au pointage (ses affaires sont proposées en premier)', role: 'prioritaire au pointage' },
  { cle: 'active_note_rendement', colonne: 'Active la note de rendement', libelle: 'Active la note de rendement (quand toutes les descriptions du projet ont ce statut)', role: 'qui active la note de rendement' },
  { cle: 'avancement_complet', colonne: 'Avancement 100 %', libelle: 'Avancement 100 % (donné quand une ligne atteint 100 %)', role: 'des lignes à 100 %' },
  { cle: 'en_train_de_faire', colonne: 'En train de faire', libelle: 'En train de faire (Planning Projet : les lignes à ce statut disent ce que fait la personne)', role: '« en train de faire »' },
] as const

// Une description change la quantité du projet : on relit le projet et la liste des projets
const versionProjets = ref(0)
function apresDescription() {
  s.chargerProjet()
  versionProjets.value++
}
const retirer = (niveau: 'affaire' | 'prestation' | 'projet') =>
  niveau === 'affaire' ? (affaireId.value = null) : niveau === 'prestation' ? (prestationId.value = null) : (projetId.value = null)
// Paramètres > Autorisation : chaque panneau s'affiche avec le droit « Voir » de son module
const auth = useAuthStore()
</script>

<template>
  <div class="page page-large">
    <EnTetePage
      titre="Ajouter un marché"
      description="Choisissez une affaire, cochez ses prestations, puis ajoutez les projets / communes et leurs descriptions."
    />
    <div class="barre-selection">
      <FilSelection :affaire="affaire" :prestation="prestation" :projet="projet" @retirer="retirer" />
      <ChoixTacheTemps v-model="tacheId" @tache="tacheTemps = $event" />
    </div>

    <div class="marche">
      <div class="zone-affaires"><PanneauAffaires v-model:selection="affaireId" :tache="tacheTemps" @modifie="s.chargerAffaire" /></div>
      <div class="zone-prestations">
        <PanneauPrestations v-model:selection="prestationId" :tache="tacheTemps" :affaire="affaire" @modifie="s.chargerPrestation" />
      </div>
      <div class="zone-projets">
        <PanneauProjets v-if="auth.peut('voir', 'marches_projets')" v-model:selection="projetId" :tache="tacheTemps" :affaire="affaire" :prestation="prestation" :version="versionProjets" @modifie="s.chargerProjet" />
      </div>
      <div class="zone-descriptions">
        <PanneauDescriptions v-if="auth.peut('voir', 'marches_descriptions')" :affaire="affaire" :prestation="prestation" :projet="projet" @modifie="apresDescription" />
      </div>
      <div class="zone-taches">
        <PanneauCatalogue v-if="auth.peut('voir', 'marches_taches')" titre="Tâches" module="marches_taches" icone="list-task" nom="tâche" feminin :api="tachesApi" cle-stockage="marches-taches" avec-type
          vide-texte="Les tâches seront proposées lors du pointage." />
      </div>
      <div class="zone-statuts">
        <PanneauCatalogue v-if="auth.peut('voir', 'marches_statuts')" titre="Statuts" module="marches_statuts" icone="flag" nom="statut" :api="statutsApi" cle-stockage="marches-statuts" avec-couleur :roles-uniques="ROLES_STATUT"
          vide-texte="Les statuts seront proposés lors du pointage." />
      </div>
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
    'descriptions taches'
    'statuts statuts'; /* pleine largeur : ses colonnes de rôles restent visibles */
  gap: var(--e4);
  align-items: start;
}
.marche > div { min-width: 0; } /* sinon un tableau large élargit toute la page */
.zone-affaires { grid-area: affaires; }
.zone-prestations { grid-area: prestations; }
.zone-projets { grid-area: projets; }
.zone-descriptions { grid-area: descriptions; }
.zone-taches { grid-area: taches; }
.zone-statuts { grid-area: statuts; }
@media (max-width: 1200px) {
  .marche { grid-template-columns: 1fr; grid-template-areas: 'affaires' 'prestations' 'projets' 'descriptions' 'taches' 'statuts'; }
}
</style>
