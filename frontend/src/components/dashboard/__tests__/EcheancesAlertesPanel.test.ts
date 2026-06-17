import { describe, expect, it } from 'vitest';
import { buildFeedRows } from '../echeances-alertes-utils';
import { ROUTES } from '@/constants/routes';
import type { Monument } from '@/types';
import type { Notification } from '@/types';
import type { ProjectDeadline } from '@/lib/project-stats';

// ---- ISO date helpers (relative to "now") ----
const iso = (offsetDays: number): string => {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
};

// ---- minimal builders ----
function makeMonument(partial: Partial<Monument> & { id: string }): Monument {
  return {
    id: partial.id,
    userId: 'u1',
    nom: partial.nom ?? `Monument ${partial.id}`,
    codeInsee: '00000',
    protection: 'classe',
    proprietaire: 'public_commune',
    etatConservation: partial.etatConservation ?? 'moyen',
    urgenceTravaux: partial.urgenceTravaux,
    photos: [],
    completionPercentage: partial.completionPercentage ?? 60,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  } as Monument;
}

function makeDeadline(
  partial: Partial<ProjectDeadline> & { id: string; joursRestants: number }
): ProjectDeadline {
  const date = iso(partial.joursRestants);
  return {
    id: partial.id,
    label: partial.label ?? `Échéance ${partial.id}`,
    date,
    source: partial.source ?? 'aide',
    joursRestants: partial.joursRestants,
    urgency: partial.urgency ?? 'normal',
    monumentId: partial.monumentId,
    aideId: partial.aideId,
    dossierId: partial.dossierId,
  };
}

function makeNotification(partial: Partial<Notification> & { id: string }): Notification {
  return {
    id: partial.id,
    userId: 'u1',
    type: partial.type ?? 'info',
    categorie: partial.categorie ?? 'system',
    titre: partial.titre ?? `Notification ${partial.id}`,
    message: partial.message ?? '',
    lue: partial.lue ?? false,
    dateCreation: partial.dateCreation ?? new Date().toISOString(),
  };
}

describe('buildFeedRows — empty state', () => {
  it('returns an empty array when all inputs are empty', () => {
    expect(buildFeedRows([], [], [])).toEqual([]);
  });
});

describe('buildFeedRows — péril & incomplete dossiers', () => {
  it('produces a péril row for a monument en péril', () => {
    const m = makeMonument({ id: 'm1', etatConservation: 'peril', completionPercentage: 40 });
    const rows = buildFeedRows([], [m], []);
    expect(rows.filter((r) => r.id === 'peril-m1')).toHaveLength(1);
  });

  it('produces a péril row for an urgenceTravaux=critique monument', () => {
    const m = makeMonument({ id: 'm2', urgenceTravaux: 'critique', completionPercentage: 50 });
    const rows = buildFeedRows([], [m], []);
    expect(rows.filter((r) => r.id === 'peril-m2')).toHaveLength(1);
  });

  it('does NOT surface incomplete dossiers — they no longer belong to the échéancier', () => {
    const m = makeMonument({ id: 'm3', etatConservation: 'mauvais', completionPercentage: 70 });
    const rows = buildFeedRows([], [m], []);
    expect(rows).toHaveLength(0);
  });

  it('does NOT produce any row for a monument with completion = 100', () => {
    const m = makeMonument({ id: 'm4', etatConservation: 'bon', completionPercentage: 100 });
    const rows = buildFeedRows([], [m], []);
    expect(rows.filter((r) => r.id.endsWith('m4'))).toHaveLength(0);
  });
});

describe('buildFeedRows — deadline routing', () => {
  it('routes a dossier deadline to DOSSIER_DETAIL(dossierId)', () => {
    const d = makeDeadline({ id: 'd1', joursRestants: 5, dossierId: 'dossier-abc', source: 'dossier' });
    const row = buildFeedRows([d], [], []).find((r) => r.id === 'deadline-d1');
    expect(row?.to).toBe(ROUTES.DOSSIER_DETAIL('dossier-abc'));
  });

  it('routes an aide deadline to its aide page (PROJET_AIDE)', () => {
    const d = makeDeadline({
      id: 'd2',
      joursRestants: 10,
      aideId: 'aide-xyz',
      monumentId: 'mon-1',
      source: 'aide',
    });
    const row = buildFeedRows([d], [], []).find((r) => r.id === 'deadline-d2');
    expect(row?.to).toBe(ROUTES.PROJET_AIDE('mon-1', 'aide-xyz'));
  });

  it('falls back to the projects list for an aide deadline without a known monument', () => {
    const d = makeDeadline({ id: 'd3', joursRestants: 10, aideId: 'aide-xyz', source: 'aide' });
    const row = buildFeedRows([d], [], []).find((r) => r.id === 'deadline-d3');
    expect(row?.to).toBe(ROUTES.PROJETS);
  });

  it('filters out past deadlines (joursRestants < 0)', () => {
    const past = makeDeadline({ id: 'd3', joursRestants: -5 });
    expect(buildFeedRows([past], [], []).find((r) => r.id === 'deadline-d3')).toBeUndefined();
  });
});

