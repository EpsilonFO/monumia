export const ROUTES = {
  LANDING: '/',

  ONBOARDING: '/onboarding',
  ONBOARDING_PROFIL: '/onboarding/profil',
  ONBOARDING_MONUMENT: '/onboarding/monument',

  DASHBOARD: '/app',

  MONUMENTS: '/app/monuments',
  MONUMENT_DETAIL: (id: string) => `/app/monuments/${id}`,
  MONUMENT_NEW: '/app/monuments/nouveau',

  AIDES: '/app/monuments',
  AIDE_DETAIL: (aideId: string, monumentId?: string) =>
    monumentId ? `/app/aides/${aideId}?monumentId=${monumentId}` : `/app/aides/${aideId}`,

  DOSSIERS: '/app/dossiers',
  DOSSIER_DETAIL: (id: string) => `/app/dossiers/${id}`,

  DOCUMENTS: '/app/documents',

  PROFIL: '/app/profil',
} as const;
