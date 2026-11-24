<!-- Onglet « Équipes » : une ligne par responsable. Lecture seule (données de l'API RH). -->
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { equipesApi } from '@/api'
import { useListe } from '@/composables/useListe'
import type { Colonne, Equipe, Identifiant } from '@/types'
import UiEmploye from '@/components/ui/UiEmploye.vue'
import UiPagination from '@/components/ui/UiPagination.vue'
import UiRecherche from '@/components/ui/UiRecherche.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTableau from '@/components/ui/UiTableau.vue'

const props = defineProps<{ pole?: string }>()
const emit = defineEmits<{ ouvrir: [id: Identifiant]; 'update:pole': [pole: string] }>()

const liste = useListe(equipesApi, { filtres: { pole: props.pole ?? '' }, tri: 'nom' })
const { lignes, total, page, taillePage, recherche, tri, filtres, chargement, erreur } = liste

// Le filtre de pôle est gardé dans l'adresse de la page (?pole=...)
watch(() => props.pole, (p) => (filtres.pole = p ?? ''))
watch(() => filtres.pole, (p) => emit('update:pole', String(p ?? '')))

const poles = ref<string[]>([])
onMounted(async () => (poles.value = (await equipesApi.poles()).map((p) => p.pole)))

const colonnes: Colonne[] = [
  { cle: 'nom', libelle: 'Responsable', triable: true },
  { cle: 'code_barre', libelle: 'Employé', triable: true },
  { cle: 'poste', libelle: 'Poste' },
  { cle: 'pole', libelle: 'Pôle' },
  { cle: 'nb_membres', libelle: 'Collaborateurs', alignement: 'droite', triable: true },
]
</script>

<template>
  <div class="carte">
    <div class="barre-outils">
      <UiRecherche v-model="recherche" placeholder="Responsable : matricule, nom ou prénom" />
      <UiSelect v-model="filtres.pole" :options="poles" placeholder="Tous les pôles" aria-label="Pôle" />
    </div>

    <UiTableau
      v-model:tri="tri"
      :colonnes="colonnes"
      :lignes="lignes"
      :chargement="chargement"
      :erreur="erreur"
      vide-titre="Aucune équipe trouvée"
      vide-texte="Une équipe apparaît dès qu'un employé a au moins un collaborateur direct dans l'API RH."
      cliquable
      @selection="(e: Equipe) => emit('ouvrir', e.id)"
    >
      <template #cellule-nom="{ ligne }"><UiEmploye :employe="ligne.responsable" sans-matricule /></template>
      <template #cellule-code_barre="{ ligne }"><span class="identifiant">{{ ligne.responsable.identifiant }}</span></template>
      <template #cellule-poste="{ ligne }">{{ ligne.poste || '—' }}</template>
      <template #cellule-pole="{ ligne }">{{ ligne.pole || '—' }}</template>
    </UiTableau>

    <UiPagination v-model:page="page" :total="total" :taille-page="taillePage" />
  </div>
</template>

<style scoped>
.barre-outils { display: flex; gap: var(--e3); flex-wrap: wrap; padding: var(--e4); border-bottom: 1px solid var(--bordure); }
.barre-outils .saisie { width: auto; min-width: 200px; }
.identifiant { font-weight: 600; color: var(--marine); white-space: nowrap; }
</style>
