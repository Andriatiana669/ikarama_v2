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
  /** Dupliquer : un nouveau pointage prérempli avec celui-ci (même date et mêmes heures, à changer) */
  modele?: Pointage | null
}>()
/** Pointage dont les valeurs remplissent le formulaire : celui modifié, ou le modèle à dupliquer */
const depart = computed(() => props.pointage ?? props.modele ?? null)
/** Personne pointée : celle du pointage modifié ou dupliqué (Suivi), sinon moi */
const employeVise = computed(() => (props.source ? depart.value?.employe ?? null : null))
const emit = defineEmits<{ enregistre: [] }>()
const toast = useToast()

const LIBELLES_ROLE = { PRODUCTION: 'Employé', CONTROLE: 'Contrôleur', REPRISE: 'Employé reprise' } as const
const COLONNE_COMMENTAIRE = { PRODUCTION: 'Commentaires', CONTROLE: 'Commentaires contrôle', REPRISE: 'Commentaires reprise' } as const

const date = ref('')
const debut = ref('')
const fin = ref('')
const affaire = ref<Identifiant | null>(null)
const nomProjet = ref<string | null>(null)   // Projet / Commune choisi par son nom (avant la prestation)
const prestation = ref<Identifiant | null>(null)
const projet = ref<Identifiant | null>(null)
const quantites = ref<Record<string, string>>({})   // quantités affichées (modifiables) des descriptions choisies
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
  const p = depart.value
  date.value = p?.date ?? props.dateParDefaut
  debut.value = p?.heure_debut.slice(0, 5) ?? ''
  fin.value = p?.heure_fin.slice(0, 5) ?? ''
  commentaire.value = p?.commentaire ?? ''
  pause.value = p?.pause ?? false
  heuresTouchees = !!props.modele   // Dupliquer : on garde les heures du modèle
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
  nomProjet.value = p ? (tousLesProjets.value.find((x) => x.id === projet.value)?.nom ?? null) : nomProjet.value
  choisies.value = p?.marche.description_ids ?? choisies.value
  quantites.value = {}
  lineaires.value = {}
  remplirQuantites()
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

// Cascade : Affaire -> Projet / Commune -> Prestation -> Description(s).
// Une même commune peut exister sous plusieurs prestations : la liste montre chaque nom une fois, puis la prestation
// propose celles qui ont cette commune (remplie automatiquement s'il n'y en a qu'une). Un seul choix -> rempli.
const prestations = computed(() => arbre.value?.prestations ?? [])
const tousLesProjets = computed(() => prestations.value.flatMap((pr) => pr.projets.map((p) => ({ ...p, prestation_id: pr.id }))))
const cle = (nom: string) => nom.trim().toLowerCase()
const nomsProjets = computed(() => {
  const vus = new Map<string, string>()
  tousLesProjets.value.forEach((p) => vus.has(cle(p.nom)) || vus.set(cle(p.nom), p.nom))
  return [...vus.values()]
})
const projetsDuNom = computed(() => (nomProjet.value ? tousLesProjets.value.filter((p) => cle(p.nom) === cle(nomProjet.value!)) : []))
const prestationsDuProjet = computed(() => prestations.value.filter((pr) => projetsDuNom.value.some((p) => p.prestation_id === pr.id)))
const prestationChoisie = computed(() => prestations.value.find((p) => p.id === prestation.value) ?? null)
const projetChoisi = computed(() => tousLesProjets.value.find((p) => p.id === projet.value) ?? null)
const descriptions = computed(() => projetChoisi.value?.descriptions ?? [])
const descriptionChoisie = computed(() =>
  choisies.value.length === 1 ? descriptions.value.find((d) => d.id === choisies.value[0]) ?? null : null,
)
const tacheChoisie = computed(() => props.taches.find((t) => t.id === tache.value) ?? null)

const seul = <T extends { id: Identifiant }>(liste: T[]) => (liste.length === 1 ? liste[0]!.id : null)
watch(affaire, async (id) => {
  if (initialisation) return
  arbre.value = null
  nomProjet.value = null
  prestation.value = projet.value = null
  choisies.value = []
  if (id) {
    await chargerArbre(id)
    if (nomsProjets.value.length === 1) nomProjet.value = nomsProjets.value[0]!
  }
})
watch(nomProjet, () => {
  if (initialisation) return
  prestation.value = seul(prestationsDuProjet.value)
  projet.value = prestation.value ? projetsDuNom.value.find((p) => p.prestation_id === prestation.value)?.id ?? null : null
})
watch(prestation, (id) => {
  if (initialisation) return
  projet.value = id ? projetsDuNom.value.find((p) => p.prestation_id === id)?.id ?? null : null
})
watch(projet, () => {
  if (initialisation) return
  const unique = seul(descriptions.value)
  choisies.value = unique ? [unique] : []
})

