<!--
  Marchés > Durée estimatif (calculs : backend/marches/duree.py).
    Pour chaque Projet / Commune : temps estimatif = quantité ÷ rendement objectif × heures par jour
    (Paramètres > Rendement & Note), puis durée = temps ÷ ressources disponibles (simulation, rien n'est
    enregistré). Durée totale et durée restante (d'après l'Avancement des lignes de feuille), en jours ou en heures.
    Filtres (listes à cocher, aucune = tout) : Statut, Descriptions, Affaires, Prestations, Rendements objectifs.
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { dureeEstimativeApi } from '@/api'
import type { DureeEstimative, ProjetDuree } from '@/api/marches'
import { useToast } from '@/composables/useToast'
import ListeCases from '@/components/rendement/ListeCases.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiRecherche from '@/components/ui/UiRecherche.vue'

const toast = useToast()
const choix = reactive({ affaires: [] as (number | string)[], prestations: [] as (number | string)[], rendements: [] as (number | string)[],
  descriptions: [] as (number | string)[], statuts: [] as (number | string)[] })
const filtres = computed(() => Object.fromEntries(Object.entries(choix).map(([k, v]) => [k, v.join(',')])))
const donnees = ref<DureeEstimative | null>(null)
const chargement = ref(false)
async function charger() {
  chargement.value = true
  try {
    donnees.value = await dureeEstimativeApi.charger(filtres.value)
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargement.value = false
  }
}
onMounted(charger)
watchDebounced(filtres, charger, { debounce: 300, deep: true })

// Ressources disponibles : simulation (1 par défaut), rien n'est enregistré
const ressources = reactive<Record<string, number>>({})
const ressourcesDe = (p: ProjetDuree) => Math.max(1, Number(ressources[p.id]) || 1)
const changer = (p: ProjetDuree, delta: number) => (ressources[p.id] = Math.max(1, Math.min(999, ressourcesDe(p) + delta)))
const pourTous = ref(1)
function appliquerATous() {
  ;(donnees.value?.projets ?? []).forEach((p) => (ressources[p.id] = Math.max(1, Number(pourTous.value) || 1)))
}

// Affichage en jours ou en heures
const unite = ref<'jours' | 'heures'>('jours')
const h = computed(() => donnees.value?.heures_par_jour ?? 8)
const nombre = (v: number, d = 1) => v.toLocaleString('fr-FR', { maximumFractionDigits: d })
function duree(heures: number | null, p?: ProjetDuree) {
  if (heures === null) return '—'
  const t = p ? heures / ressourcesDe(p) : heures
  const v = unite.value === 'jours' ? t / h.value : t
  const suffixe = unite.value === 'jours' ? 'j' : 'h'
  if (v > 0 && v < 0.01) return `< 0,01 ${suffixe}`      // un très petit temps ne s'affiche pas « 0 »
  return `${nombre(v, v < 10 ? 2 : 1)} ${suffixe}`
}

