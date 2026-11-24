<!-- Onglet « Organigramme » : la hiérarchie réelle (N+1), dépliable, avec recherche. -->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { equipesApi } from '@/api'
import { useRequete } from '@/composables/useRequete'
import type { Identifiant, NoeudHierarchie } from '@/types'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEtatVide from '@/components/ui/UiEtatVide.vue'
import UiRecherche from '@/components/ui/UiRecherche.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import NoeudOrganigramme from './NoeudOrganigramme.vue'

const emit = defineEmits<{ ouvrir: [id: Identifiant] }>()

const pole = ref('')
const recherche = ref('')
const poles = ref<string[]>([])
const ouverts = reactive(new Set<Identifiant>())

const { donnees: arbre, chargement, erreur, executer } = useRequete(
  (p: string) => equipesApi.organigramme(p || undefined),
  [] as NoeudHierarchie[],
)

async function charger() {
  await executer(pole.value)
  ouverts.clear()
  arbre.value.forEach((racine) => ouverts.add(racine.id)) // premier niveau déplié
}
onMounted(async () => {
  charger()
  poles.value = (await equipesApi.poles()).map((p) => p.pole)
})
watch(pole, charger)

/** Parcourt tout l'arbre (fonction utilitaire) */
function parcourir(noeuds: NoeudHierarchie[], visite: (n: NoeudHierarchie, ancetres: NoeudHierarchie[]) => void, ancetres: NoeudHierarchie[] = []) {
  for (const n of noeuds) {
    visite(n, ancetres)
    parcourir(n.enfants, visite, [...ancetres, n])
  }
}

// Recherche : on garde les personnes trouvées et leur chaîne de responsables
const resultat = computed(() => {
  const texte = recherche.value.toLowerCase()
  const correspondances = new Set<Identifiant>()
  if (!texte) return { visibles: null, correspondances }
  const visibles = new Set<Identifiant>()
  parcourir(arbre.value, (n, ancetres) => {
    const cible = `${n.nom_affiche} ${n.nom} ${n.prenom} ${n.identifiant} ${n.poste ?? ''}`.toLowerCase()
    if (cible.includes(texte)) {
      correspondances.add(n.id)
      visibles.add(n.id)
      ancetres.forEach((a) => visibles.add(a.id))
    }
  })
  return { visibles, correspondances }
})

// Pendant une recherche, le chemin vers chaque résultat est déplié automatiquement
watch(resultat, ({ visibles }) => visibles?.forEach((id) => ouverts.add(id)))

const racines = computed(() =>
  resultat.value.visibles ? arbre.value.filter((r) => resultat.value.visibles!.has(r.id)) : arbre.value,
)

const basculer = (id: Identifiant) => (ouverts.has(id) ? ouverts.delete(id) : ouverts.add(id))
const toutDeplier = () => parcourir(arbre.value, (n) => n.enfants.length && ouverts.add(n.id))
const toutReplier = () => ouverts.clear()
</script>

<template>
  <div class="carte">
    <div class="barre-outils">
      <UiRecherche v-model="recherche" placeholder="Rechercher une personne ou un poste" />
      <UiSelect v-model="pole" :options="poles" placeholder="Tous les pôles" aria-label="Pôle" />
      <div class="ligne boutons">
        <UiBouton variante="fantome" petit icone="arrows-expand" @click="toutDeplier">Tout déplier</UiBouton>
        <UiBouton variante="fantome" petit icone="arrows-collapse" @click="toutReplier">Tout replier</UiBouton>
      </div>
    </div>

    <div class="carte-corps">
      <UiChargement v-if="chargement" />
      <div v-else-if="erreur" class="alerte alerte-erreur"><i class="bi bi-exclamation-triangle" aria-hidden="true" />{{ erreur }}</div>
      <UiEtatVide
        v-else-if="!racines.length"
        icone="diagram-3"
        :titre="recherche ? 'Personne ne correspond à cette recherche' : 'Organigramme vide'"
        :texte="recherche ? undefined : 'Lancez une synchronisation avec l’API RH depuis la page Utilisateurs.'"
      />
      <ul v-else class="arbre">
        <NoeudOrganigramme
          v-for="racine in racines"
          :key="racine.id"
          :noeud="racine"
          :ouverts="ouverts"
          :visibles="resultat.visibles"
          :correspondances="resultat.correspondances"
          @basculer="basculer"
          @ouvrir="emit('ouvrir', $event)"
        />
      </ul>
    </div>
  </div>
</template>

<style scoped>
.barre-outils { display: flex; gap: var(--e3); flex-wrap: wrap; align-items: center; padding: var(--e4); border-bottom: 1px solid var(--bordure); }
.barre-outils .saisie { width: auto; min-width: 200px; }
.boutons { margin-left: auto; gap: var(--e1); }
.arbre { padding: 0; }
</style>
