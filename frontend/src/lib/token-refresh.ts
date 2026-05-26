import { useAuthStore } from '@/stores/useAuthStore';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

let refreshPromise: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  const { refreshToken, setTokens, logout } = useAuthStore.getState();
  if (!refreshToken) {
    logout();
    return false;
  }

  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      logout();
      return false;
    }

    const data = await res.json();
    if (!data.access_token || !data.refresh_token) {
      logout();
      return false;
    }
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    logout();
    return false;
  }
}

/**
 * Deduplicated refresh: all concurrent callers share a single in-flight
 * refresh request. The promise is only cleared *after* the request settles,
 * preventing double-refresh races that would invalidate the refresh_token.
 */
export function tryRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

/** True if the JWT is missing, malformed, or expires within `slackSeconds`. */
export function isJwtExpired(token: string | null, slackSeconds = 30): boolean {
  if (!token) return true;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    if (typeof payload.exp !== 'number') return true;
    return payload.exp * 1000 < Date.now() + slackSeconds * 1000;
  } catch {
    return true;
  }
}

/**
 * Ensure the stored access_token is fresh, refreshing via the backend if
 * needed. Returns false if no valid session can be established.
 */
export async function ensureFreshAccessToken(): Promise<boolean> {
  const token = useAuthStore.getState().token;
  if (token && !isJwtExpired(token)) return true;
  return tryRefresh();
}
