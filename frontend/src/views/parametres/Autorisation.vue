<!--
  Paramètres > Autorisation (superadmins) : le « moindre privilège », comme les skins d'Alimanaka.
    Droits de base (fixes) + rôles qui AUTORISENT ou REFUSENT une action d'un module, sur un périmètre.
    Un refus l'emporte toujours. Un rôle s'attribue à une personne, un poste ou un pôle.
  Moteur de décision : backend/autorisations/droits.py.
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { affairesApi, rolesApi } from '@/api'
import type { AttributionRole, CatalogueDroits, DroitRole, ModuleDroits, ResultatTest, Role } from '@/api/autorisations'
import { messageErreur } from '@/api/client'
import { useConfirmation } from '@/composables/useConfirmation'
import { useToast } from '@/composables/useToast'
import type { EmployeResume, Identifiant } from '@/types'
import { formatDateHeure } from '@/utils/format'
import SelectEmploye from '@/components/formulaires/SelectEmploye.vue'
import ChoixValeur from '@/components/autorisations/ChoixValeur.vue'
import ListePerimetres, { type Perimetre } from '@/components/autorisations/ListePerimetres.vue'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'
import UiModale from '@/components/ui/UiModale.vue'
import UiOnglets from '@/components/ui/UiOnglets.vue'

const toast = useToast()
const { confirmer } = useConfirmation()
const onglet = ref('roles')
const catalogue = ref<CatalogueDroits | null>(null)
const roles = ref<Role[]>([])
const affaires = ref<{ id: Identifiant; nom: string; num_affaire: string }[]>([])
const choisi = ref<Role | null>(null)

async function chargerRoles(garder?: Identifiant) {
  roles.value = await rolesApi.tous()
  const id = garder ?? choisi.value?.id
  choisir(roles.value.find((r) => r.id === id) ?? roles.value[0] ?? null)
}
onMounted(async () => {
  try {
    const [c, a, v] = await Promise.all([rolesApi.catalogue(), affairesApi.tous({ inclure_inactifs: true }), rolesApi.valeurs()])
    catalogue.value = c
    affaires.value = a as typeof affaires.value
    valeurs.value = v
    await chargerRoles()
  } catch (e) {
    toast.erreur(e)
  }
})

// --- Fiche du rôle -------------------------------------------------------------------------
const fiche = reactive({ nom: '', description: '', actif: true })
// Pour chaque action : plusieurs périmètres « Autoriser sur… » et « Refuser sur… »
type Case = { autoriser: Perimetre[]; refuser: Perimetre[] }
const grille = reactive<Record<string, Case>>({})
const cle = (m: string, a: string) => `${m}:${a}`
const modifiee = ref(false)
const valeurs = ref<{ postes: string[]; poles: string[] }>({ postes: [], poles: [] })

function choisir(role: Role | null) {
  choisi.value = role
  Object.keys(grille).forEach((k) => delete grille[k])
  if (!role || !catalogue.value) return
  Object.assign(fiche, { nom: role.nom, description: role.description, actif: role.actif })
  for (const m of catalogue.value.modules) {
    for (const a of m.actions) {
      const droits = role.droits.filter((x) => x.module === m.code && x.action === a)
      const versPerimetre = (d: DroitRole): Perimetre => ({
        perimetre: d.perimetre, valeur: d.valeur, employe: d.employe, employe_details: d.employe_details ?? null, affaire: d.affaire,
      })
      grille[cle(m.code, a)] = {
        autoriser: droits.filter((d) => d.effet === 'AUTORISER').map(versPerimetre),
        refuser: droits.filter((d) => d.effet === 'REFUSER').map(versPerimetre),
      }
    }
  }
  chargerAttributions()
  window.setTimeout(() => (modifiee.value = false))
}
watch([grille, fiche], () => (modifiee.value = !!choisi.value), { deep: true })