describe('buildFeedRows — kind assignment', () => {
  it('assigns kind=urgent for a deadline less than 30 days out (rouge)', () => {
    const rows = buildFeedRows([makeDeadline({ id: 'u1', joursRestants: 3 })], [], []);
    expect(rows.find((r) => r.id === 'deadline-u1')?.kind).toBe('urgent');
  });

  it('assigns kind=warning for a deadline 30–100 days out (orange)', () => {
    const rows = buildFeedRows([makeDeadline({ id: 'u2', joursRestants: 50 })], [], []);
    expect(rows.find((r) => r.id === 'deadline-u2')?.kind).toBe('warning');
  });

  it('assigns kind=info for a deadline more than 100 days out (bleu)', () => {
    const rows = buildFeedRows([makeDeadline({ id: 'u3', joursRestants: 120 })], [], []);
    expect(rows.find((r) => r.id === 'deadline-u3')?.kind).toBe('info');
  });

  it('maps urgent notifications to kind=urgent and info ones to kind=info', () => {
    const urgent = makeNotification({ id: 'n1', type: 'urgent' });
    const info = makeNotification({ id: 'n2', type: 'info' });
    const rows = buildFeedRows([], [], [urgent, info]);
    expect(rows.find((r) => r.id === 'notif-n1')?.kind).toBe('urgent');
    expect(rows.find((r) => r.id === 'notif-n2')?.kind).toBe('info');
  });
});

describe('buildFeedRows — badges', () => {
  it('uses J-X for a future deadline and Auj. for today', () => {
    const rows = buildFeedRows(
      [makeDeadline({ id: 'b1', joursRestants: 3 }), makeDeadline({ id: 'b2', joursRestants: 0 })],
      [],
      []
    );
    expect(rows.find((r) => r.id === 'deadline-b1')?.badge).toBe('J-3');
    expect(rows.find((r) => r.id === 'deadline-b2')?.badge).toBe('Auj.');
  });

  it('uses "Péril" for a péril monument', () => {
    const peril = makeMonument({ id: 'p1', etatConservation: 'peril' });
    const rows = buildFeedRows([], [peril], []);
    expect(rows.find((r) => r.id === 'peril-p1')?.badge).toBe('Péril');
  });

  it('uses "Nouveau" for an unread notification', () => {
    const rows = buildFeedRows([], [], [makeNotification({ id: 'n9' })]);
    expect(rows.find((r) => r.id === 'notif-n9')?.badge).toBe('Nouveau');
  });
});

describe('buildFeedRows — notifications visibility', () => {
  it('includes unread notifications and skips read ones', () => {
    const unread = makeNotification({ id: 'n1', lue: false });
    const read = makeNotification({ id: 'n2', lue: true });
    const rows = buildFeedRows([], [], [unread, read]);
    expect(rows.find((r) => r.id === 'notif-n1')).toBeDefined();
    expect(rows.find((r) => r.id === 'notif-n2')).toBeUndefined();
  });
});

describe('buildFeedRows — sort order', () => {
  it('orders urgent before warning before info', () => {
    const urgent = makeDeadline({ id: 's1', joursRestants: 3 });
    const warning = makeDeadline({ id: 's2', joursRestants: 50 });
    const info = makeDeadline({ id: 's3', joursRestants: 120 });
    // Pass them out of order; expect sorted by urgency.
    const rows = buildFeedRows([info, warning, urgent], [], []);
    expect(rows.map((r) => r.kind)).toEqual(['urgent', 'warning', 'info']);
  });

  it('places a péril monument at the head of the urgent group, before urgent deadlines', () => {
    const urgentDeadline = makeDeadline({ id: 's4', joursRestants: 2 });
    const peril = makeMonument({ id: 'mp', etatConservation: 'peril', completionPercentage: 100 });
    const rows = buildFeedRows([urgentDeadline], [peril], []);
    expect(rows[0].id).toBe('peril-mp');
    expect(rows[1].id).toBe('deadline-s4');
  });

  it('orders deadlines of the same kind by joursRestants ascending', () => {
    const far = makeDeadline({ id: 'f', joursRestants: 6 });
    const near = makeDeadline({ id: 'n', joursRestants: 1 });
    const rows = buildFeedRows([far, near], [], []);
    expect(rows.map((r) => r.id)).toEqual(['deadline-n', 'deadline-f']);
  });
});

describe('buildFeedRows — no display cap', () => {
  it('returns every deadline without truncation (toutes les échéances < 100 j sont affichées)', () => {
    const deadlines = Array.from({ length: 9 }, (_, i) =>
      makeDeadline({ id: `d${i}`, joursRestants: i + 1 })
    );
    const rows = buildFeedRows(deadlines, [], []);
    expect(rows.filter((r) => r.id.startsWith('deadline-'))).toHaveLength(9);
  });
});
