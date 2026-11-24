<!--
  Rendement > Evolution (calculs : backend/rendements/analyse.py, evolution()).
  Comme Globale, sans projets / communes, sans filtre de tâches ni camembert des quantités : deux courbes de rendement
  par date pointée, chacune pour un groupe de tâches défini dans Paramètres > Graphiques, et l'écart en % entre elles.
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { analyseRendementApi, evolutionRendementApi } from '@/api'
import type { DonneesEvolution, EmployeGlobale, OptionsRendement } from '@/api/rendements'
import { useToast } from '@/composables/useToast'
import GraphiqueCourbes from '@/components/rendement/GraphiqueCourbes.vue'
import { calculerEcarts, dansTolerance, formatPct } from '@/utils/rendement'
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
  affaires: [] as number[], prestations: [] as number[],
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
  affaires: choix.affaires.join(','), prestations: choix.prestations.join(','),
  employes: choix.employes.join(','), statut: choix.statut ? String(choix.statut) : '',
  mois: choix.mois.join(','), debut: choix.debut, fin: choix.fin,
}))

const options = ref<OptionsRendement | null>(null)
const donnees = ref<DonneesEvolution | null>(null)
const chargement = ref(false)

async function chargerOptions() {
  try {
    options.value = await analyseRendementApi.options({ affaires: filtres.value.affaires, prestations: filtres.value.prestations })
    // (seulement si quelque chose change : sinon les listes se rechargeraient sans fin)
    const prestations = new Set(options.value.prestations.map((p) => p.id))
    if (choix.prestations.some((id) => !prestations.has(id))) choix.prestations = choix.prestations.filter((id) => prestations.has(id))
  } catch (e) {
    toast.erreur(e)
  }
}
async function charger() {
  chargement.value = true
  try {
    donnees.value = await evolutionRendementApi.charger(filtres.value)
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
/** Objectif, rendement moyen et rentabilité d'un employé, objectifs de l'aperçu compris */
function calculer(e: EmployeGlobale) {
  const mesurees = e.descriptions.filter((d) => d.rendement !== null)
  if (!mesurees.length) return { objectif: null, rentabilite: null }
  const objectif = mesurees.reduce((s, d) => s + (apercu[d.prestation_id] ?? d.objectif), 0) / mesurees.length
  // Pas de plafond : 2 = deux fois l'objectif
  return { objectif, rentabilite: e.rendement === null ? null : e.rendement / objectif }
}
const employes = computed(() => (donnees.value?.employes ?? []).map((e) => ({ ...e, ...calculer(e) })))

const f = (v: number | null | undefined, decimales = 0) =>
  v === null || v === undefined ? '—' : v.toLocaleString('fr-FR', { maximumFractionDigits: decimales, minimumFractionDigits: decimales })
const unite = computed(() => donnees.value?.unite ?? '')
const unitesDifferentes = computed(() => (donnees.value?.unites.length ?? 0) > 1)

const courbes = computed(() =>
  (donnees.value?.courbes ?? []).map((c) => ({
    ...c, detail: c.taches.length ? c.taches.map((t) => t.nom).join(' + ') : 'toutes les tâches',
  })),
)
/** Objectif affiché : celui de la prestation (aperçu compris), s'il n'y en a qu'une */
const objectifCourbes = computed(() => {
  const o = donnees.value?.objectifs ?? []
  return o.length === 1 ? apercu[o[0]!.id] ?? o[0]!.objectif : null
})
const aucuneCourbe = computed(() => !(donnees.value?.dates.length))

// --- Écart entre les deux courbes : panneau, affichage et tolérance ------------------
const ecart = reactive({ afficher: true, min: 0, max: 0 })
const ecarts = computed(() => calculerEcarts(donnees.value?.courbes ?? []))
const ecartMoyen = computed(() => (ecarts.value.length ? ecarts.value.reduce((s, e) => s + e.pct, 0) / ecarts.value.length : null))
/** Écarts hors tolérance : les seuls affichés sur le graphique */
const ecartsVisibles = computed(() => ecarts.value.filter((e) => !dansTolerance(e.pct, ecart.min, ecart.max)))
const dateCourte = (i: number) =>
  new Date(`${donnees.value!.dates[i]}T12:00:00`).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })
