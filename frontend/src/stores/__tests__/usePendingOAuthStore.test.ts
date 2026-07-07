import { describe, it, expect, beforeEach } from 'vitest';
import { usePendingOAuthStore } from '../usePendingOAuthStore';

const SESSION = {
  accessToken: 'jwt-access',
  refreshToken: 'jwt-refresh',
  email: 'marie@exemple.fr',
  prenom: 'Marie',
  nom: 'Dupont',
};

describe('usePendingOAuthStore', () => {
  beforeEach(() => {
    usePendingOAuthStore.getState().clear();
  });

  it('est vide par défaut', () => {
    expect(usePendingOAuthStore.getState().has()).toBe(false);
    expect(usePendingOAuthStore.getState().accessToken).toBeNull();
  });

  it('stocke la session OAuth en attente', () => {
    usePendingOAuthStore.getState().setSession(SESSION);
    const s = usePendingOAuthStore.getState();
    expect(s.has()).toBe(true);
    expect(s.accessToken).toBe('jwt-access');
    expect(s.prenom).toBe('Marie');
  });

  it('clear() remet tout à null', () => {
    usePendingOAuthStore.getState().setSession(SESSION);
    usePendingOAuthStore.getState().clear();
    const s = usePendingOAuthStore.getState();
    expect(s.has()).toBe(false);
    expect(s.refreshToken).toBeNull();
    expect(s.email).toBeNull();
  });
});
