export const ROUTES = {
  LANDING: '/',
  RESET_PASSWORD: '/reset-password',

  DASHBOARD: '/app',

  /**
   * Aiguillage « Mon compte », où arrivent les boutons de la landing quand un
   * visiteur est déjà connecté. La landing ne sait qu'une chose — une session
   * existe (cookie de présence) — donc c'est ici, côté application, qu'on
   * choisit entre le tableau de bord, la fiche du monument et le wizard
   * d'enregistrement (cf. `lib/destination-compte.ts`).
   */
  MON_COMPTE: '/mon-compte',

  // Page Tarifs (publique). Le monument passe par l'URL et non par le state de
  // navigation : l'aller-retour vers Stripe quitte le site et perd tout state.
  // Le nom du paramètre (`projet`) est figé : d'anciens liens de retour Stripe
  // circulent encore. Sa valeur est et reste un id de MONUMENT, mais il ne sert
  // plus qu'à revenir au bon endroit : les offres sont des abonnements de
  // compte, elles ne débloquent pas un bien en particulier.
  TARIFS: (monumentId?: string) => (monumentId ? `/tarifs?projet=${monumentId}` : '/tarifs'),

  // ── Monuments : le bien, sa fiche sanitaire, ses documents, son équipe ──
  MONUMENTS: '/app/monuments',
  MONUMENT_NEW: '/app/monuments/nouveau',
  /** Onglets : ?tab=sanitaire|projets|documents|equipe */
  MONUMENT_DETAIL: (id: string) => `/app/monuments/${id}`,

  /**
   * Wizard projet du parcours DÉCOUVERTE (publique, sans monument en base) :
   * le visiteur y cadre son chantier et répond au questionnaire avant d'avoir
   * un compte. Sous `/monuments/nouveau` parce qu'elle en est la suite
   * immédiate, et parce que le brouillon du monument est son seul prérequis.
   */
  PROJET_NEW_INVITE: '/app/monuments/nouveau/projet',

  /**
   * Rejeu du brouillon découverte, juste après l'inscription : le monument et
   * le projet y sont créés pour de vrai. Écran unique où convergent les trois
   * entrées (inscription email, retour Google, « J'ai déjà un compte »), pour
   * que le wizard n'ait pas à survivre au changement d'état d'auth.
   */
  REPRISE: '/app/reprise',

  // ── Projets de travaux : un chantier, son questionnaire, ses aides ──
  PROJET_NEW: (monumentId: string) => `/app/monuments/${monumentId}/projets/nouveau`,
  /** Onglets : ?tab=aides|dossiers */
  PROJET_DETAIL: (projetId: string) => `/app/projets/${projetId}`,
  PROJET_AIDE: (projetId: string, aideId: string) => `/app/projets/${projetId}/aides/${aideId}`,
  PROJET_DOSSIER: (projetId: string, dossierId: string) => `/app/projets/${projetId}/dossiers/${dossierId}`,

  DOCUMENTS: '/app/documents',
  PROFIL: '/app/profil',

  /**
   * Administration du catalogue, réservée au rôle `admin` de la table
   * `comptes_roles` (et au socle `ADMIN_USER_IDS`) côté serveur. Hors de
   * `/app` et absente de la navigation : c'est une page
   * d'exploitation, pas une fonctionnalité du produit. On y arrive par le lien
   * discret de la page Profil.
   */
  ADMIN: '/admin',

  /**
   * Le catalogue en chiffres (aides par territoire, par nature, chiffrage).
   * Sous `/admin` et derrière le même garde : c'est la même page
   * d'exploitation, vue par les nombres plutôt que ligne à ligne.
   */
  ADMIN_STATS: '/admin/statistiques',

  INVITATION: (token: string) => `/invitation/${token}`,
} as const;
