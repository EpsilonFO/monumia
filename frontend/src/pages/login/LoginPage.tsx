import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Landmark, Eye, EyeOff, Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuthStore } from '@/stores/useAuthStore';
import { authService } from '@/services/auth.service';
import { toast } from 'sonner';

export function LoginPage() {
  const setAuth = useAuthStore((s) => s.setAuth);
  const navigate = useNavigate();

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
      navigate(user.segment === 'btp' ? '/btp' : '/');
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

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    if (registerForm.password !== registerForm.confirmPassword) {
      toast.error('Les mots de passe ne correspondent pas');
      return;
    }
    if (registerForm.password.length < 8) {
      toast.error('Le mot de passe doit contenir au moins 8 caractères');
      return;
    }
    // Store credentials temporarily so OnboardingProfile can complete registration
    sessionStorage.setItem('pending-register', JSON.stringify({
      email: registerForm.email,
      password: registerForm.password,
    }));
    navigate('/onboarding');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-amber-50/30 to-stone-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        {/* Logo */}
        <div className="text-center space-y-2">
          <div className="flex items-center justify-center gap-3 mb-1">
            <div className="w-11 h-11 rounded-xl bg-primary flex items-center justify-center shadow-md">
              <Landmark className="h-6 w-6 text-primary-foreground" />
            </div>
            <span className="text-2xl font-bold tracking-tight text-foreground">PatriAlta</span>
          </div>
          <p className="text-muted-foreground text-sm">
            La plateforme de financement du patrimoine historique
          </p>
        </div>

        <Card>
          <Tabs defaultValue="login">
            <CardHeader className="pb-2">
              <TabsList className="w-full">
                <TabsTrigger value="login" className="flex-1">Connexion</TabsTrigger>
                <TabsTrigger value="register" className="flex-1">Inscription</TabsTrigger>
              </TabsList>
            </CardHeader>

            {/* ── Connexion ── */}
            <TabsContent value="login">
              <form onSubmit={handleLogin}>
                <CardContent className="space-y-4 pt-2">
                  <div className="space-y-1">
                    <Label htmlFor="login-email">Email</Label>
                    <Input
                      id="login-email"
                      type="email"
                      autoComplete="email"
                      placeholder="marie.dupont@mairie.fr"
                      value={loginForm.email}
                      onChange={(e) => setLoginForm((f) => ({ ...f, email: e.target.value }))}
                      required
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="login-password">Mot de passe</Label>
                    <div className="relative">
                      <Input
                        id="login-password"
                        type={showLoginPwd ? 'text' : 'password'}
                        autoComplete="current-password"
                        placeholder="••••••••"
                        value={loginForm.password}
                        onChange={(e) => setLoginForm((f) => ({ ...f, password: e.target.value }))}
                        required
                        className="pr-10"
                      />
                      <button
                        type="button"
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        onClick={() => setShowLoginPwd((v) => !v)}
                      >
                        {showLoginPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                  <Button type="submit" className="w-full" disabled={loginLoading}>
                    {loginLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    Se connecter
                  </Button>
                </CardContent>
              </form>
            </TabsContent>

            {/* ── Inscription ── */}
            <TabsContent value="register">
              <form onSubmit={handleRegister}>
                <CardContent className="space-y-4 pt-2">
                  <CardDescription>
                    Créez votre compte. Vous complèterez votre profil à l'étape suivante.
                  </CardDescription>
                  <div className="space-y-1">
                    <Label htmlFor="reg-email">Email *</Label>
                    <Input
                      id="reg-email"
                      type="email"
                      autoComplete="email"
                      placeholder="marie.dupont@mairie.fr"
                      value={registerForm.email}
                      onChange={(e) => setRegisterForm((f) => ({ ...f, email: e.target.value }))}
                      required
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="reg-password">Mot de passe * (min. 8 caractères)</Label>
                    <div className="relative">
                      <Input
                        id="reg-password"
                        type={showRegisterPwd ? 'text' : 'password'}
                        autoComplete="new-password"
                        placeholder="••••••••"
                        value={registerForm.password}
                        onChange={(e) => setRegisterForm((f) => ({ ...f, password: e.target.value }))}
                        required
                        className="pr-10"
                      />
                      <button
                        type="button"
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        onClick={() => setShowRegisterPwd((v) => !v)}
                      >
                        {showRegisterPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="reg-confirm">Confirmer le mot de passe *</Label>
                    <Input
                      id="reg-confirm"
                      type="password"
                      autoComplete="new-password"
                      placeholder="••••••••"
                      value={registerForm.confirmPassword}
                      onChange={(e) => setRegisterForm((f) => ({ ...f, confirmPassword: e.target.value }))}
                      required
                    />
                  </div>
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={!registerForm.email || !registerForm.password || !registerForm.confirmPassword}
                  >
                    Créer mon compte
                  </Button>
                </CardContent>
              </form>
            </TabsContent>
          </Tabs>
        </Card>
      </div>
    </div>
  );
}
