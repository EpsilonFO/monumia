import { useState } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';
import {
  IconEnregistrer,
  IconNotification,
  IconMaison,
  IconMonument,
  IconCompte,
  IconContact,
  IconTelephone,
  IconProtection,
  IconSucces,
  IconDeconnexion,
} from '@/components/icons';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { C, SERIF } from '@/lib/brand';
import { computeProfileCompletion } from '@/lib/profile-completion';
import { authService } from '@/services/auth.service';
import { useAuthStore } from '@/stores/useAuthStore';
import { useSegmentLabel } from '@/hooks/useSegment';

const FR_PHONE_REGEX = /^(?:\+33|0033|0)[1-9](?:[\s.\-]?\d{2}){4}$/;
const isValidPhone = (v: string) => !v || FR_PHONE_REGEX.test(v.trim());

const FONCTION_LABELS: Record<string, string> = {
  maire: 'Maire',
  adjoint_patrimoine: 'Adjoint au patrimoine',
  secretaire_mairie: 'Secrétaire de mairie',
  dgs: 'Directeur général des services',
  autre: 'Autre',
};
const TYPE_PROPRIETAIRE_LABELS: Record<string, string> = {
  personne_physique: 'Personne physique',
  sci: 'SCI',
  association: 'Association',
  autre: 'Autre',
};
const REGIME_FISCAL_LABELS: Record<string, string> = {
  monuments_historiques: 'Régime Monuments Historiques',
  droit_commun: 'Droit commun',
  mecenat: 'Mécénat',
};

const DEFAULT_NOTIF_PREFS = {
  urgentDeadlines: true,
  newAidesMatched: true,
  dossierUpdates: true,
  emailNotifications: false,
};

