<!--
  Accueil : première page après la connexion (backend/ikarama/accueil.py).
    Bandeau : salutation, date, semaine, raccourcis. Chiffres clés : aujourd'hui, semaine, erreurs, lignes à surveiller.
    Gauche : ma semaine (barres et objectif 8 h), mon équipe (droit « Voir » de la Vérification).
    Droite : mon planning (7 jours), mes lignes à surveiller, mes affaires (responsable), contrôles et activité (superadmin).
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { accueilApi } from '@/api'
import type { Accueil } from '@/api/notifications'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/store/auth'
import { formatHeures, formatRelatif } from '@/utils/format'
import UiAvatar from '@/components/ui/UiAvatar.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'
import UiProgression from '@/components/ui/UiProgression.vue'

const router = useRouter()
const toast = useToast()
const auth = useAuthStore()
const donnees = ref<Accueil | null>(null)
onMounted(async () => {
  try {
    donnees.value = await accueilApi()
  } catch (e) {
    toast.erreur(e)
  }
})

const bonjour = computed(() => {
  const h = new Date().getHours()
  return h < 12 ? 'Bonjour' : h < 18 ? 'Bon après-midi' : 'Bonsoir'
})
const prenom = computed(() => donnees.value?.employe?.prenom_usuel || donnees.value?.employe?.prenom || '')
const aujourdhui = new Date()
const dateLongue = (() => {
  const t = aujourdhui.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
  return t.charAt(0).toUpperCase() + t.slice(1)
})()
const numeroSemaine = (() => {
  const d = new Date(Date.UTC(aujourdhui.getFullYear(), aujourdhui.getMonth(), aujourdhui.getDate()))
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7))
  return Math.ceil(((d.getTime() - Date.UTC(d.getUTCFullYear(), 0, 1)) / 86400000 + 1) / 7)
})()
const jourCourt = (d: string) => new Date(`${d}T12:00:00`).toLocaleDateString('fr-FR', { weekday: 'short' }).replace('.', '')
const dateCourte = (d: string) => new Date(`${d}T12:00:00`).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })
const nomJour = (d: string) => {
  const t = new Date(`${d}T12:00:00`).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'short' })
  return t.charAt(0).toUpperCase() + t.slice(1)
}

// Chiffres clés
const objectifSemaine = computed(() => (donnees.value?.moi?.semaine.filter((j) => j.ouvrable).length ?? 5) * 8 * 60)
const pct = (v: number, max: number) => Math.min(100, Math.round((v / Math.max(max, 1)) * 100))
// Barres de la semaine : échelle sur 10 h, repère de l'objectif à 8 h
const ECHELLE = 10 * 60
const hauteur = (m: number) => `${Math.min(100, (m / ECHELLE) * 100)}%`
const repere = `${(8 * 60 / ECHELLE) * 100}%`

// Mon équipe : les 8 plus gros manques, le reste sur demande
const toutVoirEquipe = ref(false)
const manquesAffiches = computed(() => (toutVoirEquipe.value ? donnees.value?.equipe?.manques : donnees.value?.equipe?.manques.slice(0, 8)) ?? [])
const plusGrosManque = computed(() => Math.max(1, ...(donnees.value?.equipe?.manques ?? []).map((m) => m.manque_minutes)))

const GRAVITES: Record<string, string> = { erreur: 'ko', attention: 'att', info: 'info' }
const RACCOURCIS = computed(() => [
  { libelle: 'Mon temps', icone: 'stopwatch', route: '/pointages/mon-temps' },
  { libelle: 'Mes feuilles', icone: 'table', route: '/google-sheet/mes-feuilles' },
  { libelle: 'Planning', icone: 'calendar-week', route: '/planning-projet' },
  ...(auth.peut('voir', 'pointages_verification') ? [{ libelle: 'Vérification', icone: 'patch-check', route: '/pointages/verification' }] : []),
])
</script>

