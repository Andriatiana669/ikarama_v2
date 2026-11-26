<!--
  Une feuille, façon tableur : une ligne par description du périmètre.
  Les colonnes du Marché sont en lecture seule ; les autres se modifient directement dans le tableau.
  Responsables et membres : Employé, Statut, Avancement, Commentaires, Contrôleur, Employé reprise ;
  responsables seulement : Nombre de reprises et critères.
  En direct : les modifications des autres arrivent aussitôt (temps réel), ou toutes les 4 secondes sans lui, et une case que
  quelqu'un d'autre est en train de modifier est entourée de rouge avec son nom.
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { feuillesApi, lignesFeuilleApi, statutsFeuilleApi } from '@/api'
import { ApiErreur } from '@/api/client'
import type { SaisieLigne } from '@/api/gsheets'
import { useSuiviFeuille } from '@/composables/useSuiviFeuille'
import { useToast } from '@/composables/useToast'
import type { ChampFormulaire, Colonne, EmployeResume, Feuille, LigneFeuille, StatutResume } from '@/types'
import { formatDate, formatDateHeure, formatNombre, formatRelatif } from '@/utils/format'
import CellulePersonne from '@/components/feuilles/CellulePersonne.vue'
import HistoriqueFeuille from '@/components/feuilles/HistoriqueFeuille.vue'
import ZoneCellule from '@/components/feuilles/ZoneCellule.vue'
import UiAvatar from '@/components/ui/UiAvatar.vue'
import CelluleSaisie from '@/components/feuilles/CelluleSaisie.vue'
import CelluleStatut from '@/components/feuilles/CelluleStatut.vue'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import ImportExcel from '@/components/ui/ImportExcel.vue'
import { ancienneDonneeApi, tempsEstimatifApi } from '@/api'
import type { ParametresTempsEstimatif } from '@/api/gsheets'
import TableauDonnees from '@/components/ui/TableauDonnees.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const id = computed(() => Number(route.params.id))

const feuille = ref<Feuille | null>(null)
const personnes = ref<Record<string, EmployeResume[]>>({})
const statuts = ref<StatutResume[]>([])
const erreur = ref<string | null>(null)

/** Recharge la feuille et ses personnes (après un import qui a pu élargir la feuille) */
async function rechargerFeuille() {
  ;[feuille.value, personnes.value] = await Promise.all([feuillesApi.lire(id.value), feuillesApi.personnes(id.value)])
  tableau.value?.recharger()
}

onMounted(async () => {
  try {
    ;[feuille.value, personnes.value, statuts.value] = await Promise.all([
      feuillesApi.lire(id.value),
      feuillesApi.personnes(id.value),
      statutsFeuilleApi() as Promise<StatutResume[]>,
    ])
  } catch (e) {
    erreur.value = e instanceof Error ? e.message : 'Feuille introuvable.'
  }
})

// ------------------------------------------------------------------
// Saisie : chaque modification est enregistrée aussitôt, et la ligne mise à jour sur place
// ------------------------------------------------------------------
const modifiees = reactive<Record<number, LigneFeuille>>({})
const ligneA = (l: LigneFeuille) => modifiees[l.id] ?? l
const tableau = ref<{ recharger: () => void } | null>(null)

/** Valeurs que je vois avant de modifier : le serveur refuse si quelqu'un les a changées entre-temps */
function valeursVues(ligne: LigneFeuille, saisie: SaisieLigne) {
  const actuelle = ligneA(ligne) as unknown as Record<string, unknown>
  const vues: Record<string, unknown> = {}
  for (const cle of Object.keys(saisie)) if (cle !== 'notes_saisies') vues[cle] = actuelle[cle]
  for (const critere of Object.keys(saisie.notes_saisies ?? {})) vues[`note_${critere}`] = ligneA(ligne).notes[critere] ?? null
  return vues
}

async function enregistrer(ligne: LigneFeuille, saisie: SaisieLigne) {
  try {
    modifiees[ligne.id] = await lignesFeuilleApi.modifier(ligne.id, { ...saisie, attendu: valeursVues(ligne, saisie) })
  } catch (e) {
    if (e instanceof ApiErreur && e.code === 'conflit') {
      toast.info(e.message)
      modifiees[ligne.id] = await lignesFeuilleApi.lire(ligne.id).catch(() => ligneA(ligne))
    } else {
      toast.erreur(e)
    }
  }
}

