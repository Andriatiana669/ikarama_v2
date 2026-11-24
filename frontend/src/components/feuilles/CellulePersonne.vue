<!-- Cellule « Employé / Contrôleur / Employé reprise » : choix parmi les personnes de l'affaire. -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { EmployeResume, Identifiant } from '@/types'
import UiAvatar from '@/components/ui/UiAvatar.vue'
import UiMenuDeroulant from '@/components/ui/UiMenuDeroulant.vue'

const props = defineProps<{
  valeur: EmployeResume | null
  options: EmployeResume[]
  desactive?: boolean
  libelle: string
  /** Du temps a été pointé : la personne ne peut plus être changée */
  verrouille?: boolean
}>()
const emit = defineEmits<{ choisir: [id: Identifiant | null]; edition: [enCours: boolean] }>()

const ancre = ref<HTMLElement | null>(null)
const ouvert = ref(false)
watch(ouvert, (valeur) => emit('edition', valeur))
const filtre = ref('')
const visibles = computed(() => {
  const t = filtre.value.toLowerCase()
  return props.options.filter((p) => !t || `${p.identifiant} ${p.nom_affiche}`.toLowerCase().includes(t))
})

function choisir(id: Identifiant | null, fermer: () => void) {
  fermer()
  filtre.value = ''
  if (id !== (props.valeur?.id ?? null)) emit('choisir', id)
}
</script>

<template>
  <button
    ref="ancre"
    type="button"
    class="cellule-choix"
    :disabled="desactive || verrouille"
    :title="verrouille ? 'Verrouillé : du temps a déjà été pointé dans Pointages' : undefined"
    :aria-label="`${libelle} : ${valeur?.identifiant ?? 'aucun'}`"
    :aria-expanded="ouvert"
    @click="ouvert = !ouvert"
  >
    <template v-if="valeur">
      <UiAvatar :nom="valeur.nom_affiche" :matricule="valeur.code_barre" />
      <span class="identifiant">{{ valeur.identifiant }}</span>
    </template>
    <span v-else class="vide">{{ desactive ? '—' : 'Choisir…' }}</span>
    <i v-if="verrouille" class="bi bi-lock-fill verrou" aria-hidden="true" />
    <i v-else-if="!desactive" class="bi bi-chevron-down" aria-hidden="true" />
  </button>

  <UiMenuDeroulant v-model="ouvert" :ancre="ancre" :largeur-min="240">
    <template #default="{ fermer }">
      <div class="recherche"><input v-model="filtre" class="saisie" placeholder="Rechercher…" aria-label="Rechercher une personne" /></div>
      <button type="button" class="option" @click="choisir(null, fermer)"><span class="vide">Personne</span></button>
      <button
        v-for="p in visibles"
        :key="p.id"
        type="button"
        class="option"
        :class="{ actif: p.id === valeur?.id }"
        role="option"
        :aria-selected="p.id === valeur?.id"
        @click="choisir(p.id, fermer)"
      >
        <UiAvatar :nom="p.nom_affiche" :matricule="p.code_barre" />
        <span class="identifiant">{{ p.identifiant }}</span>
        <span class="texte-doux texte-xs">{{ p.nom_affiche }}</span>
      </button>
      <p v-if="!visibles.length" class="texte-doux texte-xs aucun">Aucune personne.</p>
    </template>
  </UiMenuDeroulant>
</template>

<style scoped>
.cellule-choix {
  display: inline-flex; align-items: center; gap: var(--e2); width: 100%; min-width: 150px;
  padding: 3px 6px; border: 1px solid transparent; border-radius: var(--rayon); background: none; cursor: pointer; text-align: left;
}
.cellule-choix:hover:not(:disabled) { border-color: var(--bordure); background: var(--surface); }
.cellule-choix:disabled { cursor: default; }
.cellule-choix .bi { margin-left: auto; font-size: 0.65rem; color: var(--texte-leger); }
.cellule-choix :deep(.avatar), .option :deep(.avatar) { width: 24px; height: 24px; font-size: 0.6rem; }
.verrou { color: var(--texte-leger); font-size: 0.7rem !important; }
.identifiant { font-weight: 600; color: var(--marine); white-space: nowrap; }
.vide { color: var(--texte-leger); }
.recherche { padding: var(--e1) var(--e2) var(--e2); }
.recherche .saisie { height: 32px; }
.option { display: flex; align-items: center; gap: var(--e2); width: 100%; padding: var(--e2) var(--e3); border: none; background: none; cursor: pointer; text-align: left; font-size: var(--taille-s); }
.option:hover, .option.actif { background: var(--marine-pale); }
.aucun { padding: var(--e2) var(--e3); }
</style>
