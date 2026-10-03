import { describe, it, expect, beforeEach, vi } from 'vitest';
import type { Monument, MonumentInput, Projet } from '@/types';

// Environnement vitest = node : localStorage (global ET sur `window`, que le
// stockage par défaut de zustand/persist lit) avant tout import de store.
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
Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: faussetteStorage,
});
globalThis.window ??= {} as never;
Object.defineProperty(globalThis.window, 'localStorage', {
  configurable: true,
  value: faussetteStorage,
});

// sessionStorage pour le drapeau de retour Google.
const sessionBacking = new Map<string, string>();
Object.defineProperty(globalThis, 'sessionStorage', {
  configurable: true,
  value: {
    getItem: (k: string) => sessionBacking.get(k) ?? null,
    setItem: (k: string, v: string) => void sessionBacking.set(k, String(v)),
    removeItem: (k: string) => void sessionBacking.delete(k),
    clear: () => sessionBacking.clear(),
    key: (i: number) => [...sessionBacking.keys()][i] ?? null,
    get length() {
      return sessionBacking.size;
    },
  } as Storage,
});

const creerMonument = vi.fn();
const getMonumentById = vi.fn();
const creerProjet = vi.fn();
const getProjetById = vi.fn();

vi.mock('@/services/monument.service', () => ({
  monumentService: {
    create: (...a: unknown[]) => creerMonument(...a),
    getById: (...a: unknown[]) => getMonumentById(...a),
  },
}));
vi.mock('@/services/projet.service', () => ({
  projetService: {
    create: (...a: unknown[]) => creerProjet(...a),
    getById: (...a: unknown[]) => getProjetById(...a),
  },
}));

const {
  brouillonPretPourRejeu,
  finaliserBrouillon,
  marquerRetourGoogleBrouillon,
  monumentDepuisBrouillon,
  prendreRetourGoogleBrouillon,
} = await import('@/lib/brouillon-invite');
const { useBrouillonInviteStore, VERSION_BROUILLON } = await import(
  '@/stores/useBrouillonInviteStore'
);
const { useMonumentStore } = await import('@/stores/useMonumentStore');
const { useProjetStore } = await import('@/stores/useProjetStore');

const MONUMENT: MonumentInput = {
  nom: 'Chapelle Saint-Julien',
  commune: 'Rouen',
  codeInsee: '76540',
  protection: 'classe',
  proprietaire: ['prive_personne_physique'],
  etatConservation: 'peril',
};

const MONUMENT_CREE = { ...MONUMENT, id: 'mon-1' } as Monument;
const PROJET_CREE = { id: 'prj-1', monumentId: 'mon-1' } as Projet;

/** Brouillon complet, tel qu'il arrive sur l'écran de reprise. */
function brouillonComplet() {
  const store = useBrouillonInviteStore.getState();
  store.setMonument(MONUMENT);
  store.setCadrage(['restauration_travaux'], ['toiture']);
  store.setAnswers({ etat_travaux: 'non_commences' });
  store.setEtape('inscription');
}

beforeEach(() => {
  vi.clearAllMocks();
  useBrouillonInviteStore.getState().vider();
  useMonumentStore.setState({ monuments: [], activeMonumentId: null });
  useProjetStore.setState({ projets: [], loaded: false });
  backing.clear();
  sessionBacking.clear();
  creerMonument.mockResolvedValue(MONUMENT_CREE);
  getMonumentById.mockResolvedValue(MONUMENT_CREE);
  creerProjet.mockResolvedValue(PROJET_CREE);
  getProjetById.mockResolvedValue(PROJET_CREE);
});

describe('brouillonPretPourRejeu', () => {
  it('faux sur un brouillon vide', () => {
    expect(brouillonPretPourRejeu()).toBe(false);
  });

  it("faux tant que l'inscription n'est pas atteinte", () => {
    useBrouillonInviteStore.getState().setMonument(MONUMENT);
    useBrouillonInviteStore.getState().setEtape('questionnaire');
    expect(brouillonPretPourRejeu()).toBe(false);
  });

  it('vrai sur un brouillon complet', () => {
    brouillonComplet();
    expect(brouillonPretPourRejeu()).toBe(true);
  });
});

describe('monumentDepuisBrouillon', () => {
  it("complète ce qu'un Monument exige, sans inventer d'identifiant réel", () => {
    const m = monumentDepuisBrouillon(MONUMENT);
    expect(m.nom).toBe('Chapelle Saint-Julien');
    expect(m.protection).toBe('classe');
    expect(m.photos).toEqual([]);
    expect(m.completionPercentage).toBe(0);
    expect(m.id).toBe('brouillon');
    expect(typeof m.createdAt).toBe('string');
  });
});

describe('drapeau de retour Google', () => {
  it("n'est pas levé par défaut", () => {
    expect(prendreRetourGoogleBrouillon()).toBe(false);
  });

  it('se pose et se consomme une seule fois', () => {
    marquerRetourGoogleBrouillon();
    expect(prendreRetourGoogleBrouillon()).toBe(true);
    expect(prendreRetourGoogleBrouillon()).toBe(false);
  });
});

