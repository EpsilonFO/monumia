// Parse le fragment d'URL renvoyé par Supabase après un login OAuth ou un clic
// dans un lien d'email (#access_token=…&refresh_token=…&type=signup). Même
// mécanique que ResetPasswordPage : le client supabase-js est configuré avec
// detectSessionInUrl=false, donc le parsing est manuel et les jetons ne
// touchent jamais le localStorage.
export type OAuthCallbackResult =
  /** `type` distingue le retour Google (vide) du clic dans un lien d'email
   *  (`signup`, `invite`, `recovery`…). L'écran d'atterrissage en a besoin :
   *  parler de Google à qui vient de confirmer son adresse le perdrait. */
  | { status: 'ok'; accessToken: string; refreshToken: string; type: string }
  /** `code` porte `error_code` quand Supabase en donne un. Le seul qui change
   *  quelque chose est `otp_expired` : un lien périmé se re-demande, il ne se
   *  réessaie pas. */
  | { status: 'error'; message: string; code: string };

export function parseOAuthCallbackHash(hash: string): OAuthCallbackResult {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  const params = new URLSearchParams(raw);

  const providerError = params.get('error_description') || params.get('error');
  if (providerError) {
    return {
      status: 'error',
      message: providerError,
      code: params.get('error_code') ?? params.get('error') ?? '',
    };
  }

  const accessToken = params.get('access_token');
  if (!accessToken) return { status: 'error', message: 'missing_tokens', code: 'missing_tokens' };

  return {
    status: 'ok',
    accessToken,
    refreshToken: params.get('refresh_token') ?? '',
    type: params.get('type') ?? '',
  };
}
