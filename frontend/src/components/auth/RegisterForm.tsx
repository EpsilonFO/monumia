import { useState, type ReactNode } from 'react';
import { EyeOff, Loader2, ArrowRight, Check, X } from 'lucide-react';
import { IconVoir } from '@/components/icons';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { useAuthStore } from '@/stores/useAuthStore';
import { authService } from '@/services/auth.service';
import { ApiError } from '@/lib/api-error';
import { C } from '@/lib/brand';
import { passwordChecks, isPasswordValid, PASSWORD_RULES } from '@/lib/password';
import { isValidPhone, PHONE_ERROR } from '@/lib/phone';
import { toast } from 'sonner';
import type { User } from '@/types';

const MUTED = 'var(--muted-foreground)';
const LIGHT = 'var(--muted-foreground)';
const SUCCESS = 'var(--success)';

export const inputCls =
  'h-11 text-[14px] bg-card border-border focus:border-primary focus:ring-primary/10';

// Pages légales, servies par la landing (monumia.fr). Internes : la case CGU
// de ce formulaire est le seul endroit qui les consomme. (`InvitationLandingPage`
// en a ses propres copies, antérieures.)
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

interface RegisterFormProps {
  /** Appelé APRÈS `setAuth` : la session est en place, la navigation peut
   *  viser une route protégée. */
  onSuccess: (user: User) => void;
  /**
   * Le recours offert quand l'adresse est déjà prise (409). Fourni par
   * l'appelant, parce que « se connecter » ne veut pas dire la même chose de
   * part et d'autre : la page de connexion bascule son propre onglet, l'étape
   * d'inscription du wizard navigue vers `/login?reprise=brouillon` pour que
   * le brouillon suive.
   */
  recoursConnexion?: ReactNode;
}

/**
 * Le formulaire d'inscription par email : identifiants à gauche, identité à
 * droite, compte créé en une seule soumission.
 *
 * Extrait de `LoginPage` parce que le parcours découverte s'inscrit à la fin de
 * son wizard, sans quitter l'écran. Les deux appelants partagent donc les mêmes
 * validations et la même case CGU — un formulaire dupliqué aurait dérivé.
 */
export function RegisterForm({ onSuccess, recoursConnexion }: RegisterFormProps) {
  const setAuth = useAuthStore((s) => s.setAuth);

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
  // Adresse déjà inscrite (409) : un message avec une ISSUE, pas un toast qui
  // s'efface. C'est le cas le plus fréquent, et le plus coûteux dans le
  // parcours découverte — il ne faut pas laisser croire que tout est perdu.
  const [dejaInscrit, setDejaInscrit] = useState(false);
  const pwdChecks = passwordChecks(registerForm.password);
  const pwdValid = isPasswordValid(registerForm.password);

  const updateRegister = (updates: Partial<typeof registerForm>) => {
    setRegisterForm((f) => ({ ...f, ...updates }));
    if (updates.email !== undefined) setDejaInscrit(false);
  };

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
      // Jeton absent : ce serait `enable_confirmations = true` côté Supabase,
      // où le compte existe mais la session attend la validation de l'email.
      // `setAuth(user, null)` ne compile pas et poserait un état mi-connecté
      // que `ProtectedRoute` rejetterait sans rien expliquer.
      if (!access_token) {
        toast.success('Compte créé. Confirmez votre email, puis reconnectez-vous.');
        return;
      }
      setAuth(user, access_token);
      onSuccess(user);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        setDejaInscrit(true);
      } else {
        toast.error(err instanceof Error ? err.message : 'Erreur lors de la création du compte');
      }
    } finally {
      setRegisterLoading(false);
    }
  };

  return (
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
            {dejaInscrit && (
              <p className="text-[12.5px] leading-[1.5]" style={{ color: C.danger }}>
                Un compte existe déjà avec cette adresse. {recoursConnexion}
              </p>
            )}
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
  );
}
