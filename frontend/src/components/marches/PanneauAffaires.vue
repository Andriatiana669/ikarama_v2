<!--
  Affaires : point de départ du Marché. Un clic choisit l'affaire (panneaux de droite).
  mode = gestion  : création, modification, archivage (Ajouter un marché)
         mes      : mes affaires (responsable ou membre) ; un responsable peut modifier les membres
         archives : affaires archivées, avec « Désarchiver »
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { affairesApi } from '@/api'
import { useConfirmation } from '@/composables/useConfirmation'
import { useEdition } from '@/composables/useEdition'
import { useToast } from '@/composables/useToast'
import type { Affaire, ChampFormulaire, Colonne, Identifiant } from '@/types'
import { formatDateHeure, formatNombre } from '@/utils/format'
import FormulaireModale from '@/components/formulaires/FormulaireModale.vue'
import ImportExcel from '@/components/ui/ImportExcel.vue'
import TableauDonnees from '@/components/ui/TableauDonnees.vue'
import StatutSuivi from './StatutSuivi.vue'
import { LIGNES_PAR_PAGE_MARCHE } from './constantes'
import UiBouton from '@/components/ui/UiBouton.vue'
import { useAuthStore } from '@/store/auth'
import UiEmploye from '@/components/ui/UiEmploye.vue'
import UiPersonnes from '@/components/ui/UiPersonnes.vue'

const selection = defineModel<Identifiant | null | undefined>('selection')
const props = withDefaults(
  defineProps<{
    mode?: 'gestion' | 'mes' | 'archives'
    /** Tâche dont le temps est affiché (menu « Temps de la tâche ») */
    tache?: { id: number; nom: string } | null
  }>(),
  { mode: 'gestion', tache: null },
)
const emit = defineEmits<{ ligne: [affaire: Affaire]; modifie: [] }>()

const toast = useToast()
const { confirmer } = useConfirmation()

const tableau = ref<{ recharger: () => void } | null>(null)
const importOuvert = ref(false)
const edition = useEdition(affairesApi, { nom: 'affaire', feminin: true, verbeSupprimer: 'archiver' }, () => {
  tableau.value?.recharger()
  emit('modifie')
})

// Mes marchés et Archives : colonnes secondaires masquées par défaut pour garder les boutons visibles
const secondaire = computed(() => props.mode !== 'gestion')
const colonnes = computed<Colonne[]>(() => [
  { cle: 'id', libelle: 'ID', triable: true, largeur: '52px' },
  { cle: 'num_affaire', libelle: 'Num affaire', triable: true },
  { cle: 'nom', libelle: 'Nom affaire', triable: true },
  ...(props.mode === 'mes' ? [{ cle: 'mon_role', libelle: 'Mon rôle' }] : []),
  ...(props.mode === 'archives' ? [{ cle: 'modifie_le', libelle: 'Archivée le' }] : []),
  { cle: 'temps', libelle: 'Temps', masqueeParDefaut: secondaire.value },
  ...(props.tache ? [{ cle: 'temps_tache', libelle: `Temps « ${props.tache.nom} »` }] : []),
  { cle: 'statut', libelle: 'Statut', masqueeParDefaut: secondaire.value },
  { cle: 'responsables', libelle: 'Responsable', cleExport: 'responsables_details' },
  { cle: 'membres', libelle: 'Membres', cleExport: 'membres_details' },
  { cle: 'pointage_seul', libelle: 'Options', cleExport: 'pointage_seul' },
  { cle: 'cree_par', libelle: 'Créée par', cleExport: 'cree_par_details', masqueeParDefaut: secondaire.value },
  { cle: 'cree_le', libelle: 'Créée le', triable: true, masqueeParDefaut: secondaire.value },
])

const parametres = computed(() => ({
  ...(props.mode === 'mes' ? { mes: 1 } : props.mode === 'archives' ? { archives: 1 } : {}),
  tache: props.tache?.id ?? '',
}))
const titre = computed(() => ({ gestion: 'Affaires', mes: 'Mes affaires', archives: 'Affaires archivées' })[props.mode])
const textesVides = {
  gestion: ['Aucune affaire', 'Créez la première affaire avec le bouton « Nouvelle affaire ».'],
  mes: ['Aucune affaire', "Vous n'êtes responsable ni membre d'aucune affaire en cours."],
  archives: ['Aucune affaire archivée', 'Les affaires archivées depuis « Ajouter un marché » apparaissent ici.'],
}

