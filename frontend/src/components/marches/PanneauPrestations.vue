<!--
  Prestations : catalogue commun. Une affaire choisie : ses prestations cochées s'affichent d'abord
  (le glisser-déposer, qui change l'ordre du catalogue, n'est possible que sans affaire choisie). Quand une affaire est choisie, une case permet de cocher
  les prestations concernées ; un clic sur une prestation cochée ouvre ses Projets/Communes.
-->
<script setup lang="ts">
import { useAuthStore } from '@/store/auth'
import { computed, ref } from 'vue'
import { affairesApi, prestationsApi } from '@/api'
import { useEdition } from '@/composables/useEdition'
import { useToast } from '@/composables/useToast'
import type { Affaire, ChampFormulaire, Colonne, Identifiant, Prestation } from '@/types'
import { formatNombre } from '@/utils/format'
import FormulaireModale from '@/components/formulaires/FormulaireModale.vue'
import ImportExcel from '@/components/ui/ImportExcel.vue'
import TableauDonnees from '@/components/ui/TableauDonnees.vue'
import StatutSuivi from './StatutSuivi.vue'
import { LIGNES_PAR_PAGE_MARCHE } from './constantes'
import UiBouton from '@/components/ui/UiBouton.vue'

const selection = defineModel<Identifiant | null | undefined>('selection')
const props = defineProps<{
  affaire: Affaire | null
  /** Tâche dont le temps est affiché (menu « Temps de la tâche ») */
  tache?: { id: number; nom: string } | null
  /** Mes marchés : seulement les prestations cochées de l'affaire, sans modification */
  lecture?: boolean
}>()
const emit = defineEmits<{ ligne: [prestation: Prestation]; modifie: [] }>()

const toast = useToast()
const tableau = ref<{ recharger: () => void } | null>(null)
const importOuvert = ref(false)
const recharger = () => {
  tableau.value?.recharger()
  emit('modifie')
}
const edition = useEdition(
  prestationsApi,
  {
    nom: 'prestation',
    feminin: true,
    // Les rendements s'éditent sous forme de liste de nombres
    preparer: (p) => ({ valeurs_rendement: p.rendements.map((r) => String(Number(r.valeur))) }),
  },
  recharger,
)

const colonnes = computed<Colonne[]>(() => [
  ...(props.affaire && !props.lecture ? [{ cle: 'cochee', libelle: 'Concernée', alignement: 'centre' as const, largeur: '80px' }] : []),
  { cle: 'id', libelle: 'ID', triable: true, largeur: '52px' },
  { cle: 'nom', libelle: 'Nom prestation', triable: true },
  { cle: 'rendements', libelle: 'Rendement objectif / j' },
  { cle: 'unite', libelle: 'Unité', triable: true },
  { cle: 'temps', libelle: 'Temps' },
  ...(props.tache ? [{ cle: 'temps_tache', libelle: `Temps « ${props.tache.nom} »` }] : []),
  ...(props.affaire ? [{ cle: 'statut', libelle: 'Statut' }] : []),
])

const filtres = computed<ChampFormulaire[]>(() =>
  props.affaire && !props.lecture
    ? [{ cle: 'cochees', libelle: 'Afficher', type: 'select', options: [{ valeur: '1', libelle: "Seulement celles de l'affaire" }], placeholder: 'Toutes les prestations' }]
    : [],
)

const champs: ChampFormulaire[] = [
  { cle: 'nom', libelle: 'Nom de la prestation', type: 'texte', requis: true },
  { cle: 'unite', libelle: 'Unité', type: 'texte', requis: true, placeholder: 'ex. fiches, pages, km' },
  {
    cle: 'valeurs_rendement', libelle: 'Rendements objectifs par jour', type: 'nombres', requis: true, pleineLargeur: true,
    placeholder: '/ jour', aide: 'Une ou plusieurs valeurs : elles seront proposées pour chaque projet.',
  },
]

async function cocher(prestation: Prestation, coche: boolean) {
  if (!props.affaire) return
  try {
    await affairesApi.cocherPrestation(props.affaire.id, prestation.id, coche)
    if (!coche && selection.value === prestation.id) selection.value = null
  } catch (e) {
    toast.erreur(e)
  }
  recharger()
}

function peutChoisir(prestation: Prestation) {
  if (!props.affaire) {
    toast.info("Choisissez d'abord une affaire.")
    return false
  }
  if (!prestation.cochee) {
    toast.info(`Cochez « ${prestation.nom} » pour cette affaire pour gérer ses projets.`)
    return false
  }
  return true
}
// Paramètres > Autorisation : boutons affichés selon les droits
const auth = useAuthStore()
</script>