export function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const updateProfile = useAuthStore((s) => s.updateProfile);
  const _updateNotifPrefs = useAuthStore((s) => s.updateNotificationPreferences);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const { isCommune, isPrive } = useSegmentLabel();

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
  const notifPrefs = currentUser.notificationPreferences ?? DEFAULT_NOTIF_PREFS;
  const completion = computeProfileCompletion(currentUser);

  const updateNotifPref = (prefs: Parameters<typeof _updateNotifPrefs>[0]) =>
    _updateNotifPrefs(prefs).catch((e: any) => toast.error(e.message || 'Erreur de mise à jour'));

  const handlePhoneChange = (value: string) => {
    setForm({ ...form, telephone: value });
    setPhoneError(value && !isValidPhone(value) ? 'Numéro invalide (ex : 06 12 34 56 78)' : null);
  };

  const handleSave = async () => {
    if (!isValidPhone(form.telephone)) {
      setPhoneError('Numéro invalide (ex : 06 12 34 56 78)');
      return;
    }
    setSaving(true);
    try {
      await updateProfile({
        prenom: form.prenom,
        nom: form.nom,
        telephone: form.telephone || undefined,
      });
      toast.success('Profil mis à jour');
    } catch (e: any) {
      toast.error(e.message || 'Erreur lors de la mise à jour');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setResetState('sending');
    try {
      await authService.requestPasswordReset(currentUser.email);
      setResetState('sent');
      toast.success('Email envoyé');
    } catch (e: any) {
      setResetState('idle');
      toast.error(e.message || "Impossible d'envoyer l'email pour le moment");
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const initials = `${currentUser.prenom?.[0] ?? ''}${currentUser.nom?.[0] ?? ''}`.toUpperCase();
  const inputCls =
    'h-11 text-[15px] bg-card border-border focus:border-primary focus:ring-primary/10 font-sans';
  const labelCls = 'text-[13px] font-medium text-foreground font-sans';

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      {/* ─── EN-TÊTE éditorial ─── */}
      <div>
        <span
          className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: C.blue }}
        >
          <span aria-hidden style={{ width: 22, height: 2, borderRadius: 2, background: C.orange }} />
          Mon espace
        </span>
        <h1
          className="mt-2 text-[clamp(1.7rem,4vw,2.3rem)] leading-[1.1]"
          style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
        >
          Bonjour <span style={{ color: C.blue }}>{currentUser.prenom}</span>
        </h1>
      </div>

      {/* ─── CARTE DE MEMBRE + complétion ─── */}
      <div className="rounded-2xl border border-border bg-card p-6">
        <div className="flex items-center gap-4">
          <span
            className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full text-[22px] font-semibold"
            style={{ background: C.paleBlue, color: C.blue }}
          >
            {initials || <IconCompte className="h-7 w-7" />}
          </span>
          <div className="min-w-0">
            <p className="truncate text-[20px]" style={{ fontFamily: SERIF, color: C.ink }}>
              {currentUser.prenom} {currentUser.nom}
            </p>
            <Badge variant="outline" className="mt-1 border-border text-[12px] text-foreground">
              {isCommune ? 'Commune' : 'Propriétaire privé'}
            </Badge>
          </div>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <SummaryRow icon={<IconContact className="h-4 w-4" />} value={currentUser.email} />
          <SummaryRow
            icon={<IconTelephone className="h-4 w-4" />}
            value={currentUser.telephone || 'Téléphone non renseigné'}
            muted={!currentUser.telephone}
          />
        </div>

        {/* Nudge de complétion — sobre */}
        <div className="mt-5 border-t border-border pt-4">
          {completion.percent >= 100 ? (
            <p className="flex items-center gap-2 text-[13.5px] font-medium" style={{ color: C.blue }}>
              <IconSucces className="h-4 w-4" style={{ color: C.orange }} />
              Votre profil est complet. Merci !
            </p>
          ) : (
            <>
              <div className="flex items-center justify-between text-[13px]">
                <span className="font-medium text-foreground">Profil complété</span>
                <span style={{ color: C.blue }}>{completion.percent} %</span>
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full" style={{ background: C.paleBlue }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${completion.percent}%`, background: C.orange }}
                />
              </div>
              <p className="mt-2 text-[13px]" style={{ color: C.grayFg }}>
                Il ne manque plus que {completion.missing[0]} pour être joignable sur vos dossiers.
              </p>
            </>
          )}
        </div>
      </div>

      {/* ─── INFORMATIONS PERSONNELLES ─── */}
      <Panel>
        <PanelHeader
          icon={<IconCompte className="h-4 w-4 text-primary" strokeWidth={1.8} />}
          title="Vos informations"
        />
        <div className="space-y-4 px-6 py-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="nom" className={labelCls}>Nom</Label>
              <Input id="nom" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="prenom" className={labelCls}>Prénom</Label>
              <Input id="prenom" value={form.prenom} onChange={(e) => setForm({ ...form, prenom: e.target.value })} className={inputCls} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="telephone" className={labelCls}>Téléphone</Label>
            <Input
              id="telephone"
              value={form.telephone}
              onChange={(e) => handlePhoneChange(e.target.value)}
              placeholder="06 12 34 56 78"
              className={`${inputCls}${phoneError ? ' border-destructive focus:border-destructive focus:ring-destructive/10' : ''}`}
            />
            {phoneError && <p className="text-[12px] text-destructive">{phoneError}</p>}
          </div>
          <div className="space-y-1.5">
            <Label className={labelCls}>Adresse email</Label>
            <p className="flex h-11 items-center text-[15px] text-muted-foreground">{currentUser.email}</p>
          </div>
          <button
            onClick={handleSave}
            disabled={saving || !!phoneError}
            className="inline-flex items-center gap-2 rounded-xl px-6 py-3 text-[14px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            style={{ background: C.blue }}
          >
            <IconEnregistrer className="h-4 w-4" strokeWidth={1.8} />
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      </Panel>

      {/* ─── SEGMENT ─── */}
      <Panel>
        <PanelHeader
          icon={isCommune
            ? <IconMonument className="h-4 w-4 text-accent" strokeWidth={1.8} />
            : <IconMaison className="h-4 w-4 text-accent" strokeWidth={1.8} />}
          tint="warning"
          title={isCommune ? 'Ma commune' : 'Mon profil propriétaire'}
        />
        <div className="space-y-2.5 px-6 py-5">
          {isCommune && currentUser.commune && (
            <>
              <InfoRow label="Commune" value={currentUser.commune.nom} />
              <InfoRow label="Code INSEE" value={currentUser.commune.codeInsee} />
              <InfoRow label="Département" value={currentUser.commune.departement} />
              <InfoRow label="Population" value={`${currentUser.commune.population} hab.`} />
              <InfoRow label="Fonction" value={FONCTION_LABELS[currentUser.commune.fonction] ?? currentUser.commune.fonction} />
            </>
          )}
          {isPrive && currentUser.prive && (
            <>
              <InfoRow label="Type" value={TYPE_PROPRIETAIRE_LABELS[currentUser.prive.typeProprietaire] ?? currentUser.prive.typeProprietaire} />
              {currentUser.prive.regimeFiscal && (
                <InfoRow label="Régime fiscal" value={REGIME_FISCAL_LABELS[currentUser.prive.regimeFiscal] ?? currentUser.prive.regimeFiscal} />
              )}
            </>
          )}
        </div>
      </Panel>

      {/* ─── SÉCURITÉ ─── */}
      <Panel>
        <PanelHeader
          icon={<IconProtection className="h-4 w-4 text-primary" strokeWidth={1.8} />}
          title="Sécurité & connexion"
        />
        <div className="px-6 py-5">
          {resetState === 'sent' ? (
            <div className="flex items-start gap-3 rounded-xl p-4" style={{ background: C.paleBlue }}>
              <IconSucces className="mt-0.5 h-5 w-5 shrink-0" style={{ color: C.blue }} />
              <div className="text-[14px]" style={{ color: C.ink }}>
                <p className="font-medium">Un email vient d'être envoyé à {currentUser.email}.</p>
                <p className="mt-1" style={{ color: C.grayFg }}>
                  Ouvrez-le et cliquez sur le lien pour choisir un nouveau mot de passe. Pensez à vérifier vos courriers indésirables.
                </p>
                <button onClick={handleReset} className="mt-2 text-[13px] font-medium underline" style={{ color: C.blue }}>
                  Renvoyer l'email
                </button>
              </div>
            </div>
          ) : (
            <>
              <p className="text-[14px]" style={{ color: C.grayFg }}>
                Votre compte est protégé. Pour changer votre mot de passe, nous vous envoyons un lien
                sécurisé par email — rien à retenir.
              </p>
              <button
                onClick={handleReset}
                disabled={resetState === 'sending'}
                className="mt-3 inline-flex items-center gap-2 rounded-xl border px-5 py-3 text-[14px] font-semibold transition-colors hover:bg-[var(--secondary)] disabled:opacity-50"
                style={{ borderColor: C.border, color: C.blue }}
              >
                <IconContact className="h-4 w-4" />
                {resetState === 'sending' ? 'Envoi en cours…' : 'Recevoir un lien pour changer mon mot de passe'}
              </button>
            </>
          )}
        </div>
      </Panel>

      {/* ─── NOTIFICATIONS ─── */}
      <Panel>
        <PanelHeader
          icon={<IconNotification className="h-4 w-4 text-primary" strokeWidth={1.8} />}
          title="Vous prévenir"
        />
        <div className="space-y-4 px-6 py-5">
          <NotifToggle
            label="Échéances urgentes"
            description="Nous vous alertons quand une date limite approche."
            checked={notifPrefs.urgentDeadlines}
            onChange={(v) => updateNotifPref({ urgentDeadlines: v })}
          />
          <NotifToggle
            label="Nouvelles aides pour vous"
            description="Quand une aide correspond à votre monument."
            checked={notifPrefs.newAidesMatched}
            onChange={(v) => updateNotifPref({ newAidesMatched: v })}
          />
          <NotifToggle
            label="Suivi de vos dossiers"
            description="Progression et actions de vos collaborateurs."
            checked={notifPrefs.dossierUpdates}
            onChange={(v) => updateNotifPref({ dossierUpdates: v })}
          />
          <NotifToggle
            label="Recevoir aussi par email"
            description="En plus des notifications dans l'application."
            checked={notifPrefs.emailNotifications}
            onChange={(v) => updateNotifPref({ emailNotifications: v })}
          />
        </div>
      </Panel>

      {/* ─── DÉCONNEXION ─── */}
      <div className="pb-2">
        <button
          onClick={handleLogout}
          className="inline-flex items-center gap-2 rounded-xl border px-5 py-3 text-[14px] font-medium transition-colors hover:bg-[var(--destructive-muted)]"
          style={{ borderColor: C.border, color: C.danger }}
        >
          <IconDeconnexion className="h-4 w-4" />
          Se déconnecter
        </button>
      </div>
    </div>
  );
}

/* ── Sous-composants ── */

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
      <h3 className="text-[17px]" style={{ fontFamily: SERIF, color: C.ink }}>{title}</h3>
    </div>
  );
}

function SummaryRow({ icon, value, muted }: { icon: React.ReactNode; value: string; muted?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-[14px]" style={{ color: muted ? C.grayMuted : C.grayFg }}>
      <span style={{ color: C.blue }}>{icon}</span>
      <span className="truncate">{value}</span>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2 text-[14px]">
      <span className="text-muted-foreground">{label} :</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}

function NotifToggle({ label, description, checked, onChange }: {
  label: string; description: string; checked: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-[14px] font-medium text-foreground">{label}</p>
        <p className="text-[13px] text-muted-foreground">{description}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}
