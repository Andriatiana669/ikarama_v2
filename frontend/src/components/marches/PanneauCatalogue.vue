<!--
  Catalogue simple (un nom par ligne), commun à toutes les affaires : Tâches, Statuts…
  <PanneauCatalogue titre="Statuts" icone="flag" nom="statut" :api="statutsApi" cle-stockage="marches-statuts" />
-->
<script setup lang="ts">
import { ref } from 'vue'
import type { Parametres } from '@/api/ressource'
import { useEdition } from '@/composables/useEdition'
import { useToast } from '@/composables/useToast'
import type { ChampFormulaire, Colonne, ElementCatalogue, Identifiant, Page } from '@/types'
import { couleurTexte, formatDateHeure } from '@/utils/format'
import FormulaireModale from '@/components/formulaires/FormulaireModale.vue'
import TableauDonnees from '@/components/ui/TableauDonnees.vue'
import { LIGNES_PAR_PAGE_MARCHE } from './constantes'
import UiBouton from '@/components/ui/UiBouton.vue'
import { useAuthStore } from '@/store/auth'
import UiEmploye from '@/components/ui/UiEmploye.vue'

/** Option que plusieurs éléments peuvent avoir en même temps (Statuts : ignorer la description sans quantité) */
export interface OptionMultiple {
  cle: 'ignorer_sans_quantite'
  colonne: string
  libelle: string
}

export interface RoleUnique {
  cle: 'par_defaut' | 'prioritaire_pointage' | 'active_note_rendement' | 'avancement_complet' | 'en_train_de_faire'
  /** Titre de colonne */
  colonne: string
  /** Libellé de la case du formulaire */
  libelle: string
  /** « par défaut », « prioritaire au pointage »… (messages) */
  role: string
}

const props = withDefaults(
  defineProps<{
    titre: string
    icone: string
    /** Module de Paramètres > Autorisation (ex. marches_taches, marches_statuts) */
    module: string
    /** Nom d'un élément, ex. « tâche » */
    nom: string
    feminin?: boolean
    cleStockage: string
    api: {
      lister: (p?: Parametres) => Promise<Page<ElementCatalogue>>
      creer: (d: any) => Promise<ElementCatalogue>
      modifier: (id: Identifiant, d: any) => Promise<ElementCatalogue>
      supprimer: (id: Identifiant) => Promise<void>
      exporter: (p: Parametres, c: { cle: string; libelle: string }[], n: string) => Promise<void>
      reordonner: (ids: Identifiant[]) => Promise<void>
    }
    videTexte?: string
    /** Chaque élément a une couleur de fond (Statuts) */
    avecCouleur?: boolean
    /** Rôles détenus par un seul élément à la fois (Statuts : par défaut, prioritaire…) : une colonne de boutons radio */
    rolesUniques?: readonly RoleUnique[]
    /** Options que plusieurs éléments peuvent avoir (une colonne de cases à cocher) */
    optionsMultiples?: readonly OptionMultiple[]
    /** Tâches : type qui relie le temps pointé à une colonne des feuilles */
    avecType?: boolean
  }>(),
  { feminin: false },
)

const TYPES_TACHE = [
  { valeur: 'PRODUCTION', libelle: 'Production', aide: 'Employé + Temps de prod', classe: 'badge-marine' },
  { valeur: 'CONTROLE', libelle: 'Contrôle', aide: 'Contrôleur + Temps de contrôle', classe: 'badge-attention' },
  { valeur: 'REPRISE', libelle: 'Reprise', aide: 'Employé reprise + Temps de reprise', classe: 'badge-rouge' },
  { valeur: 'AUTRE', libelle: 'Autre', aide: 'rien n’est reporté dans la feuille', classe: '' },
]
const typeDe = (valeur?: string) => TYPES_TACHE.find((t) => t.valeur === valeur) ?? TYPES_TACHE[3]!

