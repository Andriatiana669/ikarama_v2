<!--
  Paramètres > Temps Estimatif (administrateurs).
    Temps Estimatif = Quantité ÷ Rendement objectif par jour (jours ; × heures par jour pour des heures).
    Ligne rouge : Temps de prod ≥ Temps Estimatif ; orange : Temps de prod ≥ (100 − marge) % du Temps Estimatif.
    Plus de couleur quand la ligne a le statut qui « Active la note de rendement ».
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { tempsEstimatifApi } from '@/api'
import type { ParametresTempsEstimatif } from '@/api/gsheets'
import { messageErreur } from '@/api/client'
import { useToast } from '@/composables/useToast'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiCouleur from '@/components/ui/UiCouleur.vue'

const toast = useToast()
const p = ref<ParametresTempsEstimatif | null>(null)
const envoi = ref(false)
onMounted(async () => {
  try {
    p.value = await tempsEstimatifApi.lire()
  } catch (e) {
    toast.erreur(e)
  }
})
const seuilOrange = computed(() => (p.value ? 100 - p.value.marge : 80))

async function enregistrer() {
  if (!p.value) return
  envoi.value = true
  try {
    p.value = await tempsEstimatifApi.enregistrer(p.value)
    toast.succes('Paramètres du Temps Estimatif enregistrés')
  } catch (e) {
    toast.erreur(messageErreur(e))
  } finally {
    envoi.value = false
  }
}
</script>

<template>
  <div class="page pile">
    <EnTetePage titre="Temps Estimatif" description="Le temps à passer sur une ligne de feuille, d'après sa quantité et le Rendement objectif, et ses couleurs d'alerte.">
      <UiBouton variante="primaire" icone="check-lg" :chargement="envoi" :desactive="!p" @click="enregistrer">Enregistrer</UiBouton>
    </EnTetePage>

    <UiChargement v-if="!p" />
    <template v-else>
      <section class="carte carte-corps pile">
        <h2 class="titre-section"><i class="bi bi-calculator" aria-hidden="true" /> Calcul</h2>
        <p class="formule">Temps Estimatif = Quantité ÷ Rendement objectif par jour
          <span class="texte-doux">({{ p.heures_par_jour ?? 8 }} h par jour, réglé dans Paramètres > Rendement &amp; Note)</span></p>
        <div class="champ">
          <span class="champ-libelle">Unité par défaut dans les feuilles</span>
          <div class="bascule" role="radiogroup" aria-label="Unité par défaut">
            <button type="button" role="radio" :aria-checked="p.unite === 'heures'" :class="{ actif: p.unite === 'heures' }" @click="p.unite = 'heures'">Heures</button>
            <button type="button" role="radio" :aria-checked="p.unite === 'jours'" :class="{ actif: p.unite === 'jours' }" @click="p.unite = 'jours'">Jours</button>
          </div>
          <span class="champ-aide">Chacun peut basculer entre heures et jours dans la feuille.</span>
        </div>
      </section>

      <section class="carte carte-corps pile">
        <h2 class="titre-section"><i class="bi bi-palette" aria-hidden="true" /> Couleurs des lignes</h2>
        <div class="regles">
          <div class="regle">
            <span class="champ-libelle">Dépassé : Temps de prod ≥ Temps Estimatif</span>
            <UiCouleur v-model="p.couleur_rouge" />
          </div>
          <div class="regle">
            <span class="champ-libelle">Proche : Temps de prod ≥ {{ seuilOrange }} % du Temps Estimatif</span>
            <UiCouleur v-model="p.couleur_orange" />
            <label class="marge">Marge
              <input v-model.number="p.marge" class="saisie" type="number" min="0" max="99" step="1" aria-label="Marge en %" /> %
            </label>
          </div>
        </div>
        <p class="texte-petit texte-doux">La couleur disparaît dès que la ligne a le statut qui « Active la note de rendement » (Marchés > Statuts).</p>

        <div class="apercu" aria-label="Aperçu">
          <span class="texte-xs texte-doux">Aperçu, pour un Temps Estimatif de 10 h :</span>
          <div class="ligne-apercu">Temps de prod 6 h : pas de couleur</div>
          <div class="ligne-apercu" :style="{ background: `color-mix(in srgb, ${p.couleur_orange} 16%, var(--surface))`, boxShadow: `inset 4px 0 0 ${p.couleur_orange}` }">
            Temps de prod {{ Math.max(seuilOrange / 10, 0).toLocaleString('fr-FR') }} h : proche
          </div>
          <div class="ligne-apercu" :style="{ background: `color-mix(in srgb, ${p.couleur_rouge} 16%, var(--surface))`, boxShadow: `inset 4px 0 0 ${p.couleur_rouge}` }">
            Temps de prod 10 h ou plus : dépassé
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.titre-section { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-m); color: var(--marine); }
.formule { font-weight: 600; }
.bascule { display: inline-flex; width: fit-content; border: 1px solid var(--bordure-forte); border-radius: var(--rayon); overflow: hidden; }
.bascule button { padding: 6px 16px; border: none; background: var(--surface); font-weight: 600; color: var(--texte-doux); cursor: pointer; }
.bascule button.actif { background: var(--marine); color: #fff; }
.regles { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: var(--e4); }
.regle { display: flex; flex-direction: column; gap: var(--e2); }
.marge { display: inline-flex; align-items: center; gap: var(--e2); font-size: var(--taille-s); font-weight: 600; }
.marge .saisie { width: 80px; text-align: right; }
.apercu { display: flex; flex-direction: column; gap: 4px; max-width: 480px; }
.ligne-apercu { padding: var(--e2) var(--e3); border: 1px solid var(--bordure); border-radius: var(--rayon-s); font-size: var(--taille-s); }
</style>
