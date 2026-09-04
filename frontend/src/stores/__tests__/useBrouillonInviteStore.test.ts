import { describe, it, expect, beforeEach } from 'vitest';

// Environnement vitest = node : on fournit un localStorage minimal AVANT
// d'importer le store (zustand/persist le capture à la création).
const backing = new Map<string, string>();
const faussetteStorage = {
  getItem: (k: string) => backing.get(k) ?? null,
  setItem: (k: string, v: string) => void backing.set(k, String(v)),
  removeItem: (k: string) => void backing.delete(k),
  clear: () => backing.clear(),
  key: (i: number) => [...backing.keys()][i] ?? null,
  get length() {
    return backing.size;
  },
} as Storage;

// defineProperty : sous Node ≥22, `localStorage` est un accesseur global que
// l'affectation directe ne remplace pas silencieusement.
Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: faussetteStorage,
});
// Et sur `window` aussi : le stockage par défaut de zustand/persist lit
// `window.localStorage`, pas le global. Sans ça le middleware se rabat sur un
// mode sans stockage (avertissement en console) et n'expose même pas
// `store.persist`.
globalThis.window ??= {} as never;
Object.defineProperty(globalThis.window, 'localStorage', {
  configurable: true,
  value: faussetteStorage,
});

const { useBrouillonInviteStore, estPerime, VERSION_BROUILLON } = await import(
  '@/stores/useBrouillonInviteStore'
);

const KEY = 'monumia-brouillon-invite';

const MONUMENT: import('@/types').MonumentInput = {
  nom: 'Chapelle Saint-Julien',
  commune: 'Rouen',
  codeInsee: '76540',
  protection: 'classe',
  proprietaire: 'prive_personne_physique',
};

function vide() {
  useBrouillonInviteStore.getState().vider();
  backing.clear();
}

describe('brouillon du parcours découverte', () => {
  beforeEach(vide);

  it('part vide', () => {
    const s = useBrouillonInviteStore.getState();
    expect(s.monument).toBeNull();
    expect(s.travaux).toBeNull();
    expect(s.answers).toEqual({});
    expect(s.etape).toBe('intention');
    expect(s.monumentId).toBeNull();
  });

  it('persiste le monument, la version et la date de création', () => {
    useBrouillonInviteStore.getState().setMonument(MONUMENT);

    const persiste = JSON.parse(backing.get(KEY) ?? '{}');
    expect(persiste.version).toBe(VERSION_BROUILLON);
    expect(persiste.state.monument.nom).toBe('Chapelle Saint-Julien');
    expect(typeof persiste.state.creeLe).toBe('string');
  });

  it('garde la date de création du premier enregistrement', () => {
    useBrouillonInviteStore.getState().setMonument(MONUMENT);
    const premier = useBrouillonInviteStore.getState().creeLe;
    useBrouillonInviteStore.getState().setMonument({ ...MONUMENT, nom: 'Autre nom' });
    expect(useBrouillonInviteStore.getState().creeLe).toBe(premier);
  });

  it('remet le cadrage à zéro quand le monument change de bien', () => {
    const store = useBrouillonInviteStore.getState();
    store.setMonument(MONUMENT);
    store.setCadrage(['restauration_travaux'], ['toiture']);
    store.setAnswers({ etat_travaux: 'non_commences' });
    store.setEtape('questionnaire');

    useBrouillonInviteStore.getState().setMonument({ ...MONUMENT, nom: 'Autre monument' });

    const s = useBrouillonInviteStore.getState();
    expect(s.raisons).toEqual([]);
    expect(s.travaux).toBeNull();
    expect(s.answers).toEqual({});
    expect(s.etape).toBe('intention');
  });

  it('conserve le cadrage quand seul un détail du même bien est corrigé', () => {
    const store = useBrouillonInviteStore.getState();
    store.setMonument(MONUMENT);
    store.setCadrage(['restauration_travaux'], ['toiture']);
    store.setAnswers({ etat_travaux: 'non_commences' });

    // Retour en arrière dans le wizard monument : la protection est corrigée,
    // le bien reste le même (nom, commune, code INSEE inchangés).
    useBrouillonInviteStore.getState().setMonument({ ...MONUMENT, protection: 'inscrit' });

    const s = useBrouillonInviteStore.getState();
    expect(s.travaux).toEqual(['toiture']);
    expect(s.answers).toEqual({ etat_travaux: 'non_commences' });
  });

  it('mémorise les ids posés pendant le rejeu', () => {
    const store = useBrouillonInviteStore.getState();
    store.setMonument(MONUMENT);
    store.marquerMonumentCree('mon-1');
    expect(useBrouillonInviteStore.getState().monumentId).toBe('mon-1');
    useBrouillonInviteStore.getState().marquerProjetCree('prj-1');
    expect(useBrouillonInviteStore.getState().projetId).toBe('prj-1');
  });

  it('vider ramène tout à l’état initial', () => {
    const store = useBrouillonInviteStore.getState();
    store.setMonument(MONUMENT);
    store.setCadrage(['fiscalite'], []);
    store.setEtape('inscription');
    store.marquerMonumentCree('mon-1');

    useBrouillonInviteStore.getState().vider();

    const s = useBrouillonInviteStore.getState();
    expect(s.monument).toBeNull();
    expect(s.monumentId).toBeNull();
    expect(s.creeLe).toBeNull();
    expect(s.etape).toBe('intention');
  });
});

