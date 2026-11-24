// src/utils/pointage.ts
// Même règle que le serveur (backend/pointages/calculs.py), pour l'aperçu du formulaire.
const DEBUT_JOURNEE = 7 * 60 + 30
const FIN_JOURNEE = 16 * 60 + 30
const PAUSE = 60

const minutes = (heure: string) => {
  const [h, m] = heure.split(':').map(Number)
  return h === undefined || m === undefined || Number.isNaN(h) || Number.isNaN(m) ? null : h * 60 + m
}

/** { normales, hs } en minutes, ou null si les heures sont incomplètes / incohérentes */
export function calculerPointage(date: string, debut: string, fin: string, pause: boolean) {
  const d = minutes(debut)
  const f = minutes(fin)
  if (d === null || f === null || f <= d || !date) return null
  const jour = new Date(`${date}T12:00:00`).getDay() // 0 = dimanche, 6 = samedi
  const ouvrable = jour >= 1 && jour <= 5
  let normales = ouvrable ? Math.max(0, Math.min(f, FIN_JOURNEE) - Math.max(d, DEBUT_JOURNEE)) : 0
  let hs = f - d - normales
  if (pause) {
    const retrait = Math.min(PAUSE, normales)
    normales -= retrait
    hs -= Math.min(PAUSE - retrait, hs)
  }
  return { normales, hs, ouvrable }
}

const enHeure = (m: number) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`

/** Créneaux non pointés de 07:30–16:30 pour des pointages « HH:MM » d'un jour ouvrable */
export function creneauxLibres(pointages: { heure_debut: string; heure_fin: string }[]): [string, string][] {
  const intervalles = pointages
    .map((p) => [minutes(p.heure_debut.slice(0, 5)), minutes(p.heure_fin.slice(0, 5))] as const)
    .filter((i): i is readonly [number, number] => i[0] !== null && i[1] !== null)
    .sort((a, b) => a[0] - b[0])
  const libres: [string, string][] = []
  let curseur = DEBUT_JOURNEE
  for (const [d, f] of intervalles) {
    if (d > curseur) libres.push([enHeure(curseur), enHeure(Math.min(d, FIN_JOURNEE))])
    curseur = Math.max(curseur, f)
    if (curseur >= FIN_JOURNEE) break
  }
  if (curseur < FIN_JOURNEE) libres.push([enHeure(curseur), enHeure(FIN_JOURNEE)])
  return libres.filter(([d, f]) => d < f)
}
