<!--
  Paramètres > Vérification des droits (superadmin ; calculs : backend/autorisations/verification.py).
    Fiche d'une personne : postes et pôles (API RH), accès au site, rôles appliqués et comment, rôles visés par un
                           intitulé proche, grille complète module × action avec les raisons.
    Comparer deux personnes : les deux grilles côte à côte, les différences mises en évidence et expliquées.
    Anomalies : attributions qui ne correspondent à personne, intitulés écrits de plusieurs façons, rôles sans
                effet, refus qui annulent un droit, personnes sans rôle.
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { verificationDroitsApi } from '@/api/autorisations'
import type { AnomalieDroits, CaseDroit, ComparaisonDroits, FicheDroits } from '@/api/autorisations'
import { useToast } from '@/composables/useToast'
import SelectEmploye from '@/components/formulaires/SelectEmploye.vue'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'
import UiOnglets from '@/components/ui/UiOnglets.vue'

const toast = useToast()
const onglet = ref('fiche')
const anomalies = ref<AnomalieDroits[] | null>(null)
const nbAnomalies = computed(() => (anomalies.value ?? []).filter((a) => a.gravite !== 'info').reduce((t, a) => t + a.nombre, 0))
const ONGLETS = computed(() => [
  { valeur: 'fiche', libelle: 'Fiche d’une personne', icone: 'person-badge' },
  { valeur: 'comparer', libelle: 'Comparer deux personnes', icone: 'people' },
  { valeur: 'anomalies', libelle: 'Anomalies', icone: 'exclamation-triangle', compteur: nbAnomalies.value || undefined },
])

// --- Fiche ---------------------------------------------------------------------------------------
const personne = ref<number | null>(null)
const fiche = ref<FicheDroits | null>(null)
const chargementFiche = ref(false)
const seulementAutorises = ref(false)
watch(personne, async (id) => {
  fiche.value = null
  if (!id) return
  chargementFiche.value = true
  try {
    fiche.value = await verificationDroitsApi.fiche(id)
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargementFiche.value = false
  }
})
const grilleAffichee = computed(() => (fiche.value?.grille ?? [])
  .map((m) => ({ ...m, actions: seulementAutorises.value ? m.actions.filter((a) => a.autorise) : m.actions }))
  .filter((m) => m.actions.length))
const caseOuverte = ref('')

// --- Comparer --------------------------------------------------------------------------------------
const personneA = ref<number | null>(null)
const personneB = ref<number | null>(null)
const comparaison = ref<ComparaisonDroits | null>(null)
const chargementComparaison = ref(false)
const seulementDifferences = ref(true)
watch([personneA, personneB], async ([a, b]) => {
  comparaison.value = null
  if (!a || !b) return
  chargementComparaison.value = true
  try {
    comparaison.value = await verificationDroitsApi.comparer(a, b)
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargementComparaison.value = false
  }
})
const lignesComparaison = computed(() => (comparaison.value?.grille ?? [])
  .map((m) => ({ ...m, actions: seulementDifferences.value ? m.actions.filter((a) => a.difference) : m.actions }))
  .filter((m) => m.actions.length))

// --- Anomalies -------------------------------------------------------------------------------------
const chargementAnomalies = ref(false)
async function chargerAnomalies() {
  chargementAnomalies.value = true
  try {
    anomalies.value = await verificationDroitsApi.anomalies()
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargementAnomalies.value = false
  }
}
onMounted(chargerAnomalies)

const symbole = (c: CaseDroit) => (c.autorise ? 'bi-check-circle-fill' : c.refuse ? 'bi-slash-circle-fill' : 'bi-x-circle')
const etat = (c: CaseDroit) => (c.autorise ? 'oui' : c.refuse ? 'refus' : 'non')
const ICONES_GRAVITE: Record<string, string> = { erreur: 'x-octagon-fill', attention: 'exclamation-triangle-fill', info: 'info-circle-fill' }
</script>

