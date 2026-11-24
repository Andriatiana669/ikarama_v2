<!-- Affichage compact d'un employé : avatar + nom + matricule. -->
<script setup lang="ts">
import type { EmployeResume } from '@/types'
import { nomEmploye } from '@/utils/format'
import UiAvatar from './UiAvatar.vue'

defineProps<{ employe?: EmployeResume | null; sansMatricule?: boolean }>()
</script>

<template>
  <span v-if="employe" class="employe">
    <UiAvatar :nom="nomEmploye(employe)" :matricule="employe.code_barre" />
    <span class="identite">
      <span class="gras tronquer">{{ nomEmploye(employe) }}</span>
      <span v-if="!sansMatricule && employe.code_barre" class="code">{{ employe.code_barre }}</span>
    </span>
  </span>
  <span v-else class="texte-leger">—</span>
</template>

<style scoped>
.employe { display: inline-flex; align-items: center; gap: var(--e2); min-width: 0; }
.identite { display: flex; flex-direction: column; line-height: 1.25; min-width: 0; }
.texte-leger { color: var(--texte-leger); }
</style>
