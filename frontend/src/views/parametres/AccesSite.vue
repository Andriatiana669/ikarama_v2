<!--
  Paramètres > Accès au site (administrateurs).
  Règles « Autoriser » / « Refuser » par pôle, poste, matricule ou responsable N+1.
  La logique est côté serveur : backend/autorisations/acces.py
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { accesApi, reglesAccesApi } from '@/api'
import { ApiErreur } from '@/api/client'
import { useConfirmation } from '@/composables/useConfirmation'
import { useRequete } from '@/composables/useRequete'
import type { ApercuAcces, ChampFormulaire, Colonne, Identifiant, Option, RegleAcces } from '@/types'
import { pluriel } from '@/utils/format'
import GestionCrud from '@/components/formulaires/GestionCrud.vue'
import EtatAcces from '@/components/parametres/EtatAcces.vue'
import VerifierAcces from '@/components/parametres/VerifierAcces.vue'
import EnTetePage from '@/components/ui/EnTetePage.vue'
import UiEmploye from '@/components/ui/UiEmploye.vue'

const { confirmer } = useConfirmation()
const apercu = useRequete(() => accesApi.apercu(), null as ApercuAcces | null)
const verification = ref<{ rafraichir: () => void } | null>(null)
onMounted(apercu.executer)

function apresModification() {
  apercu.executer()
  verification.value?.rafraichir()
}

/**
 * Si une modification retire son propre accès, le serveur répond 409 « perte_acces » :
 * on demande confirmation, puis on renvoie la même demande avec ?confirmer=1.
 */
async function avecConfirmation<R>(operation: (confirmer: boolean) => Promise<R>): Promise<R> {
  try {
    return await operation(false)
  } catch (e) {
    if (e instanceof ApiErreur && e.code === 'perte_acces') {
      const ok = await confirmer({
        titre: 'Vous allez perdre votre accès',
        message: `${e.message} Pour revenir en arrière, il faudra passer par l'administration Django (compte avec mot de passe) ou la commande « manage.py acces_site ».`,
        libelleConfirmer: 'Oui, enregistrer',
        danger: true,
      })
      if (ok) return operation(true)
    }
    throw e
  }
}

const ressource = {
  lister: reglesAccesApi.lister,
  creer: (d: Partial<RegleAcces>) => avecConfirmation((c) => reglesAccesApi.creer(d, c)),
  modifier: (id: Identifiant, d: Partial<RegleAcces>) => avecConfirmation((c) => reglesAccesApi.modifier(id, d, c)),
  supprimer: (id: Identifiant) => avecConfirmation((c) => reglesAccesApi.supprimer(id, c)),
}

const EFFETS: Option[] = [
  { valeur: 'AUTORISER', libelle: 'Autoriser' },
  { valeur: 'REFUSER', libelle: 'Refuser' },
]
const CRITERES: Option[] = [
  { valeur: 'POLE', libelle: 'Pôle' },
  { valeur: 'POSTE', libelle: 'Poste' },
  { valeur: 'MATRICULE', libelle: 'Matricule (une personne)' },
  { valeur: 'N1', libelle: 'Responsable N+1' },
]
const PORTEES: Option[] = [
  { valeur: 'DIRECT', libelle: 'Ses collaborateurs directs' },
  { valeur: 'HIERARCHIE', libelle: 'Toute la hiérarchie sous lui (N-1, N-2…)' },
]

// Listes de tous les pôles et postes (une seule requête, partagée par les deux champs)
let valeurs: Promise<{ poles: string[]; postes: string[] }> | null = null
const lireValeurs = () => (valeurs ??= accesApi.valeurs())
const enOptions = (liste: string[]): Option[] => liste.map((v) => ({ valeur: v, libelle: v }))