const envoi = ref(false)
async function enregistrer() {
  if (!choisi.value || !catalogue.value) return
  const droits: DroitRole[] = []
  for (const m of catalogue.value.modules) {
    for (const a of m.actions) {
      const c = grille[cle(m.code, a)]!
      for (const [effet, liste] of [['AUTORISER', c.autoriser], ['REFUSER', c.refuser]] as const) {
        for (const p of liste) {
          droits.push({ effet, module: m.code, action: a, perimetre: p.perimetre, valeur: p.valeur, employe: p.employe, affaire: p.affaire })
        }
      }
    }
  }
  envoi.value = true
  try {
    await rolesApi.modifier(choisi.value.id, { ...fiche })
    await rolesApi.enregistrerDroits(choisi.value.id, droits)
    toast.succes(`Rôle « ${fiche.nom} » enregistré`)
    await chargerRoles(choisi.value.id)
  } catch (e) {
    toast.erreur(messageErreur(e))
  } finally {
    envoi.value = false
  }
}

// Nouveau rôle : fenêtre de l'application (window.prompt est bloqué par certains navigateurs)
const creation = reactive({ ouverte: false, nom: '', description: '', erreur: '', envoi: false })
watch(() => creation.nom, () => (creation.erreur = ''))   // le message disparaît dès qu'on corrige
function nouveauRole() {
  Object.assign(creation, { ouverte: true, nom: '', description: '', erreur: '', envoi: false })
}
async function creerRole() {
  const nom = creation.nom.trim()
  if (!nom) {
    creation.erreur = 'Indiquez le nom du rôle.'
    return
  }
  creation.envoi = true
  try {
    const role = await rolesApi.creer({ nom, description: creation.description.trim(), actif: true })
    creation.ouverte = false
    toast.succes(`Rôle « ${nom} » créé : réglez maintenant ses droits`)
    await chargerRoles(role.id)
  } catch (e) {
    creation.erreur = messageErreur(e)
  } finally {
    creation.envoi = false
  }
}
async function supprimerRole() {
  if (!choisi.value) return
  if (!(await confirmer({ titre: 'Supprimer le rôle', message: `Supprimer « ${choisi.value.nom} », ses droits et ses attributions ?`, danger: true }))) return
  try {
    await rolesApi.supprimer(choisi.value.id)
    choisi.value = null
    await chargerRoles()
  } catch (e) {
    toast.erreur(messageErreur(e))
  }
}

// --- Attributions -------------------------------------------------------------------------
const attributions = ref<AttributionRole[]>([])
const personnes = ref<{ nombre: number; personnes: EmployeResume[] } | null>(null)
const ajout = reactive({ critere: 'MATRICULE' as AttributionRole['critere'], employe: null as Identifiant | null, poste: '', pole: '' })
async function chargerAttributions() {
  if (!choisi.value) return
  const id = choisi.value.id
  ;[attributions.value, personnes.value] = await Promise.all([rolesApi.attributions(id), rolesApi.personnes(id)])
}
async function ajouterAttribution() {
  if (!choisi.value) return
  try {
    await rolesApi.ajouterAttribution({ role: choisi.value.id, ...ajout })
    Object.assign(ajout, { employe: null, poste: '', pole: '' })
    await chargerAttributions()
    await chargerRoles(choisi.value.id)
  } catch (e) {
    toast.erreur(messageErreur(e))
  }
}
async function basculerAttribution(a: AttributionRole) {
  await rolesApi.modifierAttribution(a.id, { actif: !a.actif })
  await chargerAttributions()
}
async function retirerAttribution(a: AttributionRole) {
  await rolesApi.retirerAttribution(a.id)
  await chargerAttributions()
  await chargerRoles(choisi.value?.id)
}

// --- Tester un accès ----------------------------------------------------------------------
const test = reactive({ employe: null as Identifiant | null, module: 'pointages_suivi', action: 'voir', cible_employe: null as Identifiant | null, cible_affaire: null as Identifiant | null })
const moduleTest = computed(() => catalogue.value?.modules.find((m) => m.code === test.module))
watch(() => test.module, () => {
  test.action = moduleTest.value?.actions[0] ?? 'voir'
  test.cible_employe = null
  test.cible_affaire = null
})
const resultat = ref<ResultatTest | null>(null)
async function tester() {
  if (!test.employe) return toast.erreur('Choisissez la personne à tester.')
  try {
    resultat.value = await rolesApi.tester({ ...test, employe: test.employe })
  } catch (e) {
    toast.erreur(messageErreur(e))
  }
}

