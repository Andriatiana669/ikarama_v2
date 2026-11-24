<!-- Un champ généré à partir de sa description (type ChampFormulaire). -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { ChampFormulaire, EmployeResume, Option } from '@/types'
import UiChamp from '@/components/ui/UiChamp.vue'
import UiSaisie from '@/components/ui/UiSaisie.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import SelectEmploye from './SelectEmploye.vue'
import SelectEmployes from './SelectEmployes.vue'
import UiListeNombres from '@/components/ui/UiListeNombres.vue'
import UiCouleur from '@/components/ui/UiCouleur.vue'

const modele = defineModel<any>()
const props = defineProps<{
  champ: ChampFormulaire
  erreur?: string | string[]
  /** Données détaillées déjà connues (« <cle>_details ») : nom de la personne choisie, etc. */
  employeInitial?: EmployeResume | EmployeResume[] | null
}>()

const options = ref<Option[]>(props.champ.options ?? [])
onMounted(async () => {
  if (props.champ.chargerOptions) options.value = await props.champ.chargerOptions()
})
</script>

<template>
  <label v-if="champ.type === 'case'" class="case">
    <input v-model="modele" type="checkbox" />
    {{ champ.libelle }}
  </label>
  <UiChamp v-else v-slot="{ id, invalide }" :libelle="champ.libelle" :aide="champ.aide" :erreur="erreur" :requis="champ.requis">
    <SelectEmploye
      v-if="champ.type === 'employe'"
      :id="id"
      v-model="modele"
      :employe-initial="Array.isArray(employeInitial) ? null : employeInitial"
      :invalide="invalide"
      :rechercher="champ.rechercherEmploye"
    />
    <SelectEmployes
      v-else-if="champ.type === 'employes'"
      :id="id"
      v-model="modele"
      :employes-initiaux="Array.isArray(employeInitial) ? employeInitial : null"
      :invalide="invalide"
      :bouton-tous="champ.boutonTous"
      :configurations="champ.configurations"
    />
    <UiCouleur v-else-if="champ.type === 'couleur'" :id="id" v-model="modele" :apercu="champ.placeholder" />
    <UiListeNombres v-else-if="champ.type === 'nombres'" :id="id" v-model="modele" :suffixe="champ.placeholder" :invalide="invalide" />
    <UiSelect
      v-else-if="champ.type === 'select'"
      :id="id"
      v-model="modele"
      :options="options"
      :placeholder="champ.placeholder ?? (champ.requis ? undefined : '—')"
      :invalide="invalide"
    />
    <UiSaisie
      v-else
      :id="id"
      v-model="modele"
      :type="champ.type === 'nombre' ? 'number' : champ.type === 'date' ? 'date' : 'text'"
      :multiligne="champ.type === 'zone'"
      :placeholder="champ.placeholder"
      :invalide="invalide"
    />
  </UiChamp>
</template>
