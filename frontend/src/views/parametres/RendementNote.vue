<!--
  Paramètres > Rendement & Note : réglage des formules des feuilles (communes à toutes les feuilles).
  Calculs côté serveur : backend/rendements/calculs.py
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { parametresRendementApi } from '@/api'
import { ApiErreur } from '@/api/client'
import { useConfirmation } from '@/composables/useConfirmation'
import { useToast } from '@/composables/useToast'
import type { ParametresRendement, TrancheReprise } from '@/types'
import { formatDateHeure, formatNombre } from '@/utils/format'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChamp from '@/components/ui/UiChamp.vue'
import UiChargement from '@/components/ui/UiChargement.vue'

const toast = useToast()
const { confirmer } = useConfirmation()
const parametres = ref<ParametresRendement | null>(null)
const erreurs = ref<Record<string, any>>({})
const envoi = ref(false)

const versNombres = (p: ParametresRendement): ParametresRendement => ({
  ...p,
  tranches_reprise: p.tranches_reprise.map((t) => ({ jusqua: t.jusqua === null ? null : Number(t.jusqua), note: Number(t.note) })),
})
onMounted(async () => {
  try {
    parametres.value = versNombres(await parametresRendementApi.lire())
  } catch (e) {
    toast.erreur(e)
  }
})

// --- Tranches de la note de qualité (sans critère) ---
const tranches = computed(() => parametres.value?.tranches_reprise ?? [])
const debutTranche = (i: number) => (i === 0 ? 0 : Number(tranches.value[i - 1]?.jusqua ?? 0))
function ajouterTranche() {
  const liste = tranches.value
  const avantDerniere = liste.length > 1 ? Number(liste[liste.length - 2]!.jusqua) : 0
  liste.splice(liste.length - 1, 0, { jusqua: Math.min(avantDerniere + 10, 99), note: 1 })
}
const retirerTranche = (i: number) => tranches.value.splice(i, 1)

// --- Exemple de calcul en direct ---
const exemple = ref({ quantite: 1000, objectif: 120, prod: 6, controle: 1, reprise: 1 })
const resultat = computed(() => {
  const p = parametres.value
  if (!p) return null
  const h = Number(p.heures_par_jour)
  const { quantite, objectif, prod, controle, reprise } = exemple.value
  const rProd = prod ? (quantite / prod) * h : null
  const total = prod + (controle || 0) + (reprise || 0)
  const rTotal = total ? (quantite / total) * h : null
  const nRend = rTotal !== null && objectif ? Math.min(Number(p.note_max), (Number(p.note_objectif) * rTotal) / objectif) : null
  const pct = prod ? ((reprise || 0) / prod) * 100 : null
  const tranche = pct === null ? null : p.tranches_reprise.find((t) => t.jusqua === null || pct < Number(t.jusqua))
  return { rProd, rTotal, nRend, pct, nQual: tranche ? Number(tranche.note) : null }
})

async function enregistrer() {
  if (!parametres.value) return
  envoi.value = true
  erreurs.value = {}
  try {
    parametres.value = versNombres(await parametresRendementApi.enregistrer(parametres.value))
    toast.succes('Paramètres enregistrés : toutes les feuilles utilisent les nouvelles formules')
  } catch (e) {
    if (e instanceof ApiErreur) erreurs.value = e.erreurs
    toast.erreur(e)
  } finally {
    envoi.value = false
  }
}

async function reinitialiser() {
  if (!(await confirmer({ titre: "Revenir aux valeurs d'origine ?", message: '8 h par jour, note 2,5 à l’objectif, note maximale 5, critères de 1 à 5, tranches 15 / 35 / 55 / 85 %.', libelleConfirmer: 'Réinitialiser', danger: true }))) return
  parametres.value = versNombres(await parametresRendementApi.reinitialiser())
  toast.succes("Valeurs d'origine rétablies")
}

const premiere = (cle: string) => {
  const e = erreurs.value[cle]
  return Array.isArray(e) ? (typeof e[0] === 'string' ? e[0] : 'Valeur invalide.') : e
}
</script>

