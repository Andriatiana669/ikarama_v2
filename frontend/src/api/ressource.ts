// src/api/ressource.ts
/**
 * Fabrique d'accès à une ressource REST Django (ModelViewSet).
 * Une ligne suffit pour obtenir lister / tous / lire / creer / modifier / supprimer :
 *
 *   export const xxxApi = creerRessource<Xxx>('/application/xxx/')
 *   const page = await xxxApi.lister({ search: 'prod', page: 2 })
 */
import apiClient from './client'
import type { Identifiant, Page, RapportImport } from '@/types'

export type Parametres = Record<string, string | number | boolean | null | undefined>

/** Retire les paramètres vides pour garder des URL propres */
export const nettoyer = (parametres: Parametres = {}) =>
  Object.fromEntries(Object.entries(parametres).filter(([, v]) => v !== '' && v !== null && v !== undefined))

/** Enregistre un fichier reçu du serveur sur le poste de l'utilisateur */
export function telecharger(contenu: Blob, nomFichier: string) {
  const lien = document.createElement('a')
  lien.href = URL.createObjectURL(contenu)
  lien.download = nomFichier
  lien.click()
  setTimeout(() => URL.revokeObjectURL(lien.href), 1000)
}

export function creerRessource<T, Creation = Partial<T>>(chemin: string) {
  const url = (id?: Identifiant, action?: string) =>
    `${chemin}${id !== undefined ? `${id}/` : ''}${action ? `${action}/` : ''}`

  return {
    /** Une page de résultats */
    async lister(parametres: Parametres = {}): Promise<Page<T>> {
      const { data } = await apiClient.get(url(), { params: nettoyer(parametres) })
      // Si l'API n'est pas paginée, on renvoie quand même le format « page »
      return Array.isArray(data) ? { count: data.length, next: null, previous: null, results: data } : data
    },
    /** Tous les éléments sans pagination (listes déroulantes) */
    async tous(parametres: Parametres = {}): Promise<T[]> {
      const { data } = await apiClient.get(url(), { params: nettoyer({ ...parametres, page_size: 0 }) })
      return Array.isArray(data) ? data : data.results
    },
    async lire(id: Identifiant, parametres: Parametres = {}): Promise<T> {
      return (await apiClient.get(url(id), { params: nettoyer(parametres) })).data
    },
    async creer(donnees: Creation): Promise<T> {
      return (await apiClient.post(url(), donnees)).data
    },
    async modifier(id: Identifiant, donnees: Partial<Creation>): Promise<T> {
      return (await apiClient.patch(url(id), donnees)).data
    },
    async supprimer(id: Identifiant): Promise<void> {
      await apiClient.delete(url(id))
    },
    /** Nouvel ordre manuel (poignées ≡) : ids dans l'ordre voulu */
    async reordonner(ids: Identifiant[]): Promise<void> {
      await apiClient.post(url(undefined, 'reordonner'), { ids })
    },
    /** Télécharge l'export Excel des colonnes données, avec les mêmes filtres que la liste */
    async exporter(parametres: Parametres, colonnes: { cle: string; libelle: string }[], nomFichier: string): Promise<void> {
      const { data } = await apiClient.get(url(undefined, 'exporter'), {
        params: nettoyer({ ...parametres, colonnes: JSON.stringify(colonnes), nom: nomFichier }),
        responseType: 'blob',
      })
      telecharger(data, `${nomFichier}.xlsx`)
    },
    /** Télécharge le modèle Excel d'import (colonnes + onglet « Aide ») */
    async telechargerModele(nomFichier: string, parametres: Parametres = {}): Promise<void> {
      const { data } = await apiClient.get(url(undefined, 'modele'), { params: nettoyer(parametres), responseType: 'blob' })
      telecharger(data, `${nomFichier}.xlsx`)
    },
    /** Import Excel ; simulation = aperçu sans rien enregistrer */
    async importer(fichier: File, simulation: boolean, parametres: Parametres = {}): Promise<RapportImport> {
      const formulaire = new FormData()
      formulaire.append('fichier', fichier)
      if (simulation) formulaire.append('simulation', '1')
      return (await apiClient.post(url(undefined, 'importer'), formulaire, { params: nettoyer(parametres), timeout: 180_000 })).data
    },
    /** Action personnalisée : action(id, 'retirer', {...}) ou action(undefined, 'mes-equipes') */
    async action<R = any>(id: Identifiant | undefined, nom: string, donnees?: unknown, methode: 'get' | 'post' = 'post'): Promise<R> {
      const reponse =
        methode === 'get'
          ? await apiClient.get(url(id, nom), { params: nettoyer(donnees as Parametres) })
          : await apiClient.post(url(id, nom), donnees)
      return reponse.data
    },
  }
}

export type Ressource<T> = ReturnType<typeof creerRessource<T>>