const partsTemps = computed(() => (donnees.value?.temps_par_tache ?? []).map((t) => ({ nom: t.nom, valeur: t.heures })))
const titreTemps = computed(() => {
  const noms = (donnees.value?.taches_camembert ?? []).map((t) => `Temps de ${t.nom}`)
  return noms.length ? `Somme de ${noms.join(' et somme de ')}` : 'Somme du temps par tâche'
})

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
    await evolutionRendementApi.exporter(filtres.value)
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
        <h1>Évolution du rendement</h1>
        <p class="texte-doux texte-petit">Rendement par date pointée pour deux groupes de tâches, rentabilités de la sélection.</p>
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
        <ListeCases v-model="choix.employes" titre="Liste des employés"
          :options="(donnees?.liste_employes ?? []).map((e) => ({ id: e.id, nom: e.identifiant }))" aide="Aucun coché : tous." />

        <section class="liste-ecart carte">
          <header class="entete-ecart">Écart entre les courbes</header>
          <div class="moyenne" :title="`Moyenne sur ${ecarts.length} date(s) où les deux courbes existent`">
            <span class="texte-xs texte-doux">Écart moyen</span>
            <strong>{{ ecartMoyen === null ? '—' : formatPct(ecartMoyen) }}</strong>
            <span v-if="donnees?.courbes.length === 2" class="texte-xs texte-doux">{{ donnees.courbes[1]!.nom }} / {{ donnees.courbes[0]!.nom }}</span>
          </div>
          <label class="bascule-ecart">
            <input v-model="ecart.afficher" type="checkbox" role="switch" />
            <span class="interrupteur" aria-hidden="true" />
            Afficher les écarts sur le graphique
          </label>
          <fieldset class="tolerance" :disabled="!ecart.afficher">
            <legend class="texte-xs">Tolérance (non affichés)</legend>
            <label>de <input v-model.number="ecart.min" class="saisie" type="number" step="0.5" aria-label="Tolérance minimale en %" /> %</label>
            <label>à <input v-model.number="ecart.max" class="saisie" type="number" step="0.5" aria-label="Tolérance maximale en %" /> %</label>
          </fieldset>
          <ul v-if="ecarts.length" class="liste-dates">
            <li v-for="e in ecarts" :key="e.i" :class="{ masque: dansTolerance(e.pct, ecart.min, ecart.max) }"
              :title="dansTolerance(e.pct, ecart.min, ecart.max) ? 'Dans la tolérance : non affiché' : undefined">
              <span>{{ dateCourte(e.i) }}</span><span class="gras">{{ formatPct(e.pct) }}</span>
            </li>
          </ul>
          <p v-else class="texte-xs texte-doux">Aucune date où les deux courbes existent.</p>
        </section>
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
          <p v-if="unitesDifferentes" class="alerte alerte-attention">
            <i class="bi bi-rulers" aria-hidden="true" />
            Unités différentes ({{ donnees.unites.join(', ') }}) : cochez une prestation pour comparer les rendements.
          </p>

          <section class="carte graphique">
            <header class="titre-carte"><i class="bi bi-graph-up" aria-hidden="true" /> Évolution du rendement
              <span class="texte-xs texte-doux">({{ unite || '—' }} / j, par date pointée)</span></header>
            <UiEtatVide v-if="unitesDifferentes" icone="rulers" titre="Unités différentes" texte="Cochez une prestation pour tracer les courbes." />
            <UiEtatVide v-else-if="aucuneCourbe" icone="graph-up" titre="Aucun pointage pour cette sélection" />
            <GraphiqueCourbes v-else :dates="donnees.dates" :courbes="courbes" :objectif="objectifCourbes" :unite="unite"
              :ecarts="ecart.afficher ? ecartsVisibles : []" />
            <p class="texte-xs texte-doux">
              Chaque courbe : quantité ÷ temps des tâches de la courbe × {{ f(donnees.heures_par_jour, 0) }} h, la quantité d'une description
              étant répartie sur ses dates au prorata de ce temps. Écart : (courbe 2 − courbe 1) ÷ courbe 1, aux dates où les deux existent.
              Groupes de tâches, noms et couleurs : Paramètres > Graphiques.
              <span v-if="apercuActif" class="attention">Aperçu avec des objectifs modifiés.</span>
            </p>
          </section>

          <div class="camemberts">
            <section class="carte graphique">
              <header class="titre-carte"><i class="bi bi-pie-chart-fill" aria-hidden="true" /> {{ titreTemps }}</header>
              <UiEtatVide v-if="!partsTemps.length" icone="pie-chart" titre="Aucun temps pointé" />
              <GraphiqueCamembert v-else :parts="partsTemps" unite="h" :decimales="2" />
              <p class="texte-xs texte-doux">Tâches choisies dans Paramètres > Graphiques{{ donnees.taches_camembert.length ? '' : ' : aucune cochée, toutes les tâches sont affichées' }}.</p>
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
                    :title="`Rendement ${f(e.rendement)} / objectif ${f(e.objectif)} ${unite}`">{{ f(e.rentabilite, 2) }}</span>
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
.liste-ecart { display: flex; flex-direction: column; gap: var(--e2); padding: var(--e2); }
.entete-ecart { padding: var(--e2); border-radius: var(--rayon); background: var(--marine); color: #fff; font-weight: 600; font-size: var(--taille-s); text-align: center; }
.moyenne { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: var(--e2); border-radius: var(--rayon); background: var(--surface-douce); }
.moyenne strong { font-size: var(--taille-l); color: var(--marine); }
.bascule-ecart { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-s); cursor: pointer; }
.bascule-ecart input { position: absolute; opacity: 0; }
.interrupteur { position: relative; width: 34px; height: 18px; flex: none; border-radius: 999px; background: var(--bordure-forte); transition: background 0.15s; }
.interrupteur::after { content: ''; position: absolute; top: 2px; left: 2px; width: 14px; height: 14px; border-radius: 50%; background: #fff; transition: transform 0.15s; }
.bascule-ecart input:checked + .interrupteur { background: var(--marine); }
.bascule-ecart input:checked + .interrupteur::after { transform: translateX(16px); }
.bascule-ecart input:focus-visible + .interrupteur { outline: 2px solid var(--marine-clair); outline-offset: 2px; }
.tolerance { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; border: none; padding: 0; font-size: var(--taille-s); }
.tolerance legend { color: var(--texte-doux); margin-bottom: 4px; }
.tolerance .saisie { width: 64px; height: 28px; padding: 0 6px; text-align: right; }
.tolerance:disabled { opacity: 0.5; }
.liste-dates { list-style: none; display: flex; flex-direction: column; gap: 2px; max-height: 150px; overflow-y: auto; font-size: var(--taille-s); }
.liste-dates li { display: flex; justify-content: space-between; padding: 2px var(--e2); border-radius: var(--rayon-s); background: var(--surface-douce); }
.liste-dates li.masque { opacity: 0.45; text-decoration: line-through; }
@media (max-width: 1300px) {
  .disposition { grid-template-columns: 1fr; }
}
</style>