// ------------------------------------------------------------------
// Suivi en direct
// ------------------------------------------------------------------
const suivi = useSuiviFeuille(() => id.value, {
  surLignes: (lignes) => lignes.forEach((l) => (modifiees[l.id] = l)),
  surRechargement: () => tableau.value?.recharger(),
})
/** Je commence / j'arrête de modifier une case */
const editer = (ligne: LigneFeuille, champ: string) => (enCours: boolean) =>
  suivi.signalerEdition(enCours ? { ligne: ligne.id, champ } : null)
const occupant = (ligne: LigneFeuille, champ: string) => suivi.occupant(ligne.id, champ)
const nouvellesLignes = computed(() =>
  feuille.value && suivi.nbLignes.value !== null ? Math.max(0, suivi.nbLignes.value - feuille.value.nb_lignes) : 0,
)
function afficherNouvellesLignes() {
  if (feuille.value && suivi.nbLignes.value !== null) feuille.value.nb_lignes = suivi.nbLignes.value
  tableau.value?.recharger()
}

// Import des données : modèle prérempli avec les lignes actuelles de cette feuille
const importOuvert = ref(false)
// Import des anciennes données (colonnes des anciens fichiers ; crée projets / communes et descriptions)
const importAncienOuvert = ref(false)
const sourceAncien = {
  telechargerModele: (nom: string) => ancienneDonneeApi.telechargerModele(nom, { feuille: id.value }),
  importer: (fichier: File, simulation: boolean) => ancienneDonneeApi.importer(fichier, simulation, { feuille: id.value }),
}

const sourceImport = {
  telechargerModele: (nom: string) => lignesFeuilleApi.telechargerModele(nom, { feuille: id.value }),
  importer: (fichier: File, simulation: boolean) => lignesFeuilleApi.importer(fichier, simulation, { feuille: id.value }),
}

// --- Temps Estimatif : unité (heures / jours) et couleur des lignes (Paramètres > Temps Estimatif) ---
const reglagesTemps = ref<ParametresTempsEstimatif | null>(null)
const uniteTemps = ref<'heures' | 'jours'>('heures')
tempsEstimatifApi.lire().then((r) => {
  reglagesTemps.value = r
  uniteTemps.value = r.unite
}).catch(() => undefined)
function texteTempsEstimatif(heures: string | null) {
  if (heures === null) return '—'
  const h = Number(heures)
  if (uniteTemps.value === 'jours') {
    const j = h / (reglagesTemps.value?.heures_par_jour || 8)
    return `${j.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} j`
  }
  return `${h.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} h`
}
function styleLigne(ligne: LigneFeuille) {
  // Version à jour de la ligne (suivi en direct, modification) : la couleur change sans actualiser
  const alerte = ligneA(ligne).alerte_temps
  const r = reglagesTemps.value
  if (!r || !alerte) return undefined
  const couleur = alerte === 'rouge' ? r.couleur_rouge : r.couleur_orange
  return { background: `color-mix(in srgb, ${couleur} 16%, var(--surface))`, boxShadow: `inset 4px 0 0 ${couleur}` }
}

// --- Encarts « Affaires et prestations » et « Note de qualité » : repliés par défaut, choix mémorisé ---
const CLE_ENCARTS = 'ikarama.feuille.encarts'
const encarts = reactive<{ affaires: boolean; qualite: boolean }>((() => {
  try {
    return { affaires: false, qualite: false, ...JSON.parse(localStorage.getItem(CLE_ENCARTS) || '{}') }
  } catch {
    return { affaires: false, qualite: false }
  }
})())
function basculerEncart(cle: 'affaires' | 'qualite') {
  encarts[cle] = !encarts[cle]
  try {
    localStorage.setItem(CLE_ENCARTS, JSON.stringify(encarts))
  } catch {
    // stockage indisponible : le choix vaut pour cette page seulement
  }
}
const resumeAffaires = computed(() => {
  const perimetres = feuille.value?.perimetres ?? []
  const affaires = new Set(perimetres.map((p) => p.affaire)).size
  return `${affaires} affaire(s), ${perimetres.length} prestation(s)`
})

