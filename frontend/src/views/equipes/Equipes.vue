<!--
  Page Équipes, en lecture seule : tout vient de l'API RH (pôle et responsable N+1 des employés).
  Une équipe = un responsable et ses collaborateurs directs.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Identifiant } from '@/types'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiOnglets from '@/components/ui/UiOnglets.vue'
import DetailEquipe from '@/components/equipes/DetailEquipe.vue'
import ListeEquipes from '@/components/equipes/ListeEquipes.vue'
import ListePoles from '@/components/equipes/ListePoles.vue'
import Organigramme from '@/components/equipes/Organigramme.vue'

const route = useRoute()
const router = useRouter()

const ONGLETS = [
  { valeur: 'equipes', libelle: 'Équipes', icone: 'people' },
  { valeur: 'poles', libelle: 'Pôles', icone: 'diagram-2' },
  { valeur: 'organigramme', libelle: 'Organigramme', icone: 'diagram-3' },
]

// Onglet et pôle gardés dans l'adresse (?onglet=equipes&pole=...) : partageables
const changerQuery = (modif: Record<string, string | undefined>) =>
  router.replace({ query: { ...route.query, ...modif } })

const onglet = computed({
  get: () => (ONGLETS.some((o) => o.valeur === route.query.onglet) ? String(route.query.onglet) : 'equipes'),
  set: (valeur) => changerQuery({ onglet: valeur }),
})
const pole = computed({
  get: () => (route.query.pole ? String(route.query.pole) : ''),
  set: (valeur) => changerQuery({ pole: valeur || undefined }),
})

const voirEquipesDuPole = (p: string) => changerQuery({ onglet: 'equipes', pole: p })

const detailOuvert = ref(false)
const equipeId = ref<Identifiant | null>(null)
function ouvrirEquipe(id: Identifiant) {
  equipeId.value = id
  detailOuvert.value = true
}
</script>

<template>
  <div class="page">
    <EnTetePage
      titre="Équipes"
      description="Calculées automatiquement depuis l'API RH : une équipe regroupe un responsable et ses collaborateurs directs."
    />
    <UiOnglets v-model="onglet" :onglets="ONGLETS" class="onglets-page" />

    <ListeEquipes v-if="onglet === 'equipes'" v-model:pole="pole" @ouvrir="ouvrirEquipe" />
    <ListePoles v-else-if="onglet === 'poles'" @voir-equipes="voirEquipesDuPole" />
    <Organigramme v-else @ouvrir="ouvrirEquipe" />

    <DetailEquipe v-model="detailOuvert" :equipe-id="equipeId" />
  </div>
</template>

<style scoped>
.onglets-page { margin-bottom: var(--e4); }
</style>
