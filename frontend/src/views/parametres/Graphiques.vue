<!--
  Paramètres > Graphiques (administrateurs) : réglages des graphiques du Rendement, en un seul endroit.
    Globale   : tâches du camembert « Somme du temps par tâche ».
    Evolution : deux courbes superposées, chacune un groupe de tâches (nom, couleur, tâches).
    Réel vs Objectif : barre 1 = le réel (ses tâches), barre 2 = le Rendement objectif.
    Analyse : seuils des zones et des signaux automatiques.
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { parametresGraphiquesApi, tachesApi } from '@/api'
import type { ParametresGraphiques } from '@/api/rendements'
import { messageErreur } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useSelectionRendement } from '@/store/selectionRendement'
import type { ElementCatalogue } from '@/types'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiCouleur from '@/components/ui/UiCouleur.vue'

const toast = useToast()
const taches = ref<ElementCatalogue[]>([])
const p = ref<ParametresGraphiques | null>(null)
const envoi = ref(false)

onMounted(async () => {
  try {
    ;[taches.value, p.value] = await Promise.all([tachesApi.tous() as Promise<ElementCatalogue[]>, parametresGraphiquesApi.lire()])
  } catch (e) {
    toast.erreur(e)
  }
})

const GROUPES = [
  { prefixe: 'courbe', element: 'de la courbe', icone: 'graph-up', titre: 'Evolution : deux courbes superposées',
    aide: 'Chaque courbe montre le rendement par date pointée pour son groupe de tâches.' },
  { prefixe: 'barre', element: 'de la barre', icone: 'bar-chart', titre: 'Réel vs Objectif : deux barres par employé',
    aide: 'Barre 1 : le réel, avec le temps de ses tâches. Barre 2 : le Rendement objectif (pas de tâches).' },
] as const
type Cle = `${'courbe' | 'barre'}${1 | 2}_${'nom' | 'couleur' | 'taches'}`
const cle = <S extends 'nom' | 'couleur' | 'taches'>(prefixe: 'courbe' | 'barre', n: 1 | 2, suffixe: S) => `${prefixe}${n}_${suffixe}` as Extract<Cle, `${string}_${S}`>

const SEUILS = [
  { cle: 'analyse_seuil_temps', libelle: '« Beaucoup de temps » à partir de', unite: '%', min: 1, max: 100,
    aide: 'Part du temps du mois : sépare « À garder / À revoir » de « Potentiel / Ponctuel ».' },
  { cle: 'analyse_seuil_aide', libelle: 'Badge « Aide » à partir de', unite: '%', min: 1, max: 100,
    aide: 'Part du temps passée sur des lignes dont il n’est pas l’Employé.' },
  { cle: 'analyse_mois_adaptation', libelle: 'Période d’adaptation', unite: 'mois', min: 1, max: 24,
    aide: 'Premiers mois sur une prestation : un rendement sous l’objectif y est « En adaptation ».' },
  { cle: 'analyse_seuil_baisse', libelle: 'Badge « Baisse soudaine » à partir de', unite: '%', min: 1, max: 100,
    aide: 'Chute de rentabilité par rapport à ses mois précédents, alors qu’il est bon ailleurs.' },
] as const

function basculer(liste: number[], id: number) {
  const i = liste.indexOf(id)
  if (i >= 0) liste.splice(i, 1)
  else liste.push(id)
}

async function enregistrer() {
  if (!p.value) return
  envoi.value = true
  try {
    p.value = await parametresGraphiquesApi.enregistrer(p.value)
    const selection = useSelectionRendement()   // les onglets suivent sans recharger
    selection.sourcesAutorisees = { feuilles: p.value.donnees_feuilles, pointages: !!p.value.donnees_pointages }
    selection.actif = !!p.value.synchronisation
    toast.succes('Paramètres des graphiques enregistrés')
  } catch (e) {
    toast.erreur(messageErreur(e))
  } finally {
    envoi.value = false
  }
}
</script>

