<!--
  Écran de gestion complet d'une ressource : recherche, filtres, tableau paginé,
  création, modification et désactivation. Une page de liste = ce composant + 2 tableaux de configuration.

  <GestionCrud :ressource="xxxApi" :colonnes="colonnes" :champs="champs" :textes="textes" :filtres="filtres">
    <template #cellule-nom="{ ligne }"><strong>{{ ligne.nom }}</strong></template>
  </GestionCrud>
-->
<script setup lang="ts" generic="T extends { id: number }">
import { computed, ref, shallowRef } from 'vue'
import type { Parametres } from '@/api/ressource'
import { useConfirmation } from '@/composables/useConfirmation'
import { useListe } from '@/composables/useListe'
import { useToast } from '@/composables/useToast'
import type { ChampFormulaire, Colonne, Identifiant, Page } from '@/types'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiPagination from '@/components/ui/UiPagination.vue'
import UiRecherche from '@/components/ui/UiRecherche.vue'
import UiTableau from '@/components/ui/UiTableau.vue'
import ChampFormulaireVue from './ChampFormulaire.vue'
import FormulaireModale from './FormulaireModale.vue'

export interface TextesCrud {
  nouveau: string          // « Nouveau pôle » (bouton et titre)
  modifier: string         // « Modifier le pôle »
  supprimer: string        // « Désactiver ce pôle ? »
  enregistre: string       // « Pôle enregistré »
  supprime: string         // « Pôle désactivé »
  vide: string             // « Aucun pôle pour le moment »
  recherche?: string
  boutonSupprimer?: string // « Désactiver » par défaut (ou « Supprimer »)
}

const props = withDefaults(
  defineProps<{
    ressource: {
      lister: (p?: Parametres) => Promise<Page<T>>
      creer: (d: any) => Promise<T>
      modifier: (id: Identifiant, d: any) => Promise<T>
      supprimer: (id: Identifiant) => Promise<void>
    }
    colonnes: Colonne[]
    champs: ChampFormulaire[]
    textes: TextesCrud
    filtres?: ChampFormulaire[]
    valeursParDefaut?: Record<string, any>
    modifiable?: boolean
    triInitial?: string
  }>(),
  { modifiable: true, filtres: () => [] },
)
const emit = defineEmits<{ selection: [ligne: T]; modifie: [] }>()

const toast = useToast()
const { confirmer } = useConfirmation()

const liste = useListe<T>(props.ressource, {
  tri: props.triInitial,
  filtres: Object.fromEntries(props.filtres.map((f) => [f.cle, ''])),
})

const formulaireOuvert = ref(false)
const enCours = shallowRef<T | null>(null)
const titreFormulaire = computed(() => (enCours.value ? props.textes.modifier : props.textes.nouveau))

function ouvrir(ligne: T | null = null) {
  enCours.value = ligne
  formulaireOuvert.value = true
}

const enregistrer = (valeurs: Record<string, any>) =>
  enCours.value ? props.ressource.modifier(enCours.value.id, valeurs) : props.ressource.creer(valeurs)

function apresEnregistrement() {
  toast.succes(props.textes.enregistre)
  liste.charger()
  emit('modifie')
}

async function supprimer(ligne: T) {
  const libelle = props.textes.boutonSupprimer ?? 'Désactiver'
  if (!(await confirmer({ titre: props.textes.supprimer, libelleConfirmer: libelle, danger: true }))) return
  try {
    await props.ressource.supprimer(ligne.id)
    toast.succes(props.textes.supprime)
    liste.charger()
    emit('modifie')
  } catch (e) {
    toast.erreur(e)
  }
}

defineExpose({ recharger: liste.charger, ouvrir })
</script>

<template>
  <div class="carte">
    <div class="barre-outils">
      <UiRecherche v-model="liste.recherche.value" :placeholder="textes.recherche" />
      <div v-for="filtre in filtres" :key="filtre.cle" class="filtre">
        <ChampFormulaireVue v-model="liste.filtres[filtre.cle]" :champ="{ ...filtre, requis: false }" />
      </div>
      <slot name="outils" />
      <UiBouton v-if="modifiable" class="ajouter" variante="primaire" icone="plus-lg" @click="ouvrir()">
        {{ textes.nouveau }}
      </UiBouton>
    </div>

    <UiTableau
      v-model:tri="liste.tri.value"
      :colonnes="colonnes"
      :lignes="liste.lignes.value"
      :chargement="liste.chargement.value"
      :erreur="liste.erreur.value"
      :vide-titre="textes.vide"
      :vide-texte="liste.recherche.value ? 'Essayez une autre recherche.' : undefined"
      cliquable
      @selection="emit('selection', $event)"
    >
      <template v-for="(_, nom) in $slots" #[nom]="donnees">
        <slot :name="nom" v-bind="donnees ?? {}" />
      </template>
      <template v-if="modifiable" #actions="{ ligne }">
        <slot name="actions-ligne" :ligne="ligne" />
        <UiBouton variante="fantome" icone="pencil" petit icone-seule @click="ouvrir(ligne)">Modifier</UiBouton>
        <UiBouton
          variante="fantome"
          :icone="textes.boutonSupprimer ? 'trash' : 'archive'"
          petit
          icone-seule
          @click="supprimer(ligne)"
        >
          {{ textes.boutonSupprimer ?? 'Désactiver' }}
        </UiBouton>
      </template>
    </UiTableau>

    <UiPagination v-model:page="liste.page.value" :total="liste.total.value" :taille-page="liste.taillePage.value" />

    <FormulaireModale
      v-model="formulaireOuvert"
      :titre="titreFormulaire"
      :champs="champs"
      :valeurs-initiales="enCours ?? valeursParDefaut"
      :enregistrer="enregistrer"
      @enregistre="apresEnregistrement"
    />
  </div>
</template>

<style scoped>
.barre-outils {
  display: flex;
  align-items: flex-end;
  gap: var(--e3);
  flex-wrap: wrap;
  padding: var(--e4);
  border-bottom: 1px solid var(--bordure);
}
.filtre { min-width: 180px; }
.ajouter { margin-left: auto; }
</style>
