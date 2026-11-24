<!-- Google Sheet > Mes feuilles : les feuilles dont je suis créateur, responsable ou membre d'une affaire. -->
<script setup lang="ts">
import { useAuthStore } from '@/store/auth'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { equipeFeuilleApi, feuillesApi } from '@/api'
import type { EquipeAffaire } from '@/api/gsheets'
import UiModale from '@/components/ui/UiModale.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import { useEdition } from '@/composables/useEdition'
import type { Colonne, Feuille } from '@/types'
import { couleurTexte, formatDateHeure } from '@/utils/format'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import ImportExcel from '@/components/ui/ImportExcel.vue'
import TableauDonnees from '@/components/ui/TableauDonnees.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'
import UiProgression from '@/components/ui/UiProgression.vue'

const router = useRouter()
const auth = useAuthStore()
// La liste des feuilles ne s'exporte qu'avec le droit « Exporter » (Paramètres > Autorisation)
const sourceFeuilles = computed(() =>
  auth.peut('exporter', 'gsheets_feuilles') ? feuillesApi : ({ ...feuillesApi, exporter: undefined } as unknown as typeof feuillesApi))
const importOuvert = ref(false)
const tableau = ref<{ recharger: () => void } | null>(null)
const suppression = useEdition(feuillesApi as any, { nom: 'feuille', feminin: true }, () => tableau.value?.recharger())

const colonnes: Colonne[] = [
  { cle: 'id', libelle: 'ID', triable: true, largeur: '52px' },
  { cle: 'nom', libelle: 'Feuille', triable: true },
  { cle: 'affaires', libelle: 'Affaires', cleExport: false },
  { cle: 'nb_lignes', libelle: 'Lignes', alignement: 'droite' },
  { cle: 'avancement_moyen', libelle: 'Avancement moyen' },
  { cle: 'statuts', libelle: 'Statuts', cleExport: false },
  { cle: 'mon_role', libelle: 'Mon rôle' },
  { cle: 'cree_par', libelle: 'Créée par', cleExport: 'cree_par_details' },
  { cle: 'cree_le', libelle: 'Créée le', triable: true },
  { cle: 'equipe', libelle: 'Équipe', cleExport: false, alignement: 'centre', largeur: '64px' },
]

/** Affaires de la feuille, avec leurs prestations */
// Bouton « œil » : responsables et membres des affaires de la feuille
const equipeOuverte = ref(false)
const equipeFeuille = ref<Feuille | null>(null)
const equipe = ref<EquipeAffaire[] | null>(null)
async function voirEquipe(f: Feuille) {
  equipeFeuille.value = f
  equipe.value = null
  equipeOuverte.value = true
  try {
    equipe.value = await equipeFeuilleApi(f.id)
  } catch {
    equipe.value = []
  }
}
const MAX_AFFAIRES = 2
const MAX_PRESTATIONS = 3

const affairesDe = (f: Feuille) => {
  const groupes = new Map<number, { nom: string; prestations: string[] }>()
  for (const p of f.perimetres) {
    const g = groupes.get(p.affaire) ?? { nom: `${p.num_affaire ? `${p.num_affaire} – ` : ''}${p.nom_affaire}`, prestations: [] }
    g.prestations.push(p.nom_prestation)
    groupes.set(p.affaire, g)
  }
  return [...groupes.values()]
}
const ouvrir = (f: Feuille) => router.push(`/google-sheet/feuilles/${f.id}`)
</script>

