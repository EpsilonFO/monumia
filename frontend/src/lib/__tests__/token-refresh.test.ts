import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Environnement vitest = node : localStorage, window et document minimaux AVANT
// d'importer le store (cf. token-storage.test.ts).
const backing = new Map<string, string>();
Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: {
    getItem: (k: string) => backing.get(k) ?? null,
    setItem: (k: string, v: string) => void backing.set(k, String(v)),
    removeItem: (k: string) => void backing.delete(k),
    clear: () => backing.clear(),
    key: (i: number) => [...backing.keys()][i] ?? null,
    get length() {
      return backing.size;
    },
  } as Storage,
});
globalThis.window ??= {} as never;
// zustand/persist écrit dans `window.localStorage`, pas dans le global.
(globalThis.window as { localStorage?: Storage }).localStorage = globalThis.localStorage;
(globalThis.window as { location?: object }).location ??= {
  hostname: 'localhost',
  protocol: 'http:',
};
globalThis.document ??= { cookie: '' } as never;

const { tryRefresh, sessionRefusee, ATTENTES_REESSAI_MS } = await import('@/lib/token-refresh');
const { useAuthStore } = await import('@/stores/useAuthStore');

const USER = { id: 'u1', onboardingComplete: true } as never;

function reponse(status: number, corps: unknown = {}): Response {
  return new Response(JSON.stringify(corps), { status });
}

/** Rejoue les réponses dans l'ordre ; une Error est levée comme une coupure réseau. */
function serveur(...reponses: Array<Response | Error>) {
  const fetchMock = vi.fn(async () => {
    const r = reponses.shift();
    if (!r) throw new Error('appel inattendu');
    if (r instanceof Error) throw r;
    return r;
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

/** Laisse filer toutes les attentes de réessai. */
async function resoudre<T>(promesse: Promise<T>): Promise<T> {
  await vi.runAllTimersAsync();
  return promesse;
}

describe('sessionRefusee', () => {
  it('vrai pour un refus du serveur', () => {
    expect(sessionRefusee(400)).toBe(true);
    expect(sessionRefusee(401)).toBe(true);
    expect(sessionRefusee(403)).toBe(true);
  });

  it('faux pour une panne : la session reste valide', () => {
    for (const status of [408, 429, 500, 502, 503, 504]) expect(sessionRefusee(status)).toBe(false);
  });
});

describe('tryRefresh', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    useAuthStore.setState({ user: USER, token: null, isOnboarded: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('pose le nouveau jeton', async () => {
    serveur(reponse(200, { access_token: 'at-neuf' }));
    expect(await resoudre(tryRefresh())).toBe(true);
    expect(useAuthStore.getState().token).toBe('at-neuf');
  });

  it('déconnecte sur un refus du serveur', async () => {
    const fetchMock = serveur(reponse(401));
    expect(await resoudre(tryRefresh())).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('traverse le redémarrage du backend sans déconnecter', async () => {
    const fetchMock = serveur(
      reponse(502),
      new TypeError('Failed to fetch'),
      reponse(200, { access_token: 'at-neuf' }),
    );
    expect(await resoudre(tryRefresh())).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(useAuthStore.getState().token).toBe('at-neuf');
  });

  it('garde la session quand le serveur reste injoignable', async () => {
    const pannes = Array.from({ length: ATTENTES_REESSAI_MS.length + 1 }, () => reponse(503));
    const fetchMock = serveur(...pannes);
    expect(await resoudre(tryRefresh())).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(ATTENTES_REESSAI_MS.length + 1);
    expect(useAuthStore.getState().user).toEqual(USER);
  });

  it("garde le refresh token hérité tant que le serveur n'a pas tranché", async () => {
    localStorage.setItem(
      'monumia-auth',
      JSON.stringify({ state: { user: USER, refreshToken: 'rt-legacy' }, version: 0 }),
    );
    const fetchMock = serveur(reponse(502), reponse(200, { access_token: 'at-neuf' }));
    expect(await resoudre(tryRefresh())).toBe(true);

    const corps = (fetchMock.mock.calls as unknown as Array<[string, RequestInit]>).map(
      ([, init]) => init.body,
    );
    expect(corps).toEqual([
      JSON.stringify({ refresh_token: 'rt-legacy' }),
      JSON.stringify({ refresh_token: 'rt-legacy' }),
    ]);
    expect(localStorage.getItem('monumia-auth')).not.toContain('rt-legacy');
  });
});
