<!--
  Paramètres > Configurations Responsables (superadmin) : des groupes de personnes nommés, ajoutés d'un coup dans le
  champ Responsables d'une affaire (« Ajouter une configuration… »). La configuration par défaut préremplit les
  Responsables d'une nouvelle affaire.
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { configurationsResponsablesApi } from '@/api'
import type { ConfigurationResponsables } from '@/api/marches'
import { useConfirmation } from '@/composables/useConfirmation'
import { useEdition } from '@/composables/useEdition'
import { useToast } from '@/composables/useToast'
import type { ChampFormulaire } from '@/types'
import FormulaireModale from '@/components/formulaires/FormulaireModale.vue'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'
import UiPersonnes from '@/components/ui/UiPersonnes.vue'

const toast = useToast()
const { confirmer } = useConfirmation()
const configurations = ref<ConfigurationResponsables[] | null>(null)
async function charger() {
  try {
    configurations.value = await configurationsResponsablesApi.tous()
  } catch (e) {
    toast.erreur(e)
  }
}
onMounted(charger)

const edition = useEdition(configurationsResponsablesApi, { nom: 'configuration', feminin: true }, charger)
const champs: ChampFormulaire[] = [
  { cle: 'nom', libelle: 'Nom de la configuration', type: 'texte', requis: true, pleineLargeur: true },
  { cle: 'personnes', libelle: 'Personnes', type: 'employes', requis: true, pleineLargeur: true,
    aide: '« Ajouter l’équipe de… » ajoute d’un coup tous les subordonnés d’une personne.' },
  { cle: 'par_defaut', libelle: 'Par défaut (préremplit les Responsables d’une nouvelle affaire)', type: 'case', pleineLargeur: true },
]
async function supprimer(c: ConfigurationResponsables) {
  if (!(await confirmer({ titre: 'Supprimer la configuration', message: `Supprimer « ${c.nom} » ? Les affaires existantes ne changent pas.`, danger: true }))) return
  try {
    await configurationsResponsablesApi.supprimer(c.id)
    toast.succes(`« ${c.nom} » supprimée`)
    await charger()
  } catch (e) {
    toast.erreur(e)
  }
}
async function rendreParDefaut(c: ConfigurationResponsables) {
  try {
    await configurationsResponsablesApi.modifier(c.id, { par_defaut: !c.par_defaut })
    await charger()
  } catch (e) {
    toast.erreur(e)
  }
}
</script>

<template>
  <div class="page pile">
    <EnTetePage titre="Configurations Responsables"
      description="Des groupes de personnes à ajouter d’un coup dans le champ Responsables d’une affaire (« Ajouter une configuration… »). La configuration par défaut préremplit les Responsables d’une nouvelle affaire.">
      <UiBouton variante="primaire" icone="plus-lg" @click="edition.ouvrir()">Nouvelle configuration</UiBouton>
    </EnTetePage>

    <UiChargement v-if="!configurations" />
    <UiEtatVide v-else-if="!configurations.length" class="carte" icone="collection" titre="Aucune configuration"
      texte="Créez une configuration, par exemple « Direction Saisie » avec les responsables habituels." />
    <div v-else class="grille">
      <article v-for="c in configurations" :key="c.id" class="carte configuration" :class="{ defaut: c.par_defaut }">
        <header class="tete">
          <h2>{{ c.nom }}</h2>
          <span v-if="c.par_defaut" class="badge-defaut"><i class="bi bi-star-fill" aria-hidden="true" /> Par défaut</span>
        </header>
        <p class="texte-xs texte-doux">{{ c.personnes_details.length }} personne(s)</p>
        <UiPersonnes :personnes="c.personnes_details" />
        <footer class="actions">
          <UiBouton variante="fantome" petit :icone="c.par_defaut ? 'star-fill' : 'star'" @click="rendreParDefaut(c)">
            {{ c.par_defaut ? 'Ne plus mettre par défaut' : 'Mettre par défaut' }}</UiBouton>
          <span class="espace" />
          <UiBouton variante="fantome" petit icone="pencil" @click="edition.ouvrir({ ...c, personnes_details: c.personnes_details } as any)">Modifier</UiBouton>
          <UiBouton variante="fantome" petit icone="trash" @click="supprimer(c)">Supprimer</UiBouton>
        </footer>
      </article>
    </div>

    <FormulaireModale v-model="edition.ouvert.value" :titre="edition.titre.value" :champs="champs"
      :valeurs-initiales="edition.valeursInitiales.value" :enregistrer="edition.enregistrer" />
  </div>
</template>

<style scoped>
.grille { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: var(--e4); }
.configuration { display: flex; flex-direction: column; gap: var(--e2); padding: var(--e4); border-top: 4px solid var(--bordure-forte); }
.configuration.defaut { border-top-color: var(--marine); }
.tete { display: flex; align-items: center; justify-content: space-between; gap: var(--e2); }
.tete h2 { font-size: var(--taille-m); color: var(--marine); }
.badge-defaut { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; border-radius: 999px; background: var(--marine); color: #fff; font-size: var(--taille-xs); font-weight: 700; }
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2); margin-top: auto; padding-top: var(--e2); border-top: 1px solid var(--bordure); }
.espace { flex: 1; }
</style>
