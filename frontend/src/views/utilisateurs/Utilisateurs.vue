<!-- Liste des employés (synchronisés depuis l'API RH). -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { utilisateursApi } from '@/api'
import { useListe } from '@/composables/useListe'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/store/auth'
import type { Colonne, Employe } from '@/types'
import { pluriel } from '@/utils/format'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiBouton from '@/components/ui/UiBouton.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'
import UiPagination from '@/components/ui/UiPagination.vue'
import UiRecherche from '@/components/ui/UiRecherche.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTableau from '@/components/ui/UiTableau.vue'
import FicheEmploye from '@/components/utilisateurs/FicheEmploye.vue'

const auth = useAuthStore()
const toast = useToast()
const liste = useListe(utilisateursApi, { filtres: { pole: '', poste: '', statut: '' }, tri: 'nom' })
const { lignes, total, page, taillePage, recherche, tri, filtres, chargement, erreur } = liste

const valeurs = ref({ poles: [] as string[], postes: [] as string[], statuts: [] as string[] })
const chargerValeurs = async () => (valeurs.value = await utilisateursApi.valeursFiltres())
onMounted(chargerValeurs)

const colonnes: Colonne[] = [
  { cle: 'nom', libelle: 'Utilisateur', triable: true },
  { cle: 'code_barre', libelle: 'Employé', triable: true },
  { cle: 'poste', libelle: 'Poste' },
  { cle: 'pole', libelle: 'Pôle' },
  { cle: 'chef', libelle: 'Responsable (N+1)' },
  { cle: 'statut_acces', libelle: 'Accès', alignement: 'centre' },
]

const ficheOuverte = ref(false)
const selection = ref<Employe | null>(null)
function ouvrirFiche(employe: Employe) {
  selection.value = employe
  ficheOuverte.value = true
}

const synchro = ref(false)
async function synchroniser() {
  synchro.value = true
  try {
    const r = await utilisateursApi.synchroniser()
    toast.succes(
      `Synchronisation terminée : ${pluriel(r.crees, 'création')}, ${pluriel(r.mis_a_jour, 'mise à jour', 'mises à jour')}.`,
    )
    if (r.erreurs?.length) toast.erreur(`${pluriel(r.erreurs.length, 'fiche')} en erreur : voir le journal du serveur.`)
    liste.charger()
    chargerValeurs()
  } catch (e) {
    toast.erreur(e)
  } finally {
    synchro.value = false
  }
}
</script>

<template>
  <div class="page">
    <EnTetePage titre="Utilisateurs" :description="`${pluriel(total, 'employé')}, synchronisés depuis l'API RH.`">
      <UiBouton v-if="auth.estAdministrateur" icone="arrow-repeat" :chargement="synchro" @click="synchroniser">
        Synchroniser avec l'API RH
      </UiBouton>
    </EnTetePage>

    <div class="carte">
      <div class="barre-outils">
        <UiRecherche v-model="recherche" placeholder="Matricule, nom, prénom ou e-mail" />
        <UiSelect v-model="filtres.pole" :options="valeurs.poles" placeholder="Tous les pôles" aria-label="Pôle" />
        <UiSelect v-model="filtres.poste" :options="valeurs.postes" placeholder="Tous les postes" aria-label="Poste" />
        <UiSelect v-model="filtres.statut" :options="valeurs.statuts" placeholder="Tous les statuts" aria-label="Statut" />
      </div>

      <UiTableau
        v-model:tri="tri"
        :colonnes="colonnes"
        :lignes="lignes"
        :chargement="chargement"
        :erreur="erreur"
        vide-titre="Aucun employé trouvé"
        vide-texte="Modifiez la recherche ou les filtres."
        cliquable
        @selection="ouvrirFiche"
      >
        <template #cellule-nom="{ ligne }"><UiEmploye :employe="ligne" sans-matricule /></template>
        <template #cellule-code_barre="{ ligne }"><span class="identifiant">{{ ligne.identifiant || '—' }}</span></template>
        <template #cellule-poste="{ ligne }">{{ ligne.postes[0]?.poste_nom || '—' }}</template>
        <template #cellule-pole="{ ligne }">{{ ligne.postes[0]?.pole || '—' }}</template>
        <template #cellule-chef="{ ligne }"><UiEmploye :employe="ligne.chef" sans-matricule /></template>
        <template #cellule-statut_acces="{ ligne }">
          <span v-if="ligne.statut_acces === 'RETIRE'" class="badge badge-rouge">Accès retiré</span>
          <i v-else-if="ligne.statut_acces === 'CONNECTE'" class="bi bi-check-circle-fill compte-ok" title="S'est déjà connecté" />
          <span v-else class="texte-doux texte-xs">Jamais connecté</span>
        </template>
      </UiTableau>

      <UiPagination v-model:page="page" :total="total" :taille-page="taillePage" />
    </div>

    <FicheEmploye v-model="ficheOuverte" :employe="selection" />
  </div>
</template>

<style scoped>
.barre-outils { display: flex; gap: var(--e3); flex-wrap: wrap; padding: var(--e4); border-bottom: 1px solid var(--bordure); }
.barre-outils .saisie { width: auto; min-width: 170px; }
.compte-ok { color: var(--succes); }
.identifiant { font-weight: 600; color: var(--marine); white-space: nowrap; }
</style>
