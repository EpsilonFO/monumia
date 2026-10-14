import { authFetch, handleResponse } from '@/lib/auth-fetch';
import { ApiError } from '@/lib/api-error';
import { suivre } from '@/lib/posthog';

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
  telephone?: string;
  /** Inscription venue du parcours découverte : le lien de confirmation
   *  ramènera sur l'écran de reprise du brouillon. */
  reprise?: boolean;
}

export interface RegisterCollaboratorPayload {
  email: string;
  password: string;
  prenom: string;
  nom: string;
  metier: string;
  telephone?: string;
  /** Jeton de l'invitation d'où vient l'inscription : le lien de confirmation
   *  ramènera sur elle. */
  invitation?: string;
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

/**
 * Réponse d'une INSCRIPTION, où le jeton peut manquer.
 *
 * `access_token` nul veut dire : compte créé, session en attente de la
 * confirmation de l'adresse email. Type distinct d'`AuthResponse` à dessein —
 * la connexion, elle, ne rend jamais de jeton nul (elle répond 403), et
 * relâcher son type aurait obligé tous ses appelants à traiter un cas
 * impossible. Ici au contraire, le compilateur exige que le cas soit vu.
 */
export interface RegisterResponse extends Omit<AuthResponse, 'access_token'> {
  access_token: string | null;
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

  async register(payload: RegisterPayload): Promise<RegisterResponse> {
    const res = await fetch(`${BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    const reponse = await handleResponse<RegisterResponse>(res);
    suivre({ nom: 'inscription', proprietes: { canal: 'email', viaInvitation: false } });
    return reponse;
  },

  async registerCollaborator(payload: RegisterCollaboratorPayload): Promise<RegisterResponse> {
    const res = await fetch(`${BASE}/auth/register-collaborator`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    const reponse = await handleResponse<RegisterResponse>(res);
    suivre({ nom: 'inscription', proprietes: { canal: 'email', viaInvitation: true } });
    return reponse;
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
    const reponse = await handleResponse<{ user: import('@/types').User }>(res);
    suivre({ nom: 'inscription', proprietes: { canal: 'google', viaInvitation: false } });
    return reponse;
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
    const reponse = await handleResponse<{ user: import('@/types').User }>(res);
    suivre({ nom: 'inscription', proprietes: { canal: 'google', viaInvitation: true } });
    return reponse;
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

  /** Une visite guidée vue ou passée : elle ne se rejouera plus. */
  async marquerGuideVu(id: import('@/lib/guides').GuideId): Promise<import('@/types').User> {
    const res = await authFetch(`${BASE}/auth/me/guides`, {
      method: 'PATCH',
      body: JSON.stringify({ id }),
    });
    return handleResponse(res);
  },

  /** « Revoir les visites guidées » : toutes se rejouent. */
  async reinitialiserGuides(): Promise<import('@/types').User> {
    const res = await authFetch(`${BASE}/auth/me/guides`, { method: 'DELETE' });
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

  /** Renvoie l'email de confirmation d'inscription. Réponse toujours 200 :
   *  l'existence du compte ne se déduit pas d'ici. */
  async resendConfirmation(
    email: string,
    intention?: { reprise?: boolean; invitation?: string },
  ): Promise<void> {
    const res = await fetch(`${BASE}/auth/resend-confirmation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, ...intention }),
    });
    await handleResponse(res);
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
