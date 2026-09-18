import { afterEach, describe, expect, it, vi } from 'vitest';
import { contexteYbug, idProjetYbug } from '@/lib/ybug';
import type { User } from '@/types';

const UTILISATEUR: User = {
  id: 'u-1',
  email: 'testeur@exemple.fr',
  prenom: 'Camille',
  nom: 'Durand',
  onboardingComplete: true,
  notificationPreferences: {
    urgentDeadlines: true,
    newAidesMatched: true,
    dossierUpdates: true,
    emailNotifications: true,
  },
  createdAt: '2026-09-01T00:00:00Z',
};

describe('idProjetYbug', () => {
  afterEach(() => vi.unstubAllEnvs());

  it("rend undefined sans variable — le widget ne se charge pas", () => {
    vi.stubEnv('VITE_YBUG_ID', '');
    expect(idProjetYbug()).toBeUndefined();
  });

  it('ignore une valeur qui n’est que des espaces', () => {
    vi.stubEnv('VITE_YBUG_ID', '   ');
    expect(idProjetYbug()).toBeUndefined();
  });

  it('rend l’identifiant nettoyé', () => {
    vi.stubEnv('VITE_YBUG_ID', ' abc123 ');
    expect(idProjetYbug()).toBe('abc123');
  });
});

describe('contexteYbug', () => {
  it('rend un visiteur anonyme hors session', () => {
    // `id: null` et pas un objet vide : sinon Ybug garderait le dernier
    // utilisateur identifié après une déconnexion.
    expect(contexteYbug(null, ['veille'])).toEqual({ id: null });
  });

  it('joint identité, email et offres', () => {
    expect(contexteYbug(UTILISATEUR, ['veille', 'multi_monuments'])).toEqual({
      id: 'u-1',
      username: 'Camille Durand',
      email: 'testeur@exemple.fr',
      offres: 'veille, multi_monuments',
      admin: false,
    });
  });

  it('dit « gratuit » sur une liste vide, et rien tant que les droits n’ont pas répondu', () => {
    expect(contexteYbug(UTILISATEUR, []).offres).toBe('gratuit');
    expect(contexteYbug(UTILISATEUR, undefined)).not.toHaveProperty('offres');
  });

  it('retombe sur l’email si le nom est vide', () => {
    const anonyme = { ...UTILISATEUR, prenom: '', nom: '' };
    expect(contexteYbug(anonyme, undefined).username).toBe('testeur@exemple.fr');
  });

  it('signale un compte administrateur', () => {
    expect(contexteYbug({ ...UTILISATEUR, estAdmin: true }, undefined).admin).toBe(true);
  });
});