const champs: ChampFormulaire[] = [
  { cle: 'effet', libelle: 'Effet', type: 'select', requis: true, options: EFFETS, aide: 'Un refus l’emporte toujours sur une autorisation.' },
  { cle: 'critere', libelle: 'Critère', type: 'select', requis: true, options: CRITERES },
  {
    cle: 'pole', libelle: 'Pôle', type: 'select', requis: true, pleineLargeur: true,
    chargerOptions: async () => enOptions((await lireValeurs()).poles),
    visible: (v) => v.critere === 'POLE',
  },
  {
    cle: 'poste', libelle: 'Poste', type: 'select', requis: true, pleineLargeur: true,
    chargerOptions: async () => enOptions((await lireValeurs()).postes),
    visible: (v) => v.critere === 'POSTE',
  },
  {
    cle: 'employe', libelle: 'Personne', type: 'employe', requis: true,
    rechercherEmploye: accesApi.employes,
    visible: (v) => v.critere === 'MATRICULE',
    pleineLargeur: true,
  },
  {
    cle: 'employe', libelle: 'Responsable N+1', type: 'employe', requis: true,
    rechercherEmploye: accesApi.employes,
    aide: 'Le responsable lui-même n’est pas concerné : ajoutez-le par son matricule si besoin.',
    visible: (v) => v.critere === 'N1',
  },
  { cle: 'portee', libelle: 'Portée', type: 'select', requis: true, options: PORTEES, visible: (v) => v.critere === 'N1' },
  { cle: 'commentaire', libelle: 'Commentaire', type: 'texte', placeholder: 'Pourquoi cette règle ?', pleineLargeur: true },
  { cle: 'actif', libelle: 'Règle active', type: 'case' },
]

const filtres: ChampFormulaire[] = [
  { cle: 'effet', libelle: 'Effet', type: 'select', options: EFFETS, placeholder: 'Tous' },
  { cle: 'critere', libelle: 'Critère', type: 'select', options: CRITERES, placeholder: 'Tous' },
]

const colonnes: Colonne[] = [
  { cle: 'effet', libelle: 'Effet', largeur: '120px', triable: true },
  { cle: 'regle', libelle: 'Règle' },
  { cle: 'nb_personnes', libelle: 'Personnes', alignement: 'droite' },
  { cle: 'commentaire', libelle: 'Commentaire' },
  { cle: 'actif', libelle: 'État', alignement: 'centre' },
]

const textes = {
  nouveau: 'Nouvelle règle',
  modifier: 'Modifier la règle',
  supprimer: 'Supprimer cette règle ?',
  enregistre: 'Règle enregistrée',
  supprime: 'Règle supprimée',
  vide: 'Aucune règle : le site est ouvert à tous',
  recherche: 'Pôle, poste, matricule, commentaire',
  boutonSupprimer: 'Supprimer',
}
</script>

<template>
  <div class="page pile">
    <EnTetePage
      titre="Accès au site"
      description="Choisissez qui peut entrer sur Ikarama. Les personnes refusées voient une page « Accès non autorisé » et n'apparaissent nulle part dans l'application, sauf si elles se sont déjà connectées."
    />

    <EtatAcces :apercu="apercu.donnees.value" />

    <div class="disposition">
      <GestionCrud
        :ressource="ressource"
        :colonnes="colonnes"
        :champs="champs"
        :filtres="filtres"
        :textes="textes"
        :valeurs-par-defaut="{ effet: 'AUTORISER', critere: 'POLE', portee: 'DIRECT', actif: true }"
        @modifie="apresModification"
      >
        <template #cellule-effet="{ ligne }">
          <span :class="['badge', ligne.effet === 'REFUSER' ? 'badge-rouge' : 'badge-succes']">{{ ligne.effet_libelle }}</span>
        </template>
        <template #cellule-regle="{ ligne }">
          <span class="texte-doux texte-xs bloc">{{ ligne.critere_libelle }}</span>
          <UiEmploye v-if="ligne.employe_details" :employe="ligne.employe_details" />
          <span v-else class="gras">{{ ligne.pole || ligne.poste }}</span>
          <span v-if="ligne.critere === 'N1'" class="texte-xs texte-doux bloc">{{ ligne.portee_libelle }}</span>
        </template>
        <template #cellule-nb_personnes="{ ligne }">{{ pluriel(ligne.nb_personnes, 'personne') }}</template>
        <template #cellule-commentaire="{ ligne }">
          <span class="texte-doux">{{ ligne.commentaire || '—' }}</span>
        </template>
        <template #cellule-actif="{ ligne }">
          <span :class="['badge', ligne.actif ? 'badge-marine' : '']">{{ ligne.actif ? 'Active' : 'Inactive' }}</span>
        </template>
      </GestionCrud>

      <VerifierAcces ref="verification" />
    </div>
  </div>
</template>

<style scoped>
.disposition { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: var(--e4); align-items: start; }
.bloc { display: block; }
@media (max-width: 1100px) { .disposition { grid-template-columns: 1fr; } }
</style>
