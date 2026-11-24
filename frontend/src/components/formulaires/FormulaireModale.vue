<!--
  Formulaire complet dans une modale, généré à partir d'une liste de champs.
  Affiche sous chaque champ les erreurs renvoyées par Django.

  <FormulaireModale v-model="ouvert" titre="Nouvel élément" :champs="champs"
                    :valeurs-initiales="element" :enregistrer="(v) => xxxApi.creer(v)" @enregistre="recharger" />
-->
<script setup lang="ts">
import { reactive, ref, useId, watch } from 'vue'
import { ApiErreur, messageErreur } from '@/api/client'
import type { ChampFormulaire } from '@/types'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiModale from '@/components/ui/UiModale.vue'
import ChampFormulaireVue from './ChampFormulaire.vue'

const ouvert = defineModel<boolean>({ default: false })
const props = withDefaults(
  defineProps<{
    titre: string
    champs: ChampFormulaire[]
    valeursInitiales?: Record<string, any> | null
    enregistrer: (valeurs: Record<string, any>) => Promise<unknown>
    libelleEnregistrer?: string
    taille?: 'petite' | 'moyenne' | 'grande'
  }>(),
  { libelleEnregistrer: 'Enregistrer', taille: 'moyenne' },
)
const emit = defineEmits<{ enregistre: [resultat: unknown] }>()

const idFormulaire = useId()
const valeurs = reactive<Record<string, any>>({})
const erreurs = ref<Record<string, any>>({})
const erreurGenerale = ref('')
const envoi = ref(false)

function initialiser() {
  Object.keys(valeurs).forEach((cle) => delete valeurs[cle])
  for (const champ of props.champs) {
    const initiale = props.valeursInitiales?.[champ.cle]
    valeurs[champ.cle] =
      initiale ??
      (champ.type === 'case' ? false
        : champ.type === 'couleur' ? '#E8EEF6'
        : champ.type === 'employes' || champ.type === 'nombres' ? []
        : champ.type === 'select' || champ.type === 'employe' ? null
        : '')
  }
  erreurs.value = {}
  erreurGenerale.value = ''
}

watch(ouvert, (valeur) => valeur && initialiser(), { immediate: true })

/** Les listes vides deviennent null pour Django (clés étrangères, nombres) */
const versApi = () =>
  Object.fromEntries(
    props.champs
      .filter((c) => !c.visible || c.visible(valeurs))
      .map((c) => [c.cle, valeurs[c.cle] === '' && c.type !== 'texte' && c.type !== 'zone' ? null : valeurs[c.cle]]),
      // (les listes, comme les personnes ou les nombres, sont envoyées telles quelles)
  )

async function soumettre() {
  envoi.value = true
  erreurs.value = {}
  erreurGenerale.value = ''
  try {
    const resultat = await props.enregistrer(versApi())
    ouvert.value = false
    emit('enregistre', resultat)
  } catch (e) {
    if (e instanceof ApiErreur && Object.keys(e.erreurs).length) {
      erreurs.value = e.erreurs
      const champsConnus = props.champs.map((c) => c.cle)
      const horsChamps = Object.keys(e.erreurs).some((cle) => !champsConnus.includes(cle))
      if (horsChamps) erreurGenerale.value = e.message
    } else {
      erreurGenerale.value = messageErreur(e)
    }
  } finally {
    envoi.value = false
  }
}
</script>

<template>
  <UiModale v-model="ouvert" :titre="titre" :taille="taille" :bloquante="envoi">
    <form :id="idFormulaire" class="grille-2" novalidate @submit.prevent="soumettre">
      <div v-if="erreurGenerale" class="alerte alerte-erreur pleine-largeur" role="alert">
        <i class="bi bi-exclamation-triangle" aria-hidden="true" />{{ erreurGenerale }}
      </div>
      <template v-for="(champ, index) in champs" :key="`${champ.cle}-${index}`">
        <div v-if="!champ.visible || champ.visible(valeurs)" :class="{ 'pleine-largeur': champ.pleineLargeur || champ.type === 'zone' }">
          <ChampFormulaireVue
            v-model="valeurs[champ.cle]"
            :champ="champ"
            :erreur="erreurs[champ.cle]"
            :employe-initial="valeursInitiales?.[`${champ.cle}_details`]"
          />
        </div>
      </template>
      <slot :valeurs="valeurs" />
    </form>
    <template #pied>
      <UiBouton :desactive="envoi" @click="ouvert = false">Annuler</UiBouton>
      <UiBouton variante="primaire" type="submit" :form="idFormulaire" :chargement="envoi">{{ libelleEnregistrer }}</UiBouton>
    </template>
  </UiModale>
</template>
