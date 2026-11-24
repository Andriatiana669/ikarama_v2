<!--
  Tableau de données générique.
  - colonnes : [{ cle: 'nom', libelle: 'Nom', triable: true }]
  - personnaliser une cellule : <template #cellule-nom="{ ligne }">...</template>
  - colonne d'actions à droite : <template #actions="{ ligne }">...</template>
  - tri : v-model:tri="tri"  ('nom' ou '-nom', format Django ?ordering=)
  - ligne choisie en surbrillance : :selection="idChoisi"
  - ordre manuel : deplacable + @deplacer="(ids) => ..." (poignée ≡ à gauche, glisser-déposer)
-->
<script setup lang="ts" generic="T extends Record<string, any>">
import { computed, ref, shallowRef } from 'vue'
import type { Colonne } from '@/types'
import UiChargement from './UiChargement.vue'
import UiEtatVide from './UiEtatVide.vue'

const tri = defineModel<string>('tri', { default: '' })
const props = withDefaults(
  defineProps<{
    colonnes: Colonne[]
    lignes: T[]
    chargement?: boolean
    erreur?: string | null
    cle?: string
    cliquable?: boolean
    videTitre?: string
    videTexte?: string
    selection?: unknown
    deplacable?: boolean
    /** Style d'une ligne (ex. couleur d'alerte) */
    styleLigne?: (ligne: T) => Record<string, string> | undefined
  }>(),
  { cle: 'id', videTitre: 'Aucun résultat' },
)
const emit = defineEmits<{ selection: [ligne: T]; deplacer: [ids: unknown[]] }>()

// --- Glisser-déposer (ordre manuel) ---
const enDeplacement = shallowRef<T[] | null>(null)
const indexDeplace = ref<number | null>(null)
const lignesAffichees = computed(() => enDeplacement.value ?? props.lignes)

function debutDeplacement(evenement: DragEvent, index: number) {
  enDeplacement.value = [...props.lignes]
  indexDeplace.value = index
  evenement.dataTransfer?.setData('text/plain', String(index))
  if (evenement.dataTransfer) evenement.dataTransfer.effectAllowed = 'move'
}

function survol(index: number) {
  const liste = enDeplacement.value
  const depart = indexDeplace.value
  if (!liste || depart === null || depart === index) return
  const copie = [...liste]
  const [element] = copie.splice(depart, 1)
  copie.splice(index, 0, element!)
  enDeplacement.value = copie
  indexDeplace.value = index
}

function finDeplacement() {
  const liste = enDeplacement.value
  if (liste && liste.some((l, i) => l[props.cle] !== props.lignes[i]?.[props.cle])) {
    emit('deplacer', liste.map((l) => l[props.cle]))
  }
  // La liste locale reste affichée jusqu'au rechargement par le parent
  setTimeout(() => {
    enDeplacement.value = null
    indexDeplace.value = null
  }, 400)
}

const valeur = (ligne: T, cle: string) =>
  cle.split('.').reduce<any>((objet, morceau) => objet?.[morceau], ligne) ?? '—'

function trier(colonne: Colonne) {
  if (!colonne.triable) return
  tri.value = tri.value === colonne.cle ? `-${colonne.cle}` : colonne.cle
}

const sensTri = (colonne: Colonne) =>
  tri.value === colonne.cle ? 'ascending' : tri.value === `-${colonne.cle}` ? 'descending' : undefined

const classeAlignement = (colonne: Colonne) =>
  colonne.alignement === 'droite' ? 'droite' : colonne.alignement === 'centre' ? 'centre' : ''

function surClavier(evenement: KeyboardEvent, ligne: T) {
  if (props.cliquable && (evenement.key === 'Enter' || evenement.key === ' ')) {
    evenement.preventDefault()
    emit('selection', ligne)
  }
}
</script>

<template>
  <div class="tableau-conteneur">
    <div v-if="erreur" class="alerte alerte-erreur" role="alert">
      <i class="bi bi-exclamation-triangle" aria-hidden="true" />{{ erreur }}
    </div>
    <table v-else class="tableau">
      <thead>
        <tr>
          <th v-if="deplacable" class="col-poignee"><span class="masque-visuel">Ordre</span></th>
          <th
            v-for="colonne in colonnes"
            :key="colonne.cle"
            :class="classeAlignement(colonne)"
            :style="colonne.largeur ? { width: colonne.largeur } : undefined"
            :aria-sort="sensTri(colonne)"
          >
            <button v-if="colonne.triable" class="entete-triable" type="button" @click="trier(colonne)">
              {{ colonne.libelle }}
              <i
                class="bi"
                :class="sensTri(colonne) === 'descending' ? 'bi-arrow-down' : sensTri(colonne) ? 'bi-arrow-up' : 'bi-arrow-down-up'"
                aria-hidden="true"
              />
            </button>
            <template v-else>{{ colonne.libelle }}</template>
          </th>
          <th v-if="$slots.actions" class="droite"><span class="masque-visuel">Actions</span></th>
        </tr>
      </thead>
      <tbody v-if="lignes.length">
        <tr
          v-for="(ligne, index) in lignesAffichees"
          :key="ligne[cle]"
          :class="{ cliquable, choisie: selection !== undefined && selection === ligne[cle], deplacee: indexDeplace === index }"
          :style="styleLigne?.(ligne)"
          :aria-selected="selection !== undefined ? selection === ligne[cle] : undefined"
          @dragover.prevent="deplacable && survol(index)"
          @drop.prevent="deplacable && finDeplacement()"
          :tabindex="cliquable ? 0 : undefined"
          @click="cliquable && emit('selection', ligne)"
          @keydown="surClavier($event, ligne)"
        >
          <td
            v-if="deplacable"
            class="col-poignee"
            draggable="true"
            title="Glisser pour changer l'ordre"
            @click.stop
            @dragstart="debutDeplacement($event, index)"
            @dragend="finDeplacement"
          >
            <i class="bi bi-list" aria-hidden="true" />
          </td>
          <td v-for="colonne in colonnes" :key="colonne.cle" :class="classeAlignement(colonne)">
            <slot :name="`cellule-${colonne.cle}`" :ligne="ligne" :valeur="valeur(ligne, colonne.cle)">
              {{ valeur(ligne, colonne.cle) }}
            </slot>
          </td>
          <td v-if="$slots.actions" class="droite actions" @click.stop>
            <slot name="actions" :ligne="ligne" />
          </td>
        </tr>
      </tbody>
    </table>
    <UiChargement v-if="chargement && !lignes.length && !erreur" />
    <UiEtatVide v-else-if="!chargement && !lignes.length && !erreur" :titre="videTitre" :texte="videTexte">
      <slot name="vide" />
    </UiEtatVide>
  </div>
</template>

<style scoped>
.entete-triable {
  display: inline-flex;
  align-items: center;
  gap: var(--e1);
  border: none;
  background: none;
  font-weight: inherit;
  color: inherit;
  cursor: pointer;
}
.entete-triable .bi { font-size: 0.75rem; opacity: 0.7; }
.actions { white-space: nowrap; width: 1%; }
.col-poignee { width: 32px; padding-right: 0 !important; color: var(--texte-leger); cursor: grab; }
.col-poignee:active { cursor: grabbing; }
tr.choisie td { background: var(--marine-pale) !important; }
tr.choisie td:first-child { box-shadow: inset 3px 0 0 var(--rouge); }
tr.deplacee td { background: var(--rouge-pale) !important; }
.actions :deep(.btn) { margin-left: var(--e1); }
</style>
