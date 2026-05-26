import { useAuthStore } from '@/stores/useAuthStore';
import { tryRefresh } from '@/lib/token-refresh';

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
