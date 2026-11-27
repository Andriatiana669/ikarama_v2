<!-- Projets / Communes d'une affaire, pour une prestation cochée. Un clic ouvre ses Descriptions. -->
<script setup lang="ts">
import { useAuthStore } from '@/store/auth'
import { computed, ref, watch } from 'vue'
import { projetsApi } from '@/api'
import { useEdition } from '@/composables/useEdition'
import type { Affaire, ChampFormulaire, Colonne, Identifiant, Prestation, Projet } from '@/types'
import { formatDate, formatNombre } from '@/utils/format'
import FormulaireModale from '@/components/formulaires/FormulaireModale.vue'
import TableauDonnees from '@/components/ui/TableauDonnees.vue'
import StatutSuivi from './StatutSuivi.vue'
import { LIGNES_PAR_PAGE_MARCHE } from './constantes'
import UiBouton from '@/components/ui/UiBouton.vue'

const selection = defineModel<Identifiant | null | undefined>('selection')
const props = defineProps<{
  affaire: Affaire | null
  /** Tâche dont le temps est affiché (menu « Temps de la tâche ») */
  tache?: { id: number; nom: string } | null
  prestation: Prestation | null
  /** Mes marchés : consultation seulement */
  lecture?: boolean
  /** Change quand une description est modifiée : la quantité affichée est rechargée */
  version?: number
}>()
const emit = defineEmits<{ ligne: [projet: Projet]; modifie: [] }>()

const tableau = ref<{ recharger: () => void } | null>(null)
const edition = useEdition(
  projetsApi,
  {
    nom: 'projet / commune',
    messageSuppression:
      'Ses descriptions seront supprimées, et leurs lignes retirées des feuilles si elles sont vides. Si des données y ont déjà été saisies, la suppression sera refusée.',
    valeursCreation: () => ({ affaire: props.affaire?.id, prestation: props.prestation?.id }),
  },
  () => {
    tableau.value?.recharger()
    emit('modifie')
  },
)

watch(() => props.version, () => tableau.value?.recharger())

const inactif = computed(() =>
  !props.affaire
    ? { titre: 'Choisissez une affaire', texte: 'Cliquez sur une affaire, puis sur une de ses prestations cochées.' }
    : !props.prestation
      ? { titre: 'Choisissez une prestation', texte: 'Cliquez sur une prestation cochée pour cette affaire.' }
      : null,
)

const unite = computed(() => props.prestation?.unite ?? '')

const colonnes = computed<Colonne[]>(() => [
  { cle: 'numero', libelle: 'ID', triable: true, largeur: '52px' },
  { cle: 'nom', libelle: 'Nom projet / commune', triable: true },
  { cle: 'quantite', libelle: `Quantité${unite.value ? ` (${unite.value})` : ''}`, triable: true, alignement: 'droite' },
  { cle: 'rendement_valeur', libelle: 'Rendement objectif / j', alignement: 'droite' },
  { cle: 'date_livraison', libelle: 'Date de livraison', triable: true },
  // Report DT : surface saisie et linéaire total calculé (somme des quantités linéaires)
  ...(props.affaire?.report_dt ? [
    { cle: 'surface_m2', libelle: 'Surface (m²)', alignement: 'droite' as const },
    { cle: 'lineaire_total', libelle: 'Linéaire total (ML)', alignement: 'droite' as const },
  ] : []),
  { cle: 'statut', libelle: 'Statut' },
  { cle: 'temps', libelle: 'Temps' },
  ...(props.tache ? [{ cle: 'temps_tache', libelle: `Temps « ${props.tache.nom} »` }] : []),
  { cle: 'nb_descriptions', libelle: 'Descriptions', alignement: 'droite', masqueeParDefaut: true },
])

