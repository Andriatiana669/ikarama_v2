<!--
  Pointages regroupés par jour, en deux modes :
    mien : Pointages > Mon temps (mes pointages ; ajouter, importer, modifier, supprimer)
    tous : Pointages > Suivi (superadmins : tout le monde ; filtres ; modifier, supprimer)
  H_Durée et HS sont calculés par le serveur (pointages/calculs.py) ; le temps est reporté
  automatiquement dans les feuilles selon le type de la tâche.
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { pointagesApi, suiviPointagesApi, utilisateursApi } from '@/api'
import { useColonnes } from '@/composables/useColonnes'
import { useConfirmation } from '@/composables/useConfirmation'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/store/auth'
import type { Colonne, Identifiant, Pointage, ResumePointage, TacheResume } from '@/types'
import { formatHeure, formatHeures, formatJourLong, formatNombre } from '@/utils/format'
import { creneauxLibres } from '@/utils/pointage'

const estOuvrable = (date: string) => {
  const jour = new Date(`${date}T12:00:00`).getDay()
  return jour >= 1 && jour <= 5
}
import FormulairePointage from '@/components/pointages/FormulairePointage.vue'
import SelectEmploye from '@/components/formulaires/SelectEmploye.vue'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import ImportExcel from '@/components/ui/ImportExcel.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'
import UiMenuDeroulant from '@/components/ui/UiMenuDeroulant.vue'
import UiRecherche from '@/components/ui/UiRecherche.vue'

const props = withDefaults(defineProps<{ mode?: 'mien' | 'tous' }>(), { mode: 'mien' })
const tous = props.mode === 'tous'
const source = tous ? suiviPointagesApi : pointagesApi

const auth = useAuthStore()
const toast = useToast()
const { confirmer } = useConfirmation()

// Période : du lundi de la semaine à aujourd'hui
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const aujourdhui = new Date()
const lundi = new Date(aujourdhui)
lundi.setDate(aujourdhui.getDate() - ((aujourdhui.getDay() + 6) % 7))
const debut = ref(iso(lundi))
const fin = ref(iso(aujourdhui))

const pointages = ref<Pointage[]>([])
const resume = ref<(ResumePointage & { nb_personnes?: number }) | null>(null)

// Suivi : filtres par personne, pôle et tâche
const filtreEmploye = ref<Identifiant | null>(null)
const filtrePole = ref('')
const filtreTache = ref<Identifiant | ''>('')
const poles = ref<string[]>([])
const parametres = () => ({
  debut: debut.value, fin: fin.value,
  ...(tous ? { employe: filtreEmploye.value ?? '', pole: filtrePole.value, tache: filtreTache.value } : {}),
})
const taches = ref<TacheResume[]>([])
const chargement = ref(false)
const recherche = ref('')

async function charger() {
  if (debut.value > fin.value) return toast.erreur('La date de début doit être avant la date de fin.')
  chargement.value = true
  try {
    ;[pointages.value, resume.value] = await Promise.all([
      source.tous(parametres()),
      tous ? suiviPointagesApi.resume(parametres()) : pointagesApi.resume(debut.value, fin.value),
    ])
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargement.value = false
  }
}
onMounted(async () => {
  charger()
  taches.value = await pointagesApi.taches()
  if (tous) poles.value = (await utilisateursApi.valeursFiltres()).poles ?? []
})

// En-tête : pôle > nom
const pole = computed(() => auth.employe?.postes?.[0]?.pole || '—')
const nomComplet = computed(() => (auth.employe ? `${auth.employe.nom.toUpperCase()} ${auth.employe.prenom}` : auth.nomAffiche))