const tableau = ref<{ recharger: () => void } | null>(null)
const edition = useEdition(props.api, { nom: props.nom, feminin: props.feminin }, () => tableau.value?.recharger())
const majuscule = (t: string) => t.charAt(0).toUpperCase() + t.slice(1)

const colonnes: Colonne[] = [
  { cle: 'id', libelle: 'ID', triable: true, largeur: '52px' },
  { cle: 'nom', libelle: majuscule(props.nom), triable: true },
  ...(props.rolesUniques ?? []).map((r) => ({ cle: r.cle, libelle: r.colonne, alignement: 'centre' as const, largeur: '100px' })),
  ...(props.optionsMultiples ?? []).map((r) => ({ cle: r.cle, libelle: r.colonne, alignement: 'centre' as const, largeur: '110px' })),
  ...(props.avecType ? [{ cle: 'type', libelle: 'Type (colonne de la feuille)', cleExport: 'type_libelle' }] : []),
  { cle: 'cree_par', libelle: props.feminin ? 'Créée par' : 'Créé par', cleExport: 'cree_par_details', masqueeParDefaut: true },
  { cle: 'cree_le', libelle: props.feminin ? 'Créée le' : 'Créé le', triable: true, masqueeParDefaut: true },
]
const champs: ChampFormulaire[] = [
  { cle: 'nom', libelle: majuscule(props.nom), type: 'texte', requis: true, pleineLargeur: true },
  ...(props.avecCouleur
    ? [{ cle: 'couleur', libelle: 'Couleur de fond', type: 'couleur' as const, pleineLargeur: true, placeholder: `Aperçu du ${props.nom}` }]
    : []),
  ...(props.avecType
    ? [{
        cle: 'type', libelle: 'Type', type: 'select' as const, requis: true, pleineLargeur: true,
        options: TYPES_TACHE.map((t) => ({ valeur: t.valeur, libelle: `${t.libelle} – ${t.aide}` })),
        aide: 'Le temps pointé sur cette tâche est reporté dans la colonne correspondante des feuilles.',
      },
      {
        cle: 'plusieurs_descriptions', libelle: 'Plusieurs descriptions (le temps est partagé au prorata des quantités)',
        type: 'case' as const, pleineLargeur: true,
      },
      {
        cle: 'temps_projet', libelle: 'Ajouter au temps du projet (sans compter deux fois ce qui est déjà dans les feuilles)',
        type: 'case' as const, pleineLargeur: true,
      }]
    : []),
  ...(props.rolesUniques ?? []).map((r) => ({ cle: r.cle, libelle: r.libelle, type: 'case' as const, pleineLargeur: true })),
  ...(props.optionsMultiples ?? []).map((r) => ({ cle: r.cle, libelle: r.libelle, type: 'case' as const, pleineLargeur: true })),
]


const toast = useToast()
async function basculerUnique(ligne: ElementCatalogue, cle: RoleUnique['cle'], role: string) {
  const actif = !!ligne[cle]
  try {
    await props.api.modifier(ligne.id, { [cle]: !actif })
    toast.succes(actif ? `Plus aucun statut ${role}` : `« ${ligne.nom} » est le statut ${role}`)
  } catch (e) {
    toast.erreur(e)
  }
  tableau.value?.recharger()
}
async function basculerOption(ligne: ElementCatalogue, cle: OptionMultiple['cle']) {
  try {
    await props.api.modifier(ligne.id, { [cle]: !ligne[cle] })
  } catch (e) {
    toast.erreur(e)
  }
  tableau.value?.recharger()
}
// Paramètres > Autorisation : Marchés > Catalogues (par défaut, seul le superadmin modifie)
const auth = useAuthStore()
</script>

