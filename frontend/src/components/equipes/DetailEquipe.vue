<!--
  Équipe d'un responsable (modale) : ses collaborateurs directs.
  On peut descendre dans l'équipe d'un collaborateur, puis revenir en arrière.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { equipesApi } from '@/api'
import { useRequete } from '@/composables/useRequete'
import type { Colonne, EquipeDetail, Identifiant } from '@/types'
import { pluriel } from '@/utils/format'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'
import UiModale from '@/components/ui/UiModale.vue'
import UiTableau from '@/components/ui/UiTableau.vue'

const ouvert = defineModel<boolean>({ default: false })
const props = defineProps<{ equipeId: Identifiant | null }>()

const pile = ref<Identifiant[]>([]) // équipes visitées, pour le bouton « Retour »
const { donnees: equipe, chargement, erreur, executer } = useRequete(
  (id: Identifiant) => equipesApi.lire(id),
  null as EquipeDetail | null,
)

watch(ouvert, (valeur) => {
  if (valeur && props.equipeId) {
    pile.value = [props.equipeId]
    executer(props.equipeId)
  }
})

function descendre(id: Identifiant) {
  pile.value.push(id)
  executer(id)
}
function remonter() {
  pile.value.pop()
  executer(pile.value[pile.value.length - 1]!)
}

const titre = computed(() => (equipe.value ? `Équipe de ${equipe.value.responsable.nom_affiche}` : 'Équipe'))
const sousTitre = computed(() =>
  equipe.value
    ? [equipe.value.responsable.identifiant, equipe.value.poste, equipe.value.pole].filter(Boolean).join(', ')
    : undefined,
)

const colonnes: Colonne[] = [
  { cle: 'nom', libelle: 'Utilisateur' },
  { cle: 'code_barre', libelle: 'Employé' },
  { cle: 'poste', libelle: 'Poste' },
  { cle: 'pole', libelle: 'Pôle' },
  { cle: 'equipe', libelle: 'Son équipe', alignement: 'droite' },
]
</script>

<template>
  <UiModale v-model="ouvert" :titre="titre" :sous-titre="sousTitre" taille="grande">
    <div class="pile">
      <div class="ligne-entre">
        <UiBouton v-if="pile.length > 1" variante="fantome" icone="arrow-left" petit @click="remonter">Retour</UiBouton>
        <span v-else />
        <span v-if="equipe" class="badge badge-marine">{{ pluriel(equipe.nb_membres, 'collaborateur direct', 'collaborateurs directs') }}</span>
      </div>

      <UiTableau
        :colonnes="colonnes"
        :lignes="equipe?.membres ?? []"
        :chargement="chargement"
        :erreur="erreur"
        vide-titre="Aucun collaborateur direct"
      >
        <template #cellule-nom="{ ligne }"><UiEmploye :employe="ligne" sans-matricule /></template>
        <template #cellule-code_barre="{ ligne }"><span class="identifiant">{{ ligne.identifiant }}</span></template>
        <template #cellule-poste="{ ligne }">{{ ligne.postes[0]?.poste_nom || '—' }}</template>
        <template #cellule-pole="{ ligne }">{{ ligne.postes[0]?.pole || '—' }}</template>
        <template #cellule-equipe="{ ligne }">
          <UiBouton v-if="ligne.nb_subordonnes" variante="fantome" petit icone="diagram-2" @click="descendre(ligne.id)">
            {{ ligne.nb_subordonnes }}
          </UiBouton>
          <span v-else class="texte-doux">—</span>
        </template>
      </UiTableau>
    </div>
  </UiModale>
</template>

<style scoped>
.identifiant { font-weight: 600; color: var(--marine); white-space: nowrap; }
</style>
