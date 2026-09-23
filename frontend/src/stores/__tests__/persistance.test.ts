import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Monument, Projet } from '@/types';

// Environnement vitest = node : un localStorage minimal, posé AVANT d'importer
// les stores (même patron que lib/__tests__/token-storage.test.ts).
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

// Le store d'auth importe session.ts (hint cross-domain) : window/document minimaux.
globalThis.window ??= {} as never;
(globalThis.window as { location?: object }).location ??= {
  hostname: 'localhost',
  protocol: 'http:',
};
globalThis.document ??= { cookie: '' } as never;
// Le profil d'auth passe par `window.localStorage` (stockage par défaut de persist).
(globalThis.window as { localStorage?: Storage }).localStorage = globalThis.localStorage;

const CLE_MONUMENTS = 'monumia-cache-monuments';

/**
 * Des modules NEUFS à chaque appel : c'est ce que voit une page rechargée — le
 * localStorage survit, l'état des modules (dont le compte ouvert) repart de zéro.
 */
async function recharger() {
  vi.resetModules();
  const persistance = await import('@/stores/persistance');
  const { useAuthStore } = await import('@/stores/useAuthStore');
  const { useMonumentStore } = await import('@/stores/useMonumentStore');
  const { useProjetStore } = await import('@/stores/useProjetStore');
  const { useDossierStore } = await import('@/stores/useDossierStore');
  const { useAideStore } = await import('@/stores/useAideStore');
  return {
    ...persistance,
    useAuthStore,
    useMonumentStore,
    useProjetStore,
    useDossierStore,
    useAideStore,
  };
}

function monument(over: Partial<Monument> = {}): Monument {
  return {
    id: 'm1',
    userId: 'u1',
    nom: 'Château de Test',
    codeInsee: '75056',
    photos: [],
    ...over,
  } as Monument;
}

function projet(over: Partial<Projet> = {}): Projet {
  return {
    id: 'p1',
    monumentId: 'm1',
    userId: 'u1',
    travauxEnvisages: [],
    questionnaire: {},
    createdAt: '2026-09-22T00:00:00Z',
    updatedAt: '2026-09-22T00:00:00Z',
    ...over,
  } as Projet;
}

function entree(cle: string) {
  const brut = localStorage.getItem(cle);
  return brut ? JSON.parse(brut) : null;
}

describe('cache local des stores', () => {
  beforeEach(() => localStorage.clear());

  it('écrit sous le compte ouvert, et se relit au rechargement', async () => {
    const avant = await recharger();
    avant.ouvrirCaches('u1');
    avant.useMonumentStore.getState().setMonuments([monument()]);

    const stocke = entree(CLE_MONUMENTS);
    expect(stocke.compte).toBe('u1');
    expect(stocke.state.monuments).toHaveLength(1);

    const apres = await recharger();
    expect(apres.useMonumentStore.getState().monuments).toEqual([]); // pas relu à la création
    apres.ouvrirCaches('u1');
    const [relu] = apres.useMonumentStore.getState().monuments;
    expect(relu.nom).toBe('Château de Test');
    expect(relu.depuisLeCache).toBe(true);
  });

  it("n'écrit rien tant qu'aucun compte n'est ouvert", async () => {
    const s = await recharger();
    s.useMonumentStore.getState().setMonuments([monument()]);
    expect(localStorage.getItem(CLE_MONUMENTS)).toBeNull();
  });

  it("jette le cache d'un autre compte, et l'efface du poste", async () => {
    const avant = await recharger();
    avant.ouvrirCaches('u1');
    avant.useMonumentStore.getState().setMonuments([monument()]);

    const apres = await recharger();
    apres.ouvrirCaches('u2');
    expect(apres.useMonumentStore.getState().monuments).toEqual([]);
    expect(localStorage.getItem(CLE_MONUMENTS)).toBeNull();
  });

  it('jette une entrée plus vieille que le TTL', async () => {
    const avant = await recharger();
    avant.ouvrirCaches('u1');
    avant.useMonumentStore.getState().setMonuments([monument()]);
    const stocke = entree(CLE_MONUMENTS);
    stocke.ecritLe = Date.now() - avant.TTL_CACHE_MS - 1000;
    localStorage.setItem(CLE_MONUMENTS, JSON.stringify(stocke));

    const apres = await recharger();
    apres.ouvrirCaches('u1');
    expect(apres.useMonumentStore.getState().monuments).toEqual([]);
  });

  it('jette une version inconnue au lieu de la migrer', async () => {
    const avant = await recharger();
    avant.ouvrirCaches('u1');
    avant.useMonumentStore.getState().setMonuments([monument()]);
    const stocke = entree(CLE_MONUMENTS);
    stocke.version = 99;
    localStorage.setItem(CLE_MONUMENTS, JSON.stringify(stocke));

    const apres = await recharger();
    apres.ouvrirCaches('u1');
    expect(apres.useMonumentStore.getState().monuments).toEqual([]);
  });

  it('vide la mémoire quand la session change de compte sans déconnexion', async () => {
    const s = await recharger();
    s.ouvrirCaches('u1');
    s.useMonumentStore.getState().setMonuments([monument()]);
    s.useProjetStore.getState().setProjets([projet()]);

    s.ouvrirCaches('u2');
    expect(s.useMonumentStore.getState().monuments).toEqual([]);
    expect(s.useProjetStore.getState().projets).toEqual([]);
  });

  it('la déconnexion efface toutes les entrées du cache', async () => {
    const s = await recharger();
    s.useAuthStore.getState().setAuth({ id: 'u1', onboardingComplete: true } as never, 'jeton');
    s.useMonumentStore.getState().setMonuments([monument()]);
    s.useProjetStore.getState().setProjets([projet()]);
    s.useDossierStore.getState().setDossiers([]);
    s.useAideStore.getState().setDigests({});
    // Une entrée d'un format abandonné : la purge se fait par préfixe.
    localStorage.setItem('monumia-cache-ancien', '{}');
    expect([...backing.keys()].filter((k) => k.startsWith(s.PREFIXE_CACHE)).length).toBe(5);

    s.useAuthStore.getState().logout();

    expect([...backing.keys()].filter((k) => k.startsWith(s.PREFIXE_CACHE))).toEqual([]);
    expect(s.useMonumentStore.getState().monuments).toEqual([]);
    // Et rien ne se réécrit après coup, faute de compte ouvert.
    s.useMonumentStore.getState().setMonuments([monument()]);
    expect(localStorage.getItem(CLE_MONUMENTS)).toBeNull();
  });

  it("un store évalué après l'ouverture des caches se relit quand même", async () => {
    const avant = await recharger();
    avant.ouvrirCaches('u1');
    avant.useProjetStore.getState().setProjets([projet()]);

    // L'ordre qu'impose le cycle d'imports quand l'application y entre par un
    // store de données : les caches s'ouvrent, PUIS le store s'évalue.
    vi.resetModules();
    const persistance = await import('@/stores/persistance');
    persistance.ouvrirCaches('u1');
    const { useProjetStore } = await import('@/stores/useProjetStore');
    expect(useProjetStore.getState().projets.map((p) => p.id)).toEqual(['p1']);
  });

  it('la réhydratation du profil ouvre les caches de son compte', async () => {
    const avant = await recharger();
    avant.useAuthStore.getState().setAuth({ id: 'u1', onboardingComplete: true } as never, 'jeton');
    avant.useMonumentStore.getState().setMonuments([monument()]);

    // Rechargement : le profil persisté est relu à la création du store d'auth,
    // et c'est lui qui ouvre les caches — avant toute réponse du serveur.
    const apres = await recharger();
    expect(apres.useMonumentStore.getState().monuments).toHaveLength(1);
  });
});

