import { describe, expect, it } from 'vitest';
import { resolveLegacyProjetId } from '@/lib/legacy-id';

describe('resolveLegacyProjetId', () => {
  it('un id qui répond comme projet est un projet', () => {
    expect(resolveLegacyProjetId(true, false)).toEqual({ kind: 'projet' });
  });

  it('le projet prime, même si un monument porte le même id', () => {
    // Cas théorique (deux espaces d'UUID distincts), mais la règle doit être
    // explicite : `/app/projets/:id` désigne aujourd'hui un projet.
    expect(resolveLegacyProjetId(true, true)).toEqual({ kind: 'projet' });
  });

  it('un id inconnu comme projet mais connu comme monument est un vieux lien', () => {
    expect(resolveLegacyProjetId(false, true)).toEqual({ kind: 'monument' });
  });

  it('un id inconnu des deux côtés est introuvable — pas de redirection au hasard', () => {
    expect(resolveLegacyProjetId(false, false)).toEqual({ kind: 'introuvable' });
  });
});