<template>
  <TableauDonnees
    ref="tableau"
    :taille-page="LIGNES_PAR_PAGE_MARCHE"
    v-model:selection="selection"
    titre="Prestations"
    icone="clipboard-check"
    cle-stockage="marches-prestations"
    :source="prestationsApi"
    :colonnes="colonnes"
    :filtres="filtres"
    :parametres="lecture ? { affaire: affaire?.id ?? '', cochees: 1, tache: tache?.id ?? '' } : { affaire: affaire?.id ?? '', tache: tache?.id ?? '' }"
    :inactif="lecture && !affaire ? { titre: 'Choisissez une affaire', texte: 'Ses prestations apparaîtront ici.' } : null"
    :selectionnable="peutChoisir"
    :deplacable="!lecture && !affaire"
    placeholder-recherche="Nom ou unité"
    vide-titre="Aucune prestation"
    vide-texte="Les prestations forment un catalogue commun à toutes les affaires."
    @ligne="(p: Prestation) => emit('ligne', p)"
  >
    <template v-if="!lecture" #actions>
      <UiBouton v-if="auth.peut('importer', 'marches_prestations')" variante="secondaire" petit icone="file-earmark-arrow-up" @click="importOuvert = true">Importer</UiBouton>
      <UiBouton v-if="auth.peut('creer', 'marches_prestations')" variante="secondaire" petit icone="plus-lg" @click="edition.ouvrir()">Nouvelle prestation</UiBouton>
    </template>
    <template #cellule-cochee="{ ligne }">
      <input
        type="checkbox"
        class="coche"
        :checked="ligne.cochee"
        :disabled="!auth.peut('modifier', 'marches_affaires')"
        :aria-label="`${ligne.nom} concernée par l'affaire`"
        @click.stop
        @change="cocher(ligne, ($event.target as HTMLInputElement).checked)"
      />
    </template>
    <template #cellule-nom="{ ligne }">
      <span class="gras">{{ ligne.nom }}</span>
      <span v-if="ligne.nb_projets" class="badge badge-marine projets">{{ ligne.nb_projets }} projet(s)</span>
    </template>
    <template #cellule-rendements="{ ligne }">
      <span class="valeurs">
        <span v-for="r in ligne.rendements" :key="r.id" class="badge">{{ formatNombre(r.valeur) }}</span>
      </span>
    </template>
    <template #cellule-statut="{ ligne }"><StatutSuivi :statut="ligne.statut" /></template>
    <template #cellule-temps_tache="{ ligne }">
      <span class="temps-tache">{{ ligne.temps_tache && Number(ligne.temps_tache) ? `${formatNombre(ligne.temps_tache)} h` : '—' }}</span>
    </template>
    <template #cellule-temps="{ ligne }">
      <span :title="ligne.temps ? 'Temps de prod + contrôle + reprise (feuilles)' : undefined">{{ ligne.temps ? `${formatNombre(ligne.temps)} h` : '—' }}</span>
    </template>
    <template v-if="!lecture" #actions-ligne="{ ligne }">
      <UiBouton v-if="auth.peut('modifier', 'marches_prestations')" variante="fantome" icone="pencil" petit icone-seule @click="edition.ouvrir(ligne)">Modifier</UiBouton>
      <UiBouton v-if="auth.peut('supprimer', 'marches_prestations')" variante="fantome" icone="trash" petit icone-seule @click="edition.supprimer(ligne, ligne.nom)">Supprimer</UiBouton>
    </template>
  </TableauDonnees>

  <ImportExcel
    v-if="!lecture"
    v-model="importOuvert"
    titre="Importer des prestations"
    nom-modele="Modele_import_prestations"
    :source="prestationsApi"
    @importe="tableau?.recharger(); emit('modifie')"
  />
  <FormulaireModale
    v-model="edition.ouvert.value"
    :titre="edition.titre.value"
    :champs="champs"
    :valeurs-initiales="edition.valeursInitiales.value"
    :enregistrer="edition.enregistrer"
  />
</template>

<style scoped>
.coche { width: 16px; height: 16px; accent-color: var(--marine); cursor: pointer; }
.valeurs { display: inline-flex; flex-wrap: wrap; gap: 4px; }
.projets { margin-left: var(--e2); }
.temps-tache { color: var(--marine-clair); font-weight: 600; }
</style>
