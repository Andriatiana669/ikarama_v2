<!--
  Ajouter / modifier un pointage.
  Date et heures, puis en cascade : Affaire > Prestation > Projet / Commune > Description, puis la Tâche.
  Un seul choix possible à une étape : il est rempli automatiquement.
  Tâche « Plusieurs descriptions » : on coche plusieurs descriptions du projet, et le temps est
  partagé au prorata de leurs quantités (à parts égales si une quantité manque).
  Si la description est dans une feuille, le temps y est reporté selon le type de la tâche ;
  sinon il est seulement enregistré.
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { pointagesApi } from '@/api'
import type { CreneauxJour, SaisiePointage } from '@/api/pointages'
import { ApiErreur, messageErreur } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { ArborescenceAffaire, Identifiant, Pointage, TacheResume } from '@/types'
import { couleurTexte, formatHeures, formatNombre } from '@/utils/format'
import { calculerPointage } from '@/utils/pointage'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChamp from '@/components/ui/UiChamp.vue'
import UiModale from '@/components/ui/UiModale.vue'
import ChoixAffaire from './ChoixAffaire.vue'

const ouvert = defineModel<boolean>({ default: false })
const props = defineProps<{
  pointage: Pointage | null
  taches: TacheResume[]
  dateParDefaut: string
  /** Suivi (administrateur) : le pointage d'une autre personne, enregistré par cette source */
  source?: { modifier: (id: Identifiant, d: SaisiePointage) => Promise<Pointage> }
}>()
/** Personne pointée : celle du pointage modifié (Suivi), sinon moi */
const employeVise = computed(() => (props.source ? props.pointage?.employe ?? null : null))
const emit = defineEmits<{ enregistre: [] }>()
const toast = useToast()

const LIBELLES_ROLE = { PRODUCTION: 'Employé', CONTROLE: 'Contrôleur', REPRISE: 'Employé reprise' } as const
const COLONNE_COMMENTAIRE = { PRODUCTION: 'Commentaires', CONTROLE: 'Commentaires contrôle', REPRISE: 'Commentaires reprise' } as const

const date = ref('')
const debut = ref('')
const fin = ref('')
const affaire = ref<Identifiant | null>(null)
const prestation = ref<Identifiant | null>(null)
const projet = ref<Identifiant | null>(null)
const choisies = ref<Identifiant[]>([])   // description(s) choisie(s)
const tache = ref<Identifiant | null>(null)
const commentaire = ref('')
const pause = ref(false)

// Créneaux libres du jour : les heures du nouveau pointage sont proposées (et restent modifiables)
const creneaux = ref<CreneauxJour | null>(null)
let heuresTouchees = false
async function chargerCreneaux() {
  if (!date.value) return
  try {
    const reponse = await pointagesApi.creneaux(date.value, { employe: employeVise.value, sauf: props.pointage?.id })
    if (reponse.date !== date.value) return
    creneaux.value = reponse
    if (!props.pointage && !heuresTouchees) {
      debut.value = reponse.suggestion.debut
      fin.value = reponse.suggestion.fin ?? ''
    }
  } catch {
    creneaux.value = null
  }
}
watch(date, () => ouvert.value && chargerCreneaux())
const toucherHeures = () => (heuresTouchees = true)
const libelleAffaire = ref('')
const arbre = ref<ArborescenceAffaire | null>(null)
const chargementArbre = ref(false)
const erreurs = ref<Record<string, any>>({})
const envoi = ref(false)
let initialisation = false

watch(ouvert, async (valeur) => {
  if (!valeur) return
  initialisation = true
  const p = props.pointage
  date.value = p?.date ?? props.dateParDefaut
  debut.value = p?.heure_debut.slice(0, 5) ?? ''
  fin.value = p?.heure_fin.slice(0, 5) ?? ''
  commentaire.value = p?.commentaire ?? ''
  pause.value = p?.pause ?? false
  heuresTouchees = false
  creneaux.value = null
  chargerCreneaux()
  tache.value = p?.tache ?? null
  erreurs.value = {}
  libelleAffaire.value = p ? (p.marche.num_affaire ? `${p.marche.num_affaire} - ${p.marche.nom_affaire}` : p.marche.nom_affaire) : ''
  affaire.value = p?.marche.affaire_id ?? null
  arbre.value = null
  if (affaire.value) await chargerArbre(affaire.value)
  prestation.value = p?.marche.prestation_id ?? prestation.value
  projet.value = p?.marche.projet_id ?? projet.value
  choisies.value = p?.marche.description_ids ?? choisies.value
  await nextTick() // laisse passer les observateurs de la cascade sans rien effacer
  initialisation = false
})

