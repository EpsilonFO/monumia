export const ROUTES = {
  LANDING: '/',
  RESET_PASSWORD: '/reset-password',

  ONBOARDING: '/onboarding',
  ONBOARDING_PROFIL: '/onboarding/profil',
  ONBOARDING_MONUMENT: '/onboarding/monument',

  DASHBOARD: '/app',

  // Page Tarifs (publique). Le projet passe par l'URL et non par le state de
  // navigation : l'aller-retour vers Stripe quitte le site et perd tout state.
  TARIFS: (monumentId?: string) => (monumentId ? `/tarifs?projet=${monumentId}` : '/tarifs'),

  // Onglet unifié « Projet » (projet = monument)
  PROJETS: '/app/projets',
  PROJET_NEW: '/app/projets/nouveau',
  PROJET_DETAIL: (id: string) => `/app/projets/${id}`,
  PROJET_AIDE: (projetId: string, aideId: string) => `/app/projets/${projetId}/aides/${aideId}`,
  PROJET_DOSSIER: (projetId: string, dossierId: string) => `/app/projets/${projetId}/dossiers/${dossierId}`,

  DOCUMENTS: '/app/documents',
  MODELES: '/app/modeles',
  PROFIL: '/app/profil',

  INVITATION: (token: string) => `/invitation/${token}`,

  // Alias de compatibilité — résolvent sur l'onglet Projet unifié pour que tous les
  // appelants compilent pendant la migration. Les liens profonds corrects sont posés
  // par les pages Projet (AideCard/DossierCard → PROJET_AIDE).
  MONUMENTS: '/app/projets',
  MONUMENT_DETAIL: (id: string) => `/app/projets/${id}`,
  MONUMENT_NEW: '/app/projets/nouveau',
  AIDES: '/app/projets',
  DOSSIERS: '/app/projets',
  AIDE_DETAIL: (aideId: string, monumentId?: string) =>
    monumentId ? `/app/projets/${monumentId}/aides/${aideId}` : '/app/projets',
  DOSSIER_DETAIL: (id: string) => `/app/projets?dossier=${id}`,
} as const;
