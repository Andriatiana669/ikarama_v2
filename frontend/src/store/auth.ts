// src/store/auth.ts
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi } from '@/api'
import { deconnecter } from '@/services/session'
import type { UtilisateurConnecte } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const utilisateur = ref<UtilisateurConnecte | null>(null)

  const estConnecte = computed(() => utilisateur.value !== null)
  const estAdministrateur = computed(() => !!utilisateur.value?.est_administrateur)
  /** Faux : la personne ne respecte pas les règles d'accès au site */
  const aAcces = computed(() => !!utilisateur.value?.acces_site)
  const employe = computed(() => utilisateur.value?.employe ?? null)
  const nomAffiche = computed(
    () => employe.value?.nom_affiche || `${utilisateur.value?.prenom ?? ''} ${utilisateur.value?.nom ?? ''}`.trim() || utilisateur.value?.username || '',
  )

  const matricule = computed(() => employe.value?.code_barre || utilisateur.value?.username || '')
  const email = computed(() => employe.value?.email || utilisateur.value?.email || '')

  /** Charge l'utilisateur connecté depuis le backend (appelé au démarrage). */
  async function charger() {
    utilisateur.value = await authApi.moi()
    return utilisateur.value
  }

  /**
   * Droits de Paramètres > Autorisation : peut('creer', 'gsheets_feuilles').
   * Le superadmin peut tout. Les modules non gérés par les rôles (Mon temps, Rendement…) restent ouverts :
   * leurs règles métier sont appliquées par le serveur.
   */
  function peut(verbe: string, module?: string) {
    if (!estConnecte.value || !aAcces.value) return false
    if (estAdministrateur.value) return true
    const droits = utilisateur.value?.autorisations ?? {}
    if (!module || !(module in droits)) return true
    return droits[module]!.includes(verbe)
  }
  const estResponsable = computed(() => estAdministrateur.value || !!utilisateur.value?.est_responsable)

  function seDeconnecter() {
    utilisateur.value = null
    deconnecter()
  }

  return { utilisateur, estConnecte, estAdministrateur, estResponsable, aAcces, employe, nomAffiche, matricule, email, charger, peut, seDeconnecter }
})