// Colonnes (bouton « Colonnes »)
const colonnes: Colonne[] = [
  { cle: 'employe', libelle: 'Employé', cleExport: 'employe_details.identifiant' },
  { cle: 'heure_debut', libelle: 'H_Début' },
  { cle: 'heure_fin', libelle: 'H_Fin' },
  { cle: 'minutes_normales', libelle: 'H_Durée' },
  { cle: 'minutes_hs', libelle: 'HS' },
  { cle: 'pause', libelle: 'Pause' },
  { cle: 'num_affaire', libelle: 'Num affaire', cleExport: 'marche.num_affaire' },
  { cle: 'nom_affaire', libelle: 'Nom affaire', cleExport: 'marche.nom_affaire' },
  { cle: 'prestation', libelle: 'Prestation', cleExport: 'marche.prestation' },
  { cle: 'projet', libelle: 'Projet / Commune', cleExport: 'marche.projet' },
  { cle: 'description', libelle: 'Description', cleExport: 'marche.description' },
  { cle: 'tache', libelle: 'Tâche', cleExport: 'tache_details.nom' },
  { cle: 'quantite', libelle: 'Quantité', cleExport: 'marche.quantite' },
  { cle: 'unite', libelle: 'Unité', cleExport: 'marche.unite' },
  { cle: 'commentaire', libelle: 'Commentaire' },
]
const affichage = useColonnes(tous ? 'suivi-pointages' : 'mon-temps', () => colonnes)
const visible = (cle: string) => !affichage.masquees.value.includes(cle)
const menuColonnes = ref(false)
const boutonColonnes = ref<{ $el: HTMLElement } | null>(null)

// Regroupement par jour (avec la recherche)
const jours = computed(() => {
  const t = recherche.value.toLowerCase()
  const filtres = pointages.value.filter((p) =>
    !t || [p.marche.num_affaire, p.marche.nom_affaire, p.marche.prestation, p.marche.projet, p.marche.description, p.tache_details.nom, p.commentaire]
      .join(' ').toLowerCase().includes(t),
  )
  const groupes = new Map<string, Pointage[]>()
  for (const p of filtres) groupes.set(p.date, [...(groupes.get(p.date) ?? []), p])
  return [...groupes.entries()].map(([date, liste]) => ({
    date,
    liste,
    minutes: liste.reduce((s, p) => s + p.minutes_normales + p.minutes_hs, 0),
    hs: liste.reduce((s, p) => s + p.minutes_hs, 0),
    // Mon temps : créneaux non pointés de 07:30–16:30 (jours ouvrables) ; Suivi : plusieurs personnes, sans objet
    libres: !tous && estOuvrable(date) ? creneauxLibres(liste) : [],
  }))
})

// Export Excel de la période
const exportEnCours = ref(false)
async function exporter() {
  exportEnCours.value = true
  try {
    await source.exporter(
      { ...parametres(), search: recherche.value },
      colonnes.filter((c) => visible(c.cle)).map((c) => ({ cle: (c.cleExport as string) || c.cle, libelle: c.libelle })),
      `${tous ? 'Suivi' : 'Pointages'} ${debut.value} au ${fin.value}`,
    )
  } catch (e) {
    toast.erreur(e)
  } finally {
    exportEnCours.value = false
  }
}

