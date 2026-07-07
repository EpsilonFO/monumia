import { authFetch, handleResponse } from '@/lib/auth-fetch';
import { ApiError } from '@/lib/api-error';

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

export type RegisterOauthPayload = Omit<RegisterPayload, 'email' | 'password'>;
export type RegisterCollaboratorOauthPayload = Omit<
  RegisterCollaboratorPayload,
  'email' | 'password'
>;

export interface OauthProfileStatusResponse {
  exists: boolean;
  user?: import('@/types').User;
  prefill?: { email: string; prenom: string; nom: string };
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: import('@/types').User;
}

export const authService = {
  // credentials: 'include' sur les appels d'auth : nécessaire pour recevoir /
  // envoyer le cookie httpOnly `monumia_refresh` posé par le backend.
  async login(payload: LoginPayload): Promise<AuthResponse> {
    const res = await fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    return handleResponse<AuthResponse>(res);
  },

  async register(payload: RegisterPayload): Promise<AuthResponse> {
    const res = await fetch(`${BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    return handleResponse<AuthResponse>(res);
  },

  async registerCollaborator(payload: RegisterCollaboratorPayload): Promise<AuthResponse> {
    const res = await fetch(`${BASE}/auth/register-collaborator`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    return handleResponse<AuthResponse>(res);
  },

  async oauthProfileStatus(accessToken: string): Promise<OauthProfileStatusResponse> {
    const res = await fetch(`${BASE}/auth/oauth/profile-status`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return handleResponse<OauthProfileStatusResponse>(res);
  },

  async registerOauth(
    payload: RegisterOauthPayload,
    accessToken: string,
  ): Promise<{ user: import('@/types').User }> {
    const res = await fetch(`${BASE}/auth/register-oauth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async registerCollaboratorOauth(
    payload: RegisterCollaboratorOauthPayload,
    accessToken: string,
  ): Promise<{ user: import('@/types').User }> {
    const res = await fetch(`${BASE}/auth/register-collaborator-oauth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  /** Échange unique post-callback Google : le refresh token part en cookie httpOnly. */
  async oauthSession(accessToken: string, refreshToken: string): Promise<void> {
    const res = await fetch(`${BASE}/auth/oauth/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      credentials: 'include',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.detail ?? `HTTP ${res.status}`);
    }
  },

  async logout(): Promise<void> {
    await authFetch(`${BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  },

  async refreshSession(): Promise<AuthResponse> {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
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

  async requestPasswordReset(email: string): Promise<void> {
    const res = await fetch(`${BASE}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    await handleResponse(res);
  },
};