<template>
  <div class="page">
    <EnTetePage
      titre="Rendement & Note"
      description="Réglages des formules utilisées dans toutes les feuilles (Google Sheet). Les colonnes calculées se mettent à jour immédiatement."
    >
      <UiBouton icone="arrow-counterclockwise" @click="reinitialiser">Valeurs d'origine</UiBouton>
      <UiBouton variante="primaire" icone="check-lg" :chargement="envoi" @click="enregistrer">Enregistrer</UiBouton>
    </EnTetePage>

    <UiChargement v-if="!parametres" />
    <div v-else class="disposition">
      <div class="pile">
        <section class="carte">
          <header class="carte-entete"><h2>Rendements</h2></header>
          <div class="carte-corps pile">
            <p class="formule">Rendement prod = Quantité ÷ Temps de prod × <strong>{{ formatNombre(parametres.heures_par_jour) }}</strong></p>
            <p class="formule">Rendement total = Quantité ÷ (Temps de prod + Temps de contrôle + Temps de reprise) × <strong>{{ formatNombre(parametres.heures_par_jour) }}</strong></p>
            <UiChamp v-slot="{ id }" libelle="Heures par jour" aide="Les temps sont en heures : le rendement est ramené à une journée." :erreur="premiere('heures_par_jour')">
              <input :id="id" v-model="parametres.heures_par_jour" class="saisie court" inputmode="decimal" />
            </UiChamp>
          </div>
        </section>

        <section class="carte">
          <header class="carte-entete"><h2>Note de rendement</h2></header>
          <div class="carte-corps pile">
            <p class="formule">
              Note = <strong>{{ formatNombre(parametres.note_objectif) }}</strong> × (Rendement total ÷ Rendement objectif / j),
              au plus <strong>{{ formatNombre(parametres.note_max) }}</strong>
            </p>
            <div class="grille-2">
              <UiChamp v-slot="{ id }" libelle="Note quand l'objectif est atteint" :erreur="premiere('note_objectif')">
                <input :id="id" v-model="parametres.note_objectif" class="saisie" inputmode="decimal" />
              </UiChamp>
              <UiChamp v-slot="{ id }" libelle="Note maximale" :erreur="premiere('note_max')">
                <input :id="id" v-model="parametres.note_max" class="saisie" inputmode="decimal" />
              </UiChamp>
            </div>
          </div>
        </section>

        <section class="carte">
          <header class="carte-entete"><h2>Note de qualité</h2></header>
          <div class="carte-corps pile">
            <h3>Feuille avec critères de CTRL</h3>
            <p class="formule">Note = moyenne des critères remplis ; chaque critère est noté entre les bornes ci-dessous.</p>
            <div class="grille-2">
              <UiChamp v-slot="{ id }" libelle="Note minimale d'un critère" :erreur="premiere('note_critere_min')">
                <input :id="id" v-model="parametres.note_critere_min" class="saisie" inputmode="decimal" />
              </UiChamp>
              <UiChamp v-slot="{ id }" libelle="Note maximale d'un critère" :erreur="premiere('note_critere_max')">
                <input :id="id" v-model="parametres.note_critere_max" class="saisie" inputmode="decimal" />
              </UiChamp>
            </div>

            <h3>Feuille sans critère</h3>
            <p class="formule">Pourcentage = Temps de reprise ÷ Temps de prod × 100, puis la note de sa tranche :</p>
            <p v-if="premiere('tranches_reprise')" class="alerte alerte-erreur"><i class="bi bi-exclamation-triangle" aria-hidden="true" />{{ premiere('tranches_reprise') }}</p>
            <table class="tableau tranches">
              <thead><tr><th>De</th><th>Jusqu'à (exclu)</th><th>Note</th><th /></tr></thead>
              <tbody>
                <tr v-for="(t, i) in tranches" :key="i">
                  <td>{{ formatNombre(debutTranche(i)) }} %</td>
                  <td>
                    <span v-if="t.jusqua === null" class="texte-doux">et plus</span>
                    <span v-else class="ligne"><input v-model.number="(t as TrancheReprise).jusqua" class="saisie court" inputmode="decimal" :aria-label="`Limite de la tranche ${i + 1}`" /> %</span>
                  </td>
                  <td><input v-model.number="(t as TrancheReprise).note" class="saisie court" inputmode="decimal" :aria-label="`Note de la tranche ${i + 1}`" /></td>
                  <td class="droite">
                    <UiBouton v-if="t.jusqua !== null && tranches.length > 2" variante="fantome" icone="trash" petit icone-seule @click="retirerTranche(i)">Retirer</UiBouton>
                  </td>
                </tr>
              </tbody>
            </table>
            <div><UiBouton variante="fantome" icone="plus-lg" petit @click="ajouterTranche">Ajouter une tranche</UiBouton></div>
          </div>
        </section>
        <p class="texte-xs texte-doux">Dernière modification : {{ formatDateHeure(parametres.modifie_le) }}</p>
      </div>

      <aside class="carte exemple">
        <header class="carte-entete"><h2>Essayer</h2></header>
        <div class="carte-corps pile">
          <p class="texte-xs texte-doux">Exemple de calcul avec les réglages affichés (non enregistrés compris).</p>
          <div class="grille-2">
            <UiChamp v-slot="{ id }" libelle="Quantité"><input :id="id" v-model.number="exemple.quantite" class="saisie" inputmode="decimal" /></UiChamp>
            <UiChamp v-slot="{ id }" libelle="Objectif / j"><input :id="id" v-model.number="exemple.objectif" class="saisie" inputmode="decimal" /></UiChamp>
            <UiChamp v-slot="{ id }" libelle="Temps de prod (h)"><input :id="id" v-model.number="exemple.prod" class="saisie" inputmode="decimal" /></UiChamp>
            <UiChamp v-slot="{ id }" libelle="Contrôle (h)"><input :id="id" v-model.number="exemple.controle" class="saisie" inputmode="decimal" /></UiChamp>
            <UiChamp v-slot="{ id }" libelle="Reprise (h)"><input :id="id" v-model.number="exemple.reprise" class="saisie" inputmode="decimal" /></UiChamp>
          </div>
          <dl v-if="resultat" class="fiche">
            <dt>Rendement prod</dt><dd>{{ formatNombre(resultat.rProd) }}</dd>
            <dt>Rendement total</dt><dd>{{ formatNombre(resultat.rTotal) }}</dd>
            <dt>Note de rendement</dt><dd>{{ formatNombre(resultat.nRend) }}</dd>
            <dt>Reprise / prod</dt><dd>{{ resultat.pct === null ? '—' : `${formatNombre(resultat.pct)} %` }}</dd>
            <dt>Note de qualité (sans critère)</dt><dd>{{ formatNombre(resultat.nQual) }}</dd>
          </dl>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.disposition { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: var(--e4); align-items: start; }
.formule { padding: var(--e2) var(--e3); border-radius: var(--rayon); background: var(--surface-douce); font-size: var(--taille-s); }
.court { width: 110px; }
h3 { margin-top: var(--e2); }
.tranches { max-width: 520px; }
.tranches td { padding: var(--e2) var(--e3); }
.exemple { position: sticky; top: calc(var(--hauteur-barre) + var(--e4)); }
@media (max-width: 1100px) { .disposition { grid-template-columns: 1fr; } .exemple { position: static; } }
</style>