// Historique (chargé seulement à l'ouverture)
const historiqueOuvert = ref(false)
const historiqueLigne = ref<{ id: number; numero: number; description: string } | null>(null)
function ouvrirHistorique(ligne: LigneFeuille | null = null) {
  historiqueLigne.value = ligne ? { id: ligne.id, numero: ligne.numero, description: ligne.marche.description } : null
  historiqueOuvert.value = true
}
const nombreOuVide = (v: string) => (v === '' ? null : v.replace(',', '.'))

// ------------------------------------------------------------------
// Colonnes (dans l'ordre demandé) ; « cleExport » = donnée envoyée à Excel
// ------------------------------------------------------------------
const colonnes = computed<Colonne[]>(() => [
  { cle: 'numero', libelle: 'ID', triable: true, largeur: '52px' },
  { cle: 'employe', libelle: 'Employé', cleExport: 'employe_details.identifiant' },
  { cle: 'marche.num_affaire', libelle: 'Num affaire' },
  { cle: 'marche.nom_affaire', libelle: 'Nom affaire' },
  { cle: 'marche.prestation', libelle: 'Prestation' },
  { cle: 'marche.projet', libelle: 'Projet / Commune' },
  { cle: 'description', libelle: 'Description', cleExport: 'marche.description' },
  { cle: 'marche.unite', libelle: 'Unité' },
  { cle: 'quantite', libelle: 'Quantité', cleExport: 'marche.quantite', alignement: 'droite' },
  { cle: 'temps_estimatif', libelle: 'Temps Estimatif', alignement: 'droite' },
  { cle: 'temps_prod', libelle: 'Temps de prod' },
  { cle: 'date_debut', libelle: 'Date de début' },
  { cle: 'statut', libelle: 'Statut', cleExport: 'statut_details.nom' },
  { cle: 'avancement', libelle: 'Avancement', triable: true },
  { cle: 'commentaires', libelle: 'Commentaires' },
  { cle: 'rendement_objectif', libelle: 'Rendement objectif / j', cleExport: 'marche.rendement_objectif', alignement: 'droite' },
  { cle: 'rendement_prod', libelle: 'Rendement prod' },
  { cle: 'controleur', libelle: 'Contrôleur', cleExport: 'controleur_details.identifiant' },
  { cle: 'statut_controle', libelle: 'Statut de contrôle', cleExport: 'statut_controle_details.nom' },
  { cle: 'temps_controle', libelle: 'Temps de contrôle' },
  { cle: 'commentaires_controle', libelle: 'Commentaires contrôle' },
  { cle: 'nb_reprises', libelle: 'Nombre de reprises', alignement: 'droite' },
  { cle: 'employe_reprise', libelle: 'Employé reprise', cleExport: 'employe_reprise_details.identifiant' },
  { cle: 'temps_reprise', libelle: 'Temps de reprise' },
  { cle: 'commentaires_reprise', libelle: 'Commentaires reprise' },
  { cle: 'rendement_total', libelle: 'Rendement total' },
  { cle: 'date_livraison', libelle: 'Date de livraison', cleExport: 'marche.date_livraison' },
  { cle: 'note_rendement', libelle: 'Note de rendement' },
  { cle: 'note_qualite', libelle: 'Note de qualité' },
  ...(feuille.value?.utiliser_criteres ? feuille.value.criteres : []).map((c) => ({
    cle: `critere_${c.id}`,
    libelle: `Critère ${c.numero}`,
    cleExport: `notes.${c.id}`,
    alignement: 'droite' as const,
  })),
  { cle: 'modifie', libelle: 'Dernière modification', cleExport: 'modifie_par_details.identifiant' },
])

