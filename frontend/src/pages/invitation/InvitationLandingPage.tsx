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
import { ConfirmerEmail } from '@/components/auth/ConfirmerEmail';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { passwordChecks, isPasswordValid, PASSWORD_RULES } from '@/lib/password';
import { setPendingInvitation } from '@/lib/pending-invitation';
import { ApiError } from '@/lib/api-error';
import { toast } from 'sonner';
import { Trans, useTranslation } from 'react-i18next';
import { localeIntl } from '@/i18n/format';

const SUCCESS = 'var(--success)';
import type { InvitationPreview } from '@/types';

type Mode = 'choice' | 'signup' | 'login' | 'oauth';

const MUTED = 'var(--muted-foreground)';
const LIGHT = 'var(--muted-foreground)';
const INPUT_CLS = 'h-12 text-[17px] bg-card border-border focus:border-primary focus:ring-primary/10';

// Pages légales, servies par la landing (monumia.fr).
const CGU_URL = 'https://monumia.fr/cgu';
const PRIVACY_URL = 'https://monumia.fr/confidentialite';

/* Acceptation des CGU : requise pour toute création de compte,
   formulaire email comme retour de Google. */
function CguConsent({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  const { t } = useTranslation('compte');
  const linkCls = 'font-medium underline underline-offset-2';
  return (
    <label className="flex cursor-pointer items-start gap-2.5">
      <Checkbox checked={checked} onCheckedChange={(v) => onChange(v === true)} className="mt-[3px]" />
      <span className="text-[15px] leading-[1.55]" style={{ color: MUTED }}>
        <Trans
          t={t}
          i18nKey="commun.cgu"
          components={{
            cgu: <a href={CGU_URL} target="_blank" rel="noopener noreferrer" className={linkCls} style={{ color: C.blue }} />,
            confidentialite: <a href={PRIVACY_URL} target="_blank" rel="noopener noreferrer" className={linkCls} style={{ color: C.blue }} />,
          }}
        />
      </span>
    </label>
  );
}

export function InvitationLandingPage() {
  const { t } = useTranslation('compte');
  const { token = '' } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setAuth = useAuthStore((s) => s.setAuth);
  const logout = useAuthStore((s) => s.logout);

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
  // Confirmation d'email exigée : le compte est créé mais sans session, donc
  // l'invitation ne peut pas être acceptée tout de suite. Le lien de
  // confirmation ramène ici (`invitation` transmis au serveur), et le bouton
  // « Rejoindre » attendra la personne, connectée.
  const [emailAConfirmer, setEmailAConfirmer] = useState<{
    email: string;
    // Ce qui a mené là : l'inscription (le compte vient d'être créé) ou la
    // connexion (compte plus ancien, jamais confirmé). Le message diffère.
    variante: 'inscription' | 'connexion';
  } | null>(null);

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
      .catch((e) => setError(e instanceof Error ? e.message : t('InvitationLandingPage.introuvable')));
  }, [token, t]);

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
      toast.error(e instanceof Error ? e.message : t('InvitationLandingPage.impossibleRejoindre'));
    } finally {
      setBusy(false);
    }
  };

  const handleSignup = async () => {
    if (!isPasswordValid(form.password)) {
      toast.error(t('commun.motDePasseInvalide'));
      return;
    }
    if (!form.metier) {
      toast.error(t('InvitationLandingPage.indiquerRole'));
      return;
    }
    if (!acceptCgu) {
      toast.error(t('commun.accepterCgu'));
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
        invitation: token,
      });
      if (!access_token) {
        setEmailAConfirmer({ email: form.email, variante: 'inscription' });
        return;
      }
      setAuth(u, access_token);
      await acceptAndGo();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : t('InvitationLandingPage.echecInscription'));
    } finally {
      setBusy(false);
    }
  };

  const handleOauthSignup = async () => {
    if (!form.metier) {
      toast.error(t('InvitationLandingPage.indiquerRole'));
      return;
    }
    if (!form.prenom.trim() || !form.nom.trim()) {
      toast.error(t('InvitationLandingPage.renseignerNom'));
      return;
    }
    if (!acceptCgu) {
      toast.error(t('commun.accepterCgu'));
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
      toast.error(e instanceof Error ? e.message : t('InvitationLandingPage.echecInscription'));
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
      // 403 : identifiants bons, adresse pas encore confirmée. Le renvoi de
      // l'email est le seul chemin de sortie, un toast rouge n'en donnerait
      // aucun.
      if (e instanceof ApiError && e.status === 403) {
        setEmailAConfirmer({ email: form.email, variante: 'connexion' });
        return;
      }
      toast.error(e instanceof Error ? e.message : t('InvitationLandingPage.connexionImpossible'));
    } finally {
      setBusy(false);
    }
  };

  // ── États non nominaux ──
  if (emailAConfirmer) {
    return (
      <AuthLayout panelEyebrow={t('InvitationLandingPage.eyebrow')}>
        <ConfirmerEmail
          email={emailAConfirmer.email}
          intention={{ invitation: token }}
          variante={emailAConfirmer.variante}
        >
          <p className="text-center text-[15px] leading-[1.6]" style={{ color: C.grayMuted }}>
            {preview?.projetTitre
              ? t('InvitationLandingPage.resteValableProjet', { projet: preview.projetTitre })
              : preview
                ? t('InvitationLandingPage.resteValableNom', { monument: preview.monumentNom })
                : t('InvitationLandingPage.resteValableMonument')}
          </p>
        </ConfirmerEmail>
      </AuthLayout>
    );
  }
  if (error) {
    return (
      <AuthLayout panelEyebrow={t('InvitationLandingPage.eyebrow')}>
        <Heading>{t('InvitationLandingPage.introuvable')}</Heading>
        <p className="text-[17px]" style={{ color: C.danger }}>{error}</p>
        <p className="text-[16px]" style={{ color: LIGHT }}>
          {t('InvitationLandingPage.demanderNouveauLien')}
        </p>
      </AuthLayout>
    );
  }
  if (!preview) {
    return (
      <AuthLayout panelEyebrow={t('InvitationLandingPage.eyebrow')}>
        <div className="flex items-center justify-center py-10">
          <Loader2 className="h-6 w-6 animate-spin" style={{ color: LIGHT }} />
        </div>
      </AuthLayout>
    );
  }
  if (preview.status !== 'pending') {
    return (
      <AuthLayout panelEyebrow={t('InvitationLandingPage.eyebrow')}>
        <Heading>{t('InvitationLandingPage.expiree')}</Heading>
        <p className="text-[17px]" style={{ color: C.danger }}>{t('InvitationLandingPage.plusValide')}</p>
        <p className="text-[16px]" style={{ color: LIGHT }}>
          {t('InvitationLandingPage.expireeDetail')}
        </p>
      </AuthLayout>
    );
  }

  const expires = new Date(preview.expiresAt).toLocaleDateString(localeIntl(), { day: 'numeric', month: 'long', year: 'numeric' });

  // Le libellé suit la portée : rejoindre « le monument » quand l'invitation ne
  // donne qu'un chantier annoncerait plus que ce qui s'ouvre.
  const libelleRejoindre = preview.projetId ? t('InvitationLandingPage.rejoindreProjet') : t('InvitationLandingPage.rejoindreMonument');

  // Le serveur refuse l'acceptation depuis un autre compte que le destinataire
  // (`invitation_destinee_a`) : le dire avant le clic plutôt qu'en toast.
  const emailCompte = user ? user.email : mode === 'oauth' ? oauthEmail : null;
  const autreCompte =
    !!emailCompte && emailCompte.trim().toLowerCase() !== preview.email.trim().toLowerCase();

  const panelHeadline = (
    <Trans
      t={t}
      i18nKey="InvitationLandingPage.panneauTitre"
      values={{ inviteur: preview.inviterNom, monument: preview.monumentNom }}
      components={{
        inviteur: <span className="font-normal" />,
        br: <br />,
        accent: <span style={{ color: C.orange }} />,
      }}
    />
  );
  // Dire la portée AVANT d'accepter : découvrir après coup qu'on ne voit qu'un
  // seul chantier passerait pour une panne.
  const panelDescription = preview?.projetId
    ? t('InvitationLandingPage.panneauProjet')
    : t('InvitationLandingPage.panneauMonument');

  return (
    <AuthLayout panelEyebrow={t('InvitationLandingPage.eyebrowCollaborer')} panelHeadline={panelHeadline} panelDescription={panelDescription}>
      {/* contexte (visible aussi sur mobile, où le panneau bleu est masqué) */}
      <div className="space-y-3">
        <p className="text-[17px]" style={{ color: MUTED }}>
          <Trans
            t={t}
            i18nKey="InvitationLandingPage.inviteSur"
            values={{ inviteur: preview.inviterNom }}
            components={{ gras: <strong style={{ color: C.ink }} /> }}
          />
        </p>
        <h1 className="text-[30px] leading-[1.15]" style={{ fontFamily: SERIF, color: C.ink }}>
          {t('InvitationLandingPage.nomMonument', { monument: preview.monumentNom })}
        </h1>
        {preview.projetTitre && (
          <p className="text-[16px]" style={{ color: MUTED }}>
            <Trans
              t={t}
              i18nKey="InvitationLandingPage.surProjet"
              values={{ projet: preview.projetTitre }}
              components={{ accent: <strong style={{ color: C.orange }} /> }}
            />
          </p>
        )}
        <p className="text-[16px]" style={{ color: LIGHT }}>
          <Trans
            t={t}
            i18nKey="InvitationLandingPage.enTantQue"
            components={{ accent: <strong style={{ color: C.blue }} /> }}
          />
        </p>
      </div>

      {autreCompte ? (
        <div className="flex flex-col gap-4">
          <div
            className="rounded-xl p-4 text-[16px] leading-[1.55]"
            style={{ background: 'var(--secondary)', color: C.ink }}
          >
            <Trans
              t={t}
              i18nKey="InvitationLandingPage.autreCompte"
              values={{ compte: emailCompte, destinataire: preview.email }}
              components={{ gras: <span className="font-semibold" /> }}
            />
          </div>
          <SecondaryButton
            onClick={() => {
              if (user) logout();
              clearOAuthSession();
              setMode('choice');
            }}
          >
            {t('InvitationLandingPage.changerCompte')}
          </SecondaryButton>
        </div>
      ) : user ? (
        <PrimaryButton onClick={handleJoinLoggedIn} busy={busy}>{libelleRejoindre}</PrimaryButton>
      ) : mode === 'choice' ? (
        <div className="flex flex-col gap-2.5">
          <PrimaryButton onClick={() => setMode('signup')}>{t('InvitationLandingPage.jeCreeMonCompte')}</PrimaryButton>
          <SecondaryButton onClick={() => setMode('login')}>{t('InvitationLandingPage.dejaUnCompte')}</SecondaryButton>
        </div>
      ) : mode === 'oauth' ? (
        <div className="flex flex-col gap-4">
          <div
            className="flex items-start gap-2.5 rounded-xl p-4 text-[16px] leading-[1.55]"
            style={{ background: 'var(--secondary)', color: C.ink }}
          >
            <Check className="mt-0.5 h-4 w-4 flex-shrink-0" style={{ color: SUCCESS }} />
            <span>
              <Trans
                t={t}
                i18nKey={
                  oauthEmail
                    ? preview.projetId
                      ? 'InvitationLandingPage.googleAvecEmailProjet'
                      : 'InvitationLandingPage.googleAvecEmailMonument'
                    : preview.projetId
                      ? 'InvitationLandingPage.googleProjet'
                      : 'InvitationLandingPage.googleMonument'
                }
                values={{ email: oauthEmail ?? '' }}
                components={{ gras: <span className="font-semibold" /> }}
              />
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <FormField label={t('commun.prenom')} htmlFor="inv-oauth-prenom">
              <Input id="inv-oauth-prenom" value={form.prenom} onChange={(e) => setForm({ ...form, prenom: e.target.value })} className={INPUT_CLS} />
            </FormField>
            <FormField label={t('commun.nom')} htmlFor="inv-oauth-nom">
              <Input id="inv-oauth-nom" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} className={INPUT_CLS} />
            </FormField>
          </div>
          <FormField label={t('InvitationLandingPage.votreRole')} htmlFor="inv-oauth-metier">
            <MetierSelect value={form.metier} onChange={(v) => setForm({ ...form, metier: v })} />
          </FormField>
          <FormField label={t('InvitationLandingPage.telephoneOptionnel')} htmlFor="inv-oauth-tel">
            <Input id="inv-oauth-tel" type="tel" value={form.telephone} onChange={(e) => setForm({ ...form, telephone: e.target.value })} className={INPUT_CLS} />
          </FormField>
          <CguConsent checked={acceptCgu} onChange={setAcceptCgu} />
          <PrimaryButton onClick={handleOauthSignup} busy={busy}>{libelleRejoindre}</PrimaryButton>
        </div>
      ) : mode === 'signup' ? (
        <div className="flex flex-col gap-4">
          <GoogleButton
            beforeRedirect={() => setPendingInvitation(token)}
          />
          <div className="flex items-center gap-3" aria-hidden="true">
            <span className="h-px flex-1" style={{ background: C.border }} />
            <span className="text-[15px] whitespace-nowrap" style={{ color: LIGHT }}>
              {t('commun.ouAvecEmail')}
            </span>
            <span className="h-px flex-1" style={{ background: C.border }} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <FormField label={t('commun.prenom')} htmlFor="inv-prenom">
              <Input id="inv-prenom" value={form.prenom} onChange={(e) => setForm({ ...form, prenom: e.target.value })} className={INPUT_CLS} />
            </FormField>
            <FormField label={t('commun.nom')} htmlFor="inv-nom">
              <Input id="inv-nom" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} className={INPUT_CLS} />
            </FormField>
          </div>
          <FormField label={t('commun.email')} htmlFor="inv-email">
            <Input id="inv-email" type="email" value={form.email} disabled className={`${INPUT_CLS} disabled:bg-muted disabled:text-muted-foreground`} />
          </FormField>
          <FormField label={t('commun.motDePasse')} htmlFor="inv-password">
            <Input id="inv-password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={INPUT_CLS} />
            {form.password && (
              <div className="flex flex-wrap gap-x-4 gap-y-0.5 pt-1">
                {PASSWORD_RULES.map(({ key, label }) => {
                  const ok = passwordChecks(form.password)[key];
                  return (
                    <div key={key} className="flex items-center gap-1.5 text-[14px]" style={{ color: ok ? SUCCESS : LIGHT }}>
                      {ok ? <Check className="h-3 w-3 flex-shrink-0" /> : <X className="h-3 w-3 flex-shrink-0" />}
                      {label}
                    </div>
                  );
                })}
              </div>
            )}
          </FormField>
          <FormField label={t('InvitationLandingPage.votreRole')} htmlFor="inv-metier">
            <MetierSelect value={form.metier} onChange={(v) => setForm({ ...form, metier: v })} />
          </FormField>
          <FormField label={t('InvitationLandingPage.telephoneOptionnel')} htmlFor="inv-tel">
            <Input id="inv-tel" value={form.telephone} onChange={(e) => setForm({ ...form, telephone: e.target.value })} className={INPUT_CLS} />
          </FormField>
          <CguConsent checked={acceptCgu} onChange={setAcceptCgu} />
          <PrimaryButton onClick={handleSignup} busy={busy}>{t('InvitationLandingPage.creerEtRejoindre')}</PrimaryButton>
          <BackLink onClick={() => setMode('choice')} />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <FormField label={t('commun.email')} htmlFor="inv-login-email">
            <Input id="inv-login-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={INPUT_CLS} />
          </FormField>
          <FormField label={t('commun.motDePasse')} htmlFor="inv-login-password">
            <Input id="inv-login-password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={INPUT_CLS} />
          </FormField>
          <PrimaryButton onClick={handleLogin} busy={busy}>{t('InvitationLandingPage.connecterEtRejoindre')}</PrimaryButton>
          <BackLink onClick={() => setMode('choice')} />
        </div>
      )}

      <p className="text-[14px]" style={{ color: LIGHT }}>{t('InvitationLandingPage.valableJusquau', { date: expires })}</p>
    </AuthLayout>
  );
}

function Heading({ children }: { children: React.ReactNode }) {
  return (
    <h1 className="text-[30px] leading-[1.15]" style={{ fontFamily: SERIF, color: C.ink }}>
      {children}
    </h1>
  );
}

function FormField({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor} className="text-[16px] font-medium" style={{ color: C.ink }}>{label}</Label>
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
      className="group flex h-12 w-full items-center justify-center gap-2 rounded-lg text-[16px] font-semibold text-white transition-opacity duration-200 hover:opacity-90 disabled:opacity-50"
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
      className="h-12 w-full rounded-lg border text-[16px] font-medium transition-colors hover:bg-card"
      style={{ borderColor: C.border, color: C.blue }}
    >
      {children}
    </button>
  );
}

function BackLink({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation();
  return (
    <button type="button" onClick={onClick} className="self-center text-[15px] underline underline-offset-2" style={{ color: C.orange }}>
      {t('actions.retour')}
    </button>
  );
}
