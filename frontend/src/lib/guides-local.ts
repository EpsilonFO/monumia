import type { GuideId } from './guides';

/**
 * Le « déjà vu » des visites guidées sur CET appareil : seule mémoire du
 * visiteur sans compte, et repli quand l'écriture sur le compte échoue. Tout
 * accès est protégé : un navigateur privé ou un stockage bloqué rend une
 * mémoire vide, jamais une erreur.
 */
const CLE = 'monumia-guides-vus';

function lire(): Record<string, string> {
  try {
    const brut = localStorage.getItem(CLE);
    const valeur: unknown = brut ? JSON.parse(brut) : {};
    return valeur && typeof valeur === 'object' ? (valeur as Record<string, string>) : {};
  } catch {
    return {};
  }
}

export function guideVuLocalement(id: GuideId): boolean {
  return id in lire();
}

export function retenirGuideLocal(id: GuideId): void {
  try {
    localStorage.setItem(CLE, JSON.stringify({ ...lire(), [id]: new Date().toISOString() }));
  } catch {
    // Stockage indisponible : la visite se rejouera, rien de plus.
  }
}

export function oublierGuidesLocaux(): void {
  try {
    localStorage.removeItem(CLE);
  } catch {
    // idem
  }
}
