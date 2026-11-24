<!-- Liste de cases à cocher avec recherche (filtres de la page Rendement). v-model = ids cochés. -->
<script setup lang="ts">
import UiRecherche from '@/components/ui/UiRecherche.vue'
import { computed } from 'vue'

const modele = defineModel<(number | string)[]>({ default: () => [] })
defineProps<{
  titre: string
  options: { id: number | string; nom: string; detail?: string }[]
  aide?: string
  /** Barre de recherche standard (celle des tableaux, ex. Marchés > Ajouter un marché) */
  rechercheStandard?: boolean
}>()
/** Texte de recherche, partageable (v-model:recherche) */
const recherche = defineModel<string>('recherche', { default: '' })
const filtrer = (o: { nom: string; detail?: string }) => !recherche.value || `${o.nom} ${o.detail ?? ''}`.toLowerCase().includes(recherche.value.toLowerCase())
const basculer = (id: number | string) => (modele.value = modele.value.includes(id) ? modele.value.filter((i) => i !== id) : [...modele.value, id])
const nb = computed(() => modele.value.length)
</script>

<template>
  <section class="liste carte">
    <UiRecherche v-if="rechercheStandard" v-model="recherche" class="recherche-standard" :placeholder="`Rechercher : ${titre}`" />
    <input v-else v-model="recherche" class="saisie recherche" :placeholder="`Rechercher`" :aria-label="`Rechercher : ${titre}`" />
    <header class="entete">
      <span>{{ titre }}</span>
      <button v-if="nb" type="button" class="effacer" :title="`Tout décocher (${nb})`" @click="modele = []">{{ nb }} <i class="bi bi-x" aria-hidden="true" /></button>
    </header>
    <p v-if="aide" class="aide texte-xs texte-doux">{{ aide }}</p>
    <ul>
      <li v-for="o in options.filter(filtrer)" :key="o.id">
        <label class="case">
          <input type="checkbox" :checked="modele.includes(o.id)" @change="basculer(o.id)" />
          <span class="nom">{{ o.nom }}<span v-if="o.detail" class="texte-xs texte-doux"> ({{ o.detail }})</span></span>
        </label>
      </li>
      <li v-if="!options.filter(filtrer).length" class="texte-xs texte-doux vide">Aucun élément</li>
    </ul>
  </section>
</template>

<style scoped>
.liste { display: flex; flex-direction: column; padding: var(--e2); gap: var(--e2); min-width: 0; }
.recherche { height: 30px; font-size: var(--taille-s); }
/* Recherche standard dans une colonne : ne s'étire pas en hauteur, prend toute la largeur */
.recherche-standard { flex: none !important; min-width: 0 !important; max-width: none !important; }
.entete { display: flex; align-items: center; justify-content: center; gap: var(--e2); position: relative; padding: var(--e2); border-radius: var(--rayon); background: var(--marine); color: #fff; font-weight: 600; font-size: var(--taille-s); }
.effacer { position: absolute; right: 6px; display: inline-flex; align-items: center; padding: 0 6px; border: none; border-radius: 999px; background: var(--rouge); color: #fff; font-size: var(--taille-xs); font-weight: 700; cursor: pointer; }
.aide { margin: 0 var(--e1); }
ul { list-style: none; display: flex; flex-direction: column; gap: 4px; max-height: 168px; overflow-y: auto; }
li .case { display: flex; align-items: center; gap: var(--e2); padding: 4px var(--e2); border-radius: var(--rayon-s); background: var(--surface-douce); font-size: var(--taille-s); }
li .case:hover { background: var(--marine-pale); }
.nom { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vide { padding: var(--e2); }
</style>
