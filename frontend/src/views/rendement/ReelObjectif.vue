<!--
  Rendement > Réel vs Objectif (calculs : backend/rendements/analyse.py, reel_objectif()).
  Comme Globale, sans filtre de tâches ni camembert du temps : deux barres par employé, le réel (tâches de la barre 1,
  Paramètres > Graphiques) et le Rendement objectif (barre 2, modifiable en aperçu), deux jauges sur la même échelle.
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { analyseRendementApi, reelObjectifApi } from '@/api'
import type { DonneesReelObjectif, EmployeGlobale, OptionsRendement } from '@/api/rendements'
import { useToast } from '@/composables/useToast'
import GraphiqueBarresGroupees from '@/components/rendement/GraphiqueBarresGroupees.vue'
import GraphiqueJauge from '@/components/rendement/GraphiqueJauge.vue'
import GraphiqueCamembert from '@/components/rendement/GraphiqueCamembert.vue'
import ListeCases from '@/components/rendement/ListeCases.vue'
import { useSynchronisationRendement } from '@/composables/useSynchronisationRendement'
import UiBouton from '@/components/ui/UiBouton.vue'
import BoutonSourceDonnees from '@/components/rendement/BoutonSourceDonnees.vue'
import { useSourceDonnees } from '@/composables/useSourceDonnees'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'

const toast = useToast()

const choix = reactive({
  affaires: [] as number[], prestations: [] as number[], projets: [] as number[],
  employes: [] as number[], statut: '' as number | '', mois: [] as string[], debut: '', fin: '',
  // Listes à cocher (commentaires complets ; « __sans__ » = Sans commentaire)
  commentaires: [] as string[], commentairesControle: [] as string[],
})
// Synchronisation des données : Affaires et Prestations partagées entre les onglets du Rendement
const synchro = useSynchronisationRendement(choix)

// Données des feuilles (état commun aux onglets du Rendement)
const source = useSourceDonnees()

const filtres = computed(() => ({
  commentaires: choix.commentaires.length ? JSON.stringify(choix.commentaires) : '',
  commentaires_controle: choix.commentairesControle.length ? JSON.stringify(choix.commentairesControle) : '',
  source: source.valeur.value,
  affaires: choix.affaires.join(','), prestations: choix.prestations.join(','), projets: choix.projets.join(','),
  employes: choix.employes.join(','), statut: choix.statut ? String(choix.statut) : '',
  mois: choix.mois.join(','), debut: choix.debut, fin: choix.fin,
}))

const options = ref<OptionsRendement | null>(null)
const donnees = ref<DonneesReelObjectif | null>(null)
const chargement = ref(false)

async function chargerOptions() {
  try {
    options.value = await analyseRendementApi.options({ affaires: filtres.value.affaires, prestations: filtres.value.prestations })
    // (seulement si quelque chose change : sinon les listes se rechargeraient sans fin)
    const prestations = new Set(options.value.prestations.map((p) => p.id))
    if (choix.prestations.some((id) => !prestations.has(id))) choix.prestations = choix.prestations.filter((id) => prestations.has(id))
    const projets = new Set(options.value.projets.map((p) => p.id))
    if (choix.projets.some((id) => !projets.has(id))) choix.projets = choix.projets.filter((id) => projets.has(id))
  } catch (e) {
    toast.erreur(e)
  }
}
async function charger() {
  chargement.value = true
  try {
    donnees.value = await reelObjectifApi.charger(filtres.value)
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargement.value = false
  }
}
onMounted(async () => {
  await chargerOptions()
  charger()
})
watch(() => [choix.affaires, choix.prestations], chargerOptions, { deep: true })
watchDebounced(filtres, charger, { debounce: 350, deep: true })