async function chargerArbre(id: Identifiant) {
  chargementArbre.value = true
  try {
    arbre.value = await pointagesApi.arborescence(id, employeVise.value)
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargementArbre.value = false
  }
}

// Cascade : chaque choix remet à zéro la suite ; un seul choix possible -> rempli automatiquement
const prestations = computed(() => arbre.value?.prestations ?? [])
const prestationChoisie = computed(() => prestations.value.find((p) => p.id === prestation.value) ?? null)
const projets = computed(() => prestationChoisie.value?.projets ?? [])
const projetChoisi = computed(() => projets.value.find((p) => p.id === projet.value) ?? null)
const descriptions = computed(() => projetChoisi.value?.descriptions ?? [])
const descriptionChoisie = computed(() =>
  choisies.value.length === 1 ? descriptions.value.find((d) => d.id === choisies.value[0]) ?? null : null,
)
const tacheChoisie = computed(() => props.taches.find((t) => t.id === tache.value) ?? null)

const seul = <T extends { id: Identifiant }>(liste: T[]) => (liste.length === 1 ? liste[0]!.id : null)
watch(affaire, async (id) => {
  if (initialisation) return
  arbre.value = null
  prestation.value = projet.value = null
  choisies.value = []
  if (id) {
    await chargerArbre(id)
    prestation.value = seul(prestations.value)
  }
})
watch(prestation, () => {
  if (initialisation) return
  projet.value = seul(projets.value)
})
watch(projet, () => {
  if (initialisation) return
  const unique = seul(descriptions.value)
  choisies.value = unique ? [unique] : []
})

// Plusieurs descriptions seulement pour une tâche qui le permet
const multiple = computed(() => !!tacheChoisie.value?.plusieurs_descriptions)
watch(multiple, (oui) => {
  if (!oui && choisies.value.length > 1) choisies.value = choisies.value.slice(0, 1)
})
/** Liste déroulante (une seule description) */
const description = computed({
  get: () => choisies.value[0] ?? null,
  set: (id: Identifiant | null) => (choisies.value = id ? [id] : []),
})
function basculer(id: Identifiant) {
  choisies.value = choisies.value.includes(id) ? choisies.value.filter((d) => d !== id) : [...choisies.value, id]
}

/** Aperçu du partage (même règle que le serveur) */
const lignesChoisies = computed(() => descriptions.value.filter((d) => choisies.value.includes(d.id)))
const partage = computed(() => {
  const liste = lignesChoisies.value
  const auProrata = liste.every((d) => d.quantite !== null && Number(d.quantite) > 0)
  const quantites = liste.map((d) => (auProrata ? Number(d.quantite) : 1))
  const total = quantites.reduce((a, b) => a + b, 0) || 1
  return {
    auProrata,
    parts: liste.map((d, i) => ({
      id: d.id,
      part: quantites[i]! / total,
      minutes: tempsCompte.value ? Math.round((tempsCompte.value * quantites[i]!) / total) : null,
    })),
  }
})
const partDe = (id: Identifiant) => partage.value.parts.find((p) => p.id === id) ?? null

/** Descriptions dont la colonne de la tâche est déjà occupée par quelqu'un d'autre */
const occupations = computed(() => {
  const t = tacheChoisie.value
  if (!t || t.type === 'AUTRE') return []
  const type = t.type
  return lignesChoisies.value
    .filter((d) => d.ligne && d.ligne.occupants[type] && !d.ligne.mes_roles.includes(type))
    .map((d) => ({ description: d.nom, occupant: d.ligne!.occupants[type]! }))
})

/** Temps compté (H_Durée + HS, pause retirée) : c'est lui qui est partagé entre les descriptions */
const tempsCompte = computed(() => (apercu.value ? apercu.value.normales + apercu.value.hs : null))
/** Aperçu exact : H_Durée et HS de ce pointage (même règle que le serveur) */
const apercu = computed(() => calculerPointage(date.value, debut.value, fin.value, pause.value))


