<!--
  Plusieurs périmètres pour une action d'un rôle (Autoriser sur… / Refuser sur…) : des pastilles, et « + » pour en ajouter.
  Chaque périmètre peut demander une valeur : un pôle ou un poste (liste avec recherche), une personne, une affaire.
-->
<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import type { EmployeResume, Identifiant } from '@/types'
import SelectEmploye from '@/components/formulaires/SelectEmploye.vue'
import ChoixValeur from './ChoixValeur.vue'

export interface Perimetre {
  perimetre: string
  valeur: string
  employe: Identifiant | null
  employe_details: EmployeResume | null
  affaire: Identifiant | null
}
const liste = defineModel<Perimetre[]>({ default: () => [] })
const props = defineProps<{
  perimetres: Record<string, string>
  effet: 'AUTORISER' | 'REFUSER'
  affaires: { id: Identifiant; nom: string; num_affaire: string }[]
  postes: string[]
  poles: string[]
  libelle: string
}>()

const ajout = ref(false)
const nouveau = reactive<Perimetre>({ perimetre: '', valeur: '', employe: null, employe_details: null, affaire: null })
const personne = ref<EmployeResume | null>(null)
const besoin = computed(() => ({
  POLE: 'pole', POSTE: 'poste', PERSONNE: 'personne', EQUIPE_DE: 'personne', AFFAIRE: 'affaire',
} as Record<string, string>)[nouveau.perimetre] ?? null)
const erreur = ref('')

function ouvrir() {
  Object.assign(nouveau, { perimetre: Object.keys(props.perimetres)[0]!, valeur: '', employe: null, employe_details: null, affaire: null })
  personne.value = null
  erreur.value = ''
  ajout.value = true
}
function valider() {
  if (besoin.value === 'poste' && !nouveau.valeur) return (erreur.value = 'Choisissez le poste.')
  if (besoin.value === 'personne' && !nouveau.employe) return (erreur.value = 'Choisissez la personne.')
  if (besoin.value === 'affaire' && !nouveau.affaire) return (erreur.value = 'Choisissez l’affaire.')
  const element = { ...nouveau, employe_details: personne.value }
  const deja = liste.value.some((p) => p.perimetre === element.perimetre && p.valeur === element.valeur
    && p.employe === element.employe && p.affaire === element.affaire)
  if (!deja) liste.value = [...liste.value, element]
  ajout.value = false
}
function retirer(i: number) {
  liste.value = liste.value.filter((_, j) => j !== i)
}
const nomAffaire = (id: Identifiant | null) => {
  const a = props.affaires.find((x) => x.id === id)
  return a ? (a.num_affaire ? `${a.num_affaire} – ${a.nom}` : a.nom) : '?'
}
function texte(p: Perimetre) {
  const base = props.perimetres[p.perimetre] ?? p.perimetre
  if (p.perimetre === 'PERSONNE') return `Personne : ${p.employe_details?.identifiant ?? p.employe}`
  if (p.perimetre === 'EQUIPE_DE') return `Équipe de ${p.employe_details?.identifiant ?? p.employe}`
  if (p.perimetre === 'AFFAIRE') return `Affaire : ${nomAffaire(p.affaire)}`
  if (p.perimetre === 'POSTE') return `Poste : ${p.valeur}`
  if (p.perimetre === 'POLE') return p.valeur ? `Pôle : ${p.valeur}` : 'Mon pôle'
  return base.replace(/ \(.*\)$/, '')
}
</script>

<template>
  <div class="liste-perimetres" :class="effet === 'AUTORISER' ? 'ok' : 'ko'">
    <span v-for="(p, i) in liste" :key="i" class="pastille" :title="perimetres[p.perimetre]">
      {{ texte(p) }}
      <button type="button" class="retirer" :aria-label="`Retirer ${texte(p)}`" @click="retirer(i)"><i class="bi bi-x" aria-hidden="true" /></button>
    </span>
    <button v-if="!ajout" type="button" class="ajouter" :aria-label="libelle" :title="libelle" @click="ouvrir">
      <i class="bi bi-plus-lg" aria-hidden="true" />{{ liste.length ? '' : (effet === 'AUTORISER' ? 'Autoriser' : 'Refuser') }}
    </button>
    <div v-else class="formulaire" @keydown.enter.prevent="valider">
      <select v-model="nouveau.perimetre" class="saisie" :aria-label="`${libelle} : périmètre`">
        <option v-for="(l, code) in perimetres" :key="code" :value="code">{{ l }}</option>
      </select>
      <ChoixValeur v-if="besoin === 'pole'" v-model="nouveau.valeur" :options="poles" placeholder="Pôle (vide : le mien)" />
      <ChoixValeur v-if="besoin === 'poste'" v-model="nouveau.valeur" :options="postes" placeholder="Rechercher un poste" />
      <SelectEmploye v-if="besoin === 'personne'" v-model="nouveau.employe" placeholder="Rechercher une personne"
        @choisi="(e: EmployeResume | null) => (personne = e)" />
      <select v-if="besoin === 'affaire'" v-model="nouveau.affaire" class="saisie" aria-label="Affaire">
        <option :value="null" disabled>L’affaire…</option>
        <option v-for="a in affaires" :key="a.id" :value="a.id">{{ nomAffaire(a.id) }}</option>
      </select>
      <button type="button" class="valider" @click="valider"><i class="bi bi-check-lg" aria-hidden="true" /> Ajouter</button>
      <button type="button" class="annuler" @click="ajout = false">Annuler</button>
      <span v-if="erreur" class="erreur" role="alert">{{ erreur }}</span>
    </div>
  </div>
</template>

<style scoped>
.liste-perimetres { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.pastille { display: inline-flex; align-items: center; gap: 2px; padding: 2px 4px 2px 10px; border-radius: 999px; font-size: var(--taille-xs); font-weight: 600; }
.ok .pastille { background: color-mix(in srgb, var(--succes) 14%, var(--surface)); color: var(--succes); border: 1px solid color-mix(in srgb, var(--succes) 35%, transparent); }
.ko .pastille { background: color-mix(in srgb, var(--rouge) 10%, var(--surface)); color: var(--rouge); border: 1px solid color-mix(in srgb, var(--rouge) 35%, transparent); }
.retirer { display: inline-grid; place-items: center; width: 18px; height: 18px; border: none; border-radius: 50%; background: none; color: inherit; cursor: pointer; }
.retirer:hover { background: rgba(0, 0, 0, 0.08); }
.ajouter { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; border: 1px dashed var(--bordure-forte); border-radius: 999px; background: none; font-size: var(--taille-xs); font-weight: 700; color: var(--texte-doux); cursor: pointer; }
.ok .ajouter:hover { border-color: var(--succes); color: var(--succes); }
.ko .ajouter:hover { border-color: var(--rouge); color: var(--rouge); }
.formulaire { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; width: 100%; padding: 6px; border-radius: var(--rayon); background: var(--surface-douce); }
.formulaire .saisie { min-width: 200px; max-width: 300px; }
.valider, .annuler { padding: 5px 10px; border-radius: var(--rayon); font-size: var(--taille-xs); font-weight: 700; cursor: pointer; }
.valider { border: none; background: var(--marine); color: #fff; }
.annuler { border: 1px solid var(--bordure-forte); background: var(--surface); color: var(--texte-doux); }
.erreur { font-size: var(--taille-xs); color: var(--rouge); font-weight: 600; }
</style>