const champs = computed<ChampFormulaire[]>(() => [
  { cle: 'nom', libelle: 'Nom du projet / de la commune', type: 'texte', requis: true, pleineLargeur: true,
    aide: 'La quantité se calcule toute seule : c’est la somme des quantités de ses descriptions.' },
  {
    cle: 'rendement', libelle: 'Rendement objectif par jour', type: 'select', requis: true,
    options: (props.prestation?.rendements ?? []).map((r, i) => ({
      valeur: r.id,
      libelle: `Objectif ${i + 1} : ${formatNombre(r.valeur)} ${unite.value} / j`,
    })),
  },
  { cle: 'date_livraison', libelle: 'Date de livraison', type: 'date', requis: true },
  ...(props.affaire?.report_dt ? [{
    cle: 'surface_m2', libelle: 'Surface (m²)', type: 'nombre' as const,
    aide: 'Report DT : arrondie à 2 décimales, peut rester vide. Le linéaire total est la somme des quantités linéaires des descriptions ; la Quantité de chaque description en est calculée.',
  }] : []),
])

const titre = computed(() => (props.prestation ? `Projets / Communes – ${props.prestation.nom}` : 'Projets / Communes'))
// Paramètres > Autorisation : boutons affichés selon les droits
const auth = useAuthStore()
</script>

<template>
  <TableauDonnees
    ref="tableau"
    :taille-page="LIGNES_PAR_PAGE_MARCHE"
    v-model:selection="selection"
    :titre="titre"
    icone="geo-alt"
    cle-stockage="marches-projets"
    :source="projetsApi"
    :colonnes="colonnes"
    :parametres="{ affaire: affaire?.id ?? '', prestation: prestation?.id ?? '', tache: tache?.id ?? '' }"
    :inactif="inactif"
    :deplacable="!lecture"
    placeholder-recherche="Nom du projet"
    vide-titre="Aucun projet / commune"
    vide-texte="Ajoutez les projets ou communes de cette prestation."
    @ligne="(p: Projet) => emit('ligne', p)"
  >
    <template #actions>
      <UiBouton v-if="!inactif && !lecture && auth.peut('creer', 'marches_projets')" variante="secondaire" petit icone="plus-lg" @click="edition.ouvrir()">Nouveau projet</UiBouton>
    </template>
    <template #cellule-surface_m2="{ ligne }">{{ ligne.surface_m2 === null ? '—' : formatNombre(ligne.surface_m2) }}</template>
    <template #cellule-lineaire_total="{ ligne }">{{ ligne.lineaire_total === null ? '—' : formatNombre(ligne.lineaire_total) }}</template>
    <template #cellule-nom="{ ligne }"><span class="gras">{{ ligne.nom }}</span></template>
    <template #cellule-quantite="{ ligne }">
      <span title="Somme des quantités des descriptions">{{ formatNombre(ligne.quantite) }}</span>
    </template>
    <template #cellule-rendement_valeur="{ ligne }">{{ formatNombre(ligne.rendement_valeur) }}</template>
    <template #cellule-date_livraison="{ ligne }">{{ formatDate(ligne.date_livraison) }}</template>
    <template #cellule-statut="{ ligne }"><StatutSuivi :statut="ligne.statut" /></template>
    <template #cellule-temps_tache="{ ligne }">
      <span class="temps-tache">{{ ligne.temps_tache && Number(ligne.temps_tache) ? `${formatNombre(ligne.temps_tache)} h` : '—' }}</span>
    </template>
    <template #cellule-temps="{ ligne }">
      <span :title="ligne.temps ? 'Temps de prod + contrôle + reprise (feuilles)' : undefined">{{ ligne.temps ? `${formatNombre(ligne.temps)} h` : '—' }}</span>
    </template>
    <template v-if="!lecture" #actions-ligne="{ ligne }">
      <UiBouton v-if="auth.peut('modifier', 'marches_projets')" variante="fantome" icone="pencil" petit icone-seule @click="edition.ouvrir(ligne)">Modifier</UiBouton>
      <UiBouton v-if="auth.peut('supprimer', 'marches_projets')" variante="fantome" icone="trash" petit icone-seule @click="edition.supprimer(ligne, ligne.nom)">Supprimer</UiBouton>
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
.temps-tache { color: var(--marine-clair); font-weight: 600; }
</style>
