<!-- Outil : choisir une personne et voir si elle a accès, et pourquoi. -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { accesApi } from '@/api'
import { useRequete } from '@/composables/useRequete'
import type { Identifiant } from '@/types'
import SelectEmploye from '@/components/formulaires/SelectEmploye.vue'
import UiChamp from '@/components/ui/UiChamp.vue'

const employeId = ref<Identifiant | null>(null)
const { donnees: resultat, chargement, erreur, executer } = useRequete(
  (id: Identifiant) => accesApi.verifier(id),
  null as Awaited<ReturnType<typeof accesApi.verifier>> | null,
)
watch(employeId, (id) => {
  if (id) executer(id)
  else resultat.value = null
})

/** Relance la vérification (après une modification de règle) */
defineExpose({ rafraichir: () => employeId.value && executer(employeId.value) })
</script>

<template>
  <section class="carte">
    <header class="carte-entete">
      <h2>Vérifier une personne</h2>
    </header>
    <div class="carte-corps pile">
      <UiChamp v-slot="{ id }" libelle="Employé" aide="Tous les employés, y compris ceux qui n'ont pas accès.">
        <SelectEmploye :id="id" v-model="employeId" :rechercher="accesApi.employes" />
      </UiChamp>

      <p v-if="chargement" class="texte-doux texte-petit">Vérification…</p>
      <p v-else-if="erreur" class="alerte alerte-erreur">{{ erreur }}</p>
      <div v-else-if="resultat" class="pile resultat">
        <p :class="['alerte', resultat.acces ? 'alerte-succes' : 'alerte-erreur']">
          <i :class="resultat.acces ? 'bi bi-check-circle-fill' : 'bi bi-x-octagon-fill'" aria-hidden="true" />
          <span>
            <strong>{{ resultat.employe.identifiant }}</strong> :
            {{ resultat.acces ? 'peut entrer sur le site' : "n'a pas accès au site" }}
            <template v-if="resultat.statut === 'RETIRE'"> (déjà connecté auparavant, reste visible)</template>
          </span>
        </p>
        <div>
          <p class="texte-petit gras">Règles qui la concernent</p>
          <ul v-if="resultat.regles.length" class="regles">
            <li v-for="r in resultat.regles" :key="r.id">
              <span :class="['badge', r.effet === 'REFUSER' ? 'badge-rouge' : 'badge-succes']">
                {{ r.effet === 'REFUSER' ? 'Refuser' : 'Autoriser' }}
              </span>
              {{ r.description }}
            </li>
          </ul>
          <p v-else class="texte-doux texte-petit">
            Aucune.
            {{ resultat.mode_ouvert ? 'Le site est ouvert à tous : elle entre.' : "Aucune règle ne l'autorise : elle n'entre pas." }}
          </p>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.regles { list-style: none; display: flex; flex-direction: column; gap: var(--e2); margin-top: var(--e2); font-size: var(--taille-s); }
.regles li { display: flex; align-items: center; gap: var(--e2); }
</style>