async function enregistrer() {
  erreurs.value = {}
  if (!affaire.value) erreurs.value.affaire = 'Choisissez l’affaire.'
  else if (!prestation.value) erreurs.value.prestation = 'Choisissez la prestation.'
  else if (!projet.value) erreurs.value.projet = 'Choisissez le projet / la commune.'
  else if (!choisies.value.length) erreurs.value.descriptions = multiple.value ? 'Cochez au moins une description.' : 'Choisissez la description.'
  if (!tache.value) erreurs.value.tache = 'Choisissez la tâche.'
  if (Object.keys(erreurs.value).length) return
  envoi.value = true
  const donnees = {
    date: date.value, heure_debut: debut.value, heure_fin: fin.value, pause: pause.value,
    descriptions: choisies.value, tache: tache.value!, commentaire: commentaire.value,
  }
  try {
    if (props.pointage) await (props.source ?? pointagesApi).modifier(props.pointage.id, donnees)
    else await pointagesApi.creer(donnees)
    toast.succes(props.pointage ? 'Pointage modifié' : 'Pointage ajouté')
    emit('enregistre')
    ouvert.value = false
  } catch (e) {
    if (e instanceof ApiErreur && Object.keys(e.erreurs).length) {
      erreurs.value = e.erreurs
      if (!['date', 'heure_debut', 'heure_fin', 'pause', 'descriptions', 'tache'].some((c) => c in e.erreurs)) erreurs.value.general = e.message
    } else erreurs.value.general = messageErreur(e)
  } finally {
    envoi.value = false
  }
}
const premier = (cle: string) => (Array.isArray(erreurs.value[cle]) ? erreurs.value[cle][0] : erreurs.value[cle])
</script>