const filtres = computed<ChampFormulaire[]>(() => {
  const affaires = new Map<number, string>()
  feuille.value?.perimetres.forEach((p) => affaires.set(p.affaire, p.nom_affaire))
  const tous = new Map<number, EmployeResume>()
  Object.values(personnes.value).flat().forEach((p) => tous.set(p.id, p))
  return [
    { cle: 'affaire', libelle: 'Affaire', type: 'select', placeholder: 'Toutes', options: [...affaires].map(([v, l]) => ({ valeur: v, libelle: l })) },
    { cle: 'statut', libelle: 'Statut', type: 'select', placeholder: 'Tous', options: statuts.value.map((s) => ({ valeur: s.id, libelle: s.nom })) },
    { cle: 'statut_controle', libelle: 'Statut de contrôle', type: 'select', placeholder: 'Tous', options: statuts.value.map((s) => ({ valeur: s.id, libelle: s.nom })) },
    { cle: 'employe', libelle: 'Employé', type: 'select', placeholder: 'Tous', options: [...tous.values()].map((p) => ({ valeur: p.id, libelle: p.identifiant })) },
  ]
})

const optionsPersonnes = (l: LigneFeuille) => personnes.value[String(l.marche.affaire_id)] ?? []
const nomCritere = (cle: string) => `cellule-${cle}`
const heures = (v: string | null) => (v === null ? '—' : `${formatNombre(v)} h`)
/** Couleur d'une note sur 5 : rouge sous 2,5, vert à partir de 4 */
const classeNote = (v: string | null) => (v === null ? '' : Number(v) >= 4 ? 'bonne' : Number(v) < 2.5 ? 'faible' : 'moyenne')
</script>

