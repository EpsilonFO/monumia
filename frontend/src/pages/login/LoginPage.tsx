import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { EyeOff, Loader2, ArrowRight, ArrowLeft } from 'lucide-react';
import { IconVoir } from '@/components/icons';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuthStore } from '@/stores/useAuthStore';
import { authService } from '@/services/auth.service';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { GoogleButton } from '@/components/auth/GoogleButton';
import { RegisterForm, inputCls } from '@/components/auth/RegisterForm';
import { ConfirmerEmail } from '@/components/auth/ConfirmerEmail';
import { ApiError } from '@/lib/api-error';
import { brouillonPretPourRejeu, marquerRetourGoogleBrouillon } from '@/lib/brouillon-invite';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { toast } from 'sonner';

const MUTED = 'var(--muted-foreground)';
const LIGHT = 'var(--muted-foreground)';

export function LoginPage() {
  const setAuth = useAuthStore((s) => s.setAuth);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // « J'ai déjà un compte » depuis le wizard découverte. Le paramètre est
  // EXIGÉ : sans lui, un brouillon oublié dans le localStorage détournerait
  // une connexion ordinaire vers l'écran de reprise. Cliquer est une demande,
  // arriver par un vieux lien ne l'est pas.
  const reprise = searchParams.get('reprise') === 'brouillon' && brouillonPretPourRejeu();
  const apresAuth = reprise ? ROUTES.REPRISE : null;
  // Arrivée du parcours découverte : l'INSCRIPTION d'abord. Le visiteur vient
  // de décrire son monument et de répondre au questionnaire — dans la quasi
  // totalité des cas il n'a pas encore de compte, et lui présenter un
  // formulaire de connexion vide lui ferait chercher l'onglet. Celui de la
  // connexion reste à un clic, pour les rares qui reviennent.
  const [tab, setTab] = useState<'login' | 'register' | 'forgot'>(
    reprise ? 'register' : 'login',
  );
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotState, setForgotState] = useState<'idle' | 'sending' | 'sent'>('idle');

  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault();
    setForgotState('sending');
    try {
      await authService.requestPasswordReset(forgotEmail);
      setForgotState('sent');
    } catch {
      // Réponse volontairement indifférenciée (le back répond toujours 200).
      setForgotState('sent');
    }
  };

  // --- Connexion ---
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [loginLoading, setLoginLoading] = useState(false);
  const [showLoginPwd, setShowLoginPwd] = useState(false);
  // Adresse à confirmer : après une inscription (le compte vient d'être créé)
  // ou après une connexion refusée en 403 (compte plus ancien, jamais
  // confirmé). L'adresse est prise et la session fermée : le renvoi de l'email
  // est la seule issue, d'où un écran plein et non un toast.
  const [emailAConfirmer, setEmailAConfirmer] = useState<{
    email: string;
    variante: 'inscription' | 'connexion';
  } | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginLoading(true);
    try {
      const { user, access_token } = await authService.login(loginForm);
      setAuth(user, access_token);
      navigate(
        apresAuth ?? (user.accountType === 'collaborateur' ? ROUTES.MONUMENTS : '/app'),
      );
    } catch (err: unknown) {
      // 403 : le mot de passe est BON, c'est l'adresse qui n'est pas confirmée.
      // Un toast « email ou mot de passe incorrect » enverrait l'utilisateur
      // ressaisir un mot de passe juste, puis demander une réinitialisation
      // qui ne réglerait rien.
      if (err instanceof ApiError && err.status === 403) {
        setEmailAConfirmer({ email: loginForm.email, variante: 'connexion' });
        return;
      }
      toast.error(err instanceof Error ? err.message : 'Email ou mot de passe incorrect');
    } finally {
      setLoginLoading(false);
    }
  };

  // Arrivée depuis le parcours découverte : le visiteur vient de cliquer
  // « Se connecter pour découvrir mon diagnostic ». Le panneau lui redit
  // pourquoi il est là — sans ça, il tombe sur un écran de connexion
  // générique qui ne parle plus du tout de son monument. Hissé hors du rendu
  // parce que l'écran d'attente de confirmation le réutilise tel quel.
  const panneau = {
    panelEyebrow: reprise ? 'Votre diagnostic vous attend' : undefined,
    panelHeadline: reprise ? (
      <>
        Votre diagnostic est <span style={{ color: C.orange }}>prêt</span>.
      </>
    ) : undefined,
    panelDescription: reprise
      ? 'Votre monument et votre projet sont conservés : dès votre connexion, ils rejoignent votre espace et le diagnostic s’ouvre.'
      : undefined,
  };

  // L'adresse à confirmer prend TOUT l'écran : ni titre, ni onglets, ni bouton
  // Google. Il n'y a plus qu'une chose à faire, aller dans sa boîte, et tout ce
  // qui parlait de créer un compte parle désormais d'une étape déjà franchie.
  // Un simple retour suffit pour revenir corriger l'adresse.
  if (emailAConfirmer) {
    return (
      <AuthLayout contentClassName="max-w-md space-y-6" {...panneau}>
        <button
          type="button"
          onClick={() => setEmailAConfirmer(null)}
          className="flex items-center gap-1.5 text-[15.5px] font-medium transition-opacity hover:opacity-70"
          style={{ color: MUTED }}
        >
          <ArrowLeft className="h-4 w-4" />
          Retour
        </button>
        <ConfirmerEmail
          email={emailAConfirmer.email}
          intention={{ reprise }}
          variante={emailAConfirmer.variante}
        />
      </AuthLayout>
    );
  }

  return (
    // L'inscription tient six champs sur deux colonnes : la colonne crème
    // s'élargit pour que les placeholders respirent, au lieu de couper des
    // champs de moitié dans la largeur de la connexion.
    <AuthLayout
      contentClassName={tab === 'register' ? 'max-w-3xl space-y-5' : 'max-w-md space-y-6'}
      {...panneau}
    >
      {/* heading */}
      <div className="space-y-1.5">
        <h1 className="text-[clamp(1.6rem,3vw,2rem)] leading-[1.1]" style={{ fontFamily: SERIF, color: C.ink }}>
          {reprise ? (
            <>Plus qu&rsquo;une <span style={{ color: C.blue }}>étape</span>.</>
          ) : tab === 'login' ? (
            <>Bon <span style={{ color: C.blue }}>retour</span>.</>
          ) : (
            <>Créer un <span style={{ color: C.blue }}>compte</span></>
          )}
        </h1>
        <p className="text-[16px]" style={{ color: MUTED }}>
          {reprise
            ? 'Créez votre compte gratuit — ou connectez-vous si vous en avez déjà un : votre diagnostic s’ouvre juste après.'
            : tab === 'login'
              ? 'Connectez-vous pour accéder à votre espace.'
              : 'Tout se passe ici : votre compte est créé en une étape.'}
        </p>
      </div>

      {/* tab switcher */}
      <div className="flex gap-1 rounded-xl p-1" style={{ background: C.paleBlue }}>
        {(['login', 'register'] as const).map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setEmailAConfirmer(null); }}
            className="flex-1 rounded-lg py-2 text-[15.5px] font-semibold transition-all duration-200"
            style={{
              background: tab === t ? C.blue : 'transparent',
              color: tab === t ? 'white' : C.blue,
            }}
          >
            {t === 'login' ? 'Connexion' : 'Inscription'}
          </button>
        ))}
      </div>

      {/* ── Connexion Google (login + inscription) ── */}
      {tab !== 'forgot' && (
        <div className="space-y-4">
          {/* Le bouton garde sa largeur de bouton, centré : sur l'inscription
              élargie, l'étirer sur 768 px en ferait une banderole. Le filet, lui,
              sépare bien les deux sections et court sur toute la largeur. */}
          <div className="md:mx-auto md:max-w-md">
            <GoogleButton
              beforeRedirect={reprise ? marquerRetourGoogleBrouillon : undefined}
            />
            {/* L'inscription Google contourne le formulaire, donc sa case CGU.
                La mention qui porte alors l'acceptation est active sur l'écran
                d'inscription du parcours découverte (`InscriptionStep`), où
                c'est le seul chemin d'entrée ; ici les deux onglets cohabitent
                et la case du formulaire reste la référence. */}
          </div>
          <div className="flex items-center gap-3" aria-hidden="true">
            <span className="h-px flex-1" style={{ background: 'var(--border)' }} />
            <span className="text-[15px] whitespace-nowrap" style={{ color: MUTED }}>
              ou avec votre adresse email
            </span>
            <span className="h-px flex-1" style={{ background: 'var(--border)' }} />
          </div>
        </div>
      )}

      {/* ── Connexion ── */}
      {tab === 'login' && (
        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="login-email" className="text-[15.5px] font-medium" style={{ color: C.ink }}>Email</Label>
            <Input
              id="login-email"
              type="email"
              autoComplete="email"
              placeholder="marie.dupont@mairie.fr"
              value={loginForm.email}
              onChange={(e) => setLoginForm((f) => ({ ...f, email: e.target.value }))}
              required
              className={inputCls}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="login-password" className="text-[15.5px] font-medium" style={{ color: C.ink }}>Mot de passe</Label>
            <div className="relative">
              <Input
                id="login-password"
                type={showLoginPwd ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="••••••••"
                value={loginForm.password}
                onChange={(e) => setLoginForm((f) => ({ ...f, password: e.target.value }))}
                required
                className={`${inputCls} pr-11`}
              />
              <button
                type="button"
                className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
                style={{ color: LIGHT }}
                onClick={() => setShowLoginPwd((v) => !v)}
              >
                {showLoginPwd ? <EyeOff className="h-4 w-4" /> : <IconVoir className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div className="text-right -mt-2">
            <button
              type="button"
              onClick={() => { setForgotEmail(loginForm.email); setForgotState('idle'); setTab('forgot'); }}
              className="text-[15px] font-medium underline underline-offset-2"
              style={{ color: C.blue }}
            >
              Mot de passe oublié ?
            </button>
          </div>
          <button
            type="submit"
            disabled={loginLoading}
            className="group flex h-11 w-full items-center justify-center gap-2 rounded-lg text-[16px] font-semibold text-white transition-opacity duration-200 hover:opacity-90 disabled:opacity-50"
            style={{ background: C.orange }}
          >
            {loginLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <>
                Se connecter
                <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
              </>
            )}
          </button>
        </form>
      )}

      {/* ── Inscription ── */}
      {tab === 'register' && (
        <RegisterForm
          reprise={reprise}
          onSuccess={() => navigate(apresAuth ?? '/app')}
          onConfirmationRequise={(email) => setEmailAConfirmer({ email, variante: 'inscription' })}
          recoursConnexion={
            <button
              type="button"
              onClick={() => setTab('login')}
              className="font-semibold underline underline-offset-2"
              style={{ color: C.orange }}
            >
              Se connecter
            </button>
          }
        />
      )}

      {/* ── Mot de passe oublié ── */}
      {tab === 'forgot' && (
        forgotState === 'sent' ? (
          <div className="space-y-4">
            <div className="rounded-xl p-4 text-[16px]" style={{ background: C.paleBlue, color: C.ink }}>
              Si un compte existe pour <span className="font-semibold">{forgotEmail || 'cette adresse'}</span>, un email vient d'être envoyé avec un lien pour choisir un nouveau mot de passe. Pensez à vérifier vos courriers indésirables.
            </div>
            <button
              onClick={() => setTab('login')}
              className="flex h-11 w-full items-center justify-center rounded-lg text-[16px] font-semibold text-white transition-opacity hover:opacity-90"
              style={{ background: C.orange }}
            >
              Retour à la connexion
            </button>
          </div>
        ) : (
          <form onSubmit={handleForgot} className="space-y-4">
            <p className="text-[16px]" style={{ color: MUTED }}>
              Indiquez votre email : nous vous enverrons un lien pour choisir un nouveau mot de passe. Rien à retenir.
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="forgot-email" className="text-[15.5px] font-medium" style={{ color: C.ink }}>Email</Label>
              <Input
                id="forgot-email"
                type="email"
                autoComplete="email"
                placeholder="marie.dupont@mairie.fr"
                value={forgotEmail}
                onChange={(e) => setForgotEmail(e.target.value)}
                required
                className={inputCls}
              />
            </div>
            <button
              type="submit"
              disabled={forgotState === 'sending' || !forgotEmail}
              className="flex h-11 w-full items-center justify-center gap-2 rounded-lg text-[16px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: C.orange }}
            >
              {forgotState === 'sending' ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Recevoir le lien'}
            </button>
            <p className="text-center text-[15px]" style={{ color: MUTED }}>
              <button type="button" onClick={() => setTab('login')} className="font-semibold underline underline-offset-2" style={{ color: C.orange }}>
                Retour à la connexion
              </button>
            </p>
          </form>
        )
      )}

      {/* footer note */}
      <p className="text-center text-[15px]" style={{ color: LIGHT }}>
        {tab === 'login' ? (
          <>
            Pas encore de compte ?{' '}
            <button onClick={() => setTab('register')} className="font-semibold underline underline-offset-2" style={{ color: C.orange }}>
              Créer un compte
            </button>
          </>
        ) : (
          <>
            Déjà inscrit ?{' '}
            <button onClick={() => setTab('login')} className="font-semibold underline underline-offset-2" style={{ color: C.orange }}>
              Se connecter
            </button>
          </>
        )}
      </p>
    </AuthLayout>
  );
}
