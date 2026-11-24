<!--
  Rendement : rendement réel comparé au rendement objectif (calculs : backend/rendements/analyse.py).
  Filtres : affaires, prestations, projets / communes, tâches (seules les cochées comptent dans le temps),
  statut du projet et période. Sans affaire cochée : rien. Barres : le niveau en dessous de la sélection
  (prestations, projets, descriptions) précédé du Global (si une seule unité).
  Tableau « Rendement objectif » : on peut modifier les objectifs pour un APERÇU, rien n'est enregistré.
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { analyseRendementApi } from '@/api'
import type { AnalyseRendement, FiltresRendement, OptionsRendement } from '@/api/rendements'
import { useToast } from '@/composables/useToast'
import GraphiqueAires from '@/components/rendement/GraphiqueAires.vue'
import GraphiqueBarres from '@/components/rendement/GraphiqueBarres.vue'
import ListeCases from '@/components/rendement/ListeCases.vue'
import UiAvatar from '@/components/ui/UiAvatar.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'

const toast = useToast()

const choix = reactive({
  affaires: [] as number[],
  prestations: [] as number[],
  projets: [] as number[],
  taches: [] as number[],
  statut: '' as number | '',
  debut: '',
  fin: '',
  granularite: 'jour' as 'jour' | 'mois',
})
const onglet = ref<'projets' | 'personnes'>('projets')
const rechercheEmployes = ref('')

const filtres = computed<FiltresRendement>(() => ({
  affaires: choix.affaires.join(','),
  prestations: choix.prestations.join(','),
  projets: choix.projets.join(','),
  taches: choix.taches.join(','),
  statut: choix.statut ? String(choix.statut) : '',
  debut: choix.debut,
  fin: choix.fin,
  granularite: choix.granularite,
}))

const options = ref<OptionsRendement | null>(null)
const analyse = ref<AnalyseRendement | null>(null)
const chargement = ref(false)

