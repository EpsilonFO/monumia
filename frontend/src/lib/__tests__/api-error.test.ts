import { describe, it, expect } from 'vitest';
import { ApiError, isAccessLostError } from '../api-error';

describe('ApiError', () => {
  it('conserve le statut et le message', () => {
    const err = new ApiError(404, 'Projet introuvable ou accès refusé');
    expect(err).toBeInstanceOf(Error);
    expect(err.status).toBe(404);
    expect(err.message).toBe('Projet introuvable ou accès refusé');
  });
});

describe('isAccessLostError', () => {
  it('détecte une perte d’accès définitive sur 403 et 404', () => {
    expect(isAccessLostError(new ApiError(404, 'Projet introuvable'))).toBe(true);
    expect(isAccessLostError(new ApiError(403, 'Action non autorisée'))).toBe(true);
  });

  it('ignore les erreurs transitoires', () => {
    expect(isAccessLostError(new ApiError(500, 'Server error'))).toBe(false);
    expect(isAccessLostError(new ApiError(0, 'Network error'))).toBe(false);
  });

  it('ignore une erreur sans information de statut', () => {
    expect(isAccessLostError(new Error('HTTP 404'))).toBe(false);
    expect(isAccessLostError(undefined)).toBe(false);
    expect(isAccessLostError(null)).toBe(false);
  });
});
