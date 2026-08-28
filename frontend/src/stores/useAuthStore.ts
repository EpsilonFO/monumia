import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, NotificationPreferences } from '@/types';
import { authService } from '@/services/auth.service';
import { useMonumentStore } from './useMonumentStore';
import { useProjetStore } from './useProjetStore';
import { useDossierStore } from './useDossierStore';
import { useDocumentStore } from './useDocumentStore';
import { useAideStore } from './useAideStore';
import { useSuiviStore } from './useSuiviStore';
import { useBillingStore } from './useBillingStore';
import { setSessionCookie, clearSessionCookie } from '@/lib/session';

interface AuthState {
  user: User | null;
  token: string | null;
  isOnboarded: boolean;

  setAuth: (user: User, token: string) => void;
  setTokens: (token: string) => void;
  setUser: (user: User) => void;
  updateProfile: (updates: Partial<User>) => Promise<void>;
  completeOnboarding: () => void;
  updateNotificationPreferences: (prefs: Partial<NotificationPreferences>) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isOnboarded: false,

      setAuth: (user, token) => {
        set({ user, token, isOnboarded: user.onboardingComplete });
        // Let the landing page (separate origin) know a session is active.
        setSessionCookie();
      },

      setTokens: (token) => set({ token }),

      setUser: (user) => set({ user, isOnboarded: user.onboardingComplete }),

      updateProfile: async (updates) => {
        if (!get().token) return;
        const updated = await authService.updateProfile({
          prenom: updates.prenom,
          nom: updates.nom,
          email: updates.email,
          telephone: updates.telephone,
        });
        set({ user: updated });
      },

      completeOnboarding: () =>
        set((state) => ({
          isOnboarded: true,
          user: state.user
            ? { ...state.user, onboardingComplete: true }
            : null,
        })),

      updateNotificationPreferences: async (prefs) => {
        if (!get().token) return;
        const updated = await authService.updateNotificationPreferences(prefs);
        set({ user: updated });
      },

      logout: () => {
        set({ user: null, token: null, isOnboarded: false });
        clearSessionCookie();
        // Reset all data stores to prevent data leaking between accounts
        useMonumentStore.setState({ monuments: [], activeMonumentId: null });
        useProjetStore.setState({ projets: [], loaded: false });
        useDossierStore.setState({ dossiers: [], loaded: false });
        useDocumentStore.setState({ documents: [], loading: false, error: null });
        useAideStore.setState({ diagnosticsByProjet: {}, digestsByProjet: {} });
        useSuiviStore.setState({ suivis: [], loadedProjets: {} });
        // Sinon les monuments débloqués du compte précédent resteraient ouverts
        // pour le suivant, le temps que /billing/access réponde.
        useBillingStore.getState().reset();
      },
    }),
    {
      name: 'monumia-auth',
      // Les tokens ne touchent JAMAIS le localStorage : seul le profil est
      // persisté (UX). La session est restaurée au boot via le cookie httpOnly.
      partialize: (state) => ({ user: state.user, isOnboarded: state.isOnboarded }),
      // Keep the cross-domain session hint in sync after a page reload.
      onRehydrateStorage: () => (state) => {
        if (state?.user) setSessionCookie();
        else clearSessionCookie();
      },
    }
  )
);
