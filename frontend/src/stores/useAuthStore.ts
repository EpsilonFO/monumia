import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, UserSegment, NotificationPreferences } from '@/types';
import { authService } from '@/services/auth.service';
import { useMonumentStore } from './useMonumentStore';
import { useDossierStore } from './useDossierStore';
import { useDocumentStore } from './useDocumentStore';
import { useAideStore } from './useAideStore';

interface AuthState {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  isOnboarded: boolean;

  setAuth: (user: User, token: string, refreshToken?: string | null) => void;
  setTokens: (token: string, refreshToken: string) => void;
  setUser: (user: User) => void;
  updateProfile: (updates: Partial<User>) => Promise<void>;
  completeOnboarding: () => void;
  setSegment: (segment: UserSegment) => void;
  updateNotificationPreferences: (prefs: Partial<NotificationPreferences>) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      isOnboarded: false,

      setAuth: (user, token, refreshToken = null) =>
        set({ user, token, refreshToken, isOnboarded: user.onboardingComplete }),

      setTokens: (token, refreshToken) =>
        set({ token, refreshToken }),

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

      setSegment: (segment) =>
        set((state) => ({
          user: state.user ? { ...state.user, segment } : null,
        })),

      updateNotificationPreferences: async (prefs) => {
        if (!get().token) return;
        const updated = await authService.updateNotificationPreferences(prefs);
        set({ user: updated });
      },

      logout: () => {
        set({ user: null, token: null, refreshToken: null, isOnboarded: false });
        // Reset all data stores to prevent data leaking between accounts
        useMonumentStore.setState({ monuments: [], activeMonumentId: null });
        useDossierStore.setState({ dossiers: [], loaded: false });
        useDocumentStore.setState({ documents: [], loading: false, error: null });
        useAideStore.setState({ aides: [], diagnosticsByMonument: {}, loading: false, error: null });
      },
    }),
    {
      name: 'patrialta-auth',
    }
  )
);