// Mes marchés : un responsable modifie les membres de son affaire
const membres = useEdition(
  { creer: async () => ({}) as Affaire, modifier: (id, d) => affairesApi.modifierMembres(id, d.membres), supprimer: async () => {} },
  { nom: 'membres' },
  () => {
    tableau.value?.recharger()
    emit('modifie')
  },
)
const champsMembres: ChampFormulaire[] = [{ cle: 'membres', libelle: 'Membres', type: 'employes', requis: true, pleineLargeur: true, boutonTous: true }]

async function supprimer(affaire: Affaire) {
  const ok = await confirmer({
    titre: `Supprimer définitivement « ${affaire.nom} » ?`,
    message:
      "L'affaire sera effacée, sans retour possible. C'est refusé tant qu'elle a des prestations cochées, des projets / communes ou des descriptions. Pour simplement la mettre de côté, archivez-la.",
    libelleConfirmer: 'Supprimer définitivement',
    danger: true,
  })
  if (!ok) return
  try {
    await affairesApi.supprimerDefinitivement(affaire.id)
    toast.succes('Affaire supprimée')
    if (selection.value === affaire.id) selection.value = null
    tableau.value?.recharger()
    emit('modifie')
  } catch (e) {
    toast.erreur(e)
  }
}

async function desarchiver(affaire: Affaire) {
  if (!(await confirmer({ titre: `Désarchiver « ${affaire.nom} » ?`, message: "L'affaire reviendra dans « Ajouter un marché » et « Mes marchés ».", libelleConfirmer: 'Désarchiver' }))) return
  try {
    await affairesApi.desarchiver(affaire.id)
    toast.succes('Affaire désarchivée')
    tableau.value?.recharger()
    emit('modifie')
  } catch (e) {
    toast.erreur(e)
  }
}

const filtres: ChampFormulaire[] = [
  { cle: 'responsable', libelle: 'Responsable', type: 'employe' },
  { cle: 'membre', libelle: 'Membre', type: 'employe' },
]

const champs: ChampFormulaire[] = [
  { cle: 'num_affaire', libelle: "N° d'affaire", type: 'texte', aide: 'Facultatif' },
  { cle: 'nom', libelle: "Nom de l'affaire", type: 'texte', requis: true },
  { cle: 'responsables', libelle: 'Responsables', type: 'employes', requis: true, pleineLargeur: true, configurations: true },
  { cle: 'membres', libelle: 'Membres', type: 'employes', requis: true, pleineLargeur: true, boutonTous: true },
  { cle: 'pointage_seul', libelle: 'Pointage seulement (pas de feuille)', type: 'case', pleineLargeur: true,
    aide: 'Affaire suivie au pointage sans feuille : les Contrôles de cohérence ne la signalent pas. On peut quand même lui créer une feuille.' },
  { cle: 'report_dt', libelle: 'Report DT', type: 'case', pleineLargeur: true,
    aide: 'Surface (m²) par projet / commune et Quantité linéaire (ML) par description : Quantité = Quantité linéaire × Surface ÷ Linéaire total (somme du projet).' },
]
// Paramètres > Autorisation : Ajouter un marché (affaires en cours) et Archives
const auth = useAuthStore()
</script>

