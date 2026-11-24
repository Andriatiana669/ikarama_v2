<!-- Mon profil : ma fiche, mon responsable, mes équipes, mes subordonnés directs. -->
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { equipesApi, monResumeApi, utilisateursApi } from '@/api'
import { useRequete } from '@/composables/useRequete'
import { useAuthStore } from '@/store/auth'
import type { EmployeResume, Equipe } from '@/types'
import { formatDateHeure, pluriel } from '@/utils/format'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiAvatar from '@/components/ui/UiAvatar.vue'
import UiChargement from '@/components/ui/UiChargement.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'

const auth = useAuthStore()
const employe = computed(() => auth.employe)

const equipes = useRequete(() => equipesApi.mesEquipes(), [] as Equipe[])
// Résumé : affaires / prestations où je suis « Employé » d'une ligne de feuille, moyennes des notes
const resume = useRequete(() => monResumeApi(), null as Awaited<ReturnType<typeof monResumeApi>> | null)
const note = (v: number | null) => (v === null ? '—' : v.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
const classeNote = (v: number | null) => (v === null ? '' : v >= 4 ? 'bonne' : v >= 2.5 ? 'moyenne' : 'faible')
const quantite = (v: number) => v.toLocaleString('fr-FR', { maximumFractionDigits: 0 })
const subordonnes = useRequete(
  async () => (employe.value ? utilisateursApi.subordonnes(employe.value.id) : []),
  [] as EmployeResume[],
)
onMounted(() => {
  equipes.executer()
  subordonnes.executer()
  resume.executer()
})

</script>

<template>
  <div class="page">
    <EnTetePage titre="Mon profil" description="Ces informations viennent de l'API RH. Pour les corriger, contactez le service RH." />

    <section class="carte resume">
      <header class="carte-entete">
        <h2>Mon résumé</h2>
        <span class="texte-xs texte-doux">Lignes de feuille où je suis « Employé »</span>
      </header>
      <div class="carte-corps pile">
        <UiChargement v-if="resume.chargement.value" />
        <p v-else-if="!resume.donnees.value?.nb_lignes" class="texte-doux texte-petit">Vous n'êtes « Employé » d'aucune ligne de feuille pour l'instant.</p>
        <template v-else>
          <div class="indicateurs">
            <div class="indicateur">
              <span class="libelle">Affaires et prestations</span>
              <strong>{{ resume.donnees.value!.groupes.length }}</strong>
              <span class="texte-xs texte-doux">{{ pluriel(resume.donnees.value!.nb_lignes, 'ligne') }}</span>
            </div>
            <div class="indicateur" :class="classeNote(resume.donnees.value!.note_rendement)">
              <span class="libelle">Note de rendement moyenne</span>
              <strong>{{ note(resume.donnees.value!.note_rendement) }}</strong>
              <span class="texte-xs texte-doux">sur {{ pluriel(resume.donnees.value!.nb_notes_rendement, 'ligne notée', 'lignes notées') }}</span>
            </div>
            <div class="indicateur" :class="classeNote(resume.donnees.value!.note_qualite)">
              <span class="libelle">Note de qualité moyenne</span>
              <strong>{{ note(resume.donnees.value!.note_qualite) }}</strong>
              <span class="texte-xs texte-doux">sur {{ pluriel(resume.donnees.value!.nb_notes_qualite, 'ligne notée', 'lignes notées') }}</span>
            </div>
          </div>
          <div class="tableau-conteneur">
            <table class="tableau">
              <thead>
                <tr><th>Affaire</th><th>Prestation</th><th class="droite">Lignes</th><th class="droite">Quantité</th>
                  <th class="droite">Note de rendement</th><th class="droite">Note de qualité</th></tr>
              </thead>
              <tbody>
                <tr v-for="g in resume.donnees.value!.groupes" :key="`${g.affaire}-${g.prestation}`">
                  <td class="gras">{{ g.affaire }}</td>
                  <td>{{ g.prestation }}</td>
                  <td class="droite">{{ g.nb_lignes }}</td>
                  <td class="droite nowrap">{{ quantite(g.quantite) }} {{ g.unite }}</td>
                  <td class="droite"><span class="note" :class="classeNote(g.note_rendement)" :title="`${g.nb_notes_rendement} ligne(s) notée(s)`">{{ note(g.note_rendement) }}</span></td>
                  <td class="droite"><span class="note" :class="classeNote(g.note_qualite)" :title="`${g.nb_notes_qualite} ligne(s) notée(s)`">{{ note(g.note_qualite) }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="texte-xs texte-doux">
            Moyennes des lignes notées seulement : la Note de rendement n'existe qu'une fois le projet au statut qui l'active,
            et une ligne sans temps n'a pas de note.
          </p>
        </template>
      </div>
    </section>

    <div class="grille-2">
      <section class="carte">
        <div class="carte-corps pile">
          <div class="ligne identite">
            <UiAvatar :nom="auth.nomAffiche" :matricule="employe?.code_barre" grand />
            <div>
              <h2>{{ auth.nomAffiche }}</h2>
              <p class="code">{{ employe?.code_barre || auth.utilisateur?.username }}</p>
            </div>
          </div>
          <dl class="fiche">
            <dt>Nom complet</dt><dd>{{ employe ? `${employe.prenom} ${employe.nom}` : '—' }}</dd>
            <dt>E-mail</dt><dd>{{ employe?.email || auth.utilisateur?.email || '—' }}</dd>
            <template v-for="poste in employe?.postes ?? []" :key="poste.id">
              <dt>Poste</dt><dd>{{ poste.poste_nom || '—' }} <span v-if="poste.poste_statut" class="badge">{{ poste.poste_statut }}</span></dd>
              <dt>Pôle</dt><dd>{{ poste.pole || '—' }}</dd>
            </template>
            <dt>Responsable (N+1)</dt><dd><UiEmploye :employe="employe?.chef" /></dd>
            <dt>Profil</dt>
            <dd><span :class="auth.estAdministrateur ? 'badge badge-rouge' : 'badge'">{{ auth.estAdministrateur ? 'Administrateur' : 'Utilisateur' }}</span></dd>
            <dt>Dernière mise à jour RH</dt><dd>{{ formatDateHeure(employe?.derniere_synchro) }}</dd>
          </dl>
        </div>
      </section>

      <div class="pile">
        <section class="carte">
          <header class="carte-entete"><h2>Mes équipes</h2></header>
          <div class="carte-corps">
            <UiChargement v-if="equipes.chargement.value" />
            <p v-else-if="!equipes.donnees.value.length" class="texte-doux texte-petit">Vous n'êtes membre d'aucune équipe.</p>
            <ul v-else class="liste">
              <li v-for="equipe in equipes.donnees.value" :key="equipe.id" class="ligne-entre">
                <span>
                  <span class="gras">Équipe de {{ equipe.responsable.nom_affiche }}</span>
                  <span class="texte-doux texte-xs bloc">
                    {{ [equipe.pole, pluriel(equipe.nb_membres, 'collaborateur')].filter(Boolean).join(', ') }}
                  </span>
                </span>
                <span :class="['badge', equipe.mon_role === 'RESPONSABLE' ? 'badge-marine' : '']">
                  {{ equipe.mon_role === 'RESPONSABLE' ? 'Responsable' : 'Membre' }}
                </span>
              </li>
            </ul>
          </div>
        </section>

        <section class="carte">
          <header class="carte-entete">
            <h2>Mes collaborateurs directs</h2>
            <span class="badge">{{ subordonnes.donnees.value.length }}</span>
          </header>
          <div class="carte-corps">
            <p v-if="!subordonnes.donnees.value.length" class="texte-doux texte-petit">Personne ne vous est rattaché directement.</p>
            <ul v-else class="liste">
              <li v-for="s in subordonnes.donnees.value" :key="s.id"><UiEmploye :employe="s" /></li>
            </ul>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.identite { gap: var(--e4); }
.liste { list-style: none; display: flex; flex-direction: column; gap: var(--e3); }
.bloc { display: block; }
.grille-2 { align-items: start; }
.resume { margin-bottom: var(--e4); }
.indicateurs { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--e3); }
.indicateur { display: flex; flex-direction: column; gap: 2px; padding: var(--e3); border-radius: var(--rayon); background: var(--surface-douce); border-left: 4px solid var(--bordure-forte); }
.indicateur .libelle { font-size: var(--taille-s); color: var(--texte-doux); font-weight: 600; }
.indicateur strong { font-size: var(--taille-xxl); color: var(--marine); }
.indicateur.bonne { border-left-color: var(--succes); }
.indicateur.moyenne { border-left-color: var(--attention); }
.indicateur.faible { border-left-color: var(--rouge); }
.note { display: inline-block; min-width: 48px; padding: 1px 8px; border-radius: 999px; font-weight: 700; text-align: center; }
.note.bonne { background: color-mix(in srgb, var(--succes) 15%, transparent); color: var(--succes); }
.note.moyenne { background: color-mix(in srgb, var(--attention) 15%, transparent); color: var(--attention); }
.note.faible { background: color-mix(in srgb, var(--rouge) 12%, transparent); color: var(--rouge); }
.droite { text-align: right; }
.nowrap { white-space: nowrap; }
</style>
