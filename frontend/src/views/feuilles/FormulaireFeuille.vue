<!--
  Google Sheet > Créer une nouvelle feuille (et modification d'une feuille : /google-sheet/feuilles/<id>/modifier).
  1. Nom  2. Affaires dont je suis responsable + leurs prestations  3. Critères de CTRL (commentaire obligatoire)
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { feuillesApi } from '@/api'
import { ApiErreur, messageErreur } from '@/api/client'
import { useConfirmation } from '@/composables/useConfirmation'
import { useToast } from '@/composables/useToast'
import type { AffaireDisponible, Feuille, Identifiant } from '@/types'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChamp from '@/components/ui/UiChamp.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'
import UiRecherche from '@/components/ui/UiRecherche.vue'
import UiSaisie from '@/components/ui/UiSaisie.vue'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const { confirmer } = useConfirmation()

const idFeuille = computed(() => (route.params.id ? Number(route.params.id) : null))
const modification = computed(() => idFeuille.value !== null)

const chargement = ref(true)
const affaires = ref<AffaireDisponible[]>([])
const feuilleInitiale = ref<Feuille | null>(null)
const recherche = ref('')

const nom = ref('')
/** Prestations cochées pour chaque affaire choisie : { affaireId: Set<prestationId> } */
const choix = reactive<Record<number, Set<Identifiant>>>({})
const utiliserCriteres = ref(true)
const nbCriteres = ref<number | ''>(0)
const criteres = ref<string[]>([])

const erreurs = ref<Record<string, any>>({})
const envoi = ref(false)

onMounted(async () => {
  try {
    affaires.value = await feuillesApi.affairesDisponibles(idFeuille.value)
    if (idFeuille.value) {
      const f = await feuillesApi.lire(idFeuille.value)
      feuilleInitiale.value = f
      nom.value = f.nom
      for (const p of f.perimetres) (choix[p.affaire] ??= new Set()).add(p.prestation)
      criteres.value = f.criteres.map((c) => c.commentaire)
      nbCriteres.value = criteres.value.length
      utiliserCriteres.value = f.utiliser_criteres
    }
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargement.value = false
  }
})

// Le nombre de critères ajuste la liste des commentaires
watch(nbCriteres, (n) => {
  const total = Math.max(0, Math.min(30, Number(n) || 0))
  criteres.value = Array.from({ length: total }, (_, i) => criteres.value[i] ?? '')
})

const affairesVisibles = computed(() => {
  const t = recherche.value.toLowerCase()
  return affaires.value.filter((a) => !t || `${a.num_affaire} ${a.nom}`.toLowerCase().includes(t))
})

const affaireChoisie = (id: Identifiant) => !!choix[id]
function basculerAffaire(a: AffaireDisponible) {
  if (choix[a.id]) delete choix[a.id]
  else choix[a.id] = new Set()
}
function toutCocher(a: AffaireDisponible) {
  const libres = a.prestations.filter((p) => !p.deja_dans).map((p) => p.id)
  const ensemble = (choix[a.id] ??= new Set())
  const tout = libres.every((id) => ensemble.has(id))
  libres.forEach((id) => (tout ? ensemble.delete(id) : ensemble.add(id)))
}
function basculerPrestation(affaire: Identifiant, prestation: Identifiant) {
  const ensemble = choix[affaire]!
  if (ensemble.has(prestation)) ensemble.delete(prestation)
  else ensemble.add(prestation)
}

const perimetres = computed(() =>
  Object.entries(choix).flatMap(([a, prestations]) => [...prestations].map((p) => ({ affaire: Number(a), prestation: p }))),
)
// Récapitulatif : prestations choisies et nombre de lignes créées (une par description)
const resume = computed(() => affaires.value.filter((a) => choix[a.id]?.size).map((a) => ({
  affaire: a,
  prestations: a.prestations.filter((p) => choix[a.id]!.has(p.id)),
})))
const nbLignes = computed(() => resume.value.reduce((t, r) => t + r.prestations.reduce((u, p) => u + (p.nb_descriptions ?? 0), 0), 0))
const nbCriteresUtilises = computed(() => (utiliserCriteres.value ? criteres.value.length : 0))
const etapesFaites = computed(() => [!!nom.value.trim(), perimetres.value.length > 0 && !affairesSansPrestation.value.length,
  !utiliserCriteres.value || criteres.value.every((c) => c.trim())])
const changerNbCriteres = (delta: number) => (nbCriteres.value = Math.max(0, Math.min(30, (Number(nbCriteres.value) || 0) + delta)))
const affairesSansPrestation = computed(() =>
  affaires.value.filter((a) => choix[a.id] && choix[a.id]!.size === 0).map((a) => a.nom),
)

async function enregistrer() {
  erreurs.value = {}
  if (!nom.value.trim()) erreurs.value.nom = 'Donnez un nom à la feuille.'
  if (!perimetres.value.length) erreurs.value.perimetres_saisis = 'Choisissez au moins une affaire et une de ses prestations.'
  if (affairesSansPrestation.value.length)
    erreurs.value.perimetres_saisis = `Cochez au moins une prestation pour : ${affairesSansPrestation.value.join(', ')}.`
  if (utiliserCriteres.value && criteres.value.some((c) => !c.trim()))
    erreurs.value.criteres_saisis = 'Chaque critère de CTRL doit avoir un commentaire.'
  if (Object.keys(erreurs.value).length) return

  // Modification : prévenir si des lignes ou des notes vont disparaître
  if (feuilleInitiale.value) {
    const retires = feuilleInitiale.value.perimetres.filter(
      (p) => !perimetres.value.some((n) => n.affaire === p.affaire && n.prestation === p.prestation),
    )
    const criteresRetires = utiliserCriteres.value ? feuilleInitiale.value.criteres.length - criteres.value.length : 0
    if (retires.length || criteresRetires > 0) {
      const ok = await confirmer({
        titre: 'Des données vont être supprimées',
        message: [
          retires.length ? `Les lignes de ${retires.map((r) => `« ${r.nom_prestation} » (${r.nom_affaire})`).join(', ')} seront supprimées.` : '',
          criteresRetires > 0 ? `Les notes des ${criteresRetires} dernier(s) critère(s) seront supprimées.` : '',
        ].filter(Boolean).join(' '),
        libelleConfirmer: 'Enregistrer quand même',
        danger: true,
      })
      if (!ok) return
    }
  }

  envoi.value = true
  try {
    const donnees = {
      nom: nom.value.trim(),
      utiliser_criteres: utiliserCriteres.value,
      perimetres_saisis: perimetres.value,
      criteres_saisis: utiliserCriteres.value ? criteres.value.map((c) => c.trim()) : [],
    }
    const feuille = idFeuille.value ? await feuillesApi.modifier(idFeuille.value, donnees) : await feuillesApi.creer(donnees)
    toast.succes(modification.value ? 'Feuille enregistrée' : 'Feuille créée')
    router.push(`/google-sheet/feuilles/${feuille.id}`)
  } catch (e) {
    if (e instanceof ApiErreur && Object.keys(e.erreurs).length) erreurs.value = e.erreurs
    else toast.erreur(messageErreur(e))
  } finally {
    envoi.value = false
  }
}
</script>

<template>
  <div class="page page-large">
    <EnTetePage
      :titre="modification ? 'Modifier la feuille' : 'Créer une nouvelle feuille'"
      description="Trois étapes : le nom, les affaires et leurs prestations (une ligne par description de leurs projets), puis les critères de contrôle."
    />

    <UiChargement v-if="chargement" />
    <form v-else class="disposition" novalidate @submit.prevent="enregistrer">
      <div class="etapes">
        <!-- 1. Nom -->
        <section class="carte etape" :class="{ faite: etapesFaites[0] }">
          <header class="tete-etape">
            <span class="numero"><i v-if="etapesFaites[0]" class="bi bi-check-lg" aria-hidden="true" /><template v-else>1</template></span>
            <div><h2>Nom de la feuille</h2><p class="texte-doux texte-petit">Un nom clair pour la retrouver dans Mes feuilles.</p></div>
          </header>
          <UiChamp v-slot="{ id }" libelle="Nom" requis :erreur="erreurs.nom">
            <UiSaisie :id="id" v-model="nom" placeholder="ex. Suivi saisie – novembre" :invalide="!!erreurs.nom" />
          </UiChamp>
        </section>

        <!-- 2. Affaires et prestations -->
        <section class="carte etape" :class="{ faite: etapesFaites[1] }">
          <header class="tete-etape">
            <span class="numero"><i v-if="etapesFaites[1]" class="bi bi-check-lg" aria-hidden="true" /><template v-else>2</template></span>
            <div><h2>Affaires et prestations</h2>
              <p class="texte-doux texte-petit">Les affaires où vous pouvez créer une feuille. Une prestation d’une affaire ne peut être que dans une seule feuille.</p></div>
          </header>
          <p v-if="erreurs.perimetres_saisis" class="alerte alerte-erreur" role="alert">
            <i class="bi bi-exclamation-triangle" aria-hidden="true" />{{ Array.isArray(erreurs.perimetres_saisis) ? erreurs.perimetres_saisis[0] : erreurs.perimetres_saisis }}
          </p>
          <UiEtatVide v-if="!affaires.length" icone="briefcase" titre="Aucune affaire disponible"
            texte="Il faut le droit « Créer » de Google Sheet > Mes feuilles sur au moins une affaire en cours." />
          <template v-else>
            <UiRecherche v-if="affaires.length > 4" v-model="recherche" placeholder="Rechercher une affaire" />
            <ul class="affaires">
              <li v-for="a in affairesVisibles" :key="a.id" class="affaire" :class="{ choisie: affaireChoisie(a.id) }">
                <div class="tete-affaire">
                  <label class="case-affaire">
                    <input type="checkbox" :checked="affaireChoisie(a.id)" @change="basculerAffaire(a)" />
                    <span class="nom-affaire"><span v-if="a.num_affaire" class="code">{{ a.num_affaire }}</span>{{ a.nom }}</span>
                  </label>
                  <span class="texte-xs texte-doux">{{ a.prestations.length }} prestation(s)</span>
                  <button v-if="affaireChoisie(a.id) && a.prestations.some((p) => !p.deja_dans)" type="button" class="lien" @click="toutCocher(a)">Tout cocher</button>
                </div>
                <div v-if="affaireChoisie(a.id)" class="prestations">
                  <span v-if="!a.prestations.length" class="texte-doux texte-xs">Aucune prestation cochée pour cette affaire dans Marchés.</span>
                  <label v-for="p in a.prestations" :key="p.id" class="tuile" :class="{ cochee: choix[a.id]?.has(p.id), prise: !!p.deja_dans }"
                    :title="p.deja_dans ? `Déjà dans la feuille « ${p.deja_dans} »` : ''">
                    <input type="checkbox" :checked="choix[a.id]?.has(p.id)" :disabled="!!p.deja_dans" @change="basculerPrestation(a.id, p.id)" />
                    <span class="tuile-texte">
                      <span class="gras">{{ p.nom }}</span>
                      <span v-if="p.deja_dans" class="texte-xs prise-texte"><i class="bi bi-lock" aria-hidden="true" /> déjà dans « {{ p.deja_dans }} »</span>
                      <span v-else class="texte-xs texte-doux">{{ p.nb_projets ?? 0 }} projet(s) · {{ p.nb_descriptions ?? 0 }} ligne(s)</span>
                    </span>
                  </label>
                </div>
              </li>
            </ul>
          </template>
        </section>

        <!-- 3. Critères de CTRL -->
        <section class="carte etape" :class="{ faite: etapesFaites[2] }">
          <header class="tete-etape">
            <span class="numero"><i v-if="etapesFaites[2]" class="bi bi-check-lg" aria-hidden="true" /><template v-else>3</template></span>
            <div class="large"><h2>Critères de contrôle</h2>
              <p class="texte-doux texte-petit">{{ utiliserCriteres
                ? 'Chaque critère devient une colonne notée de 1 à 5 ; la note de qualité est leur moyenne.'
                : 'Sans critère, la note de qualité est calculée d’après le temps de reprise (Paramètres > Rendement & Note).' }}</p></div>
            <label class="interrupteur-ligne">
              <input v-model="utiliserCriteres" type="checkbox" role="switch" />
              <span class="interrupteur" aria-hidden="true" /> Utiliser les critères
            </label>
          </header>
          <template v-if="utiliserCriteres">
            <div class="compteur">
              <span class="champ-libelle">Nombre de critères</span>
              <div class="pas-a-pas">
                <button type="button" aria-label="Un critère de moins" :disabled="!criteres.length" @click="changerNbCriteres(-1)"><i class="bi bi-dash-lg" aria-hidden="true" /></button>
                <input v-model.number="nbCriteres" type="number" min="0" max="30" aria-label="Nombre de critères" />
                <button type="button" aria-label="Un critère de plus" :disabled="criteres.length >= 30" @click="changerNbCriteres(1)"><i class="bi bi-plus-lg" aria-hidden="true" /></button>
              </div>
              <span class="texte-xs texte-doux">de 0 à 30</span>
            </div>
            <p v-if="erreurs.criteres_saisis" class="alerte alerte-erreur" role="alert">
              <i class="bi bi-exclamation-triangle" aria-hidden="true" />{{ Array.isArray(erreurs.criteres_saisis) ? erreurs.criteres_saisis[0] : erreurs.criteres_saisis }}
            </p>
            <ol v-if="criteres.length" class="criteres">
              <li v-for="(_, i) in criteres" :key="i" class="critere">
                <span class="numero-critere">{{ i + 1 }}</span>
                <input v-model="criteres[i]" class="saisie" :aria-label="`Commentaire du critère ${i + 1}`" placeholder="Ce qui est contrôlé (obligatoire)"
                  :aria-invalid="!!erreurs.criteres_saisis && !criteres[i]?.trim()" />
              </li>
            </ol>
            <button v-if="criteres.length < 30" type="button" class="ajouter-critere" @click="changerNbCriteres(1)">
              <i class="bi bi-plus-lg" aria-hidden="true" /> Ajouter un critère</button>
          </template>
        </section>
      </div>

      <!-- Récapitulatif -->
      <aside class="recapitulatif carte">
        <h2>Récapitulatif</h2>
        <dl>
          <div><dt>Nom</dt><dd :class="{ vide: !nom.trim() }">{{ nom.trim() || 'à indiquer' }}</dd></div>
          <div><dt>Affaires</dt><dd>{{ resume.length }}</dd></div>
          <div><dt>Prestations</dt><dd>{{ perimetres.length }}</dd></div>
          <div><dt>Lignes créées</dt><dd class="fort">{{ nbLignes }}</dd></div>
          <div><dt>Critères</dt><dd>{{ utiliserCriteres ? nbCriteresUtilises : 'non (temps de reprise)' }}</dd></div>
        </dl>
        <ul v-if="resume.length" class="choix">
          <li v-for="r in resume" :key="r.affaire.id">
            <span class="gras">{{ r.affaire.num_affaire ? `${r.affaire.num_affaire} – ` : '' }}{{ r.affaire.nom }}</span>
            <span class="texte-xs texte-doux">{{ r.prestations.map((p) => p.nom).join(', ') }}</span>
          </li>
        </ul>
        <p v-else class="texte-xs texte-doux">Cochez une affaire puis ses prestations.</p>
        <div class="boutons">
          <UiBouton type="submit" variante="primaire" :icone="modification ? 'check-lg' : 'file-earmark-plus'" :chargement="envoi">
            {{ modification ? 'Enregistrer' : 'Créer la feuille' }}
          </UiBouton>
          <UiBouton @click="router.back()">Annuler</UiBouton>
        </div>
      </aside>
    </form>
  </div>
</template>

<style scoped>
.page-large { max-width: 1200px; }
.disposition { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: var(--e4); align-items: start; }
.etapes { display: flex; flex-direction: column; gap: var(--e4); min-width: 0; }
.etape { display: flex; flex-direction: column; gap: var(--e3); padding: var(--e4); border-left: 4px solid var(--bordure-forte); }
.etape.faite { border-left-color: var(--succes); }
.tete-etape { display: flex; align-items: flex-start; gap: var(--e3); }
.tete-etape .large { flex: 1; }
.tete-etape h2 { font-size: var(--taille-m); color: var(--marine); }
.numero { display: grid; place-items: center; width: 32px; height: 32px; flex: none; border-radius: 50%; background: var(--marine); color: #fff; font-weight: 800; }
.faite .numero { background: var(--succes); }
.affaires { list-style: none; display: flex; flex-direction: column; gap: var(--e2); }
.affaire { border: 1px solid var(--bordure); border-radius: var(--rayon); transition: border-color 0.15s; }
.affaire.choisie { border-color: var(--marine-clair); box-shadow: 0 0 0 3px var(--marine-pale); }
.tete-affaire { display: flex; align-items: center; gap: var(--e3); padding: var(--e3); }
.case-affaire { display: flex; align-items: center; gap: var(--e2); flex: 1; cursor: pointer; }
.nom-affaire { display: flex; align-items: center; gap: var(--e2); font-weight: 600; }
.code { padding: 1px 8px; border-radius: 6px; background: var(--marine-pale); color: var(--marine); font-size: var(--taille-xs); font-weight: 800; }
.lien { border: none; background: none; color: var(--marine-clair); font-size: var(--taille-s); font-weight: 600; cursor: pointer; }
.prestations { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: var(--e2); padding: 0 var(--e3) var(--e3); }
.tuile { display: flex; align-items: flex-start; gap: var(--e2); padding: var(--e2) var(--e3); border: 1px solid var(--bordure); border-radius: var(--rayon); background: var(--surface); cursor: pointer; }
.tuile input { margin-top: 3px; }
.tuile.cochee { border-color: var(--marine); background: var(--marine-pale); }
.tuile.prise { cursor: not-allowed; opacity: 0.65; background: var(--surface-douce); }
.tuile-texte { display: flex; flex-direction: column; min-width: 0; }
.prise-texte { color: var(--attention); font-weight: 600; }
.interrupteur-ligne { display: flex; align-items: center; gap: var(--e2); flex: none; font-weight: 600; font-size: var(--taille-s); cursor: pointer; }
.interrupteur-ligne input { position: absolute; opacity: 0; }
.interrupteur { position: relative; width: 40px; height: 22px; border-radius: 999px; background: var(--bordure-forte); transition: background 0.15s; }
.interrupteur::after { content: ''; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: #fff; transition: transform 0.15s; }
.interrupteur-ligne input:checked + .interrupteur { background: var(--marine); }
.interrupteur-ligne input:checked + .interrupteur::after { transform: translateX(18px); }
.interrupteur-ligne input:focus-visible + .interrupteur { outline: 2px solid var(--marine-clair); outline-offset: 2px; }
.compteur { display: flex; align-items: center; gap: var(--e3); }
.pas-a-pas { display: inline-flex; border: 1px solid var(--bordure-forte); border-radius: var(--rayon); overflow: hidden; }
.pas-a-pas button { width: 36px; border: none; background: var(--surface-douce); color: var(--marine); cursor: pointer; }
.pas-a-pas button:disabled { opacity: 0.4; cursor: default; }
.pas-a-pas input { width: 56px; border: none; text-align: center; font-weight: 700; }
.criteres { list-style: none; display: flex; flex-direction: column; gap: var(--e2); }
.critere { display: flex; align-items: center; gap: var(--e3); }
.numero-critere { display: grid; place-items: center; width: 28px; height: 28px; flex: none; border-radius: 8px; background: var(--marine-pale); color: var(--marine); font-weight: 800; font-size: var(--taille-s); }
.critere .saisie { flex: 1; }
.ajouter-critere { align-self: flex-start; display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border: 1px dashed var(--bordure-forte); border-radius: var(--rayon); background: none; color: var(--marine); font-weight: 600; cursor: pointer; }
.recapitulatif { position: sticky; top: 76px; display: flex; flex-direction: column; gap: var(--e3); padding: var(--e4); }
.recapitulatif h2 { font-size: var(--taille-m); color: var(--marine); }
.recapitulatif dl { display: flex; flex-direction: column; gap: 6px; }
.recapitulatif dl div { display: flex; justify-content: space-between; gap: var(--e2); font-size: var(--taille-s); }
.recapitulatif dt { color: var(--texte-doux); }
.recapitulatif dd { font-weight: 700; text-align: right; }
.recapitulatif dd.vide { color: var(--texte-leger); font-weight: 400; font-style: italic; }
.recapitulatif dd.fort { color: var(--marine); font-size: var(--taille-l); }
.choix { list-style: none; display: flex; flex-direction: column; gap: var(--e2); padding-top: var(--e2); border-top: 1px solid var(--bordure); }
.choix li { display: flex; flex-direction: column; font-size: var(--taille-s); }
.boutons { display: flex; flex-direction: column; gap: var(--e2); }
@media (max-width: 1000px) { .disposition { grid-template-columns: 1fr; } .recapitulatif { position: static; } }
</style>
