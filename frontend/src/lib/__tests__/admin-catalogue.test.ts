import { describe, expect, it } from 'vitest';
import {
  faitEffectif,
  filtrerAides,
  filtrerFaits,
  normaliser,
  payloadSurcharge,
} from '@/lib/admin-catalogue';
import type { AdminAide, AdminFait, OptionSurchargee } from '@/types/admin.types';

function aide(over: Partial<AdminAide> = {}): AdminAide {
  return {
    slug: 'drac-monuments-historiques',
    nom: 'Subvention DRAC — Église classée',
    organisme: 'DRAC Île-de-France',
    categorie: 'etat_drac',
    regions: [],
    engineReady: true,
    disponibilite: 'maintenant',
    retiree: false,
    motif: null,
    retireeLe: null,
    ...over,
  };
}

function option(id: string, label: string, unknown = false): OptionSurchargee {
  return { id, label, unknown };
}

function fait(over: Partial<AdminFait> = {}): AdminFait {
  return {
    key: 'usage_du_bien',
    type: 'enum',
    scope: 'monument',
    pending: false,
    nbAides: 3,
    original: {
      question: 'Quel est l’usage du bien ?',
      help: 'Son usage principal aujourd’hui.',
      options: [option('culte', 'Lieu de culte'), option('musee', 'Musée')],
    },
    surcharge: null,
    impactParOption: { factKey: 'usage_du_bien', parOption: [], supprimees: [] },
    ...over,
  };
}

describe('normaliser', () => {
  it('efface les accents et la casse', () => {
    expect(normaliser('  Église CLASSÉE ')).toBe('eglise classee');
  });
});

describe('filtrerAides', () => {
  it('cherche sur le nom sans se soucier des accents ni de la casse', () => {
    expect(filtrerAides([aide()], 'eglise')).toHaveLength(1);
    expect(filtrerAides([aide()], 'ÉGLISE')).toHaveLength(1);
  });

  it('cherche aussi sur le slug et sur l’organisme', () => {
    expect(filtrerAides([aide()], 'drac-monuments')).toHaveLength(1);
    expect(filtrerAides([aide()], 'ile-de-france')).toHaveLength(1);
  });

  it('rend tout quand la recherche est vide', () => {
    const liste = [aide(), aide({ slug: 'autre' })];
    expect(filtrerAides(liste, '   ')).toBe(liste);
  });

  it('ne rend rien sur une recherche sans correspondance', () => {
    expect(filtrerAides([aide()], 'toiture')).toEqual([]);
  });
});

describe('faitEffectif', () => {
  it('rend le YAML quand rien n’est surchargé', () => {
    expect(faitEffectif(fait())).toEqual(fait().original);
  });

  it('superpose champ par champ : un nul garde le YAML', () => {
    const effectif = faitEffectif(
      fait({ surcharge: { question: 'Reformulée ?', help: null, options: null } }),
    );
    expect(effectif.question).toBe('Reformulée ?');
    expect(effectif.help).toBe('Son usage principal aujourd’hui.');
    expect(effectif.options).toEqual(fait().original.options);
  });

  it('remplace la liste entière des réponses, sans fusion', () => {
    const effectif = faitEffectif(
      fait({
        surcharge: { question: null, help: null, options: [option('culte', 'Église')] },
      }),
    );
    expect(effectif.options).toEqual([option('culte', 'Église')]);
  });
});

describe('filtrerFaits', () => {
  it('cherche sur la clé, la question effective et les libellés', () => {
    expect(filtrerFaits([fait()], 'usage_du')).toHaveLength(1);
    expect(filtrerFaits([fait()], 'musee')).toHaveLength(1);
  });

  it('cherche la question SURCHARGÉE, celle qui est réellement posée', () => {
    const surcharge = fait({
      surcharge: { question: 'Le bien accueille-t-il du public ?', help: null, options: null },
    });
    expect(filtrerFaits([surcharge], 'accueille')).toHaveLength(1);
    expect(filtrerFaits([surcharge], 'quel est l’usage')).toEqual([]);
  });
});