describe('finaliserBrouillon — chemin nominal', () => {
  it('crée le monument puis le projet, avec les intentions recomposées', async () => {
    brouillonComplet();

    const { monumentId, projetId } = await finaliserBrouillon();

    expect(monumentId).toBe('mon-1');
    expect(projetId).toBe('prj-1');
    expect(creerMonument).toHaveBeenCalledTimes(1);
    expect(creerMonument).toHaveBeenCalledWith(expect.objectContaining({ nom: MONUMENT.nom }));
    expect(creerProjet).toHaveBeenCalledWith('mon-1', {
      travauxEnvisages: ['toiture'],
      questionnaire: { etat_travaux: 'non_commences', _raisons: ['restauration_travaux'] },
    });
  });

  it('amorce les stores et vide le brouillon', async () => {
    brouillonComplet();
    await finaliserBrouillon();

    expect(useMonumentStore.getState().monuments.map((m) => m.id)).toEqual(['mon-1']);
    expect(useMonumentStore.getState().activeMonumentId).toBe('mon-1');
    expect(useProjetStore.getState().projets.map((p) => p.id)).toEqual(['prj-1']);
    expect(useBrouillonInviteStore.getState().monument).toBeNull();
  });

  it('« Pas encore déterminé » part en liste vide, jamais en null', async () => {
    const store = useBrouillonInviteStore.getState();
    store.setMonument(MONUMENT);
    store.setEtape('inscription');
    await finaliserBrouillon();

    expect(creerProjet).toHaveBeenCalledWith('mon-1', {
      travauxEnvisages: [],
      questionnaire: { _raisons: [] },
    });
  });

  it('refuse de rejouer un brouillon sans monument', async () => {
    await expect(finaliserBrouillon()).rejects.toThrow(/brouillon/i);
    expect(creerMonument).not.toHaveBeenCalled();
  });
});

describe('finaliserBrouillon — reprise après échec', () => {
  it('ne recrée pas le monument quand son id est déjà posé', async () => {
    brouillonComplet();
    useBrouillonInviteStore.getState().marquerMonumentCree('mon-1');

    await finaliserBrouillon();

    expect(creerMonument).not.toHaveBeenCalled();
    expect(getMonumentById).toHaveBeenCalledWith('mon-1');
    expect(creerProjet).toHaveBeenCalledTimes(1);
  });

  it('ne recrée pas le projet quand son id est déjà posé', async () => {
    brouillonComplet();
    useBrouillonInviteStore.getState().marquerMonumentCree('mon-1');
    useBrouillonInviteStore.getState().marquerProjetCree('prj-1');

    await finaliserBrouillon();

    expect(creerMonument).not.toHaveBeenCalled();
    expect(creerProjet).not.toHaveBeenCalled();
    expect(getProjetById).toHaveBeenCalledWith('prj-1');
  });

  it("garde le monumentId et le brouillon quand la création du projet échoue", async () => {
    brouillonComplet();
    creerProjet.mockRejectedValue(new Error('réseau'));

    await expect(finaliserBrouillon()).rejects.toThrow('réseau');

    // C'est tout l'enjeu : le monument existe en base, l'écrire dans le
    // brouillon AVANT l'appel projet est ce qui rend « Réessayer » sans doublon.
    const s = useBrouillonInviteStore.getState();
    expect(s.monumentId).toBe('mon-1');
    expect(s.monument).not.toBeNull();
    expect(s.etape).toBe('inscription');
  });

  it('un « Réessayer » ne rejoue que le projet', async () => {
    brouillonComplet();
    creerProjet.mockRejectedValueOnce(new Error('réseau'));
    await expect(finaliserBrouillon()).rejects.toThrow('réseau');

    await finaliserBrouillon();

    expect(creerMonument).toHaveBeenCalledTimes(1);
    expect(creerProjet).toHaveBeenCalledTimes(2);
    expect(useBrouillonInviteStore.getState().monument).toBeNull();
  });

  it('laisse le brouillon intact quand la création du monument échoue', async () => {
    brouillonComplet();
    creerMonument.mockRejectedValue(new Error('402'));

    await expect(finaliserBrouillon()).rejects.toThrow('402');

    const s = useBrouillonInviteStore.getState();
    expect(s.monumentId).toBeNull();
    expect(s.monument).not.toBeNull();
    expect(creerProjet).not.toHaveBeenCalled();
  });
});

describe('finaliserBrouillon — deux onglets', () => {
  it('relit le stockage avant de rejouer', async () => {
    // L'autre onglet a fini le questionnaire ; celui-ci a un état plus ancien.
    useBrouillonInviteStore.setState({ monument: null, etape: 'intention' });
    backing.set(
      'monumia-brouillon-invite',
      JSON.stringify({
        version: VERSION_BROUILLON,
        state: {
          monument: MONUMENT,
          raisons: ['fiscalite'],
          // `null` : l'étape des activités n'a pas été posée (intention
          // fiscale). La clé `_familles` reste donc absente du questionnaire.
          familles: null,
          travaux: ['facade'],
          answers: { etat_travaux: 'acheves' },
          etape: 'inscription',
          monumentId: null,
          projetId: null,
          creeLe: new Date().toISOString(),
        },
      })
    );

    await finaliserBrouillon();

    expect(creerProjet).toHaveBeenCalledWith('mon-1', {
      travauxEnvisages: ['facade'],
      questionnaire: { etat_travaux: 'acheves', _raisons: ['fiscalite'] },
    });
  });
});