<template>
  <div class="page pile">
    <EnTetePage titre="Vérification des droits"
      description="Pourquoi une personne a (ou n’a pas) un droit : sa fiche complète, la comparaison de deux personnes, et les anomalies qui empêchent un rôle de s’appliquer." />
    <UiOnglets v-model="onglet" :onglets="ONGLETS" />

    <!-- ===================== Fiche d'une personne ===================== -->
    <template v-if="onglet === 'fiche'">
      <section class="carte carte-corps choix">
        <span class="champ-libelle">Personne</span>
        <SelectEmploye v-model="personne" placeholder="Rechercher une personne (matricule, nom)" />
      </section>
      <UiChargement v-if="chargementFiche" />
      <UiEtatVide v-else-if="!fiche" class="carte" icone="person-badge" titre="Choisissez une personne"
        texte="Ses rôles, comment ils s’appliquent, et la réponse pour chaque module et chaque action." />
      <template v-else>
        <div class="resume">
          <section class="carte carte-corps">
            <UiEmploye :employe="fiche.employe" />
            <div class="pastilles">
              <span v-if="fiche.superadmin" class="pastille marine"><i class="bi bi-shield-fill-check" aria-hidden="true" /> Superadmin : tous les droits</span>
              <span class="pastille" :class="fiche.acces_site.acces ? 'ok' : 'ko'">
                <i class="bi" :class="fiche.acces_site.acces ? 'bi-door-open' : 'bi-door-closed'" aria-hidden="true" />
                {{ fiche.acces_site.acces ? 'Accès au site' : 'Pas d’accès au site' }}</span>
              <span v-if="fiche.jamais_connecte" class="pastille info">Jamais connectée</span>
            </div>
            <ul v-if="fiche.acces_site.regles.length" class="texte-xs texte-doux regles">
              <li v-for="r in fiche.acces_site.regles" :key="r.id">{{ r.effet === 'AUTORISER' ? 'Autorisé' : 'Refusé' }} : {{ r.description }}</li>
            </ul>
          </section>
          <section class="carte carte-corps">
            <h2 class="titre-section">Postes et pôles (fiche RH)</h2>
            <p v-if="!fiche.postes.length" class="texte-petit texte-doux">Aucun poste dans sa fiche : seuls les rôles attribués à la personne s’appliquent.</p>
            <ul v-else class="liste-simple">
              <li v-for="(p, i) in fiche.postes" :key="i"><span class="gras">{{ p.poste || '—' }}</span> <span class="texte-doux">· pôle {{ p.pole || '—' }}</span></li>
            </ul>
          </section>
          <section class="carte carte-corps">
            <h2 class="titre-section">Rôles appliqués</h2>
            <p v-if="!fiche.roles.length" class="texte-petit texte-doux">Aucun rôle : seulement les droits de base.</p>
            <ul v-else class="liste-simple">
              <li v-for="r in fiche.roles" :key="r.id"><span class="gras">{{ r.nom }}</span>
                <span class="texte-xs texte-doux">{{ r.comment.join(' ; ') }}</span></li>
            </ul>
            <div v-if="fiche.roles_proches.length" class="alerte alerte-attention texte-petit proches" role="note">
              <i class="bi bi-exclamation-triangle" aria-hidden="true" />
              <div>Rôle(s) visé(s) par un intitulé proche, mais <strong>non appliqué(s)</strong> :
                <ul><li v-for="(p, i) in fiche.roles_proches" :key="i">« {{ p.role }} » attribué au {{ p.critere }} « {{ p.valeur }} » ; sa fiche dit « {{ p.fiche }} »</li></ul>
              </div>
            </div>
          </section>
        </div>

        <section class="carte carte-corps">
          <header class="tete-grille">
            <h2 class="titre-section">Droits, module par module</h2>
            <label class="bascule"><input v-model="seulementAutorises" type="checkbox" /> Seulement ce qui est autorisé</label>
          </header>
          <p class="texte-xs texte-doux legende">
            <i class="bi bi-check-circle-fill oui" aria-hidden="true" /> autorisé ·
            <i class="bi bi-x-circle non" aria-hidden="true" /> pas de droit ·
            <i class="bi bi-slash-circle-fill refus" aria-hidden="true" /> refusé par un rôle · cliquez une action pour voir pourquoi
          </p>
          <div class="modules">
            <article v-for="m in grilleAffichee" :key="m.module" class="module">
              <h3>{{ m.libelle }}</h3>
              <div class="actions">
                <button v-for="a in m.actions" :key="a.action" type="button" class="action" :class="[etat(a), { ouverte: caseOuverte === `${m.module}.${a.action}` }]"
                  :aria-expanded="caseOuverte === `${m.module}.${a.action}`" :title="a.resume"
                  @click="caseOuverte = caseOuverte === `${m.module}.${a.action}` ? '' : `${m.module}.${a.action}`">
                  <i class="bi" :class="symbole(a)" aria-hidden="true" /> {{ a.libelle }}
                </button>
              </div>
              <template v-for="a in m.actions" :key="`r-${a.action}`">
                <div v-if="caseOuverte === `${m.module}.${a.action}`" class="raisons">
                  <p class="gras">{{ a.resume }}</p>
                  <ul><li v-for="(r, i) in a.raisons" :key="i">{{ r }}</li></ul>
                </div>
              </template>
            </article>
          </div>
        </section>
      </template>
    </template>

    <!-- ===================== Comparer deux personnes ===================== -->
    <template v-else-if="onglet === 'comparer'">
      <section class="carte carte-corps choix-deux">
        <label class="champ"><span class="champ-libelle">Personne A</span><SelectEmploye v-model="personneA" placeholder="Rechercher" /></label>
        <i class="bi bi-arrow-left-right separateur" aria-hidden="true" />
        <label class="champ"><span class="champ-libelle">Personne B</span><SelectEmploye v-model="personneB" placeholder="Rechercher" /></label>
      </section>
      <UiChargement v-if="chargementComparaison" />
      <UiEtatVide v-else-if="!comparaison" class="carte" icone="people" titre="Choisissez deux personnes"
        texte="Par exemple celle qui voit le bouton et celle qui ne le voit pas." />
      <template v-else>
        <div class="resume deux">
          <section v-for="(c, i) in [comparaison.a, comparaison.b]" :key="i" class="carte carte-corps">
            <p class="texte-xs texte-doux">Personne {{ i === 0 ? 'A' : 'B' }}</p>
            <UiEmploye :employe="c.employe" />
            <p class="texte-xs"><span class="gras">Postes :</span> {{ c.postes.map((p) => `${p.poste || '—'} (${p.pole || '—'})`).join(', ') || 'aucun' }}</p>
            <p class="texte-xs"><span class="gras">Rôles :</span> {{ c.roles.map((r) => r.nom).join(', ') || 'aucun' }}{{ c.superadmin ? ' · superadmin' : '' }}</p>
            <p v-if="!c.acces_site.acces" class="texte-xs ko-texte">Pas d’accès au site</p>
            <p v-for="(p, j) in c.roles_proches" :key="j" class="texte-xs att-texte">
              « {{ p.role }} » vise le {{ p.critere }} « {{ p.valeur }} » mais sa fiche dit « {{ p.fiche }} »</p>
          </section>
        </div>
        <section class="carte carte-corps">
          <header class="tete-grille">
            <h2 class="titre-section">
              <span class="pastille" :class="comparaison.differences ? 'ko' : 'ok'">{{ comparaison.differences }}</span>
              différence(s) de droits
            </h2>
            <label class="bascule"><input v-model="seulementDifferences" type="checkbox" /> Seulement les différences</label>
          </header>
          <p v-if="!comparaison.differences" class="ok-texte texte-petit"><i class="bi bi-check-circle-fill" aria-hidden="true" />
            Mêmes droits partout. Si l’une voit un bouton et pas l’autre, ce n’est pas un droit : même page ? même affaire (en cours ou archivée) ? page rechargée ?</p>
          <div v-if="lignesComparaison.length" class="tableau-conteneur">
            <table class="comparaison">
              <thead><tr><th>Module</th><th>Action</th><th>A</th><th>B</th><th>Pourquoi</th></tr></thead>
              <tbody>
                <template v-for="m in lignesComparaison" :key="m.module">
                  <tr v-for="(x, i) in m.actions" :key="x.action" :class="{ difference: x.difference }">
                    <td v-if="i === 0" :rowspan="m.actions.length" class="gras">{{ m.libelle }}</td>
                    <td>{{ x.libelle }}</td>
                    <td><i class="bi" :class="[symbole(x.a), etat(x.a)]" :aria-label="x.a.resume" /></td>
                    <td><i class="bi" :class="[symbole(x.b), etat(x.b)]" :aria-label="x.b.resume" /></td>
                    <td class="texte-xs">
                      <template v-if="x.difference">
                        <div><span class="gras">A :</span> {{ x.a.resume }} <span class="texte-doux">{{ x.a.raisons.join(' ; ') }}</span></div>
                        <div><span class="gras">B :</span> {{ x.b.resume }} <span class="texte-doux">{{ x.b.raisons.join(' ; ') }}</span></div>
                      </template>
                      <span v-else class="texte-doux">identique</span>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </template>

    <!-- ===================== Anomalies ===================== -->
    <template v-else>
      <div class="ligne-actions">
        <p class="texte-petit texte-doux">Ce qui empêche le plus souvent un rôle de s’appliquer comme prévu.</p>
        <UiBouton icone="arrow-clockwise" :chargement="chargementAnomalies" @click="chargerAnomalies">Actualiser</UiBouton>
      </div>
      <UiChargement v-if="!anomalies" />
      <template v-else>
        <section v-for="a in anomalies" :key="a.code" class="carte carte-corps anomalie" :class="[a.gravite, { vide: !a.nombre }]">
          <header class="tete-anomalie">
            <i class="bi" :class="a.nombre ? `bi-${ICONES_GRAVITE[a.gravite]}` : 'bi-check-circle-fill'" aria-hidden="true" />
            <h2>{{ a.titre }}</h2>
            <span class="pastille" :class="a.nombre ? a.gravite : 'ok'">{{ a.nombre }}</span>
          </header>
          <p class="texte-xs texte-doux">{{ a.aide }}</p>
          <ul v-if="a.nombre" class="elements">
            <li v-for="(e, i) in a.elements" :key="i"><span class="gras">{{ e.texte }}</span><span class="texte-xs texte-doux">{{ e.detail }}</span></li>
          </ul>
        </section>
        <p class="texte-xs texte-doux">Pour corriger : <RouterLink to="/parametres/autorisations">Paramètres > Autorisation</RouterLink> (onglet Rôles, « Qui a ce rôle »).</p>
      </template>
    </template>
  </div>
