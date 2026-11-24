<!-- Fiche détaillée d'un employé (dans une modale) avec ses subordonnés. -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { utilisateursApi } from '@/api'
import type { Employe, EmployeResume } from '@/types'
import { formatDateHeure } from '@/utils/format'
import UiAvatar from '@/components/ui/UiAvatar.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'
import UiModale from '@/components/ui/UiModale.vue'
import UiOnglets from '@/components/ui/UiOnglets.vue'

const ouvert = defineModel<boolean>({ default: false })
const props = defineProps<{ employe: Employe | null }>()

const onglet = ref('fiche')
const niveau = ref<'direct' | 'hierarchie'>('direct')
const subordonnes = ref<EmployeResume[]>([])

watch(
  () => [props.employe?.id, niveau.value, ouvert.value] as const,
  async ([id, , estOuvert]) => {
    if (!id || !estOuvert) return
    subordonnes.value = await utilisateursApi.subordonnes(id, niveau.value)
  },
)
watch(ouvert, (valeur) => valeur && (onglet.value = 'fiche'))
</script>

<template>
  <UiModale v-model="ouvert" :titre="employe?.nom_affiche ?? ''" :sous-titre="employe?.code_barre ?? undefined" taille="grande">
    <template v-if="employe">
      <div class="identite ligne">
        <UiAvatar :nom="employe.nom_affiche" :matricule="employe.code_barre" grand />
        <div>
          <p class="gras">{{ employe.civilite }} {{ employe.prenom }} {{ employe.nom }}</p>
          <p class="texte-doux texte-petit">{{ employe.email || 'Pas d’adresse e-mail' }}</p>
        </div>
      </div>

      <UiOnglets
        v-model="onglet"
        :onglets="[
          { valeur: 'fiche', libelle: 'Fiche', icone: 'person-vcard' },
          { valeur: 'equipe', libelle: 'Subordonnés', icone: 'diagram-2', compteur: employe.nb_subordonnes },
        ]"
      />

      <div v-if="onglet === 'fiche'" class="contenu-onglet">
        <dl class="fiche">
          <dt>Matricule</dt><dd>{{ employe.code_barre || '—' }}</dd>
          <dt>Responsable (N+1)</dt><dd><UiEmploye :employe="employe.chef" /></dd>
          <template v-for="poste in employe.postes" :key="poste.id">
            <dt>Poste</dt><dd>{{ poste.poste_nom || '—' }} <span class="badge">{{ poste.poste_statut }}</span></dd>
            <dt>Pôle</dt><dd>{{ poste.pole || '—' }}</dd>
          </template>
          <dt>Compte Ikarama</dt>
          <dd>
            <span :class="employe.a_un_compte ? 'badge badge-succes' : 'badge'">
              {{ employe.a_un_compte ? 'Déjà connecté' : 'Jamais connecté' }}
            </span>
          </dd>
          <dt>Dernière synchro RH</dt><dd>{{ formatDateHeure(employe.derniere_synchro) }}</dd>
        </dl>
      </div>

      <div v-else class="contenu-onglet pile">
        <div class="ligne">
          <label class="case"><input v-model="niveau" type="radio" value="direct" /> Directs (N-1)</label>
          <label class="case"><input v-model="niveau" type="radio" value="hierarchie" /> Toute la hiérarchie</label>
        </div>
        <p v-if="!subordonnes.length" class="texte-doux texte-petit">Aucun subordonné.</p>
        <ul v-else class="liste-subordonnes">
          <li v-for="s in subordonnes" :key="s.id"><UiEmploye :employe="s" /></li>
        </ul>
      </div>
    </template>
  </UiModale>
</template>

<style scoped>
.identite { margin-bottom: var(--e4); gap: var(--e4); }
.contenu-onglet { padding-top: var(--e4); }
.liste-subordonnes { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--e3); }
</style>