<template>
  <TableauDonnees
    ref="tableau"
    :taille-page="LIGNES_PAR_PAGE_MARCHE"
    :titre="titre"
    :icone="icone"
    :cle-stockage="cleStockage"
    :source="api"
    :colonnes="colonnes"
    :cliquable="false"
    deplacable
    :placeholder-recherche="`Rechercher un${feminin ? 'e' : ''} ${nom}`"
    :vide-titre="`Aucun${feminin ? 'e' : ''} ${nom}`"
    :vide-texte="videTexte"
  >
    <template #actions>
      <UiBouton v-if="auth.peut('creer', module)" variante="secondaire" petit icone="plus-lg" @click="edition.ouvrir()">
        Nouve{{ feminin ? "lle" : "au" }} {{ nom }}
      </UiBouton>
    </template>
    <template v-if="avecCouleur" #cellule-nom="{ ligne }">
      <span class="pastille-nom" :style="{ background: ligne.couleur, color: couleurTexte(ligne.couleur) }">{{ ligne.nom }}</span>
    </template>
    <template v-if="avecType" #cellule-type="{ ligne }">
      <span :class="['badge', typeDe(ligne.type).classe]" :title="typeDe(ligne.type).aide">{{ typeDe(ligne.type).libelle }}</span>
      <span class="texte-xs texte-doux aide-type">{{ typeDe(ligne.type).aide }}</span>
      <span v-if="ligne.plusieurs_descriptions" class="badge aide-type" title="Le pointage peut viser plusieurs descriptions d'un même projet">
        <i class="bi bi-diagram-2" aria-hidden="true" /> Plusieurs descriptions
      </span>
      <span v-if="ligne.temps_projet" class="badge aide-type" title="Son temps s'ajoute au Temps du Projet / Commune">
        <i class="bi bi-plus-circle" aria-hidden="true" /> Temps du projet
      </span>
    </template>
    <template v-for="r in rolesUniques ?? []" :key="r.cle" #[`cellule-${r.cle}`]="{ ligne }">
      <input
        type="radio"
        class="radio"
        :name="r.cle"
        :checked="!!ligne[r.cle]"
        :aria-label="`${ligne.nom} : ${r.role}`"
        :title="ligne[r.cle] ? 'Cliquer pour retirer' : r.libelle"
        @click.prevent="basculerUnique(ligne, r.cle, r.role)"
      />
    </template>
    <template v-for="r in optionsMultiples ?? []" :key="r.cle" #[`cellule-${r.cle}`]="{ ligne }">
      <input type="checkbox" class="radio" :checked="!!ligne[r.cle]" :aria-label="`${ligne.nom} : ${r.libelle}`" :title="r.libelle"
        :disabled="!auth.peut('modifier', module)" @click.prevent="basculerOption(ligne, r.cle)" />
    </template>
    <template #cellule-cree_par="{ ligne }"><UiEmploye :employe="ligne.cree_par_details" sans-matricule /></template>
    <template #cellule-cree_le="{ ligne }">{{ formatDateHeure(ligne.cree_le) }}</template>
    <template #actions-ligne="{ ligne }">
      <UiBouton v-if="auth.peut('modifier', module)" variante="fantome" icone="pencil" petit icone-seule @click="edition.ouvrir(ligne)">Modifier</UiBouton>
      <UiBouton v-if="auth.peut('supprimer', module)" variante="fantome" icone="trash" petit icone-seule @click="edition.supprimer(ligne, ligne.nom)">Supprimer</UiBouton>
    </template>
  </TableauDonnees>

  <FormulaireModale
    v-model="edition.ouvert.value"
    :titre="edition.titre.value"
    :champs="champs"
    :valeurs-initiales="edition.valeursInitiales.value"
    :enregistrer="edition.enregistrer"
    :taille="avecCouleur ? 'moyenne' : 'petite'"
  />
</template>

<style scoped>
.aide-type { margin-left: var(--e2); }
.radio { width: 16px; height: 16px; accent-color: var(--marine); cursor: pointer; }
.pastille-nom { display: inline-block; padding: 2px 10px; border-radius: 999px; font-weight: 600; font-size: var(--taille-s); }
</style>
