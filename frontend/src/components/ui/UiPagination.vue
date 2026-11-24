<!-- Pagination : <UiPagination v-model:page="page" :total="total" :taille-page="25" /> -->
<script setup lang="ts">
import { computed } from 'vue'

const page = defineModel<number>('page', { required: true })
const props = defineProps<{ total: number; taillePage: number }>()

const nbPages = computed(() => Math.max(1, Math.ceil(props.total / props.taillePage)))
const debut = computed(() => (props.total ? (page.value - 1) * props.taillePage + 1 : 0))
const fin = computed(() => Math.min(page.value * props.taillePage, props.total))
</script>

<template>
  <nav v-if="total > 0" class="pagination ligne-entre" aria-label="Pagination">
    <span class="texte-doux texte-petit">{{ debut }}–{{ fin }} sur {{ total }}</span>
    <div v-if="nbPages > 1" class="ligne">
      <button class="btn btn-secondaire btn-petit btn-icone" :disabled="page <= 1" aria-label="Page précédente" @click="page--">
        <i class="bi bi-chevron-left" aria-hidden="true" />
      </button>
      <span class="texte-petit">Page {{ page }} / {{ nbPages }}</span>
      <button class="btn btn-secondaire btn-petit btn-icone" :disabled="page >= nbPages" aria-label="Page suivante" @click="page++">
        <i class="bi bi-chevron-right" aria-hidden="true" />
      </button>
    </div>
  </nav>
</template>

<style scoped>
.pagination { padding: var(--e3) var(--e4); border-top: 1px solid var(--bordure); }
</style>
