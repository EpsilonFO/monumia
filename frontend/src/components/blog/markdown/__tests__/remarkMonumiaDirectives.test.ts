import { describe, it, expect } from 'vitest';
import remarkMonumiaDirectives from '../remarkMonumiaDirectives';

/** Helpers de construction de nœuds mdast minimalistes. */
const text = (value: string) => ({ type: 'text', value });
const strong = (value: string) => ({ type: 'strong', children: [text(value)] });
const para = (...children: any[]) => ({ type: 'paragraph', children });
const li = (...children: any[]) => ({ type: 'listItem', children });
const list = (ordered: boolean, ...items: any[]) => ({
  type: 'list',
  ordered,
  children: items,
});
const directive = (name: string, children: any[], attributes: any = {}) => ({
  type: 'containerDirective',
  name,
  attributes,
  children,
});

function run(node: any) {
  const tree = { type: 'root', children: [node] };
  remarkMonumiaDirectives()(tree);
  return node;
}

describe('remarkMonumiaDirectives', () => {
  it('callout : pose hName/variant et extrait le titre du label', () => {
    const labelPara = { ...para(text('Ne vous trompez pas')), data: { directiveLabel: true } };
    const node = run(directive('attention', [labelPara, para(text('Contenu.'))]));
    expect(node.data.hName).toBe('mon-callout');
    expect(node.data.hProperties).toEqual({ variant: 'attention', title: 'Ne vous trompez pas' });
    // le label est retiré des enfants, le contenu reste
    expect(node.children).toHaveLength(1);
    expect(node.children[0].children[0].value).toBe('Contenu.');
  });

  it('callout sans label : titre vide', () => {
    const node = run(directive('remarque', [para(text('Juste un texte.'))]));
    expect(node.data.hProperties.variant).toBe('remarque');
    expect(node.data.hProperties.title).toBe('');
  });

  it('chiffres : extrait value (strong) et label', () => {
    const node = run(
      directive('chiffres', [
        list(
          false,
          li(para(strong('20 %'), text(' — aide pour un bien inscrit'))),
          li(para(strong('35 %'), text(' — aide pour un bien classé'))),
        ),
      ]),
    );
    expect(node.data.hName).toBe('mon-keyfigures');
    expect(JSON.parse(node.data.hProperties.data)).toEqual([
      { value: '20 %', label: 'aide pour un bien inscrit' },
      { value: '35 %', label: 'aide pour un bien classé' },
    ]);
    expect(node.children).toHaveLength(0);
  });

  it('barres : parse "label: nombre" et l\'unité', () => {
    const node = run(
      directive(
        'barres',
        [list(false, li(para(text('Inscrit: 20'))), li(para(text('Classé: 35'))))],
        { unit: '%' },
      ),
    );
    expect(node.data.hName).toBe('mon-barchart');
    expect(node.data.hProperties.unit).toBe('%');
    expect(JSON.parse(node.data.hProperties.data)).toEqual([
      { label: 'Inscrit', value: 20 },
      { label: 'Classé', value: 35 },
    ]);
  });

  it('comparatif : lignes alignées séparées par | + titres de colonnes', () => {
    const node = run(
      directive(
        'comparatif',
        [
          list(
            false,
            li(para(text('Niveau | Premier niveau | Le plus élevé'))),
            li(para(text('Autorisation | Déclaration préalable | Préfet'))),
          ),
        ],
        { a: 'Bien inscrit', b: 'Bien classé' },
      ),
    );
    expect(node.data.hName).toBe('mon-comparison');
    expect(node.data.hProperties.cola).toBe('Bien inscrit');
    expect(node.data.hProperties.colb).toBe('Bien classé');
    expect(JSON.parse(node.data.hProperties.data)).toEqual([
      { aspect: 'Niveau', a: 'Premier niveau', b: 'Le plus élevé' },
      { aspect: 'Autorisation', a: 'Déclaration préalable', b: 'Préfet' },
    ]);
  });

  it('etapes : titre (strong) + description', () => {
    const node = run(
      directive('etapes', [
        list(
          true,
          li(para(strong('Contacter la DRAC'), text(' — en amont du projet.'))),
          li(para(strong('Déposer le dossier'), text(' — avec les pièces requises.'))),
        ),
      ]),
    );
    expect(node.data.hName).toBe('mon-steps');
    expect(JSON.parse(node.data.hProperties.data)).toEqual([
      { title: 'Contacter la DRAC', description: 'en amont du projet.' },
      { title: 'Déposer le dossier', description: 'avec les pièces requises.' },
    ]);
  });

  it('figure : caption depuis le label', () => {
    const labelPara = { ...para(text('Schéma des niveaux')), data: { directiveLabel: true } };
    const node = run(directive('figure', [labelPara, para(text('contenu'))]));
    expect(node.data.hName).toBe('mon-figure');
    expect(node.data.hProperties.caption).toBe('Schéma des niveaux');
  });

  it('directive inconnue : laissée intacte', () => {
    const node = run(directive('inconnue', [para(text('x'))]));
    expect(node.data?.hName).toBeUndefined();
  });

  it('etapes : display par défaut = frise', () => {
    const node = run(directive('etapes', [list(true, li(para(strong('A'), text(' — x'))))]));
    expect(node.data.hProperties.display).toBe('frise');
  });

  it('etapes : display repris de l\'attribut', () => {
    const node = run(
      directive('etapes', [list(true, li(para(strong('A'), text(' — x'))))], { display: 'colonnes' }),
    );
    expect(node.data.hProperties.display).toBe('colonnes');
  });

  it('chiffres : display par défaut = cartes', () => {
    const node = run(directive('chiffres', [list(false, li(para(strong('35 %'), text(' — base'))))]));
    expect(node.data.hProperties.display).toBe('cartes');
  });

  it('comparatif : display par défaut = tableau', () => {
    const node = run(
      directive('comparatif', [list(false, li(para(text('A | x | y'))))], { a: 'A', b: 'B' }),
    );
    expect(node.data.hProperties.display).toBe('tableau');
  });

  it('frise : date (strong) + événement', () => {
    const node = run(
      directive('frise', [
        list(
          false,
          li(para(strong('1840'), text(' — première loi de protection'))),
          li(para(strong('1913'), text(' — loi sur les monuments historiques'))),
        ),
      ]),
    );
    expect(node.data.hName).toBe('mon-timeline');
    expect(JSON.parse(node.data.hProperties.data)).toEqual([
      { date: '1840', event: 'première loi de protection' },
      { date: '1913', event: 'loi sur les monuments historiques' },
    ]);
  });

  it('decision : question + branches oui/non', () => {
    const labelPara = { ...para(text('Suis-je concerné ?')), data: { directiveLabel: true } };
    const node = run(
      directive('decision', [
        labelPara,
        list(
          false,
          li(para(text('Bien protégé ? | oui: relevez de la DRAC | non: voyez la mairie'))),
        ),
      ]),
    );
    expect(node.data.hName).toBe('mon-decision');
    expect(node.data.hProperties.title).toBe('Suis-je concerné ?');
    expect(JSON.parse(node.data.hProperties.data)).toEqual([
      { q: 'Bien protégé ?', yes: 'relevez de la DRAC', no: 'voyez la mairie' },
    ]);
  });

  it('citation : source depuis le label, enfants conservés', () => {
    const labelPara = { ...para(text('Code du patrimoine, art. L621-1')), data: { directiveLabel: true } };
    const node = run(directive('citation', [labelPara, para(text('Sont considérés…'))]));
    expect(node.data.hName).toBe('mon-quote');
    expect(node.data.hProperties.source).toBe('Code du patrimoine, art. L621-1');
    expect(node.children).toHaveLength(1);
  });

  it('checklist : items en texte + titre', () => {
    const labelPara = { ...para(text('À préparer')), data: { directiveLabel: true } };
    const node = run(
      directive('checklist', [
        labelPara,
        list(false, li(para(text('Le devis des travaux'))), li(para(text('L’arrêté de protection')))),
      ]),
    );
    expect(node.data.hName).toBe('mon-checklist');
    expect(node.data.hProperties.title).toBe('À préparer');
    expect(JSON.parse(node.data.hProperties.data)).toEqual([
      'Le devis des travaux',
      'L’arrêté de protection',
    ]);
  });

  it('cout : libellé + montant, unité par défaut €', () => {
    const node = run(
      directive('cout', [
        list(false, li(para(text('Étude préalable: 8000'))), li(para(text('Travaux: 90000')))),
      ]),
    );
    expect(node.data.hName).toBe('mon-cost');
    expect(node.data.hProperties.unit).toBe('€');
    expect(JSON.parse(node.data.hProperties.data)).toEqual([
      { label: 'Étude préalable', value: 8000 },
      { label: 'Travaux', value: 90000 },
    ]);
  });

  it('exergue : valeur depuis le label, enfants conservés', () => {
    const labelPara = { ...para(text('35 %')), data: { directiveLabel: true } };
    const node = run(directive('exergue', [labelPara, para(text('des travaux pris en charge.'))]));
    expect(node.data.hName).toBe('mon-pullstat');
    expect(node.data.hProperties.value).toBe('35 %');
    expect(node.children).toHaveLength(1);
  });
});
