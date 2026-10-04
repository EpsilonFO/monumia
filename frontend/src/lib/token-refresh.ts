import { useAuthStore } from '@/stores/useAuthStore';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

let refreshPromise: Promise<boolean> | null = null;

const STORAGE_KEY = 'monumia-auth';

/** Refresh token de l'ancien format localStorage (avant cookie httpOnly). */
export function readLegacyRefreshToken(): string | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return typeof parsed?.state?.refreshToken === 'string' ? parsed.state.refreshToken : null;
  } catch {
    return null;
  }
}

/** Retire les champs sensibles hérités sans toucher au reste de l'entrée. */
export function purgeLegacyTokens(): void {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed?.state && ('refreshToken' in parsed.state || 'token' in parsed.state)) {
      delete parsed.state.refreshToken;
      delete parsed.state.token;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed));
    }
  } catch {
    /* entrée illisible : on la laisse, partialize l'assainira au prochain write */
  }
}

/**
 * Attentes entre deux essais quand le serveur ne répond pas : de quoi couvrir
 * le redémarrage d'un backend pendant un déploiement (2 à 4 s de 502).
 */
export const ATTENTES_REESSAI_MS = [500, 1000, 2000, 4000];

/**
 * Vrai si le serveur a JUGÉ la session : elle est perdue, on déconnecte. Un
 * 5xx (backend qui redémarre, Supabase en panne), un 408 ou un 429 ne disent
 * rien du cookie de refresh, qui reste valide. Les confondre déconnectait
 * tous les comptes actifs à chaque déploiement.
 */
export function sessionRefusee(status: number): boolean {
  return status >= 400 && status < 500 && status !== 408 && status !== 429;
}

type Issue = 'ok' | 'refusee' | 'panne';

async function essayerRefresh(): Promise<Issue> {
  const { setTokens, setUser } = useAuthStore.getState();

  // Migration one-shot : un refresh token de l'ancien format est envoyé une
  // dernière fois dans le body ; ensuite le cookie httpOnly prend le relais.
  // Relu à chaque essai, et purgé seulement quand le serveur a tranché : le
  // perdre sur une panne transformerait l'essai suivant en refus.
  const legacy = readLegacyRefreshToken();

  let res: Response;
  try {
    res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      ...(legacy
        ? {
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: legacy }),
          }
        : {}),
    });
  } catch {
    return 'panne';
  }

  if (!res.ok && !sessionRefusee(res.status)) return 'panne';
  if (legacy) purgeLegacyTokens();
  if (!res.ok) return 'refusee';

  try {
    const data = await res.json();
    if (!data.access_token) return 'refusee';
    setTokens(data.access_token);
    if (data.user) setUser(data.user);
    return 'ok';
  } catch {
    return 'panne';
  }
}

async function doRefresh(): Promise<boolean> {
  for (let essai = 0; ; essai++) {
    const issue = await essayerRefresh();
    if (issue === 'ok') return true;
    if (issue === 'refusee') {
      useAuthStore.getState().logout();
      return false;
    }
    if (essai >= ATTENTES_REESSAI_MS.length) {
      // Serveur toujours injoignable : la session n'est pas perdue pour
      // autant. On garde le profil et le cookie, le prochain appel réessaiera.
      return false;
    }
    await new Promise((r) => setTimeout(r, ATTENTES_REESSAI_MS[essai]));
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