// Report DT : on saisit la quantité linéaire ; Quantité = Quantité linéaire × Surface ÷ Linéaire total (somme du projet)
const reportDt = computed(() => !!arbre.value?.report_dt)
const lineaires = ref<Record<string, string>>({})
const nombre = (v: string | null | undefined) => (v === null || v === undefined || String(v).trim() === '' ? null : Number(String(v).replace(',', '.')))
const arrondi2 = (v: number) => Math.round(v * 100) / 100
const lineaireDe = (d: { id: Identifiant; quantite_lineaire?: string | null }) =>
  String(d.id) in lineaires.value ? lineaires.value[String(d.id)]! : d.quantite_lineaire ?? ''
/** Linéaire total du projet avec les valeurs saisies (aperçu, même règle que le serveur) */
const lineaireTotal = computed(() => descriptions.value.reduce((t, d) => t + (nombre(lineaireDe(d)) ?? 0), 0))
function quantiteCalculee(d: { id: Identifiant; quantite_lineaire?: string | null }) {
  const ql = nombre(lineaireDe(d))
  const surface = nombre(projetChoisi.value?.surface_m2 ?? null)
  if (ql === null || surface === null || !lineaireTotal.value) return null
  return arrondi2((ql * surface) / lineaireTotal.value)
}
const lineairesModifies = () => {
  const changes: Record<string, string> = {}
  for (const d of descriptions.value) {
    if (!choisies.value.includes(d.id) || !d.quantite_modifiable || !(String(d.id) in lineaires.value)) continue
    const v = String(lineaires.value[String(d.id)] ?? '').replace(',', '.').trim()
    if ((nombre(v) ?? null) !== (nombre(d.quantite_lineaire ?? null) ?? null)) changes[String(d.id)] = v
  }
  return changes
}

// Quantité des descriptions choisies : affichée et modifiable (droit « Pointages > Quantité des descriptions »)
function remplirQuantites() {
  for (const d of descriptions.value) {
    if (choisies.value.includes(d.id) && !(String(d.id) in lineaires.value) && d.quantite_lineaire !== undefined)
      lineaires.value[String(d.id)] = d.quantite_lineaire === null ? '' : String(Number(d.quantite_lineaire))
    // « 6000.00 » s'affiche « 6000 »
    if (choisies.value.includes(d.id) && !(String(d.id) in quantites.value)) quantites.value[String(d.id)] = d.quantite === null ? '' : String(Number(d.quantite))
  }
}
watch(choisies, remplirQuantites, { deep: true })
const quantiteDe = (d: { id: Identifiant; quantite: string | null; quantite_lineaire?: string | null }) => {
  if (reportDt.value) return quantiteCalculee(d)?.toString() ?? ''
  return quantites.value[String(d.id)] ?? d.quantite ?? ''
}
const quantitesModifiees = () => {
  const changes: Record<string, string> = {}
  for (const d of descriptions.value) {
    if (reportDt.value || !choisies.value.includes(d.id) || !d.quantite_modifiable) continue
    const v = (quantites.value[String(d.id)] ?? '').toString().replace(',', '.').trim()
    if (v !== '' && Number(v) !== Number(d.quantite ?? NaN)) changes[String(d.id)] = v
  }
  return changes
}

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
function toutCocher(oui: boolean) {
  choisies.value = oui ? descriptions.value.map((d) => d.id) : []
}
function basculer(id: Identifiant) {
  choisies.value = choisies.value.includes(id) ? choisies.value.filter((d) => d !== id) : [...choisies.value, id]
}

