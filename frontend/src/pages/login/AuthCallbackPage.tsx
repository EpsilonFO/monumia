import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { Loader2 } from 'lucide-react';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { useAuthStore } from '@/stores/useAuthStore';
import { usePendingOAuthStore } from '@/stores/usePendingOAuthStore';
import { authService } from '@/services/auth.service';
import { parseOAuthCallbackHash } from '@/lib/oauth-callback';
import { takePendingInvitation } from '@/lib/pending-invitation';
import {
  brouillonPretPourRejeu,
  prendreRetourGoogleBrouillon,
} from '@/lib/brouillon-invite';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';

const MUTED = 'var(--muted-foreground)';

const ERROR_MESSAGE =
  'La connexion avec Google n’a pas abouti. Vous pouvez réessayer, ou vous connecter avec votre adresse email.';

/** Un lien de confirmation périmé ne se réessaie pas : il se re-demande. Le
 *  message doit le dire, sinon la personne reclique indéfiniment sur le même
 *  lien mort. */
const EXPIRE_MESSAGE =
  'Ce lien a expiré. Depuis la page de connexion, saisissez vos identifiants : un nouvel email de confirmation vous sera proposé.';

/**
 * Atterrissage du flux « Continuer avec Google », et du lien de CONFIRMATION
 * d'email : les deux arrivent ici avec les jetons dans le fragment d'URL. On demande au backend si le profil
 * applicatif existe déjà : oui → connexion directe ; non → le profil est créé
 * ici même à partir de ce que Google renvoie, puis connexion directe.
 *
 * Aucun écran d'onboarding : l'inscription par email crée le compte d'un seul
 * coup depuis /login, le parcours Google fait de même. Seule exception, le
 * parcours invitation, qui garde son écran parce qu'il lui faut le métier du
 * collaborateur et le rôle sur le projet (les jetons l'attendent alors en
 * mémoire dans usePendingOAuthStore).
 */
/**
 * Ce que l'URL d'arrivée raconte, lu UNE FOIS au premier rendu.
 *
 * Lecture séparée de l'effet, parce que l'effet efface l'URL aussitôt (les
 * jetons ne doivent pas traîner dans la barre d'adresse) : tout ce dont
 * l'écran a besoin doit avoir été extrait avant.
 */
