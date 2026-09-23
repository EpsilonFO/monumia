import { beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Le transport est remplacé : ce qu'on teste, c'est le PARTAGE de la requête en
 * vol — la coquille de l'espace et la page affichée appellent `load()` au même
 * montage, et une seule requête doit partir.
 */
const authFetch = vi.fn();
vi.mock('@/lib/auth-fetch', () => ({
  authFetch: (...args: unknown[]) => authFetch(...args),
  handleResponse: (res: unknown) => res,
}));

const { dashboardService } = await import('@/services/dashboard.service');
const { useProjetStore } = await import('@/stores/useProjetStore');

const VIDE = { monuments: [], projets: [], dossiers: [], digests: {}, suivis: {} };

/** Une promesse qu'on résout à la main. */
function differee<T>() {
  let resoudre!: (v: T) => void;
  const promesse = new Promise<T>((r) => {
    resoudre = r;
  });
  return { promesse, resoudre };
}

function ligneProjet(updatedAt: string, questionnaire: Record<string, string>) {
  return {
    id: 'p1',
    monument_id: 'm1',
    user_id: 'u1',
    travaux_envisages: [],
    questionnaire,
    created_at: '2026-09-22T00:00:00Z',
    updated_at: updatedAt,
  };
}

describe('dashboardService.load', () => {
  beforeEach(() => {
    authFetch.mockReset();
    useProjetStore.setState({ projets: [], loaded: false });
  });

  it('deux appels rapprochés partagent une seule requête', async () => {
    const reponse = differee<typeof VIDE>();
    authFetch.mockReturnValue(reponse.promesse);

    const a = dashboardService.load();
    const b = dashboardService.load();
    expect(a).toBe(b);
    expect(authFetch).toHaveBeenCalledTimes(1);

    reponse.resoudre(VIDE);
    await a;
  });

  it('une fois réglée, la requête suivante repart bien', async () => {
    authFetch.mockResolvedValue(VIDE);
    await dashboardService.load();
    await dashboardService.load();
    expect(authFetch).toHaveBeenCalledTimes(2);
  });

  it('un échec libère la place pour la tentative suivante', async () => {
    authFetch.mockRejectedValueOnce(new Error('réseau'));
    await expect(dashboardService.load()).rejects.toThrow('réseau');
    authFetch.mockResolvedValue(VIDE);
    await dashboardService.load();
    expect(authFetch).toHaveBeenCalledTimes(2);
  });

  it("n'écrase pas un projet écrit pendant que la requête était en vol", async () => {
    // Une réponse au questionnaire enregistrée à 10 h 01, alors que le
    // tableau de bord rapporte l'état de 10 h 00.
    const { toProjet } = await import('@/services/projet.service');
    useProjetStore.setState({
      projets: [toProjet(ligneProjet('2026-09-22T10:01:00Z', { fait: 'oui' }))],
    });
    authFetch.mockResolvedValue({ ...VIDE, projets: [ligneProjet('2026-09-22T10:00:00Z', {})] });

    await dashboardService.load();

    expect(useProjetStore.getState().projets[0].questionnaire).toEqual({ fait: 'oui' });
  });

  it('un projet relu du cache cède toujours la place au serveur', async () => {
    const { toProjet } = await import('@/services/projet.service');
    useProjetStore.setState({
      projets: [
        { ...toProjet(ligneProjet('2026-09-22T10:01:00Z', { vieux: 'oui' })), depuisLeCache: true },
      ],
    });
    authFetch.mockResolvedValue({ ...VIDE, projets: [ligneProjet('2026-09-22T10:00:00Z', {})] });

    await dashboardService.load();

    const [p] = useProjetStore.getState().projets;
    expect(p.questionnaire).toEqual({});
    expect(p.depuisLeCache).toBeUndefined();
  });
});
