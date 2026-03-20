const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

function authHeaders(token: string) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

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

  async logout(token: string): Promise<void> {
    await fetch(`${BASE}/auth/logout`, {
      method: 'POST',
      headers: authHeaders(token),
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

  async getMe(token: string): Promise<import('@/types').User> {
    const res = await fetch(`${BASE}/auth/me`, {
      headers: authHeaders(token),
    });
    return handleResponse(res);
  },

  async updateProfile(
    token: string,
    updates: { prenom?: string; nom?: string; email?: string; telephone?: string },
  ): Promise<import('@/types').User> {
    const res = await fetch(`${BASE}/auth/me`, {
      method: 'PATCH',
      headers: authHeaders(token),
      body: JSON.stringify(updates),
    });
    return handleResponse(res);
  },

  async updateNotificationPreferences(
    token: string,
    prefs: Partial<import('@/types').NotificationPreferences>,
  ): Promise<import('@/types').User> {
    const res = await fetch(`${BASE}/auth/me/notifications`, {
      method: 'PATCH',
      headers: authHeaders(token),
      body: JSON.stringify(prefs),
    });
    return handleResponse(res);
  },
};
