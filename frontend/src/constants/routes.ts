export const ROUTES = {
  LANDING: '/',
  RESET_PASSWORD: '/reset-password',

  DASHBOARD: '/app',

  // Page Tarifs (publique). Le monument passe par l'URL et non par le state de
  // navigation : l'aller-retour vers Stripe quitte le site et perd tout state.
  // Le nom du paramètre (`projet`) est figé : d'anciens liens de retour Stripe
  // circulent encore. Sa valeur est et reste un id de MONUMENT — c'est lui
  // qu'on débloque.
  TARIFS: (monumentId?: string) => (monumentId ? `/tarifs?projet=${monumentId}` : '/tarifs'),

  // ── Monuments : le bien, sa fiche sanitaire, ses documents, son équipe ──
  MONUMENTS: '/app/monuments',
  MONUMENT_NEW: '/app/monuments/nouveau',
  /** Onglets : ?tab=sanitaire|projets|documents|equipe */
  MONUMENT_DETAIL: (id: string) => `/app/monuments/${id}`,

  // ── Projets de travaux : un chantier, son questionnaire, ses aides ──
  PROJET_NEW: (monumentId: string) => `/app/monuments/${monumentId}/projets/nouveau`,
  /** Onglets : ?tab=aides|dossiers */
  PROJET_DETAIL: (projetId: string) => `/app/projets/${projetId}`,
  PROJET_AIDE: (projetId: string, aideId: string) => `/app/projets/${projetId}/aides/${aideId}`,
  PROJET_DOSSIER: (projetId: string, dossierId: string) => `/app/projets/${projetId}/dossiers/${dossierId}`,

  DOCUMENTS: '/app/documents',
  PROFIL: '/app/profil',

  INVITATION: (token: string) => `/invitation/${token}`,
} as const;