describe('payloadSurcharge', () => {
  const original = fait();

  it('rend null quand le brouillon recopie le YAML', () => {
    expect(
      payloadSurcharge(original, {
        question: original.original.question,
        help: original.original.help ?? '',
        options: original.original.options,
      }),
    ).toBeNull();
  });

  it('ignore les espaces de bord', () => {
    expect(
      payloadSurcharge(original, {
        question: `  ${original.original.question}  `,
        help: `  ${original.original.help}  `,
        options: original.original.options,
      }),
    ).toBeNull();
  });

  it('ne garde que ce qui diffère', () => {
    const payload = payloadSurcharge(original, {
      question: 'Reformulée ?',
      help: original.original.help ?? '',
      options: original.original.options,
    });
    expect(payload).toEqual({ question: 'Reformulée ?', help: null, options: null });
  });

  it('traite une aide contextuelle vidée comme une différence', () => {
    const payload = payloadSurcharge(original, {
      question: original.original.question,
      help: '',
      options: original.original.options,
    });
    expect(payload).toEqual({ question: null, help: '', options: null });
  });

  it('détecte un libellé renommé, un ordre changé et une réponse ajoutée', () => {
    const renomme = payloadSurcharge(original, {
      question: original.original.question,
      help: original.original.help ?? '',
      options: [option('culte', 'Église ou chapelle'), option('musee', 'Musée')],
    });
    expect(renomme?.options).toEqual([option('culte', 'Église ou chapelle'), option('musee', 'Musée')]);

    const inverse = payloadSurcharge(original, {
      question: original.original.question,
      help: original.original.help ?? '',
      options: [option('musee', 'Musée'), option('culte', 'Lieu de culte')],
    });
    expect(inverse?.options).toHaveLength(2);

    const ajoutee = payloadSurcharge(original, {
      question: original.original.question,
      help: original.original.help ?? '',
      options: [...original.original.options, option('ferme', 'Ferme')],
    });
    expect(ajoutee?.options).toHaveLength(3);
  });

  it('compare au YAML et non à la surcharge en place', () => {
    // Revenir au texte d'origine alors qu'une surcharge existe doit rendre
    // null : la page appelle alors DELETE, et la ligne disparaît.
    const surcharge = fait({
      surcharge: { question: 'Reformulée ?', help: null, options: null },
    });
    expect(
      payloadSurcharge(surcharge, {
        question: surcharge.original.question,
        help: surcharge.original.help ?? '',
        options: surcharge.original.options,
      }),
    ).toBeNull();
  });

  it('traite un libellé vidé par l’administrateur comme une différence', () => {
    const payload = payloadSurcharge(original, {
      question: original.original.question,
      help: original.original.help ?? '',
      options: [option('culte', '  '), option('musee', 'Musée')],
    });
    // Le serveur le refusera (422) ; la page, elle, désactive déjà le bouton.
    expect(payload?.options?.[0].label).toBe('');
  });
});

describe('payloadSurcharge sur une question Oui/Non', () => {
  /** Un booléen qui déclare ses réponses : chacune dit la valeur qu'elle envoie
   *  aux prédicats des aides. */
  const booleen = fait({
    key: 'travaux_partie_protegee',
    type: 'boolean',
    original: {
      question: 'Les travaux portent-ils sur la partie protégée ?',
      help: null,
      options: [
        { id: 'oui', label: 'Oui', unknown: false, valeur: true },
        { id: 'non', label: 'Non', unknown: false, valeur: false },
        { id: 'les_deux', label: 'Les deux', unknown: false, valeur: true },
      ],
    },
  });

  const brouillonDe = (options: OptionSurchargee[]) => ({
    question: booleen.original.question,
    help: '',
    options,
  });

  it('rend un payload quand SEULE une valeur change', () => {
    // Le bug silencieux le plus coûteux du lot : sans `valeur` dans la
    // comparaison, la page appellerait DELETE et la modification disparaîtrait.
    const payload = payloadSurcharge(
      booleen,
      brouillonDe([
        { id: 'oui', label: 'Oui', unknown: false, valeur: true },
        { id: 'non', label: 'Non', unknown: false, valeur: false },
        { id: 'les_deux', label: 'Les deux', unknown: false, valeur: null },
      ]),
    );
    expect(payload?.options?.[2].valeur).toBeNull();
  });

  it('rend null quand le brouillon reprend l’original, valeurs comprises', () => {
    expect(payloadSurcharge(booleen, brouillonDe(booleen.original.options))).toBeNull();
  });

  it('ne voit pas de différence entre une valeur absente et null sur un enum', () => {
    // `undefined !== null` ferait apparaître une surcharge inutile sur TOUS les
    // enums, dont les réponses n'ont pas de `valeur`.
    const enumerable = fait();
    const avecNull: OptionSurchargee[] = enumerable.original.options.map((o) => ({
      ...o,
      valeur: null,
    }));
    expect(
      payloadSurcharge(enumerable, {
        question: enumerable.original.question,
        help: enumerable.original.help ?? '',
        options: avecNull,
      }),
    ).toBeNull();
  });
});