<template>
  <div class="page page-large">
    <div v-if="erreur" class="carte"><UiEtatVide icone="file-earmark-x" titre="Feuille introuvable" :texte="erreur" /></div>
    <UiChargement v-else-if="!feuille" />
    <template v-else>
      <EnTetePage :titre="feuille.nom" :description="`${feuille.nb_lignes} ligne(s), une par description`">
        <span class="direct" :class="{ hors: suivi.horsLigne.value }"
          :title="`${suivi.tempsReel.value ? 'Temps réel : les changements arrivent aussitôt.' : 'Mise à jour toutes les 4 secondes (temps réel indisponible).'}${suivi.derniereMaj.value ? ` Dernière mise à jour : ${formatDateHeure(suivi.derniereMaj.value)}` : ''}`">
          <span class="point" aria-hidden="true" />{{ suivi.horsLigne.value ? 'Connexion perdue, nouvel essai…' : 'En direct' }}
          <i v-if="suivi.tempsReel.value && !suivi.horsLigne.value" class="bi bi-lightning-charge-fill eclair" aria-label="temps réel" />
        </span>
        <UiBouton icone="arrow-left" @click="router.push('/google-sheet/mes-feuilles')">Mes feuilles</UiBouton>
        <div class="bascule-unite" role="group" aria-label="Unité du Temps Estimatif" title="Unité du Temps Estimatif">
          <button type="button" :class="{ actif: uniteTemps === 'heures' }" :aria-pressed="uniteTemps === 'heures'" @click="uniteTemps = 'heures'">Heures</button>
          <button type="button" :class="{ actif: uniteTemps === 'jours' }" :aria-pressed="uniteTemps === 'jours'" @click="uniteTemps = 'jours'">Jours</button>
        </div>
        <UiBouton icone="clock-history" @click="ouvrirHistorique()">Historique</UiBouton>
        <UiBouton v-if="feuille.droits?.importer_donnees" icone="file-earmark-arrow-up" @click="importOuvert = true">Importer les données</UiBouton>
        <UiBouton v-if="feuille.droits?.importer_donnees" icone="clock-history" @click="importAncienOuvert = true">Import ancienne donnée</UiBouton>
        <UiBouton v-if="feuille.droits?.modifier" icone="pencil" @click="router.push(`/google-sheet/feuilles/${feuille.id}/modifier`)">Modifier la feuille</UiBouton>
      </EnTetePage>

      <!-- Encarts repliables (repliés par défaut ; le choix est mémorisé dans le navigateur) -->
      <div class="infos" :class="{ replies: !encarts.affaires && !encarts.qualite }">
        <section class="carte encart" :class="{ ouvert: encarts.affaires }">
          <button type="button" class="tete-encart" :aria-expanded="encarts.affaires" aria-controls="encart-affaires" @click="basculerEncart('affaires')">
            <i class="bi bi-briefcase" aria-hidden="true" />
            <span class="titre-bloc">Affaires et prestations</span>
            <span class="resume-encart">{{ resumeAffaires }}</span>
            <i class="bi chevron" :class="encarts.affaires ? 'bi-chevron-up' : 'bi-chevron-down'" aria-hidden="true" />
          </button>
          <div v-show="encarts.affaires" id="encart-affaires" class="corps-encart">
            <ul class="liste">
              <li v-for="p in feuille.perimetres" :key="`${p.affaire}-${p.prestation}`">
                <span class="gras">{{ p.num_affaire ? `${p.num_affaire} – ` : '' }}{{ p.nom_affaire }}</span>
                <span class="badge">{{ p.nom_prestation }}</span>
              </li>
            </ul>
          </div>
        </section>
        <section class="carte encart" :class="{ ouvert: encarts.qualite }">
          <button type="button" class="tete-encart" :aria-expanded="encarts.qualite" aria-controls="encart-qualite" @click="basculerEncart('qualite')">
            <i class="bi bi-patch-check" aria-hidden="true" />
            <span class="titre-bloc">Note de qualité</span>
            <span class="resume-encart">{{ feuille.utiliser_criteres && feuille.criteres.length ? `${feuille.criteres.length} critère(s)` : 'Sans critère' }}</span>
            <i class="bi chevron" :class="encarts.qualite ? 'bi-chevron-up' : 'bi-chevron-down'" aria-hidden="true" />
          </button>
          <div v-show="encarts.qualite" id="encart-qualite" class="corps-encart">
            <template v-if="feuille.utiliser_criteres && feuille.criteres.length">
              <p class="texte-petit texte-doux aide">Moyenne des critères de CTRL (notes de 1 à 5) :</p>
              <ul class="liste">
                <li v-for="c in feuille.criteres" :key="c.id"><span class="badge badge-marine">Critère {{ c.numero }}</span> {{ c.commentaire }}</li>
              </ul>
            </template>
            <p v-else class="texte-petit texte-doux">
              Sans critère : calculée d'après le temps de reprise par rapport au temps de prod
              (<RouterLink to="/parametres/rendement-note">Paramètres > Rendement & Note</RouterLink>).
            </p>
          </div>
        </section>
      </div>

      <div v-if="nouvellesLignes" class="alerte bandeau" role="status">
        <i class="bi bi-plus-circle" aria-hidden="true" />
        <span>{{ nouvellesLignes }} nouvelle(s) ligne(s) depuis l'ouverture (descriptions ajoutées dans le Marché).</span>
        <UiBouton variante="secondaire" petit @click="afficherNouvellesLignes">Afficher</UiBouton>
      </div>

      <TableauDonnees
        ref="tableau"
        titre="Lignes"
        icone="table"
        :cle-stockage="`feuille-${feuille.id}`"
        :style-ligne="styleLigne"
        :source="lignesFeuilleApi"
        :colonnes="colonnes"
        :filtres="filtres"
        :parametres="{ feuille: feuille.id }"
        :taille-page="50"
        :cliquable="false"
        placeholder-recherche="Description, projet, affaire, employé…"
        vide-titre="Aucune ligne"
        vide-texte="Les lignes apparaissent dès que les projets des prestations choisies ont des descriptions (Marchés)."
        class="tableur"
      >
        <template #cellule-numero="{ ligne }">
          <span class="numero">
            {{ ligne.numero }}
            <span v-for="p in suivi.occupantsLigne(ligne.id)" :key="p.employe.id" class="present" :title="`${p.employe.identifiant} modifie cette ligne`">
              <UiAvatar :nom="p.employe.nom_affiche" :matricule="p.employe.code_barre" />
            </span>
          </span>
        </template>
        <template #cellule-employe="{ ligne }">
          <ZoneCellule :occupant="occupant(ligne, 'employe')">
            <CellulePersonne libelle="Employé" :valeur="ligneA(ligne).employe_details" :options="optionsPersonnes(ligne)"
              :desactive="!ligne.peut_modifier" :verrouille="ligneA(ligne).colonnes_verrouillees?.includes('employe')"
              @edition="editer(ligne, 'employe')($event)" @choisir="(v) => enregistrer(ligne, { employe: v })" />
          </ZoneCellule>
        </template>
        <template #cellule-description="{ ligne }">
          <span class="gras">{{ ligne.marche.description }}</span>
          <span v-if="ligne.retiree" class="badge badge-attention bloc" title="Cette description n'existe plus dans le Marché">retirée du marché</span>
        </template>
        <template #cellule-quantite="{ ligne }">{{ formatNombre(ligne.marche.quantite) }}</template>
        <template #cellule-statut="{ ligne }">
          <ZoneCellule :occupant="occupant(ligne, 'statut')">
            <CelluleStatut :valeur="ligneA(ligne).statut_details" :options="statuts" :desactive="!ligne.peut_modifier"
              @edition="editer(ligne, 'statut')($event)" @choisir="(v) => enregistrer(ligne, { statut: v })" />
          </ZoneCellule>
        </template>
        <template #cellule-avancement="{ ligne }">
          <ZoneCellule :occupant="occupant(ligne, 'avancement')">
            <CelluleSaisie type="pourcentage" libelle="Avancement en %" :valeur="ligneA(ligne).avancement"
              :desactive="!ligne.peut_modifier" @edition="editer(ligne, 'avancement')($event)"
              @enregistrer="(v) => enregistrer(ligne, { avancement: Number(v) || 0 })" />
          </ZoneCellule>
        </template>
        <template #cellule-commentaires="{ ligne }">
          <ZoneCellule :occupant="occupant(ligne, 'commentaires')">
            <CelluleSaisie libelle="Commentaires" :valeur="ligneA(ligne).commentaires" :desactive="!ligne.peut_modifier"
              @edition="editer(ligne, 'commentaires')($event)" @enregistrer="(v) => enregistrer(ligne, { commentaires: v })" />
          </ZoneCellule>
        </template>
        <template v-for="champ in ['commentaires_controle', 'commentaires_reprise'] as const" :key="champ" #[`cellule-${champ}`]="{ ligne }">
          <ZoneCellule :occupant="occupant(ligne, champ)">
            <CelluleSaisie :libelle="champ === 'commentaires_controle' ? 'Commentaires contrôle' : 'Commentaires reprise'"
              :valeur="ligneA(ligne)[champ]" :desactive="!ligne.peut_modifier"
              @edition="editer(ligne, champ)($event)" @enregistrer="(v) => enregistrer(ligne, { [champ]: v })" />
          </ZoneCellule>
        </template>
        <template #cellule-temps_estimatif="{ ligne }">
          <span class="temps-estimatif" :title="ligneA(ligne).alerte_temps === 'rouge' ? 'Temps de prod égal ou supérieur au Temps Estimatif'
            : ligneA(ligne).alerte_temps === 'orange' ? 'Temps de prod proche du Temps Estimatif' : 'Quantité ÷ Rendement objectif'">
            {{ texteTempsEstimatif(ligneA(ligne).temps_estimatif) }}
          </span>
        </template>
        <template #cellule-rendement_objectif="{ ligne }">{{ formatNombre(ligne.marche.rendement_objectif) }}</template>
        <template #cellule-statut_controle="{ ligne }">
          <ZoneCellule :occupant="occupant(ligne, 'statut_controle')">
            <CelluleStatut :valeur="ligneA(ligne).statut_controle_details ?? null" :options="statuts" :desactive="!ligne.peut_modifier"
              @edition="editer(ligne, 'statut_controle')($event)" @choisir="(v) => enregistrer(ligne, { statut_controle: v })" />
          </ZoneCellule>
        </template>
        <template #cellule-controleur="{ ligne }">
          <ZoneCellule :occupant="occupant(ligne, 'controleur')">
            <CellulePersonne libelle="Contrôleur" :valeur="ligneA(ligne).controleur_details" :options="optionsPersonnes(ligne)"
              :desactive="!ligne.peut_modifier" :verrouille="ligneA(ligne).colonnes_verrouillees?.includes('controleur')"
              @edition="editer(ligne, 'controleur')($event)" @choisir="(v) => enregistrer(ligne, { controleur: v })" />
          </ZoneCellule>
        </template>
        <template #cellule-nb_reprises="{ ligne }">
          <ZoneCellule :occupant="occupant(ligne, 'nb_reprises')">
            <CelluleSaisie type="nombre" libelle="Nombre de reprises" :valeur="ligneA(ligne).nb_reprises"
              :desactive="!ligne.peut_saisir_controle" @edition="editer(ligne, 'nb_reprises')($event)"
              @enregistrer="(v) => enregistrer(ligne, { nb_reprises: Number(v) || 0 })" />
          </ZoneCellule>
        </template>
        <template #cellule-employe_reprise="{ ligne }">
          <ZoneCellule :occupant="occupant(ligne, 'employe_reprise')">
            <CellulePersonne libelle="Employé reprise" :valeur="ligneA(ligne).employe_reprise_details" :options="optionsPersonnes(ligne)"
              :desactive="!ligne.peut_modifier" :verrouille="ligneA(ligne).colonnes_verrouillees?.includes('employe_reprise')"
              @edition="editer(ligne, 'employe_reprise')($event)"
              @choisir="(v) => enregistrer(ligne, { employe_reprise: v })" />
          </ZoneCellule>
        </template>
        <template #cellule-temps_prod="{ ligne }">{{ heures(ligneA(ligne).temps_prod) }}</template>
        <template #cellule-temps_controle="{ ligne }">{{ heures(ligneA(ligne).temps_controle) }}</template>
        <template #cellule-temps_reprise="{ ligne }">{{ heures(ligneA(ligne).temps_reprise) }}</template>
        <template #cellule-date_debut="{ ligne }">{{ ligneA(ligne).date_debut ? formatDate(ligneA(ligne).date_debut) : '—' }}</template>
        <template #cellule-rendement_prod="{ ligne }"><span title="Quantité ÷ Temps de prod × heures par jour">{{ formatNombre(ligneA(ligne).rendement_prod) }}</span></template>
        <template #cellule-rendement_total="{ ligne }"><span title="Quantité ÷ (prod + contrôle + reprise) × heures par jour">{{ formatNombre(ligneA(ligne).rendement_total) }}</span></template>
        <template #cellule-note_rendement="{ ligne }"><span class="note" :class="classeNote(ligneA(ligne).note_rendement)">{{ formatNombre(ligneA(ligne).note_rendement) }}</span></template>
        <template #cellule-note_qualite="{ ligne }"><span class="note" :class="classeNote(ligneA(ligne).note_qualite)">{{ formatNombre(ligneA(ligne).note_qualite) }}</span></template>
        <template #cellule-date_livraison="{ ligne }"><span class="nowrap">{{ formatDate(ligne.marche.date_livraison) }}</span></template>
        <template v-for="c in feuille.criteres" :key="c.id" #[nomCritere(`critere_${c.id}`)]="{ ligne }">
          <ZoneCellule :occupant="occupant(ligne, `note_${c.id}`)">
            <CelluleSaisie type="nombre" :libelle="`Critère ${c.numero} : ${c.commentaire} (note de 1 à 5)`" :valeur="ligneA(ligne).notes[String(c.id)] ?? null"
              :desactive="!ligne.peut_saisir_controle" @edition="editer(ligne, `note_${c.id}`)($event)"
              @enregistrer="(v) => enregistrer(ligne, { notes_saisies: { [String(c.id)]: nombreOuVide(v) } })" />
          </ZoneCellule>
        </template>
        <template #cellule-modifie="{ ligne }">
          <span v-if="ligneA(ligne).modifie_par_details" class="modifie" :title="formatDateHeure(ligneA(ligne).modifie_le)">
            <UiAvatar :nom="ligneA(ligne).modifie_par_details!.nom_affiche" :matricule="ligneA(ligne).modifie_par_details!.code_barre" />
            <span>
              <span class="gras">{{ ligneA(ligne).modifie_par_details!.identifiant }}</span>
              <span class="texte-xs texte-doux bloc-texte">{{ formatRelatif(ligneA(ligne).modifie_le) }}</span>
            </span>
          </span>
          <span v-else class="texte-doux">—</span>
        </template>
        <template #actions-ligne="{ ligne }">
          <UiBouton variante="fantome" icone="clock-history" petit icone-seule @click="ouvrirHistorique(ligne)">Historique de la ligne</UiBouton>
        </template>
      </TableauDonnees>

      <HistoriqueFeuille v-model="historiqueOuvert" :feuille-id="feuille.id" :ligne="historiqueLigne" />
      <ImportExcel
        v-model="importOuvert"
        :titre="`Importer les données de « ${feuille.nom} »`"
        :nom-modele="`Donnees_${feuille.nom.replace(/[^\w-]+/g, '_')}`"
        :source="sourceImport"
        @importe="tableau?.recharger()"
      />
      <ImportExcel
        v-model="importAncienOuvert"
        :titre="`Import ancienne donnée dans « ${feuille.nom} »`"
        nom-modele="Modele_ancienne_donnee"
        :source="sourceAncien"
        @importe="rechargerFeuille"
      />
    </template>
  </div>
