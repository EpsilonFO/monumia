import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { Loader2 } from 'lucide-react';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { useAuthStore } from '@/stores/useAuthStore';
import { usePendingOAuthStore } from '@/stores/usePendingOAuthStore';
import { authService } from '@/services/auth.service';
import { parseOAuthCallbackHash } from '@/lib/oauth-callback';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';

const MUTED = 'var(--muted-foreground)';

const ERROR_MESSAGE =
  'La connexion avec Google n’a pas abouti. Vous pouvez réessayer, ou vous connecter avec votre adresse email.';

/**
 * Atterrissage du flux « Continuer avec Google ». Supabase redirige ici avec
 * les jetons dans le fragment d'URL. On demande au backend si le profil
 * applicatif existe déjà : oui → connexion directe ; non → onboarding
 * (les jetons attendent en mémoire dans usePendingOAuthStore).
 */
export function AuthCallbackPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const setPendingSession = usePendingOAuthStore((s) => s.setSession);
  const [error, setError] = useState<string | null>(null);
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return; // garde StrictMode : l'effet ne doit tourner qu'une fois
    ranRef.current = true;

    const parsed = parseOAuthCallbackHash(window.location.hash);
    // Nettoie l'URL pour ne pas laisser traîner les jetons.
    window.history.replaceState(null, '', window.location.pathname);

    if (parsed.status === 'error') {
      setError(ERROR_MESSAGE);
      return;
    }

    authService
      .oauthProfileStatus(parsed.accessToken)
      .then(async (status) => {
        if (status.exists && status.user) {
          // Le refresh token du hash part en cookie httpOnly avant d'entrer
          // dans l'app. Échec non bloquant : la session reste valable jusqu'à
          // expiration de l'access token.
          if (parsed.refreshToken) {
            await authService.oauthSession(parsed.accessToken, parsed.refreshToken).catch(() => {});
          }
          setAuth(status.user, parsed.accessToken);
          navigate(
            status.user.accountType === 'collaborateur' ? ROUTES.PROJETS : '/app',
            { replace: true },
          );
        } else {
          setPendingSession({
            accessToken: parsed.accessToken,
            refreshToken: parsed.refreshToken,
            email: status.prefill?.email ?? '',
            prenom: status.prefill?.prenom ?? '',
            nom: status.prefill?.nom ?? '',
          });
          navigate('/onboarding', { replace: true });
        }
      })
      .catch((err: unknown) => { console.error(err); setError(ERROR_MESSAGE); });
  }, [navigate, setAuth, setPendingSession]);

  return (
    <AuthLayout>
      <div className="space-y-2.5">
        <h1
          className="text-[clamp(1.9rem,4vw,2.5rem)] leading-[1.1]"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          Connexion avec <span style={{ color: C.blue }}>Google</span>
        </h1>
        <p className="text-[15px]" style={{ color: MUTED }}>
          {error ? 'La connexion ne s’est pas terminée.' : 'Un instant, nous vous connectons…'}
        </p>
      </div>

      {error ? (
        <div className="space-y-4">
          <div className="rounded-xl p-4 text-[14px]" style={{ background: C.paleDanger, color: C.danger }}>
            {error}
          </div>
          <button
            onClick={() => navigate('/login')}
            className="flex h-12 w-full items-center justify-center rounded-lg text-[14px] font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: C.orange }}
          >
            Retour à la connexion
          </button>
        </div>
      ) : (
        <div
          className="flex items-center justify-center gap-3 rounded-xl p-6 text-[15px]"
          style={{ background: C.paleBlue, color: C.ink }}
        >
          <Loader2 className="h-5 w-5 animate-spin" style={{ color: C.blue }} />
          Connexion en cours…
        </div>
      )}
    </AuthLayout>
  );
}
