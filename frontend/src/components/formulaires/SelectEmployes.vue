<!--
  Choix de plusieurs employés : étiquettes + champ de recherche. v-model = liste d'ids.
  « Ajouter l'équipe de… » : on choisit une personne, tous ses subordonnés (à tous les niveaux) sont ajoutés, sans elle.
  « Ajouter une configuration… » (prop configurations) : les personnes d'une configuration de Paramètres >
  Configurations Responsables ; la configuration par défaut préremplit le champ quand il est vide (nouvelle affaire).
-->
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { configurationsResponsablesApi, utilisateursApi } from '@/api'
import type { ConfigurationResponsables } from '@/api/marches'
import { useConfirmation } from '@/composables/useConfirmation'
import { useToast } from '@/composables/useToast'
import type { EmployeResume, Identifiant } from '@/types'
import UiAvatar from '@/components/ui/UiAvatar.vue'
import SelectEmploye from './SelectEmploye.vue'

const modele = defineModel<Identifiant[]>({ default: () => [] })
const props = defineProps<{
  /** « Ajouter une configuration… » et préremplissage par la configuration par défaut */
  configurations?: boolean
  employesInitiaux?: EmployeResume[] | null
  invalide?: boolean
  id?: string
  /** Bouton « Tout le monde » : toutes les personnes ayant accès au site */
  boutonTous?: boolean
}>()
const { confirmer } = useConfirmation()
const toast = useToast()
const chargementTous = ref(false)

async function ajouterTout() {
  chargementTous.value = true
  try {
    const tous = (await utilisateursApi.tous({ format_court: true })) as unknown as EmployeResume[]
    const nouveaux = tous.filter((e) => !modele.value.includes(e.id))
    if (!nouveaux.length) return toast.info('Tout le monde est déjà ajouté.')
    const ok = await confirmer({
      titre: `Ajouter ${nouveaux.length} personne(s) ?`,
      message: 'Toutes les personnes ayant accès au site seront ajoutées. Vous pourrez en retirer ensuite.',
      libelleConfirmer: 'Ajouter tout le monde',
    })
    if (!ok) return
    choisis.value = [...choisis.value, ...nouveaux]
    modele.value = [...modele.value, ...nouveaux.map((e) => e.id)]
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargementTous.value = false
  }
}

// Ajouter toute l'équipe d'une personne (sous-équipes comprises), sans la personne elle-même
const equipeOuverte = ref(false)
const chargementEquipe = ref(false)
async function ajouterEquipe(chef: EmployeResume | null) {
  if (!chef) return
  chargementEquipe.value = true
  try {
    const equipe = await utilisateursApi.subordonnes(chef.id, 'hierarchie')
    const nouveaux = equipe.filter((e) => !modele.value.includes(e.id) && e.id !== chef.id)
    if (!equipe.length) return toast.info(`${chef.identifiant} n’a personne dans son équipe.`)
    if (!nouveaux.length) return toast.info(`Toute l’équipe de ${chef.identifiant} est déjà ajoutée.`)
    choisis.value = [...choisis.value, ...nouveaux]
    modele.value = [...modele.value, ...nouveaux.map((e) => e.id)]
    toast.succes(`${nouveaux.length} personne(s) de l’équipe de ${chef.identifiant} ajoutée(s)`)
    equipeOuverte.value = false
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargementEquipe.value = false
  }
}

// Configurations de responsables (Paramètres > Configurations Responsables)
const listeConfigurations = ref<ConfigurationResponsables[]>([])
const configurationsOuvertes = ref(false)
function ajouterPersonnes(personnes: EmployeResume[]) {
  const nouveaux = personnes.filter((e) => !modele.value.includes(e.id))
  choisis.value = [...choisis.value, ...nouveaux]
  modele.value = [...modele.value, ...nouveaux.map((e) => e.id)]
  return nouveaux.length
}
function ajouterConfiguration(c: ConfigurationResponsables) {
  const n = ajouterPersonnes(c.personnes_details)
  if (n) toast.succes(`${n} personne(s) de « ${c.nom} » ajoutée(s)`)
  else toast.info(`Les personnes de « ${c.nom} » sont déjà ajoutées.`)
  configurationsOuvertes.value = false
}
onMounted(async () => {
  if (!props.configurations) return
  try {
    listeConfigurations.value = await configurationsResponsablesApi.tous()
  } catch {
    return
  }
  // Nouveau formulaire (champ vide) : la configuration par défaut le préremplit
  const defaut = listeConfigurations.value.find((c) => c.par_defaut)
  if (defaut && !modele.value.length) ajouterPersonnes(defaut.personnes_details)
})

function toutRetirer() {
  modele.value = []
}

// Noms des personnes choisies (pour les étiquettes)
const choisis = ref<EmployeResume[]>([...(props.employesInitiaux ?? [])])
watch(() => props.employesInitiaux, (liste) => (choisis.value = [...(liste ?? [])]))
watch(modele, (ids) => (choisis.value = choisis.value.filter((e) => ids.includes(e.id))))


