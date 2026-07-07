import { describe, expect, it } from 'vitest';
import { projectsDataReady, type ProjectsDataReadyInput } from '../projects-data-ready';

/** Entrée « tout est prêt » pour deux monuments — chaque test dégrade un axe. */
function readyInput(): ProjectsDataReadyInput {
  return {
    monumentsSettled: true,
    dossiersSettled: true,
    monumentIds: ['m1', 'm2'],
    diagnostics: { m1: { aides: [] }, m2: { aides: [] } },
    settledDiags: {},
    loadedSuivis: { m1: true, m2: true },
    settledSuivis: {},
  };
}

describe('projectsDataReady', () => {
  it('est prêt quand monuments, dossiers, diagnostics et suivis sont tous là', () => {
    expect(projectsDataReady(readyInput())).toBe(true);
  });

  it('attend la liste des monuments', () => {
    expect(projectsDataReady({ ...readyInput(), monumentsSettled: false })).toBe(false);
  });

  it('attend les dossiers', () => {
    expect(projectsDataReady({ ...readyInput(), dossiersSettled: false })).toBe(false);
  });

  it('attend le diagnostic d’aides de chaque monument', () => {
    const input = readyInput();
    input.diagnostics = { m1: { aides: [] } }; // m2 pas encore diagnostiqué
    expect(projectsDataReady(input)).toBe(false);
  });

  it('attend les suivis de chaque monument', () => {
    const input = readyInput();
    input.loadedSuivis = { m1: true }; // suivis de m2 pas encore chargés
    expect(projectsDataReady(input)).toBe(false);
  });

  it('un diagnostic en échec compte comme réglé — carte dégradée plutôt que squelette éternel', () => {
    const input = readyInput();
    input.diagnostics = { m1: { aides: [] } };
    input.settledDiags = { m2: true }; // l'appel de m2 a échoué mais est terminé
    expect(projectsDataReady(input)).toBe(true);
  });

  it('un chargement de suivis en échec compte comme réglé', () => {
    const input = readyInput();
    input.loadedSuivis = { m1: true };
    input.settledSuivis = { m2: true };
    expect(projectsDataReady(input)).toBe(true);
  });

  it('sans aucun monument, prêt dès que la liste est arrivée', () => {
    const input = { ...readyInput(), monumentIds: [], diagnostics: {}, loadedSuivis: {} };
    expect(projectsDataReady(input)).toBe(true);
  });
});
