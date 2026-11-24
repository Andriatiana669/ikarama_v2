<!-- Un employé dans l'organigramme, avec ses collaborateurs directs (composant récursif). -->
<script setup lang="ts">
import { computed } from 'vue'
import type { Identifiant, NoeudHierarchie } from '@/types'
import { pluriel } from '@/utils/format'
import UiAvatar from '@/components/ui/UiAvatar.vue'

const props = defineProps<{
  noeud: NoeudHierarchie
  ouverts: Set<Identifiant>
  /** Pendant une recherche : seuls ces nœuds sont affichés */
  visibles: Set<Identifiant> | null
  correspondances: Set<Identifiant>
}>()
const emit = defineEmits<{ basculer: [id: Identifiant]; ouvrir: [id: Identifiant] }>()

const enfants = computed(() =>
  props.visibles ? props.noeud.enfants.filter((e) => props.visibles!.has(e.id)) : props.noeud.enfants,
)
const ouvert = computed(() => props.ouverts.has(props.noeud.id))
</script>

<template>
  <li>
    <div class="noeud" :class="{ trouve: correspondances.has(noeud.id) }">
      <button
        v-if="noeud.enfants.length"
        type="button"
        class="basculer"
        :aria-expanded="ouvert"
        :aria-label="ouvert ? 'Replier' : 'Déplier'"
        @click="emit('basculer', noeud.id)"
      >
        <i class="bi" :class="ouvert ? 'bi-chevron-down' : 'bi-chevron-right'" aria-hidden="true" />
      </button>
      <span v-else class="basculer vide" />

      <UiAvatar :nom="noeud.nom_affiche" :matricule="noeud.code_barre" />
      <span class="identite">
        <span class="gras">{{ noeud.nom_affiche }}</span>
        <span class="texte-xs texte-doux">{{ [noeud.identifiant, noeud.poste, noeud.pole].filter(Boolean).join(', ') }}</span>
      </span>

      <button v-if="noeud.nb_membres" type="button" class="badge badge-marine equipe" @click="emit('ouvrir', noeud.id)">
        {{ pluriel(noeud.nb_membres, 'collaborateur') }}
      </button>
    </div>

    <ul v-if="ouvert && enfants.length">
      <NoeudOrganigramme
        v-for="enfant in enfants"
        :key="enfant.id"
        :noeud="enfant"
        :ouverts="ouverts"
        :visibles="visibles"
        :correspondances="correspondances"
        @basculer="emit('basculer', $event)"
        @ouvrir="emit('ouvrir', $event)"
      />
    </ul>
  </li>
</template>

<style scoped>
li { list-style: none; }
ul { margin-left: 15px; padding-left: var(--e4); border-left: 1px solid var(--bordure); }
.noeud {
  display: flex;
  align-items: center;
  gap: var(--e3);
  padding: var(--e2) var(--e3);
  margin: 2px 0;
  border-radius: var(--rayon);
}
.noeud:hover { background: var(--surface-douce); }
.noeud.trouve { background: var(--rouge-pale); }
.basculer {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  flex: none;
  border: none;
  border-radius: var(--rayon-s);
  background: none;
  color: var(--texte-doux);
  cursor: pointer;
}
.basculer:hover { background: var(--marine-pale); color: var(--marine); }
.basculer.vide { cursor: default; }
.identite { display: flex; flex-direction: column; min-width: 0; line-height: 1.3; }
.equipe { margin-left: auto; cursor: pointer; }
.equipe:hover { background: var(--marine); color: #fff; }
</style>
