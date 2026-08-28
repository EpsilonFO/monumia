/**
 * Jeton d'invitation mis de côté le temps d'un aller-retour Google.
 *
 * Le flux OAuth quitte l'application : un store en mémoire (comme
 * usePendingOAuthStore) ne survivrait pas à la redirection, et l'URL de retour
 * est imposée par la liste blanche Supabase. D'où `sessionStorage`, borné à
 * l'onglet et effacé dès que le jeton a servi.
 *
 * Ce jeton n'est pas un secret de session : il vient déjà en clair dans le lien
 * reçu par email et ne donne accès qu'à un projet, une fois.
 */
const KEY = 'monumia_pending_invitation';

export function setPendingInvitation(token: string): void {
  try {
    sessionStorage.setItem(KEY, token);
  } catch {
    // Navigation privée ou stockage saturé : l'utilisateur retombera sur le
    // parcours email depuis son lien d'invitation.
  }
}

export function takePendingInvitation(): string | null {
  try {
    const token = sessionStorage.getItem(KEY);
    if (token) sessionStorage.removeItem(KEY);
    return token;
  } catch {
    return null;
  }
}

export function clearPendingInvitation(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* rien à faire */
  }
}
