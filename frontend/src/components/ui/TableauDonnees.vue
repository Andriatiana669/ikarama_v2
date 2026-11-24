<!--
  Variante « grille » : fournir le slot #grille="{ lignes }" à la place du tableau (ex. cases à cocher).

  Tableau de données complet, avec la barre d'outils commune à toute l'application :
  Colonnes (afficher / masquer), Filtres, Exporter (Excel), Rechercher, ordre manuel (≡).

  <TableauDonnees
    titre="Tâches" icone="list-task" cle-stockage="taches"
    :source="tachesApi" :colonnes="colonnes" deplacable
    :parametres="{ affaire: affaireId }"            // filtres imposés par la page
    :inactif="!affaireId ? { titre: 'Choisissez une affaire' } : null"
    v-model:selection="tacheChoisie"
  >
    <template #actions><UiBouton …>Nouvelle tâche</UiBouton></template>
    <template #cellule-nom="{ ligne }">…</template>
    <template #actions-ligne="{ ligne }">…</template>
  </TableauDonnees>
-->
<script setup lang="ts" generic="T extends { id: number }">
import { computed, ref, watch } from 'vue'
import type { Parametres } from '@/api/ressource'
import { useColonnes } from '@/composables/useColonnes'
import { useListe } from '@/composables/useListe'
import { useToast } from '@/composables/useToast'
import type { ChampFormulaire, Colonne, Identifiant, Page } from '@/types'
import ChampFormulaireVue from '@/components/formulaires/ChampFormulaire.vue'
import UiBouton from './UiBouton.vue'
import UiEtatVide from './UiEtatVide.vue'
import UiMenuDeroulant from './UiMenuDeroulant.vue'
import UiPagination from './UiPagination.vue'
import UiRecherche from './UiRecherche.vue'
import UiTableau from './UiTableau.vue'

const selection = defineModel<Identifiant | null | undefined>('selection')
const props = withDefaults(
  defineProps<{
    /** Style d'une ligne (ex. couleur d'alerte du Temps Estimatif) */
    styleLigne?: (ligne: any) => Record<string, string> | undefined
    titre: string
    icone?: string
    cleStockage: string
    source: {
      lister: (p?: Parametres) => Promise<Page<T>>
      exporter?: (p: Parametres, c: { cle: string; libelle: string }[], nom: string) => Promise<void>
      reordonner?: (ids: Identifiant[]) => Promise<void>
    }
    colonnes: Colonne[]
    filtres?: ChampFormulaire[]
    parametres?: Parametres
    /** Tableau en attente (ex. aucune affaire choisie) : message à la place des données */
    inactif?: { titre: string; texte?: string } | null
    deplacable?: boolean
    cliquable?: boolean
    taillePage?: number
    videTitre?: string
    videTexte?: string
    placeholderRecherche?: string
    /** Une ligne peut-elle être choisie ? (sinon le clic est ignoré) */
    selectionnable?: (ligne: T) => boolean
  }>(),
  { filtres: () => [], parametres: () => ({}), cliquable: true, taillePage: 25, videTitre: 'Aucun élément' },
)
const emit = defineEmits<{ ligne: [ligne: T] }>()

const toast = useToast()

// Pas d'appel au serveur tant que le tableau est inactif
const sourceListe = {
  lister: (p?: Parametres): Promise<Page<T>> =>
    props.inactif ? Promise.resolve({ count: 0, next: null, previous: null, results: [] }) : props.source.lister(p),
}
const liste = useListe<T>(sourceListe, {
  taillePage: props.taillePage,
  filtres: { ...Object.fromEntries(props.filtres.map((f) => [f.cle, ''])), ...props.parametres },
})
watch(() => ({ ...props.parametres }), (p) => Object.assign(liste.filtres, p), { deep: true })
watch(() => !!props.inactif, () => liste.charger())

// Colonnes
const affichage = useColonnes(props.cleStockage, () => props.colonnes)
const menuColonnes = ref(false)
const boutonColonnes = ref<{ $el: HTMLElement } | null>(null)

// Filtres
const filtresOuverts = ref(false)
const nbFiltresActifs = computed(() => props.filtres.filter((f) => liste.filtres[f.cle] !== '' && liste.filtres[f.cle] != null).length)
function effacerFiltres() {
  props.filtres.forEach((f) => (liste.filtres[f.cle] = ''))
}

// Ordre manuel : seulement quand la liste suit l'ordre enregistré
const deplacementPossible = computed(() => props.deplacable && !!props.source.reordonner && !liste.tri.value)
async function deplacer(ids: unknown[]) {
  try {
    await props.source.reordonner!(ids as Identifiant[])
  } catch (e) {
    toast.erreur(e)
  }
  liste.charger()
}

// Export Excel des colonnes affichées
const exportEnCours = ref(false)
async function exporter() {
  if (!props.source.exporter) return
  exportEnCours.value = true
  try {
    const colonnesExport = affichage.visibles.value
      .filter((c) => c.cleExport !== false)
      .map((c) => ({ cle: (c.cleExport as string) || c.cle, libelle: c.libelle }))
    await props.source.exporter(
      { ...liste.filtres, search: liste.recherche.value, ordering: liste.tri.value },
      colonnesExport,
      props.titre,
    )
  } catch (e) {
    toast.erreur(e)
  } finally {
    exportEnCours.value = false
  }
}

function choisir(ligne: T) {
  emit('ligne', ligne)
  if (props.selectionnable && !props.selectionnable(ligne)) return
  selection.value = selection.value === ligne.id ? null : ligne.id
}

defineExpose({ recharger: liste.charger })
</script>

