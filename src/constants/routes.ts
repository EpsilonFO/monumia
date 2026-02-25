export const ROUTES = {
  ONBOARDING: '/onboarding',
  ONBOARDING_PROFIL: '/onboarding/profil',
  ONBOARDING_MONUMENT: '/onboarding/monument',

  DASHBOARD: '/',

  MONUMENTS: '/monuments',
  MONUMENT_DETAIL: (id: string) => `/monuments/${id}`,
  MONUMENT_NEW: '/monuments/nouveau',

  AIDES: '/aides',
  AIDE_DETAIL: (id: string) => `/aides/${id}`,

  DOSSIERS: '/dossiers',
  DOSSIER_DETAIL: (id: string) => `/dossiers/${id}`,

  DOCUMENTS: '/documents',

  PROFIL: '/profil',
} as const;