<template>
  <div class="page page-large">
    <!-- Bandeau -->
    <section class="bandeau">
      <div class="salutation">
        <UiAvatar v-if="donnees?.employe" :nom="donnees.employe.nom_affiche" :matricule="donnees.employe.code_barre" grand />
        <div>
          <h1>{{ bonjour }}{{ prenom ? `, ${prenom}` : '' }}</h1>
          <p>{{ dateLongue }} · semaine {{ numeroSemaine }}</p>
        </div>
      </div>
      <nav class="raccourcis" aria-label="Raccourcis">
        <UiBouton variante="primaire" icone="plus-lg" class="pointer" @click="router.push('/pointages/mon-temps')">Pointer</UiBouton>
        <RouterLink v-for="r in RACCOURCIS" :key="r.route" :to="r.route" class="raccourci"><i :class="`bi bi-${r.icone}`" aria-hidden="true" />{{ r.libelle }}</RouterLink>
      </nav>
    </section>

    <UiChargement v-if="!donnees" />
    <template v-else>
      <!-- Chiffres clés -->
      <section v-if="donnees.moi" class="chiffres-cles" aria-label="Chiffres clés">
        <article class="cle">
          <i class="bi bi-sun icone-cle" aria-hidden="true" />
          <div class="valeur-cle"><span class="libelle">Aujourd’hui</span><strong>{{ formatHeures(donnees.moi.minutes_aujourdhui) }}</strong>
            <span class="sous">sur 8 h</span></div>
          <div class="jauge"><span :style="{ width: `${pct(donnees.moi.minutes_aujourdhui, 480)}%` }" :class="{ plein: donnees.moi.minutes_aujourdhui >= 480 }" /></div>
        </article>
        <article class="cle">
          <i class="bi bi-calendar-week icone-cle" aria-hidden="true" />
          <div class="valeur-cle"><span class="libelle">Cette semaine</span><strong>{{ formatHeures(donnees.moi.minutes_semaine) }}</strong>
            <span class="sous">sur {{ formatHeures(objectifSemaine) }}</span></div>
          <div class="jauge"><span :style="{ width: `${pct(donnees.moi.minutes_semaine, objectifSemaine)}%` }" :class="{ plein: donnees.moi.minutes_semaine >= objectifSemaine }" /></div>
        </article>
        <RouterLink to="/pointages/mon-temps" class="cle lien-cle" :class="donnees.moi.erreurs.length ? 'alerte-cle' : 'ok-cle'">
          <i class="bi icone-cle" :class="donnees.moi.erreurs.length ? 'bi-exclamation-triangle' : 'bi-check2-circle'" aria-hidden="true" />
          <div class="valeur-cle"><span class="libelle">Erreurs de pointage</span><strong>{{ donnees.moi.erreurs.length }}</strong>
            <span class="sous">{{ donnees.moi.erreurs.length ? 'à corriger cette semaine' : 'tout est en ordre' }}</span></div>
        </RouterLink>
        <article class="cle" :class="donnees.moi.alertes.rouges ? 'alerte-cle' : donnees.moi.alertes.nombre ? 'att-cle' : 'ok-cle'">
          <i class="bi bi-hourglass-split icone-cle" aria-hidden="true" />
          <div class="valeur-cle"><span class="libelle">Lignes à surveiller</span><strong>{{ donnees.moi.alertes.nombre }}</strong>
            <span class="sous">{{ donnees.moi.alertes.rouges }} dépassée(s)</span></div>
        </article>
      </section>

      <div class="colonnes">
        <div class="colonne">
          <!-- Ma semaine -->
          <section v-if="donnees.moi" class="carte bloc">
            <header class="tete"><h2><i class="bi bi-bar-chart" aria-hidden="true" /> Ma semaine</h2>
              <RouterLink to="/pointages/mon-temps" class="voir">Mon temps <i class="bi bi-arrow-right" aria-hidden="true" /></RouterLink></header>
            <div class="graphique" role="img" aria-label="Heures pointées par jour cette semaine">
              <span class="repere" :style="{ bottom: repere }"><span>8 h</span></span>
              <div v-for="j in donnees.moi.semaine" :key="j.date" class="jour" :class="{ weekend: !j.ouvrable, futur: j.futur }"
                :title="`${dateCourte(j.date)} : ${formatHeures(j.minutes)}`">
                <span class="heures">{{ j.minutes ? formatHeures(j.minutes) : '' }}</span>
                <div class="colonne-barre"><div class="barre" :class="{ complet: j.minutes >= 480 }" :style="{ height: hauteur(j.minutes) }" /></div>
                <span class="nom">{{ jourCourt(j.date) }}</span>
              </div>
            </div>
            <ul v-if="donnees.moi.erreurs.length" class="erreurs">
              <li v-for="e in donnees.moi.erreurs" :key="e.date + e.type">
                <i class="bi" :class="e.type === 'PAUSE' ? 'bi-cup-hot' : 'bi-exclamation-circle'" aria-hidden="true" /> {{ e.message }}
              </li>
            </ul>
            <p v-else class="ok"><i class="bi bi-check-circle-fill" aria-hidden="true" /> Aucune erreur de pointage cette semaine.</p>
          </section>

          <!-- Mon équipe (droit « Voir » de la Vérification) -->
          <section v-if="donnees.equipe" class="carte bloc">
            <header class="tete"><h2><i class="bi bi-people" aria-hidden="true" /> Mon équipe : pointages incomplets</h2>
              <span class="texte-xs texte-doux">semaine du {{ dateCourte(donnees.equipe.periode.debut) }} au {{ dateCourte(donnees.equipe.periode.fin) }}</span></header>
            <div class="resume-equipe">
              <span class="pastille-chiffre" :class="donnees.equipe.nb_manques ? 'ko' : 'ok'">{{ donnees.equipe.nb_manques }}</span>
              personne(s) incomplète(s) sur {{ donnees.equipe.nb_equipe }}
            </div>
            <p v-if="!donnees.equipe.manques.length" class="ok"><i class="bi bi-check-circle-fill" aria-hidden="true" /> Tout le monde a pointé.</p>
            <ul v-else class="manques">
              <li v-for="m in manquesAffiches" :key="m.employe.id" :title="m.detail.join('\n')">
                <UiEmploye :employe="m.employe" />
                <span class="barre-manque"><span :style="{ width: `${(m.manque_minutes / plusGrosManque) * 100}%` }" /></span>
                <span class="manque">−{{ formatHeures(m.manque_minutes) }}</span>
              </li>
            </ul>
            <div class="pied-bloc">
              <button v-if="(donnees.equipe.manques.length ?? 0) > 8" type="button" class="lien" @click="toutVoirEquipe = !toutVoirEquipe">
                {{ toutVoirEquipe ? 'Voir moins' : `Voir les ${donnees.equipe.manques.length}` }}</button>
              <RouterLink to="/pointages/verification" class="voir">Vérification <i class="bi bi-arrow-right" aria-hidden="true" /></RouterLink>
            </div>
          </section>

          <!-- Mes affaires (responsable) -->
          <section v-if="donnees.responsable" class="carte bloc">
            <header class="tete"><h2><i class="bi bi-briefcase" aria-hidden="true" /> Mes affaires</h2>
              <span class="texte-xs texte-doux">{{ donnees.responsable.nb_affaires }} affaire(s) en cours</span></header>
            <p class="sous-titre"><span class="pastille-chiffre" :class="donnees.responsable.alertes.rouges ? 'ko' : 'info'">{{ donnees.responsable.alertes.nombre }}</span>
              ligne(s) à surveiller, dont {{ donnees.responsable.alertes.rouges }} dépassée(s)</p>
            <ul v-if="donnees.responsable.alertes.lignes.length" class="alertes">
              <li v-for="l in donnees.responsable.alertes.lignes.slice(0, 5)" :key="`${l.feuille_id}-${l.numero}`">
                <RouterLink :to="`/google-sheet/feuilles/${l.feuille_id}`" class="alerte-ligne" :class="l.alerte">
                  <span class="pastille-alerte" />
                  <span class="texte-alerte"><span class="gras">{{ l.description }}</span>
                    <span class="texte-xs texte-doux">{{ l.employe ?? 'sans Employé' }} · {{ l.feuille }}, ligne {{ l.numero }}</span></span>
                  <span class="nowrap gras">{{ l.temps_prod.toLocaleString('fr-FR') }} h</span>
                </RouterLink>
              </li>
            </ul>
            <p class="sous-titre">Avancement des feuilles</p>
            <ul class="feuilles">
              <li v-for="f in donnees.responsable.feuilles" :key="f.id">
                <RouterLink :to="`/google-sheet/feuilles/${f.id}`" class="gras">{{ f.nom }}</RouterLink>
                <span class="texte-xs texte-doux">{{ f.nb_lignes }} ligne(s)</span>
                <UiProgression :valeur="f.avancement" />
              </li>
            </ul>
          </section>
        </div>

        <div class="colonne">
          <!-- Mon planning -->
          <section v-if="donnees.moi" class="carte bloc">
            <header class="tete"><h2><i class="bi bi-calendar-week" aria-hidden="true" /> Mon planning</h2>
              <RouterLink to="/planning-projet" class="voir">Planning <i class="bi bi-arrow-right" aria-hidden="true" /></RouterLink></header>
            <ul class="planning">
              <li v-for="(j, i) in donnees.moi.planning.filter((x) => x.ouvrable || x.projets.length)" :key="j.date" :class="{ aujourd: i === 0 }">
                <span class="jour-planning">{{ i === 0 ? 'Aujourd’hui' : nomJour(j.date) }}</span>
                <span v-if="j.projets.length" class="projets-planning">
                  <span v-for="p in j.projets" :key="p.projet" class="projet-planifie" :title="`${p.affaire} › ${p.prestation}`">{{ p.projet }}</span>
                </span>
                <span v-else class="texte-xs texte-leger">Rien de planifié</span>
              </li>
            </ul>
          </section>

          <!-- Mes lignes à surveiller -->
          <section v-if="donnees.moi" class="carte bloc">
            <header class="tete"><h2><i class="bi bi-hourglass-split" aria-hidden="true" /> Mes lignes à surveiller</h2>
              <span class="pastille-chiffre" :class="donnees.moi.alertes.rouges ? 'ko' : donnees.moi.alertes.nombre ? 'att' : 'ok'">{{ donnees.moi.alertes.nombre }}</span></header>
            <p v-if="!donnees.moi.alertes.nombre" class="ok"><i class="bi bi-check-circle-fill" aria-hidden="true" /> Aucune ligne n’approche de son Temps Estimatif.</p>
            <ul v-else class="alertes">
              <li v-for="l in donnees.moi.alertes.lignes" :key="`${l.feuille_id}-${l.numero}`">
                <RouterLink :to="`/google-sheet/feuilles/${l.feuille_id}`" class="alerte-ligne" :class="l.alerte">
                  <span class="pastille-alerte" />
                  <span class="texte-alerte"><span class="gras">{{ l.description }}</span>
                    <span class="texte-xs texte-doux">{{ l.affaire }} · {{ l.feuille }}, ligne {{ l.numero }}</span></span>
                  <span class="nowrap gras">{{ l.temps_prod.toLocaleString('fr-FR') }} h</span>
                </RouterLink>
              </li>
            </ul>
          </section>

          <!-- Contrôles de cohérence (superadmin, ou droit « Voir » par un rôle) -->
          <section v-if="donnees.administrateur" class="carte bloc">
            <header class="tete"><h2><i class="bi bi-clipboard2-check" aria-hidden="true" /> Contrôles de cohérence</h2>
              <RouterLink to="/parametres/controles" class="voir">Tout voir <i class="bi bi-arrow-right" aria-hidden="true" /></RouterLink></header>
            <p v-if="!donnees.administrateur.total_controles" class="ok"><i class="bi bi-check-circle-fill" aria-hidden="true" /> Aucun problème détecté.</p>
            <ul v-else class="controles">
              <li v-for="c in donnees.administrateur.controles" :key="c.code">
                <RouterLink :to="`/parametres/controles#${c.code}`" class="controle">
                  <span class="pastille-chiffre" :class="GRAVITES[c.gravite]">{{ c.nombre }}</span>{{ c.titre }}
                </RouterLink>
              </li>
            </ul>
          </section>
          <section v-if="donnees.administrateur && auth.estAdministrateur" class="carte bloc">
            <header class="tete"><h2><i class="bi bi-activity" aria-hidden="true" /> Activité récente des feuilles</h2></header>
            <p v-if="!donnees.administrateur.activite.length" class="texte-doux texte-petit">Aucune activité.</p>
            <ul v-else class="activite">
              <li v-for="(a, i) in donnees.administrateur.activite" :key="i">
                <span class="point-activite" aria-hidden="true" />
                <div><span class="gras">{{ a.auteur }}</span> · {{ a.libelle }}
                  <span v-if="a.nouvelle_valeur" class="texte-doux">« {{ a.nouvelle_valeur }} »</span>
                  <div class="texte-xs texte-leger"><RouterLink :to="`/google-sheet/feuilles/${a.feuille_id}`">{{ a.feuille }}{{ a.ligne ? `, ligne ${a.ligne}` : '' }}</RouterLink>
                    · {{ formatRelatif(a.date) }}</div></div>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page-large { max-width: 1440px; }
