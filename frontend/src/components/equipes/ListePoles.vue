<!-- Onglet « Pôles » : déduits des postes des employés. Un clic montre les équipes du pôle. -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { equipesApi } from '@/api'
import { useRequete } from '@/composables/useRequete'
import type { Colonne, PoleRH } from '@/types'
import UiRecherche from '@/components/ui/UiRecherche.vue'
import UiTableau from '@/components/ui/UiTableau.vue'

const emit = defineEmits<{ 'voir-equipes': [pole: string] }>()

const { donnees: poles, chargement, erreur, executer } = useRequete(() => equipesApi.poles(), [] as PoleRH[])
onMounted(executer)

const recherche = ref('')
const lignes = computed(() =>
  poles.value
    .filter((p) => p.pole.toLowerCase().includes(recherche.value.toLowerCase()))
    .map((p) => ({ ...p, id: p.pole })),
)

const colonnes: Colonne[] = [
  { cle: 'pole', libelle: 'Pôle' },
  { cle: 'nb_employes', libelle: 'Employés', alignement: 'droite' },
  { cle: 'nb_equipes', libelle: 'Équipes', alignement: 'droite' },
]
</script>

<template>
  <div class="carte">
    <div class="barre-outils">
      <UiRecherche v-model="recherche" placeholder="Nom du pôle" />
    </div>
    <UiTableau
      :colonnes="colonnes"
      :lignes="lignes"
      :chargement="chargement"
      :erreur="erreur"
      vide-titre="Aucun pôle"
      vide-texte="Les pôles apparaissent après la synchronisation avec l'API RH."
      cliquable
      @selection="(p) => emit('voir-equipes', p.pole)"
    >
      <template #cellule-pole="{ ligne }"><span class="gras">{{ ligne.pole }}</span></template>
    </UiTableau>
  </div>
</template>

<style scoped>
.barre-outils { padding: var(--e4); border-bottom: 1px solid var(--bordure); }
</style>
