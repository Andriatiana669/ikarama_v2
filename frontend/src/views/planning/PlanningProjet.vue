<!--
  Planning Projet (module « Planning Projet » de Paramètres > Autorisation ; calculs : backend/planning/views.py).
    Grille : les semaines défilent de gauche à droite (la colonne Employé et les en-têtes restent figés) ;
    les semaines précédentes / suivantes se chargent en arrivant au bord. Passé et aujourd'hui : projets pointés
    (heures) ; aujourd'hui et l'avenir : projets planifiés. Sous l'identifiant : ce que la personne est en train
    de faire (lignes de feuille au statut « En train de faire » de Marchés > Statuts).
    Panneau de droite, toujours visible : Projets / Communes à planifier (glisser sur une case, ou cliquer puis
    cliquer la case) et Employés avec leurs jours libres. Filtres : personne, équipe de (afficher / masquer),
    pôle, poste, affaires, contenu, disponibles, lignes vides.
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { planningApi } from '@/api'
import type { Echeance, LignePlanning, ProjetPlanning, SemainePlanning } from '@/api/planning'
import { messageErreur } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { Identifiant } from '@/types'
import FiltreMulti from '@/components/planning/FiltreMulti.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiAvatar from '@/components/ui/UiAvatar.vue'
import { useTempsReel } from '@/composables/useTempsReel'

const toast = useToast()
const LARGEUR_JOUR = 124        // px : colonnes fixes, pour garder la position quand on charge des semaines avant
const LOT = 4                   // semaines chargées en plus en arrivant au bord
const MAX_SEMAINES = 26

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const ajouterJours = (texte: string, n: number) => {
  const d = new Date(`${texte}T12:00:00`)
  d.setDate(d.getDate() + n)
  return iso(d)
}
const lundiDe = (d: Date) => {
  const l = new Date(d)
  l.setDate(l.getDate() - ((l.getDay() + 6) % 7))
  return iso(l)
}

// --- Plage chargée -------------------------------------------------------------------------------
const debut = ref(ajouterJours(lundiDe(new Date()), -14))   // 2 semaines avant celle-ci
const nbSemaines = ref(8)
const donnees = ref<SemainePlanning | null>(null)
const chargement = ref(false)
const grilleEl = ref<HTMLElement | null>(null)

async function charger() {
  chargement.value = true
  try {
    donnees.value = await planningApi.plage(debut.value, nbSemaines.value)
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargement.value = false
  }
}
async function allerAujourdhui() {
  await nextTick()
  const index = donnees.value?.jours.findIndex((j) => j.aujourdhui) ?? -1
  if (grilleEl.value && index >= 0) grilleEl.value.scrollLeft = Math.max(0, index * LARGEUR_JOUR - LARGEUR_JOUR)
}
async function defiler() {
  const el = grilleEl.value
  if (!el || chargement.value || nbSemaines.value >= MAX_SEMAINES) return
  if (el.scrollLeft + el.clientWidth > el.scrollWidth - 200) {
    nbSemaines.value += LOT
    await charger()
  } else if (el.scrollLeft < 120) {
    debut.value = ajouterJours(debut.value, -7 * LOT)
    nbSemaines.value += LOT
    const avant = el.scrollLeft
    await charger()
    await nextTick()
    el.scrollLeft = avant + 7 * LOT * LARGEUR_JOUR    // on reste sur les mêmes jours
  }
}

// --- Projets / Communes ------------------------------------------------------------------------
const projets = ref<(ProjetPlanning & Echeance)[]>([])
const rechercheProjets = ref('')
const projetChoisi = ref<ProjetPlanning | null>(null)
async function chargerProjets() {
  try {
    projets.value = await planningApi.projets(rechercheProjets.value)
  } catch (e) {
    toast.erreur(e)
  }
}
watchDebounced(rechercheProjets, chargerProjets, { debounce: 300 })