// --- Objectifs modifiés pour l'aperçu (par prestation) : jamais enregistrés ---------------
const apercu = reactive<Record<number, number>>({})
const apercuActif = computed(() => Object.keys(apercu).length > 0)
const revenir = () => Object.keys(apercu).forEach((k) => delete apercu[Number(k)])
function changerObjectif(id: number, origine: number, e: Event) {
  const v = Number((e.target as HTMLInputElement).value.replace(',', '.'))
  if (!Number.isFinite(v) || v <= 0 || v === origine) delete apercu[id]
  else apercu[id] = v
}
/** Objectif (barre 2) et rentabilité d'un employé, objectifs de l'aperçu compris */
function calculer(e: EmployeGlobale) {
  const mesurees = e.descriptions.filter((d) => d.rendement !== null)
  if (!mesurees.length) return { ...e, objectif: null, rentabilite: null }
  const objectif = mesurees.reduce((s, d) => s + (apercu[d.prestation_id] ?? d.objectif), 0) / mesurees.length
  // Pas de plafond : 2 = deux fois l'objectif
  return { ...e, objectif, rentabilite: e.rendement === null ? null : e.rendement / objectif }
}
const employes = computed(() => (donnees.value?.employes ?? []).map(calculer))
const groupes = computed(() => donnees.value?.barres ?? [])
const reel = computed(() => groupes.value[0])
const detailReel = computed(() => (reel.value?.taches.length ? reel.value.taches.map((t) => t.nom).join(' + ') : 'toutes les tâches'))

/** Jauges : moyennes du réel et de l'objectif des employés mesurés, sur une échelle commune */
const moyenne = (liste: number[]) => (liste.length ? liste.reduce((s, v) => s + v, 0) / liste.length : null)
const mesures = computed(() => employes.value.filter((e) => e.rendement !== null))
const jaugeReel = computed(() => moyenne(mesures.value.map((e) => e.rendement!)))
const jaugeObjectif = computed(() => moyenne(mesures.value.map((e) => e.objectif).filter((o): o is number => o !== null)))
const echelleJauges = computed(() => Math.max((jaugeObjectif.value ?? 0) * 2, (jaugeReel.value ?? 0) * 1.1, 1))

const f = (v: number | null | undefined, decimales = 0) =>
  v === null || v === undefined ? '—' : v.toLocaleString('fr-FR', { maximumFractionDigits: decimales, minimumFractionDigits: decimales })
const unite = computed(() => donnees.value?.unite ?? '')
const unitesDifferentes = computed(() => (donnees.value?.unites.length ?? 0) > 1)

// Source « Pointages » : une seule série, les heures pointées (H_Durée + HS) de la barre 1
const enHeures = computed(() => donnees.value?.source === 'pointages_seuls')
const groupesAffiches = computed(() => (enHeures.value
  ? [{ nom: 'Heures pointées', couleur: groupes.value[0]?.couleur ?? '#18355D', taches: groupes.value[0]?.taches ?? [], objectif: false }]
  : groupes.value))
const barres = computed(() =>
  employes.value.map((e) => ({
    nom: e.identifiant,
    valeurs: enHeures.value ? [e.heures] : [e.rendement, e.rendement === null ? null : e.objectif],
    detail: `${f(e.quantite)} ${unite.value}, ${f(e.heures, 2)} h`,
  })),
)
const partsQuantite = computed(() => employes.value.filter((e) => e.quantite > 0).map((e) => ({ nom: e.identifiant, valeur: e.quantite })))
// Mois proposés (dates de début de la sélection)
const nomMois = (m: string) => {
  const t = new Date(`${m}-01T12:00:00`).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
  return t.charAt(0).toUpperCase() + t.slice(1)
}
const basculerMois = (m: string) => (choix.mois = choix.mois.includes(m) ? choix.mois.filter((x) => x !== m) : [...choix.mois, m])

const exportEnCours = ref(false)
async function exporter() {
  exportEnCours.value = true
  try {
    await reelObjectifApi.exporter(filtres.value)
  } catch (e) {
    toast.erreur(e)
  } finally {
    exportEnCours.value = false
  }
}
</script>

