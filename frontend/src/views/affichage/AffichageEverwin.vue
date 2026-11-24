<!--
  Affichage Everwin : la semaine de pointages (lundi → dimanche) en grille, en lecture seule.
  Une ligne par affaire et par tâche, le total de la semaine, une case par jour ;
  l'icône « message » d'une case montre le détail. Total du jour en rouge si la H_Durée
  d'un jour ouvrable n'atteint pas 8 h. Un superadmin peut choisir une autre personne.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { everwinApi } from '@/api'
import type { DetailEverwin, GrilleEverwin } from '@/api/pointages'
import { useToast } from '@/composables/useToast'
import type { Identifiant } from '@/types'
import SelectEmploye from '@/components/formulaires/SelectEmploye.vue'
import UiAvatar from '@/components/ui/UiAvatar.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'
import UiMenuDeroulant from '@/components/ui/UiMenuDeroulant.vue'
import UiRecherche from '@/components/ui/UiRecherche.vue'

const toast = useToast()

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const lundiDe = (d: Date) => {
  const l = new Date(d)
  l.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return l
}
const lundi = ref(lundiDe(new Date()))
const changerSemaine = (pas: number) => {
  const l = new Date(lundi.value)
  l.setDate(l.getDate() + 7 * pas)
  lundi.value = l
}
const cetteSemaine = () => (lundi.value = lundiDe(new Date()))
const estCetteSemaine = computed(() => iso(lundi.value) === iso(lundiDe(new Date())))
const libelleSemaine = computed(() => {
  const dimanche = new Date(lundi.value)
  dimanche.setDate(dimanche.getDate() + 6)
  const f = (d: Date, annee = false) => d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', ...(annee ? { year: 'numeric' } : {}) })
  return `Semaine du ${f(lundi.value)} au ${f(dimanche, true)}`
})

// Personne affichée : moi ; un superadmin peut en choisir une autre
const personne = ref<Identifiant | null>(null)
const grille = ref<GrilleEverwin | null>(null)
const chargement = ref(false)
async function charger() {
  chargement.value = true
  try {
    grille.value = await everwinApi.semaine(iso(lundi.value), personne.value)
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargement.value = false
  }
}
watch([lundi, personne], charger, { immediate: true })

const recherche = ref('')
const affaires = computed(() => {
  const t = recherche.value.toLowerCase()
  return (grille.value?.affaires ?? []).filter((a) => !t || `${a.num_affaire} ${a.nom} ${a.taches.join(' ')}`.toLowerCase().includes(t))
})

const h = (minutes?: number) => (minutes ? (minutes / 60).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '')
const nomAffaire = (a: { num_affaire: string; nom: string }) => (a.num_affaire ? `${a.num_affaire} - ${a.nom}` : a.nom)

// Détail d'une case (icône message)
const detail = ref<{ titre: string; lignes: DetailEverwin[] } | null>(null)
const ancreDetail = ref<HTMLElement | null>(null)
const detailOuvert = ref(false)
function ouvrirDetail(evenement: MouseEvent, titre: string, lignes: DetailEverwin[]) {
  ancreDetail.value = evenement.currentTarget as HTMLElement
  detail.value = { titre, lignes }
  detailOuvert.value = true
}

const exportEnCours = ref(false)
async function exporter() {
  exportEnCours.value = true
  try {
    await everwinApi.exporter(iso(lundi.value), personne.value)
  } catch (e) {
    toast.erreur(e)
  } finally {
    exportEnCours.value = false
  }
}
</script>