// --- Temps réel : chaque changement (planification, pointage, statut) rafraîchit la grille ------------
//     (sans WebSocket : relecture toutes les 30 s)
const tempsReel = useTempsReel()
let attente: number | undefined
let minuteur: number | undefined
const rafraichirBientot = () => {
  window.clearTimeout(attente)
  attente = window.setTimeout(() => {
    if (!chargement.value) charger()
  }, 400)
}
const desabonner = tempsReel.ecouter('planning', rafraichirBientot)
function programmer() {
  window.clearInterval(minuteur)
  if (!tempsReel.connecte.value) minuteur = window.setInterval(() => !document.hidden && charger(), 30_000)
}
watch(tempsReel.connecte, (oui) => {
  programmer()
  if (oui) charger()   // reconnecté : rattraper ce qui a pu changer
})

onMounted(async () => {
  tempsReel.suivrePlanning()
  programmer()
  await Promise.all([charger(), chargerProjets()])
  allerAujourdhui()
})
onBeforeUnmount(() => {
  desabonner()
  tempsReel.quitterPlanning()
  window.clearTimeout(attente)
  window.clearInterval(minuteur)
})

// --- Filtres ---------------------------------------------------------------------------------------
const recherche = ref('')
const equipeAfficher = ref<(string | number)[]>([])
const equipeMasquer = ref<(string | number)[]>([])
const poles = ref<(string | number)[]>([])
const postes = ref<(string | number)[]>([])
const affaires = ref<(string | number)[]>([])
const voirPointe = ref(true)
const voirPrevu = ref(true)
const voirEnCours = ref(true)
const voirEcheances = ref(true)
const seulementDisponibles = ref(false)
const masquerVides = ref(false)

const lignes = computed(() => donnees.value?.lignes ?? [])
const optionsEquipes = computed(() => {
  const chefs = new Set(lignes.value.flatMap((l) => l.chefs))
  return lignes.value.filter((l) => chefs.has(l.employe.id)).map((l) => ({ id: l.employe.id, nom: `Équipe de ${l.employe.identifiant}` }))
})
const optionsPoles = computed(() => [...new Set(lignes.value.flatMap((l) => l.poles))].sort().map((p) => ({ id: p, nom: p })))
const optionsPostes = computed(() => [...new Set(lignes.value.flatMap((l) => l.postes))].sort().map((p) => ({ id: p, nom: p })))
const optionsAffaires = computed(() => {
  const vues = new Map<Identifiant, string>()
  const ajouter = (p: ProjetPlanning) => p.affaire_id && vues.set(p.affaire_id, p.num_affaire ? `${p.num_affaire} – ${p.affaire}` : p.affaire)
  lignes.value.forEach((l) => {
    l.en_cours.forEach(ajouter)
    Object.values(l.cases).forEach((c) => [...c.pointe, ...c.prevu].forEach(ajouter))
  })
  return [...vues].map(([id, nom]) => ({ id, nom })).sort((a, b) => a.nom.localeCompare(b.nom))
})

const dansEquipe = (l: LignePlanning, chefs: (string | number)[]) =>
  chefs.includes(l.employe.id) || l.chefs.some((c) => chefs.includes(c))
const garderProjet = (p: ProjetPlanning) => !affaires.value.length || affaires.value.includes(p.affaire_id as number)
const contenu = (l: LignePlanning, date: string) => {
  const c = l.cases[date]
  return {
    pointe: voirPointe.value ? (c?.pointe ?? []).filter(garderProjet) : [],
    prevu: voirPrevu.value ? (c?.prevu ?? []).filter(garderProjet) : [],
  }
}
const lignesVisibles = computed(() => {
  const q = recherche.value.trim().toLowerCase()
  return lignes.value.filter((l) => {
    if (q && !`${l.employe.identifiant} ${l.employe.nom_affiche}`.toLowerCase().includes(q)) return false
    if (equipeAfficher.value.length && !dansEquipe(l, equipeAfficher.value)) return false
    if (equipeMasquer.value.length && dansEquipe(l, equipeMasquer.value)) return false
    if (poles.value.length && !l.poles.some((p) => poles.value.includes(p))) return false
    if (postes.value.length && !l.postes.some((p) => postes.value.includes(p))) return false
    if (seulementDisponibles.value && !l.jours_libres.length) return false
    if (masquerVides.value) {
      const rien = (donnees.value?.jours ?? []).every((j) => {
        const c = contenu(l, j.date)
        return !c.pointe.length && !c.prevu.length
      })
      if (rien && !(voirEnCours.value && l.en_cours.some(garderProjet))) return false
    }
    return true
  })
})
const nbFiltres = computed(() => [equipeAfficher, equipeMasquer, poles, postes, affaires].filter((f) => f.value.length).length
  + Number(!!recherche.value) + Number(seulementDisponibles.value) + Number(masquerVides.value)
  + Number(!voirPointe.value) + Number(!voirPrevu.value) + Number(!voirEnCours.value) + Number(!voirEcheances.value))
