// Parse le fragment d'URL renvoyé par Supabase après un login OAuth
// (#access_token=…&refresh_token=…). Même mécanique que ResetPasswordPage :
// le client supabase-js est configuré avec detectSessionInUrl=false, donc le
// parsing est manuel et les jetons ne touchent jamais le localStorage.
export type OAuthCallbackResult =
  | { status: 'ok'; accessToken: string; refreshToken: string }
  | { status: 'error'; message: string };

export function parseOAuthCallbackHash(hash: string): OAuthCallbackResult {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  const params = new URLSearchParams(raw);

  const providerError = params.get('error_description') || params.get('error');
  if (providerError) return { status: 'error', message: providerError };

  const accessToken = params.get('access_token');
  if (!accessToken) return { status: 'error', message: 'missing_tokens' };

  return { status: 'ok', accessToken, refreshToken: params.get('refresh_token') ?? '' };
}
