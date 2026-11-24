<!--
  Historique des modifications d'une feuille (ou d'une seule ligne), chargé seulement à l'ouverture.
-->
<script setup lang="ts">
import { computed } from 'vue'
import { historiqueFeuilleApi } from '@/api'
import type { Colonne, Identifiant } from '@/types'
import { formatDateHeure } from '@/utils/format'
import TableauDonnees from '@/components/ui/TableauDonnees.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'
import UiModale from '@/components/ui/UiModale.vue'

const ouvert = defineModel<boolean>({ default: false })
const props = defineProps<{ feuilleId: Identifiant; ligne?: { id: Identifiant; numero: number; description: string } | null }>()

const colonnes = computed<Colonne[]>(() => [
  { cle: 'date', libelle: 'Date', triable: true },
  ...(props.ligne ? [] : [{ cle: 'numero_ligne', libelle: 'Ligne' }, { cle: 'description', libelle: 'Description' }]),
  { cle: 'libelle', libelle: 'Colonne' },
  { cle: 'ancienne_valeur', libelle: 'Avant' },
  { cle: 'nouvelle_valeur', libelle: 'Après' },
  { cle: 'auteur', libelle: 'Par', cleExport: 'auteur_details.identifiant' },
])
const titre = computed(() => (props.ligne ? `Historique de la ligne ${props.ligne.numero} – ${props.ligne.description}` : 'Historique de la feuille'))
</script>

<template>
  <UiModale v-model="ouvert" :titre="titre" taille="grande">
    <TableauDonnees
      v-if="ouvert"
      titre="Modifications"
      icone="clock-history"
      cle-stockage="historique-feuille"
      :source="historiqueFeuilleApi"
      :colonnes="colonnes"
      :parametres="{ feuille: feuilleId, ligne: ligne?.id ?? '' }"
      :taille-page="20"
      :cliquable="false"
      placeholder-recherche="Colonne, valeur, personne…"
      vide-titre="Aucune modification pour l'instant"
    >
      <template #cellule-date="{ ligne: m }"><span class="nowrap">{{ formatDateHeure(m.date) }}</span></template>
      <template #cellule-ancienne_valeur="{ ligne: m }"><span class="avant">{{ m.ancienne_valeur || '—' }}</span></template>
      <template #cellule-nouvelle_valeur="{ ligne: m }"><span class="gras">{{ m.nouvelle_valeur || '—' }}</span></template>
      <template #cellule-auteur="{ ligne: m }"><UiEmploye :employe="m.auteur_details" sans-matricule /></template>
    </TableauDonnees>
  </UiModale>
</template>

<style scoped>
.nowrap { white-space: nowrap; }
.avant { color: var(--texte-doux); text-decoration: line-through; text-decoration-color: var(--texte-leger); }
</style>