function effacerFiltres() {
  recherche.value = ''
  ;[equipeAfficher, equipeMasquer, poles, postes, affaires].forEach((f) => (f.value = []))
  voirPointe.value = voirPrevu.value = voirEnCours.value = voirEcheances.value = true
  seulementDisponibles.value = masquerVides.value = false
}

// --- Planifier : glisser-déposer, ou choisir un projet puis cliquer une case ---------------------------
type Glisse = { type: 'projet'; projet: ProjetPlanning } | { type: 'prevu'; id: Identifiant }
let glisse: Glisse | null = null
const glisser = (element: Glisse) => (glisse = element)
const survol = ref('')
const cleCase = (employe: Identifiant, date: string) => `${employe}|${date}`
const planifiableCase = (l: LignePlanning, date: string) => l.planifiable && date >= (donnees.value?.aujourdhui ?? '')

async function deposer(l: LignePlanning, date: string) {
  survol.value = ''
  const element = glisse
  glisse = null
  if (!element || !planifiableCase(l, date)) return
  try {
    if (element.type === 'projet') await planningApi.planifier({ employe: l.employe.id, date, projet: element.projet.projet_id })
    else await planningApi.deplacer(element.id, { employe: l.employe.id, date })
    await charger()
  } catch (e) {
    toast.erreur(messageErreur(e))
  }
}
function cliquerCase(l: LignePlanning, date: string) {
  if (!projetChoisi.value || !planifiableCase(l, date)) return
  glisser({ type: 'projet', projet: projetChoisi.value })
  deposer(l, date)
}
async function retirer(id: Identifiant) {
  try {
    await planningApi.retirer(id)
    await charger()
  } catch (e) {
    toast.erreur(messageErreur(e))
  }
}

// --- Affichage ----------------------------------------------------------------------------------------
const projetsVisibles = computed(() => projets.value.filter(garderProjet))

// --- Échéances : date de livraison des projets et leur état ------------------------------------------
const ETATS: Record<Echeance['etat'], { libelle: string; icone: string }> = {
  retard: { libelle: 'En retard', icone: 'exclamation-octagon-fill' },
  proche: { libelle: 'Bientôt', icone: 'alarm' },
  ok: { libelle: 'Livraison', icone: 'flag-fill' },
  termine: { libelle: 'Terminé', icone: 'check-circle-fill' },
}
const echeancesDu = (date: string) => (donnees.value?.echeances[date] ?? []).filter(garderProjet)
const auMoinsUneEcheance = computed(() => (donnees.value?.jours ?? []).some((j) => echeancesDu(j.date).length))
function texteEcheance(p: Echeance) {
  if (!p.date_livraison) return 'Pas de date de livraison'
  const jours = Math.round((new Date(`${p.date_livraison}T12:00:00`).getTime() - new Date(`${donnees.value?.aujourdhui ?? ''}T12:00:00`).getTime()) / 86400000)
  if (p.etat === 'termine') return `Terminé (livraison le ${dateLongue(p.date_livraison)})`
  if (jours < 0) return `En retard de ${-jours} jour(s)`
  if (jours === 0) return 'Livraison aujourd’hui'
  return `Livraison dans ${jours} jour(s)`
}
const rechercheEmployes = ref('')
const disponibles = computed(() => {
  const q = rechercheEmployes.value.trim().toLowerCase()
  return lignesVisibles.value.filter((l) => !q || l.employe.identifiant.toLowerCase().includes(q))
})
const jourCourt = (date: string) => {
  const noms = ['Dim.', 'Lun.', 'Mar.', 'Mer.', 'Jeu.', 'Ven.', 'Sam.']
  return `${noms[new Date(`${date}T12:00:00`).getDay()]} ${date.slice(8, 10)}/${date.slice(5, 7)}`
}
const dateLongue = (date: string) => `${date.slice(8, 10)}/${date.slice(5, 7)}/${date.slice(0, 4)}`
const heures = (m: number) => `${(m / 60).toLocaleString('fr-FR', { maximumFractionDigits: 2 })} h`
const nomAffaire = (p: ProjetPlanning) => (p.num_affaire ? `${p.num_affaire} – ${p.affaire}` : p.affaire)

