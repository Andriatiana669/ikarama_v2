<!--
  Rendement > Analyse (calculs : backend/rendements/analyse.py, analyse_employes()).
  Employés comparés côte à côte : pour le mois choisi, où chacun passe son temps (affaire / prestation) et avec quelle
  rentabilité (carte à bulles + tableau), puis le suivi mois par mois avec les signaux automatiques
  (Aide, En adaptation, Baisse soudaine ; seuils dans Paramètres > Graphiques).
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { analyseEmployesApi, analyseRendementApi } from '@/api'
import type { CaseAnalyse, DonneesAnalyse, OptionsRendement } from '@/api/rendements'
import { useToast } from '@/composables/useToast'
import GraphiqueBulles from '@/components/rendement/GraphiqueBulles.vue'
import ListeCases from '@/components/rendement/ListeCases.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import BoutonSourceDonnees from '@/components/rendement/BoutonSourceDonnees.vue'
import { useSourceDonnees } from '@/composables/useSourceDonnees'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'

const toast = useToast()
const choix = reactive({ affaires: [] as number[], prestations: [] as number[], taches: [] as number[], employes: [] as number[], mois: [] as string[] })
// Données des feuilles (état commun aux onglets du Rendement)
const source = useSourceDonnees()

const filtres = computed(() => ({
  source: source.valeur.value,
  affaires: choix.affaires.join(','), prestations: choix.prestations.join(','), taches: choix.taches.join(','),
  employes: choix.employes.join(','), mois: choix.mois.join(','),
}))
const options = ref<OptionsRendement | null>(null)
const donnees = ref<DonneesAnalyse | null>(null)
const chargement = ref(false)

