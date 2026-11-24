// src/store/interface.ts
// État de l'interface (menu latéral) partagé entre Sidebar et Navbar.
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const CLE = 'ika_menu_reduit'

export const useInterfaceStore = defineStore('interface', () => {
  const menuReduit = ref(localStorage.getItem(CLE) === '1')
  const menuMobileOuvert = ref(false)

  watch(menuReduit, (valeur) => localStorage.setItem(CLE, valeur ? '1' : '0'))

  const basculerMenu = () => (menuReduit.value = !menuReduit.value)
  const ouvrirMenuMobile = () => (menuMobileOuvert.value = true)
  const fermerMenuMobile = () => (menuMobileOuvert.value = false)

  return { menuReduit, menuMobileOuvert, basculerMenu, ouvrirMenuMobile, fermerMenuMobile }
})
