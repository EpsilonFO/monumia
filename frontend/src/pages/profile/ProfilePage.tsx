import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { toast } from 'sonner';
import { Trans, useTranslation } from 'react-i18next';
import {
  IconEnregistrer,
  IconCompte,
  IconContact,
  IconTelephone,
  IconProtection,
  IconSucces,
  IconDeconnexion,
  IconReglages,
  IconEcheance,
} from '@/components/icons';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { OffreUpsell } from '@/components/shared/OffreUpsell';
import { useOffre } from '@/hooks/useOffre';
import { C, SERIF } from '@/lib/brand';
import { computeProfileCompletion } from '@/lib/profile-completion';
import { clePostHog, enregistrerRefusMesure, mesureRefusee } from '@/lib/mesure-audience';
import { authService } from '@/services/auth.service';
import { useAuthStore } from '@/stores/useAuthStore';
import { isValidPhone } from '@/lib/phone';
import { ROUTES } from '@/constants/routes';
import { RAPPEL_DELAIS_DEFAUT, type NotificationPreferences } from '@/types';
import { SelecteurLangue } from '@/i18n/SelecteurLangue';

export function ProfilePage() {
  const { t } = useTranslation(['compte', 'common']);
  const user = useAuthStore((s) => s.user);
  const updateProfile = useAuthStore((s) => s.updateProfile);
  const logout = useAuthStore((s) => s.logout);
  const reinitialiserGuides = useAuthStore((s) => s.reinitialiserGuides);
  const navigate = useNavigate();

  const [form, setForm] = useState({
    prenom: user?.prenom ?? '',
    nom: user?.nom ?? '',
    telephone: user?.telephone ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [resetState, setResetState] = useState<'idle' | 'sending' | 'sent'>('idle');

  if (!user) return null;
  const currentUser = user;
  const completion = computeProfileCompletion(currentUser);

  const handlePhoneChange = (value: string) => {
    setForm({ ...form, telephone: value });
    setPhoneError(value && !isValidPhone(value) ? t('ProfilePage.numeroInvalide') : null);
  };

  const handleSave = async () => {
    if (!isValidPhone(form.telephone)) {
      setPhoneError(t('ProfilePage.numeroInvalide'));
      return;
    }
    setSaving(true);
    try {
      await updateProfile({
        prenom: form.prenom,
        nom: form.nom,
        telephone: form.telephone || undefined,
      });
      toast.success(t('ProfilePage.profilMisAJour'));
    } catch (e: any) {
      toast.error(e.message || t('ProfilePage.erreurMiseAJour'));
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setResetState('sending');
    try {
      await authService.requestPasswordReset(currentUser.email);
      setResetState('sent');
      toast.success(t('ProfilePage.emailEnvoye'));
    } catch (e: any) {
      setResetState('idle');
      toast.error(e.message || t('ProfilePage.erreurEnvoiEmail'));
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const hour = new Date().getHours();
  const salutation =
    hour < 12
      ? 'ProfilePage.salutationMatin'
      : hour < 18
        ? 'ProfilePage.salutationApresMidi'
        : 'ProfilePage.salutationSoir';
  const initials = `${currentUser.prenom?.[0] ?? ''}${currentUser.nom?.[0] ?? ''}`.toUpperCase();
  const complete = completion.percent >= 100;

  const inputCls =
    'h-11 text-[17px] bg-card border-border focus:border-primary focus:ring-primary/10 font-sans';

  return (
    <div className="flex flex-col gap-5">
      {/* ═════════ CARTE IDENTITÉ — tout au même endroit, modifiable ═════════ */}
      <section className="overflow-hidden rounded-2xl border border-border">
        {/* Bandeau : jauge + accueil */}
        <div
          className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center sm:gap-7 sm:px-8"
          style={{ background: 'linear-gradient(120deg, var(--secondary) 0%, var(--card) 62%)' }}
        >
          <span
            className="flex h-[100.5px] w-[100.5px] shrink-0 items-center justify-center rounded-full text-[30px] font-semibold"
            style={{ background: C.paleBlue, color: C.blue, fontFamily: SERIF }}
          >
            {initials || <IconCompte className="h-9 w-9" />}
          </span>

          <div className="min-w-0 flex-1">
            <span
              className="inline-flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.2em]"
              style={{ color: C.blue }}
            >
              <span aria-hidden style={{ width: 25, height: 2, borderRadius: 2, background: C.orange }} />
              {t('ProfilePage.monEspace')}
            </span>
            <h1
              className="mt-1.5 text-[clamp(1.7rem,3.5vw,2.4rem)] leading-[1.05]"
              style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
            >
              <Trans
                t={t}
                i18nKey={salutation}
                values={{ prenom: currentUser.prenom }}
                components={{ accent: <span style={{ color: C.blue }} /> }}
              />
            </h1>

            <div className="mt-3 flex flex-wrap items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 text-[14.5px]" style={{ color: C.grayMuted }}>
                <IconSucces className="h-3.5 w-3.5" style={{ color: complete ? C.orange : C.grayMuted }} />
                {complete ? t('ProfilePage.profilComplet') : t('ProfilePage.profilPresqueComplet')}
              </span>
            </div>
          </div>
        </div>

        {/* Corps : formulaire modifiable */}
        <div className="space-y-5 border-t border-border bg-card px-6 py-6 sm:px-8">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="prenom" label={t('commun.prenom')} icon={<IconCompte className="h-4 w-4" />}>
              <Input id="prenom" value={form.prenom} onChange={(e) => setForm({ ...form, prenom: e.target.value })} className={inputCls} />
            </Field>
            <Field id="nom" label={t('commun.nom')} icon={<IconCompte className="h-4 w-4" />}>
              <Input id="nom" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} className={inputCls} />
            </Field>
            <Field id="telephone" label={t('ProfilePage.telephone')} icon={<IconTelephone className="h-4 w-4" />}>
              <Input
                id="telephone"
                value={form.telephone}
                onChange={(e) => handlePhoneChange(e.target.value)}
                placeholder={t('ProfilePage.placeholderTelephone')}
                className={`${inputCls}${phoneError ? ' border-destructive focus:border-destructive focus:ring-destructive/10' : ''}`}
              />
              {phoneError && <p className="mt-1 text-[14px] text-destructive">{phoneError}</p>}
              {!form.telephone && !phoneError && (
                <p className="mt-1 text-[14px]" style={{ color: C.grayMuted }}>
                  {t('ProfilePage.telephoneRecommande')}
                </p>
              )}
            </Field>
            <Field id="email" label={t('ProfilePage.adresseEmail')} icon={<IconContact className="h-4 w-4" />} hint={t('ProfilePage.nonModifiable')}>
              <div className="flex h-11 items-center rounded-md border border-dashed border-border bg-[var(--secondary)]/40 px-3 text-[17px] text-muted-foreground">
                <span className="truncate">{currentUser.email}</span>
              </div>
            </Field>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button
              onClick={handleSave}
              disabled={saving || !!phoneError}
              className="inline-flex items-center gap-2 rounded-xl px-6 py-3 text-[16px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: C.blue }}
            >
              <IconEnregistrer className="h-4 w-4" strokeWidth={1.8} />
              {saving ? t('common:etats.enregistrement') : t('ProfilePage.enregistrerInformations')}
            </button>
            <span className="text-[14.5px]" style={{ color: C.grayMuted }}>
              {t('ProfilePage.informationsPrivees')}
            </span>
          </div>
        </div>
      </section>

      <RappelsPanel />

      <MesureAudiencePanel />

      <Panel>
        <PanelHeader
          icon={<IconProtection className="h-4 w-4 text-primary" strokeWidth={1.8} />}
          title={t('ProfilePage.securite')}
        />
        <div className="px-6 py-5">
          {resetState === 'sent' ? (
            <div className="flex items-start gap-3 rounded-xl p-4" style={{ background: C.paleBlue }}>
              <IconSucces className="mt-0.5 h-5 w-5 shrink-0" style={{ color: C.blue }} />
              <div className="text-[16px]" style={{ color: C.ink }}>
                <p className="font-medium">{t('ProfilePage.emailEnvoyeA', { email: currentUser.email })}</p>
                <p className="mt-1" style={{ color: C.grayFg }}>
                  {t('ProfilePage.ouvrirLien')}
                </p>
                <button onClick={handleReset} className="mt-2 text-[15px] font-medium underline" style={{ color: C.blue }}>
                  {t('ProfilePage.renvoyerEmail')}
                </button>
              </div>
            </div>
          ) : (
            <>
              <p className="text-[16px]" style={{ color: C.grayFg }}>
                {t('ProfilePage.securiteIntro')}
              </p>
              <button
                onClick={handleReset}
                disabled={resetState === 'sending'}
                className="mt-3 inline-flex items-center gap-2 rounded-xl border px-5 py-3 text-[16px] font-semibold transition-colors hover:bg-[var(--secondary)] disabled:opacity-50"
                style={{ borderColor: C.border, color: C.blue }}
              >
                <IconContact className="h-4 w-4" />
                {resetState === 'sending' ? t('ProfilePage.envoiEnCours') : t('ProfilePage.recevoirLien')}
              </button>
            </>
          )}
        </div>
      </Panel>

      {/* ═════════ LANGUE ═════════ */}
      <Panel>
        <PanelHeader
          icon={<IconReglages className="h-4 w-4 text-primary" strokeWidth={1.8} />}
          title={t('common:langue.libelle')}
        />
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-5">
          <p className="text-[16px]" style={{ color: C.grayFg }}>
            {t('ProfilePage.langueIntro')}
          </p>
          <SelecteurLangue className="text-[16px]" />
        </div>
      </Panel>

      {/* ═════════ VISITES GUIDÉES ═════════ */}
      <Panel>
        <PanelHeader
          icon={<IconReglages className="h-4 w-4 text-primary" strokeWidth={1.8} />}
          title={t('ProfilePage.visites')}
        />
        <div className="px-6 py-5">
          <p className="text-[16px]" style={{ color: C.grayFg }}>
            {t('ProfilePage.visitesIntro')}
          </p>
          <button
            type="button"
            onClick={() => {
              reinitialiserGuides()
                .then(() => toast.success(t('ProfilePage.visitesReinitialisees')))
                .catch(() => toast.error(t('ProfilePage.visitesErreur')));
            }}
            className="mt-3 inline-flex items-center gap-2 rounded-xl border px-5 py-3 text-[16px] font-semibold transition-colors hover:bg-[var(--secondary)]"
            style={{ borderColor: C.border, color: C.blue }}
          >
            {t('ProfilePage.revoirVisites')}
          </button>
        </div>
      </Panel>

      {/* ═════════ ADMINISTRATION ═════════
          Discrète et réservée : la seule porte vers `/admin`, qui ne figure
          dans aucune navigation. Les onglets de l'application sont les mêmes
          pour tout le monde, une page d'exploitation n'a rien à y faire. */}
      {currentUser.estAdmin && (
        <Panel>
          <PanelHeader
            icon={<IconReglages className="h-4 w-4 text-primary" strokeWidth={1.8} />}
            title={t('ProfilePage.administration')}
          />
          <div className="px-6 py-5">
            <p className="text-[16px]" style={{ color: C.grayFg }}>
              {t('ProfilePage.administrationIntro')}
            </p>
            <Link
              to={ROUTES.ADMIN}
              className="mt-3 inline-flex items-center gap-2 rounded-xl border px-5 py-3 text-[16px] font-semibold transition-colors hover:bg-[var(--secondary)]"
              style={{ borderColor: C.border, color: C.blue }}
            >
              <IconReglages className="h-4 w-4" />
              {t('ProfilePage.ouvrirAdministration')}
            </Link>
          </div>
        </Panel>
      )}

      {/* ═════════ DÉCONNEXION ═════════ */}
      <div className="pb-2">
        <button
          onClick={handleLogout}
          className="inline-flex items-center gap-2 rounded-xl border px-5 py-3 text-[16px] font-medium transition-colors hover:bg-[var(--destructive-muted)]"
          style={{ borderColor: C.border, color: C.danger }}
        >
          <IconDeconnexion className="h-4 w-4" />
          {t('common:actions.seDeconnecter')}
        </button>
      </div>
    </div>
  );
}

/* ── Rappels par email ── */

/**
 * Paliers proposés, en jours avant la date limite. Une liste fermée plutôt
 * qu'un champ libre : le besoin réel tient en quelques crans, et des pastilles
 * à cocher évitent la saisie invalide que le backend refuserait.
 */
const PALIERS_PROPOSES = [60, 30, 15, 7, 3, 1];

function RappelsPanel() {
  const { t } = useTranslation('compte');
  const user = useAuthStore((s) => s.user);
  const save = useAuthStore((s) => s.updateNotificationPreferences);
  // Les emails sont vendus avec Veille et Multi-monuments. Sur l'offre
  // gratuite, les réglages restent visibles et modifiables (ils prendront
  // effet avec l'offre), et un bandeau dit ce qui manque.
  const rappelsInclus = useOffre().rappelsEmail;
  // Optimiste : la bascule doit répondre tout de suite, l'appel suit. En cas
  // d'échec on repart de la valeur du store, qui n'a pas bougé.
  const [pending, setPending] = useState<Partial<NotificationPreferences> | null>(null);

  if (!user) return null;
  const prefs = { ...user.notificationPreferences, ...pending };
  const delais = prefs.rappelDelaisJours?.length ? prefs.rappelDelaisJours : RAPPEL_DELAIS_DEFAUT;

  const patch = async (updates: Partial<NotificationPreferences>) => {
    setPending((p) => ({ ...p, ...updates }));
    try {
      await save(updates);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : t('ProfilePage.reglageNonEnregistre'));
    } finally {
      setPending(null);
    }
  };

  const toggleDelai = (jours: number) => {
    const actif = delais.includes(jours);
    // Retirer le dernier palier reviendrait à couper les rappels sans le dire :
    // c'est l'interrupteur au-dessus qui sert à ça.
    if (actif && delais.length === 1) {
      toast.info(t('ProfilePage.garderUnRappel'));
      return;
    }
    const suivant = actif ? delais.filter((d) => d !== jours) : [...delais, jours];
    patch({ rappelDelaisJours: suivant.sort((a, b) => b - a) });
  };

  return (
    <Panel>
      <PanelHeader
        icon={<IconEcheance className="h-4 w-4 text-primary" strokeWidth={1.8} />}
        title={t('ProfilePage.rappels')}
      />
      {!rappelsInclus && (
        <div className="px-6 pt-5">
          <OffreUpsell offre="Veille" action={t('ProfilePage.rappelsUpsell')} />
        </div>
      )}
      <div className="divide-y divide-border">
        <Reglage
          titre={t('ProfilePage.echeances')}
          description={t('ProfilePage.echeancesDescription')}
          checked={prefs.rappelsEcheances}
          onChange={(v) => patch({ rappelsEcheances: v })}
        >
          <p className="mb-2 text-[15px]" style={{ color: C.grayFg }}>
            {t('ProfilePage.mePrevenir')}
          </p>
          <div className="flex flex-wrap gap-2">
            {PALIERS_PROPOSES.map((jours) => {
              const actif = delais.includes(jours);
              return (
                <button
                  key={jours}
                  type="button"
                  onClick={() => toggleDelai(jours)}
                  aria-pressed={actif}
                  className="rounded-full border px-3.5 py-1.5 text-[15px] font-medium transition-colors"
                  style={
                    actif
                      ? { borderColor: C.blue, background: C.paleBlue, color: C.blue }
                      : { borderColor: C.border, color: C.grayMuted }
                  }
                >
                  {t('ProfilePage.joursAvant', { count: jours })}
                </button>
              );
            })}
          </div>
        </Reglage>

        <Reglage
          titre={t('ProfilePage.ouvertures')}
          description={t('ProfilePage.ouverturesDescription')}
          checked={prefs.rappelsOuvertures}
          onChange={(v) => patch({ rappelsOuvertures: v })}
        />
      </div>
    </Panel>
  );
}

/* ── Mesure d'audience ── */

/**
 * L'opposition à la mesure anonyme (cf. `lib/mesure-audience.ts`). Absent d'un
 * build sans PostHog : on ne propose pas de refuser ce qui n'a pas lieu.
 */
function MesureAudiencePanel() {
  const { t } = useTranslation('compte');
  const [refusee, setRefusee] = useState(mesureRefusee);
  if (!clePostHog()) return null;

  return (
    <Panel>
      <PanelHeader
        icon={<IconProtection className="h-4 w-4 text-primary" strokeWidth={1.8} />}
        title={t('ProfilePage.mesureAudience')}
      />
      <Reglage
        titre={t('ProfilePage.statistiques')}
        description={t('ProfilePage.statistiquesDescription')}
        checked={!refusee}
        onChange={(participe) => {
          enregistrerRefusMesure(!participe);
          setRefusee(!participe);
        }}
      />
    </Panel>
  );
}

function Reglage({ titre, description, checked, onChange, children }: {
  titre: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  children?: React.ReactNode;
}) {
  return (
    <div className="px-6 py-5">
      <div className="flex items-start justify-between gap-5">
        <div className="min-w-0">
          <p className="text-[16.5px] font-medium text-foreground">{titre}</p>
          <p className="mt-1 text-[15px]" style={{ color: C.grayFg }}>
            {description}
          </p>
        </div>
        <Switch checked={checked} onCheckedChange={onChange} aria-label={titre} />
      </div>
      {checked && children && <div className="mt-4">{children}</div>}
    </div>
  );
}

/* ── Sous-composants ── */

function Field({ id, label, icon, hint, children }: {
  id: string; label: string; icon: React.ReactNode; hint?: string; children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <Label htmlFor={id} className="flex items-center gap-1.5 text-[15px] font-medium text-foreground">
          <span style={{ color: C.blue }}>{icon}</span>
          {label}
        </Label>
        {hint && <span className="text-[13.5px]" style={{ color: C.grayMuted }}>{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return <div className="overflow-hidden rounded-2xl border border-border bg-card">{children}</div>;
}

function PanelHeader({ icon, title, tint = 'blue' }: { icon: React.ReactNode; title: string; tint?: 'blue' | 'warning' }) {
  return (
    <div className="flex items-center gap-3 border-b border-border px-6 py-4">
      <span
        className={`flex h-8 w-8 items-center justify-center rounded-lg ${tint === 'warning' ? 'bg-warning-muted' : 'bg-secondary'}`}
      >
        {icon}
      </span>
      <h3 className="text-[19px]" style={{ fontFamily: SERIF, color: C.ink }}>{title}</h3>
    </div>
  );
}