<template>
  <div class="page page-large">
    <header class="ligne-titre">
      <div>
        <h1>Réel vs Objectif</h1>
        <p class="texte-doux texte-petit">Rendement réel de chaque employé, comparé à son Rendement objectif.</p>
      </div>
      <div class="ligne">
        <BoutonSourceDonnees v-if="source.autorise.value" :valeur="source.valeur.value" :autorisees="source.autorisees.value" @choisir="source.choisir" />
        <UiBouton icone="download" :chargement="exportEnCours" @click="exporter">Exporter</UiBouton>
        <UiBouton icone="arrow-clockwise" :chargement="chargement" @click="charger">Actualiser</UiBouton>
      </div>
    </header>

    <p v-if="source.valeur.value === 'feuilles'" class="alerte alerte-attention bandeau-source">
      <i class="bi bi-file-earmark-spreadsheet" aria-hidden="true" />
      Données des feuilles : temps lus dans les feuilles (Temps de prod → Employé, Temps de contrôle → Contrôleur,
      Temps de reprise → Employé reprise), datés à la Date de début. Les tâches sont prises par type (Production, Contrôle, Reprise).
    </p>
    <p v-else-if="source.valeur.value === 'pointages'" class="alerte alerte-attention bandeau-source">
      <i class="bi bi-stopwatch" aria-hidden="true" />
      Données des pointages : toutes les descriptions pointées, même sans feuille. La quantité revient à la personne qui y a pointé
      le plus de temps de Production ; période et mois portent sur le premier jour pointé (pas de statut ni de commentaires de feuille).
    </p>
    <div class="disposition">
      <!-- Filtres -->
      <aside class="colonne-filtres">
        <ListeCases v-model="choix.affaires" v-model:recherche="synchro.recherches.affaires" titre="Affaires" :options="options?.affaires ?? []" aide="Aucune cochée : toutes." />
        <ListeCases v-model="choix.prestations" v-model:recherche="synchro.recherches.prestations" titre="Prestations" :options="options?.prestations ?? []" />
        <ListeCases v-model="choix.projets" titre="Projets / Communes" :options="options?.projets ?? []" />
        <ListeCases v-model="choix.employes" titre="Liste des employés"
          :options="(donnees?.liste_employes ?? []).map((e) => ({ id: e.id, nom: e.identifiant }))" aide="Aucun coché : tous." />
      </aside>

      <!-- Graphiques -->
      <div class="colonne-centre">
        <section class="carte barre-filtres">
          <label class="mini"><span>Statut</span>
            <select v-model="choix.statut" class="saisie">
              <option value="">Tous</option>
              <option v-for="s in options?.statuts ?? []" :key="s.id" :value="s.id">{{ s.nom }}</option>
            </select>
          </label>
          <label class="mini"><span>Du</span><input v-model="choix.debut" class="saisie" type="date" /></label>
          <label class="mini"><span>Au</span><input v-model="choix.fin" class="saisie" type="date" /></label>
          <UiBouton v-if="choix.mois.length || choix.debut || choix.fin || choix.statut" variante="fantome" petit icone="x-lg"
            @click="choix.mois = []; choix.debut = ''; choix.fin = ''; choix.statut = ''">Effacer</UiBouton>
          <div class="mois">
            <span class="mini-titre">Mois (date de début)</span>
            <div class="puces" role="group" aria-label="Mois de la date de début">
              <span v-if="!donnees?.mois_disponibles.length" class="texte-xs texte-doux">Aucune date de début pour cette sélection.</span>
              <button v-for="m in donnees?.mois_disponibles ?? []" :key="m" type="button" class="puce"
                :class="{ active: choix.mois.includes(m) }" :aria-pressed="choix.mois.includes(m)" @click="basculerMois(m)">
                <i v-if="choix.mois.includes(m)" class="bi bi-check2" aria-hidden="true" />{{ nomMois(m) }}
              </button>
            </div>
          </div>
          <p class="texte-xs texte-doux periode-aide">Mois et période : descriptions commencées dans la période (« Date de début » des feuilles). Aucun mois coché : tous.</p>
        </section>

        <UiChargement v-if="chargement && !donnees" />
        <template v-else-if="donnees">
          <p v-if="unitesDifferentes && !enHeures" class="alerte alerte-attention">
            <i class="bi bi-rulers" aria-hidden="true" />
            Unités différentes ({{ donnees.unites.join(', ') }}) : cochez une prestation pour comparer les rendements.
          </p>

          <section class="carte graphique">
            <header class="titre-carte"><i class="bi bi-bar-chart" aria-hidden="true" /> {{ enHeures ? 'Heures pointées par employé' : 'Réel vs Objectif par employé' }}
              <span class="texte-xs texte-doux">({{ enHeures ? 'h, H_Durée + HS' : `${unite || '—'} / j` }})</span></header>
            <UiEtatVide v-if="!barres.length" icone="people" titre="Aucun employé pour cette sélection" />
            <GraphiqueBarresGroupees v-else :groupes="groupesAffiches" :employes="barres" :unite="enHeures ? 'h' : unite" />
            <p v-if="enHeures" class="texte-xs texte-doux">Heures pointées (H_Durée + HS) de chaque employé sur la sélection (source « Pointages » : seulement le temps de la personne à qui revient la description). Tâches de la barre 1 : {{ detailReel }}.</p>
            <p v-else class="texte-xs texte-doux">
              {{ reel?.nom }} : moyenne des rendements des descriptions de l'employé avec le temps de {{ detailReel }}.
              {{ groupes[1]?.nom }} : son Rendement objectif (tableau « Rendement objectif »). Noms, couleurs et tâches : Paramètres > Graphiques.
              <span v-if="apercuActif" class="attention">Aperçu avec des objectifs modifiés.</span>
            </p>
          </section>

          <div v-if="groupes.length === 2" class="jauges">
            <section class="carte graphique">
              <GraphiqueJauge :titre="groupes[0]!.nom" :couleur="groupes[0]!.couleur" :valeur="jaugeReel" :objectif="jaugeObjectif"
                :maximum="echelleJauges" :unite="unite" :detail="`${detailReel}, moyenne de ${mesures.length} employé(s)`" />
            </section>
            <section class="carte graphique">
              <GraphiqueJauge :titre="groupes[1]!.nom" :couleur="groupes[1]!.couleur" :valeur="jaugeObjectif" :objectif="jaugeObjectif"
                :maximum="echelleJauges" :unite="unite" sans-comparaison :detail="`Moyenne des objectifs de ${mesures.length} employé(s)`" />
            </section>
          </div>

          <div class="camemberts">
            <section class="carte graphique">
              <header class="titre-carte"><i class="bi bi-pie-chart" aria-hidden="true" /> Somme de Quantité par Employé</header>
              <UiEtatVide v-if="!partsQuantite.length" icone="pie-chart" titre="Aucune quantité" />
              <GraphiqueCamembert v-else :parts="partsQuantite" :unite="unite || 'quantité'" />
            </section>
          </div>
        </template>
      </div>

      <!-- Objectifs et rentabilités -->
      <aside class="colonne-droite">
        <section class="carte bloc">
          <header class="entete">Rendement objectif</header>
          <p v-if="!donnees?.objectifs.length" class="texte-xs texte-doux">Aucune description pour cette sélection.</p>
          <table v-else class="tableau-simple">
            <thead><tr><th>Prestation</th><th class="droite">Objectif / j</th></tr></thead>
            <tbody>
              <tr v-for="o in donnees.objectifs" :key="o.id" :class="{ modifie: apercu[o.id] !== undefined }">
                <td class="tronque" :title="o.nom">{{ o.nom }}</td>
                <td class="droite nowrap">
                  <input class="saisie saisie-objectif" type="number" min="0" step="any" :value="apercu[o.id] ?? o.objectif"
                    :aria-label="`Objectif de ${o.nom} (aperçu)`" :title="`Vrai objectif : ${f(o.objectif, 2)} ${o.unite}`"
                    @change="changerObjectif(o.id, o.objectif, $event)" />
                  <span class="texte-xs texte-doux unite-objectif">{{ o.unite }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="donnees?.objectifs.length" class="texte-xs texte-doux">Aperçu seulement : rien n'est enregistré.</p>
          <UiBouton v-if="apercuActif" variante="fantome" petit icone="arrow-counterclockwise" @click="revenir">Revenir aux vrais objectifs</UiBouton>
        </section>

        <section class="carte bloc">
          <header class="entete">Rentabilités</header>
          <p v-if="!employes.length" class="texte-xs texte-doux">Aucun employé.</p>
          <table v-else class="tableau-simple">
            <thead><tr><th>Employé</th><th class="droite">Rentabilités</th></tr></thead>
            <tbody>
              <tr v-for="e in employes" :key="e.id">
                <td class="tronque" :title="e.nom_affiche">{{ e.identifiant }}</td>
                <td class="droite">
                  <span v-if="e.rentabilite === null" class="texte-doux">—</span>
                  <span v-else class="rentabilite" :class="e.rentabilite >= 1 ? 'ok' : 'ko'"
                    :title="`Réel ${f(e.rendement)} / objectif ${f(e.objectif)} ${unite}`">{{ f(e.rentabilite, 2) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          <p class="texte-xs texte-doux">Rendement ÷ objectif : 1,00 = objectif atteint, 2,00 = le double.</p>
        </section>
        <ListeCases v-model="choix.commentaires" titre="Commentaires" :options="options?.commentaires ?? []"
          aide="Aucun coché : tous." />
        <ListeCases v-model="choix.commentairesControle" titre="Commentaires contrôle" :options="options?.commentaires_controle ?? []"
          aide="Aucun coché : tous." />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.page-large { max-width: none; }
.ligne-titre { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e3); margin-bottom: var(--e4); }
.bandeau-source { margin-bottom: var(--e4); }
.disposition { display: grid; grid-template-columns: 250px minmax(0, 1fr) 290px; gap: var(--e4); align-items: start; }
.colonne-filtres, .colonne-droite, .colonne-centre { display: flex; flex-direction: column; gap: var(--e3); min-width: 0; }
.colonne-centre { gap: var(--e4); }
.barre-filtres { display: flex; align-items: flex-end; gap: var(--e3); flex-wrap: wrap; padding: var(--e3) var(--e4); }
.periode-aide { flex-basis: 100%; }
.mois { flex-basis: 100%; display: flex; flex-direction: column; gap: 4px; }
.mini-titre { font-size: var(--taille-xs); color: var(--texte-doux); }
.puces { display: flex; flex-wrap: wrap; gap: var(--e1); }
.puce { display: inline-flex; align-items: center; gap: 4px; padding: 3px 12px; border: 1px solid var(--bordure-forte); border-radius: 999px; background: var(--surface); font-size: var(--taille-s); color: var(--texte); cursor: pointer; }
.puce:hover { border-color: var(--marine-clair); }
.puce.active { background: var(--marine); border-color: var(--marine); color: #fff; font-weight: 600; }
.mini { display: flex; flex-direction: column; gap: 2px; font-size: var(--taille-xs); color: var(--texte-doux); }
.mini .saisie { height: 32px; width: auto; min-width: 130px; }
.graphique { padding: var(--e3) var(--e4); display: flex; flex-direction: column; gap: var(--e2); }
.titre-carte { display: flex; align-items: center; gap: var(--e2); font-weight: 700; color: var(--marine); }
.jauges { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: var(--e4); }
.pastille-groupe { display: inline-block; width: 9px; height: 9px; margin-right: 4px; border-radius: 2px; }
.camemberts { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: var(--e4); }
.bloc { padding: var(--e2); display: flex; flex-direction: column; gap: var(--e2); }
.entete { padding: var(--e2); border-radius: var(--rayon); background: var(--marine); color: #fff; font-weight: 600; font-size: var(--taille-s); text-align: center; }
.tableau-simple { width: 100%; border-collapse: collapse; font-size: var(--taille-s); }
.tableau-simple th { text-align: left; font-size: var(--taille-xs); color: var(--texte-doux); font-weight: 600; padding: 4px; border-bottom: 1px solid var(--bordure-forte); }
.tableau-simple td { padding: 4px; border-bottom: 1px solid var(--bordure); }
.tableau-simple .droite { text-align: right; }
.tronque { max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nowrap { white-space: nowrap; }
.saisie-objectif { width: 80px; height: 28px; padding: 0 6px; text-align: right; }
.unite-objectif { display: inline-block; min-width: 34px; margin-left: 4px; text-align: left; }
tr.modifie .saisie-objectif { border-color: var(--attention); background: color-mix(in srgb, var(--attention) 10%, var(--surface)); font-weight: 700; }
.rentabilite { display: inline-block; min-width: 48px; padding: 1px 8px; border-radius: 999px; font-weight: 700; text-align: center; font-variant-numeric: tabular-nums; }
.rentabilite.ok { background: color-mix(in srgb, var(--succes) 15%, transparent); color: var(--succes); }
.rentabilite.ko { background: color-mix(in srgb, var(--rouge) 12%, transparent); color: var(--rouge); }
.attention { color: var(--attention); font-weight: 600; }
@media (max-width: 1300px) {
  .disposition { grid-template-columns: 1fr; }
}
</style>
