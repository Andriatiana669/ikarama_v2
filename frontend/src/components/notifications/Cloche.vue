<!--
  Cloche des notifications (en-tête) : compteur des non lues (rafraîchi chaque minute), liste, lecture.
  Cliquer une notification la marque comme lue et ouvre sa page.
-->
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { notificationsApi } from '@/api'
import type { NotificationApp } from '@/api/notifications'
import { formatRelatif } from '@/utils/format'
import { useTempsReel } from '@/composables/useTempsReel'
import UiMenuDeroulant from '@/components/ui/UiMenuDeroulant.vue'

const router = useRouter()
const nonLues = ref(0)
const ouvert = ref(false)
const bouton = ref<HTMLElement | null>(null)
const liste = ref<NotificationApp[]>([])
const chargement = ref(false)

const ICONES: Record<string, string> = {
  rappel_pointage: 'stopwatch', temps_estimatif: 'hourglass-split', pointage_modifie: 'pencil-square', import: 'file-earmark-arrow-up', affaire: 'briefcase',
}

async function compter() {
  try {
    nonLues.value = await notificationsApi.compte()
  } catch {
    // hors ligne ou session expirée : on réessaiera
  }
}
async function ouvrir() {
  ouvert.value = !ouvert.value
  if (!ouvert.value) return
  chargement.value = true
  try {
    liste.value = (await notificationsApi.lister()).results
  } finally {
    chargement.value = false
  }
}
async function cliquer(n: NotificationApp, fermer: () => void) {
  if (!n.lu) {
    nonLues.value = await notificationsApi.lire(n.id)
    n.lu = true
  }
  fermer()
  if (n.lien) router.push(n.lien)
}
async function toutLire() {
  nonLues.value = await notificationsApi.toutLire()
  liste.value.forEach((n) => (n.lu = true))
}

// Temps réel : une nouvelle notification arrive aussitôt ; l'interrogation chaque minute reste en secours
const tempsReel = useTempsReel()
const desabonner = tempsReel.ecouter('notification', () => {
  compter()
  if (ouvert.value) notificationsApi.lister().then((p) => (liste.value = p.results))
})
let minuteur: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  compter()
  minuteur = setInterval(compter, 60_000)
})
onBeforeUnmount(() => {
  clearInterval(minuteur)
  desabonner()
})
</script>

<template>
  <button ref="bouton" type="button" class="cloche" :aria-label="`Notifications : ${nonLues} non lue(s)`" :aria-expanded="ouvert" @click="ouvrir">
    <i class="bi" :class="nonLues ? 'bi-bell-fill' : 'bi-bell'" aria-hidden="true" />
    <span v-if="nonLues" class="compteur">{{ nonLues > 99 ? '99+' : nonLues }}</span>
  </button>
  <UiMenuDeroulant v-model="ouvert" :ancre="bouton" :largeur-min="380">
    <template #default="{ fermer }">
      <div class="entete">
        <span class="gras">Notifications</span>
        <button v-if="nonLues" type="button" class="lien" @click="toutLire">Tout marquer comme lu</button>
      </div>
      <p v-if="chargement && !liste.length" class="vide">Chargement…</p>
      <p v-else-if="!liste.length" class="vide"><i class="bi bi-check2-circle" aria-hidden="true" /> Aucune notification.</p>
      <ul v-else class="liste">
        <li v-for="n in liste" :key="n.id">
          <button type="button" class="notification" :class="{ lue: n.lu }" @click="cliquer(n, fermer)">
            <i class="bi icone" :class="`bi-${ICONES[n.type] ?? 'bell'}`" aria-hidden="true" />
            <span class="texte">
              <span class="titre">{{ n.titre }}</span>
              <span v-if="n.message" class="message">{{ n.message }}</span>
              <span class="quand">{{ formatRelatif(n.cree_le) }}</span>
            </span>
            <span v-if="!n.lu" class="point" aria-label="non lue" />
          </button>
        </li>
      </ul>
    </template>
  </UiMenuDeroulant>
</template>

<style scoped>
.cloche { position: relative; display: inline-grid; place-items: center; width: 38px; height: 38px; border: 1px solid var(--bordure-forte); border-radius: var(--rayon); background: var(--surface); color: var(--marine); font-size: 1.05rem; cursor: pointer; }
.cloche:hover { border-color: var(--marine-clair); }
.compteur { position: absolute; top: -6px; right: -6px; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 999px; background: var(--rouge); color: #fff; font-size: 0.65rem; font-weight: 700; line-height: 18px; text-align: center; }
.entete { display: flex; align-items: center; justify-content: space-between; padding: var(--e2) var(--e3); border-bottom: 1px solid var(--bordure); }
.lien { border: none; background: none; color: var(--marine-clair); font-size: var(--taille-xs); font-weight: 600; cursor: pointer; }
.vide { padding: var(--e4); text-align: center; color: var(--texte-doux); font-size: var(--taille-s); }
.liste { list-style: none; max-height: 420px; overflow-y: auto; }
.notification { display: flex; align-items: flex-start; gap: var(--e3); width: 100%; padding: var(--e3); border: none; border-bottom: 1px solid var(--bordure); background: color-mix(in srgb, var(--marine-pale) 55%, var(--surface)); text-align: left; cursor: pointer; }
.notification.lue { background: var(--surface); }
.notification:hover { background: var(--marine-pale); }
.icone { color: var(--marine); font-size: 1.1rem; margin-top: 2px; }
.texte { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.titre { font-weight: 600; font-size: var(--taille-s); color: var(--texte); }
.message { font-size: var(--taille-xs); color: var(--texte-doux); white-space: pre-line; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.quand { font-size: var(--taille-xs); color: var(--texte-leger); }
.point { width: 9px; height: 9px; margin-top: 6px; border-radius: 50%; background: var(--rouge); flex: none; }
</style>
