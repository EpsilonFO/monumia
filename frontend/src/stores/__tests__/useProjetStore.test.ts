import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Projet } from '@/types';

/** Le service est remplacé : ce qu'on teste, c'est la SÉRIALISATION, pas HTTP. */
const update = vi.fn();
const getById = vi.fn();
vi.mock('@/services/projet.service', () => ({
  projetService: {
    update: (...args: unknown[]) => update(...args),
    getById: (...args: unknown[]) => getById(...args),
  },
}));

const { useProjetStore } = await import('../useProjetStore');

/**
 * Un id de projet DIFFÉRENT par test : la file d'écriture est un module-level
 * `Map` clé par projet, qu'on ne veut ni vider par une trappe exportée pour les
 * tests, ni laisser fuir d'un cas au suivant.
 */
let compteur = 0;
let pid = 'p0';

/** Laisse tourner les microtâches : la file part sur un `then`, pas en synchrone. */
async function flush(ticks = 3) {
  for (let i = 0; i < ticks; i++) await Promise.resolve();
}

function projet(over: Partial<Projet> = {}): Projet {
  return {
    id: pid,
    monumentId: 'm1',
    userId: 'u1',
    travauxEnvisages: [],
    questionnaire: {},
    createdAt: '2026-09-16T00:00:00Z',
    updatedAt: '2026-09-16T00:00:00Z',
    ...over,
  } as Projet;
}

/** Une promesse qu'on résout à la main, pour entrelacer deux écritures. */
function differee<T>() {
  let resoudre!: (v: T) => void;
  const promesse = new Promise<T>((r) => {
    resoudre = r;
  });
  return { promesse, resoudre };
}

describe('repondreFait', () => {
  beforeEach(() => {
    update.mockReset();
    getById.mockReset();
    pid = `p${++compteur}`;
    useProjetStore.setState({ projets: [projet()], loaded: true });
  });

  it('écrit la réponse par-dessus le questionnaire existant', async () => {
    useProjetStore.setState({ projets: [projet({ questionnaire: { _raisons: ['x'] } })] });
    update.mockImplementation((id, input) => Promise.resolve(projet({ ...input, id })));

    await useProjetStore.getState().repondreFait(pid, 'etat_travaux', 'non_commences');

    expect(update).toHaveBeenCalledWith(pid, {
      questionnaire: { _raisons: ['x'], etat_travaux: 'non_commences' },
    });
    expect(useProjetStore.getState().getProjet(pid)?.questionnaire.etat_travaux).toBe(
      'non_commences',
    );
  });

  it('une valeur `undefined` efface la réponse', async () => {
    useProjetStore.setState({ projets: [projet({ questionnaire: { etat_travaux: 'oui' } })] });
    update.mockImplementation((id, input) => Promise.resolve(projet({ ...input, id })));

    await useProjetStore.getState().repondreFait(pid, 'etat_travaux', undefined);

    expect(update).toHaveBeenCalledWith(pid, { questionnaire: {} });
  });

  it('deux réponses rapides ne s’écrasent pas', async () => {
    // `update_projet` remplace `questionnaire` EN BLOC : parties ensemble, les
    // deux requêtes liraient le même état de départ et la seconde perdrait la
    // réponse de la première. La file garantit que la seconde part APRÈS.
    const premiere = differee<Projet>();
    update.mockImplementationOnce(() => premiere.promesse);
    update.mockImplementationOnce((id, input) => Promise.resolve(projet({ ...input, id })));

    const a = useProjetStore.getState().repondreFait(pid, 'fait_a', 'oui');
    const b = useProjetStore.getState().repondreFait(pid, 'fait_b', 'non');

    // La seconde n'est pas encore partie : elle attend l'état d'après la première.
    await flush();
    expect(update).toHaveBeenCalledTimes(1);

    premiere.resoudre(projet({ questionnaire: { fait_a: 'oui' } }));
    await a;
    await b;

    expect(update).toHaveBeenNthCalledWith(2, pid, {
      questionnaire: { fait_a: 'oui', fait_b: 'non' },
    });
    expect(useProjetStore.getState().getProjet(pid)?.questionnaire).toEqual({
      fait_a: 'oui',
      fait_b: 'non',
    });
  });

  it('un échec remonte à l’appelant mais ne bloque pas la file', async () => {
    update.mockRejectedValueOnce(new Error('403'));
    update.mockImplementationOnce((id, input) => Promise.resolve(projet({ ...input, id })));

    await expect(
      useProjetStore.getState().repondreFait(pid, 'fait_a', 'oui'),
    ).rejects.toThrow('403');
    await useProjetStore.getState().repondreFait(pid, 'fait_b', 'non');

    expect(useProjetStore.getState().getProjet(pid)?.questionnaire).toEqual({ fait_b: 'non' });
  });

  it('store non hydraté : on relit le projet plutôt que d’écrire par-dessus un vide', async () => {
    useProjetStore.setState({ projets: [], loaded: false });
    getById.mockResolvedValue(projet({ questionnaire: { deja: 'la' } }));
    update.mockImplementation((id, input) => Promise.resolve(projet({ ...input, id })));

    await useProjetStore.getState().repondreFait(pid, 'fait_a', 'oui');

    expect(getById).toHaveBeenCalledWith(pid);
    expect(update).toHaveBeenCalledWith(pid, {
      questionnaire: { deja: 'la', fait_a: 'oui' },
    });
  });

  it('projet relu du cache local : on relit le serveur, son questionnaire peut dater', async () => {
    // Une réponse donnée depuis un autre onglet après l'écriture du cache : la
    // remplacer en bloc par la version du cache l'effacerait.
    useProjetStore.setState({
      projets: [projet({ questionnaire: { perimee: 'oui' }, depuisLeCache: true })],
    });
    getById.mockResolvedValue(projet({ questionnaire: { perimee: 'oui', autre_onglet: 'non' } }));
    update.mockImplementation((id, input) => Promise.resolve(projet({ ...input, id })));

    await useProjetStore.getState().repondreFait(pid, 'fait_a', 'oui');

    expect(getById).toHaveBeenCalledWith(pid);
    expect(update).toHaveBeenCalledWith(pid, {
      questionnaire: { perimee: 'oui', autre_onglet: 'non', fait_a: 'oui' },
    });
  });
});
