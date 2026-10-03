/**
 * Recharger la page quand un morceau chargé à la demande a disparu du serveur.
 *
 * Les pages hors du chemin critique (wizards, dossier, blog, administration)
 * sont découpées en morceaux aux noms hachés (cf. `router.tsx`). Un déploiement
 * remplace ces fichiers : un onglet resté ouvert sur l'ancienne version réclame
 * au clic suivant un morceau qui n'existe plus, et React Router affichait son
 * écran d'erreur brut. Vite signale ce cas par l'événement `vite:preloadError` ;
 * recharger rapatrie le nouvel `index.html`, qui cite les bons noms.
 *
 * Un seul rechargement par fenêtre de temps : si le morceau manque encore
 * après (déploiement cassé, réseau coupé), recharger en boucle empêcherait
 * jusqu'à la lecture de l'erreur. On laisse alors l'erreur remonter.
 */

const CLE = 'monumia-rechargement-morceau';
/** En deçà, un second échec n'est plus un déploiement qu'on vient de croiser. */
export const FENETRE_MS = 10_000;

/** Vrai si un rechargement pour ce motif a eu lieu il y a moins de `FENETRE_MS`. */
export function rechargementRecent(maintenant: number, stockage: Pick<Storage, 'getItem'>): boolean {
  const dernier = Number(stockage.getItem(CLE));
  return Number.isFinite(dernier) && dernier > 0 && maintenant - dernier < FENETRE_MS;
}

export function rechargerSurMorceauPerdu(): void {
  window.addEventListener('vite:preloadError', (event) => {
    try {
      if (rechargementRecent(Date.now(), sessionStorage)) return;
      sessionStorage.setItem(CLE, String(Date.now()));
    } catch {
      // Stockage bloqué : sans mémoire du dernier essai, pas de rechargement
      // automatique — mieux vaut une erreur lisible qu'une boucle.
      return;
    }
    // Empêche l'erreur de remonter : la page repart sur la nouvelle version.
    event.preventDefault();
    window.location.reload();
  });
}
