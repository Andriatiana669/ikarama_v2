<!-- Menu latéral. Les entrées viennent de src/config/navigation.ts. -->
<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NAVIGATION, type EntreeMenu } from '@/config/navigation'
import { useAuthStore } from '@/store/auth'
import { useInterfaceStore } from '@/store/interface'
import UiAvatar from '@/components/ui/UiAvatar.vue'

const route = useRoute()
const auth = useAuthStore()
const ui = useInterfaceStore()

/** Entrées visibles selon les droits (prêt pour les skins) */
const visible = (e: EntreeMenu) => (!e.administrateur || auth.estAdministrateur) && (!e.module || auth.peut(e.verbe ?? 'voir', e.module))
const entrees = computed(() =>
  NAVIGATION.filter(visible)
    .map((e) => (e.enfants ? { ...e, enfants: e.enfants.filter(visible) } : e))
    .filter((e) => !e.enfants || e.enfants.length),
)

const estActive = (entree: EntreeMenu): boolean =>
  entree.route ? route.path.startsWith(entree.route) : !!entree.enfants?.some(estActive)

// Groupes ouverts : celui de la page courante s'ouvre automatiquement
const ouverts = reactive<Record<string, boolean>>({})
watch(
  () => route.path,
  () => entrees.value.forEach((e) => e.enfants && estActive(e) && (ouverts[e.libelle] = true)),
  { immediate: true },
)

/** Le logo sert de bouton : réduit / agrandit le menu (ferme le menu sur mobile) */
function clicLogo() {
  if (ui.menuMobileOuvert) ui.fermerMenuMobile()
  else ui.basculerMenu()
}

function basculerGroupe(entree: EntreeMenu) {
  if (ui.menuReduit) {
    ui.menuReduit = false
    ouverts[entree.libelle] = true
    return
  }
  ouverts[entree.libelle] = !ouverts[entree.libelle]
}
</script>

<template>
  <div v-if="ui.menuMobileOuvert" class="voile-mobile" @click="ui.fermerMenuMobile" />
  <aside class="menu" :class="{ reduit: ui.menuReduit, 'ouvert-mobile': ui.menuMobileOuvert }" aria-label="Menu principal">
    <button
      type="button"
      class="marque"
      :aria-label="ui.menuReduit ? 'Agrandir le menu' : 'Réduire le menu'"
      :title="ui.menuReduit ? 'Agrandir le menu' : 'Réduire le menu'"
      @click="clicLogo"
    >
      <img src="/logo_gauche.svg" alt="" class="logo-icone" />
      <img v-if="!ui.menuReduit" src="/Logo_lalamby_2.svg" alt="" class="logo" />
    </button>

    <nav class="navigation">
      <ul>
        <li v-for="entree in entrees" :key="entree.libelle">
          <!-- Entrée simple -->
          <RouterLink
            v-if="entree.route"
            :to="entree.route"
            class="lien"
            :class="{ actif: estActive(entree) }"
            :title="ui.menuReduit ? entree.libelle : undefined"
            @click="ui.fermerMenuMobile"
          >
            <i :class="`bi bi-${entree.icone}`" aria-hidden="true" />
            <span class="libelle">{{ entree.libelle }}</span>
          </RouterLink>

          <!-- Groupe avec sous-onglets -->
          <template v-else>
            <button
              type="button"
              class="lien"
              :class="{ 'parent-actif': estActive(entree) }"
              :aria-expanded="!!ouverts[entree.libelle] && !ui.menuReduit"
              :title="ui.menuReduit ? entree.libelle : undefined"
              @click="basculerGroupe(entree)"
            >
              <i :class="`bi bi-${entree.icone}`" aria-hidden="true" />
              <span class="libelle">{{ entree.libelle }}</span>
              <i class="bi bi-chevron-down chevron" :class="{ tourne: ouverts[entree.libelle] }" aria-hidden="true" />
            </button>
            <ul v-show="ouverts[entree.libelle] && !ui.menuReduit" class="sous-menu">
              <li v-for="enfant in entree.enfants" :key="enfant.route">
                <RouterLink
                  :to="enfant.route!"
                  class="lien sous-lien"
                  :class="{ actif: estActive(enfant) }"
                  @click="ui.fermerMenuMobile"
                >
                  <span class="libelle">{{ enfant.libelle }}</span>
                </RouterLink>
              </li>
            </ul>
          </template>
        </li>
      </ul>
    </nav>

    <RouterLink
      to="/profil"
      class="profil"
      :class="{ actif: route.path.startsWith('/profil') }"
      :title="ui.menuReduit ? auth.nomAffiche : undefined"
      @click="ui.fermerMenuMobile"
    >
      <UiAvatar :nom="auth.nomAffiche" :matricule="auth.matricule" />
      <span class="libelle identite">
        <span class="nom tronquer">{{ auth.nomAffiche }}</span>
        <span class="email tronquer">{{ auth.email || 'Pas d’adresse e-mail' }}</span>
      </span>
    </RouterLink>
  </aside>
