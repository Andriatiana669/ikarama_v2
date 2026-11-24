<!--
  Paramètres > Contrôles de cohérence (administrateurs) : problèmes à corriger, avec un lien pour chacun
  (calculs : backend/ikarama/controles.py).
-->
<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { controlesApi } from '@/api'
import type { Controle } from '@/api/notifications'
import { useToast } from '@/composables/useToast'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'

const route = useRoute()
const toast = useToast()
const liste = ref<Controle[] | null>(null)
const total = ref(0)
const ouverts = ref<Set<string>>(new Set())
const chargement = ref(false)

async function charger() {
  chargement.value = true
  try {
    const r = await controlesApi()
    liste.value = r.controles
    total.value = r.total
    const ancre = route.hash.replace('#', '')
    if (ancre) {
      ouverts.value.add(ancre)
      await nextTick()
      document.getElementById(ancre)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  } catch (e) {
    toast.erreur(e)
  } finally {
    chargement.value = false
  }
}
onMounted(charger)
const basculer = (code: string) => (ouverts.value.has(code) ? ouverts.value.delete(code) : ouverts.value.add(code))
const LIBELLES: Record<string, string> = { erreur: 'À corriger', attention: 'À vérifier', info: 'Information' }
</script>

<template>
  <div class="page pile">
    <EnTetePage titre="Contrôles de cohérence" description="Les données incomplètes ou incohérentes, avec un lien vers la page où les corriger.">
      <UiBouton icone="arrow-clockwise" :chargement="chargement" @click="charger">Relancer les contrôles</UiBouton>
    </EnTetePage>
    <UiChargement v-if="!liste" />
    <template v-else>
      <p class="resume" :class="{ propre: !total }">
        <i class="bi" :class="total ? 'bi-exclamation-triangle' : 'bi-check-circle-fill'" aria-hidden="true" />
        {{ total ? `${total} point(s) à regarder` : 'Aucun problème détecté.' }}
      </p>
      <section v-for="c in liste" :id="c.code" :key="c.code" class="carte controle" :class="[c.gravite, { vide: !c.nombre }]">
        <button type="button" class="tete" :aria-expanded="ouverts.has(c.code)" :disabled="!c.nombre" @click="basculer(c.code)">
          <span class="nombre">{{ c.nombre }}</span>
          <span class="textes"><span class="titre">{{ c.titre }}</span><span class="texte-xs texte-doux">{{ c.explication }}</span></span>
          <span class="gravite">{{ c.nombre ? LIBELLES[c.gravite] : 'OK' }}</span>
          <i v-if="c.nombre" class="bi" :class="ouverts.has(c.code) ? 'bi-chevron-up' : 'bi-chevron-down'" aria-hidden="true" />
        </button>
        <ul v-if="ouverts.has(c.code) && c.nombre" class="elements">
          <li v-for="(e, i) in c.elements" :key="i">
            <span class="gras">{{ e.libelle }}</span>
            <span v-if="e.detail" class="texte-xs texte-doux">{{ e.detail }}</span>
            <RouterLink v-if="e.lien" :to="e.lien" class="corriger">Corriger <i class="bi bi-arrow-right" aria-hidden="true" /></RouterLink>
          </li>
          <li v-if="c.nombre > c.elements.length" class="texte-xs texte-doux">… et {{ c.nombre - c.elements.length }} autre(s).</li>
        </ul>
      </section>
    </template>
  </div>
</template>

<style scoped>
.resume { display: flex; align-items: center; gap: var(--e2); font-weight: 700; color: var(--attention); }
.resume.propre { color: var(--succes); }
.controle { overflow: hidden; border-left: 5px solid var(--bordure-forte); }
.controle.erreur { border-left-color: var(--rouge); }
.controle.attention { border-left-color: var(--attention); }
.controle.info { border-left-color: var(--marine-clair); }
.controle.vide { border-left-color: var(--succes); opacity: 0.75; }
.tete { display: flex; align-items: center; gap: var(--e3); width: 100%; padding: var(--e3) var(--e4); border: none; background: none; text-align: left; cursor: pointer; }
.tete:disabled { cursor: default; }
.nombre { min-width: 42px; padding: 2px 10px; border-radius: 999px; background: var(--surface-douce); font-weight: 700; text-align: center; color: var(--marine); }
.erreur .nombre { background: color-mix(in srgb, var(--rouge) 14%, transparent); color: var(--rouge); }
.attention .nombre { background: color-mix(in srgb, var(--attention) 16%, transparent); color: var(--attention); }
.vide .nombre { background: color-mix(in srgb, var(--succes) 15%, transparent); color: var(--succes); }
.textes { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.titre { font-weight: 700; color: var(--texte); }
.gravite { font-size: var(--taille-xs); font-weight: 700; color: var(--texte-doux); text-transform: uppercase; letter-spacing: 0.03em; }
.elements { list-style: none; border-top: 1px solid var(--bordure); }
.elements li { display: flex; align-items: center; gap: var(--e3); flex-wrap: wrap; padding: var(--e2) var(--e4); border-bottom: 1px solid var(--bordure); font-size: var(--taille-s); }
.corriger { margin-left: auto; font-weight: 600; color: var(--marine-clair); text-decoration: none; }
</style>