/* Bandeau */
.bandeau { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e4); margin-bottom: var(--e4);
  padding: var(--e4) var(--e5, 28px); border-radius: var(--rayon-l, 14px); color: #fff;
  background: linear-gradient(120deg, var(--marine) 0%, #24497a 70%, #2f5b92 100%); box-shadow: 0 8px 24px rgba(24, 53, 93, 0.18); }
.salutation { display: flex; align-items: center; gap: var(--e3); }
.salutation :deep(.avatar) { box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.35); }
.bandeau h1 { color: #fff; font-size: 1.6rem; }
.bandeau p { margin-top: 2px; color: rgba(255, 255, 255, 0.8); font-size: var(--taille-s); }
.raccourcis { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2); }
.pointer { background: var(--rouge) !important; border-color: var(--rouge) !important; }
.raccourci { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: var(--rayon); background: rgba(255, 255, 255, 0.12);
  color: #fff; font-size: var(--taille-s); font-weight: 600; text-decoration: none; transition: background 0.15s; }
.raccourci:hover { background: rgba(255, 255, 255, 0.22); }
/* Chiffres clés */
.chiffres-cles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--e3); margin-bottom: var(--e4); }
.cle { position: relative; display: flex; flex-direction: column; gap: var(--e2); padding: var(--e3) var(--e4); border: 1px solid var(--bordure);
  border-radius: var(--rayon-l, 12px); background: var(--surface); box-shadow: var(--ombre-s, 0 1px 3px rgba(0,0,0,.06)); color: var(--texte); text-decoration: none; }
