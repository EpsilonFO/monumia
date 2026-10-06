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
import { useBrouillonInviteStore } from './useBrouillonInviteStore';
import { setSessionCookie, clearSessionCookie } from '@/lib/session';
import type { GuideId } from '@/lib/guides';
import { oublierGuidesLocaux, retenirGuideLocal } from '@/lib/guides-local';
import { fermerCaches, ouvrirCaches } from './persistance';

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
  /** Visite guidée vue ou passée : sur le compte, et sur l'appareil en repli. */
  marquerGuideVu: (id: GuideId) => void;
  /** « Revoir les visites guidées » du profil. */
  reinitialiserGuides: () => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isOnboarded: false,

      setAuth: (user, token) => {
        // Avant de poser le compte : s'il diffère de celui dont les caches
        // sont ouverts, leurs états mémoire sont vidés d'abord.
        ouvrirCaches(user.id);
        set({ user, token, isOnboarded: user.onboardingComplete });
        // Let the landing page (separate origin) know a session is active.
        setSessionCookie();
      },

      setTokens: (token) => set({ token }),

      setUser: (user) => {
        // Le profil rendu par le serveur fait foi : s'il ne désigne pas le
        // compte du profil persisté (session changée dans un autre onglet),
        // les caches du précédent se ferment ici.
        ouvrirCaches(user.id);
        set({ user, isOnboarded: user.onboardingComplete });
      },

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

      marquerGuideVu: (id) => {
        // Sur l'appareil d'abord : le visiteur sans compte n'a que lui, et une
        // écriture serveur qui échoue (migration pas encore appliquée) ne doit
        // pas rejouer la visite à chaque arrivée.
        retenirGuideLocal(id);
        const { user, token } = get();
        if (!user || !token) return;
        set({ user: { ...user, guidesVus: { ...user.guidesVus, [id]: new Date().toISOString() } } });
        authService
          .marquerGuideVu(id)
          .then((updated) => set({ user: updated }))
          .catch((err) => console.error('Visite guidée non enregistrée sur le compte (ignoré):', err));
      },

      reinitialiserGuides: async () => {
        oublierGuidesLocaux();
        if (!get().token) return;
        const updated = await authService.reinitialiserGuides();
        set({ user: updated });
      },

      logout: () => {
        // Les caches locaux d'abord : une fois fermés, les remises à zéro
        // ci-dessous ne réécrivent plus rien, et leurs entrées quittent le poste.
        fermerCaches();
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
        // Le brouillon découverte n'est PAS une donnée de compte : c'est une
        // saisie faite avant d'en avoir un, et la vider ferait perdre son
        // travail à qui se déconnecte pour reprendre sur le bon compte. Sauf
        // s'il porte déjà un monumentId — le rejeu a commencé, il est lié au
        // compte qui part.
        if (useBrouillonInviteStore.getState().monumentId) {
          useBrouillonInviteStore.getState().vider();
        }
      },
    }),
    {
      name: 'monumia-auth',
      // Les tokens ne touchent JAMAIS le localStorage : seul le profil est
      // persisté (UX). La session est restaurée au boot via le cookie httpOnly.
      partialize: (state) => ({ user: state.user, isOnboarded: state.isOnboarded }),
      // Keep the cross-domain session hint in sync after a page reload.
      // Ouvre aussi les caches des stores de données, au nom du compte relu :
      // c'est ce qui permet d'afficher le dernier état connu avant la première
      // réponse du serveur (cf. stores/persistance).
      onRehydrateStorage: () => (state) => {
        if (state?.user) {
          setSessionCookie();
          ouvrirCaches(state.user.id);
        } else clearSessionCookie();
      },
    }
  )
);
