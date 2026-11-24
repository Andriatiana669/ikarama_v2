<!-- Résumé : mode ouvert / restreint, nombre de personnes autorisées, mon propre accès. -->
<script setup lang="ts">
import type { ApercuAcces } from '@/types'
import { pluriel } from '@/utils/format'

defineProps<{ apercu: ApercuAcces | null }>()
</script>

<template>
  <div v-if="apercu" class="grille-3">
    <div class="carte carte-corps indicateur">
      <span class="texte-doux texte-petit">Mode</span>
      <span class="valeur">
        <i :class="apercu.mode_ouvert ? 'bi bi-unlock' : 'bi bi-lock'" aria-hidden="true" />
        {{ apercu.mode_ouvert ? 'Ouvert à tous' : 'Restreint' }}
      </span>
      <span class="texte-xs texte-doux">
        {{ apercu.mode_ouvert ? 'Aucune règle « Autoriser » : tout le monde entre, sauf les refus.' : 'Seules les personnes autorisées par une règle entrent.' }}
      </span>
    </div>
    <div class="carte carte-corps indicateur">
      <span class="texte-doux texte-petit">Personnes autorisées</span>
      <span class="valeur">{{ apercu.nb_autorises }} <span class="texte-doux sur">/ {{ apercu.nb_employes }}</span></span>
      <span class="texte-xs texte-doux">{{ pluriel(apercu.nb_regles_actives, 'règle active', 'règles actives') }}</span>
    </div>
    <div class="carte carte-corps indicateur" :class="{ alerte: apercu.moi && !apercu.moi.acces }">
      <span class="texte-doux texte-petit">Votre accès</span>
      <span class="valeur">
        <i :class="apercu.moi?.acces ? 'bi bi-check-circle-fill ok' : 'bi bi-x-octagon-fill ko'" aria-hidden="true" />
        {{ apercu.moi?.acces ? 'Autorisé' : 'Refusé' }}
      </span>
      <span class="texte-xs texte-doux">Les administrateurs sont soumis aux mêmes règles.</span>
    </div>
  </div>
</template>

<style scoped>
.indicateur { display: flex; flex-direction: column; gap: var(--e1); }
.valeur { display: flex; align-items: center; gap: var(--e2); font-size: var(--taille-xl); font-weight: 600; color: var(--marine); }
.sur { font-size: var(--taille-m); font-weight: 400; }
.ok { color: var(--succes); }
.ko { color: var(--rouge); }
.indicateur.alerte { border-color: var(--rouge); }
</style>