/** Aperçu du partage (même règle que le serveur) */
const lignesChoisies = computed(() => descriptions.value.filter((d) => choisies.value.includes(d.id)))
const partage = computed(() => {
  const liste = lignesChoisies.value
  const auProrata = liste.every((d) => quantiteDe(d) !== '' && Number(String(quantiteDe(d)).replace(',', '.')) > 0)
  const valeurs = liste.map((d) => (auProrata ? Number(String(quantiteDe(d)).replace(',', '.')) : 1))
  const total = valeurs.reduce((a, b) => a + b, 0) || 1
  return {
    auProrata,
    parts: liste.map((d, i) => ({
      id: d.id,
      part: valeurs[i]! / total,
      minutes: tempsCompte.value ? Math.round((tempsCompte.value * valeurs[i]!) / total) : null,
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
  else if (!nomProjet.value) erreurs.value.projet = 'Choisissez le projet / la commune.'
  else if (!prestation.value || !projet.value) erreurs.value.prestation = 'Choisissez la prestation.'
  else if (!choisies.value.length) erreurs.value.descriptions = multiple.value ? 'Cochez au moins une description.' : 'Choisissez la description.'
  if (!tache.value) erreurs.value.tache = 'Choisissez la tâche.'
  if (Object.keys(erreurs.value).length) return
  envoi.value = true
  const donnees = {
    date: date.value, heure_debut: debut.value, heure_fin: fin.value, pause: pause.value,
    descriptions: choisies.value, tache: tache.value!, commentaire: commentaire.value,
    ...(Object.keys(quantitesModifiees()).length ? { quantites: quantitesModifiees() } : {}),
    ...(reportDt.value && Object.keys(lineairesModifies()).length ? { quantites_lineaires: lineairesModifies() } : {}),
  }
  try {
    if (props.pointage) await (props.source ?? pointagesApi).modifier(props.pointage.id, donnees)
    else if (props.source && employeVise.value) await pointagesApi.creerPour(donnees, employeVise.value)   // dupliqué dans le Suivi
    else await pointagesApi.creer(donnees)
    toast.succes(props.pointage ? 'Pointage modifié' : props.modele ? 'Pointage dupliqué' : 'Pointage ajouté')
    emit('enregistre')
    ouvert.value = false
  } catch (e) {
    if (e instanceof ApiErreur && Object.keys(e.erreurs).length) {
      erreurs.value = e.erreurs
      if (!['date', 'heure_debut', 'heure_fin', 'pause', 'descriptions', 'tache', 'quantites'].some((c) => c in e.erreurs)) erreurs.value.general = e.message
    } else erreurs.value.general = messageErreur(e)
  } finally {
    envoi.value = false
  }
}
const premier = (cle: string) => (Array.isArray(erreurs.value[cle]) ? erreurs.value[cle][0] : erreurs.value[cle])
</script>

<template>
  <UiModale v-model="ouvert" :titre="pointage ? (source ? `Modifier le pointage de ${pointage.employe_details.nom_affiche}` : 'Modifier le pointage')
      : modele ? (source ? `Dupliquer un pointage de ${modele.employe_details.nom_affiche}` : 'Dupliquer un pointage') : 'Ajouter un pointage'" taille="moyenne" :bloquante="envoi">
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
        <UiChamp v-slot="{ id }" libelle="Projets / Communes" requis :erreur="premier('projet')"
          :aide="affaire && !chargementArbre && !nomsProjets.length ? 'Aucun projet / commune pour cette affaire.' : undefined">
          <select :id="id" v-model="nomProjet" class="saisie" :disabled="!nomsProjets.length">
            <option :value="null" disabled>{{ chargementArbre ? 'Chargement…' : 'Choisir' }}</option>
            <option v-for="n in nomsProjets" :key="n" :value="n">{{ n }}</option>
          </select>
        </UiChamp>
        <UiChamp v-slot="{ id }" libelle="Prestation" requis :erreur="premier('prestation')"
          :aide="nomProjet && prestationsDuProjet.length === 1 ? 'Remplie automatiquement : une seule prestation pour ce projet / cette commune.' : undefined">
          <select :id="id" v-model="prestation" class="saisie" :disabled="!prestationsDuProjet.length">
            <option :value="null" disabled>{{ nomProjet ? 'Choisir' : 'Choisissez d’abord le projet / la commune' }}</option>
            <option v-for="p in prestationsDuProjet" :key="p.id" :value="p.id">{{ p.nom }}</option>
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
      <div v-if="!multiple && descriptionChoisie && reportDt" class="ligne-quantite">
        <label class="champ-libelle" :for="`lineaire-${descriptionChoisie.id}`">Quantité linéaire</label>
        <input :id="`lineaire-${descriptionChoisie.id}`" v-model="lineaires[String(descriptionChoisie.id)]" class="saisie quantite" type="number" min="0" step="0.01"
          :disabled="!descriptionChoisie.quantite_modifiable" :aria-invalid="!!premier('quantites')" />
        <span class="texte-doux">ML</span>
        <span class="calcul">→ Quantité <strong>{{ quantiteCalculee(descriptionChoisie) ?? '—' }}</strong> {{ prestationChoisie?.unite }}</span>
        <span class="texte-xs texte-doux">Report DT : Quantité linéaire × Surface ({{ projetChoisi?.surface_m2 ?? '—' }} m²) ÷ Linéaire total
          ({{ arrondi2(lineaireTotal) }} ML).{{ projetChoisi?.surface_m2 ? '' : ' Surface du projet non renseignée : Quantité vide.' }}</span>
      </div>
      <div v-if="!multiple && descriptionChoisie && !reportDt" class="ligne-quantite">
        <label class="champ-libelle" :for="`quantite-${descriptionChoisie.id}`">Quantité</label>
        <input :id="`quantite-${descriptionChoisie.id}`" v-model="quantites[String(descriptionChoisie.id)]" class="saisie quantite" type="number" min="0" step="any"
          :disabled="!descriptionChoisie.quantite_modifiable" :aria-invalid="!!premier('quantites')" />
        <span class="texte-doux">{{ prestationChoisie?.unite }}</span>
        <span class="texte-xs texte-doux">{{ descriptionChoisie.quantite_modifiable
          ? 'Modifiable : enregistrée avec le pointage, et inscrite dans l’historique de la feuille.'
          : 'Lecture seule (droit « Pointages > Quantité des descriptions »).' }}</span>
      </div>
      <span v-if="premier('quantites')" class="champ-erreur" role="alert">{{ premier('quantites') }}</span>
      <div v-if="multiple" class="champ">
        <span class="champ-libelle">Descriptions <span class="requis">*</span></span>
        <span v-if="premier('descriptions')" class="champ-erreur" role="alert">{{ premier('descriptions') }}</span>
        <p v-if="!projet" class="texte-xs texte-doux">Choisissez d'abord l'affaire, le projet / la commune et la prestation.</p>
        <p v-else-if="!descriptions.length" class="texte-xs texte-doux">Aucune description pour ce projet.</p>
        <div v-else class="tout-cocher">
          <button type="button" class="lien" :disabled="choisies.length === descriptions.length" @click="toutCocher(true)">
            <i class="bi bi-check2-all" aria-hidden="true" /> Tout cocher</button>
          <button type="button" class="lien" :disabled="!choisies.length" @click="toutCocher(false)">
            <i class="bi bi-x-lg" aria-hidden="true" /> Tout décocher</button>
          <span class="texte-xs texte-doux">{{ choisies.length }} / {{ descriptions.length }} cochée(s)</span>
        </div>
        <ul v-if="projet && descriptions.length" class="multiples">
          <li v-for="d in descriptions" :key="d.id">
            <label class="case">
              <input type="checkbox" :checked="choisies.includes(d.id)" @change="basculer(d.id)" />
              <span class="gras">{{ d.nom }}</span>
              <span class="texte-xs texte-doux">{{ formatNombre(d.quantite) }} {{ prestationChoisie?.unite }}{{ d.ligne ? `, ${d.ligne.feuille}` : ', hors feuille' }}</span>
            </label>
            <span v-if="choisies.includes(d.id) && reportDt" class="quantite-multiple">
              <input v-model="lineaires[String(d.id)]" class="saisie quantite" type="number" min="0" step="0.01" :aria-label="`Quantité linéaire de ${d.nom}`"
                :disabled="!d.quantite_modifiable" title="Quantité linéaire (ML)" />
              <span class="texte-xs texte-doux">ML → {{ quantiteCalculee(d) ?? '—' }}</span>
            </span>
            <span v-if="choisies.includes(d.id) && !reportDt" class="quantite-multiple">
              <input v-model="quantites[String(d.id)]" class="saisie quantite" type="number" min="0" step="any" :aria-label="`Quantité de ${d.nom}`"
                :disabled="!d.quantite_modifiable" :title="d.quantite_modifiable ? 'Quantité (modifiable)' : 'Lecture seule'" />
              <span class="texte-xs texte-doux">{{ prestationChoisie?.unite }}</span>
            </span>
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
.ligne-quantite { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e2); margin-top: calc(-1 * var(--e2)); }
.saisie.quantite { width: 130px; text-align: right; font-weight: 700; }
.calcul { color: var(--marine); }
.tout-cocher { display: flex; align-items: center; gap: var(--e3); margin-bottom: var(--e2); }
.tout-cocher .lien { border: none; background: none; color: var(--marine-clair); font-size: var(--taille-s); font-weight: 600; cursor: pointer; padding: 0; }
.tout-cocher .lien:disabled { opacity: 0.45; cursor: default; }
.quantite-multiple { display: inline-flex; align-items: center; gap: 4px; margin-left: auto; }
.quantite-multiple .saisie.quantite { width: 100px; height: 30px; }
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