<template>
  <UiModale v-model="ouvert" :titre="pointage ? (source ? `Modifier le pointage de ${pointage.employe_details.nom_affiche}` : 'Modifier le pointage') : 'Ajouter un pointage'" taille="moyenne" :bloquante="envoi">
    <form id="form-pointage" class="pile" novalidate @submit.prevent="enregistrer">
      <p v-if="erreurs.general" class="alerte alerte-erreur" role="alert"><i class="bi bi-exclamation-triangle" aria-hidden="true" />{{ erreurs.general }}</p>

      <div class="grille-3">
        <UiChamp v-slot="{ id }" libelle="Date" requis :erreur="premier('date')">
          <input :id="id" v-model="date" class="saisie" type="date" />
        </UiChamp>
        <UiChamp v-slot="{ id }" libelle="H_Début" requis :erreur="premier('heure_debut')">
          <input :id="id" v-model="debut" class="saisie" type="time" step="300" @input="toucherHeures" />
        </UiChamp>
        <UiChamp v-slot="{ id }" libelle="H_Fin" requis :erreur="premier('heure_fin')">
          <input :id="id" v-model="fin" class="saisie" type="time" step="300" @input="toucherHeures" />
        </UiChamp>
      </div>

      <p v-if="creneaux?.ouvrable" class="creneaux texte-xs">
        <i class="bi bi-calendar2-week" aria-hidden="true" />
        <template v-if="creneaux.libres.length">
          Non pointé ce jour (07:30–16:30) :
          <button v-for="c in creneaux.libres" :key="c[0]" type="button" class="creneau" title="Utiliser ce créneau"
            @click="debut = c[0]; fin = c[1]; toucherHeures()">{{ c[0] }}–{{ c[1] }}</button>
        </template>
        <template v-else>Journée 07:30–16:30 entièrement pointée.</template>
      </p>
      <div class="ligne-pause">
        <label class="case">
          <input v-model="pause" type="checkbox" />
          <span><span class="gras">Pause (−1 h)</span>
            <span class="texte-xs texte-doux"> : à cocher sur un seul pointage par jour ouvrable (sinon erreur de pointage)</span></span>
        </label>
        <span v-if="apercu" class="apercu" aria-live="polite">
          H_Durée <span class="gras">{{ formatHeures(apercu.normales) }}</span>
          <template v-if="apercu.hs">, HS <span class="gras hs">{{ formatHeures(apercu.hs) }}</span></template>
          <span v-if="!apercu.ouvrable" class="texte-xs texte-doux"> (week-end : tout en HS)</span>
        </span>
      </div>
      <span v-if="premier('pause')" class="champ-erreur" role="alert">{{ premier('pause') }}</span>

      <UiChamp v-slot="{ id }" libelle="Affaires" requis :erreur="premier('affaire')">
        <ChoixAffaire :id="id" v-model="affaire" :libelle-initial="libelleAffaire" :invalide="!!premier('affaire')" :employe="employeVise" />
      </UiChamp>

      <div class="grille-2">
        <UiChamp v-slot="{ id }" libelle="Prestation" requis :erreur="premier('prestation')"
          :aide="affaire && !chargementArbre && !prestations.length ? 'Aucune prestation cochée pour cette affaire.' : undefined">
          <select :id="id" v-model="prestation" class="saisie" :disabled="!prestations.length">
            <option :value="null" disabled>{{ chargementArbre ? 'Chargement…' : 'Choisir' }}</option>
            <option v-for="p in prestations" :key="p.id" :value="p.id">{{ p.nom }}</option>
          </select>
        </UiChamp>
        <UiChamp v-slot="{ id }" libelle="Projets / Communes" requis :erreur="premier('projet')"
          :aide="prestation && !projets.length ? 'Aucun projet pour cette prestation.' : undefined">
          <select :id="id" v-model="projet" class="saisie" :disabled="!projets.length">
            <option :value="null" disabled>Choisir</option>
            <option v-for="p in projets" :key="p.id" :value="p.id">{{ p.nom }}</option>
          </select>
        </UiChamp>
      </div>

      <UiChamp v-slot="{ id }" libelle="Tâche" requis :erreur="premier('tache')"
        :aide="multiple ? 'Cette tâche permet de cocher plusieurs descriptions du projet : le temps est partagé au prorata des quantités.' : undefined">
        <select :id="id" v-model="tache" class="saisie">
          <option :value="null" disabled>Choisir une tâche</option>
          <option v-for="t in taches" :key="t.id" :value="t.id">{{ t.nom }} ({{ t.type_libelle }}){{ t.plusieurs_descriptions ? ' – plusieurs descriptions' : '' }}</option>
        </select>
      </UiChamp>

      <UiChamp v-if="!multiple" v-slot="{ id }" libelle="Description" requis :erreur="premier('descriptions')"
        :aide="projet && !descriptions.length ? 'Aucune description pour ce projet.' : undefined">
        <select :id="id" v-model="description" class="saisie" :disabled="!descriptions.length">
          <option :value="null" disabled>Choisir</option>
          <option v-for="d in descriptions" :key="d.id" :value="d.id">
            {{ d.nom }} ({{ formatNombre(d.quantite) }} {{ prestationChoisie?.unite }}){{ d.ligne ? ` – ${d.ligne.feuille}` : ' – hors feuille' }}
          </option>
        </select>
      </UiChamp>
      <div v-else class="champ">
        <span class="champ-libelle">Descriptions <span class="requis">*</span></span>
        <span v-if="premier('descriptions')" class="champ-erreur" role="alert">{{ premier('descriptions') }}</span>
        <p v-if="!projet" class="texte-xs texte-doux">Choisissez d'abord l'affaire, la prestation et le projet.</p>
        <p v-else-if="!descriptions.length" class="texte-xs texte-doux">Aucune description pour ce projet.</p>
        <ul v-else class="multiples">
          <li v-for="d in descriptions" :key="d.id">
            <label class="case">
              <input type="checkbox" :checked="choisies.includes(d.id)" @change="basculer(d.id)" />
              <span class="gras">{{ d.nom }}</span>
              <span class="texte-xs texte-doux">{{ formatNombre(d.quantite) }} {{ prestationChoisie?.unite }}{{ d.ligne ? `, ${d.ligne.feuille}` : ', hors feuille' }}</span>
            </label>
            <span v-if="partDe(d.id)" class="part">
              {{ Math.round(partDe(d.id)!.part * 100) }} %<template v-if="partDe(d.id)!.minutes"> ({{ formatHeures(partDe(d.id)!.minutes!) }})</template>
            </span>
          </li>
        </ul>
        <p v-if="choisies.length > 1 && !partage.auProrata" class="texte-xs attention">
          <i class="bi bi-exclamation-circle" aria-hidden="true" /> Une description n'a pas de quantité : le temps est partagé à parts égales.
        </p>
      </div>

      <div v-if="descriptionChoisie" class="info-ligne">
        <template v-if="descriptionChoisie.ligne">
          <i class="bi bi-file-earmark-spreadsheet" aria-hidden="true" />
          <span>Feuille <span class="gras">{{ descriptionChoisie.ligne.feuille }}</span>, ligne {{ descriptionChoisie.ligne.numero }}</span>
          <span v-if="descriptionChoisie.ligne.statut" class="pastille"
            :style="{ background: descriptionChoisie.ligne.statut.couleur, color: couleurTexte(descriptionChoisie.ligne.statut.couleur) }">
            {{ descriptionChoisie.ligne.statut.nom }}
          </span>
          <span v-for="r in descriptionChoisie.ligne.mes_roles" :key="r" class="badge badge-marine">{{ LIBELLES_ROLE[r as keyof typeof LIBELLES_ROLE] }}</span>
        </template>
        <template v-else>
          <i class="bi bi-info-circle" aria-hidden="true" />
          <span>Cette description n'est dans aucune feuille : le temps sera enregistré, mais pas reporté.</span>
        </template>
      </div>

      <p v-if="occupations.length" class="alerte alerte-erreur" role="alert">
        <i class="bi bi-lock-fill" aria-hidden="true" />
        <span>
          <template v-for="(o, i) in occupations" :key="o.description">{{ i ? ' ; ' : '' }}« {{ o.description }} » : {{ o.occupant }} est déjà placé(e)</template>
          comme « {{ LIBELLES_ROLE[tacheChoisie!.type as keyof typeof LIBELLES_ROLE] }} ». Cette tâche ne peut pas y être pointée.
        </span>
      </p>
      <p v-else-if="tacheChoisie && tacheChoisie.type !== 'AUTRE' && lignesChoisies.some((d) => d.ligne)" class="texte-xs texte-doux">
        Le temps sera reporté dans la colonne « {{ LIBELLES_ROLE[tacheChoisie.type as keyof typeof LIBELLES_ROLE] }} » de la feuille,
        et le commentaire dans « {{ COLONNE_COMMENTAIRE[tacheChoisie.type as keyof typeof COLONNE_COMMENTAIRE] }} ».
      </p>

      <UiChamp v-slot="{ id }" libelle="Commentaire">
        <textarea :id="id" v-model="commentaire" class="saisie" rows="2" />
      </UiChamp>
    </form>
    <template #pied>
      <UiBouton :desactive="envoi" @click="ouvert = false">Annuler</UiBouton>
      <UiBouton variante="primaire" type="submit" form="form-pointage" :chargement="envoi" :desactive="!!occupations.length">Enregistrer</UiBouton>
    </template>
  </UiModale>