</template>

<style scoped>
.choix { display: flex; align-items: center; gap: var(--e3); }
.choix :deep(.select-employe), .choix > :last-child { flex: 1; max-width: 520px; }
.choix-deux { display: grid; grid-template-columns: 1fr auto 1fr; align-items: end; gap: var(--e3); }
.separateur { margin-bottom: 10px; color: var(--texte-doux); font-size: 1.2rem; }
.resume { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e3); }
.resume.deux { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.resume .carte-corps { display: flex; flex-direction: column; gap: var(--e2); }
.titre-section { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-m); color: var(--marine); }
.pastilles { display: flex; flex-wrap: wrap; gap: 6px; }
.pastille { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; border-radius: 999px; font-size: var(--taille-xs); font-weight: 700; }
.pastille.ok { background: color-mix(in srgb, var(--succes) 14%, var(--surface)); color: var(--succes); }
.pastille.ko, .pastille.erreur { background: color-mix(in srgb, var(--rouge) 12%, var(--surface)); color: var(--rouge); }
.pastille.attention { background: color-mix(in srgb, #f59e0b 16%, var(--surface)); color: #b45309; }
.pastille.info { background: var(--marine-pale); color: var(--marine); }
.pastille.marine { background: var(--marine); color: #fff; }
.regles { list-style: none; }
.liste-simple { list-style: none; display: flex; flex-direction: column; gap: 4px; font-size: var(--taille-s); }
.liste-simple li { display: flex; flex-direction: column; }
.proches { display: flex; gap: var(--e2); }
.proches ul { margin: 4px 0 0 16px; }
.tete-grille { display: flex; align-items: center; justify-content: space-between; gap: var(--e3); }
.bascule { display: inline-flex; align-items: center; gap: 6px; font-size: var(--taille-s); cursor: pointer; }
.legende { margin: var(--e2) 0; }
.oui { color: var(--succes); } .non { color: var(--texte-leger); } .refus { color: var(--rouge); }
.modules { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: var(--e3); }
.module { padding: var(--e3); border: 1px solid var(--bordure); border-radius: var(--rayon); }
.module h3 { margin-bottom: var(--e2); font-size: var(--taille-s); color: var(--marine); }
.actions { display: flex; flex-wrap: wrap; gap: 4px; }
.action { display: inline-flex; align-items: center; gap: 4px; padding: 3px 9px; border: 1px solid var(--bordure); border-radius: 999px; background: var(--surface); font-size: var(--taille-xs); font-weight: 600; cursor: pointer; }
.action.oui { border-color: color-mix(in srgb, var(--succes) 40%, transparent); background: color-mix(in srgb, var(--succes) 8%, var(--surface)); }
.action.refus { border-color: color-mix(in srgb, var(--rouge) 40%, transparent); background: color-mix(in srgb, var(--rouge) 7%, var(--surface)); }
.action.non { color: var(--texte-doux); }
.action.ouverte { box-shadow: 0 0 0 2px var(--marine-clair); }
.raisons { margin-top: var(--e2); padding: var(--e2) var(--e3); border-radius: var(--rayon); background: var(--surface-douce); font-size: var(--taille-xs); }
.raisons ul { margin: 4px 0 0 16px; }
.comparaison { width: 100%; border-collapse: collapse; font-size: var(--taille-s); }
.comparaison th, .comparaison td { padding: 6px 8px; border-bottom: 1px solid var(--bordure); text-align: left; vertical-align: top; }
.comparaison tr.difference td { background: color-mix(in srgb, #f59e0b 8%, var(--surface)); }
.ok-texte { display: flex; align-items: center; gap: 6px; color: var(--succes); font-weight: 600; }
.ko-texte { color: var(--rouge); font-weight: 600; } .att-texte { color: #b45309; }
.ligne-actions { display: flex; align-items: center; justify-content: space-between; }
.anomalie { display: flex; flex-direction: column; gap: var(--e2); border-left: 4px solid var(--bordure-forte); }
.anomalie.erreur:not(.vide) { border-left-color: var(--rouge); }
.anomalie.attention:not(.vide) { border-left-color: #f59e0b; }
.anomalie.info:not(.vide) { border-left-color: var(--marine-clair); }
.anomalie.vide { border-left-color: var(--succes); }
.tete-anomalie { display: flex; align-items: center; gap: var(--e2); }
.tete-anomalie h2 { flex: 1; font-size: var(--taille-m); color: var(--marine); }
.anomalie.erreur .tete-anomalie > i { color: var(--rouge); } .anomalie.attention .tete-anomalie > i { color: #f59e0b; }
.anomalie.info .tete-anomalie > i { color: var(--marine-clair); } .anomalie.vide .tete-anomalie > i { color: var(--succes); }
.elements { list-style: none; display: flex; flex-direction: column; gap: 6px; }
.elements li { display: flex; flex-direction: column; padding: 6px 10px; border-radius: var(--rayon-s); background: var(--surface-douce); font-size: var(--taille-s); }
@media (max-width: 1000px) { .resume, .resume.deux, .choix-deux { grid-template-columns: 1fr; } }
</style>