<template>
  <div class="page page-large pile">
    <div class="barre carte">
      <div class="semaine">
        <UiBouton icone="chevron-left" @click="changerSemaine(-1)">Semaine précédente</UiBouton>
        <span class="libelle-semaine">{{ libelleSemaine }}</span>
        <UiBouton @click="changerSemaine(1)">Semaine suivante <i class="bi bi-chevron-right" aria-hidden="true" /></UiBouton>
        <UiBouton v-if="!estCetteSemaine" variante="fantome" petit icone="calendar-check" @click="cetteSemaine">Cette semaine</UiBouton>
      </div>
      <div class="personnes">
        <label class="champ-info">
          <span>Chef</span>
          <span class="valeur">
            <template v-if="grille?.chef"><UiAvatar :nom="grille.chef.nom_affiche" :matricule="grille.chef.code_barre" /> {{ grille.chef.nom_affiche }}</template>
            <span v-else class="texte-doux">—</span>
          </span>
        </label>
        <label class="champ-info large">
          <span>Personne</span>
          <SelectEmploye v-if="grille?.peut_choisir" v-model="personne" :employe-initial="grille?.employe" placeholder="Moi"
            :rechercher="everwinApi.personnes" />
          <span v-else class="valeur">
            <template v-if="grille"><UiAvatar :nom="grille.employe.nom_affiche" :matricule="grille.employe.code_barre" /> {{ grille.employe.nom_affiche }}</template>
          </span>
        </label>
      </div>
    </div>

    <section class="carte panneau">
      <div class="outils">
        <UiBouton variante="fantome" petit icone="download" :chargement="exportEnCours" @click="exporter">Exporter</UiBouton>
        <UiRecherche v-model="recherche" class="recherche" placeholder="Affaire ou tâche" />
      </div>

      <UiChargement v-if="chargement && !grille" />
      <div v-else-if="grille" class="tableau-conteneur">
        <table class="grille">
          <thead>
            <tr>
              <th class="col-affaire">Affaire<span class="sous">Ligne d'affaire et tâche</span></th>
              <th class="col-total">Total saisi</th>
              <th v-for="j in grille.jours" :key="j.date" :class="{ weekend: !j.ouvrable }">
                {{ j.nom }}<span class="sous">{{ j.date.slice(8, 10) }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in affaires" :key="a.id">
              <td class="col-affaire">
                <span class="gras">{{ nomAffaire(a) }}</span>
                <span class="tache"><i class="bi bi-list-task" aria-hidden="true" /> {{ a.tache }}</span>
              </td>
              <td class="col-total"><span class="pastille total">{{ h(a.total_minutes) }}</span></td>
              <td v-for="j in grille.jours" :key="j.date" :class="{ weekend: !j.ouvrable }">
                <span class="case">{{ h(a.jours[j.date]?.minutes) }}</span>
                <button
                  v-if="a.jours[j.date]"
                  type="button"
                  class="message"
                  :aria-label="`Détail du ${j.nom} ${j.date.slice(8, 10)} – ${nomAffaire(a)} – ${a.tache}`"
                  @click="ouvrirDetail($event, `${j.nom} ${j.date.slice(8, 10)} – ${nomAffaire(a)} – ${a.tache}`, a.jours[j.date]!.details)"
                >
                  <i class="bi bi-chat-left-text" aria-hidden="true" />
                </button>
                <span v-else class="message vide" aria-hidden="true"><i class="bi bi-chat-left" /></span>
              </td>
            </tr>
            <tr v-if="!affaires.length">
              <td :colspan="2 + grille.jours.length">
                <UiEtatVide icone="calendar-week" :titre="recherche ? 'Aucune affaire ne correspond' : 'Aucun pointage cette semaine'" />
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td class="col-affaire gras">Total</td>
              <td class="col-total"><span class="pastille total">{{ h(grille.total_minutes) || '0,00' }}</span></td>
              <td v-for="j in grille.jours" :key="j.date" :class="{ weekend: !j.ouvrable }">
                <span
                  class="case total-jour"
                  :class="{ rouge: grille.totaux[j.date]?.incomplet }"
                  :title="j.ouvrable ? `H_Durée : ${h(grille.totaux[j.date]?.minutes_normales) || '0'} h sur 8 h` : 'Week-end'"
                >{{ h(grille.totaux[j.date]?.minutes) }}</span>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>

    <p class="texte-xs texte-doux legende">
      <span class="echantillon rouge" /> Jour ouvrable dont la H_Durée n'atteint pas 8 h.
      Les cases comptent tout le temps pointé (H_Durée + HS) ; l'icône <i class="bi bi-chat-left-text" aria-hidden="true" /> montre le détail.
    </p>

    <UiMenuDeroulant v-model="detailOuvert" :ancre="ancreDetail" :largeur-min="360">
      <div v-if="detail" class="detail">
        <p class="gras titre-detail">{{ detail.titre }}</p>
        <div v-for="(d, i) in detail.lignes" :key="i" class="bloc">
          <p class="ligne-entre">
            <span class="gras">{{ d.heure_debut }}–{{ d.heure_fin }}</span>
            <span>{{ h(d.minutes) }} h<template v-if="d.minutes_hs"> (dont {{ h(d.minutes_hs) }} HS)</template><template v-if="d.pause">, pause −1 h</template></span>
          </p>
          <dl>
            <dt>Tâche</dt><dd>{{ d.tache }}</dd>
            <dt>Prestation</dt><dd>{{ d.prestation }}</dd>
            <dt>Projet</dt><dd>{{ d.projet }}</dd>
            <dt>Description{{ d.descriptions.length > 1 ? 's' : '' }}</dt><dd>{{ d.descriptions.join(', ') }}</dd>
            <dt>Commentaire</dt><dd>{{ d.commentaire || '—' }}</dd>
          </dl>
        </div>
      </div>
    </UiMenuDeroulant>
  </div>
</template>

<style scoped>
.page-large { max-width: none; }
.barre { display: flex; align-items: center; justify-content: space-between; gap: var(--e4); flex-wrap: wrap; padding: var(--e3) var(--e4); }
.semaine { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; }
.libelle-semaine { font-weight: 700; color: var(--marine); padding: 0 var(--e2); }
.personnes { display: flex; gap: var(--e3); flex-wrap: wrap; }
.champ-info { display: flex; flex-direction: column; gap: 2px; font-size: var(--taille-xs); color: var(--texte-doux); min-width: 220px; }
.champ-info.large { min-width: 280px; }
.champ-info .valeur { display: flex; align-items: center; gap: var(--e2); min-height: 36px; padding: 0 var(--e3); border: 1px solid var(--bordure); border-radius: var(--rayon); color: var(--texte); font-size: var(--taille-s); font-weight: 600; }
.champ-info .valeur :deep(.avatar) { width: 24px; height: 24px; font-size: 0.6rem; }
.panneau { overflow: hidden; }
.outils { display: flex; align-items: center; gap: var(--e1); padding: var(--e2) var(--e3); border-bottom: 1px solid var(--bordure); background: var(--surface-douce); }
.recherche { margin-left: auto; min-width: 160px; max-width: 260px; }
.recherche :deep(.saisie) { height: 32px; }

.grille { width: 100%; border-collapse: separate; border-spacing: 0; font-size: var(--taille-s); }
.grille thead th { background: var(--marine); color: #fff; font-weight: 600; padding: var(--e2) var(--e3); text-align: center; white-space: nowrap; }
.grille thead th.col-affaire { text-align: left; }
.grille .sous { display: block; font-size: var(--taille-xs); font-weight: 400; opacity: 0.8; font-style: italic; }
.grille td { padding: var(--e3); text-align: center; border-bottom: 1px solid var(--bordure); vertical-align: middle; }
.grille td.col-affaire { text-align: left; min-width: 260px; }
.grille td.col-affaire .sous { color: var(--texte-doux); }
.tache { display: inline-flex; align-items: center; gap: 4px; margin-top: 3px; padding: 1px 8px; border-radius: 999px; background: var(--marine-pale); color: var(--marine); font-size: var(--taille-xs); font-weight: 600; }
.grille td.col-affaire .gras { display: block; }
.grille .weekend { background: color-mix(in srgb, var(--surface-douce) 60%, transparent); }
.grille thead th.weekend { background: var(--marine-fonce); }
.case { display: block; min-width: 64px; height: 30px; line-height: 28px; margin: 0 auto; border: 1px solid var(--bordure-forte); border-radius: var(--rayon-s); background: var(--surface); font-variant-numeric: tabular-nums; font-weight: 600; color: var(--marine); }
.message { display: inline-grid; place-items: center; margin-top: 4px; width: 26px; height: 22px; border: none; border-radius: var(--rayon-s); background: none; color: var(--marine-clair); cursor: pointer; }
.message:hover { background: var(--marine-pale); }
.message.vide { color: var(--bordure-forte); cursor: default; }
.pastille.total { display: inline-block; min-width: 70px; padding: 4px 10px; border-radius: var(--rayon-s); background: #4fd65a; color: #0b3d12; font-weight: 700; font-variant-numeric: tabular-nums; }
tfoot td { background: var(--surface-douce); border-bottom: none; }
.total-jour.rouge { background: var(--rouge); border-color: var(--rouge); color: #fff; }
.legende { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; }
.echantillon { width: 14px; height: 14px; border-radius: 3px; }
.echantillon.rouge { background: var(--rouge); }

.detail { padding: var(--e2) var(--e3); max-width: 420px; }
.titre-detail { color: var(--marine); margin-bottom: var(--e2); }
.bloc { padding: var(--e2) 0; border-top: 1px solid var(--bordure); font-size: var(--taille-s); }
.bloc dl { display: grid; grid-template-columns: auto 1fr; gap: 2px var(--e3); margin-top: var(--e1); }
.bloc dt { color: var(--texte-doux); }
</style>
