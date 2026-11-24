// frontend/vite.config.ts
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import { fileURLToPath } from 'url'
import removeConsole from 'vite-plugin-remove-console'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
// Le fichier .env est à la racine du dépôt (partagé avec Django)
const dossierEnv = path.resolve(__dirname, '..')

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, dossierEnv, 'VITE_')

  return {
    // Toutes les variables VITE_* du .env racine sont disponibles dans import.meta.env
    envDir: dossierEnv,
    plugins: [
      vue(),
      // Supprime les console.log du build de production (garde error et warn)
      removeConsole(),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        // Guide utilisateur : un seul contenu (docs/guide/*.md), lu aussi par la page « Aide »
        '@docs': path.resolve(__dirname, '../docs'),
      },
    },
    server: {
      // Écoute aussi sur l'adresse du poste (ex. http://10.5.120.23:4002), pas seulement localhost
      host: true,
      port: parseInt(env.VITE_FRONTEND_PORT || '') || 4002,
      strictPort: true,
      // Autorise la lecture du guide (dossier docs/ à la racine du dépôt)
      fs: { allow: [dossierEnv] },
    },
  }
})
