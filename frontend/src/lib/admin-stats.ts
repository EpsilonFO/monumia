/**
 * Logique pure de la page « Le catalogue en chiffres » : tri, recherche, et la
 * mise en forme des deux grandeurs qui reviennent dans chaque tableau, un taux
 * et un plafond.
 *
 * Pure et testable en node, comme le reste de `src/lib` : le composant ne
 * décide ni de l'ordre des lignes ni de ce qu'un chiffre absent affiche.
 *
 * Le point à ne pas rater : un chiffrage absent vaut `null`, jamais `0`. Une
 * aide qui n'annonce aucun plafond n'est pas une aide à 0 € — la confondre
 * placerait les dispositifs les plus généreux en bas d'un tri décroissant, et
 * ferait lire « 0 € » sur une fiche qui dit simplement autre chose.
 */

import { formatCurrency, formatPercentage } from '@/lib/format-utils';
import { normaliser } from '@/lib/admin-catalogue';
import type { BlocStats } from '@/types/admin.types';

/** Ce qu'affiche une case dont la source n'annonce rien (« non chiffré »). */
export const NON_CHIFFRE = 'n.c.';

/**
 * La fourchette de taux d'un groupe, telle qu'elle se lit dans un tableau :
 * « 15 à 40 % », ou « 40 % » quand les deux bornes se rejoignent.
 */
export function formaterTaux(bloc: BlocStats): string {
  const { tauxMin, tauxMax } = bloc;
  if (tauxMin === null || tauxMax === null) return NON_CHIFFRE;
  if (tauxMin === tauxMax) return formatPercentage(tauxMax);
  return `${new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 }).format(tauxMin)} à ${formatPercentage(tauxMax)}`;
}

export function formaterMontant(valeur: number | null): string {
  return valeur === null ? NON_CHIFFRE : formatCurrency(valeur);
}

/** « 12 / 29 » : combien d'aides du groupe portent réellement ce chiffre. */
export function formaterCouverture(chiffrees: number, total: number): string {
  return `${chiffrees} / ${total}`;
}

export type SensTri = 'asc' | 'desc';

export interface Tri<T> {
  cle: keyof T;
  sens: SensTri;
}

/**
 * Tri stable d'un tableau de lignes, croissant ou décroissant.
 *
 * Les valeurs absentes (`null`) finissent TOUJOURS en bas, quel que soit le
 * sens : « pas de plafond annoncé » n'est ni le plus grand ni le plus petit
 * des plafonds, et le remonter en tête d'un tri décroissant cacherait les
 * lignes qu'on cherchait justement à voir.
 *
 * Le texte se compare en français (`localeCompare`) : sans lui, « Éure » et
 * « Ardèche » se rangent sur leur code d'accent plutôt que sur leur lettre.
 */
export function trierLignes<T>(lignes: T[], tri: Tri<T>): T[] {
  const facteur = tri.sens === 'asc' ? 1 : -1;
  return [...lignes].sort((a, b) => {
    const gauche = a[tri.cle];
    const droite = b[tri.cle];
    if (gauche === droite) return 0;
    if (gauche === null || gauche === undefined) return 1;
    if (droite === null || droite === undefined) return -1;
    if (typeof gauche === 'string' && typeof droite === 'string') {
      return gauche.localeCompare(droite, 'fr') * facteur;
    }
    return (Number(gauche) - Number(droite)) * facteur;
  });
}

/** Bascule d'en-tête : re-cliquer la même colonne inverse le sens, changer de
 *  colonne repart du sens le plus utile pour elle. */
export function basculerTri<T>(tri: Tri<T>, cle: keyof T, sensParDefaut: SensTri): Tri<T> {
  if (tri.cle !== cle) return { cle, sens: sensParDefaut };
  return { cle, sens: tri.sens === 'asc' ? 'desc' : 'asc' };
}

interface Territoire {
  code: string;
  label: string;
  regionLabel?: string;
  nb: number;
}

/**
 * Recherche sur le nom, le code INSEE et la région de rattachement : on tape
 * « 88 » comme on tape « Vosges », et « Grand Est » sort ses dix départements.
 */
export function filtrerTerritoires<T extends Territoire>(lignes: T[], recherche: string): T[] {
  const q = normaliser(recherche);
  if (!q) return lignes;
  return lignes.filter((ligne) =>
    [ligne.code, ligne.label, ligne.regionLabel ?? ''].some((champ) =>
      normaliser(champ).includes(q),
    ),
  );
}

/**
 * Masque les territoires sans aucune aide propre.
 *
 * Par défaut on les GARDE : un zéro en face d'un département est le premier
 * chiffre de prospection de la page, pas une ligne à ranger. Le masquage est
 * une commodité de lecture, jamais l'état initial.
 */
export function masquerVides<T extends { nb: number }>(lignes: T[], actif: boolean): T[] {
  return actif ? lignes.filter((ligne) => ligne.nb > 0) : lignes;
}

/** « à 14:32:05 » : l'heure du dernier rafraîchissement, pour que la page dise
 *  d'elle-même si elle est encore vivante. */
export function formaterHeure(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
}
