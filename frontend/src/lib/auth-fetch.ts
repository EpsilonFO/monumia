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
 * refresh request. The promise is only cleared *after* all `.then()` microtasks
 * have settled, preventing double-refresh races.
 */
function tryRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

/**
 * Wrapper around fetch that:
 * 1. Injects the Authorization header automatically
 * 2. On 401, attempts a single token refresh then retries
 */
export async function authFetch(
  input: string | URL,
  init?: RequestInit
): Promise<Response> {
  const token = useAuthStore.getState().token;
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('Content-Type') && init?.body) {
    headers.set('Content-Type', 'application/json');
  }

  let res = await fetch(input, { ...init, headers });

  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (!refreshed) {
      return res;
    }

    // Retry with the new token
    const newToken = useAuthStore.getState().token;
    headers.set('Authorization', `Bearer ${newToken}`);
    res = await fetch(input, { ...init, headers });
  }

  return res;
}

export async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}
