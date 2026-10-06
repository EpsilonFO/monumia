import { describe, expect, it } from 'vitest';
import { blocsTexteAide, longueurTexteAide } from '../texte-aide';

describe('blocsTexteAide', () => {
  it('un texte replié par YAML reste un paragraphe', () => {
    expect(blocsTexteAide('Une phrase. Une autre.')).toEqual([
      { type: 'p', texte: 'Une phrase. Une autre.' },
    ]);
  });

  it('une ligne vide fait un paragraphe, « - » fait une puce', () => {
    const texte = [
      "L'architecture romane date des XIe et XIIe siècles. On la reconnaît à :",
      '- des arcs en plein cintre ;',
      '- des voûtes',
      '  en berceau.',
      '',
      'Un élément réemployé suffit.',
    ].join('\n');
    expect(blocsTexteAide(texte)).toEqual([
      { type: 'p', texte: "L'architecture romane date des XIe et XIIe siècles. On la reconnaît à :" },
      { type: 'ul', puces: ['des arcs en plein cintre ;', 'des voûtes en berceau.'] },
      { type: 'p', texte: 'Un élément réemployé suffit.' },
    ]);
  });

  it('les lignes coupées d’un paragraphe se recollent', () => {
    expect(blocsTexteAide('Début de\nla phrase.')).toEqual([{ type: 'p', texte: 'Début de la phrase.' }]);
  });

  it('rien ou du blanc : aucun bloc', () => {
    expect(blocsTexteAide(null)).toEqual([]);
    expect(blocsTexteAide('  \n\n ')).toEqual([]);
  });

  it('mesure le texte lu, sans les tirets ni les retours', () => {
    expect(longueurTexteAide('Ab\n- cd\n- ef')).toBe('Ab'.length + 'cd ef'.length);
  });
});
