import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { EyeOff, Loader2, ArrowRight, Check, X } from 'lucide-react';
import { IconVoir } from '@/components/icons';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { getSupabase } from '@/lib/supabase';
import { passwordChecks, isPasswordValid, PASSWORD_RULES } from '@/lib/password';
import { C, SERIF } from '@/lib/brand';
import { toast } from 'sonner';

const MUTED = 'var(--muted-foreground)';
const SUCCESS = 'var(--success)';
const inputCls = 'h-12 text-[17px] bg-card border-border focus:border-primary focus:ring-primary/10';

/**
 * Atterrissage du lien de réinitialisation de mot de passe. Supabase redirige
 * ici avec les jetons dans le fragment d'URL (#access_token=…&refresh_token=…&
 * type=recovery). On pose la session localement (client Supabase en mode
 * persistSession=false) puis on met à jour le mot de passe via updateUser.
 */
export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [saving, setSaving] = useState(false);

  const checks = passwordChecks(password);
  const valid = isPasswordValid(password);

  useEffect(() => {
    const hash = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : '';
    const params = new URLSearchParams(hash);
    const errorDescription = params.get('error_description');
    const accessToken = params.get('access_token');
    const refreshToken = params.get('refresh_token');
    const type = params.get('type');

    if (errorDescription) {
      setLinkError(errorDescription);
      return;
    }
    if (!accessToken || type !== 'recovery') {
      setLinkError('Ce lien de réinitialisation est invalide ou a expiré.');
      return;
    }

    getSupabase().auth
      .setSession({ access_token: accessToken, refresh_token: refreshToken ?? '' })
      .then(({ error }) => {
        if (error) {
          setLinkError('Ce lien de réinitialisation est invalide ou a expiré.');
          return;
        }
        setReady(true);
        // Nettoie l'URL pour ne pas laisser traîner les jetons.
        window.history.replaceState(null, '', window.location.pathname);
      });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready || saving) return;
    if (password !== confirm) {
      toast.error('Les deux mots de passe ne correspondent pas');
      return;
    }
    if (!valid) {
      toast.error('Le mot de passe doit contenir au moins 8 caractères et 1 chiffre');
      return;
    }
    setSaving(true);
    try {
      const { error } = await getSupabase().auth.updateUser({ password });
      if (error) throw new Error(error.message);
      await getSupabase().auth.signOut().catch(() => {});
      toast.success('Votre mot de passe a été changé. Connectez-vous avec le nouveau.');
      navigate('/login');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Impossible de changer le mot de passe.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AuthLayout>
      <div className="space-y-2.5">
        <h1 className="text-[clamp(1.9rem,4vw,2.5rem)] leading-[1.1]" style={{ fontFamily: SERIF, color: C.ink }}>
          Nouveau <span style={{ color: C.blue }}>mot de passe</span>
        </h1>
        <p className="text-[17px]" style={{ color: MUTED }}>
          {linkError
            ? 'Le lien ne fonctionne plus.'
            : 'Choisissez un nouveau mot de passe pour votre compte.'}
        </p>
      </div>

      {linkError ? (
        <div className="space-y-4">
          <div className="rounded-xl p-4 text-[16px]" style={{ background: C.paleDanger, color: C.danger }}>
            {linkError}
          </div>
          <button
            onClick={() => navigate('/login')}
            className="flex h-12 w-full items-center justify-center gap-2 rounded-lg text-[16px] font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: C.orange }}
          >
            Retour à la connexion
          </button>
          <p className="text-center text-[15px]" style={{ color: MUTED }}>
            Vous pourrez redemander un lien depuis « Mot de passe oublié ? ».
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-1.5">
            <Label htmlFor="new-password" className="text-[16px] font-medium" style={{ color: C.ink }}>
              Nouveau mot de passe
            </Label>
            <div className="relative">
              <Input
                id="new-password"
                type={show ? 'text' : 'password'}
                autoComplete="new-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={!ready}
                className={`${inputCls} pr-11`}
              />
              <button
                type="button"
                className="absolute right-3.5 top-1/2 -translate-y-1/2"
                style={{ color: MUTED }}
                onClick={() => setShow((v) => !v)}
                aria-label={show ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
              >
                {show ? <EyeOff className="h-4 w-4" /> : <IconVoir className="h-4 w-4" />}
              </button>
            </div>
            {password && (
              <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 pt-0.5">
                {PASSWORD_RULES.map(({ key, label }) => (
                  <div key={key} className="flex items-center gap-1.5 text-[14px]" style={{ color: checks[key] ? SUCCESS : MUTED }}>
                    {checks[key] ? <Check className="h-3 w-3 flex-shrink-0" /> : <X className="h-3 w-3 flex-shrink-0" />}
                    {label}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="confirm-password" className="text-[16px] font-medium" style={{ color: C.ink }}>
              Confirmer le mot de passe
            </Label>
            <Input
              id="confirm-password"
              type={show ? 'text' : 'password'}
              autoComplete="new-password"
              placeholder="••••••••"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              disabled={!ready}
              className={inputCls}
            />
          </div>

          <button
            type="submit"
            disabled={!ready || saving || !valid || !confirm}
            className="group flex h-12 w-full items-center justify-center gap-2 rounded-lg text-[16px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            style={{ background: C.orange }}
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <>
                Changer mon mot de passe
                <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
              </>
            )}
          </button>
        </form>
      )}
    </AuthLayout>
  );
}
