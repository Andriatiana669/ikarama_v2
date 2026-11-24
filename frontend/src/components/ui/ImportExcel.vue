<!--
  Import Excel en deux étapes, pour n'importe quelle ressource qui propose modele/ et importer/ :
    1. on choisit le fichier -> aperçu ligne par ligne (rien n'est encore enregistré) ;
    2. on confirme -> les lignes valides sont importées, les lignes en erreur ignorées.
  <ImportExcel v-model="ouvert" titre="Importer des prestations" nom-modele="Modele_prestations"
               :source="prestationsApi" @importe="recharger" />
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { messageErreur } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { RapportImport } from '@/types'
import { pluriel } from '@/utils/format'
import UiBouton from './UiBouton.vue'
import UiModale from './UiModale.vue'

const ouvert = defineModel<boolean>({ default: false })
const props = defineProps<{
  titre: string
  nomModele: string
  source: {
    telechargerModele: (nom: string) => Promise<void>
    importer: (fichier: File, simulation: boolean) => Promise<RapportImport>
  }
}>()
const emit = defineEmits<{ importe: [rapport: RapportImport] }>()

const toast = useToast()
const fichier = ref<File | null>(null)
const apercu = ref<RapportImport | null>(null)
const erreurFichier = ref('')
const chargement = ref(false)
const import_ = ref(false)
const survol = ref(false)
const seulementErreurs = ref(false)

watch(ouvert, (valeur) => valeur && reinitialiser())
function reinitialiser() {
  fichier.value = null
  apercu.value = null
  erreurFichier.value = ''
  seulementErreurs.value = false
}

async function choisir(f: File | undefined | null) {
  if (!f) return
  reinitialiser()
  fichier.value = f
  chargement.value = true
  try {
    apercu.value = await props.source.importer(f, true)
    seulementErreurs.value = apercu.value.erreurs > 0 && apercu.value.erreurs < apercu.value.total
  } catch (e) {
    erreurFichier.value = messageErreur(e)
  } finally {
    chargement.value = false
  }
}
function deposer(e: DragEvent) {
  survol.value = false
  choisir(e.dataTransfer?.files?.[0])
}

const valides = computed(() => (apercu.value ? apercu.value.crees + apercu.value.modifies : 0))
const lignes = computed(() =>
  (apercu.value?.lignes ?? []).filter((l) => !seulementErreurs.value || l.action === 'erreur'),
)

async function importer() {
  if (!fichier.value) return
  import_.value = true
  try {
    const rapport = await props.source.importer(fichier.value, false)
    toast.succes(
      `Import terminé : ${pluriel(rapport.crees, 'création')}, ${pluriel(rapport.modifies, 'mise à jour', 'mises à jour')}` +
        (rapport.erreurs ? `, ${pluriel(rapport.erreurs, 'ligne ignorée', 'lignes ignorées')}.` : '.'),
    )
    emit('importe', rapport)
    ouvert.value = false
  } catch (e) {
    toast.erreur(e)
  } finally {
    import_.value = false
  }
}

async function modele() {
  try {
    await props.source.telechargerModele(props.nomModele)
  } catch (e) {
    toast.erreur(e)
  }
}

const ACTIONS = {
  creation: { libelle: 'À créer', classe: 'badge-succes' },
  modification: { libelle: 'À mettre à jour', classe: 'badge-marine' },
  inchange: { libelle: 'Inchangée', classe: '' },
  erreur: { libelle: 'Erreur', classe: 'badge-rouge' },
} as const
</script>

<template>
  <UiModale v-model="ouvert" :titre="titre" taille="grande" :bloquante="import_">
    <div class="pile">
      <div class="ligne-entre etape">
        <p class="texte-petit texte-doux">
          Partez du modèle : il contient les bonnes colonnes et un onglet « Aide » avec des exemples.
        </p>
        <UiBouton icone="file-earmark-arrow-down" petit @click="modele">Télécharger le modèle</UiBouton>
      </div>

      <label
        class="depot"
        :class="{ survol, rempli: fichier }"
        @dragover.prevent="survol = true"
        @dragleave="survol = false"
        @drop.prevent="deposer"
      >
        <input type="file" accept=".xlsx" class="masque-visuel" @change="choisir(($event.target as HTMLInputElement).files?.[0])" />
        <i class="bi bi-file-earmark-excel" aria-hidden="true" />
        <span v-if="fichier" class="gras">{{ fichier.name }}</span>
        <span v-else><span class="gras">Choisissez un fichier .xlsx</span> ou déposez-le ici</span>
        <span class="texte-xs texte-doux">5 Mo et 2 000 lignes au maximum</span>
      </label>

      <p v-if="chargement" class="texte-doux texte-petit"><i class="bi bi-hourglass-split" aria-hidden="true" /> Lecture du fichier et vérification des lignes…</p>
      <p v-if="erreurFichier" class="alerte alerte-erreur" role="alert"><i class="bi bi-exclamation-triangle" aria-hidden="true" />{{ erreurFichier }}</p>

      <template v-if="apercu">
        <div class="resume">
          <span class="badge badge-succes">{{ pluriel(apercu.crees, 'à créer', 'à créer') }}</span>
          <span class="badge badge-marine">{{ pluriel(apercu.modifies, 'à mettre à jour', 'à mettre à jour') }}</span>
          <span v-if="apercu.inchanges" class="badge">{{ pluriel(apercu.inchanges, 'inchangée', 'inchangées') }}</span>
          <span class="badge" :class="apercu.erreurs ? 'badge-rouge' : ''">{{ pluriel(apercu.erreurs, 'erreur') }}</span>
          <label v-if="apercu.erreurs" class="case texte-petit filtre"><input v-model="seulementErreurs" type="checkbox" /> Seulement les erreurs</label>
        </div>
        <p class="alerte texte-petit"><i class="bi bi-info-circle" aria-hidden="true" />Aperçu : rien n'est encore enregistré. Les lignes en erreur seront ignorées.</p>

        <div class="tableau-conteneur liste">
          <table class="tableau">
            <thead><tr><th>Ligne Excel</th><th>Résultat</th><th>Élément</th><th>Détail</th></tr></thead>
            <tbody>
              <tr v-for="l in lignes" :key="l.numero" :class="{ erreur: l.action === 'erreur' }">
                <td class="code">{{ l.numero }}</td>
                <td><span class="badge" :class="ACTIONS[l.action].classe">{{ ACTIONS[l.action].libelle }}</span></td>
                <td class="gras">{{ l.libelle }}</td>
                <td>
                  <ul v-if="l.messages.length" class="messages" :class="{ avertissements: l.action !== 'erreur' }"><li v-for="(m, i) in l.messages" :key="i">{{ m }}</li></ul>
                  <span v-else class="texte-doux">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>

    <template #pied>
      <UiBouton :desactive="import_" @click="ouvert = false">Annuler</UiBouton>
      <UiBouton variante="primaire" icone="upload" :chargement="import_" :desactive="!apercu || !valides" @click="importer">
        {{ apercu ? `Importer ${pluriel(valides, 'ligne')}` : 'Importer' }}
      </UiBouton>
    </template>
  </UiModale>
</template>

<style scoped>
.etape { align-items: center; }
.depot {
  display: flex; flex-direction: column; align-items: center; gap: var(--e1);
  padding: var(--e5); border: 2px dashed var(--bordure-forte); border-radius: var(--rayon-l);
  background: var(--surface-douce); cursor: pointer; text-align: center; transition: border-color var(--transition), background var(--transition);
}
.depot .bi { font-size: 1.75rem; color: var(--succes); }
.depot:hover, .depot.survol { border-color: var(--marine-clair); background: var(--marine-pale); }
.depot.rempli { border-style: solid; }
.depot:focus-within { box-shadow: var(--anneau-focus); }
.resume { display: flex; align-items: center; gap: var(--e2); flex-wrap: wrap; }
.filtre { margin-left: auto; }
.liste { max-height: 340px; overflow-y: auto; border: 1px solid var(--bordure); border-radius: var(--rayon); }
tr.erreur td { background: var(--rouge-pale); }
.messages { margin: 0; padding-left: 1rem; font-size: var(--taille-s); color: var(--danger); }
/* Ligne importée malgré des avertissements (ex. personne introuvable) */
.messages.avertissements { color: var(--attention); }
</style>