</template>

<style scoped>
.menu {
  position: sticky;
  top: 0;
  height: 100vh;
  width: var(--largeur-menu);
  flex: none;
  display: flex;
  flex-direction: column;
  background: var(--marine);
  color: rgba(255, 255, 255, 0.78);
  transition: width var(--transition);
  z-index: 50;
}
.menu.reduit { width: var(--largeur-menu-reduit); }

.marque {
  display: flex;
  align-items: center;
  gap: var(--e3);
  height: var(--hauteur-barre);
  padding: 0 var(--e5);
  border: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: none;
  cursor: pointer;
}
.marque:hover { background: rgba(255, 255, 255, 0.04); }
.marque:focus-visible { box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.5); }
.logo-icone { height: 30px; width: 30px; flex: none; }
.logo { height: 26px; width: auto; min-width: 0; }
.reduit .marque { justify-content: center; padding: 0; }

.navigation { flex: 1; overflow-y: auto; padding: var(--e3) 0; }
.navigation ul { list-style: none; }

.lien {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--e3);
  width: 100%;
  min-height: 40px;
  padding: var(--e2) var(--e5);
  border: none;
  background: none;
  color: inherit;
  font-size: var(--taille-s);
  font-weight: 500;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
  transition: background var(--transition), color var(--transition);
}
.lien .bi:first-child { font-size: 1.05rem; width: 20px; text-align: center; flex: none; }
.lien:hover { background: rgba(255, 255, 255, 0.06); color: #fff; text-decoration: none; }
.lien:focus-visible { box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.5); }

/* Page courante : trait rouge à gauche, comme l'aiguille du logo */
.lien.actif { background: var(--marine-fonce); color: #fff; font-weight: 600; }
.lien.actif::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: var(--rouge);
}
.parent-actif { color: #fff; }

.chevron { margin-left: auto; font-size: 0.75rem; transition: transform var(--transition); }
.chevron.tourne { transform: rotate(180deg); }

.sous-menu { padding-bottom: var(--e2); }
.sous-lien { min-height: 34px; padding-left: calc(var(--e5) + 20px + var(--e3)); font-size: var(--taille-s); }

.reduit .libelle, .reduit .chevron { display: none; }
.reduit .lien { justify-content: center; padding: var(--e2) 0; }

.profil {
  display: flex;
  align-items: center;
  gap: var(--e3);
  padding: var(--e3) var(--e4);
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  color: inherit;
  text-decoration: none;
}
.profil:hover { background: rgba(255, 255, 255, 0.06); text-decoration: none; }
.profil.actif { background: var(--marine-fonce); }
.profil:focus-visible { box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.5); }
.profil .avatar { background: rgba(255, 255, 255, 0.12); color: #fff; }
.identite { display: flex; flex-direction: column; min-width: 0; line-height: 1.3; }
.identite .nom { color: #fff; font-weight: 600; font-size: var(--taille-s); }
.identite .email { color: rgba(255, 255, 255, 0.6); font-size: var(--taille-xs); }
.reduit .profil { justify-content: center; padding: var(--e3) 0; }

.voile-mobile { display: none; }

@media (max-width: 900px) {
  .menu, .menu.reduit {
    position: fixed;
    left: 0;
    width: var(--largeur-menu);
    transform: translateX(-100%);
    transition: transform var(--transition);
  }
  .menu.ouvert-mobile { transform: none; box-shadow: var(--ombre-haute); }
  .reduit .libelle, .reduit .chevron { display: inline; }
  .reduit .lien { justify-content: flex-start; padding: var(--e2) var(--e5); }
  .reduit .profil { justify-content: flex-start; padding: var(--e3) var(--e4); }
  .reduit .identite { display: flex; }
  .voile-mobile { display: block; position: fixed; inset: 0; z-index: 40; background: rgba(15, 36, 64, 0.4); }
}
</style>
