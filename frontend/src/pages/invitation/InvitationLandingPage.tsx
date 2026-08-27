import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { Loader2, ArrowRight, Check, X } from 'lucide-react';
import { invitationService } from '@/services/invitation.service';
import { authService } from '@/services/auth.service';
import { useAuthStore } from '@/stores/useAuthStore';
import { usePendingOAuthStore } from '@/stores/usePendingOAuthStore';
import { MetierSelect } from '@/components/sharing/MetierSelect';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { GoogleButton } from '@/components/auth/GoogleButton';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { passwordChecks, isPasswordValid, PASSWORD_RULES } from '@/lib/password';
import { setPendingInvitation } from '@/lib/pending-invitation';
import { toast } from 'sonner';

const SUCCESS = 'var(--success)';
import type { InvitationPreview } from '@/types';

type Mode = 'choice' | 'signup' | 'login' | 'oauth';

const MUTED = 'var(--muted-foreground)';
const LIGHT = 'var(--muted-foreground)';
const INPUT_CLS = 'h-12 text-[15px] bg-card border-border focus:border-primary focus:ring-primary/10';

// Pages légales, servies par la landing (monumia.fr).
const CGU_URL = 'https://monumia.fr/cgu';
const PRIVACY_URL = 'https://monumia.fr/confidentialite';

/* Acceptation des CGU : requise pour toute création de compte,
   formulaire email comme retour de Google. */