// --- Journal ------------------------------------------------------------------------------
const journal = ref<{ date: string; auteur: string; texte: string }[] | null>(null)
watch(onglet, async (o) => {
  if (o === 'journal') journal.value = await rolesApi.journal()
})

const nomAffaire = (a: { nom: string; num_affaire: string }) => (a.num_affaire ? `${a.num_affaire} – ${a.nom}` : a.nom)
const baseTexte = (m: ModuleDroits, a: string) => {
  const b = m.base[a]
  return b ? `${b.condition} : ${b.libelle}` : '—'
}
const ONGLETS = [
  { valeur: 'roles', libelle: 'Rôles', icone: 'person-badge' },
  { valeur: 'base', libelle: 'Droits de base', icone: 'shield' },
  { valeur: 'tester', libelle: 'Tester un accès', icone: 'search' },
  { valeur: 'journal', libelle: 'Journal', icone: 'clock-history' },
]
</script>

<template>
  <div class="page page-large">
    <EnTetePage titre="Autorisation" description="Le minimum de privilège : des droits de base pour tous, et des rôles qui autorisent ou refusent une action sur un périmètre. Un refus l’emporte toujours ; le superadmin a tous les droits." />
    <UiOnglets v-model="onglet" :onglets="ONGLETS" />
    <UiChargement v-if="!catalogue" />

    <!-- ===================== Rôles ===================== -->
    <div v-else-if="onglet === 'roles'" class="disposition">
      <aside class="carte liste-roles">
        <header class="tete-liste"><span class="gras">Rôles</span>
          <UiBouton variante="primaire" petit icone="plus-lg" @click="nouveauRole">Nouveau</UiBouton></header>
        <p v-if="!roles.length" class="texte-xs texte-doux vide">Aucun rôle : tout le monde n’a que les droits de base.</p>
        <button v-for="r in roles" :key="r.id" type="button" class="role" :class="{ actif: choisi?.id === r.id, inactif: !r.actif }" @click="choisir(r)">
          <span class="gras">{{ r.nom }}</span>
          <span class="texte-xs texte-doux">{{ r.nb_droits }} droit(s), {{ r.nb_attributions }} attribution(s){{ r.actif ? '' : ' — désactivé' }}</span>
        </button>
      </aside>

      <UiEtatVide v-if="!choisi" class="carte" icone="person-badge" titre="Choisissez ou créez un rôle" />
      <div v-else class="pile">
        <section class="carte carte-corps fiche">
          <label class="champ"><span class="champ-libelle">Nom</span><input v-model="fiche.nom" class="saisie" /></label>
          <label class="champ large"><span class="champ-libelle">Description</span><input v-model="fiche.description" class="saisie" placeholder="À quoi sert ce rôle ?" /></label>
          <label class="case-actif"><input v-model="fiche.actif" type="checkbox" /> Actif</label>
          <div class="actions-fiche">
            <UiBouton variante="danger" icone="trash" @click="supprimerRole">Supprimer</UiBouton>
            <UiBouton variante="primaire" icone="check-lg" :chargement="envoi" :desactive="!modifiee" @click="enregistrer">Enregistrer</UiBouton>
          </div>
        </section>

        <section class="carte carte-corps pile">
          <header><h2 class="titre-section"><i class="bi bi-grid-3x3" aria-hidden="true" /> Droits du rôle</h2>
            <p class="texte-xs texte-doux">Pour chaque action, ajoutez autant de périmètres que nécessaire : <strong class="ok">Autoriser sur…</strong>
              (en plus du droit de base) et <strong class="ko">Refuser sur…</strong> (un refus l’emporte toujours ; « Tout » retire complètement le droit).</p></header>
          <div v-for="m in catalogue.modules" :key="m.code" class="module">
            <h3>{{ m.libelle }}</h3>
            <p class="texte-xs texte-doux">{{ m.aide }}</p>
            <table class="grille">
              <thead><tr><th>Action</th><th>Droit de base</th><th>Autoriser sur…</th><th>Refuser sur…</th></tr></thead>
              <tbody>
                <tr v-for="a in m.actions" :key="a"
                  :class="{ autoriser: grille[cle(m.code, a)]?.autoriser.length, refuser: grille[cle(m.code, a)]?.refuser.length }">
                  <td class="gras">{{ catalogue.actions[a] }}</td>
                  <td class="texte-xs texte-doux">{{ baseTexte(m, a) }}</td>
                  <td>
                    <ListePerimetres v-model="grille[cle(m.code, a)]!.autoriser" effet="AUTORISER" :perimetres="m.perimetres" :affaires="affaires"
                      :postes="valeurs.postes" :poles="valeurs.poles" :libelle="`Autoriser « ${catalogue.actions[a]} » sur ${m.libelle}`" />
                  </td>
                  <td>
                    <ListePerimetres v-model="grille[cle(m.code, a)]!.refuser" effet="REFUSER" :perimetres="m.perimetres" :affaires="affaires"
                      :postes="valeurs.postes" :poles="valeurs.poles" :libelle="`Refuser « ${catalogue.actions[a]} » sur ${m.libelle}`" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="carte carte-corps pile">
          <header><h2 class="titre-section"><i class="bi bi-people" aria-hidden="true" /> Qui a ce rôle</h2>
            <p class="texte-xs texte-doux">Une personne, ou automatiquement tout un poste ou un pôle (selon l’API RH).</p></header>
          <ul v-if="attributions.length" class="attributions">
            <li v-for="a in attributions" :key="a.id" :class="{ inactif: !a.actif }">
              <UiEmploye v-if="a.critere === 'MATRICULE' && a.employe_details" :employe="a.employe_details" />
              <span v-else class="gras"><i class="bi" :class="a.critere === 'POSTE' ? 'bi-person-vcard' : 'bi-diagram-3'" aria-hidden="true" /> {{ a.description }}</span>
              <span class="texte-xs texte-doux">{{ a.actif ? '' : 'désactivée' }}</span>
              <UiBouton variante="fantome" petit :icone="a.actif ? 'pause-circle' : 'play-circle'" @click="basculerAttribution(a)">{{ a.actif ? 'Désactiver' : 'Activer' }}</UiBouton>
              <UiBouton variante="fantome" petit icone="x-lg" icone-seule @click="retirerAttribution(a)">Retirer</UiBouton>
            </li>
          </ul>
          <p v-else class="texte-petit texte-doux">Personne n’a encore ce rôle.</p>
          <div class="ajout">
            <select v-model="ajout.critere" class="saisie" aria-label="Attribuer à">
              <option value="MATRICULE">Une personne</option><option value="POSTE">Un poste</option><option value="POLE">Un pôle</option>
            </select>
            <SelectEmploye v-if="ajout.critere === 'MATRICULE'" v-model="ajout.employe" placeholder="Rechercher une personne" />
            <ChoixValeur v-else-if="ajout.critere === 'POSTE'" v-model="ajout.poste" :options="valeurs.postes" placeholder="Rechercher un poste" />
            <ChoixValeur v-else v-model="ajout.pole" :options="valeurs.poles" placeholder="Rechercher un pôle" />
            <UiBouton icone="plus-lg" @click="ajouterAttribution">Attribuer</UiBouton>
          </div>
          <details v-if="personnes" class="concernes">
            <summary>{{ personnes.nombre }} personne(s) ont ce rôle aujourd’hui</summary>
            <ul><li v-for="p in personnes.personnes" :key="p.id"><UiEmploye :employe="p" /></li></ul>
          </details>
        </section>
      </div>
    </div>

    <!-- ===================== Droits de base ===================== -->
    <section v-else-if="onglet === 'base'" class="carte carte-corps pile">
      <p class="texte-petit texte-doux">Ce que chacun peut faire sans rôle : seulement voir les feuilles de ses affaires, et consulter
        Mes marchés (ses affaires). Paramètres, Utilisateurs et Équipes sont réservés au superadmin. Suivi, Vérification,
        Créer une nouvelle feuille, Ajouter un marché (et chacun de ses panneaux) et Archives demandent un rôle.</p>
      <div v-for="m in catalogue.modules" :key="m.code" class="module">
        <h3>{{ m.libelle }}</h3>
        <table class="grille">
          <thead><tr><th>Action</th><th>Qui</th><th>Périmètre</th></tr></thead>
          <tbody>
            <tr v-for="a in m.actions" :key="a">
              <td class="gras">{{ catalogue.actions[a] }}</td>
              <td>{{ m.base[a]?.condition ?? 'Superadmin seulement' }}</td>
              <td>{{ m.base[a]?.libelle ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ===================== Tester un accès ===================== -->
    <section v-else-if="onglet === 'tester'" class="carte carte-corps pile">
      <p class="texte-petit texte-doux">La décision du système pour une personne, avec ses rôles du moment, et pourquoi.</p>
      <div class="formulaire-test">
        <label class="champ"><span class="champ-libelle">Personne</span><SelectEmploye v-model="test.employe" placeholder="Rechercher" /></label>
        <label class="champ"><span class="champ-libelle">Module</span>
          <select v-model="test.module" class="saisie"><option v-for="m in catalogue.modules" :key="m.code" :value="m.code">{{ m.libelle }}</option></select></label>
        <label class="champ"><span class="champ-libelle">Action</span>
          <select v-model="test.action" class="saisie"><option v-for="a in moduleTest?.actions ?? []" :key="a" :value="a">{{ catalogue.actions[a] }}</option></select></label>
        <label v-if="moduleTest?.cible === 'personnes'" class="champ"><span class="champ-libelle">Sur la personne (facultatif)</span>
          <SelectEmploye v-model="test.cible_employe" placeholder="Rechercher" /></label>
        <label v-if="moduleTest?.cible === 'affaires'" class="champ"><span class="champ-libelle">Sur l’affaire (facultatif)</span>
          <select v-model="test.cible_affaire" class="saisie"><option :value="null">—</option>
            <option v-for="af in affaires" :key="af.id" :value="af.id">{{ nomAffaire(af) }}</option></select></label>
        <UiBouton variante="primaire" icone="search" @click="tester">Tester</UiBouton>
      </div>
      <div v-if="resultat" class="resultat" :class="resultat.autorise ? 'oui' : 'non'">
        <p class="gras"><i class="bi" :class="resultat.autorise ? 'bi-check-circle-fill' : 'bi-x-circle-fill'" aria-hidden="true" /> {{ resultat.resume }}</p>
        <p v-if="resultat.roles" class="texte-xs">Rôles : {{ resultat.roles.length ? resultat.roles.join(', ') : 'aucun' }}</p>
        <ul class="texte-petit"><li v-for="(r, i) in resultat.raisons" :key="i">{{ r }}</li></ul>
      </div>
    </section>

    <!-- ===================== Journal ===================== -->
    <section v-else class="carte carte-corps">
      <UiChargement v-if="!journal" />
      <p v-else-if="!journal.length" class="texte-doux texte-petit">Aucune modification pour l’instant.</p>
      <ul v-else class="journal">
        <li v-for="(l, i) in journal" :key="i"><span class="texte-xs texte-doux">{{ formatDateHeure(l.date) }}</span>
          <span class="gras">{{ l.auteur }}</span> <span>{{ l.texte }}</span></li>
      </ul>
    </section>

    <UiModale v-model="creation.ouverte" titre="Nouveau rôle" taille="petite">
      <form class="pile" @submit.prevent="creerRole">
        <label class="champ"><span class="champ-libelle">Nom <span class="requis">*</span></span>
          <input v-model="creation.nom" class="saisie" :class="{ invalide: creation.erreur && !creation.nom.trim() }" maxlength="100"
            placeholder="ex. Chef de projet, RH lecture" autofocus /></label>
        <label class="champ"><span class="champ-libelle">Description</span>
          <textarea v-model="creation.description" class="saisie" rows="3" placeholder="À quoi sert ce rôle ? (facultatif)" /></label>
        <p v-if="creation.erreur" class="alerte alerte-erreur texte-petit" role="alert">{{ creation.erreur }}</p>
        <div class="boutons-modale">
          <UiBouton type="button" @click="creation.ouverte = false">Annuler</UiBouton>
          <UiBouton type="submit" variante="primaire" icone="plus-lg" :chargement="creation.envoi">Créer le rôle</UiBouton>
        </div>
      </form>
    </UiModale>
  </div>
</template>

<style scoped>
.page-large { max-width: none; }
.disposition { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: var(--e4); align-items: start; margin-top: var(--e4); }
.liste-roles { display: flex; flex-direction: column; padding: var(--e3); gap: 4px; position: sticky; top: 76px; }
.tete-liste { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--e2); }
.vide { padding: var(--e2); }
.role { display: flex; flex-direction: column; gap: 2px; padding: var(--e2) var(--e3); border: 1px solid transparent; border-radius: var(--rayon); background: none; text-align: left; cursor: pointer; }
.role:hover { background: var(--surface-douce); }
.role.actif { border-color: var(--marine); background: var(--marine-pale); }
.role.inactif { opacity: 0.6; }
.fiche { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--e3); }
.fiche .champ { min-width: 200px; }
.fiche .large { flex: 1; min-width: 280px; }
.case-actif { display: inline-flex; align-items: center; gap: var(--e2); font-weight: 600; height: 38px; }
.actions-fiche { display: flex; gap: var(--e2); margin-left: auto; }
.titre-section { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-m); color: var(--marine); }
.module { margin-top: var(--e3); }
.module h3 { font-size: var(--taille-m); color: var(--marine); }
.grille { width: 100%; margin-top: var(--e2); border-collapse: collapse; font-size: var(--taille-s); table-layout: fixed; }
.grille th:nth-child(1) { width: 12%; } .grille th:nth-child(2) { width: 22%; }
.grille th:nth-child(3), .grille th:nth-child(4) { width: 33%; }
.grille th { text-align: left; font-size: var(--taille-xs); color: var(--texte-doux); padding: 6px 8px; border-bottom: 1px solid var(--bordure-forte); }
.grille td { padding: 6px 8px; border-bottom: 1px solid var(--bordure); vertical-align: middle; }

