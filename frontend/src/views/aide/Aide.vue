<!--
  Aide : le guide utilisateur. Même contenu que docs/guide/*.md (un seul texte, lu ici et dans le dépôt).
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { marked } from 'marked'
import { useAuthStore } from '@/store/auth'
import guideEmploye from '@docs/guide/employe.md?raw'
import guideResponsable from '@docs/guide/responsable.md?raw'
import guideAdministrateur from '@docs/guide/administrateur.md?raw'

const auth = useAuthStore()
const GUIDES = [
  { cle: 'employe', libelle: 'Employé', icone: 'person', texte: guideEmploye },
  { cle: 'responsable', libelle: 'Responsable', icone: 'person-badge', texte: guideResponsable },
  { cle: 'administrateur', libelle: 'Administrateur', icone: 'shield-lock', texte: guideAdministrateur, admin: true },
]
const guides = computed(() => GUIDES.filter((g) => !g.admin || auth.estAdministrateur))
const actif = ref('employe')
const guide = computed(() => guides.value.find((g) => g.cle === actif.value) ?? guides.value[0]!)

// Contenu écrit par l'équipe (docs/guide) : pas de HTML venant des utilisateurs
const html = computed(() => marked.parse(guide.value.texte, { async: false }) as string)
const sommaire = computed(() =>
  [...guide.value.texte.matchAll(/^## (.+)$/gm)].map((m, i) => ({ id: `section-${i}`, titre: m[1]! })),
)
const contenu = ref<HTMLElement | null>(null)
watch(html, async () => {
  await nextTick()
  contenu.value?.querySelectorAll('h2').forEach((h, i) => (h.id = `section-${i}`))
}, { immediate: true })
const aller = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
</script>

<template>
  <div class="page page-large">
    <header class="ligne-titre">
      <div>
        <h1>Aide</h1>
        <p class="texte-doux texte-petit">Le guide d'utilisation d'Ikarama, selon votre rôle.</p>
      </div>
    </header>

    <div class="onglets" role="tablist">
      <button v-for="g in guides" :key="g.cle" type="button" role="tab" :aria-selected="actif === g.cle" :class="{ actif: actif === g.cle }"
        @click="actif = g.cle">
        <i :class="`bi bi-${g.icone}`" aria-hidden="true" /> {{ g.libelle }}
      </button>
    </div>

    <div class="disposition">
      <nav class="carte sommaire" aria-label="Sommaire">
        <p class="titre-sommaire">Sommaire</p>
        <button v-for="s in sommaire" :key="s.id" type="button" @click="aller(s.id)">{{ s.titre }}</button>
      </nav>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <article ref="contenu" class="carte guide" v-html="html" />
    </div>
  </div>
</template>

<style scoped>
.page-large { max-width: 1200px; }
.ligne-titre { margin-bottom: var(--e4); }
.onglets { display: flex; gap: var(--e2); margin-bottom: var(--e4); flex-wrap: wrap; }
.onglets button { display: inline-flex; align-items: center; gap: var(--e2); padding: 8px 16px; border: 1px solid var(--bordure-forte); border-radius: var(--rayon); background: var(--surface); font-weight: 600; color: var(--texte-doux); cursor: pointer; }
.onglets button.actif { background: var(--marine); border-color: var(--marine); color: #fff; }
.disposition { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: var(--e4); align-items: start; }
.sommaire { position: sticky; top: 76px; display: flex; flex-direction: column; gap: 2px; padding: var(--e3); }
.titre-sommaire { font-size: var(--taille-xs); font-weight: 700; color: var(--texte-doux); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: var(--e2); }
.sommaire button { padding: 5px 8px; border: none; border-radius: var(--rayon-s); background: none; text-align: left; font-size: var(--taille-s); color: var(--marine); cursor: pointer; }
.sommaire button:hover { background: var(--marine-pale); }
.guide { padding: var(--e5, 28px) var(--e5, 32px); line-height: 1.65; }
.guide :deep(h1) { font-size: var(--taille-xl); color: var(--marine); margin-bottom: var(--e3); }
.guide :deep(h2) { font-size: var(--taille-l); color: var(--marine); margin: var(--e5, 28px) 0 var(--e2); padding-top: var(--e2); border-top: 1px solid var(--bordure); scroll-margin-top: 80px; }
.guide :deep(h3) { font-size: var(--taille-m); color: var(--marine); margin: var(--e4) 0 var(--e2); }
.guide :deep(p) { margin: var(--e2) 0; }
.guide :deep(ul), .guide :deep(ol) { margin: var(--e2) 0 var(--e2) 1.3rem; }
.guide :deep(li) { margin: 3px 0; }
.guide :deep(code) { padding: 1px 6px; border-radius: 4px; background: var(--surface-douce); font-size: 0.88em; }
.guide :deep(table) { width: 100%; margin: var(--e3) 0; border-collapse: collapse; font-size: var(--taille-s); }
.guide :deep(th), .guide :deep(td) { padding: 6px 10px; border: 1px solid var(--bordure); text-align: left; vertical-align: top; }
.guide :deep(th) { background: var(--surface-douce); color: var(--texte-doux); }
.guide :deep(strong) { color: var(--texte); }
@media (max-width: 900px) { .disposition { grid-template-columns: 1fr; } .sommaire { position: static; } }
</style>
