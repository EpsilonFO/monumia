import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router';
import { ArrowRight, Loader2, Check } from 'lucide-react';
import { toast } from 'sonner';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuthStore } from '@/stores/useAuthStore';
import { usePendingOAuthStore } from '@/stores/usePendingOAuthStore';
import { authService } from '@/services/auth.service';
import { isValidPhone, PHONE_ERROR } from '@/lib/phone';

// Tokens du tableau de bord — CSS custom properties de thème
const C = {
  bgAlt: 'var(--card)',
  text: 'var(--foreground)',
  textMuted: 'var(--muted-foreground)',
  textLight: 'var(--muted-foreground)',
  royal: 'var(--primary)',
  terra: 'var(--accent)',
  border: 'var(--border)',
} as const;

const FONT_HEADING = "'PT Serif', Georgia, 'Times New Roman', serif";

const inputCls = 'h-10 text-[14px] bg-card border-border focus:border-primary focus:ring-primary/10';

/**
 * Complétion de profil après une connexion Google.
 *
 * L'inscription par email crée le compte d'un seul coup depuis LoginPage : cet
 * écran ne sert plus qu'au parcours OAuth, où le provider ne fournit ni
 * téléphone ni confirmation du nom. Sans session OAuth en attente, il n'y a
 * rien à compléter et on renvoie vers la connexion.
 */
export function OnboardingProfile() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const oauthAccessToken = usePendingOAuthStore((s) => s.accessToken);
  const oauthRefreshToken = usePendingOAuthStore((s) => s.refreshToken);
  const oauthEmail = usePendingOAuthStore((s) => s.email);
  const oauthPrenom = usePendingOAuthStore((s) => s.prenom);
  const oauthNom = usePendingOAuthStore((s) => s.nom);
  const clearOAuthSession = usePendingOAuthStore((s) => s.clear);

  const [loading, setLoading] = useState(false);
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [form, setForm] = useState({
    nom: oauthNom ?? '',
    prenom: oauthPrenom ?? '',
    telephone: '',
  });

  const update = (updates: Partial<typeof form>) => setForm((f) => ({ ...f, ...updates }));

  const handlePhoneChange = (value: string) => {
    update({ telephone: value });
    setPhoneError(value && !isValidPhone(value) ? PHONE_ERROR : null);
  };

  if (!oauthAccessToken) {
    return <Navigate to="/login" replace />;
  }

  const isValid = !!form.prenom.trim() && !!form.nom.trim() && !phoneError;

  const handleSubmit = async () => {
    if (!isValidPhone(form.telephone)) {
      setPhoneError(PHONE_ERROR);
      return;
    }
    setLoading(true);
    try {
      const { user } = await authService.registerOauth(
        {
          prenom: form.prenom.trim(),
          nom: form.nom.trim(),
          telephone: form.telephone.trim() || undefined,
        },
        oauthAccessToken,
      );
      // Le refresh token du hash Google part en cookie httpOnly. Échec non
      // bloquant : la session tient jusqu'à expiration de l'access token.
      if (oauthRefreshToken) {
        await authService.oauthSession(oauthAccessToken, oauthRefreshToken).catch(() => {});
      }
      clearOAuthSession();
      setAuth(user, oauthAccessToken);
      navigate('/app');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la création du compte');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* heading */}
      <div className="space-y-2">
        <div className="flex items-center gap-2.5">
          <span style={{ width: 22, height: 2, borderRadius: 2, background: C.terra }} />
          <span className="text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.royal }}>
            Dernière étape
          </span>
        </div>
        <h1
          className="text-[clamp(1.5rem,3.5vw,2rem)] font-light tracking-[-0.02em]"
          style={{ fontFamily: FONT_HEADING, color: C.text }}
        >
          Votre profil
        </h1>
        <div
          className="flex items-start gap-2.5 rounded-xl p-4 text-[14px] leading-[1.55]"
          style={{ background: 'var(--secondary)', color: C.text }}
        >
          <Check className="mt-0.5 h-4 w-4 flex-shrink-0" style={{ color: 'var(--success)' }} />
          <span>
            Vous êtes connecté avec votre compte Google
            {oauthEmail ? (
              <>
                {' '}
                (<span className="font-semibold">{oauthEmail}</span>)
              </>
            ) : null}
            . Vérifiez votre nom et c'est terminé.
          </span>
        </div>
      </div>

      <div className="rounded-2xl border p-5" style={{ borderColor: C.border, background: C.bgAlt }}>
        <h3 className="mb-4 text-[17px] font-normal" style={{ fontFamily: FONT_HEADING, color: C.text }}>
          Informations personnelles
        </h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="nom" className="text-[13px] font-medium" style={{ color: C.text }}>Nom *</Label>
            <Input
              id="nom"
              autoComplete="family-name"
              value={form.nom}
              onChange={(e) => update({ nom: e.target.value })}
              placeholder="Dupont"
              className={inputCls}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="prenom" className="text-[13px] font-medium" style={{ color: C.text }}>Prénom *</Label>
            <Input
              id="prenom"
              autoComplete="given-name"
              value={form.prenom}
              onChange={(e) => update({ prenom: e.target.value })}
              placeholder="Marie"
              className={inputCls}
            />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor="telephone" className="text-[13px] font-medium" style={{ color: C.text }}>
              Téléphone <span className="font-normal" style={{ color: C.textLight }}>(optionnel)</span>
            </Label>
            <Input
              id="telephone"
              type="tel"
              autoComplete="tel"
              value={form.telephone}
              onChange={(e) => handlePhoneChange(e.target.value)}
              placeholder="02 33 40 00 00"
              className={`${inputCls}${phoneError ? ' border-destructive focus:border-destructive' : ''}`}
            />
            {phoneError && <p className="mt-0.5 text-[12px] text-destructive">{phoneError}</p>}
          </div>
        </div>
      </div>

      <div className="flex justify-end pt-1">
        <button
          onClick={handleSubmit}
          disabled={!isValid || loading}
          className="group flex items-center gap-2 rounded-lg px-6 py-2.5 text-[13px] font-semibold text-white transition-opacity duration-200 hover:opacity-90 disabled:opacity-50"
          style={{ background: C.terra }}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : (
            <>
              Accéder à mon espace
              <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
