<!-- Bouton standard. <UiBouton variante="primaire" icone="plus" :chargement="envoi">Ajouter</UiBouton> -->
<script setup lang="ts">
withDefaults(
  defineProps<{
    variante?: 'primaire' | 'secondaire' | 'danger' | 'fantome'
    icone?: string
    chargement?: boolean
    desactive?: boolean
    petit?: boolean
    type?: 'button' | 'submit'
    /** Bouton icône seule : le texte sert d'étiquette accessible */
    iconeSeule?: boolean
  }>(),
  { variante: 'secondaire', type: 'button' },
)
</script>

<template>
  <button
    :type="type"
    class="btn"
    :class="[`btn-${variante}`, { 'btn-petit': petit, 'btn-icone': iconeSeule }]"
    :disabled="desactive || chargement"
    :aria-busy="chargement || undefined"
  >
    <span v-if="chargement" class="tourniquet" aria-hidden="true" />
    <i v-else-if="icone" :class="`bi bi-${icone}`" aria-hidden="true" />
    <span :class="{ 'masque-visuel': iconeSeule }"><slot /></span>
  </button>
</template>

<style scoped>
.tourniquet {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: tourne 0.7s linear infinite;
}
@keyframes tourne { to { transform: rotate(360deg); } }
</style>