<template>
  <div class="page pile">
    <EnTetePage titre="Graphiques" description="Les réglages des graphiques du Rendement, au même endroit : ils s'appliquent à tout le monde.">
      <UiBouton variante="primaire" icone="check-lg" :chargement="envoi" :desactive="!p" @click="enregistrer">Enregistrer</UiBouton>
    </EnTetePage>

    <UiChargement v-if="!p" />
    <template v-else>
      <section class="carte carte-corps pile">
        <header>
          <h2 class="titre-section"><i class="bi bi-file-earmark-spreadsheet" aria-hidden="true" /> Source des données</h2>
          <p class="texte-petit texte-doux">
            Chaque source autorisée apparaît dans le choix « Source » des onglets du Rendement, à côté de la source normale
            (pointages + feuilles). Feuilles : le temps est lu dans les feuilles (Temps de prod, de contrôle, de reprise, datés à
            la Date de début). Pointages : toutes les descriptions pointées comptent, même sans feuille (la quantité revient à
            la personne qui a pointé le plus de Production ; période et mois sur le premier jour pointé).
          </p>
        </header>
        <label class="interrupteur-ligne">
          <input v-model="p.donnees_feuilles" type="checkbox" role="switch" />
          <span class="interrupteur" aria-hidden="true" />
          Autoriser les données des feuilles (anciennes données sans pointage)
        </label>
        <label class="interrupteur-ligne">
          <input v-model="p.synchronisation" type="checkbox" role="switch" />
          <span class="interrupteur" aria-hidden="true" />
          Synchronisation des données : mêmes Affaires et Prestations dans Globale, Evolution, Réel vs Objectif et Evaluation Employé
        </label>
        <label class="interrupteur-ligne">
          <input v-model="p.donnees_pointages" type="checkbox" role="switch" />
          <span class="interrupteur" aria-hidden="true" />
          Autoriser les données des pointages (affaires pointées sans feuille)
        </label>
      </section>

      <section class="carte carte-corps pile">
        <header>
          <h2 class="titre-section"><i class="bi bi-pie-chart" aria-hidden="true" /> Globale : camembert du temps</h2>
          <p class="texte-petit texte-doux">Tâches affichées dans « Somme du temps par tâche ». Aucune cochée : toutes les tâches.</p>
        </header>
        <div class="cases">
          <label v-for="t in taches" :key="t.id" class="case puce" :class="{ active: p.taches_camembert.includes(t.id) }">
            <input type="checkbox" :checked="p.taches_camembert.includes(t.id)" @change="basculer(p.taches_camembert, t.id)" /> {{ t.nom }}
          </label>
        </div>
      </section>

      <section v-for="groupe in GROUPES" :key="groupe.prefixe" class="carte carte-corps pile">
        <header>
          <h2 class="titre-section"><i :class="`bi bi-${groupe.icone}`" aria-hidden="true" /> {{ groupe.titre }}</h2>
          <p class="texte-petit texte-doux">{{ groupe.aide }} Aucune tâche cochée : toutes.</p>
        </header>
        <div class="courbes">
          <div v-for="n in [1, 2] as const" :key="n" class="courbe" :style="{ borderColor: p[cle(groupe.prefixe, n, 'couleur')] }">
            <div class="ligne-courbe">
              <label class="champ">
                <span class="champ-libelle">Nom {{ groupe.element }} {{ n }}</span>
                <input v-model="p[cle(groupe.prefixe, n, 'nom')]" class="saisie" maxlength="60" />
              </label>
              <div class="champ">
                <span class="champ-libelle">Couleur</span>
                <UiCouleur v-model="p[cle(groupe.prefixe, n, 'couleur')]" />
              </div>
            </div>
            <p v-if="groupe.prefixe === 'barre' && n === 2" class="texte-petit texte-doux objectif-info">
              <i class="bi bi-bullseye" aria-hidden="true" /> Affiche le Rendement objectif de l’employé (tableau « Rendement objectif »).
            </p>
            <template v-else>
            <span class="champ-libelle">Tâches</span>
            <div class="cases">
              <label v-for="t in taches" :key="t.id" class="case puce" :class="{ active: p[cle(groupe.prefixe, n, 'taches')].includes(t.id) }"
                :style="p[cle(groupe.prefixe, n, 'taches')].includes(t.id) ? { background: p[cle(groupe.prefixe, n, 'couleur')], borderColor: p[cle(groupe.prefixe, n, 'couleur')] } : undefined">
                <input type="checkbox" :checked="p[cle(groupe.prefixe, n, 'taches')].includes(t.id)" @change="basculer(p[cle(groupe.prefixe, n, 'taches')], t.id)" /> {{ t.nom }}
              </label>
            </div>
            </template>
          </div>
        </div>
      </section>

      <section class="carte carte-corps pile">
        <header>
          <h2 class="titre-section"><i class="bi bi-search" aria-hidden="true" /> Analyse : zones et signaux</h2>
          <p class="texte-petit texte-doux">Seuils de la carte du mois et des badges automatiques de l’onglet Analyse.</p>
        </header>
        <div class="seuils">
          <label v-for="s in SEUILS" :key="s.cle" class="champ seuil">
            <span class="champ-libelle">{{ s.libelle }}</span>
            <span class="saisie-unite"><input v-model.number="p[s.cle]" class="saisie" type="number" :min="s.min" :max="s.max" step="1" />{{ s.unite }}</span>
            <span class="champ-aide">{{ s.aide }}</span>
          </label>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.titre-section { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-m); color: var(--marine); }
.cases { display: flex; flex-wrap: wrap; gap: var(--e2); }
.puce { padding: 4px 12px; border: 1px solid var(--bordure-forte); border-radius: 999px; cursor: pointer; font-size: var(--taille-s); }
.puce input { position: absolute; opacity: 0; pointer-events: none; }
.puce.active { background: var(--marine); border-color: var(--marine); color: #fff; font-weight: 600; }
.interrupteur-ligne { display: flex; align-items: center; gap: var(--e2); font-weight: 600; cursor: pointer; width: fit-content; }
.interrupteur-ligne input { position: absolute; opacity: 0; }
.interrupteur { position: relative; width: 40px; height: 22px; flex: none; border-radius: 999px; background: var(--bordure-forte); transition: background 0.15s; }
.interrupteur::after { content: ''; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: #fff; transition: transform 0.15s; }
.interrupteur-ligne input:checked + .interrupteur { background: var(--marine); }
.interrupteur-ligne input:checked + .interrupteur::after { transform: translateX(18px); }
.interrupteur-ligne input:focus-visible + .interrupteur { outline: 2px solid var(--marine-clair); outline-offset: 2px; }
.seuils { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: var(--e4); }
.saisie-unite { display: inline-flex; align-items: center; gap: var(--e2); font-weight: 600; color: var(--texte-doux); }
.saisie-unite .saisie { width: 90px; text-align: right; }
.objectif-info { display: flex; align-items: center; gap: var(--e2); padding: var(--e2); border-radius: var(--rayon); background: var(--surface-douce); }
.courbes { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: var(--e4); }
.courbe { display: flex; flex-direction: column; gap: var(--e2); padding: var(--e3); border: 1px solid; border-left-width: 5px; border-radius: var(--rayon); }
.ligne-courbe { display: flex; gap: var(--e3); align-items: flex-end; flex-wrap: wrap; }
.ligne-courbe .champ:first-child { flex: 1; min-width: 180px; }
</style>
