<!--
  Pastille d'un employé : sa photo de profil si elle existe, sinon ses initiales.
  <UiAvatar :nom="employe.nom_affiche" :matricule="employe.code_barre" />
  L'adresse des photos vient de VITE_PHOTO_PROFIL_URL (config/environnement.ts).
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ENV } from '@/config/environnement'
import { initiales } from '@/utils/format'

const props = defineProps<{ nom?: string | null; matricule?: string | null; grand?: boolean }>()

const photoIndisponible = ref(false)
watch(() => props.matricule, () => (photoIndisponible.value = false))

const urlPhoto = computed(() =>
  ENV.photoProfil && props.matricule && !photoIndisponible.value
    ? ENV.photoProfil.replace('{matricule}', encodeURIComponent(props.matricule))
    : null,
)
</script>

<template>
  <span class="avatar" :class="{ 'avatar-grand': grand }" aria-hidden="true">
    <img v-if="urlPhoto" :src="urlPhoto" alt="" loading="lazy" @error="photoIndisponible = true" />
    <template v-else>{{ initiales(nom) }}</template>
  </span>
</template>

<style scoped>
.avatar { overflow: hidden; }
.avatar img { width: 100%; height: 100%; object-fit: cover; }
</style>
