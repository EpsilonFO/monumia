import { describe, expect, it } from 'vitest';
import { normalize, scoreTemplate, matchTemplates } from '@/lib/template-matching';
import type { Template } from '@/types';

function makeTemplate(partial: Partial<Template> & { id: string }): Template {
  return {
    slug: partial.id,
    nom: '',
    typeDocument: 'autre',
    tags: [],
    categoriesAide: [],
    fichierUrl: `${partial.id}.md`,
    nomFichier: `${partial.id}.md`,
    ...partial,
  };
}

const planFinancement = makeTemplate({
  id: 'plan',
  nom: 'Plan de financement prévisionnel',
  typeDocument: 'plan_financement',
  tags: ['plan', 'financement', 'previsionnel', 'budget'],
});
const devis = makeTemplate({
  id: 'devis',
  nom: 'Cadre de devis détaillé',
  typeDocument: 'devis',
  tags: ['devis', 'travaux', 'estimation'],
});
const deliberation = makeTemplate({
  id: 'delib',
  nom: 'Délibération du conseil municipal',
  typeDocument: 'deliberation',
  tags: ['deliberation', 'conseil', 'municipal', 'commune'],
  categoriesAide: ['etat_drac', 'region'],
});

const LIBRARY = [planFinancement, devis, deliberation];

describe('normalize', () => {
  it('lowercases, strips accents, drops stopwords and short tokens', () => {
    expect(normalize('Plan de financement prévisionnel')).toEqual([
      'plan',
      'financement',
      'previsionnel',
    ]);
  });

  it('splits snake_case type keys into tokens', () => {
    expect(normalize('plan_financement')).toEqual(['plan', 'financement']);
  });

  it('returns an empty list for stopword-only / punctuation input', () => {
    expect(normalize("de l' et des")).toEqual([]);
    expect(normalize('—  ,')).toEqual([]);
  });
});

describe('scoreTemplate', () => {
  it('scores on meaningful token overlap', () => {
    expect(scoreTemplate(planFinancement, 'Plan de financement prévisionnel')).toBeGreaterThan(0);
  });

  it('does not match on stopwords alone', () => {
    // "Photos de l'état actuel" shares only stopwords with the plan template.
    expect(scoreTemplate(planFinancement, "Photos de l'état actuel")).toBe(0);
  });

  it('gives a category bonus when the aide category is targeted', () => {
    const withCat = scoreTemplate(deliberation, 'Délibération du conseil municipal', 'etat_drac');
    const withoutCat = scoreTemplate(deliberation, 'Délibération du conseil municipal');
    expect(withCat).toBeGreaterThan(withoutCat);
  });
});

describe('matchTemplates', () => {
  it('returns the relevant template for a checklist label', () => {
    const result = matchTemplates(LIBRARY, 'Devis détaillé des entreprises');
    expect(result.map((t) => t.id)).toEqual(['devis']);
  });

  it('returns an empty array when nothing meaningfully matches', () => {
    expect(matchTemplates(LIBRARY, "Photos de l'état actuel")).toEqual([]);
  });

  it('ranks the best match first and respects the limit', () => {
    const result = matchTemplates(LIBRARY, 'Plan de financement et devis', undefined, 1);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('plan');
  });
});
