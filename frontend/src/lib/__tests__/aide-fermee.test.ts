import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/aide.service', () => ({
  aideService: { marquerFermeeVue: vi.fn().mockResolvedValue(undefined) },
}));

import { ApiError } from '@/lib/api-error';
import { aideFermeeDe, oublierAideFermee } from '@/lib/aide-fermee';
import { aideService } from '@/services/aide.service';
import { useDossierStore } from '@/stores/useDossierStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import type { AideSuivi, Dossier } from '@/types';

const SLUG = 'tt-restauration';

function dossier(id: string, projetId: string, aideId: string, deposee?: boolean): Dossier {
  return {
    id,
    projetId,
    aideId,
    aideFermee:
      deposee === undefined ? undefined : { nom: 'Patrimoine rural', fermeeLe: '2026-10-15', deposee },
  } as Dossier;
}

describe('aide fermée', () => {
  beforeEach(() => {
    useDossierStore.setState({ dossiers: [] });
    useSuiviStore.setState({ suivis: [] });
  });

  it('reconnaît le 410 du serveur, et rien d’autre', () => {
    const detail = { code: 'aide_fermee', nom: 'Patrimoine rural', fermeeLe: '2026-10-15', deposee: false };
    expect(aideFermeeDe(new ApiError(410, 'x', detail))).toEqual({
      nom: 'Patrimoine rural',
      fermeeLe: '2026-10-15',
      deposee: false,
    });
    expect(aideFermeeDe(new ApiError(404, 'Aide introuvable', 'Aide introuvable'))).toBeNull();
    expect(aideFermeeDe(new ApiError(410, 'x', { code: 'autre' }))).toBeNull();
    expect(aideFermeeDe(new Error('réseau'))).toBeNull();
  });

  it('oublie les dossiers en préparation, garde les demandes déposées', async () => {
    useDossierStore.setState({
      dossiers: [
        dossier('d1', 'p1', SLUG, false),
        dossier('d2', 'p2', SLUG, true),
        dossier('d3', 'p1', 'autre'),
      ],
    });
    useSuiviStore.setState({
      suivis: [
        { projetId: 'p1', aideId: SLUG } as AideSuivi,
        { projetId: 'p2', aideId: SLUG } as AideSuivi,
      ],
    });
    await oublierAideFermee(SLUG);
    expect(aideService.marquerFermeeVue).toHaveBeenCalledWith(SLUG);
    expect(useDossierStore.getState().dossiers.map((d) => d.id)).toEqual(['d2', 'd3']);
    expect(useSuiviStore.getState().suivis.map((s) => s.projetId)).toEqual(['p2']);
  });
});
