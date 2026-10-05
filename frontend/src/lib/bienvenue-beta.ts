/**
 * Accueil des bêta-testeurs : une modale de bienvenue à la première arrivée
 * dans l'espace, puis un projecteur sur le bouton de retour Ybug.
 *
 * Ce module est PUR (hors l'accès protégé au stockage) : il dit si le compte a
 * déjà été accueilli et où poser la bulle. Le rendu vit dans
 * `components/shared/BienvenueBeta.tsx`.
 *
 * L'accueil suit le même interrupteur que le widget (`idProjetYbug`) : sans
 * bouton de retour, la phase de bêta-test est finie et il n'y a plus rien à
 * présenter.
 */

/**
 * `v1` : changer de version remontre l'accueil à tout le monde, ce qui sert si
 * le message change de fond. Le préfixe n'est PAS celui des caches
 * (`persistance.ts`) : la déconnexion purge ceux-là, et l'accueil ne doit pas
 * revenir à chaque reconnexion.
 */
const PREFIXE = 'monumia:bienvenue-beta:v1:';

/**
 * Repli en mémoire quand le stockage est inaccessible (site data bloquées) :
 * sans lui, l'accueil reviendrait à chaque changement de page de la session.
 */
const accueillisEnMemoire = new Set<string>();

export function dejaAccueilli(userId: string): boolean {
  if (accueillisEnMemoire.has(userId)) return true;
  try {
    return localStorage.getItem(PREFIXE + userId) !== null;
  } catch {
    return false;
  }
}

export function marquerAccueilli(userId: string): void {
  accueillisEnMemoire.add(userId);
  try {
    localStorage.setItem(PREFIXE + userId, new Date().toISOString());
  } catch {
    /* stockage inaccessible : le repli en mémoire tient la session */
  }
}

export interface Cadre {
  top: number;
  left: number;
  width: number;
  height: number;
}

/** Marge entre le bouton et le halo qui l'entoure. */
export const MARGE_HALO = 8;
/** Écart entre le halo et la bulle, et entre la bulle et les bords de l'écran. */
const ECART = 14;
const GOUTTIERE = 16;
export const LARGEUR_BULLE = 320;

/**
 * Où poser la bulle autour du bouton : au-dessus, calée sur son bord droit, et
 * jamais hors de l'écran. Le bouton Ybug vit en bas à droite, mais sa position
 * vient de son script (et de `index.css` sur téléphone) : on la lit plutôt que
 * de la supposer.
 *
 * Rend aussi la position horizontale de la pointe, relative à la bulle, pour
 * qu'elle vise le centre du bouton même quand la bulle a dû se décaler.
 */
export function positionBulle(
  bouton: Cadre,
  ecran: { largeur: number; hauteur: number }
): { left: number; bottom: number; largeur: number; pointe: number } {
  const largeur = Math.min(LARGEUR_BULLE, ecran.largeur - 2 * GOUTTIERE);
  const droite = bouton.left + bouton.width + MARGE_HALO;
  const left = Math.min(
    Math.max(GOUTTIERE, droite - largeur),
    ecran.largeur - GOUTTIERE - largeur
  );
  const bottom = ecran.hauteur - (bouton.top - MARGE_HALO) + ECART;
  const centre = bouton.left + bouton.width / 2;
  const pointe = Math.min(Math.max(20, centre - left), largeur - 20);
  return { left, bottom, largeur, pointe };
}