describe('réhydratation', () => {
  beforeEach(vide);

  it('jette un état de version inconnue', async () => {
    backing.set(
      KEY,
      JSON.stringify({
        version: VERSION_BROUILLON + 1,
        state: { monument: MONUMENT, etape: 'inscription', creeLe: new Date().toISOString() },
      })
    );
    await useBrouillonInviteStore.persist.rehydrate();
    expect(useBrouillonInviteStore.getState().monument).toBeNull();
  });

  it('jette aussi une version antérieure', async () => {
    backing.set(
      KEY,
      JSON.stringify({
        version: 0,
        state: { monument: MONUMENT, etape: 'inscription', creeLe: new Date().toISOString() },
      })
    );
    await useBrouillonInviteStore.persist.rehydrate();
    expect(useBrouillonInviteStore.getState().monument).toBeNull();
  });

  it('relit un brouillon récent', async () => {
    backing.set(
      KEY,
      JSON.stringify({
        version: VERSION_BROUILLON,
        state: {
          monument: MONUMENT,
          raisons: ['restauration_travaux'],
          travaux: ['toiture'],
          answers: { etat_travaux: 'non_commences' },
          etape: 'inscription',
          monumentId: null,
          projetId: null,
          creeLe: new Date().toISOString(),
        },
      })
    );
    await useBrouillonInviteStore.persist.rehydrate();

    const s = useBrouillonInviteStore.getState();
    expect(s.monument?.nom).toBe('Chapelle Saint-Julien');
    expect(s.etape).toBe('inscription');
    expect(s.answers).toEqual({ etat_travaux: 'non_commences' });
  });

  it('purge un brouillon de plus de sept jours', async () => {
    const vieux = new Date(Date.now() - 8 * 24 * 3600 * 1000).toISOString();
    backing.set(
      KEY,
      JSON.stringify({
        version: VERSION_BROUILLON,
        state: { monument: MONUMENT, etape: 'inscription', creeLe: vieux, answers: {} },
      })
    );
    await useBrouillonInviteStore.persist.rehydrate();
    expect(useBrouillonInviteStore.getState().monument).toBeNull();
  });
});

describe('estPerime', () => {
  it('tolère un brouillon sans date (rien à purger)', () => {
    expect(estPerime(null)).toBe(false);
  });

  it('accepte une date du jour', () => {
    expect(estPerime(new Date().toISOString())).toBe(false);
  });

  it('rejette une date de huit jours', () => {
    expect(estPerime(new Date(Date.now() - 8 * 24 * 3600 * 1000).toISOString())).toBe(true);
  });

  it('rejette une date illisible', () => {
    expect(estPerime('pas-une-date')).toBe(true);
  });
});