function CguConsent({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  const linkCls = 'font-medium underline underline-offset-2';
  return (
    <label className="flex cursor-pointer items-start gap-2.5">
      <Checkbox checked={checked} onCheckedChange={(v) => onChange(v === true)} className="mt-[3px]" />
      <span className="text-[13px] leading-[1.55]" style={{ color: MUTED }}>
        J'ai lu et j'accepte les{' '}
        <a href={CGU_URL} target="_blank" rel="noopener noreferrer" className={linkCls} style={{ color: C.blue }}>
          conditions générales d'utilisation
        </a>{' '}
        et la{' '}
        <a href={PRIVACY_URL} target="_blank" rel="noopener noreferrer" className={linkCls} style={{ color: C.blue }}>
          politique de confidentialité
        </a>
        .
      </span>
    </label>
  );
}

export function InvitationLandingPage() {
  const { token = '' } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setAuth = useAuthStore((s) => s.setAuth);

  // Retour de Google : les jetons attendent en mémoire, le compte applicatif
  // n'existe pas encore. C'est ici qu'on le crée en collaborateur, parce que
  // c'est ici qu'on connaît le monument à rejoindre et le rôle à demander.
  const oauthAccessToken = usePendingOAuthStore((s) => s.accessToken);
  const oauthRefreshToken = usePendingOAuthStore((s) => s.refreshToken);
  const oauthEmail = usePendingOAuthStore((s) => s.email);
  const oauthPrenom = usePendingOAuthStore((s) => s.prenom);
  const oauthNom = usePendingOAuthStore((s) => s.nom);
  const clearOAuthSession = usePendingOAuthStore((s) => s.clear);

  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>(oauthAccessToken ? 'oauth' : 'choice');
  const [busy, setBusy] = useState(false);
  const [acceptCgu, setAcceptCgu] = useState(false);

  const [form, setForm] = useState({
    prenom: oauthPrenom ?? '',
    nom: oauthNom ?? '',
    email: '',
    password: '',
    metier: '',
    telephone: '',
  });

  useEffect(() => {
    invitationService
      .getByToken(token)
      .then((p) => {
        setPreview(p);
        setForm((f) => ({ ...f, email: p.email }));
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Invitation introuvable'));
  }, [token]);

  const acceptAndGo = async () => {
    // On atterrit là où l'invitation donne accès : le chantier si elle ne
    // portait que sur lui, le monument sinon.
    const { monumentId, projetId } = await invitationService.accept(token);
    navigate(projetId ? ROUTES.PROJET_DETAIL(projetId) : ROUTES.MONUMENT_DETAIL(monumentId));
  };

  const handleJoinLoggedIn = async () => {
    setBusy(true);
    try {
      await acceptAndGo();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Impossible de rejoindre');
    } finally {
      setBusy(false);
    }
  };

  const handleSignup = async () => {
    if (!isPasswordValid(form.password)) {
      toast.error('Le mot de passe doit contenir au moins 8 caractères et 1 chiffre');
      return;
    }
    if (!form.metier) {
      toast.error('Indiquez votre rôle sur le monument');
      return;
    }
    if (!acceptCgu) {
      toast.error("Merci d'accepter les conditions générales d'utilisation");
      return;
    }
    setBusy(true);
    try {
      const { user: u, access_token } = await authService.registerCollaborator({
        email: form.email,
        password: form.password,
        prenom: form.prenom,
        nom: form.nom,
        metier: form.metier,
        telephone: form.telephone || undefined,
      });
      setAuth(u, access_token);
      await acceptAndGo();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Échec de l'inscription");
    } finally {
      setBusy(false);
    }
  };

  const handleOauthSignup = async () => {
    if (!form.metier) {
      toast.error('Indiquez votre rôle sur le monument');
      return;
    }
    if (!form.prenom.trim() || !form.nom.trim()) {
      toast.error('Renseignez votre nom et votre prénom');
      return;
    }
    if (!acceptCgu) {
      toast.error("Merci d'accepter les conditions générales d'utilisation");
      return;
    }
    setBusy(true);
    try {
      const { user: u } = await authService.registerCollaboratorOauth(
        {
          prenom: form.prenom.trim(),
          nom: form.nom.trim(),
          metier: form.metier,
          telephone: form.telephone.trim() || undefined,
        },
        oauthAccessToken!,
      );
      // Le refresh token du hash Google part en cookie httpOnly. Échec non
      // bloquant : la session tient jusqu'à expiration de l'access token.
      if (oauthRefreshToken) {
        await authService.oauthSession(oauthAccessToken!, oauthRefreshToken).catch(() => {});
      }
      clearOAuthSession();
      setAuth(u, oauthAccessToken!);
      await acceptAndGo();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Échec de l'inscription");
    } finally {
      setBusy(false);
    }
  };

  const handleLogin = async () => {
    setBusy(true);
    try {
      const { user: u, access_token } = await authService.login({
        email: form.email,
        password: form.password,
      });
      setAuth(u, access_token);
      await acceptAndGo();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Connexion impossible');
    } finally {
      setBusy(false);
    }
  };

  // ── États non nominaux ──
  if (error) {
    return (
      <AuthLayout panelEyebrow="Invitation">
        <Heading>Invitation introuvable</Heading>
        <p className="text-[15px]" style={{ color: C.danger }}>{error}</p>
        <p className="text-[14px]" style={{ color: LIGHT }}>
          Demandez un nouveau lien à la personne qui vous a invité.
        </p>
      </AuthLayout>
    );
  }
  if (!preview) {
    return (
      <AuthLayout panelEyebrow="Invitation">
        <div className="flex items-center justify-center py-10">
          <Loader2 className="h-6 w-6 animate-spin" style={{ color: LIGHT }} />
        </div>
      </AuthLayout>
    );
  }
  if (preview.status !== 'pending') {
    return (
      <AuthLayout panelEyebrow="Invitation">
        <Heading>Invitation expirée</Heading>
        <p className="text-[15px]" style={{ color: C.danger }}>Cette invitation n'est plus valide.</p>
        <p className="text-[14px]" style={{ color: LIGHT }}>
          Elle a peut-être déjà été utilisée, annulée ou expirée. Demandez un nouveau lien à la
          personne qui vous a invité.
        </p>
      </AuthLayout>
    );
  }

  const expires = new Date(preview.expiresAt).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });

  const panelHeadline = (
    <>
      <span className="font-normal">{preview.inviterNom}</span> vous invite à collaborer sur<br />
      <span style={{ color: C.orange }}>«&nbsp;{preview.monumentNom}&nbsp;»</span>
    </>
  );
  // Dire la portée AVANT d'accepter : découvrir après coup qu'on ne voit qu'un
  // seul chantier passerait pour une panne.
  const panelDescription = preview?.projetId
    ? 'Vous rejoignez un projet de travaux précis : ses aides, ses dossiers et ses documents, ainsi que la fiche du monument en lecture. Les autres chantiers de ce monument ne vous seront pas accessibles.'
    : 'Vous pourrez consulter le monument et ses projets de travaux, suivre les aides et y déposer vos documents, aux côtés des autres intervenants.';

  return (
    <AuthLayout panelEyebrow="Invitation à collaborer" panelHeadline={panelHeadline} panelDescription={panelDescription}>
      {/* contexte (visible aussi sur mobile, où le panneau bleu est masqué) */}
      <div className="space-y-3">
        <p className="text-[15px]" style={{ color: MUTED }}>
          <strong style={{ color: C.ink }}>{preview.inviterNom}</strong> vous invite à collaborer sur
        </p>
        <h1 className="text-[26px] leading-[1.15]" style={{ fontFamily: SERIF, color: C.ink }}>
          «&nbsp;{preview.monumentNom}&nbsp;»
        </h1>
        {preview.projetTitre && (
          <p className="text-[14px]" style={{ color: MUTED }}>
            Sur le projet de travaux{' '}
            <strong style={{ color: C.orange }}>{preview.projetTitre}</strong>, et lui seul.
          </p>
        )}
        <p className="text-[14px]" style={{ color: LIGHT }}>
          Vous rejoignez en tant que <strong style={{ color: C.blue }}>collaborateur</strong>.
        </p>
      </div>

      {user ? (
        <PrimaryButton onClick={handleJoinLoggedIn} busy={busy}>Rejoindre le monument</PrimaryButton>
      ) : mode === 'choice' ? (
        <div className="flex flex-col gap-2.5">
          <PrimaryButton onClick={() => setMode('signup')}>Je crée mon compte</PrimaryButton>
          <SecondaryButton onClick={() => setMode('login')}>J'ai déjà un compte</SecondaryButton>
        </div>
      ) : mode === 'oauth' ? (
        <div className="flex flex-col gap-4">
          <div
            className="flex items-start gap-2.5 rounded-xl p-4 text-[14px] leading-[1.55]"
            style={{ background: 'var(--secondary)', color: C.ink }}
          >
            <Check className="mt-0.5 h-4 w-4 flex-shrink-0" style={{ color: SUCCESS }} />
            <span>
              Connecté avec Google
              {oauthEmail ? (
                <>
                  {' '}
                  (<span className="font-semibold">{oauthEmail}</span>)
                </>
              ) : null}
              . Indiquez votre rôle et vous rejoignez le monument.
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Prénom" htmlFor="inv-oauth-prenom">
              <Input id="inv-oauth-prenom" value={form.prenom} onChange={(e) => setForm({ ...form, prenom: e.target.value })} className={INPUT_CLS} />
            </FormField>
            <FormField label="Nom" htmlFor="inv-oauth-nom">
              <Input id="inv-oauth-nom" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} className={INPUT_CLS} />
            </FormField>
          </div>
          <FormField label="Votre rôle sur le monument" htmlFor="inv-oauth-metier">
            <MetierSelect value={form.metier} onChange={(v) => setForm({ ...form, metier: v })} />
          </FormField>
          <FormField label="Téléphone (optionnel)" htmlFor="inv-oauth-tel">
            <Input id="inv-oauth-tel" type="tel" value={form.telephone} onChange={(e) => setForm({ ...form, telephone: e.target.value })} className={INPUT_CLS} />
          </FormField>
          <CguConsent checked={acceptCgu} onChange={setAcceptCgu} />
          <PrimaryButton onClick={handleOauthSignup} busy={busy}>Rejoindre le monument</PrimaryButton>
        </div>
      ) : mode === 'signup' ? (
        <div className="flex flex-col gap-4">
          <GoogleButton
            label="Continuer avec Google"
            beforeRedirect={() => setPendingInvitation(token)}
          />
          <div className="flex items-center gap-3" aria-hidden="true">
            <span className="h-px flex-1" style={{ background: C.border }} />
            <span className="text-[13px] whitespace-nowrap" style={{ color: LIGHT }}>
              ou avec votre adresse email
            </span>
            <span className="h-px flex-1" style={{ background: C.border }} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Prénom" htmlFor="inv-prenom">
              <Input id="inv-prenom" value={form.prenom} onChange={(e) => setForm({ ...form, prenom: e.target.value })} className={INPUT_CLS} />
            </FormField>
            <FormField label="Nom" htmlFor="inv-nom">
              <Input id="inv-nom" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} className={INPUT_CLS} />
            </FormField>
          </div>
          <FormField label="Email" htmlFor="inv-email">
            <Input id="inv-email" type="email" value={form.email} disabled className={`${INPUT_CLS} disabled:bg-muted disabled:text-muted-foreground`} />
          </FormField>
          <FormField label="Mot de passe" htmlFor="inv-password">
            <Input id="inv-password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={INPUT_CLS} />
            {form.password && (
              <div className="flex flex-wrap gap-x-4 gap-y-0.5 pt-1">
                {PASSWORD_RULES.map(({ key, label }) => {
                  const ok = passwordChecks(form.password)[key];
                  return (
                    <div key={key} className="flex items-center gap-1.5 text-[12px]" style={{ color: ok ? SUCCESS : LIGHT }}>
                      {ok ? <Check className="h-3 w-3 flex-shrink-0" /> : <X className="h-3 w-3 flex-shrink-0" />}
                      {label}
                    </div>
                  );
                })}
              </div>
            )}
          </FormField>
          <FormField label="Votre rôle sur le monument" htmlFor="inv-metier">
            <MetierSelect value={form.metier} onChange={(v) => setForm({ ...form, metier: v })} />
          </FormField>
          <FormField label="Téléphone (optionnel)" htmlFor="inv-tel">
            <Input id="inv-tel" value={form.telephone} onChange={(e) => setForm({ ...form, telephone: e.target.value })} className={INPUT_CLS} />
          </FormField>
          <CguConsent checked={acceptCgu} onChange={setAcceptCgu} />
          <PrimaryButton onClick={handleSignup} busy={busy}>Créer mon compte et rejoindre</PrimaryButton>
          <BackLink onClick={() => setMode('choice')} />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <FormField label="Email" htmlFor="inv-login-email">
            <Input id="inv-login-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={INPUT_CLS} />
          </FormField>
          <FormField label="Mot de passe" htmlFor="inv-login-password">
            <Input id="inv-login-password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={INPUT_CLS} />
          </FormField>
          <PrimaryButton onClick={handleLogin} busy={busy}>Se connecter et rejoindre</PrimaryButton>
          <BackLink onClick={() => setMode('choice')} />
        </div>
      )}

      <p className="text-[12px]" style={{ color: LIGHT }}>Invitation valable jusqu'au {expires}.</p>
    </AuthLayout>
  );
}

function Heading({ children }: { children: React.ReactNode }) {
  return (
    <h1 className="text-[26px] leading-[1.15]" style={{ fontFamily: SERIF, color: C.ink }}>
      {children}
    </h1>
  );
}

function FormField({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor} className="text-[14px] font-medium" style={{ color: C.ink }}>{label}</Label>
      {children}
    </div>
  );
}

function PrimaryButton({ onClick, busy, children }: { onClick: () => void; busy?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className="group flex h-12 w-full items-center justify-center gap-2 rounded-lg text-[14px] font-semibold text-white transition-opacity duration-200 hover:opacity-90 disabled:opacity-50"
      style={{ background: C.orange }}
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : (
        <>
          {children}
          <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
        </>
      )}
    </button>
  );
}

function SecondaryButton({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-12 w-full rounded-lg border text-[14px] font-medium transition-colors hover:bg-card"
      style={{ borderColor: C.border, color: C.blue }}
    >
      {children}
    </button>
  );
}

function BackLink({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="self-center text-[13px] underline underline-offset-2" style={{ color: C.orange }}>
      Retour
    </button>
  );
}