const exportEnCours = ref(false)
async function exporter() {
  exportEnCours.value = true
  try {
    await planningApi.exporter(debut.value, nbSemaines.value)
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
        <h1>Planning Projet</h1>
        <p class="texte-doux texte-petit">Ce que fait l’équipe (pointages), ce qu’elle est en train de faire et ce qu’elle fera (planifié).</p>
      </div>
      <div class="ligne">
        <span class="direct" :class="{ actif: tempsReel.connecte.value }" :title="tempsReel.connecte.value
          ? 'Temps réel : les changements s’affichent aussitôt' : 'Mise à jour toutes les 30 secondes (temps réel indisponible)'">
          <span class="point" aria-hidden="true" />En direct<i v-if="tempsReel.connecte.value" class="bi bi-lightning-charge-fill" aria-label="temps réel" />
        </span>
        <UiBouton icone="calendar-check" @click="allerAujourdhui">Aujourd’hui</UiBouton>
        <UiBouton v-if="donnees?.droits.exporter" icone="download" :chargement="exportEnCours" @click="exporter">Exporter</UiBouton>
      </div>
    </header>

    <div class="disposition">
      <div class="colonne-grille">
        <section class="carte filtres" aria-label="Filtres">
          <input v-model="recherche" class="saisie recherche-personne" type="search" placeholder="Rechercher une personne" aria-label="Rechercher une personne" />
          <FiltreMulti v-model="equipeAfficher" libelle="Équipe de" icone="diagram-3" :options="optionsEquipes" />
          <FiltreMulti v-model="equipeMasquer" libelle="Masquer l’équipe de" icone="eye-slash" :options="optionsEquipes" />
          <FiltreMulti v-model="poles" libelle="Pôle" :options="optionsPoles" />
          <FiltreMulti v-model="postes" libelle="Poste" :options="optionsPostes" />
          <FiltreMulti v-model="affaires" libelle="Affaires" icone="briefcase" :options="optionsAffaires" />
          <span class="separateur" />
          <label class="bascule"><input v-model="voirPointe" type="checkbox" /> Pointé</label>
          <label class="bascule"><input v-model="voirPrevu" type="checkbox" /> Planifié</label>
          <label class="bascule"><input v-model="voirEnCours" type="checkbox" /> En train de faire</label>
          <label class="bascule"><input v-model="voirEcheances" type="checkbox" /> Échéances</label>
          <label class="bascule"><input v-model="seulementDisponibles" type="checkbox" /> Disponibles</label>
          <label class="bascule"><input v-model="masquerVides" type="checkbox" /> Masquer les lignes vides</label>
          <UiBouton v-if="nbFiltres" variante="fantome" petit icone="x-lg" @click="effacerFiltres">Effacer ({{ nbFiltres }})</UiBouton>
          <span v-if="projetChoisi" class="bandeau-choix"><i class="bi bi-cursor" aria-hidden="true" /> Cliquez une case pour planifier
            <strong>{{ projetChoisi.projet }}</strong> <button type="button" class="lien" @click="projetChoisi = null">Annuler</button></span>
        </section>

        <UiChargement v-if="!donnees" />
        <section v-else class="carte cadre-grille">
          <div ref="grilleEl" class="defilement" @scroll.passive="defiler">
            <table class="grille" :style="{ width: `${210 + donnees.jours.length * LARGEUR_JOUR}px` }">
              <colgroup><col style="width: 210px" /><col v-for="j in donnees.jours" :key="j.date" :style="{ width: `${LARGEUR_JOUR}px` }" /></colgroup>
              <thead>
                <tr class="rangee-semaines">
                  <th rowspan="2" class="coin">Employé</th>
                  <th v-for="s in donnees.semaines" :key="s.debut" colspan="7" class="semaine">S{{ s.numero }}</th>
                </tr>
                <tr class="rangee-jours">
                  <th v-for="j in donnees.jours" :key="j.date" class="jour" :class="{ weekend: !j.ouvrable, aujourdhui: j.aujourdhui, lundi: j.nom === 'Lun.' }">
                    <span class="nom-jour">{{ j.nom }}</span><span class="date-jour">{{ dateLongue(j.date) }}</span>
                  </th>
                </tr>
                <tr v-if="voirEcheances" class="rangee-echeances">
                  <th class="titre-echeances"><i class="bi bi-flag" aria-hidden="true" /> Échéances</th>
                  <th v-for="j in donnees.jours" :key="j.date" class="case-echeance" :class="{ lundi: j.nom === 'Lun.' }">
                    <span v-for="e in echeancesDu(j.date)" :key="e.projet_id" class="echeance" :class="e.etat"
                      :title="`${nomAffaire(e)} › ${e.prestation} › ${e.projet} : ${texteEcheance(e)} · avancement ${e.avancement} %`">
                      <i :class="`bi bi-${ETATS[e.etat].icone}`" aria-hidden="true" /><span class="texte-element">{{ e.projet }}</span>
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="l in lignesVisibles" :key="l.employe.id">
                  <th scope="row" class="employe" :title="l.employe.nom_affiche">
                    <span class="tete-employe">
                      <UiAvatar :nom="l.employe.nom_affiche" :matricule="l.employe.code_barre" />
                      <span class="identifiant">{{ l.employe.identifiant }}</span>
                    </span>
                    <template v-if="voirEnCours">
                      <span v-for="e in l.en_cours.filter(garderProjet)" :key="`${e.projet_id}-${e.description}`" class="en-cours"
                        :style="{ borderColor: donnees.statut_en_cours?.couleur }">{{ e.projet }} · {{ e.description }}</span>
                    </template>
                  </th>
                  <td v-for="j in donnees.jours" :key="j.date" class="cellule-jour"
                    :class="{ weekend: !j.ouvrable, passe: j.passe, aujourdhui: j.aujourdhui, lundi: j.nom === 'Lun.',
                              attente: projetChoisi && planifiableCase(l, j.date), survol: survol === cleCase(l.employe.id, j.date) }"
                    @dragover.prevent="planifiableCase(l, j.date) && (survol = cleCase(l.employe.id, j.date))"
                    @dragleave="survol = ''" @drop.prevent="deposer(l, j.date)" @click="cliquerCase(l, j.date)">
                    <span v-for="e in contenu(l, j.date).pointe" :key="`p${e.projet_id}`" class="element pointe"
                      :title="`Pointé : ${nomAffaire(e)} › ${e.prestation} › ${e.projet} (${heures(e.minutes)})`">
                      <span class="texte-element">{{ e.projet }}</span><small>{{ heures(e.minutes) }}</small></span>
                    <span v-for="e in contenu(l, j.date).prevu" :key="`v${e.id}`" class="element prevu"
                      :draggable="donnees.droits.modifier && l.planifiable" :title="`Planifié : ${nomAffaire(e)} › ${e.prestation} › ${e.projet}`"
                      @dragstart="glisser({ type: 'prevu', id: e.id })" @click.stop>
                      <span class="texte-element">{{ e.projet }}</span>
                      <button v-if="donnees.droits.supprimer && l.planifiable" type="button" class="retirer" :aria-label="`Retirer ${e.projet}`"
                        @click.stop="retirer(e.id)"><i class="bi bi-x" aria-hidden="true" /></button>
                    </span>
                  </td>
                </tr>
                <tr v-if="!lignesVisibles.length"><td :colspan="donnees.jours.length + 1" class="vide">Personne pour ces filtres.</td></tr>
              </tbody>
            </table>
          </div>
          <p class="legende texte-xs texte-doux">
            {{ lignesVisibles.length }} / {{ lignes.length }} personne(s) ·
            <span class="element pointe">Pointé</span> passé et aujourd’hui ·
            <span class="element prevu">Planifié</span> aujourd’hui et à venir
            <template v-if="donnees.statut_en_cours"> · sous l’identifiant : en train de faire (statut « {{ donnees.statut_en_cours.nom }} »)</template>
            <template v-else> · « En train de faire » : cochez le rôle d’un statut dans Marchés > Statuts</template>
            · <i class="bi bi-flag-fill" aria-hidden="true" /> échéance (rouge : en retard, orange : à 7 jours ou moins, vert : terminé)
            <template v-if="voirEcheances && !auMoinsUneEcheance"> (aucune sur ces semaines)</template>
            · défilez à gauche / à droite pour les autres semaines
          </p>
        </section>
      </div>

      <aside class="panneau-lateral">
        <section class="carte liste">
          <header class="entete">Listes des Projets / Communes</header>
          <input v-model="rechercheProjets" class="saisie" type="search" placeholder="Rechercher" aria-label="Rechercher un projet ou une commune" />
          <p v-if="donnees?.droits.creer" class="texte-xs texte-doux aide">Glissez un projet sur une case (aujourd’hui ou plus tard), ou cliquez-le puis cliquez la case.</p>
          <ul>
            <li v-for="p in projetsVisibles" :key="p.projet_id">
              <button type="button" class="projet" :class="{ selectionne: projetChoisi?.projet_id === p.projet_id }"
                :draggable="donnees?.droits.creer" :aria-pressed="projetChoisi?.projet_id === p.projet_id"
                @dragstart="glisser({ type: 'projet', projet: p })"
                @click="projetChoisi = donnees?.droits.creer ? (projetChoisi?.projet_id === p.projet_id ? null : p) : null">
                <span class="ligne-projet"><span class="gras">{{ p.projet }}</span>
                  <span v-if="p.etat !== 'ok'" class="etat-projet" :class="p.etat"><i :class="`bi bi-${ETATS[p.etat].icone}`" aria-hidden="true" /> {{ ETATS[p.etat].libelle }}</span></span>
                <span class="texte-xs texte-doux">{{ nomAffaire(p) }} › {{ p.prestation }}</span>
                <span class="texte-xs echeance-projet" :class="p.etat">
                  <i class="bi bi-flag" aria-hidden="true" /> {{ texteEcheance(p) }} · {{ p.avancement }} %
                  <span class="mini-barre"><span :style="{ width: `${p.avancement}%` }" /></span>
                </span>
              </button>
            </li>
            <li v-if="!projetsVisibles.length" class="texte-xs texte-doux vide">Aucun projet / commune.</li>
          </ul>
        </section>
        <section class="carte liste">
          <header class="entete">Listes des Employés et leurs disponibilités</header>
          <input v-model="rechercheEmployes" class="saisie" type="search" placeholder="Rechercher" aria-label="Rechercher un employé" />
          <p class="texte-xs texte-doux aide">Jours ouvrables des 14 prochains jours sans rien de pointé ni de planifié.</p>
          <ul>
            <li v-for="l in disponibles" :key="l.employe.id" class="dispo">
              <span class="tete-employe" :title="l.employe.nom_affiche">
                <UiAvatar :nom="l.employe.nom_affiche" :matricule="l.employe.code_barre" />
                <span class="identifiant">{{ l.employe.identifiant }}</span>
              </span>
              <span v-if="l.jours_libres.length" class="jours-libres">
                <span v-for="d in l.jours_libres.slice(0, 6)" :key="d" class="libre">{{ jourCourt(d) }}</span>
                <span v-if="l.jours_libres.length > 6" class="texte-xs texte-doux">+{{ l.jours_libres.length - 6 }}</span>
              </span>
              <span v-else class="texte-xs texte-doux">Complet</span>
            </li>
            <li v-if="!disponibles.length" class="texte-xs texte-doux vide">Personne.</li>
          </ul>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.page-large { max-width: none; }
.ligne-titre { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e3); margin-bottom: var(--e3); }
.disposition { display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: var(--e3); align-items: start; }
.colonne-grille { display: flex; flex-direction: column; gap: var(--e3); min-width: 0; }
.filtres { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2); padding: var(--e3); }
.recherche-personne { width: 200px; height: 34px; }
.separateur { width: 1px; height: 24px; background: var(--bordure-forte); }
.bascule { display: inline-flex; align-items: center; gap: 5px; font-size: var(--taille-s); cursor: pointer; white-space: nowrap; }
.bandeau-choix { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; background: var(--marine-pale); color: var(--marine); font-size: var(--taille-s); }
.lien { border: none; background: none; color: var(--rouge); font-weight: 600; cursor: pointer; }
.cadre-grille { padding: var(--e2); background: var(--surface-douce); }
.defilement { overflow: auto; height: calc(100vh - 215px); min-height: 480px; border: 1px solid var(--marine); background: var(--surface); }
.grille { border-collapse: separate; border-spacing: 0; table-layout: fixed; }
.grille th, .grille td { border-right: 1px solid var(--marine); border-bottom: 1px solid var(--marine); }
/* En-têtes figés en haut, colonne Employé figée à gauche */
thead th { position: sticky; z-index: 2; }
.rangee-semaines th { top: 0; height: 32px; }
.rangee-jours th { top: 32px; }
.rangee-jours th { height: 40px; }
.rangee-echeances th { top: 72px; }
.titre-echeances { left: 0; z-index: 4 !important; padding: 4px 8px; text-align: left; font-size: var(--taille-xs); font-weight: 700; color: var(--marine); background: #fff8f0; }
.case-echeance { padding: 2px; vertical-align: top; background: #fff8f0; font-weight: 400; }
.echeance { display: flex; align-items: center; gap: 3px; margin-bottom: 2px; padding: 1px 5px; border-radius: 4px; font-size: 0.64rem; font-weight: 700;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; background: var(--marine-pale); color: var(--marine); text-align: left; }
.echeance.retard { background: color-mix(in srgb, var(--rouge) 16%, #fff); color: var(--rouge); }
.echeance.proche { background: color-mix(in srgb, #f59e0b 20%, #fff); color: #b45309; }
.echeance.termine { background: color-mix(in srgb, var(--succes) 15%, #fff); color: var(--succes); }
.ligne-projet { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.etat-projet { flex: none; padding: 1px 7px; border-radius: 999px; font-size: 0.64rem; font-weight: 700; }
.etat-projet.retard { background: color-mix(in srgb, var(--rouge) 14%, #fff); color: var(--rouge); }
.etat-projet.proche { background: color-mix(in srgb, #f59e0b 18%, #fff); color: #b45309; }
.etat-projet.termine { background: color-mix(in srgb, var(--succes) 14%, #fff); color: var(--succes); }
.echeance-projet { display: flex; align-items: center; gap: 4px; margin-top: 2px; color: var(--texte-doux); }
.echeance-projet.retard { color: var(--rouge); font-weight: 600; }
.echeance-projet.proche { color: #b45309; font-weight: 600; }
.mini-barre { flex: 1; max-width: 70px; height: 4px; border-radius: 999px; background: var(--bordure); overflow: hidden; }
.mini-barre span { display: block; height: 100%; background: var(--marine-clair); }
.coin { left: 0; z-index: 4 !important; font-size: 1.5rem; font-weight: 500; color: var(--marine); background: var(--surface); }
.semaine { background: var(--surface); color: var(--rouge); font-size: 1.05rem; font-weight: 500; border-top: 1px solid var(--rouge); border-right: 1px solid var(--rouge) !important; }
.jour { padding: 4px; background: var(--marine); color: #fff; font-weight: 400; }
.jour.aujourdhui { box-shadow: inset 0 -4px 0 var(--rouge); }
.jour.weekend { background: #2a4a75; }
.nom-jour { display: block; font-style: italic; font-size: var(--taille-s); }
.date-jour { display: block; font-size: 0.6rem; font-style: italic; opacity: 0.85; }
.employe { position: sticky; left: 0; z-index: 1; padding: 6px 8px; text-align: left; vertical-align: top; font-weight: 400; background: var(--surface); box-shadow: 2px 0 0 var(--marine); }
.tete-employe { display: flex; align-items: center; gap: 6px; min-width: 0; }
.direct { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; background: var(--surface-douce); color: var(--texte-doux); font-size: var(--taille-xs); font-weight: 700; }
.direct .point { width: 8px; height: 8px; border-radius: 50%; background: var(--texte-leger); }
.direct.actif { color: var(--succes); background: color-mix(in srgb, var(--succes) 12%, var(--surface)); }
.direct.actif .point { background: var(--succes); }
.identifiant { display: block; font-weight: 600; color: var(--marine); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.en-cours { display: block; margin-top: 2px; padding-left: 6px; border-left: 3px solid var(--marine); font-size: 0.66rem; color: var(--texte-doux); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
tbody tr:nth-child(even) td, tbody tr:nth-child(even) .employe { background: #f7f7f7; }
.cellule-jour { height: 44px; padding: 3px; vertical-align: top; }
.cellule-jour.lundi, .jour.lundi { border-left: 2px solid var(--marine); }
.cellule-jour.weekend { background: #f3f4f6 !important; }
.cellule-jour.aujourdhui { background: color-mix(in srgb, var(--rouge) 4%, var(--surface)) !important; }
.cellule-jour.attente { cursor: copy; background: color-mix(in srgb, var(--marine-pale) 60%, var(--surface)) !important; }
.cellule-jour.survol { outline: 2px dashed var(--marine); outline-offset: -3px; background: var(--marine-pale) !important; }
.element { display: flex; align-items: center; justify-content: space-between; gap: 4px; margin-bottom: 2px; padding: 2px 6px; border-radius: 4px;
  font-size: 0.68rem; line-height: 1.25; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.legende .element { display: inline-flex; margin: 0 2px; }
.pointe { background: var(--marine); color: #fff; }
.texte-element { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.element small, .element .retirer, .echeance i { flex: none; }
.pointe small { opacity: 0.8; }
.prevu { border: 1.5px dashed var(--marine); color: var(--marine); background: var(--surface); cursor: grab; }
.retirer { display: inline-grid; place-items: center; width: 16px; height: 16px; flex: none; border: none; border-radius: 50%; background: none; color: var(--rouge); cursor: pointer; }
.vide { padding: var(--e3); text-align: left; color: var(--texte-doux); }
.legende { margin-top: var(--e2); }
/* Panneau de droite : reste visible quand on descend dans la page */
.panneau-lateral { position: sticky; top: 64px; display: flex; flex-direction: column; gap: var(--e3); height: calc(100vh - 76px); min-height: 640px; }
.liste { display: flex; flex-direction: column; gap: var(--e2); padding: var(--e3); min-height: 0; overflow: hidden; }
.liste:first-child { flex: 1 1 55%; }
.liste:last-child { flex: 1 1 45%; }
.entete { padding: 8px; border-radius: var(--rayon); background: var(--marine); color: #fff; text-align: center; font-size: var(--taille-s); }
.aide { margin: 0; }
.liste ul { flex: 1; list-style: none; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; min-height: 0; }
.projet { display: flex; flex-direction: column; width: 100%; padding: 6px 10px; border: 1px solid var(--bordure); border-radius: var(--rayon-s); background: var(--surface-douce); text-align: left; cursor: grab; }
.projet.selectionne { border-color: var(--marine); background: var(--marine-pale); }
.dispo { display: flex; flex-direction: column; align-items: flex-start; gap: 3px; padding: 5px 8px; border: 1px solid var(--bordure); border-radius: var(--rayon-s); background: var(--surface-douce); }
.dispo .identifiant { font-size: var(--taille-s); }
.jours-libres { display: flex; flex-wrap: wrap; gap: 3px; }
.libre { padding: 1px 6px; border-radius: 999px; background: color-mix(in srgb, var(--succes) 14%, var(--surface)); color: var(--succes); font-size: 0.66rem; font-weight: 600; white-space: nowrap; }
@media (max-width: 1100px) { .disposition { grid-template-columns: 1fr; } .panneau-lateral { position: static; max-height: none; } }
</style>
