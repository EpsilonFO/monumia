import { create } from 'zustand';

// In-memory only, comme usePendingRegistrationStore : jamais persisté en
// localStorage / sessionStorage. Contient les jetons Supabase issus du flux
// Google le temps que l'utilisateur termine l'onboarding (segment + profil).
// Un rechargement de page vide le store → retour au /login, comme le flux email.
interface PendingOAuthSession {
  accessToken: string;
  refreshToken: string;
  email: string;
  prenom: string;
  nom: string;
}

interface PendingOAuthState {
  accessToken: string | null;
  refreshToken: string | null;
  email: string | null;
  prenom: string | null;
  nom: string | null;
  setSession: (session: PendingOAuthSession) => void;
  clear: () => void;
  has: () => boolean;
}

export const usePendingOAuthStore = create<PendingOAuthState>()((set, get) => ({
  accessToken: null,
  refreshToken: null,
  email: null,
  prenom: null,
  nom: null,
  setSession: ({ accessToken, refreshToken, email, prenom, nom }) =>
    set({ accessToken, refreshToken, email, prenom, nom }),
  clear: () =>
    set({ accessToken: null, refreshToken: null, email: null, prenom: null, nom: null }),
  has: () => Boolean(get().accessToken),
}));
