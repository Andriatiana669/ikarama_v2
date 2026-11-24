<!--
  Pointages > Vérification (superadmins) : une ligne par personne et par jour pointé.
  Heures pointées = H_Durée du jour ; Manque = 8 h − H_Durée (jours ouvrables, les HS ne comblent pas).
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { utilisateursApi, verificationApi } from '@/api'
import type { ChampFormulaire, Colonne } from '@/types'
import { formatDate, formatNombre } from '@/utils/format'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import TableauDonnees from '@/components/ui/TableauDonnees.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const aujourdhui = new Date()
const lundi = new Date(aujourdhui)
lundi.setDate(aujourdhui.getDate() - ((aujourdhui.getDay() + 6) % 7))
const debut = ref(iso(lundi))
const fin = ref(iso(aujourdhui))

const poles = ref<string[]>([])
onMounted(async () => (poles.value = (await utilisateursApi.valeursFiltres()).poles ?? []))

const colonnes: Colonne[] = [
  { cle: 'date', libelle: 'Date' },
  { cle: 'employe', libelle: 'Employé', cleExport: 'employe.identifiant' },
  { cle: 'heures', libelle: 'Heures pointées', alignement: 'droite' },
  { cle: 'manque', libelle: 'Manque', alignement: 'droite' },
]
const filtres = (): ChampFormulaire[] => [
  { cle: 'employe', libelle: 'Employé', type: 'employe' },
  { cle: 'pole', libelle: 'Pôle', type: 'select', placeholder: 'Tous', options: poles.value.map((p) => ({ valeur: p, libelle: p })) },
  { cle: 'manques', libelle: 'Afficher', type: 'select', placeholder: 'Tous les jours', options: [{ valeur: '1', libelle: 'Seulement les manques' }] },
]
</script>

<template>
  <div class="page pile">
    <EnTetePage
      titre="Vérification des pointages"
      description="Pour chaque personne et chaque jour pointé : les heures pointées (H_Durée) et ce qui manque pour atteindre 8 h (jours ouvrables)."
    />

    <div class="barre carte">
      <label class="date"><span>Début</span><input v-model="debut" class="saisie" type="date" /></label>
      <label class="date"><span>Fin</span><input v-model="fin" class="saisie" type="date" /></label>
    </div>

    <TableauDonnees
      :key="poles.length"
      titre="Jours pointés"
      icone="clipboard2-check"
      cle-stockage="verification-pointages"
      :source="verificationApi"
      :colonnes="colonnes"
      :filtres="filtres()"
      :parametres="{ debut, fin }"
      :taille-page="50"
      :cliquable="false"
      placeholder-recherche="Nom ou matricule"
      vide-titre="Aucun jour pointé sur cette période"
    >
      <template #cellule-date="{ ligne }"><span class="nowrap">{{ formatDate(ligne.date) }}</span></template>
      <template #cellule-employe="{ ligne }"><UiEmploye :employe="ligne.employe" /></template>
      <template #cellule-heures="{ ligne }"><span class="gras">{{ formatNombre(ligne.heures) }} h</span></template>
      <template #cellule-manque="{ ligne }">
        <span v-if="ligne.manque > 0" class="manque">{{ formatNombre(ligne.manque) }} h</span>
        <span v-else class="complet"><i class="bi bi-check-circle-fill" aria-hidden="true" /> 0 h</span>
      </template>
    </TableauDonnees>
  </div>
</template>

<style scoped>
.barre { display: flex; align-items: flex-end; gap: var(--e3); padding: var(--e3) var(--e4); }
.date { display: flex; flex-direction: column; gap: 2px; font-size: var(--taille-xs); color: var(--texte-doux); }
.date .saisie { width: 160px; height: 36px; }
.nowrap { white-space: nowrap; }
.manque { color: var(--danger); font-weight: 700; }
.complet { color: var(--succes); font-weight: 600; }
</style>
