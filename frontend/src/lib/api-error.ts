/** Erreur HTTP transportant le code de statut, pour permettre aux appelants
 *  de distinguer une perte d'accès définitive d'une panne transitoire. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** Vrai si l'erreur traduit une perte d'accès définitive (projet supprimé par
 *  le chef, membre retiré, ou départ volontaire) — par opposition à une erreur
 *  transitoire (réseau, 5xx) où l'on conserve l'état local. */
export function isAccessLostError(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 403 || err.status === 404);
}
