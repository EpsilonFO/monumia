import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Eye, EyeOff, Loader2, ArrowRight, Landmark, Shield, Clock, Check, X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuthStore } from '@/stores/useAuthStore';
import { usePendingRegistrationStore } from '@/stores/usePendingRegistrationStore';
import { authService } from '@/services/auth.service';
import { toast } from 'sonner';

function getPasswordStrength(password: string) {
  const checks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /\d/.test(password),
    special: /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?`~]/.test(password),
  };
  const score = Object.values(checks).filter(Boolean).length;
  return { score, checks };
}

const C = {
  bg: '#F8F7F4',
  bgAlt: '#FFFFFF',
  text: '#1B1E2E',
  textMuted: '#5C6178',
  textLight: '#8E92A4',
  royal: '#1A237E',
  royalLight: '#3949AB',
  royalPale: '#E8EAF6',
  terra: '#C75B3A',
  terraPale: '#FBF0EC',
  border: '#E4E2DC',
} as const;

export function LoginPage() {
  const setAuth = useAuthStore((s) => s.setAuth);
  const setPendingCredentials = usePendingRegistrationStore((s) => s.setCredentials);
  const navigate = useNavigate();
  const [tab, setTab] = useState<'login' | 'register'>('login');

  // --- Connexion ---
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [loginLoading, setLoginLoading] = useState(false);
  const [showLoginPwd, setShowLoginPwd] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginLoading(true);
    try {
      const { user, access_token, refresh_token } = await authService.login(loginForm);
      setAuth(user, access_token, refresh_token);
      navigate(user.segment === 'btp' ? '/btp' : '/app');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Email ou mot de passe incorrect');
    } finally {
      setLoginLoading(false);
    }
  };

  // --- Inscription ---
  const [registerForm, setRegisterForm] = useState({
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [showRegisterPwd, setShowRegisterPwd] = useState(false);

  const pwdStrength = getPasswordStrength(registerForm.password);

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    if (registerForm.password !== registerForm.confirmPassword) {
      toast.error('Les mots de passe ne correspondent pas');
      return;
    }
    if (pwdStrength.score < 5) {
      toast.error('Le mot de passe ne remplit pas tous les critères de sécurité');
      return;
    }
    setPendingCredentials(registerForm.email, registerForm.password);
    navigate('/onboarding');
  };

  return (
    <div className="min-h-screen flex" style={{ background: C.bg }}>
      {/* ═══════ LEFT — decorative panel ═══════ */}
      <div
        className="hidden lg:flex lg:w-[45%] xl:w-[42%] relative flex-col justify-between p-12 xl:p-16 overflow-hidden"
        style={{ background: C.royal }}
      >
        {/* decorative glows */}
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full blur-[120px]" style={{ background: `${C.royalLight}50` }} />
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-56 w-56 rounded-full blur-[100px]" style={{ background: `${C.terra}18` }} />
        {/* subtle lines */}
        <div className="pointer-events-none absolute inset-0 opacity-[0.04]" style={{
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 79px, #fff 79px, #fff 80px)',
        }} />

        <div className="relative z-10">
          <button onClick={() => navigate('/')} className="flex items-center gap-3 group">
            <img src="/monumia.png" alt="Monumia" className="h-8 drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]" />
            <span className="text-[15px] font-semibold text-white/80 tracking-wide group-hover:text-white transition-colors">Monumia</span>
          </button>
        </div>

        <div className="relative z-10 space-y-8">
          <h2
            className="text-[clamp(2rem,3.5vw,3.2rem)] font-light leading-[1.1] tracking-[-0.02em] text-white"
            style={{ fontFamily: "'Cormorant Garamond', serif" }}
          >
            Financez la restauration<br />
            de votre <em className="italic" style={{ color: '#E8C9A0' }}>patrimoine</em>
          </h2>
          <p className="max-w-sm text-[15px] leading-[1.75] text-white/70">
            Identifiez les subventions, déductions fiscales et dispositifs de mécénat disponibles pour vos monuments historiques.
          </p>
        </div>

        <div className="relative z-10 flex flex-col gap-4 text-[13px] text-white/50 font-medium">
          <div className="flex items-center gap-3">
            <Landmark className="h-4 w-4 text-white/35" />
            <span>150+ aides référencées</span>
          </div>
          <div className="flex items-center gap-3">
            <Shield className="h-4 w-4 text-white/35" />
            <span>Données sécurisées</span>
          </div>
          <div className="flex items-center gap-3">
            <Clock className="h-4 w-4 text-white/35" />
            <span>Résultat instantané</span>
          </div>
        </div>
      </div>

      {/* ═══════ RIGHT — form panel ═══════ */}
      <div className="flex-1 flex flex-col">
        {/* mobile header */}
        <div className="lg:hidden flex items-center justify-between px-6 py-5" style={{ borderBottom: `1px solid ${C.border}` }}>
          <button onClick={() => navigate('/')} className="flex items-center gap-2">
            <img src="/monumia.png" alt="Monumia" className="h-7" />
            <span className="text-[15px] font-semibold" style={{ color: C.text }}>Monumia</span>
          </button>
        </div>

        <div className="flex-1 flex items-center justify-center px-6 py-12">
          <div className="w-full max-w-md space-y-8">
            {/* heading */}
            <div className="space-y-3">
              <h1
                className="text-[clamp(1.8rem,4vw,2.5rem)] font-light tracking-[-0.02em]"
                style={{ fontFamily: "'Cormorant Garamond', serif", color: C.text }}
              >
                {tab === 'login' ? 'Bon retour.' : 'Créer un compte'}
              </h1>
              <p className="text-[15px]" style={{ color: C.textMuted }}>
                {tab === 'login'
                  ? 'Connectez-vous pour accéder à votre espace.'
                  : 'Créez votre compte. Vous complèterez votre profil à l\'étape suivante.'}
              </p>
            </div>

            {/* tab switcher */}
            <div className="flex gap-0 rounded-lg overflow-hidden" style={{ border: `1px solid ${C.border}` }}>
              <button
                onClick={() => setTab('login')}
                className="flex-1 py-3 text-[14px] font-semibold transition-all duration-300"
                style={{
                  background: tab === 'login' ? C.royal : 'transparent',
                  color: tab === 'login' ? '#fff' : C.textLight,
                }}
              >
                Connexion
              </button>
              <button
                onClick={() => setTab('register')}
                className="flex-1 py-3 text-[14px] font-semibold transition-all duration-300"
                style={{
                  background: tab === 'register' ? C.royal : 'transparent',
                  color: tab === 'register' ? '#fff' : C.textLight,
                  borderLeft: `1px solid ${C.border}`,
                }}
              >
                Inscription
              </button>
            </div>

            {/* ── Connexion ── */}
            {tab === 'login' && (
              <form onSubmit={handleLogin} className="space-y-5">
                <div className="space-y-1.5">
                  <Label htmlFor="login-email" className="text-[14px] font-medium" style={{ color: C.text }}>Email</Label>
                  <Input
                    id="login-email"
                    type="email"
                    autoComplete="email"
                    placeholder="marie.dupont@mairie.fr"
                    value={loginForm.email}
                    onChange={(e) => setLoginForm((f) => ({ ...f, email: e.target.value }))}
                    required
                    className="h-12 text-[15px] bg-white border-[#E4E2DC] focus:border-[#1A237E] focus:ring-[#1A237E]/10"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="login-password" className="text-[14px] font-medium" style={{ color: C.text }}>Mot de passe</Label>
                  <div className="relative">
                    <Input
                      id="login-password"
                      type={showLoginPwd ? 'text' : 'password'}
                      autoComplete="current-password"
                      placeholder="••••••••"
                      value={loginForm.password}
                      onChange={(e) => setLoginForm((f) => ({ ...f, password: e.target.value }))}
                      required
                      className="h-12 text-[15px] pr-11 bg-white border-[#E4E2DC] focus:border-[#1A237E] focus:ring-[#1A237E]/10"
                    />
                    <button
                      type="button"
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
                      style={{ color: C.textLight }}
                      onClick={() => setShowLoginPwd((v) => !v)}
                    >
                      {showLoginPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={loginLoading}
                  className="group w-full flex items-center justify-center gap-2 h-12 text-[14px] font-semibold text-white transition-all duration-300 disabled:opacity-50 hover:shadow-lg"
                  style={{ background: C.royal }}
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
                  <Label htmlFor="reg-email" className="text-[14px] font-medium" style={{ color: C.text }}>Email</Label>
                  <Input
                    id="reg-email"
                    type="email"
                    autoComplete="email"
                    placeholder="marie.dupont@mairie.fr"
                    value={registerForm.email}
                    onChange={(e) => setRegisterForm((f) => ({ ...f, email: e.target.value }))}
                    required
                    className="h-12 text-[15px] bg-white border-[#E4E2DC] focus:border-[#1A237E] focus:ring-[#1A237E]/10"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="reg-password" className="text-[14px] font-medium" style={{ color: C.text }}>Mot de passe</Label>
                  <div className="relative">
                    <Input
                      id="reg-password"
                      type={showRegisterPwd ? 'text' : 'password'}
                      autoComplete="new-password"
                      placeholder="••••••••"
                      value={registerForm.password}
                      onChange={(e) => setRegisterForm((f) => ({ ...f, password: e.target.value }))}
                      required
                      className="h-12 text-[15px] pr-11 bg-white border-[#E4E2DC] focus:border-[#1A237E] focus:ring-[#1A237E]/10"
                    />
                    <button
                      type="button"
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors"
                      style={{ color: C.textLight }}
                      onClick={() => setShowRegisterPwd((v) => !v)}
                    >
                      {showRegisterPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {registerForm.password && (
                    <div className="space-y-2 pt-0.5">
                      {/* Force bars */}
                      <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((i) => {
                          const filled = pwdStrength.score >= i;
                          const color = pwdStrength.score <= 1 ? '#C75B3A' : pwdStrength.score <= 3 ? '#E59B3A' : '#2E7D32';
                          return (
                            <div
                              key={i}
                              className="h-1 flex-1 rounded-full transition-all duration-300"
                              style={{ background: filled ? color : '#E4E2DC' }}
                            />
                          );
                        })}
                      </div>
                      {/* Criteria list */}
                      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
                        {([
                          ['length', '8 caractères minimum'],
                          ['uppercase', '1 majuscule'],
                          ['lowercase', '1 minuscule'],
                          ['number', '1 chiffre'],
                          ['special', '1 caractère spécial'],
                        ] as [keyof typeof pwdStrength.checks, string][]).map(([key, label]) => (
                          <div key={key} className="flex items-center gap-1.5 text-[12px]" style={{ color: pwdStrength.checks[key] ? '#2E7D32' : C.textLight }}>
                            {pwdStrength.checks[key]
                              ? <Check className="h-3 w-3 flex-shrink-0" />
                              : <X className="h-3 w-3 flex-shrink-0" />}
                            {label}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="reg-confirm" className="text-[14px] font-medium" style={{ color: C.text }}>Confirmer le mot de passe</Label>
                  <Input
                    id="reg-confirm"
                    type="password"
                    autoComplete="new-password"
                    placeholder="••••••••"
                    value={registerForm.confirmPassword}
                    onChange={(e) => setRegisterForm((f) => ({ ...f, confirmPassword: e.target.value }))}
                    required
                    className="h-12 text-[15px] bg-white border-[#E4E2DC] focus:border-[#1A237E] focus:ring-[#1A237E]/10"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!registerForm.email || !registerForm.password || !registerForm.confirmPassword || pwdStrength.score < 5}
                  className="group w-full flex items-center justify-center gap-2 h-12 text-[14px] font-semibold text-white transition-all duration-300 disabled:opacity-50 hover:shadow-lg"
                  style={{ background: C.royal }}
                >
                  Créer mon compte
                  <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
                </button>
              </form>
            )}

            {/* footer note */}
            <p className="text-center text-[13px]" style={{ color: C.textLight }}>
              {tab === 'login' ? (
                <>
                  Pas encore de compte ?{' '}
                  <button onClick={() => setTab('register')} className="font-semibold underline underline-offset-2 transition-colors" style={{ color: C.terra }}>
                    Créer un compte
                  </button>
                </>
              ) : (
                <>
                  Déjà inscrit ?{' '}
                  <button onClick={() => setTab('login')} className="font-semibold underline underline-offset-2 transition-colors" style={{ color: C.terra }}>
                    Se connecter
                  </button>
                </>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