.grille tr.autoriser { background: color-mix(in srgb, var(--succes) 5%, transparent); }
.grille tr.refuser { box-shadow: inset 3px 0 0 var(--rouge); }
.effets { display: inline-flex; border: 1px solid var(--bordure-forte); border-radius: var(--rayon); overflow: hidden; }
.eff { padding: 4px 12px; border: none; background: var(--surface); font-size: var(--taille-xs); font-weight: 700; color: var(--texte-doux); cursor: pointer; }
.eff.ok[aria-pressed='true'] { background: var(--succes); color: #fff; }
.eff.ko[aria-pressed='true'] { background: var(--rouge); color: #fff; }
.perimetre { display: flex; flex-wrap: wrap; gap: var(--e2); }
.perimetre .saisie { min-width: 200px; max-width: 280px; }
.ok { color: var(--succes); } .ko { color: var(--rouge); }
.attributions { list-style: none; display: flex; flex-direction: column; gap: var(--e2); }
.attributions li { display: flex; align-items: center; gap: var(--e3); }
.attributions li > :first-child { flex: 1; }
.attributions li.inactif { opacity: 0.55; }
.ajout { display: flex; flex-wrap: wrap; gap: var(--e2); align-items: center; }
.ajout > select { width: 170px; flex: none; }
.ajout > :nth-child(2) { flex: 1; min-width: 240px; }
.concernes summary { cursor: pointer; font-weight: 600; color: var(--marine); font-size: var(--taille-s); }
.concernes ul { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--e2); margin-top: var(--e2); }
.formulaire-test { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: var(--e3); align-items: end; }
.resultat { padding: var(--e3) var(--e4); border-radius: var(--rayon); border-left: 5px solid; }
.resultat.oui { border-color: var(--succes); background: color-mix(in srgb, var(--succes) 8%, var(--surface)); }
.resultat.non { border-color: var(--rouge); background: color-mix(in srgb, var(--rouge) 7%, var(--surface)); }
.resultat ul { margin: var(--e2) 0 0 1.2rem; }
.boutons-modale { display: flex; justify-content: flex-end; gap: var(--e2); }
.requis { color: var(--rouge); }
.journal { list-style: none; display: flex; flex-direction: column; gap: var(--e2); font-size: var(--taille-s); }
.journal li { display: flex; flex-wrap: wrap; gap: var(--e2); align-items: baseline; padding-bottom: var(--e2); border-bottom: 1px solid var(--bordure); }
@media (max-width: 1000px) { .disposition { grid-template-columns: 1fr; } .liste-roles { position: static; } }
</style>
