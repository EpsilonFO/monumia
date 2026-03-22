export const ROUTES = {
  ONBOARDING: '/onboarding',
  ONBOARDING_PROFIL: '/onboarding/profil',
  ONBOARDING_MONUMENT: '/onboarding/monument',

  DASHBOARD: '/app',

  MONUMENTS: '/app/monuments',
  MONUMENT_DETAIL: (id: string) => `/app/monuments/${id}`,
  MONUMENT_NEW: '/app/monuments/nouveau',

  AIDES: '/app/dossiers',
  AIDE_DETAIL: (id: string) => `/app/aides/${id}`,

  DOSSIERS: '/app/dossiers',
  DOSSIER_DETAIL: (id: string) => `/app/dossiers/${id}`,

  DOCUMENTS: '/app/documents',

  PROFIL: '/app/profil',
} as const;
