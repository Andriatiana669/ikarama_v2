// src/utils/rendement.ts
// Écart entre deux courbes d'Evolution : (courbe 2 − courbe 1) ÷ courbe 1 × 100, aux dates où les deux existent.

export interface Ecart {
  /** Position de la date dans la liste des dates */
  i: number
  pct: number
  haut: number
  bas: number
}

export function calculerEcarts(courbes: { valeurs: (number | null)[] }[]): Ecart[] {
  if (courbes.length < 2) return []
  const [c1, c2] = courbes
  return c1!.valeurs.flatMap((a, i) => {
    const b = c2!.valeurs[i]
    if (a === null || a === undefined || b === null || b === undefined || !a) return []
    return [{ i, pct: ((b - a) / a) * 100, haut: Math.max(a, b), bas: Math.min(a, b) }]
  })
}

/** Dans la tolérance (bornes comprises) : l'écart n'est pas affiché. 0 % à 0 % : seuls les 0 % sont masqués. */
export const dansTolerance = (pct: number, min: number, max: number) => {
  const arrondi = Math.round(pct * 10) / 10
  return arrondi >= Math.min(min, max) && arrondi <= Math.max(min, max)
}

export const formatPct = (v: number) =>
  `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`
