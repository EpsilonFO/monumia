import { describe, it, expect } from 'vitest';
import { parseOAuthCallbackHash } from '../oauth-callback';

describe('parseOAuthCallbackHash', () => {
  it('extrait les jetons du hash Supabase', () => {
    const result = parseOAuthCallbackHash(
      '#access_token=jwt-a&refresh_token=jwt-r&token_type=bearer',
    );
    expect(result).toEqual({ status: 'ok', accessToken: 'jwt-a', refreshToken: 'jwt-r', type: '' });
  });

  it('accepte un hash sans préfixe #', () => {
    const result = parseOAuthCallbackHash('access_token=jwt-a&refresh_token=jwt-r');
    expect(result.status).toBe('ok');
  });

  it('signale une erreur du provider (error_description)', () => {
    const result = parseOAuthCallbackHash(
      '#error=access_denied&error_description=User+refused',
    );
    expect(result).toEqual({ status: 'error', message: 'User refused', code: 'access_denied' });
  });

  it('signale une erreur sans description (error seul)', () => {
    const result = parseOAuthCallbackHash('#error=server_error');
    expect(result).toEqual({ status: 'error', message: 'server_error', code: 'server_error' });
  });

  it('signale un hash sans jetons (accès direct à la page)', () => {
    const result = parseOAuthCallbackHash('');
    expect(result.status).toBe('error');
  });

  it('rend le type du lien d’email, qui distingue le retour Google', () => {
    const result = parseOAuthCallbackHash('#access_token=jwt-a&refresh_token=jwt-r&type=signup');
    expect(result).toMatchObject({ status: 'ok', type: 'signup' });
  });

  it('rend error_code, seul moyen de reconnaître un lien périmé', () => {
    const result = parseOAuthCallbackHash(
      '#error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired',
    );
    expect(result).toMatchObject({ status: 'error', code: 'otp_expired' });
  });

  it('tolère un refresh_token absent', () => {
    const result = parseOAuthCallbackHash('#access_token=jwt-a');
    expect(result).toEqual({ status: 'ok', accessToken: 'jwt-a', refreshToken: '', type: '' });
  });
});
