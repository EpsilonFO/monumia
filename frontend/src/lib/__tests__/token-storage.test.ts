import { describe, it, expect, beforeEach } from 'vitest';

// Environnement vitest = node : on fournit un localStorage minimal AVANT
// d'importer le store (zustand/persist le capture à la création).
const backing = new Map<string, string>();
// defineProperty : sous Node ≥22, `localStorage` est un accesseur global que
// l'affectation directe ne remplace pas silencieusement.
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

// Le store importe session.ts (hint cross-domain) : window/document minimaux.
globalThis.window ??= {} as never;
(globalThis.window as { location?: object }).location ??= {
  hostname: 'localhost',
  protocol: 'http:',
};
globalThis.document ??= { cookie: '' } as never;

const { readLegacyRefreshToken, purgeLegacyTokens } = await import('@/lib/token-refresh');
const { useAuthStore } = await import('@/stores/useAuthStore');

const KEY = 'monumia-auth';

const legacyPayload = {
  state: { user: { id: 'u1' }, token: 'at-legacy', refreshToken: 'rt-legacy', isOnboarded: true },
  version: 0,
};

describe('migration des tokens hérités du localStorage', () => {
  beforeEach(() => localStorage.clear());

  it('lit le refresh token hérité', () => {
    localStorage.setItem(KEY, JSON.stringify(legacyPayload));
    expect(readLegacyRefreshToken()).toBe('rt-legacy');
  });

  it('renvoie null sans entrée héritée', () => {
    expect(readLegacyRefreshToken()).toBeNull();
    localStorage.setItem(KEY, JSON.stringify({ state: { user: null }, version: 0 }));
    expect(readLegacyRefreshToken()).toBeNull();
  });

  it('purge les tokens hérités sans toucher au reste', () => {
    localStorage.setItem(KEY, JSON.stringify(legacyPayload));
    purgeLegacyTokens();
    const stored = JSON.parse(localStorage.getItem(KEY)!);
    expect(stored.state.refreshToken).toBeUndefined();
    expect(stored.state.token).toBeUndefined();
    expect(stored.state.user).toEqual({ id: 'u1' });
  });
});

describe('persistance du store auth', () => {
  it('ne persiste jamais les tokens (partialize les exclut)', () => {
    const partialize = useAuthStore.persist.getOptions().partialize!;
    const persisted = partialize({
      ...useAuthStore.getState(),
      user: { id: 'u1', onboardingComplete: true } as never,
      token: 'at-secret',
      isOnboarded: true,
    });
    expect(JSON.stringify(persisted)).not.toContain('at-secret');
    expect((persisted as { user?: { id?: string } }).user?.id).toBe('u1');
    expect(Object.keys(persisted)).toEqual(['user', 'isOnboarded']);
  });
});
