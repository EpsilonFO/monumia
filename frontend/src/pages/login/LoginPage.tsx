import { useState } from 'react';
import { useNavigate } from 'react-router';
import { EyeOff, Loader2, ArrowRight, Check, X } from 'lucide-react';
import { IconVoir } from '@/components/icons';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { useAuthStore } from '@/stores/useAuthStore';
import { authService } from '@/services/auth.service';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { GoogleButton } from '@/components/auth/GoogleButton';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { passwordChecks, isPasswordValid, PASSWORD_RULES } from '@/lib/password';
import { isValidPhone, PHONE_ERROR } from '@/lib/phone';
import { toast } from 'sonner';

const MUTED = 'var(--muted-foreground)';
const LIGHT = 'var(--muted-foreground)';
const SUCCESS = 'var(--success)';

const inputCls =
  'h-11 text-[14px] bg-card border-border focus:border-primary focus:ring-primary/10';

// Pages légales, servies par la landing (monumia.fr).
const CGU_URL = 'https://monumia.fr/cgu';
const PRIVACY_URL = 'https://monumia.fr/confidentialite';

function LegalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium underline underline-offset-2"
      style={{ color: C.blue }}
    >
      {children}
    </a>
  );
}

export function LoginPage() {
  const setAuth = useAuthStore((s) => s.setAuth);
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
      navigate(user.accountType === 'collaborateur' ? ROUTES.PROJETS : '/app');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Email ou mot de passe incorrect');
    } finally {
      setLoginLoading(false);
    }
  };

  // --- Inscription ---
  // Le compte est créé ici, en une seule soumission : identifiants à gauche,
  // identité à droite. Plus d'étape de profil intermédiaire, donc plus de
  // stockage transitoire du mot de passe.
  const [registerForm, setRegisterForm] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    nom: '',
    prenom: '',
    telephone: '',
  });
  const [showRegisterPwd, setShowRegisterPwd] = useState(false);
  const [registerLoading, setRegisterLoading] = useState(false);
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [acceptCgu, setAcceptCgu] = useState(false);
  const pwdChecks = passwordChecks(registerForm.password);
  const pwdValid = isPasswordValid(registerForm.password);

  const updateRegister = (updates: Partial<typeof registerForm>) =>
    setRegisterForm((f) => ({ ...f, ...updates }));

  const handlePhoneChange = (value: string) => {
    updateRegister({ telephone: value });
    setPhoneError(value && !isValidPhone(value) ? PHONE_ERROR : null);
  };

  const registerReady =
    !!registerForm.email &&
    !!registerForm.password &&
    !!registerForm.confirmPassword &&
    !!registerForm.nom.trim() &&
    !!registerForm.prenom.trim() &&
    pwdValid &&
    !phoneError &&
    acceptCgu;

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (registerForm.password !== registerForm.confirmPassword) {
      toast.error('Les mots de passe ne correspondent pas');
      return;
    }
    if (!pwdValid) {
      toast.error('Le mot de passe doit contenir au moins 8 caractères et 1 chiffre');
      return;
    }
    if (!isValidPhone(registerForm.telephone)) {
      setPhoneError(PHONE_ERROR);
      return;
    }
    if (!acceptCgu) {
      toast.error("Merci d'accepter les conditions générales d'utilisation");
      return;
    }
    setRegisterLoading(true);
    try {
      const { user, access_token } = await authService.register({
        email: registerForm.email,
        password: registerForm.password,
        prenom: registerForm.prenom.trim(),
        nom: registerForm.nom.trim(),
        telephone: registerForm.telephone.trim() || undefined,
      });
      setAuth(user, access_token);
      navigate('/app');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la création du compte');
    } finally {
      setRegisterLoading(false);
    }
  };

  return (
    // L'inscription tient six champs sur deux colonnes : la colonne crème
    // s'élargit pour que les placeholders respirent, au lieu de couper des
    // champs de moitié dans la largeur de la connexion.
    <AuthLayout contentClassName={tab === 'register' ? 'max-w-3xl space-y-5' : 'max-w-md space-y-6'}>
      {/* heading */}
      <div className="space-y-1.5">
        <h1 className="text-[clamp(1.6rem,3vw,2rem)] leading-[1.1]" style={{ fontFamily: SERIF, color: C.ink }}>
          {tab === 'login' ? (
            <>Bon <span style={{ color: C.blue }}>retour</span>.</>
          ) : (
            <>Créer un <span style={{ color: C.blue }}>compte</span></>
          )}
        </h1>
        <p className="text-[14px]" style={{ color: MUTED }}>
          {tab === 'login'
            ? 'Connectez-vous pour accéder à votre espace.'
            : 'Tout se passe ici : votre compte est créé en une étape.'}
        </p>
      </div>

      {/* tab switcher */}
      <div className="flex gap-1 rounded-xl p-1" style={{ background: C.paleBlue }}>
        {(['login', 'register'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="flex-1 rounded-lg py-2 text-[13.5px] font-semibold transition-all duration-200"
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
            <GoogleButton />
            {/* L'inscription Google contourne le formulaire (et sa case CGU) :
                l'acceptation passe alors par cette mention. */}
            {/* {tab === 'register' && (
              <p className="mt-2 text-center text-[12px] leading-[1.5]" style={{ color: LIGHT }}>
                En continuant avec Google, vous acceptez les{' '}
                <LegalLink href={CGU_URL}>CGU</LegalLink> et la{' '}
                <LegalLink href={PRIVACY_URL}>politique de confidentialité</LegalLink>.
              </p>
            )} */}
          </div>
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
        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="login-email" className="text-[13.5px] font-medium" style={{ color: C.ink }}>Email</Label>
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
            <Label htmlFor="login-password" className="text-[13.5px] font-medium" style={{ color: C.ink }}>Mot de passe</Label>
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
            className="group flex h-11 w-full items-center justify-center gap-2 rounded-lg text-[14px] font-semibold text-white transition-opacity duration-200 hover:opacity-90 disabled:opacity-50"
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
        <form onSubmit={handleRegister} className="space-y-4">
          <div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
            {/* ── Colonne gauche : identifiants de connexion ── */}
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="reg-email" className="text-[13.5px] font-medium" style={{ color: C.ink }}>Email</Label>
                <Input
                  id="reg-email"
                  type="email"
                  autoComplete="email"
                  placeholder="marie.dupont@mairie.fr"
                  value={registerForm.email}
                  onChange={(e) => updateRegister({ email: e.target.value })}
                  required
                  className={inputCls}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reg-password" className="text-[13.5px] font-medium" style={{ color: C.ink }}>Mot de passe</Label>
                <div className="relative">
                  <Input
                    id="reg-password"
                    type={showRegisterPwd ? 'text' : 'password'}
                    autoComplete="new-password"
                    placeholder="••••••••"
                    value={registerForm.password}
                    onChange={(e) => updateRegister({ password: e.target.value })}
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
                <Label htmlFor="reg-confirm" className="text-[13.5px] font-medium" style={{ color: C.ink }}>Confirmer le mot de passe</Label>
                <Input
                  id="reg-confirm"
                  type="password"
                  autoComplete="new-password"
                  placeholder="••••••••"
                  value={registerForm.confirmPassword}
                  onChange={(e) => updateRegister({ confirmPassword: e.target.value })}
                  required
                  className={inputCls}
                />
              </div>
            </div>

            {/* ── Colonne droite : votre identité ── */}
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="reg-nom" className="text-[13.5px] font-medium" style={{ color: C.ink }}>Nom</Label>
                <Input
                  id="reg-nom"
                  autoComplete="family-name"
                  placeholder="Dupont"
                  value={registerForm.nom}
                  onChange={(e) => updateRegister({ nom: e.target.value })}
                  required
                  className={inputCls}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reg-prenom" className="text-[13.5px] font-medium" style={{ color: C.ink }}>Prénom</Label>
                <Input
                  id="reg-prenom"
                  autoComplete="given-name"
                  placeholder="Marie"
                  value={registerForm.prenom}
                  onChange={(e) => updateRegister({ prenom: e.target.value })}
                  required
                  className={inputCls}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reg-tel" className="text-[13.5px] font-medium" style={{ color: C.ink }}>
                  Téléphone <span className="font-normal" style={{ color: LIGHT }}>(optionnel)</span>
                </Label>
                <Input
                  id="reg-tel"
                  type="tel"
                  autoComplete="tel"
                  placeholder="02 33 40 00 00"
                  value={registerForm.telephone}
                  onChange={(e) => handlePhoneChange(e.target.value)}
                  className={`${inputCls}${phoneError ? ' border-destructive focus:border-destructive' : ''}`}
                />
                {phoneError && <p className="text-[12px] text-destructive">{phoneError}</p>}
              </div>
            </div>
          </div>

          {/* Acceptation des CGU : requise, elle verrouille le bouton de création */}
          <label htmlFor="reg-cgu" className="flex cursor-pointer items-start gap-2.5">
            <Checkbox
              id="reg-cgu"
              checked={acceptCgu}
              onCheckedChange={(v) => setAcceptCgu(v === true)}
              className="mt-[3px]"
            />
            <span className="text-[13px] leading-[1.55]" style={{ color: MUTED }}>
              J'ai lu et j'accepte les <LegalLink href={CGU_URL}>conditions générales d'utilisation</LegalLink>{' '}
              et la <LegalLink href={PRIVACY_URL}>politique de confidentialité</LegalLink>.
            </span>
          </label>

          <button
            type="submit"
            disabled={!registerReady || registerLoading}
            className="group flex h-11 w-full items-center justify-center gap-2 rounded-lg text-[14px] font-semibold text-white transition-opacity duration-200 hover:opacity-90 disabled:opacity-50"
            style={{ background: C.orange }}
          >
            {registerLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <>
                Créer mon compte
                <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
              </>
            )}
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
              className="flex h-11 w-full items-center justify-center rounded-lg text-[14px] font-semibold text-white transition-opacity hover:opacity-90"
              style={{ background: C.orange }}
            >
              Retour à la connexion
            </button>
          </div>
        ) : (
          <form onSubmit={handleForgot} className="space-y-4">
            <p className="text-[14px]" style={{ color: MUTED }}>
              Indiquez votre email : nous vous enverrons un lien pour choisir un nouveau mot de passe. Rien à retenir.
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="forgot-email" className="text-[13.5px] font-medium" style={{ color: C.ink }}>Email</Label>
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
              className="flex h-11 w-full items-center justify-center gap-2 rounded-lg text-[14px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
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
