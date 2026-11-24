<!--
  Descriptions d'un Projet / Commune (propres à ce projet).
  Il faut d'abord choisir une affaire, une prestation et un projet.
  La somme de leurs quantités devient automatiquement la quantité du projet.
  lecture (Mes marchés) : consultation seulement.
-->
<script setup lang="ts">
import { useAuthStore } from '@/store/auth'
import { computed, ref } from 'vue'
import { descriptionsApi } from '@/api'
import { useEdition } from '@/composables/useEdition'
import type { Affaire, ChampFormulaire, Colonne, DescriptionProjet, Prestation, Projet } from '@/types'
import { formatNombre } from '@/utils/format'
import FormulaireModale from '@/components/formulaires/FormulaireModale.vue'
import TableauDonnees from '@/components/ui/TableauDonnees.vue'
import StatutSuivi from './StatutSuivi.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import { LIGNES_PAR_PAGE_MARCHE } from './constantes'

const props = defineProps<{
  affaire: Affaire | null
  prestation: Prestation | null
  projet: Projet | null
  lecture?: boolean
}>()
/** Une description a changé : la quantité du projet est à relire */
const emit = defineEmits<{ modifie: [] }>()

const tableau = ref<{ recharger: () => void } | null>(null)
const edition = useEdition(
  descriptionsApi,
  {
    nom: 'description',
    feminin: true,
    messageSuppression:
      'Sa ligne sera aussi retirée des feuilles si elle est vide. Si des données y ont déjà été saisies, la suppression sera refusée.',
    valeursCreation: () => ({ projet: props.projet?.id }),
    preparer: (d) => ({ quantite: d.quantite === null ? '' : Number(d.quantite) }),
  },
  () => {
    tableau.value?.recharger()
    emit('modifie')
  },
)

const inactif = computed(() =>
  !props.affaire
    ? { titre: 'Choisissez une affaire', texte: 'Puis une prestation et un projet / une commune.' }
    : !props.prestation
      ? { titre: 'Choisissez une prestation', texte: 'Puis un projet / une commune.' }
      : !props.projet
        ? { titre: 'Choisissez un projet / une commune', texte: 'Ses descriptions apparaîtront ici.' }
        : null,
)

const unite = computed(() => props.projet?.unite || props.prestation?.unite || '')

const colonnes = computed<Colonne[]>(() => [
  { cle: 'numero', libelle: 'ID', triable: true, largeur: '52px' },
  { cle: 'nom', libelle: 'Description', triable: true },
  { cle: 'quantite', libelle: `Quantité${unite.value ? ` (${unite.value})` : ''}`, triable: true, alignement: 'droite' },
  { cle: 'temps', libelle: 'Temps' },
  { cle: 'statut', libelle: 'Statut' },
])

const champs = computed<ChampFormulaire[]>(() => [
  { cle: 'nom', libelle: 'Description', type: 'texte', requis: true, pleineLargeur: true },
  {
    cle: 'quantite', libelle: `Quantité${unite.value ? ` (${unite.value})` : ''}`, type: 'nombre',
    aide: 'Ajoutée automatiquement à la quantité du projet.',
  },
])

const titre = computed(() => (props.projet ? `Descriptions – ${props.projet.nom}` : 'Descriptions'))
// Paramètres > Autorisation : boutons affichés selon les droits
const auth = useAuthStore()
</script>

<template>
  <TableauDonnees
    ref="tableau"
    :taille-page="LIGNES_PAR_PAGE_MARCHE"
    :titre="titre"
    icone="card-checklist"
    cle-stockage="marches-descriptions-projet"
    :source="descriptionsApi"
    :colonnes="colonnes"
    :parametres="{ projet: projet?.id ?? '' }"
    :inactif="inactif"
    :deplacable="!lecture"
    :cliquable="false"
    placeholder-recherche="Rechercher une description"
    vide-titre="Aucune description pour ce projet"
    :vide-texte="lecture ? undefined : 'Ajoutez les descriptions et leurs quantités : leur somme devient la quantité du projet.'"
  >
    <template #actions>
      <span v-if="projet" class="total" title="Quantité du projet = somme des descriptions">
        Total : {{ formatNombre(projet.quantite) }} {{ unite }}
      </span>
      <UiBouton v-if="!lecture && !inactif && auth.peut('creer', 'marches_descriptions')" variante="secondaire" petit icone="plus-lg" @click="edition.ouvrir()">
        Nouvelle description
      </UiBouton>
    </template>
    <template #cellule-nom="{ ligne }"><span class="gras">{{ ligne.nom }}</span></template>
    <template #cellule-quantite="{ ligne }">{{ formatNombre(ligne.quantite) }}</template>
    <template #cellule-temps="{ ligne }">
      <span :title="ligne.temps ? 'Temps de prod + contrôle + reprise (feuilles)' : undefined">{{ ligne.temps ? `${formatNombre(ligne.temps)} h` : '—' }}</span>
    </template>
    <template #cellule-statut="{ ligne }"><StatutSuivi :statut="ligne.statut" /></template>
    <template v-if="!lecture" #actions-ligne="{ ligne }">
      <UiBouton v-if="auth.peut('modifier', 'marches_descriptions')" variante="fantome" icone="pencil" petit icone-seule @click="edition.ouvrir(ligne as DescriptionProjet)">Modifier</UiBouton>
      <UiBouton v-if="auth.peut('supprimer', 'marches_descriptions')" variante="fantome" icone="trash" petit icone-seule @click="edition.supprimer(ligne as DescriptionProjet, ligne.nom)">Supprimer</UiBouton>
    </template>
  </TableauDonnees>

  <FormulaireModale
    v-model="edition.ouvert.value"
    :titre="edition.titre.value"
    :champs="champs"
    :valeurs-initiales="edition.valeursInitiales.value"
    :enregistrer="edition.enregistrer"
  />
</template>

<style scoped>
.total {
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  font-size: var(--taille-s);
  font-weight: 600;
  white-space: nowrap;
}
</style>