<template>
  <section class="carte panneau">
    <header class="entete">
      <h2>
        <i v-if="icone" :class="`bi bi-${icone}`" aria-hidden="true" />
        {{ titre }}
        <span v-if="!inactif" class="badge">{{ liste.total.value }}</span>
      </h2>
      <div class="ligne"><slot name="actions" /></div>
    </header>

    <div class="outils">
      <template v-if="!$slots.grille">
        <UiBouton ref="boutonColonnes" variante="fantome" petit icone="layout-three-columns" :aria-expanded="menuColonnes" @click="menuColonnes = !menuColonnes">
          Colonnes
        </UiBouton>
        <!-- Menu affiché au-dessus de la page : il n'est pas coupé par le tableau -->
        <UiMenuDeroulant v-model="menuColonnes" :ancre="boutonColonnes?.$el ?? null">
          <div class="menu-colonnes">
            <label v-for="c in colonnes" :key="c.cle" class="case">
              <input type="checkbox" :checked="!affichage.masquees.value.includes(c.cle)" @change="affichage.basculer(c.cle)" />
              {{ c.libelle }}
            </label>
            <button type="button" class="lien-reinit" @click="affichage.reinitialiser">Réinitialiser</button>
          </div>
        </UiMenuDeroulant>
      </template>
      <UiBouton
        v-if="filtres.length"
        variante="fantome"
        petit
        icone="funnel"
        :aria-expanded="filtresOuverts"
        @click="filtresOuverts = !filtresOuverts"
      >
        Filtres<span v-if="nbFiltresActifs" class="badge badge-rouge">{{ nbFiltresActifs }}</span>
      </UiBouton>
      <UiBouton v-if="source.exporter" variante="fantome" petit icone="download" :chargement="exportEnCours" :desactive="!!inactif" @click="exporter">
        Exporter
      </UiBouton>
      <UiRecherche v-model="liste.recherche.value" class="recherche" :placeholder="placeholderRecherche ?? 'Rechercher'" />
    </div>

    <div v-if="filtresOuverts && filtres.length" class="zone-filtres">
      <div v-for="f in filtres" :key="f.cle" class="filtre">
        <ChampFormulaireVue v-model="liste.filtres[f.cle]" :champ="{ ...f, requis: false }" />
      </div>
      <UiBouton v-if="nbFiltresActifs" variante="fantome" petit icone="x-circle" @click="effacerFiltres">Effacer</UiBouton>
    </div>

    <UiEtatVide v-if="inactif" icone="arrow-left-circle" :titre="inactif.titre" :texte="inactif.texte" />
    <template v-else-if="$slots.grille">
      <slot
        name="grille"
        :lignes="liste.lignes.value"
        :chargement="liste.chargement.value"
        :erreur="liste.erreur.value"
        :recharger="liste.charger"
      />
      <UiPagination v-model:page="liste.page.value" :total="liste.total.value" :taille-page="liste.taillePage.value" />
    </template>
    <template v-else>
      <UiTableau
        v-model:tri="liste.tri.value"
        class="donnees"
        :colonnes="affichage.visibles.value"
        :lignes="liste.lignes.value"
        :chargement="liste.chargement.value"
        :erreur="liste.erreur.value"
        :vide-titre="liste.recherche.value ? 'Aucun résultat' : videTitre"
        :vide-texte="liste.recherche.value ? 'Essayez une autre recherche.' : videTexte"
        :cliquable="cliquable"
        :selection="selection"
        :deplacable="deplacementPossible"
        :style-ligne="styleLigne"
        @selection="choisir"
        @deplacer="deplacer"
      >
        <template v-for="(_, nom) in $slots" #[nom]="donnees">
          <slot :name="nom" v-bind="donnees ?? {}" />
        </template>
        <template v-if="$slots['actions-ligne']" #actions="{ ligne }">
          <slot name="actions-ligne" :ligne="ligne" />
        </template>
      </UiTableau>
      <UiPagination v-model:page="liste.page.value" :total="liste.total.value" :taille-page="liste.taillePage.value" />
    </template>
  </section>
</template>

<style scoped>
.panneau { display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.entete {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--e2);
  padding: var(--e3) var(--e4);
  background: var(--marine);
  color: #fff;
}
.entete h2 { display: flex; align-items: center; gap: var(--e2); color: #fff; font-size: var(--taille-m); }
.entete .badge { background: rgba(255, 255, 255, 0.15); color: #fff; border-color: transparent; }
.entete :deep(.btn-secondaire) { background: transparent; color: #fff; border-color: rgba(255, 255, 255, 0.4); }
.entete :deep(.btn-secondaire:hover:not(:disabled)) { background: rgba(255, 255, 255, 0.12); }
.outils { display: flex; align-items: center; gap: var(--e1); flex-wrap: wrap; padding: var(--e2) var(--e3); border-bottom: 1px solid var(--bordure); }
.recherche { margin-left: auto; min-width: 160px; max-width: 260px; }
.recherche :deep(.saisie) { height: 32px; }
.menu-colonnes { display: flex; flex-direction: column; gap: var(--e2); padding: var(--e2) var(--e3); }
.menu-colonnes .case { font-size: var(--taille-s); }
.lien-reinit { align-self: flex-start; border: none; background: none; color: var(--marine-clair); font-size: var(--taille-xs); cursor: pointer; padding: 0; }
.zone-filtres { display: flex; align-items: flex-end; gap: var(--e3); flex-wrap: wrap; padding: var(--e3); background: var(--surface-douce); border-bottom: 1px solid var(--bordure); }
.filtre { min-width: 170px; }
.donnees :deep(.tableau) { font-size: var(--taille-s); }
.donnees :deep(.tableau td), .donnees :deep(.tableau th) { padding: var(--e2) var(--e3); }
</style>