<template>
  <TableauDonnees
    ref="tableau"
    :taille-page="LIGNES_PAR_PAGE_MARCHE"
    v-model:selection="selection"
    :titre="titre"
    :icone="mode === 'archives' ? 'archive' : 'briefcase'"
    :cle-stockage="`marches-affaires-${mode}`"
    :source="affairesApi"
    :colonnes="colonnes"
    :filtres="filtres"
    :parametres="parametres"
    :deplacable="mode === 'gestion'"
    :cliquable="mode !== 'archives'"
    placeholder-recherche="Nom ou n° d'affaire"
    :vide-titre="textesVides[mode][0]"
    :vide-texte="textesVides[mode][1]"
    @ligne="(a: Affaire) => emit('ligne', a)"
  >
    <template v-if="mode === 'gestion'" #actions>
      <UiBouton v-if="auth.peut('importer', 'marches_affaires')" variante="secondaire" petit icone="file-earmark-arrow-up" @click="importOuvert = true">Importer</UiBouton>
      <UiBouton v-if="auth.peut('creer', 'marches_affaires')" variante="secondaire" petit icone="plus-lg" @click="edition.ouvrir()">Nouvelle affaire</UiBouton>
    </template>
    <template #cellule-mon_role="{ ligne }">
      <span :class="['badge', ligne.mon_role === 'RESPONSABLE' ? 'badge-marine' : '']">
        {{ ligne.mon_role === 'RESPONSABLE' ? 'Responsable' : 'Membre' }}
      </span>
    </template>
    <template #cellule-modifie_le="{ ligne }"><span class="nowrap">{{ formatDateHeure(ligne.modifie_le) }}</span></template>
    <template #cellule-num_affaire="{ ligne }">{{ ligne.num_affaire || '—' }}</template>
    <template #cellule-nom="{ ligne }"><span class="gras">{{ ligne.nom }}</span></template>
    <template #cellule-temps_tache="{ ligne }">
      <span class="temps-tache">{{ ligne.temps_tache && Number(ligne.temps_tache) ? `${formatNombre(ligne.temps_tache)} h` : '—' }}</span>
    </template>
    <template #cellule-temps="{ ligne }">
      <span :title="ligne.temps ? 'Temps de prod + contrôle + reprise (feuilles)' : undefined">{{ ligne.temps ? `${formatNombre(ligne.temps)} h` : '—' }}</span>
    </template>
    <template #cellule-statut="{ ligne }"><StatutSuivi :statut="ligne.statut" /></template>
    <template #cellule-responsables="{ ligne }"><UiPersonnes :personnes="ligne.responsables_details" /></template>
    <template #cellule-pointage_seul="{ ligne }">
      <span v-if="ligne.pointage_seul" class="badge badge-marine" title="Suivie au pointage sans feuille : non signalée dans les Contrôles">
        <i class="bi bi-stopwatch" aria-hidden="true" /> Pointage seul</span>
      <span v-if="ligne.report_dt" class="badge" title="Quantité calculée depuis la Surface et la Quantité linéaire">
        <i class="bi bi-rulers" aria-hidden="true" /> Report DT</span>
      <span v-if="!ligne.pointage_seul && !ligne.report_dt" class="texte-leger">—</span>
    </template>
    <template #cellule-membres="{ ligne }"><UiPersonnes :personnes="ligne.membres_details" /></template>
    <template #cellule-cree_par="{ ligne }"><UiEmploye :employe="ligne.cree_par_details" sans-matricule /></template>
    <template #cellule-cree_le="{ ligne }"><span class="nowrap">{{ formatDateHeure(ligne.cree_le) }}</span></template>
    <template #actions-ligne="{ ligne }">
      <template v-if="mode === 'gestion'">
        <UiBouton v-if="auth.peut('modifier', 'marches_affaires')" variante="fantome" icone="pencil" petit icone-seule @click="edition.ouvrir(ligne)">Modifier</UiBouton>
        <UiBouton v-if="auth.peut('archiver', 'marches_affaires')" variante="fantome" icone="archive" petit icone-seule @click="edition.supprimer(ligne, ligne.nom)">Archiver</UiBouton>
        <UiBouton v-if="auth.peut('supprimer', 'marches_archives')" variante="fantome" icone="trash" petit icone-seule @click="supprimer(ligne)">Supprimer définitivement</UiBouton>
      </template>
      <UiBouton
        v-else-if="mode === 'mes' && ligne.mon_role === 'RESPONSABLE'"
        variante="fantome"
        icone="person-plus"
        petit
        @click="membres.ouvrir(ligne)"
      >
        Membres
      </UiBouton>
      <template v-else-if="mode === 'archives'">
        <UiBouton v-if="auth.peut('desarchiver', 'marches_archives')" variante="secondaire" icone="box-arrow-up" petit @click="desarchiver(ligne)">Désarchiver</UiBouton>
        <UiBouton v-if="auth.peut('supprimer', 'marches_archives')" variante="fantome" icone="trash" petit icone-seule @click="supprimer(ligne)">Supprimer définitivement</UiBouton>
      </template>
    </template>
  </TableauDonnees>

  <ImportExcel
    v-if="mode === 'gestion'"
    v-model="importOuvert"
    titre="Importer des affaires"
    nom-modele="Modele_import_affaires"
    :source="affairesApi"
    @importe="tableau?.recharger(); emit('modifie')"
  />
  <FormulaireModale
    v-model="edition.ouvert.value"
    :titre="edition.titre.value"
    :champs="champs"
    :valeurs-initiales="edition.valeursInitiales.value"
    :enregistrer="edition.enregistrer"
  />
  <FormulaireModale
    v-model="membres.ouvert.value"
    :titre="`Membres de « ${membres.enCours.value?.nom ?? ''} »`"
    :champs="champsMembres"
    :valeurs-initiales="membres.valeursInitiales.value"
    :enregistrer="membres.enregistrer"
  />
</template>

<style scoped>
.nowrap { white-space: nowrap; }
.temps-tache { color: var(--marine-clair); font-weight: 600; }
</style>