function ajouter(employe: EmployeResume | null) {
  if (employe && !modele.value.includes(employe.id)) {
    choisis.value.push(employe)
    modele.value = [...modele.value, employe.id]
  }
}

const retirer = (id: Identifiant) => (modele.value = modele.value.filter((i) => i !== id))
</script>

<template>
  <div class="select-employes">
    <ul v-if="choisis.length" class="etiquettes">
      <li v-for="e in choisis" :key="e.id" class="etiquette">
        <UiAvatar :nom="e.nom_affiche" :matricule="e.code_barre" />
        <span>{{ e.nom_affiche }}</span>
        <button type="button" :aria-label="`Retirer ${e.nom_affiche}`" @click="retirer(e.id)">
          <i class="bi bi-x" aria-hidden="true" />
        </button>
      </li>
    </ul>
    <div class="raccourcis">
      <button v-if="configurations && listeConfigurations.length" type="button" class="lien" :aria-expanded="configurationsOuvertes"
        @click="configurationsOuvertes = !configurationsOuvertes">
        <i class="bi bi-collection" aria-hidden="true" /> Ajouter une configuration…
      </button>
      <button type="button" class="lien" :aria-expanded="equipeOuverte" @click="equipeOuverte = !equipeOuverte">
        <i class="bi bi-diagram-3" aria-hidden="true" /> Ajouter l’équipe de…
      </button>
      <button v-if="boutonTous" type="button" class="lien" :disabled="chargementTous" @click="ajouterTout">
        <i class="bi bi-people" aria-hidden="true" /> {{ chargementTous ? 'Chargement…' : 'Tout le monde' }}
      </button>
      <button v-if="choisis.length" type="button" class="lien" @click="toutRetirer">
        <i class="bi bi-x-circle" aria-hidden="true" /> Tout retirer ({{ choisis.length }})
      </button>
    </div>
    <div v-if="configurationsOuvertes" class="equipe">
      <span class="texte-xs texte-doux">Configurations (Paramètres > Configurations Responsables) :</span>
      <div class="configurations">
        <button v-for="c in listeConfigurations" :key="c.id" type="button" class="configuration" @click="ajouterConfiguration(c)">
          <span class="gras">{{ c.nom }}</span><span class="texte-xs texte-doux">{{ c.personnes_details.length }} personne(s)</span>
          <span v-if="c.par_defaut" class="defaut">par défaut</span>
        </button>
      </div>
    </div>
    <div v-if="equipeOuverte" class="equipe">
      <span class="texte-xs texte-doux">Toute l’équipe (sous-équipes comprises) de :</span>
      <SelectEmploye :model-value="null" vider-apres-choix placeholder="Rechercher le responsable de l’équipe…" @choisi="ajouterEquipe" />
      <span v-if="chargementEquipe" class="texte-xs texte-doux">Chargement…</span>
    </div>
    <SelectEmploye
      :id="id"
      :model-value="null"
      vider-apres-choix
      placeholder="Ajouter une personne…"
      :invalide="invalide"
      @choisi="ajouter"
    />
  </div>
</template>

<style scoped>
.select-employes { display: flex; flex-direction: column; gap: var(--e2); }
.etiquettes { list-style: none; display: flex; flex-wrap: wrap; gap: var(--e1); }
.etiquette {
  display: inline-flex;
  align-items: center;
  gap: var(--e1);
  padding: 2px var(--e1) 2px 2px;
  border-radius: 999px;
  background: var(--marine-pale);
  color: var(--marine);
  font-size: var(--taille-s);
  font-weight: 600;
}
.etiquette :deep(.avatar) { width: 22px; height: 22px; font-size: 0.6rem; }
.raccourcis { display: flex; flex-wrap: wrap; gap: var(--e3); }
.configurations { display: flex; flex-wrap: wrap; gap: 6px; }
.configuration { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border: 1px solid var(--bordure-forte); border-radius: 999px; background: var(--surface); cursor: pointer; }
.configuration:hover { border-color: var(--marine); background: var(--marine-pale); }
.defaut { padding: 0 6px; border-radius: 999px; background: var(--marine); color: #fff; font-size: 0.62rem; font-weight: 700; }
.equipe { display: flex; flex-direction: column; gap: 4px; padding: var(--e2); border: 1px dashed var(--bordure-forte); border-radius: var(--rayon); background: var(--surface-douce); }
.lien { display: inline-flex; align-items: center; gap: 4px; border: none; background: none; padding: 0; color: var(--marine-clair); font-size: var(--taille-xs); font-weight: 600; cursor: pointer; }
.lien:hover:not(:disabled) { text-decoration: underline; }
.etiquettes { max-height: 160px; overflow-y: auto; }
.etiquette button { border: none; background: none; color: inherit; cursor: pointer; display: grid; place-items: center; }
</style>
