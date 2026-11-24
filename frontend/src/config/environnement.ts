// src/config/environnement.ts
// Lecture UNIQUE des variables d'environnement (fichier .env à la racine du dépôt).
// Ne jamais mettre de secret dans une variable VITE_* : elle est visible dans le navigateur.

const sansSlashFinal = (url?: string) => (url || '').replace(/\/+$/, '')

const backend = sansSlashFinal(import.meta.env.VITE_BACKEND_URL) || 'http://localhost:8000'

export const ENV = {
  backendUrl: backend,
  apiUrl: sansSlashFinal(import.meta.env.VITE_API_BASE_URL) || `${backend}/api`,
  keycloak: {
    url: sansSlashFinal(import.meta.env.VITE_KEYCLOAK_BASE_URL),
    realm: import.meta.env.VITE_KEYCLOAK_REALM || '',
    clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || '',
  },
  nomApplication: import.meta.env.VITE_NOM_APPLICATION || 'Ikarama',
  /** Adresse des photos de profil ; {matricule} est remplacé par le matricule de l'employé */
  photoProfil: import.meta.env.VITE_PHOTO_PROFIL_URL || '',
} as const