<template>
  <div class="page">
    <EnTetePage titre="Mes feuilles" description="Les feuilles des affaires dont vous êtes responsable ou membre.">
      <UiBouton v-if="auth.peut('importer', 'gsheets_feuilles')" icone="file-earmark-arrow-up" @click="importOuvert = true">Importer des feuilles</UiBouton>
      <UiBouton v-if="auth.peut('creer', 'gsheets_feuilles')" variante="primaire" icone="file-earmark-plus" @click="router.push('/google-sheet/nouvelle')">Nouvelle feuille</UiBouton>
    </EnTetePage>

    <TableauDonnees
      ref="tableau"
      titre="Feuilles"
      icone="file-earmark-spreadsheet"
      cle-stockage="feuilles"
      :source="sourceFeuilles"
      :colonnes="colonnes"
      :taille-page="10"
      placeholder-recherche="Nom de feuille ou d'affaire"
      vide-titre="Aucune feuille"
      vide-texte="Créez une feuille depuis « Créer une nouvelle feuille », ou demandez à un responsable de vous ajouter comme membre d'une affaire."
      @ligne="ouvrir"
    >
      <template #cellule-nom="{ ligne }"><span class="gras">{{ ligne.nom }}</span></template>
      <template #cellule-affaires="{ ligne }">
        <div class="affaires" :title="affairesDe(ligne).map((a) => `${a.nom} : ${a.prestations.join(', ')}`).join('\n')">
          <div v-for="a in affairesDe(ligne).slice(0, MAX_AFFAIRES)" :key="a.nom" class="affaire">
            <span class="nom-affaire">{{ a.nom }}</span>
            <span class="prestations">
              <span v-for="p in a.prestations.slice(0, MAX_PRESTATIONS)" :key="p" class="prestation">{{ p }}</span>
              <span v-if="a.prestations.length > MAX_PRESTATIONS" class="prestation plus">+{{ a.prestations.length - MAX_PRESTATIONS }}</span>
            </span>
          </div>
          <span v-if="affairesDe(ligne).length > MAX_AFFAIRES" class="autres">+ {{ affairesDe(ligne).length - MAX_AFFAIRES }} autre(s) affaire(s)</span>
        </div>
      </template>
      <template #cellule-statuts="{ ligne }">
        <div class="statuts">
          <span v-for="st in ligne.statuts ?? []" :key="String(st.id)" class="statut" :style="{ background: st.couleur, color: couleurTexte(st.couleur) }">
            {{ st.nom }} <strong>{{ st.nombre }}</strong>
          </span>
          <span v-if="!ligne.statuts?.length" class="texte-doux">—</span>
        </div>
      </template>
      <template #cellule-equipe="{ ligne }">
        <UiBouton variante="fantome" icone="eye" petit icone-seule @click.stop="voirEquipe(ligne)">Voir les responsables et les membres</UiBouton>
      </template>
      <template #cellule-avancement_moyen="{ ligne }"><UiProgression :valeur="ligne.avancement_moyen" /></template>
      <template #cellule-mon_role="{ ligne }">
        <span :class="['badge', ligne.mon_role === 'RESPONSABLE' ? 'badge-marine' : '']">
          {{ ligne.mon_role === 'RESPONSABLE' ? 'Responsable' : 'Membre' }}
        </span>
      </template>
      <template #cellule-cree_par="{ ligne }"><UiEmploye :employe="ligne.cree_par_details" sans-matricule /></template>
      <template #cellule-cree_le="{ ligne }"><span class="nowrap">{{ formatDateHeure(ligne.cree_le) }}</span></template>
      <template #actions-ligne="{ ligne }">
        <UiBouton variante="fantome" icone="box-arrow-up-right" petit icone-seule @click="ouvrir(ligne)">Ouvrir</UiBouton>
        <UiBouton v-if="ligne.droits?.modifier" variante="fantome" icone="pencil" petit icone-seule @click="router.push(`/google-sheet/feuilles/${ligne.id}/modifier`)">Modifier</UiBouton>
        <UiBouton v-if="ligne.droits?.supprimer" variante="fantome" icone="trash" petit icone-seule @click="suppression.supprimer(ligne, ligne.nom)">Supprimer</UiBouton>
      </template>
    </TableauDonnees>

    <UiModale v-model="equipeOuverte" :titre="`Équipe de « ${equipeFeuille?.nom ?? ''} »`" taille="moyenne">
      <UiChargement v-if="!equipe" />
      <p v-else-if="!equipe.length" class="texte-doux">Aucune affaire dans cette feuille.</p>
      <div v-else class="pile">
        <section v-for="a in equipe" :key="a.id" class="bloc-equipe">
          <h3>{{ a.num_affaire ? `${a.num_affaire} – ` : '' }}{{ a.nom }}</h3>
          <div class="grille-2">
            <div>
              <p class="titre-role"><i class="bi bi-person-badge" aria-hidden="true" /> Responsables ({{ a.responsables.length }})</p>
              <ul class="personnes"><li v-for="r in a.responsables" :key="r.id"><UiEmploye :employe="r" /></li></ul>
              <p v-if="!a.responsables.length" class="texte-xs texte-doux">Aucun.</p>
            </div>
            <div>
              <p class="titre-role"><i class="bi bi-people" aria-hidden="true" /> Membres ({{ a.membres.length }})</p>
              <ul class="personnes"><li v-for="m in a.membres" :key="m.id"><UiEmploye :employe="m" /></li></ul>
              <p v-if="!a.membres.length" class="texte-xs texte-doux">Aucun.</p>
            </div>
          </div>
        </section>
      </div>
    </UiModale>

    <ImportExcel
      v-model="importOuvert"
      titre="Importer des feuilles"
      nom-modele="Modele_import_feuilles"
      :source="feuillesApi"
      @importe="tableau?.recharger()"
    />
  </div>
</template>

<style scoped>
.affaires { display: flex; flex-direction: column; gap: 6px; max-width: 360px; }
.affaire { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.nom-affaire { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.prestations { display: flex; flex-wrap: wrap; gap: 4px; }
.prestation { padding: 1px 8px; border: 1px solid var(--bordure-forte); border-radius: 999px; background: var(--surface-douce); font-size: var(--taille-xs); color: var(--texte-doux); white-space: nowrap; }
.prestation.plus { font-weight: 700; color: var(--marine); }
.autres { font-size: var(--taille-xs); color: var(--marine); font-weight: 600; }
.statuts { display: flex; flex-wrap: wrap; gap: 4px; max-width: 280px; }
.statut { display: inline-flex; align-items: center; gap: 5px; padding: 1px 9px; border-radius: 999px; font-size: var(--taille-xs); font-weight: 600; white-space: nowrap; }
.bloc-equipe { padding-bottom: var(--e3); border-bottom: 1px solid var(--bordure); }
.bloc-equipe:last-child { border-bottom: none; }
.bloc-equipe h3 { font-size: var(--taille-m); color: var(--marine); margin-bottom: var(--e2); }
.titre-role { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-s); font-weight: 700; color: var(--texte-doux); margin-bottom: var(--e2); }
.personnes { list-style: none; display: flex; flex-direction: column; gap: var(--e2); }
.nowrap { white-space: nowrap; }
</style>