</template>

<style scoped>
.info-ligne { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; padding: var(--e2) var(--e3); border-radius: var(--rayon); background: var(--surface-douce); font-size: var(--taille-s); }
.creneaux { display: flex; align-items: center; gap: var(--e1); flex-wrap: wrap; color: var(--texte-doux); margin-top: calc(-1 * var(--e2)); }
.creneau { padding: 1px 8px; border: 1px dashed var(--marine-clair); border-radius: 999px; background: none; color: var(--marine); font-size: var(--taille-xs); font-weight: 600; cursor: pointer; }
.creneau:hover { background: var(--marine-pale); }
.ligne-pause { display: flex; align-items: center; justify-content: space-between; gap: var(--e3); flex-wrap: wrap; padding: var(--e2) var(--e3); border-radius: var(--rayon); background: var(--surface-douce); }
.apercu { font-size: var(--taille-s); color: var(--marine); white-space: nowrap; }
.apercu .hs { color: var(--attention); }
.multiples { list-style: none; display: flex; flex-direction: column; border: 1px solid var(--bordure); border-radius: var(--rayon); max-height: 220px; overflow-y: auto; }
.multiples li { display: flex; align-items: center; gap: var(--e2); padding: var(--e2) var(--e3); border-bottom: 1px solid var(--bordure); font-size: var(--taille-s); }
.multiples li:last-child { border-bottom: none; }
.multiples .case { flex: 1; gap: var(--e2); }
.part { font-weight: 700; color: var(--marine); white-space: nowrap; }
.attention { color: var(--attention); }
.pastille { padding: 1px 8px; border-radius: 999px; font-size: var(--taille-xs); font-weight: 600; }
</style>