async function chargerOptions() {
  try {
    options.value = await analyseRendementApi.options({ affaires: filtres.value.affaires })
    const prestations = new Set(options.value.prestations.map((p) => p.id))
    if (choix.prestations.some((id) => !prestations.has(id))) choix.prestations = choix.prestations.filter((id) => prestations.has(id))
  } catch (e) {
    toast.erreur(e)
  }
}
async function charger() {
  chargement.value = true
  try {
    donnees.value = await analyseEmployesApi.charger(filtres.value)
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
watch(() => choix.affaires, chargerOptions, { deep: true })
watchDebounced(filtres, charger, { debounce: 350, deep: true })

const nomMois = (m: string, court = false) => {
  const t = new Date(`${m}-01T12:00:00`).toLocaleDateString('fr-FR', court ? { month: 'short', year: '2-digit' } : { month: 'long', year: 'numeric' })
  return t.charAt(0).toUpperCase() + t.slice(1)
}
const basculerMois = (m: string) => (choix.mois = choix.mois.includes(m) ? choix.mois.filter((x) => x !== m) : [...choix.mois, m])
/** « Novembre 2026 », « Octobre et Novembre 2026 »… ou « Tous les mois » */
const periode = computed(() => {
  const mois = [...choix.mois].sort()
  if (!mois.length) return 'Tous les mois'
  return mois.length <= 3 ? mois.map((m) => nomMois(m)).join(', ') : `${mois.length} mois`
})
const estAnalyse = (m: string) => choix.mois.includes(m)
const titreSignal = (b: { code: string; mois?: string[] }) =>
  `${AIDE_BADGES[b.code]}${b.mois?.length ? ` (${b.mois.map((m) => nomMois(m, true)).join(', ')})` : ''}`
const f = (v: number | null | undefined, d = 0) => (v === null || v === undefined ? '—' : v.toLocaleString('fr-FR', { maximumFractionDigits: d, minimumFractionDigits: d }))
const pct = (v: number) => `${Math.round(v * 100)} %`
const ZONES: Record<string, string> = { garder: 'z-garder', revoir: 'z-revoir', potentiel: 'z-potentiel', ponctuel: 'z-ponctuel', aide: 'z-aide' }
const ICONES: Record<string, string> = { aide: 'life-preserver', adaptation: 'hourglass-split', baisse: 'graph-down-arrow' }
const AIDE_BADGES: Record<string, string> = {
  aide: 'Temps surtout passé sur les lignes d’autres personnes : rendement non jugé',
  adaptation: 'Premiers mois sur cette prestation, rendement encore sous l’objectif',
  baisse: 'Chute nette par rapport à ses mois précédents, alors qu’il est bon ailleurs ce mois-ci',
}
const points = (e: DonneesAnalyse['employes'][number]) =>
  e.carte.filter((c) => c.rentabilite !== null).map((c) => ({
    nom: c.prestation, part: c.part, rentabilite: c.rentabilite!, heures: c.heures, zone: c.zone ?? '',
    detail: `${c.affaire}, ${f(c.heures, 1)} h`,
  }))
/** Couleur d'une case du suivi : verte si rentabilité ≥ 1, rouge sinon, intensité selon l'écart */
function fondCase(c: CaseAnalyse) {
  if (c.rentabilite === null) return { background: 'var(--surface-douce)' }
  const ecart = Math.min(1, Math.abs(c.rentabilite - 1))
  const couleur = c.rentabilite >= 1 ? '30, 138, 90' : '233, 66, 66'
  return { background: `rgba(${couleur}, ${0.12 + ecart * 0.45})` }
}

const exportEnCours = ref(false)
async function exporter() {
  exportEnCours.value = true
  try {
    await analyseEmployesApi.exporter(filtres.value)
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
        <h1>Analyse mensuelle des employés</h1>
        <p class="texte-doux texte-petit">Où chacun passe son temps sur la période choisie, avec quel résultat, et comment cela évolue mois après mois.</p>
      </div>
      <div class="ligne">
        <BoutonSourceDonnees v-if="source.autorise.value" :valeur="source.valeur.value" :autorisees="source.autorisees.value" @choisir="source.choisir" />
        <UiBouton icone="download" :chargement="exportEnCours" :desactive="!choix.employes.length" @click="exporter">Exporter</UiBouton>
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
      <aside class="colonne-filtres">
        <ListeCases v-model="choix.employes" titre="Employés à comparer"
          :options="(donnees?.liste_employes ?? []).map((e) => ({ id: e.id, nom: e.identifiant }))" aide="Cochez un ou plusieurs employés." />
        <ListeCases v-model="choix.affaires" titre="Affaires" :options="options?.affaires ?? []" aide="Aucune cochée : toutes." />
        <ListeCases v-model="choix.prestations" titre="Prestations" :options="options?.prestations ?? []" aide="Aucune cochée : toutes." />
        <ListeCases v-model="choix.taches" titre="Tâches" :options="options?.taches ?? []" aide="Seules les cochées comptent dans le temps (aucune : toutes)." />
      </aside>

      <div class="colonne-centre">
        <section class="carte barre-mois">
          <span class="mini-titre">Mois analysés (aucun coché : tous)</span>
          <div class="puces" role="group" aria-label="Mois analysés">
            <span v-if="!donnees?.mois_disponibles.length" class="texte-xs texte-doux">Cochez un employé pour voir ses mois.</span>
            <button v-for="m in donnees?.mois_disponibles ?? []" :key="m" type="button" class="puce"
              :class="{ active: estAnalyse(m) }" :aria-pressed="estAnalyse(m)" @click="basculerMois(m)">
              <i v-if="estAnalyse(m)" class="bi bi-check2" aria-hidden="true" />{{ nomMois(m) }}
            </button>
            <UiBouton v-if="choix.mois.length" variante="fantome" petit icone="x-lg" @click="choix.mois = []">Tous les mois</UiBouton>
          </div>
          <p v-if="donnees" class="texte-xs texte-doux">
            Zones : « beaucoup de temps » dès {{ donnees.seuils.temps }} % du mois. Signaux : aide dès {{ donnees.seuils.aide }} %,
            adaptation pendant {{ donnees.seuils.adaptation }} mois, baisse soudaine dès −{{ donnees.seuils.baisse }} % (Paramètres > Graphiques).
          </p>
        </section>

        <UiEtatVide v-if="!choix.employes.length" class="carte" icone="people" titre="Choisissez les employés à comparer"
          texte="Cochez un ou plusieurs employés dans la liste « Employés à comparer »." />
        <UiChargement v-else-if="chargement && !donnees?.employes.length" />
        <div v-else class="employes">
          <article v-for="e in donnees?.employes ?? []" :key="e.id" class="carte employe">
            <header class="tete">
              <div>
                <h2>{{ e.identifiant }}</h2>
                <p class="texte-xs texte-doux">{{ e.nom_affiche }}, {{ periode }} : {{ f(e.heures_mois, 1) }} h pointées</p>
              </div>
            </header>

            <UiEtatVide v-if="!e.carte.length" icone="calendar-x" titre="Rien de pointé sur cette période" />
            <template v-else>
              <GraphiqueBulles v-if="points(e).length" :points="points(e)" :seuil-temps="donnees!.seuils.temps" />
              <div class="tableau-conteneur">
                <table class="tableau-simple">
                  <thead><tr><th>Affaire / Prestation</th><th class="droite">Temps</th><th class="droite">Rentab.</th><th>Zone et signaux</th></tr></thead>
                  <tbody>
                    <tr v-for="c in e.carte" :key="c.cle">
                      <td><span class="gras">{{ c.prestation }}</span><span class="texte-xs texte-doux bloc-texte">{{ c.affaire }}</span></td>
                      <td class="droite nowrap" :title="c.heures_aide ? `dont ${f(c.heures_aide, 1)} h d’aide` : undefined">
                        {{ pct(c.part) }}<span class="texte-xs texte-doux bloc-texte">{{ f(c.heures, 1) }} h</span>
                      </td>
                      <td class="droite nowrap" :title="c.rendement !== null ? `${f(c.rendement)} / ${f(c.objectif)} ${c.unite} par jour` : undefined">
                        <span v-if="c.rentabilite !== null" class="rentab" :class="c.rentabilite >= 1 ? 'ok' : 'ko'">{{ f(c.rentabilite, 2) }}</span>
                        <span v-else class="texte-doux">—</span>
                      </td>
                      <td>
                        <span v-if="c.zone" class="zone" :class="ZONES[c.zone]">{{ c.zone_libelle }}</span>
                        <span v-for="b in c.badges" :key="b.code" class="signal" :class="`s-${b.code}`" :title="titreSignal(b)">
                          <i :class="`bi bi-${ICONES[b.code]}`" aria-hidden="true" /> {{ b.libelle }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>

            <h3 class="sous-titre"><i class="bi bi-calendar3" aria-hidden="true" /> Suivi mois par mois</h3>
            <div class="tableau-conteneur">
              <table class="suivi">
                <thead>
                  <tr><th>Prestation</th><th v-for="m in e.suivi.mois" :key="m" :class="{ courant: estAnalyse(m) }">{{ nomMois(m, true) }}</th></tr>
                </thead>
                <tbody>
                  <tr v-for="l in e.suivi.lignes" :key="l.cle">
                    <td class="nom-ligne" :title="l.affaire"><span class="gras">{{ l.prestation }}</span><span class="texte-xs texte-doux bloc-texte">{{ l.affaire }}</span></td>
                    <td v-for="m in e.suivi.mois" :key="m" class="cellule" :class="{ courant: estAnalyse(m) }" :style="l.cases[m] ? fondCase(l.cases[m]!) : undefined"
                      :title="l.cases[m] ? `${pct(l.cases[m]!.part)} du temps (${f(l.cases[m]!.heures, 1)} h), rentabilité ${f(l.cases[m]!.rentabilite, 2)}${l.cases[m]!.badges.length ? ' : ' + l.cases[m]!.badges.map((b) => b.libelle).join(', ') : ''}` : 'Pas de temps ce mois-ci'">
                      <template v-if="l.cases[m]">
                        <span class="valeur">{{ l.cases[m]!.rentabilite === null ? '—' : f(l.cases[m]!.rentabilite, 2) }}</span>
                        <span class="part">{{ pct(l.cases[m]!.part) }}</span>
                        <span v-if="l.cases[m]!.badges.length" class="icones">
                          <i v-for="b in l.cases[m]!.badges" :key="b.code" :class="`bi bi-${ICONES[b.code]}`" aria-hidden="true" />
                        </span>
                      </template>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-large { max-width: none; }
.ligne-titre { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e3); margin-bottom: var(--e4); }
.bandeau-source { margin-bottom: var(--e4); }
.disposition { display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: var(--e4); align-items: start; }
.colonne-filtres, .colonne-centre { display: flex; flex-direction: column; gap: var(--e3); min-width: 0; }
.colonne-centre { gap: var(--e4); }
.barre-mois { display: flex; flex-direction: column; gap: var(--e2); padding: var(--e3) var(--e4); }
.mini-titre { font-size: var(--taille-xs); color: var(--texte-doux); }
.puces { display: flex; flex-wrap: wrap; gap: var(--e1); }
.puce { padding: 3px 12px; border: 1px solid var(--bordure-forte); border-radius: 999px; background: var(--surface); font-size: var(--taille-s); cursor: pointer; }
.puce { display: inline-flex; align-items: center; gap: 4px; }
.puce.active { background: var(--marine); border-color: var(--marine); color: #fff; font-weight: 600; }
.employes { display: grid; grid-template-columns: repeat(auto-fit, minmax(460px, 1fr)); gap: var(--e4); }
.employe { padding: var(--e3) var(--e4); display: flex; flex-direction: column; gap: var(--e3); min-width: 0; }
.employe :deep(.bulles) { max-width: 560px; align-self: center; }
.tete h2 { font-size: var(--taille-l); color: var(--marine); }
.sous-titre { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-s); color: var(--marine); margin-top: var(--e2); }
.tableau-simple { width: 100%; border-collapse: collapse; font-size: var(--taille-s); }
.tableau-simple th { text-align: left; font-size: var(--taille-xs); color: var(--texte-doux); font-weight: 600; padding: 4px; border-bottom: 1px solid var(--bordure-forte); }
.tableau-simple td { padding: 5px 4px; border-bottom: 1px solid var(--bordure); vertical-align: top; }
.droite { text-align: right; }
.nowrap { white-space: nowrap; }
.bloc-texte { display: block; }
.rentab { display: inline-block; min-width: 44px; padding: 1px 8px; border-radius: 999px; font-weight: 700; text-align: center; }
.rentab.ok { background: color-mix(in srgb, var(--succes) 15%, transparent); color: var(--succes); }
.rentab.ko { background: color-mix(in srgb, var(--rouge) 12%, transparent); color: var(--rouge); }
.zone { display: inline-block; margin: 0 4px 3px 0; padding: 1px 8px; border-radius: 999px; font-size: var(--taille-xs); font-weight: 700; color: #fff; }
.z-garder { background: #1e8a5a; } .z-revoir { background: #e94242; } .z-potentiel { background: #24497a; } .z-ponctuel { background: #b7791f; } .z-aide { background: #64748b; }
.signal { display: inline-flex; align-items: center; gap: 3px; margin: 0 4px 3px 0; padding: 1px 8px; border: 1px solid; border-radius: 999px; font-size: var(--taille-xs); font-weight: 600; }
.s-aide { color: #475569; border-color: #94a3b8; }
.s-adaptation { color: #b7791f; border-color: #e5c07b; }
.s-baisse { color: #c53030; border-color: #f2a5a5; }
.suivi { border-collapse: separate; border-spacing: 3px; font-size: var(--taille-xs); }
.suivi th { padding: 2px 6px; color: var(--texte-doux); font-weight: 600; text-align: center; white-space: nowrap; }
.suivi th.courant { color: var(--marine); }
.nom-ligne { min-width: 130px; max-width: 170px; padding-right: var(--e2); font-size: var(--taille-s); }
.cellule { width: 64px; min-width: 64px; height: 44px; border-radius: var(--rayon-s); text-align: center; vertical-align: middle; }
.cellule.courant { outline: 2px solid var(--marine); outline-offset: -1px; }
.cellule .valeur { display: block; font-weight: 700; color: var(--marine); font-size: var(--taille-s); }
.cellule .part { display: block; color: var(--texte-doux); }
.cellule .icones { display: block; color: var(--marine); font-size: 0.65rem; }
@media (max-width: 1100px) { .disposition { grid-template-columns: 1fr; } .employes { grid-template-columns: 1fr; } }
</style>