async function chargerOptions() {
  try {
    options.value = await analyseRendementApi.options(filtres.value)
    // Une prestation ou un projet qui ne fait plus partie des listes est décoché
    // (seulement si quelque chose change : sinon la liste rechargerait les options sans fin)
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
    analyse.value = await analyseRendementApi.analyser(filtres.value)
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

// Titre : la sélection en cours
const noms = (liste: { id: number; nom: string }[] | undefined, ids: number[]) =>
  (liste ?? []).filter((o) => ids.includes(o.id)).map((o) => o.nom)
const titre = computed(() => {
  const o = options.value
  const morceaux = [
    noms(o?.affaires, choix.affaires).join(', ') || 'Toutes les affaires',
    noms(o?.prestations, choix.prestations).join(', '),
    noms(o?.projets, choix.projets).join(', '),
    noms(o?.taches, choix.taches).join(', '),
  ].filter(Boolean)
  return morceaux.join(' - ')
})

const f = (v: number | null | undefined, decimales = 0) =>
  v === null || v === undefined ? '—' : v.toLocaleString('fr-FR', { maximumFractionDigits: decimales })
// Objectifs modifiés pour l'aperçu (clé de la barre -> valeur) : jamais enregistrés
const objectifsApercu = reactive<Record<string, number>>({})
const objectifDe = (b: { cle: string; objectif: number }) => objectifsApercu[b.cle] ?? b.objectif
const apercuActif = computed(() => Object.keys(objectifsApercu).length > 0)
function revenirAuxObjectifs() {
  for (const cle of Object.keys(objectifsApercu)) delete objectifsApercu[cle]
}
function changerObjectif(cle: string, origine: number, evenement: Event) {
  const valeur = Number((evenement.target as HTMLInputElement).value.replace(',', '.'))
  if (!Number.isFinite(valeur) || valeur <= 0 || valeur === origine) delete objectifsApercu[cle]
  else objectifsApercu[cle] = valeur
}
/** Objectif global : moyenne des objectifs (aperçu compris) pondérée par les quantités */
const objectifGlobal = computed(() => {
  const a = analyse.value
  if (!a?.unite || !a.barres.length) return null
  const quantite = a.barres.reduce((s, b) => s + b.quantite, 0)
  if (!quantite) return a.equipes?.objectif ?? null
  return a.barres.reduce((s, b) => s + objectifDe(b) * b.quantite, 0) / quantite
})

const LIBELLES_NIVEAU = { prestations: 'prestation', projets: 'projet / commune', descriptions: 'description' } as const
const barres = computed(() => {
  const a = analyse.value
  if (!a?.niveau) return []
  const liste = a.barres.map((b) => ({
    nom: b.nom, valeur: b.rendement, objectif: objectifDe(b), unite: b.unite,
    detail: `${f(b.quantite)} ${b.unite} en ${f(b.heures, 2)} h`,
  }))
  if (a.unite && a.equipes && objectifGlobal.value !== null && liste.length > 1) {
    liste.unshift({
      nom: 'Global', valeur: a.equipes.rendement, objectif: objectifGlobal.value, unite: a.unite, global: true,
      detail: `${f(a.equipes.quantite)} ${a.unite} en ${f(a.equipes.heures, 2)} h`,
    } as (typeof liste)[number] & { global: boolean })
  }
  return liste
})
const series = computed(() => (analyse.value?.personnes ?? []).map((p) => ({ nom: p.nom_affiche, valeurs: p.evolution })))
const employes = computed(() => {
  const t = rechercheEmployes.value.toLowerCase()
  return (analyse.value?.personnes ?? []).filter((p) => !t || `${p.nom_affiche} ${p.identifiant}`.toLowerCase().includes(t))
})
const equipes = computed(() => analyse.value?.equipes)
const atteint = computed(() => !!equipes.value?.rendement && !!objectifGlobal.value && equipes.value.rendement >= objectifGlobal.value)
const uniteGlobale = computed(() => analyse.value?.unite ?? '')
const unitesDifferentes = computed(() => (analyse.value?.unites.length ?? 0) > 1)

const exportEnCours = ref(false)
async function exporter() {
  exportEnCours.value = true
  try {
    await analyseRendementApi.exporter(filtres.value)
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
      <h1 class="titre-selection" :title="titre">{{ titre }}</h1>
      <div class="ligne">
        <UiBouton icone="download" :chargement="exportEnCours" @click="exporter">Exporter</UiBouton>
        <UiBouton icone="arrow-clockwise" :chargement="chargement" @click="charger">Actualiser</UiBouton>
      </div>
    </header>

    <div class="disposition">
      <!-- Graphique -->
      <section class="carte zone-graphique">
        <div class="barre-graphique">
          <label class="mini"><span>Statut</span>
            <select v-model="choix.statut" class="saisie">
              <option value="">Tous</option>
              <option v-for="s in options?.statuts ?? []" :key="s.id" :value="s.id">{{ s.nom }}</option>
            </select>
          </label>
          <label class="mini"><span>Du</span><input v-model="choix.debut" class="saisie" type="date" /></label>
          <label class="mini"><span>Au</span><input v-model="choix.fin" class="saisie" type="date" /></label>
          <div class="mini"><span>Évolution par</span>
            <div class="bascule" role="group" aria-label="Évolution par jour ou par mois">
              <button type="button" :class="{ actif: choix.granularite === 'jour' }" @click="choix.granularite = 'jour'">Jour</button>
              <button type="button" :class="{ actif: choix.granularite === 'mois' }" @click="choix.granularite = 'mois'">Mois</button>
            </div>
          </div>
          <div class="onglets-graphique" role="tablist">
            <button type="button" role="tab" :aria-selected="onglet === 'projets'" :class="{ actif: onglet === 'projets' }" @click="onglet = 'projets'">Histogramme</button>
            <button type="button" role="tab" :aria-selected="onglet === 'personnes'" :class="{ actif: onglet === 'personnes', rouge: true }" @click="onglet = 'personnes'">Personnes</button>
          </div>
        </div>
        <UiChargement v-if="chargement && !analyse" />
        <UiEtatVide v-else-if="!analyse?.niveau" icone="hand-index" titre="Choisissez une affaire"
          texte="Cochez au moins une affaire dans la liste « Affaires » pour afficher son rendement." />
        <template v-else>
          <p class="niveau texte-petit">
            <i class="bi bi-bar-chart-steps" aria-hidden="true" />
            Une barre par <span class="gras">{{ LIBELLES_NIVEAU[analyse.niveau] }}</span>{{ barres.some((b: any) => b.global) ? ', après le Global de la sélection' : '' }}.
            <span v-if="unitesDifferentes" class="attention">
              Unités différentes ({{ analyse.unites.join(', ') }}) : pas de global ; cochez une prestation pour l'obtenir.
            </span>
          </p>
          <template v-if="onglet === 'projets'">
            <UiEtatVide v-if="!barres.length" icone="bar-chart" titre="Rien à afficher pour cette sélection" />
            <GraphiqueBarres v-else :barres="barres" />
          </template>
          <template v-else>
            <UiEtatVide v-if="unitesDifferentes" icone="rulers" titre="Unités différentes"
              :texte="`Les prestations choisies n'ont pas la même unité (${analyse.unites.join(', ')}) : cochez une prestation.`" />
            <UiEtatVide v-else-if="!series.length" icone="graph-up" titre="Aucun pointage pour cette sélection" />
            <GraphiqueAires v-else :periodes="analyse.periodes" :series="series" :objectif="objectifGlobal"
              :unite="uniteGlobale" :granularite="analyse.granularite" />
          </template>
          <p class="texte-xs texte-doux note">
            Rendement / j = quantité ÷ temps pointé × {{ f(analyse.heures_par_jour, 2) }} h.
            {{ onglet === 'projets' ? 'Barre verte : objectif atteint ; rouge : en dessous ; trait pointillé : objectif.' : 'Quantité d’une personne : descriptions où elle est « Employé », répartie dans le temps au prorata de ses heures.' }}
            <span v-if="apercuActif" class="attention"> Aperçu avec des objectifs modifiés.</span>
          </p>
        </template>
      </section>

      <!-- Rentabilités et rendement des équipes -->
      <div class="colonne-milieu">
        <section class="carte bloc">
          <header class="entete">Rendement objectif</header>
          <p v-if="!analyse?.barres.length" class="texte-xs texte-doux">Choisissez une affaire.</p>
          <table v-else class="objectifs">
            <thead><tr><th>{{ analyse.niveau ? LIBELLES_NIVEAU[analyse.niveau] : '' }}</th><th>Objectif / j</th></tr></thead>
            <tbody>
              <tr v-if="analyse.unite && objectifGlobal !== null" class="ligne-globale">
                <td class="gras">Global</td>
                <td class="droite gras" title="Moyenne des objectifs pondérée par les quantités">{{ f(objectifGlobal) }} {{ analyse.unite }}</td>
              </tr>
              <tr v-for="b in analyse.barres" :key="b.cle" :class="{ modifie: objectifsApercu[b.cle] !== undefined }">
                <td class="nom-objectif" :title="b.nom">{{ b.nom }}</td>
                <td class="droite">
                  <input class="saisie saisie-objectif" type="number" min="0" step="any" :value="objectifDe(b)"
                    :aria-label="`Objectif de ${b.nom} (aperçu)`" :title="`Vrai objectif : ${f(b.objectif, 2)} ${b.unite}`"
                    @change="changerObjectif(b.cle, b.objectif, $event)" />
                  <span class="texte-xs texte-doux">{{ b.unite }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="analyse?.barres.length" class="texte-xs texte-doux">Modifiez une valeur pour un aperçu : rien n'est enregistré.</p>
          <UiBouton v-if="apercuActif" variante="fantome" petit icone="arrow-counterclockwise" @click="revenirAuxObjectifs">Revenir aux vrais objectifs</UiBouton>
        </section>
        <section class="carte bloc">
          <header class="entete">Rentabilités</header>
          <table class="rentabilites" aria-label="Rentabilités (à venir)">
            <tbody><tr v-for="i in 8" :key="i"><td /><td /></tr></tbody>
          </table>
          <p class="texte-xs texte-doux">Bientôt disponible.</p>
        </section>
        <section class="carte bloc">
          <header class="entete">Rendement des équipes</header>
          <div class="encadre objectif"><span>Rendement objectif{{ apercuActif ? ' (aperçu)' : '' }}</span><strong>{{ f(objectifGlobal) }} {{ uniteGlobale }}</strong></div>
          <div class="encadre" :class="atteint ? 'ok' : 'equipe'"><span>Rendement des équipes</span><strong>{{ f(equipes?.rendement) }} {{ uniteGlobale }}</strong></div>
          <p v-if="unitesDifferentes" class="texte-xs attention">Unités différentes : pas de global.</p>
          <p v-else-if="equipes" class="texte-xs texte-doux">{{ f(equipes.quantite) }} {{ uniteGlobale }} en {{ f(equipes.heures, 2) }} h pointées</p>
        </section>
      </div>

      <!-- Filtres -->
      <div class="colonne-filtres">
        <ListeCases v-model="choix.affaires" titre="Affaires" :options="options?.affaires ?? []" />
        <ListeCases v-model="choix.prestations" titre="Prestations" :options="options?.prestations ?? []" />
        <ListeCases v-model="choix.projets" titre="Projets / Communes" :options="(options?.projets ?? []).map((p) => ({ ...p, detail: p.affaire }))" />
      </div>

      <!-- Employés concernés -->
      <section class="carte zone-employes">
        <input v-model="rechercheEmployes" class="saisie recherche" placeholder="Rechercher" aria-label="Rechercher un employé" />
        <header class="entete">Liste des employés concernés</header>
        <ul class="employes">
          <li v-for="p in employes" :key="p.id">
            <UiAvatar :nom="p.nom_affiche" :matricule="p.code_barre" />
            <span class="identite"><span class="gras">{{ p.nom_affiche }}</span><span class="texte-xs texte-doux">{{ p.identifiant }}</span></span>
            <span class="chiffres" :title="`${f(p.quantite)} ${uniteGlobale} en ${f(p.heures, 2)} h`">
              <template v-if="analyse?.unite">{{ f(p.rendement) }} <span class="texte-xs texte-doux">{{ uniteGlobale }} / j</span></template>
              <span v-else class="texte-xs texte-doux">{{ f(p.heures, 2) }} h</span>
            </span>
          </li>
          <li v-if="!employes.length" class="texte-doux texte-petit vide">{{ analyse?.niveau ? "Aucun employé n'a pointé sur cette sélection." : 'Choisissez une affaire.' }}</li>
        </ul>
      </section>

      <div class="zone-taches">
        <ListeCases v-model="choix.taches" titre="Tâches" :options="options?.taches ?? []"
          aide="Seules les tâches cochées comptent dans le temps (aucune cochée : toutes)." />
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-large { max-width: none; }
.ligne-titre { display: flex; align-items: center; justify-content: space-between; gap: var(--e3); margin-bottom: var(--e4); }
.titre-selection { font-size: var(--taille-l); text-transform: uppercase; letter-spacing: 0.02em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.disposition {
  display: grid;
  grid-template-columns: minmax(0, 2.2fr) minmax(220px, 1fr) minmax(220px, 1fr);
  grid-template-areas: 'graphique milieu filtres' 'employes employes taches';
  gap: var(--e4);
  align-items: start;
}
.zone-graphique { grid-area: graphique; padding: var(--e3) var(--e4); }
.colonne-milieu { grid-area: milieu; display: flex; flex-direction: column; gap: var(--e4); }
.colonne-filtres { grid-area: filtres; display: flex; flex-direction: column; gap: var(--e3); }
.zone-employes { grid-area: employes; padding: var(--e2); display: flex; flex-direction: column; gap: var(--e2); }
.zone-taches { grid-area: taches; }
.barre-graphique { display: flex; align-items: flex-end; gap: var(--e3); flex-wrap: wrap; margin-bottom: var(--e3); }
.mini { display: flex; flex-direction: column; gap: 2px; font-size: var(--taille-xs); color: var(--texte-doux); }
.mini .saisie { height: 32px; width: auto; min-width: 120px; }
.bascule { display: inline-flex; border: 1px solid var(--bordure-forte); border-radius: 999px; overflow: hidden; }
.bascule button { padding: 4px 12px; border: none; background: var(--surface); font-size: var(--taille-xs); font-weight: 600; color: var(--texte-doux); cursor: pointer; }
.bascule button.actif { background: var(--marine); color: #fff; }
.onglets-graphique { margin-left: auto; display: flex; gap: var(--e2); }
.onglets-graphique button { padding: 6px 16px; border: 1.5px solid var(--marine); border-radius: var(--rayon); background: var(--surface); color: var(--marine); font-weight: 600; cursor: pointer; }
.onglets-graphique button.rouge { border-color: var(--rouge); color: var(--rouge); }
.onglets-graphique button.actif { background: var(--marine); color: #fff; }
.onglets-graphique button.rouge.actif { background: var(--rouge); color: #fff; }
.note { margin-top: var(--e2); }
.niveau { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; color: var(--texte-doux); margin-bottom: var(--e2); }
.attention { color: var(--attention); font-weight: 600; }
.objectifs { width: 100%; border-collapse: collapse; font-size: var(--taille-s); }
.objectifs th { text-align: left; font-size: var(--taille-xs); color: var(--texte-doux); font-weight: 600; padding: 2px 4px; text-transform: capitalize; }
.objectifs th:last-child { text-align: right; }
.objectifs td { padding: 3px 4px; border-top: 1px solid var(--bordure); }
.nom-objectif { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.objectifs td.droite { text-align: right; white-space: nowrap; }
.objectifs td.droite .texte-xs { display: inline-block; min-width: 36px; margin-left: 4px; text-align: left; }
.saisie-objectif { width: 84px; height: 28px; padding: 0 6px; text-align: right; }
.objectifs tr.modifie .saisie-objectif { border-color: var(--attention); background: color-mix(in srgb, var(--attention) 10%, var(--surface)); font-weight: 700; }
.ligne-globale td { color: var(--marine); }
.bloc { padding: var(--e2); display: flex; flex-direction: column; gap: var(--e2); }
.entete { padding: var(--e2); border-radius: var(--rayon); background: var(--marine); color: #fff; font-weight: 600; font-size: var(--taille-s); text-align: center; }
.rentabilites { width: 100%; border-collapse: collapse; }
.rentabilites td { height: 20px; border: 1px solid var(--bordure-forte); }
.encadre { position: relative; display: flex; flex-direction: column; align-items: center; padding: var(--e3) var(--e2) var(--e2); border: 1.5px solid var(--marine); border-radius: var(--rayon); margin-top: var(--e2); }
.encadre span { position: absolute; top: -9px; padding: 0 6px; background: var(--surface); font-size: var(--taille-xs); color: inherit; }
.encadre strong { font-size: var(--taille-l); }
.encadre.objectif { border-color: var(--rouge); color: var(--rouge); }
.encadre.equipe { color: var(--marine); }
.encadre.ok { border-color: var(--succes); color: var(--succes); }
.recherche { height: 30px; font-size: var(--taille-s); }
.employes { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--e2); }
.employes li { display: flex; align-items: center; gap: var(--e2); padding: var(--e2); border-radius: var(--rayon); background: var(--surface-douce); }
.identite { display: flex; flex-direction: column; min-width: 0; line-height: 1.25; }
.chiffres { margin-left: auto; font-weight: 700; color: var(--marine); white-space: nowrap; }
.vide { padding: var(--e3); }
@media (max-width: 1200px) {
  .disposition { grid-template-columns: 1fr; grid-template-areas: 'graphique' 'milieu' 'filtres' 'taches' 'employes'; }
}
</style>