.lien-cle:hover { border-color: var(--marine-clair); }
.icone-cle { position: absolute; top: var(--e3); right: var(--e4); font-size: 1.4rem; color: var(--marine-clair); opacity: 0.55; }
.valeur-cle { display: flex; flex-direction: column; }
.valeur-cle .libelle { font-size: var(--taille-xs); font-weight: 700; color: var(--texte-doux); text-transform: uppercase; letter-spacing: 0.04em; }
.valeur-cle strong { font-size: 1.9rem; line-height: 1.15; color: var(--marine); }
.valeur-cle .sous { font-size: var(--taille-xs); color: var(--texte-doux); }
.jauge { height: 6px; border-radius: 999px; background: var(--surface-douce); overflow: hidden; }
.jauge span { display: block; height: 100%; border-radius: 999px; background: var(--attention); transition: width 0.4s; }
.jauge span.plein { background: var(--succes); }
.alerte-cle { border-left: 4px solid var(--rouge); } .alerte-cle strong { color: var(--rouge); } .alerte-cle .icone-cle { color: var(--rouge); }
.att-cle { border-left: 4px solid var(--attention); } .att-cle strong { color: var(--attention); }
.ok-cle { border-left: 4px solid var(--succes); } .ok-cle .icone-cle { color: var(--succes); }
/* Colonnes */
.colonnes { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); gap: var(--e4); align-items: start; }
.colonne { display: flex; flex-direction: column; gap: var(--e4); min-width: 0; }
.bloc { padding: var(--e4); display: flex; flex-direction: column; gap: var(--e3); border-radius: var(--rayon-l, 12px); }
.tete { display: flex; align-items: center; justify-content: space-between; gap: var(--e2); }
.tete h2 { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-m); color: var(--marine); }
.voir { font-size: var(--taille-s); font-weight: 600; color: var(--marine-clair); text-decoration: none; white-space: nowrap; }
.lien { border: none; background: none; color: var(--marine-clair); font-size: var(--taille-s); font-weight: 600; cursor: pointer; }
.pied-bloc { display: flex; justify-content: space-between; align-items: center; }
/* Graphique de la semaine */
.graphique { position: relative; display: grid; grid-template-columns: repeat(7, 1fr); gap: var(--e3); height: 170px; padding-top: 18px; }
.repere { position: absolute; left: 0; right: 0; border-top: 1.5px dashed var(--rouge); margin-bottom: 22px; pointer-events: none; z-index: 1; }
.repere span { position: absolute; right: 0; top: -16px; font-size: 0.65rem; font-weight: 700; color: var(--rouge); }
.jour { display: flex; flex-direction: column; align-items: center; gap: 4px; min-height: 0; }
.jour .heures { height: 14px; font-size: 0.68rem; font-weight: 700; color: var(--marine); }
.colonne-barre { flex: 1; width: 100%; max-width: 44px; display: flex; align-items: flex-end; border-radius: 8px 8px 4px 4px; background: var(--surface-douce); overflow: hidden; }
.barre { width: 100%; border-radius: 8px 8px 4px 4px; background: linear-gradient(180deg, #f6b73c, var(--attention)); transition: height 0.4s; }
.barre.complet { background: linear-gradient(180deg, #34b47e, var(--succes)); }
.jour .nom { font-size: var(--taille-xs); color: var(--texte-doux); text-transform: capitalize; }
.jour.weekend .colonne-barre { background: repeating-linear-gradient(45deg, transparent 0 6px, var(--surface-douce) 6px 12px); }
.jour.futur { opacity: 0.45; }
.erreurs { list-style: none; display: flex; flex-wrap: wrap; gap: 6px; }
.erreurs li { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 999px; background: color-mix(in srgb, var(--rouge) 9%, var(--surface)); color: var(--danger); font-size: var(--taille-xs); font-weight: 600; }
.ok { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-s); color: var(--succes); font-weight: 600; }
/* Équipe */
.resume-equipe, .sous-titre { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-s); font-weight: 600; color: var(--texte-doux); }
.pastille-chiffre { min-width: 30px; padding: 1px 9px; border-radius: 999px; font-weight: 800; font-size: var(--taille-s); text-align: center; }
.pastille-chiffre.ko { background: color-mix(in srgb, var(--rouge) 14%, transparent); color: var(--rouge); }
.pastille-chiffre.att { background: color-mix(in srgb, var(--attention) 16%, transparent); color: var(--attention); }
.pastille-chiffre.ok { background: color-mix(in srgb, var(--succes) 15%, transparent); color: var(--succes); }
.pastille-chiffre.info { background: var(--marine-pale); color: var(--marine); }
.manques { list-style: none; display: flex; flex-direction: column; gap: 6px; }
.manques li { display: grid; grid-template-columns: minmax(0, 1fr) 120px 64px; align-items: center; gap: var(--e3); padding: 4px 6px; border-radius: var(--rayon-s); }
.manques li:hover { background: var(--surface-douce); }
.barre-manque { height: 6px; border-radius: 999px; background: var(--surface-douce); overflow: hidden; }
.barre-manque span { display: block; height: 100%; background: var(--rouge); border-radius: 999px; opacity: 0.75; }
.manque { font-weight: 800; color: var(--rouge); text-align: right; font-size: var(--taille-s); }
/* Planning, alertes, feuilles, contrôles, activité */
.planning { list-style: none; display: flex; flex-direction: column; }
.planning li { display: grid; grid-template-columns: 130px minmax(0, 1fr); align-items: center; gap: var(--e2); padding: 8px 0; border-bottom: 1px solid var(--bordure); }
.planning li:last-child { border-bottom: none; }
.planning li.aujourd .jour-planning { color: var(--rouge); }
.jour-planning { font-size: var(--taille-s); font-weight: 700; color: var(--marine); }
.projets-planning { display: flex; flex-wrap: wrap; gap: 4px; }
.projet-planifie { padding: 2px 8px; border: 1.5px dashed var(--marine); border-radius: 6px; font-size: var(--taille-xs); font-weight: 600; color: var(--marine); }
.alertes, .feuilles, .controles, .activite { list-style: none; display: flex; flex-direction: column; gap: var(--e2); }
.alerte-ligne { display: flex; align-items: center; gap: var(--e3); padding: var(--e2) var(--e3); border-radius: var(--rayon); background: var(--surface-douce); color: var(--texte); text-decoration: none; }
.alerte-ligne.rouge { background: color-mix(in srgb, var(--rouge) 9%, var(--surface)); }
.alerte-ligne.orange { background: color-mix(in srgb, #f59e0b 12%, var(--surface)); }
.pastille-alerte { width: 10px; height: 10px; border-radius: 50%; flex: none; background: #f59e0b; }
.alerte-ligne.rouge .pastille-alerte { background: var(--rouge); }
.texte-alerte { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.feuilles li { display: grid; grid-template-columns: 1fr auto 140px; align-items: center; gap: var(--e3); }
.feuilles a { color: var(--marine); text-decoration: none; }
.controle { display: flex; align-items: center; gap: var(--e3); color: var(--texte); text-decoration: none; font-size: var(--taille-s); }
.activite li { display: flex; gap: var(--e2); font-size: var(--taille-s); }
.point-activite { width: 8px; height: 8px; margin-top: 6px; flex: none; border-radius: 50%; background: var(--marine-clair); }
.nowrap { white-space: nowrap; }
@media (max-width: 1100px) { .chiffres-cles { grid-template-columns: repeat(2, minmax(0, 1fr)); } .colonnes { grid-template-columns: 1fr; } }
</style>