describe('ce qui ouvre un droit ne touche jamais le localStorage', () => {
  beforeEach(() => localStorage.clear());

  it("ni l'offre, ni le rôle, ni l'équipe d'un monument", async () => {
    const s = await recharger();
    s.ouvrirCaches('u1');
    s.useMonumentStore.getState().setMonuments([
      monument({
        offre: { dashboard: true, equipe: true } as never,
        myRole: 'owner',
        members: [{ userId: 'u9', prenom: 'A', nom: 'B', role: 'member' }],
      }),
    ]);

    const brut = localStorage.getItem(CLE_MONUMENTS)!;
    expect(brut).not.toContain('"offre"');
    expect(brut).not.toContain('"myRole"');
    expect(brut).not.toContain('"members"');
    // En mémoire, rien n'a été retiré : seul l'écrit est filtré.
    expect(s.useMonumentStore.getState().monuments[0].offre).toBeDefined();
  });

  it("ni le rôle de l'utilisateur sur un projet", async () => {
    const s = await recharger();
    s.ouvrirCaches('u1');
    s.useProjetStore.getState().setProjets([projet({ myRole: 'co_owner' })]);

    expect(localStorage.getItem('monumia-cache-projets')!).not.toContain('"myRole"');
    expect(s.useProjetStore.getState().projets[0].myRole).toBe('co_owner');

    // Une entrée trafiquée ne le rend pas non plus : le rôle d'un projet relu du
    // cache est INCONNU, et `depuisLeCache` le dit aux pages.
    const stocke = entree('monumia-cache-projets');
    stocke.state.projets[0].myRole = 'owner';
    localStorage.setItem('monumia-cache-projets', JSON.stringify(stocke));
    const apres = await recharger();
    apres.ouvrirCaches('u1');
    const [relu] = apres.useProjetStore.getState().projets;
    expect(relu.myRole).toBeUndefined();
    expect(relu.depuisLeCache).toBe(true);
  });

  it('une entrée trafiquée à la main ne rend pas son offre au monument', async () => {
    const avant = await recharger();
    avant.ouvrirCaches('u1');
    avant.useMonumentStore.getState().setMonuments([monument()]);
    const stocke = entree(CLE_MONUMENTS);
    stocke.state.monuments[0].offre = { dashboard: true };
    stocke.state.monuments[0].myRole = 'owner';
    localStorage.setItem(CLE_MONUMENTS, JSON.stringify(stocke));

    const apres = await recharger();
    apres.ouvrirCaches('u1');
    const [relu] = apres.useMonumentStore.getState().monuments;
    expect(relu.offre).toBeUndefined();
    expect(relu.myRole).toBeUndefined();
  });
});