</template>

<style scoped>
.page-large { max-width: none; }
.infos { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--e3); margin-bottom: var(--e4); align-items: start; }
.titre-bloc { text-transform: uppercase; letter-spacing: 0.04em; font-size: var(--taille-xs); font-weight: 700; color: var(--texte-doux); }
.encart { overflow: hidden; }
.tete-encart { display: flex; align-items: center; gap: var(--e2); width: 100%; padding: var(--e2) var(--e3); border: none; background: none; text-align: left; cursor: pointer; color: var(--marine); }
.tete-encart:hover { background: var(--surface-douce); }
.tete-encart:focus-visible { outline: 2px solid var(--marine-clair); outline-offset: -2px; }
.resume-encart { flex: 1; font-size: var(--taille-xs); color: var(--texte-doux); }
.chevron { color: var(--texte-doux); }
.corps-encart { padding: 0 var(--e4) var(--e3); border-top: 1px solid var(--bordure); padding-top: var(--e3); }
.liste { list-style: none; display: flex; flex-direction: column; gap: var(--e1); font-size: var(--taille-s); }
.liste li { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; }
.bloc { display: inline-flex; margin-top: 2px; }
.nowrap { white-space: nowrap; }
.tableur :deep(td) { white-space: nowrap; }
.eclair { margin-left: 2px; font-size: 0.7rem; }
.temps-estimatif { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--marine); }
.bascule-unite { display: inline-flex; height: 36px; border: 1px solid var(--bordure-forte); border-radius: var(--rayon); overflow: hidden; }
.bascule-unite button { padding: 0 12px; border: none; background: var(--surface); font-size: var(--taille-s); font-weight: 600; color: var(--texte-doux); cursor: pointer; }
.bascule-unite button.actif { background: var(--marine); color: #fff; }
/* En-tête toujours visible : le tableau défile à l'intérieur de la carte (verticalement et horizontalement),
   la ligne de titres reste collée en haut même à la ligne 350. */
.tableur :deep(.tableau-conteneur) { max-height: calc(100vh - 220px); overflow: auto; }
.tableur :deep(thead th) { position: sticky; top: 0; z-index: 3; box-shadow: inset 0 -1px 0 var(--bordure); }
.aide { margin-bottom: var(--e2); }
.note { font-weight: 600; }
.direct { display: inline-flex; align-items: center; gap: var(--e2); padding: 4px 10px; border-radius: 999px; background: var(--succes-pale); color: var(--succes); font-size: var(--taille-xs); font-weight: 600; }
.direct .point { width: 8px; height: 8px; border-radius: 50%; background: currentColor; animation: pulse 2s ease-in-out infinite; }
.direct.hors { background: var(--attention-pale); color: var(--attention); }
@keyframes pulse { 50% { opacity: 0.35; } }
.bandeau { align-items: center; margin-bottom: var(--e3); }
.bandeau span { flex: 1; }
.numero { display: inline-flex; align-items: center; gap: 4px; }
.present :deep(.avatar) { width: 20px; height: 20px; font-size: 0.55rem; box-shadow: 0 0 0 2px var(--rouge); }
.modifie { display: inline-flex; align-items: center; gap: var(--e2); }
.modifie :deep(.avatar) { width: 24px; height: 24px; font-size: 0.6rem; }
.bloc-texte { display: block; }
.note.bonne { color: var(--succes); }
.note.moyenne { color: var(--attention); }
.note.faible { color: var(--danger); }
</style>
