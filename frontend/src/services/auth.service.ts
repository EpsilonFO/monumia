import { authFetch, handleResponse } from '@/lib/auth-fetch';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  prenom: string;
  nom: string;
  segment: 'commune' | 'prive' | 'btp';
  telephone?: string;
  commune_code_insee?: string;
  commune_fonction?: string;
  prive_type_proprietaire?: string;
  prive_regime_fiscal?: string;
  btp?: object;
}

export interface RegisterCollaboratorPayload {
  email: string;
  password: string;
  prenom: string;
  nom: string;
  metier: string;
  telephone?: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string | null;
  token_type: string;
  user: import('@/types').User;
}

export const authService = {
  async login(payload: LoginPayload): Promise<AuthResponse> {
    const res = await fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<AuthResponse>(res);
  },

  async register(payload: RegisterPayload): Promise<AuthResponse> {
    const res = await fetch(`${BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<AuthResponse>(res);
  },

  async registerCollaborator(payload: RegisterCollaboratorPayload): Promise<AuthResponse> {
    const res = await fetch(`${BASE}/auth/register-collaborator`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<AuthResponse>(res);
  },

  async logout(): Promise<void> {
    await authFetch(`${BASE}/auth/logout`, {
      method: 'POST',
    });
  },

  async refreshSession(refreshToken: string): Promise<AuthResponse> {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    return handleResponse<AuthResponse>(res);
  },

  async getMe(): Promise<import('@/types').User> {
    const res = await authFetch(`${BASE}/auth/me`);
    return handleResponse(res);
  },

  async updateProfile(
    updates: { prenom?: string; nom?: string; email?: string; telephone?: string },
  ): Promise<import('@/types').User> {
    const res = await authFetch(`${BASE}/auth/me`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
    return handleResponse(res);
  },

  async updateNotificationPreferences(
    prefs: Partial<import('@/types').NotificationPreferences>,
  ): Promise<import('@/types').User> {
    const res = await authFetch(`${BASE}/auth/me/notifications`, {
      method: 'PATCH',
      body: JSON.stringify(prefs),
    });
    return handleResponse(res);
  },
};
