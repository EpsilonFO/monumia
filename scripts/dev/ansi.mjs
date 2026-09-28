// Outils texte de l'écran du lanceur : lecture des journaux colorés que
// crachent les serveurs, et largeur des caractères à l'écran.
//
// Une ligne de journal est gardée sous deux formes à la fois : le texte nu,
// caractère par caractère (c'est lui qu'on sélectionne et qu'on copie), et la
// liste des changements de style SGR (couleurs, gras) pour le réafficher tel
// que le serveur l'a écrit. Tout le reste des séquences d'échappement
// (effacement d'écran, déplacements du curseur, liens OSC) est jeté : il
// casserait la mise en page.

const CSI = /\x1b\[([0-9;:?<>=]*)[ -/]*([@-~])/y
const OSC = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?/y

function appliquerSgr(courant, params) {
  if (params === '' || params === '0') return ''
  if (params.startsWith('0;')) return `\x1b[${params.slice(2)}m`
  // Garde-fou : un programme qui empile les styles sans jamais remettre à
  // zéro ferait grossir chaque ligne indéfiniment.
  if (courant.length > 120) courant = ''
  return courant + `\x1b[${params}m`
}

/**
 * Découpe une ligne brute (sans \n) en `{ texte, larg, runs }` :
 * - `texte` : un élément par point de code ;
 * - `larg`  : largeur à l'écran de chacun (0, 1 ou 2) ;
 * - `runs`  : changements de style `[{ debut, sgr }]`, `sgr` étant l'état
 *   complet à appliquer à partir de l'indice `debut`.
 * `etat.sgr` porte le style ouvert d'une ligne à la suivante.
 */
export function analyserLigne(brut, etat = { sgr: '' }) {
  // Un \r isolé réécrit la ligne (barres de progression) : seul le dernier
  // passage compte.
  const cr = brut.lastIndexOf('\r')
  if (cr >= 0) brut = brut.slice(cr + 1)

  const texte = []
  const larg = []
  const runs = []
  let sgr = etat.sgr
  let col = 0
  if (sgr) runs.push({ debut: 0, sgr })

  const changerStyle = (nouveau) => {
    if (nouveau === sgr) return
    sgr = nouveau
    const dernier = runs[runs.length - 1]
    if (dernier && dernier.debut === texte.length) dernier.sgr = sgr
    else runs.push({ debut: texte.length, sgr })
  }

  let i = 0
  while (i < brut.length) {
    const code = brut.charCodeAt(i)
    if (code === 0x1b) {
      CSI.lastIndex = i
      const csi = CSI.exec(brut)
      if (csi) {
        if (csi[2] === 'm' && !/[?<>=]/.test(csi[1])) changerStyle(appliquerSgr(sgr, csi[1]))
        i = CSI.lastIndex
        continue
      }
      OSC.lastIndex = i
      if (OSC.exec(brut)) {
        i = OSC.lastIndex
        continue
      }
      i += 2
      continue
    }
    if (code === 0x09) {
      const n = 8 - (col % 8)
      for (let k = 0; k < n; k++) {
        texte.push(' ')
        larg.push(1)
      }
      col += n
      i++
      continue
    }
    if (code < 0x20 || code === 0x7f) {
      i++
      continue
    }
    const cp = brut.codePointAt(i)
    const car = String.fromCodePoint(cp)
    const w = largeurCar(cp)
    texte.push(car)
    larg.push(w)
    col += w
    i += car.length
  }

  etat.sgr = sgr
  return { texte, larg, runs }
}

// Symboles du plan de base qu'un terminal affiche en double largeur (❌, ✅, ⚡…).
const EMOJI_BMP = new Set([
  0x231a, 0x231b, 0x23e9, 0x23ea, 0x23eb, 0x23ec, 0x23f0, 0x23f3, 0x25fd, 0x25fe, 0x2614, 0x2615,
  0x267f, 0x2693, 0x26a1, 0x26aa, 0x26ab, 0x26bd, 0x26be, 0x26c4, 0x26c5, 0x26ce, 0x26d4, 0x26ea,
  0x26f2, 0x26f3, 0x26f5, 0x26fa, 0x26fd, 0x2705, 0x270a, 0x270b, 0x2728, 0x274c, 0x274e, 0x2753,
  0x2754, 0x2755, 0x2757, 0x2795, 0x2796, 0x2797, 0x27b0, 0x27bf, 0x2b1b, 0x2b1c, 0x2b50, 0x2b55,
])

export function largeurCar(cp) {
  if (
    (cp >= 0x300 && cp <= 0x36f) ||
    (cp >= 0x200b && cp <= 0x200f) ||
    (cp >= 0xfe00 && cp <= 0xfe0f) ||
    cp === 0x20e3
  )
    return 0
  if (EMOJI_BMP.has(cp) || (cp >= 0x2648 && cp <= 0x2653)) return 2
  if (
    cp >= 0x1100 &&
    (cp <= 0x115f ||
      (cp >= 0x2e80 && cp <= 0xa4cf && cp !== 0x303f) ||
      (cp >= 0xac00 && cp <= 0xd7a3) ||
      (cp >= 0xf900 && cp <= 0xfaff) ||
      (cp >= 0xfe30 && cp <= 0xfe4f) ||
      (cp >= 0xff00 && cp <= 0xff60) ||
      (cp >= 0xffe0 && cp <= 0xffe6) ||
      (cp >= 0x1f300 && cp <= 0x1f64f) ||
      (cp >= 0x1f680 && cp <= 0x1f6ff) ||
      (cp >= 0x1f900 && cp <= 0x1f9ff) ||
      (cp >= 0x20000 && cp <= 0x3fffd))
  )
    return 2
  return 1
}

/** Largeur à l'écran d'un texte SANS séquence d'échappement. */
export function largeurTexte(s) {
  let w = 0
  for (const c of s) w += largeurCar(c.codePointAt(0))
  return w
}

/**
 * Coupe ou complète un texte nu à exactement `largeur` colonnes. Un texte
 * coupé finit par « … ».
 */
export function ajuster(s, largeur) {
  if (largeur <= 0) return ''
  if (largeurTexte(s) <= largeur) return s + ' '.repeat(largeur - largeurTexte(s))
  let out = ''
  let w = 0
  for (const c of s) {
    const cw = largeurCar(c.codePointAt(0))
    if (w + cw > largeur - 1) break
    out += c
    w += cw
  }
  return out + '…' + ' '.repeat(largeur - 1 - w)
}

export const style = {
  gras: '\x1b[1m',
  pale: '\x1b[2m',
  inverse: '\x1b[7m',
  rouge: '\x1b[31m',
  vert: '\x1b[32m',
  jaune: '\x1b[33m',
  bleu: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  gris: '\x1b[90m',
  raz: '\x1b[0m',
}
