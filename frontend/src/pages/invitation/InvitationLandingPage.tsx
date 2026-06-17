import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { Loader2, ArrowRight } from 'lucide-react';
import { invitationService } from '@/services/invitation.service';
import { authService } from '@/services/auth.service';
import { useAuthStore } from '@/stores/useAuthStore';
import { MetierSelect } from '@/components/sharing/MetierSelect';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { toast } from 'sonner';
import type { InvitationPreview } from '@/types';

type Mode = 'choice' | 'signup' | 'login';

const MUTED = '#5c6472';
const LIGHT = '#8c92a0';
const INPUT_CLS = 'h-12 text-[15px] bg-white border-[#ece3d2] focus:border-[#0a369d] focus:ring-[#0a369d]/10';

export function InvitationLandingPage() {
  const { token = '' } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setAuth = useAuthStore((s) => s.setAuth);

  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>('choice');
  const [busy, setBusy] = useState(false);

  const [form, setForm] = useState({ prenom: '', nom: '', email: '', password: '', metier: '', telephone: '' });

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
    const { monumentId } = await invitationService.accept(token);
    navigate(ROUTES.PROJET_DETAIL(monumentId));
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
    if (!form.metier) {
      toast.error('Indiquez votre rôle sur le projet');
      return;
    }
    setBusy(true);
    try {
      const { user: u, access_token, refresh_token } = await authService.registerCollaborator({
        email: form.email,
        password: form.password,
        prenom: form.prenom,
        nom: form.nom,
        metier: form.metier,
        telephone: form.telephone || undefined,
      });
      setAuth(u, access_token, refresh_token);
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
      const { user: u, access_token, refresh_token } = await authService.login({
        email: form.email,
        password: form.password,
      });
      setAuth(u, access_token, refresh_token);
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
  const panelDescription = 'Vous pourrez consulter le projet, suivre les aides et y déposer vos documents, aux côtés des autres intervenants.';

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
        <p className="text-[14px]" style={{ color: LIGHT }}>
          Vous rejoignez en tant que <strong style={{ color: C.blue }}>collaborateur</strong>.
        </p>
      </div>

      {user ? (
        <PrimaryButton onClick={handleJoinLoggedIn} busy={busy}>Rejoindre le projet</PrimaryButton>
      ) : mode === 'choice' ? (
        <div className="flex flex-col gap-2.5">
          <PrimaryButton onClick={() => setMode('signup')}>Je crée mon compte</PrimaryButton>
          <SecondaryButton onClick={() => setMode('login')}>J'ai déjà un compte</SecondaryButton>
        </div>
      ) : mode === 'signup' ? (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Prénom" htmlFor="inv-prenom">
              <Input id="inv-prenom" value={form.prenom} onChange={(e) => setForm({ ...form, prenom: e.target.value })} className={INPUT_CLS} />
            </FormField>
            <FormField label="Nom" htmlFor="inv-nom">
              <Input id="inv-nom" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} className={INPUT_CLS} />
            </FormField>
          </div>
          <FormField label="Email" htmlFor="inv-email">
            <Input id="inv-email" type="email" value={form.email} disabled className={`${INPUT_CLS} disabled:bg-[#f3eee1] disabled:text-[#8c92a0]`} />
          </FormField>
          <FormField label="Mot de passe" htmlFor="inv-password">
            <Input id="inv-password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={INPUT_CLS} />
          </FormField>
          <FormField label="Votre rôle sur le projet" htmlFor="inv-metier">
            <MetierSelect value={form.metier} onChange={(v) => setForm({ ...form, metier: v })} />
          </FormField>
          <FormField label="Téléphone (optionnel)" htmlFor="inv-tel">
            <Input id="inv-tel" value={form.telephone} onChange={(e) => setForm({ ...form, telephone: e.target.value })} className={INPUT_CLS} />
          </FormField>
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
      className="h-12 w-full rounded-lg border text-[14px] font-medium transition-colors hover:bg-white"
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
