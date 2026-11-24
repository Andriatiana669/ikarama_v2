// src/utils/format.ts
// Fonctions d'affichage réutilisables (dates, noms, initiales).
import { format, formatDistanceToNowStrict, parseISO, isValid } from 'date-fns'
import { fr } from 'date-fns/locale'
import type { EmployeResume } from '@/types'

const lire = (valeur?: string | Date | null): Date | null => {
  if (!valeur) return null
  const date = typeof valeur === 'string' ? parseISO(valeur) : valeur
  return isValid(date) ? date : null
}

/** 09/11/2026 */
export const formatDate = (valeur?: string | Date | null) => {
  const date = lire(valeur)
  return date ? format(date, 'dd/MM/yyyy', { locale: fr }) : '—'
}

/** 09/11/2026 à 14:05 */
export const formatDateHeure = (valeur?: string | Date | null) => {
  const date = lire(valeur)
  return date ? format(date, "dd/MM/yyyy 'à' HH:mm", { locale: fr }) : '—'
}

/** « Jeannot Rakoto » (prénom usuel en priorité) */
export const nomEmploye = (employe?: Partial<EmployeResume> | null) =>
  employe ? employe.nom_affiche || `${employe.prenom_usuel || employe.prenom || ''} ${employe.nom || ''}`.trim() : '—'

/** « JR » */
export const initiales = (texte?: string | null) =>
  (texte || '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((mot) => mot[0]?.toUpperCase())
    .join('')

/** Pluriel simple : pluriel(3, 'équipe') -> « 3 équipes » */
export const pluriel = (nombre: number, mot: string, motPluriel = `${mot}s`) =>
  `${nombre} ${nombre > 1 ? motPluriel : mot}`

/** 1 234,5 (sans zéros inutiles) ; « — » si vide */
export const formatNombre = (valeur?: string | number | null) =>
  valeur === null || valeur === undefined || valeur === '' ? '—' : Number(valeur).toLocaleString('fr-FR', { maximumFractionDigits: 2 })

/** Couleur de texte lisible (sombre ou blanche) sur un fond donné (#RRGGBB) */
export function couleurTexte(fond?: string | null) {
  const hex = (fond || '').replace('#', '')
  if (hex.length !== 6) return 'var(--texte)'
  const [r, v, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  const lumiere = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  const luminance = 0.2126 * lumiere(r!) + 0.7152 * lumiere(v!) + 0.0722 * lumiere(b!)
  return luminance > 0.45 ? '#1b2738' : '#ffffff'
}

/** « il y a 2 minutes » */
export const formatRelatif = (valeur?: string | Date | null) => {
  const date = lire(valeur)
  return date ? formatDistanceToNowStrict(date, { locale: fr, addSuffix: true }) : '—'
}

/** 450 minutes -> « 7,5 h » */
export const formatHeures = (minutes?: number | null) =>
  minutes === null || minutes === undefined ? '—' : `${(minutes / 60).toLocaleString('fr-FR', { maximumFractionDigits: 2 })} h`

/** « 07:30:00 » -> « 07:30 » */
export const formatHeure = (valeur?: string | null) => (valeur ? valeur.slice(0, 5) : '—')

/** « 2026-11-02 » -> « Lundi 02 novembre 2026 » */
export const formatJourLong = (valeur?: string | null) => {
  const date = lire(valeur)
  if (!date) return '—'
  const texte = format(date, 'EEEE dd MMMM yyyy', { locale: fr })
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}