function lireArrivee() {
  const parsed = parseOAuthCallbackHash(window.location.hash);
  // L'intention posée par le serveur dans le lien de confirmation (cf.
  // `_url_retour_confirmation`), et non dans le `sessionStorage` : ce lien
  // s'ouvre presque toujours dans un autre onglet, souvent sur un autre
  // appareil, où rien du parcours n'a survécu.
  const params = new URLSearchParams(window.location.search);
  const invitation = params.get('invitation');
  const reprise = params.get('reprise') === 'brouillon';
  // Arrivée par un lien d'email plutôt que par Google. Deux flux aboutissent
  // sur cet écran, et il ne peut pas tenir le même discours aux deux :
  // « Connexion avec Google » à qui vient de confirmer son adresse est
  // incompréhensible. Sur erreur le fragment ne porte pas de `type` ; restent
  // `otp_expired`, qui ne vient que d'un lien d'email, et nos propres
  // paramètres de requête, qui ont survécu à la redirection.
  const lienEmail =
    (parsed.status === 'ok' && parsed.type !== '') ||
    (parsed.status === 'error' && parsed.code === 'otp_expired') ||
    invitation !== null ||
    reprise;
  return { parsed, invitation, reprise, lienEmail };
}

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const setPendingSession = usePendingOAuthStore((s) => s.setSession);
  const [error, setError] = useState<string | null>(null);
  // Initialiseur paresseux : l'URL est lue au premier rendu, donc avant que
  // l'effet ne la nettoie. Un `setState` dans l'effet aurait provoqué un
  // rendu en cascade pour une valeur qui ne change jamais.
  const [{ parsed, invitation, reprise, lienEmail }] = useState(lireArrivee);
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return; // garde StrictMode : l'effet ne doit tourner qu'une fois
    ranRef.current = true;

    // Nettoie l'URL pour ne pas laisser traîner les jetons.
    window.history.replaceState(null, '', window.location.pathname);

    // Google lancé depuis un lien d'invitation : on rend la main à l'écran
    // d'invitation, qui possède tout le parcours collaborateur (rôle sur le
    // projet, acceptation). Consommé ici même en cas d'erreur, pour ne pas
    // laisser un jeton traîner sur une tentative suivante.
    const pendingInvitation = takePendingInvitation() ?? invitation;

    // Google lancé depuis le parcours découverte : on renverra sur l'écran de
    // reprise, qui crée le monument et le projet du brouillon. Le drapeau est
    // consommé QUOI QU'IL ARRIVE (même sur erreur, même sans brouillon
    // rejouable), pour ne pas détourner une connexion Google ultérieure. Et
    // c'est bien lui qui porte l'intention : un brouillon oublié dans le
    // localStorage ne suffit pas à déclencher un rejeu.
    const retourBrouillon =
      (prendreRetourGoogleBrouillon() || reprise) && brouillonPretPourRejeu();

    if (parsed.status === 'error') {
      setError(parsed.code === 'otp_expired' ? EXPIRE_MESSAGE : ERROR_MESSAGE);
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
          // L'invitation garde la priorité : c'est une action explicite reçue
          // par email, et l'écran d'invitation a son propre parcours.
          navigate(
            pendingInvitation
              ? `/invitation/${pendingInvitation}`
              : retourBrouillon
                ? ROUTES.REPRISE
                : status.user.accountType === 'collaborateur'
                  ? ROUTES.MONUMENTS
                  : '/app',
            { replace: true },
          );
          return;
        }

        // Profil applicatif absent : c'est une première connexion Google.
        if (pendingInvitation) {
          // Le parcours collaborateur crée le compte lui-même, une fois le
          // métier et le rôle connus. On lui passe la main avec les jetons.
          setPendingSession({
            accessToken: parsed.accessToken,
            refreshToken: parsed.refreshToken,
            email: status.prefill?.email ?? '',
            prenom: status.prefill?.prenom ?? '',
            nom: status.prefill?.nom ?? '',
          });
          navigate(`/invitation/${pendingInvitation}`, { replace: true });
          return;
        }

        const prenom = status.prefill?.prenom?.trim() ?? '';
        const nom = status.prefill?.nom?.trim() ?? '';
        const { user } = await authService.registerOauth(
          {
            // Google ne donne pas de téléphone : il se renseigne en page profil.
            // Si le provider n'a renvoyé aucun nom, la partie locale de l'email
            // évite un affichage vide ; l'utilisateur corrige en page profil.
            prenom: prenom || (status.prefill?.email ?? '').split('@')[0] || 'Utilisateur',
            nom,
          },
          parsed.accessToken,
        );
        if (parsed.refreshToken) {
          await authService.oauthSession(parsed.accessToken, parsed.refreshToken).catch(() => {});
        }
        setAuth(user, parsed.accessToken);
        navigate(retourBrouillon ? ROUTES.REPRISE : '/app', { replace: true });
      })
      .catch((err: unknown) => { console.error(err); setError(ERROR_MESSAGE); });
  }, [navigate, setAuth, setPendingSession, parsed, invitation, reprise]);

  return (
    <AuthLayout>
      <div className="space-y-2.5">
        <h1
          className="text-[clamp(1.9rem,4vw,2.5rem)] leading-[1.1]"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          {!lienEmail ? (
            <>
              Connexion avec <span style={{ color: C.blue }}>Google</span>
            </>
          ) : error ? (
            /* L'adresse n'est justement PAS confirmée : le titre ne peut pas
               annoncer l'inverse de ce que dit le message juste dessous. */
            <>
              Lien de <span style={{ color: C.blue }}>confirmation</span>
            </>
          ) : (
            <>
              Adresse <span style={{ color: C.blue }}>confirmée</span>
            </>
          )}
        </h1>
        <p className="text-[17px]" style={{ color: MUTED }}>
          {error
            ? lienEmail
              ? 'Ce lien n’a pas pu être utilisé.'
              : 'La connexion ne s’est pas terminée.'
            : 'Un instant, nous vous connectons…'}
        </p>
      </div>

      {error ? (
        <div className="space-y-4">
          <div className="rounded-xl p-4 text-[16px]" style={{ background: C.paleDanger, color: C.danger }}>
            {error}
          </div>
          <button
            onClick={() => navigate('/login')}
            className="flex h-12 w-full items-center justify-center rounded-lg text-[16px] font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: C.orange }}
          >
            Retour à la connexion
          </button>
        </div>
      ) : (
        <div
          className="flex items-center justify-center gap-3 rounded-xl p-6 text-[17px]"
          style={{ background: C.paleBlue, color: C.ink }}
        >
          <Loader2 className="h-5 w-5 animate-spin" style={{ color: C.blue }} />
          Connexion en cours…
        </div>
      )}
    </AuthLayout>
  );
}
