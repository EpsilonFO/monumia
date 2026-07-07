import { useState } from 'react';
import { useNavigate } from 'react-router';
import { EyeOff, Loader2, ArrowRight, Check, X } from 'lucide-react';
import { IconVoir } from '@/components/icons';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuthStore } from '@/stores/useAuthStore';
import { usePendingRegistrationStore } from '@/stores/usePendingRegistrationStore';
import { authService } from '@/services/auth.service';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { GoogleButton } from '@/components/auth/GoogleButton';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { passwordChecks, isPasswordValid, PASSWORD_RULES } from '@/lib/password';
import { toast } from 'sonner';

const MUTED = 'var(--muted-foreground)';
const LIGHT = 'var(--muted-foreground)';
const SUCCESS = 'var(--success)';

const inputCls =
  'h-12 text-[15px] bg-card border-border focus:border-primary focus:ring-primary/10';

export function LoginPage() {
  const setAuth = useAuthStore((s) => s.setAuth);
  const setPendingCredentials = usePendingRegistrationStore((s) => s.setCredentials);
  const navigate = useNavigate();
  const [tab, setTab] = useState<'login' | 'register' | 'forgot'>('login');
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

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginLoading(true);
    try {
      const { user, access_token } = await authService.login(loginForm);
      setAuth(user, access_token);
      navigate(
        user.segment === 'btp'
          ? '/btp'
          : user.accountType === 'collaborateur'
            ? ROUTES.PROJETS
            : '/app',
      );
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Email ou mot de passe incorrect');
    } finally {
      setLoginLoading(false);
    }
  };

  // --- Inscription ---
  const [registerForm, setRegisterForm] = useState({ email: '', password: '', confirmPassword: '' });
  const [showRegisterPwd, setShowRegisterPwd] = useState(false);
  const pwdChecks = passwordChecks(registerForm.password);
  const pwdValid = isPasswordValid(registerForm.password);

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    if (registerForm.password !== registerForm.confirmPassword) {
      toast.error('Les mots de passe ne correspondent pas');
      return;
    }
    if (!pwdValid) {
      toast.error('Le mot de passe doit contenir au moins 8 caractères et 1 chiffre');
      return;
    }
    setPendingCredentials(registerForm.email, registerForm.password);
    navigate('/onboarding');
  };

  return (
    <AuthLayout>
      {/* heading */}
      <div className="space-y-2.5">
        <h1 className="text-[clamp(1.9rem,4vw,2.5rem)] leading-[1.1]" style={{ fontFamily: SERIF, color: C.ink }}>
          {tab === 'login' ? (
            <>Bon <span style={{ color: C.blue }}>retour</span>.</>
          ) : (
            <>Créer un <span style={{ color: C.blue }}>compte</span></>
          )}
        </h1>
        <p className="text-[15px]" style={{ color: MUTED }}>
          {tab === 'login'
            ? 'Connectez-vous pour accéder à votre espace.'
            : 'Vous compléterez votre profil à l’étape suivante.'}
        </p>
      </div>

      {/* tab switcher */}
      <div className="flex gap-1 rounded-xl p-1" style={{ background: C.paleBlue }}>
        {(['login', 'register'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="flex-1 rounded-lg py-2.5 text-[14px] font-semibold transition-all duration-200"
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
        <div className="space-y-5">
          <GoogleButton />
          <div className="flex items-center gap-3" aria-hidden="true">
            <span className="h-px flex-1" style={{ background: 'var(--border)' }} />
            <span className="text-[13px] whitespace-nowrap" style={{ color: MUTED }}>
              ou avec votre adresse email
            </span>
            <span className="h-px flex-1" style={{ background: 'var(--border)' }} />
          </div>
        </div>
      )}

      {/* ── Connexion ── */}
      {tab === 'login' && (
        <form onSubmit={handleLogin} className="space-y-5">
          <div className="space-y-1.5">
            <Label htmlFor="login-email" className="text-[14px] font-medium" style={{ color: C.ink }}>Email</Label>
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
            <Label htmlFor="login-password" className="text-[14px] font-medium" style={{ color: C.ink }}>Mot de passe</Label>
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
              className="text-[13px] font-medium underline underline-offset-2"
              style={{ color: C.blue }}
            >
              Mot de passe oublié ?
            </button>
          </div>
          <button
            type="submit"
            disabled={loginLoading}
            className="group flex h-12 w-full items-center justify-center gap-2 rounded-lg text-[14px] font-semibold text-white transition-opacity duration-200 hover:opacity-90 disabled:opacity-50"
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
        <form onSubmit={handleRegister} className="space-y-5">
          <div className="space-y-1.5">
            <Label htmlFor="reg-email" className="text-[14px] font-medium" style={{ color: C.ink }}>Email</Label>
            <Input
              id="reg-email"
              type="email"
              autoComplete="email"
              placeholder="marie.dupont@mairie.fr"
              value={registerForm.email}
              onChange={(e) => setRegisterForm((f) => ({ ...f, email: e.target.value }))}
              required
              className={inputCls}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="reg-password" className="text-[14px] font-medium" style={{ color: C.ink }}>Mot de passe</Label>
            <div className="relative">
              <Input
                id="reg-password"
                type={showRegisterPwd ? 'text' : 'password'}
                autoComplete="new-password"
                placeholder="••••••••"
                value={registerForm.password}
                onChange={(e) => setRegisterForm((f) => ({ ...f, password: e.target.value }))}
                required
                className={`${inputCls} pr-11`}
              />
              <button
                type="button"
                className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
                style={{ color: LIGHT }}
                onClick={() => setShowRegisterPwd((v) => !v)}
              >
                {showRegisterPwd ? <EyeOff className="h-4 w-4" /> : <IconVoir className="h-4 w-4" />}
              </button>
            </div>
            {registerForm.password && (
              <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 pt-0.5">
                {PASSWORD_RULES.map(({ key, label }) => (
                  <div key={key} className="flex items-center gap-1.5 text-[12px]" style={{ color: pwdChecks[key] ? SUCCESS : LIGHT }}>
                    {pwdChecks[key] ? <Check className="h-3 w-3 flex-shrink-0" /> : <X className="h-3 w-3 flex-shrink-0" />}
                    {label}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="reg-confirm" className="text-[14px] font-medium" style={{ color: C.ink }}>Confirmer le mot de passe</Label>
            <Input
              id="reg-confirm"
              type="password"
              autoComplete="new-password"
              placeholder="••••••••"
              value={registerForm.confirmPassword}
              onChange={(e) => setRegisterForm((f) => ({ ...f, confirmPassword: e.target.value }))}
              required
              className={inputCls}
            />
          </div>
          <button
            type="submit"
            disabled={!registerForm.email || !registerForm.password || !registerForm.confirmPassword || !pwdValid}
            className="group flex h-12 w-full items-center justify-center gap-2 rounded-lg text-[14px] font-semibold text-white transition-opacity duration-200 hover:opacity-90 disabled:opacity-50"
            style={{ background: C.orange }}
          >
            Créer mon compte
            <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
          </button>
        </form>
      )}

      {/* ── Mot de passe oublié ── */}
      {tab === 'forgot' && (
        forgotState === 'sent' ? (
          <div className="space-y-4">
            <div className="rounded-xl p-4 text-[14px]" style={{ background: C.paleBlue, color: C.ink }}>
              Si un compte existe pour <span className="font-semibold">{forgotEmail || 'cette adresse'}</span>, un email vient d'être envoyé avec un lien pour choisir un nouveau mot de passe. Pensez à vérifier vos courriers indésirables.
            </div>
            <button
              onClick={() => setTab('login')}
              className="flex h-12 w-full items-center justify-center rounded-lg text-[14px] font-semibold text-white transition-opacity hover:opacity-90"
              style={{ background: C.orange }}
            >
              Retour à la connexion
            </button>
          </div>
        ) : (
          <form onSubmit={handleForgot} className="space-y-5">
            <p className="text-[14px]" style={{ color: MUTED }}>
              Indiquez votre email : nous vous enverrons un lien pour choisir un nouveau mot de passe. Rien à retenir.
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="forgot-email" className="text-[14px] font-medium" style={{ color: C.ink }}>Email</Label>
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
              className="flex h-12 w-full items-center justify-center gap-2 rounded-lg text-[14px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: C.orange }}
            >
              {forgotState === 'sending' ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Recevoir le lien'}
            </button>
            <p className="text-center text-[13px]" style={{ color: MUTED }}>
              <button type="button" onClick={() => setTab('login')} className="font-semibold underline underline-offset-2" style={{ color: C.orange }}>
                Retour à la connexion
              </button>
            </p>
          </form>
        )
      )}

      {/* footer note */}
      <p className="text-center text-[13px]" style={{ color: LIGHT }}>
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