// Ajout / modification / suppression
const formulaire = ref(false)
const importOuvert = ref(false)
const enCours = ref<Pointage | null>(null)
function ouvrir(p: Pointage | null = null) {
  enCours.value = p
  formulaire.value = true
}
async function supprimer(p: Pointage) {
  const ok = await confirmer({
    titre: 'Supprimer ce pointage ?',
    message: `${tous ? `${p.employe_details.nom_affiche}, ` : ''}${formatJourLong(p.date)}, ${formatHeure(p.heure_debut)}–${formatHeure(p.heure_fin)} : le temps sera retiré de la feuille.`,
    libelleConfirmer: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  try {
    await source.supprimer(p.id)
    toast.succes('Pointage supprimé')
    charger()
  } catch (e) {
    toast.erreur(e)
  }
}
/** « Ménages : 2,85 h (71 %), Bâtiments : 1,15 h (29 %) » */
const detailParts = (p: Pointage) =>
  p.parts.map((x) => `${x.description} : ${formatHeures(x.minutes)} (${Math.round(Number(x.part) * 100)} %)`).join(', ')

const totalMinutes = computed(() => (resume.value ? resume.value.minutes_normales + resume.value.minutes_hs : 0))
</script>

<template>
  <div class="page page-large pile">
    <EnTetePage v-if="tous" titre="Suivi des pointages"
      description="Les pointages de toutes les personnes ayant accès au site. Une modification respecte les règles de la personne pointée." />
    <h1 v-else class="fil">PÔLE : {{ pole }} <i class="bi bi-chevron-right" aria-hidden="true" /> {{ nomComplet }}</h1>

    <div class="barre carte">
      <label class="date"><span>Début</span><input v-model="debut" class="saisie" type="date" /></label>
      <label class="date"><span>Fin</span><input v-model="fin" class="saisie" type="date" /></label>
      <UiBouton icone="arrow-clockwise" :chargement="chargement" @click="charger">Actualiser</UiBouton>
      <template v-if="tous">
        <label class="date employe"><span>Employé</span><SelectEmploye v-model="filtreEmploye" placeholder="Tout le monde" /></label>
        <label class="date"><span>Pôle</span>
          <select v-model="filtrePole" class="saisie"><option value="">Tous</option><option v-for="p in poles" :key="p" :value="p">{{ p }}</option></select>
        </label>
        <label class="date"><span>Tâche</span>
          <select v-model="filtreTache" class="saisie"><option value="">Toutes</option><option v-for="t in taches" :key="t.id" :value="t.id">{{ t.nom }}</option></select>
        </label>
      </template>
      <span class="espace" />
      <template v-if="!tous">
        <UiBouton variante="primaire" icone="plus-lg" @click="ouvrir()">Ajouter</UiBouton>
        <UiBouton icone="file-earmark-arrow-up" @click="importOuvert = true">Importer</UiBouton>
      </template>
    </div>

    <section class="carte panneau">
      <div class="outils">
        <UiBouton ref="boutonColonnes" variante="fantome" petit icone="layout-three-columns" @click="menuColonnes = !menuColonnes">Colonnes</UiBouton>
        <UiMenuDeroulant v-model="menuColonnes" :ancre="boutonColonnes?.$el ?? null">
          <div class="menu-colonnes">
            <label v-for="c in colonnes" :key="c.cle" class="case">
              <input type="checkbox" :checked="visible(c.cle)" @change="affichage.basculer(c.cle)" /> {{ c.libelle }}
            </label>
          </div>
        </UiMenuDeroulant>
        <UiBouton v-if="!tous || auth.peut('exporter', 'pointages_suivi')" variante="fantome" petit icone="download" :chargement="exportEnCours" @click="exporter">Exporter</UiBouton>
        <UiRecherche v-model="recherche" class="recherche" placeholder="Rechercher" />
      </div>

      <UiChargement v-if="chargement && !pointages.length" />
      <UiEtatVide v-else-if="!jours.length" icone="stopwatch" titre="Aucun pointage sur cette période"
        :texte="tous ? 'Modifiez la période ou les filtres, puis « Actualiser ».' : 'Cliquez sur « Ajouter » pour pointer votre temps.'">
        <UiBouton v-if="!tous" variante="primaire" icone="plus-lg" @click="ouvrir()">Ajouter</UiBouton>
      </UiEtatVide>
      <div v-else class="tableau-conteneur">
        <table class="tableau">
          <thead>
            <tr>
              <th class="col-action">Action</th>
              <th v-for="c in colonnes.filter((c) => visible(c.cle))" :key="c.cle">{{ c.libelle }}</th>
            </tr>
          </thead>
          <tbody v-for="jour in jours" :key="jour.date" class="jour">
            <tr class="titre-jour">
              <td :colspan="1 + affichage.visibles.value.length">
                <span class="etiquette">
                  {{ formatJourLong(jour.date) }} <span class="separateur" /> {{ formatHeures(jour.minutes) }}
                  <span v-if="jour.hs" class="badge badge-attention">dont {{ formatHeures(jour.hs) }} HS</span>
                  <span v-if="jour.libres.length" class="non-pointe" title="Créneaux de 07:30–16:30 sans pointage (la pause peut en faire partie)">
                    <i class="bi bi-hourglass-split" aria-hidden="true" /> Non pointé : {{ jour.libres.map((c) => `${c[0]}–${c[1]}`).join(', ') }}
                  </span>
                </span>
              </td>
            </tr>
            <tr v-for="p in jour.liste" :key="p.id">
              <td class="col-action">
                <UiBouton v-if="!tous || auth.peut('modifier', 'pointages_suivi')" variante="fantome" icone="pencil" petit icone-seule @click="ouvrir(p)">Modifier</UiBouton>
                <UiBouton v-if="!tous || auth.peut('supprimer', 'pointages_suivi')" variante="fantome" icone="trash" petit icone-seule @click="supprimer(p)">Supprimer</UiBouton>
              </td>
              <td v-if="visible('employe')"><UiEmploye :employe="p.employe_details" sans-matricule /></td>
              <td v-if="visible('heure_debut')" class="heure">{{ formatHeure(p.heure_debut) }}</td>
              <td v-if="visible('heure_fin')" class="heure">{{ formatHeure(p.heure_fin) }}</td>
              <td v-if="visible('minutes_normales')" class="gras">{{ formatHeures(p.minutes_normales) }}</td>
              <td v-if="visible('minutes_hs')"><span :class="{ hs: p.minutes_hs }">{{ p.minutes_hs ? formatHeures(p.minutes_hs) : '—' }}</span></td>
              <td v-if="visible('pause')"><span v-if="p.pause" class="badge" title="Pause d'une heure retirée">−1 h</span><span v-else class="texte-doux">—</span></td>
              <td v-if="visible('num_affaire')">{{ p.marche.num_affaire || '—' }}</td>
              <td v-if="visible('nom_affaire')">{{ p.marche.nom_affaire }}</td>
              <td v-if="visible('prestation')">{{ p.marche.prestation }}</td>
              <td v-if="visible('projet')">{{ p.marche.projet }}</td>
              <td v-if="visible('description')" class="gras" :title="p.parts.length > 1 ? detailParts(p) : undefined">
                {{ p.marche.description }}
                <span v-if="p.parts.length > 1" class="badge" :title="detailParts(p)">{{ p.parts.length }} descriptions</span>
              </td>
              <td v-if="visible('tache')"><span class="badge">{{ p.tache_details.nom }}</span></td>
              <td v-if="visible('quantite')" class="droite">{{ formatNombre(p.marche.quantite) }}</td>
              <td v-if="visible('unite')">{{ p.marche.unite }}</td>
              <td v-if="visible('commentaire')" class="commentaire" :title="p.commentaire">{{ p.commentaire || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="cartes">
      <div class="carte carte-corps indicateur">
        <span class="libelle">Total lignes</span>
        <span class="valeur">{{ resume?.nb_lignes ?? '—' }}</span>
      </div>
      <div class="carte carte-corps indicateur">
        <span class="libelle">Total heures</span>
        <span class="valeur">{{ formatHeures(totalMinutes) }}</span>
        <span class="texte-xs texte-doux">dont {{ formatHeures(resume?.minutes_normales ?? 0) }} de H_Durée</span>
      </div>
      <div class="carte carte-corps indicateur">
        <span class="libelle">Heures supp</span>
        <span class="valeur" :class="{ hs: resume?.minutes_hs }">{{ formatHeures(resume?.minutes_hs ?? 0) }}</span>
      </div>
      <div v-if="tous" class="carte carte-corps indicateur">
        <span class="libelle">Personnes</span>
        <span class="valeur">{{ resume?.nb_personnes ?? '—' }}</span>
        <span class="texte-xs texte-doux">Manques par jour : Pointages > Vérification</span>
      </div>
      <div v-else class="carte carte-corps indicateur erreurs" :class="{ alerte: resume?.erreurs.length }">
        <span class="libelle">Erreurs de pointage</span>
        <p v-if="!resume?.erreurs.length" class="texte-petit texte-doux"><i class="bi bi-check-circle" aria-hidden="true" /> Aucune erreur</p>
        <ul v-else class="liste-erreurs">
          <li v-for="e in resume.erreurs" :key="e.date"><i class="bi bi-exclamation-circle" aria-hidden="true" /> {{ e.message }}</li>
        </ul>
      </div>
    </section>

    <ImportExcel v-if="!tous" v-model="importOuvert" titre="Importer des pointages" nom-modele="Modele_import_pointages" :source="pointagesApi" @importe="charger" />
    <FormulairePointage v-model="formulaire" :pointage="enCours" :taches="taches" :date-par-defaut="fin"
      :source="tous ? suiviPointagesApi : undefined" @enregistre="charger" />
  </div>
</template>

<style scoped>
.page-large { max-width: none; }
.fil { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-l); }
.fil .bi { font-size: 0.8rem; color: var(--texte-leger); }
.barre { display: flex; align-items: flex-end; gap: var(--e3); flex-wrap: wrap; padding: var(--e3) var(--e4); }
.date { display: flex; flex-direction: column; gap: 2px; font-size: var(--taille-xs); color: var(--texte-doux); }
.date .saisie { width: 160px; height: 36px; }
.date.employe { min-width: 240px; }
.date.employe :deep(.saisie) { width: 100%; }
.espace { flex: 1; }
.panneau { overflow: hidden; }
.outils { display: flex; align-items: center; gap: var(--e1); padding: var(--e2) var(--e3); border-bottom: 1px solid var(--bordure); background: var(--surface-douce); }
.recherche { margin-left: auto; min-width: 160px; max-width: 260px; }
.recherche :deep(.saisie) { height: 32px; }
.menu-colonnes { display: flex; flex-direction: column; gap: var(--e2); padding: var(--e2) var(--e3); font-size: var(--taille-s); }
thead th { background: var(--marine); color: #fff; }
.tableau { font-size: var(--taille-s); }
.tableau td, .tableau th { white-space: nowrap; padding: var(--e2) var(--e3); }
.col-action { width: 1%; }
.titre-jour td { padding: var(--e4) var(--e3) var(--e2); background: var(--surface) !important; border-bottom: none; }
.etiquette { display: inline-flex; align-items: center; gap: var(--e3); font-weight: 600; color: var(--marine); }
.non-pointe { display: inline-flex; align-items: center; gap: 4px; padding: 1px 8px; border: 1px dashed var(--attention); border-radius: 999px; color: var(--attention); font-size: var(--taille-xs); font-weight: 600; }
.separateur { width: 1px; height: 14px; background: var(--bordure-forte); }
.jour tr:not(.titre-jour) td:first-child { box-shadow: inset 3px 0 0 var(--marine-pale); }
.heure { font-variant-numeric: tabular-nums; }
.hs { color: var(--attention); font-weight: 600; }
.commentaire { max-width: 240px; overflow: hidden; text-overflow: ellipsis; }
.cartes { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(0, 1.4fr); gap: var(--e4); }
.indicateur { display: flex; flex-direction: column; gap: var(--e1); }
.indicateur .libelle { font-size: var(--taille-s); color: var(--texte-doux); font-weight: 600; }
.indicateur .valeur { font-size: var(--taille-xxl); font-weight: 700; color: var(--marine); }
.erreurs.alerte { border-color: var(--rouge); }
.liste-erreurs { list-style: none; display: flex; flex-direction: column; gap: 4px; font-size: var(--taille-s); color: var(--danger); max-height: 120px; overflow-y: auto; }
@media (max-width: 1100px) { .cartes { grid-template-columns: 1fr 1fr; } }
</style>
