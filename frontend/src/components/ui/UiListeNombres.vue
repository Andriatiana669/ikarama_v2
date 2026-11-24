<!-- Saisie d'une liste de nombres (ex. rendements objectifs 1, 2, 3…). v-model = liste de textes. -->
<script setup lang="ts">
import { ref } from 'vue'

const modele = defineModel<(string | number)[]>({ default: () => [] })
withDefaults(defineProps<{ prefixe?: string; suffixe?: string; invalide?: boolean; id?: string }>(), {
  prefixe: 'Valeur',
})

const nouvelle = ref('')

function ajouter() {
  const valeur = nouvelle.value.trim().replace(',', '.')
  if (!valeur || Number.isNaN(Number(valeur))) return
  if (!modele.value.map(String).includes(valeur)) modele.value = [...modele.value, valeur]
  nouvelle.value = ''
}

function modifier(index: number, valeur: string) {
  const copie = [...modele.value]
  copie[index] = valeur.replace(',', '.')
  modele.value = copie
}

const retirer = (index: number) => (modele.value = modele.value.filter((_, i) => i !== index))
</script>

<template>
  <div class="liste-nombres">
    <div v-for="(valeur, index) in modele" :key="index" class="ligne-valeur">
      <span class="texte-doux texte-xs prefixe">{{ prefixe }} {{ index + 1 }}</span>
      <input
        class="saisie"
        inputmode="decimal"
        :value="valeur"
        :aria-label="`${prefixe} ${index + 1}`"
        @input="modifier(index, ($event.target as HTMLInputElement).value)"
      />
      <span v-if="suffixe" class="texte-doux texte-s">{{ suffixe }}</span>
      <button type="button" class="btn btn-fantome btn-icone btn-petit" :aria-label="`Retirer ${prefixe} ${index + 1}`" @click="retirer(index)">
        <i class="bi bi-x-lg" aria-hidden="true" />
      </button>
    </div>
    <div class="ligne-valeur">
      <span class="texte-doux texte-xs prefixe">{{ prefixe }} {{ modele.length + 1 }}</span>
      <input
        :id="id"
        v-model="nouvelle"
        class="saisie"
        inputmode="decimal"
        placeholder="Ajouter une valeur, puis Entrée"
        :aria-invalid="invalide || undefined"
        @keydown.enter.prevent="ajouter"
        @blur="ajouter"
      />
      <span v-if="suffixe" class="texte-doux texte-s">{{ suffixe }}</span>
      <button type="button" class="btn btn-secondaire btn-icone btn-petit" aria-label="Ajouter la valeur" @click="ajouter">
        <i class="bi bi-plus-lg" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.liste-nombres { display: flex; flex-direction: column; gap: var(--e2); }
.ligne-valeur { display: flex; align-items: center; gap: var(--e2); }
.prefixe { width: 92px; flex: none; }
.ligne-valeur .saisie { max-width: 180px; }
</style>
