import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, UserSegment, NotificationPreferences } from '@/types';

interface AuthState {
  user: User | null;
  token: string | null;
  isOnboarded: boolean;

  setAuth: (user: User, token: string) => void;
  setUser: (user: User) => void;
  updateProfile: (updates: Partial<User>) => void;
  completeOnboarding: () => void;
  setSegment: (segment: UserSegment) => void;
  updateNotificationPreferences: (prefs: Partial<NotificationPreferences>) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isOnboarded: false,

      setAuth: (user, token) =>
        set({ user, token, isOnboarded: user.onboardingComplete }),

      setUser: (user) => set({ user, isOnboarded: user.onboardingComplete }),

      updateProfile: (updates) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...updates } : null,
        })),

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

      updateNotificationPreferences: (prefs) =>
        set((state) => ({
          user: state.user
            ? {
                ...state.user,
                notificationPreferences: {
                  ...state.user.notificationPreferences,
                  ...prefs,
                },
              }
            : null,
        })),

      logout: () => set({ user: null, token: null, isOnboarded: false }),
    }),
    {
      name: 'patrialta-auth',
    }
  )
);