// Recherche et totaux
const recherche = ref('')
const projets = computed(() => {
  const q = recherche.value.trim().toLowerCase()
  return (donnees.value?.projets ?? []).filter((p) => !q || `${p.nom} ${p.affaire} ${p.num_affaire} ${p.prestation}`.toLowerCase().includes(q))
})
const total = computed(() => ({
  temps: projets.value.reduce((t, p) => t + (p.temps_heures ?? 0), 0),
  reste: projets.value.reduce((t, p) => t + (p.temps_restant_heures ?? 0), 0),
  ressources: projets.value.reduce((t, p) => t + ressourcesDe(p), 0),
}))
const progression = (p: ProjetDuree) => (p.quantite ? Math.round((1 - p.quantite_restante / p.quantite) * 100) : 0)
const dateCourte = (d: string | null) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}` : '—')
watch(() => donnees.value?.options, (o) => {
  // Retirer les choix qui ne sont plus proposés (ex. descriptions d'une affaire décochée)
  if (!o) return
  const garder = (liste: (number | string)[], options: { id: number | string }[]) => liste.filter((id) => options.some((x) => x.id === id))
  if (choix.descriptions.some((id) => !o.descriptions.some((x) => x.id === id))) choix.descriptions = garder(choix.descriptions, o.descriptions)
})

const exportEnCours = ref(false)
async function exporter() {
  exportEnCours.value = true
  try {
    const parProjet = Object.fromEntries((donnees.value?.projets ?? []).map((p) => [p.id, ressourcesDe(p)]))
    await dureeEstimativeApi.exporter(filtres.value, parProjet, unite.value)
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
        <h1>Durée estimatif</h1>
        <p class="texte-doux texte-petit">
          Le temps pour traiter chaque Projet / Commune : quantité ÷ rendement objectif × {{ nombre(h, 2) }} h par jour
          (Paramètres > Rendement & Note), réparti sur les ressources disponibles.
        </p>
      </div>
      <div class="ligne">
        <div class="bascule" role="radiogroup" aria-label="Unité">
          <button type="button" role="radio" :aria-checked="unite === 'jours'" :class="{ actif: unite === 'jours' }" @click="unite = 'jours'">Jours</button>
          <button type="button" role="radio" :aria-checked="unite === 'heures'" :class="{ actif: unite === 'heures' }" @click="unite = 'heures'">Heures</button>
        </div>
        <UiBouton icone="download" :chargement="exportEnCours" :desactive="!donnees?.projets.length" @click="exporter">Exporter</UiBouton>
      </div>
    </header>

    <div class="grille-page">
      <!-- Tableau -->
      <section class="carte tableau-duree">
        <div class="barre-tableau">
          <UiRecherche v-model="recherche" class="recherche" placeholder="Rechercher un projet ou une commune" />
          <label class="pour-tous">Ressources pour tous :
            <input v-model.number="pourTous" class="saisie" type="number" min="1" max="999" aria-label="Ressources pour tous les projets" />
            <UiBouton petit @click="appliquerATous">Appliquer</UiBouton>
          </label>
        </div>
        <div class="entete-tableau" role="row">
          <span role="columnheader">Projets / Communes</span>
          <span role="columnheader" class="centre">Ressources Disponibles</span>
          <span role="columnheader" class="droite">Durée estimatif</span>
        </div>
        <UiChargement v-if="chargement && !donnees" />
        <div v-else class="corps-tableau" role="table" aria-label="Durée estimatif par projet">
          <div v-for="p in projets" :key="p.id" class="rangee" role="row">
            <div class="cellule-projet">
              <span class="gras">{{ p.nom }}</span>
              <span class="texte-xs texte-doux">{{ p.num_affaire ? `${p.num_affaire} – ` : '' }}{{ p.affaire }} › {{ p.prestation }}</span>
              <span class="texte-xs texte-doux">
                {{ nombre(p.quantite, 0) }} {{ p.unite }} ({{ p.nb_descriptions }} description(s)) ·
                objectif {{ p.rendement_objectif ? `${nombre(p.rendement_objectif, 2)} ${p.unite} / j` : '—' }} ·
                livraison {{ dateCourte(p.date_livraison) }}
              </span>
              <span class="progression" :title="`${progression(p)} % traités (Avancement des lignes)`"><span :style="{ width: `${progression(p)}%` }" /></span>
            </div>
            <div class="cellule-ressources">
              <div class="pas-a-pas">
                <button type="button" :aria-label="`Une ressource de moins pour ${p.nom}`" :disabled="ressourcesDe(p) <= 1" @click="changer(p, -1)">
                  <i class="bi bi-dash-lg" aria-hidden="true" /></button>
                <input :value="ressourcesDe(p)" type="number" min="1" max="999" :aria-label="`Ressources disponibles pour ${p.nom}`"
                  @input="ressources[p.id] = Number(($event.target as HTMLInputElement).value)" />
                <button type="button" :aria-label="`Une ressource de plus pour ${p.nom}`" @click="changer(p, 1)"><i class="bi bi-plus-lg" aria-hidden="true" /></button>
              </div>
              <span class="texte-xs texte-doux">personne(s)</span>
            </div>
            <div class="cellule-duree">
              <div class="duree"><span class="libelle">Totale</span><strong>{{ duree(p.temps_heures, p) }}</strong></div>
              <div class="duree restante"><span class="libelle">Restante</span><strong>{{ duree(p.temps_restant_heures, p) }}</strong></div>
              <span class="texte-xs texte-doux" :title="'Temps pour une seule personne'">soit {{ duree(p.temps_heures) }} pour 1 personne</span>
            </div>
          </div>
          <p v-if="!projets.length" class="vide">Aucun projet / commune pour ces filtres.</p>
        </div>
        <footer v-if="projets.length" class="pied-tableau">
          <span>{{ projets.length }} projet(s) / commune(s)</span>
          <span>Charge totale : <strong>{{ duree(total.temps) }}</strong> · restante : <strong>{{ duree(total.reste) }}</strong> (pour 1 personne)</span>
          <span>{{ total.ressources }} ressource(s) au total</span>
        </footer>
      </section>

      <!-- Statut et Descriptions -->
      <div class="colonne-droite">
        <ListeCases recherche-standard v-model="choix.statuts" titre="Statut" :options="donnees?.options.statuts ?? []"
          aide="Seules les descriptions à ce statut comptent (aucun : toutes)." />
        <ListeCases recherche-standard v-model="choix.descriptions" titre="Descriptions" :options="donnees?.options.descriptions ?? []"
          aide="Aucune cochée : toutes." />
      </div>

      <!-- Affaires, Prestations, Rendements objectifs -->
      <div class="rangee-bas">
        <ListeCases recherche-standard v-model="choix.affaires" titre="Affaires" :options="donnees?.options.affaires ?? []" aide="Aucune cochée : toutes." />
        <ListeCases recherche-standard v-model="choix.prestations" titre="Prestations" :options="donnees?.options.prestations ?? []" aide="Aucune cochée : toutes." />
        <ListeCases recherche-standard v-model="choix.rendements" titre="Choix des Rendements Objectifs" :options="donnees?.options.rendements ?? []"
          aide="Seulement les projets qui ont ces rendements objectifs." />
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-large { max-width: none; }
.ligne-titre { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e3); margin-bottom: var(--e4); }
.bascule { display: inline-flex; height: 36px; border: 1px solid var(--bordure-forte); border-radius: var(--rayon); overflow: hidden; }
.bascule button { padding: 0 14px; border: none; background: var(--surface); font-weight: 600; color: var(--texte-doux); cursor: pointer; }
.bascule button.actif { background: var(--marine); color: #fff; }
.grille-page { display: grid; grid-template-columns: minmax(0, 1fr) 300px; grid-template-areas: 'tableau droite' 'bas bas'; gap: var(--e4); align-items: start; }
.tableau-duree { grid-area: tableau; display: flex; flex-direction: column; padding: var(--e3); min-width: 0; }
.colonne-droite { grid-area: droite; display: flex; flex-direction: column; gap: var(--e3); }
.rangee-bas { grid-area: bas; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e4); }
.barre-tableau { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e3); margin-bottom: var(--e2); }
.recherche { width: min(420px, 100%); }
.pour-tous { display: inline-flex; align-items: center; gap: var(--e2); font-size: var(--taille-s); color: var(--texte-doux); }
.pour-tous .saisie { width: 70px; text-align: center; }
.entete-tableau, .rangee { display: grid; grid-template-columns: minmax(0, 1.6fr) 180px minmax(220px, 1fr); align-items: center; gap: var(--e3); }
.entete-tableau { padding: 10px var(--e4); border-radius: var(--rayon); background: var(--marine); color: #fff; font-size: var(--taille-s); }
.centre { text-align: center; } .droite { text-align: right; }
.corps-tableau { max-height: calc(100vh - 330px); min-height: 280px; overflow-y: auto; }
.rangee { padding: var(--e3) var(--e4); border-bottom: 1px solid var(--bordure); }
.rangee:nth-child(odd) { background: #f7f7f7; }
.cellule-projet { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.progression { height: 4px; max-width: 220px; margin-top: 4px; border-radius: 999px; background: var(--bordure); overflow: hidden; }
.progression span { display: block; height: 100%; background: var(--succes); }
.cellule-ressources { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.pas-a-pas { display: inline-flex; border: 1px solid var(--bordure-forte); border-radius: var(--rayon); overflow: hidden; background: var(--surface); }
.pas-a-pas button { width: 32px; border: none; background: var(--surface-douce); color: var(--marine); cursor: pointer; }
.pas-a-pas button:disabled { opacity: 0.4; cursor: default; }
.pas-a-pas input { width: 54px; height: 32px; border: none; text-align: center; font-weight: 800; color: var(--marine); }
.cellule-duree { display: flex; flex-wrap: wrap; justify-content: flex-end; align-items: baseline; gap: 4px var(--e4); text-align: right; }
.duree { display: flex; flex-direction: column; align-items: flex-end; }
.duree .libelle { font-size: var(--taille-xs); color: var(--texte-doux); font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; }
.duree strong { font-size: var(--taille-l); color: var(--marine); }
.duree.restante strong { color: var(--attention); }
.cellule-duree > .texte-xs { flex-basis: 100%; }
.vide { padding: var(--e4); color: var(--texte-doux); }
.pied-tableau { display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--e3); margin-top: var(--e2); padding: 10px var(--e4); border-radius: var(--rayon); background: var(--surface-douce); font-size: var(--taille-s); color: var(--texte-doux); }
@media (max-width: 1100px) { .grille-page { grid-template-columns: 1fr; grid-template-areas: 'tableau' 'droite' 'bas'; } .rangee-bas { grid-template-columns: 1fr; } }
</style>
