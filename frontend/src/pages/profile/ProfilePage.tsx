import { useState } from 'react';

const FR_PHONE_REGEX = /^(?:\+33|0033|0)[1-9](?:[\s.\-]?\d{2}){4}$/;
const isValidPhone = (v: string) => !v || FR_PHONE_REGEX.test(v.trim());
import { IconEnregistrer, IconNotification, IconMonument, IconMaison, IconCle, IconCompte } from '@/components/icons';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { PageHeader } from '@/components/shared/PageHeader';
import { useAuthStore } from '@/stores/useAuthStore';
import { useSegmentLabel } from '@/hooks/useSegment';
import { toast } from 'sonner';

const FONT = "'Cormorant Garamond', serif";

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
  const updateNotifPref = (prefs: Parameters<typeof _updateNotifPrefs>[0]) =>
    _updateNotifPrefs(prefs).catch((e: any) => toast.error(e.message || 'Erreur de mise à jour'));
  const { isCommune, isPrive } = useSegmentLabel();

  if (!user) return null;

  const currentUser = user;
  const notifPrefs = currentUser.notificationPreferences ?? DEFAULT_NOTIF_PREFS;

  const [form, setForm] = useState({
    prenom: currentUser.prenom,
    nom: currentUser.nom,
    telephone: currentUser.telephone ?? '',
  });

  const [saving, setSaving] = useState(false);
  const [phoneError, setPhoneError] = useState<string | null>(null);

  const handlePhoneChange = (value: string) => {
    setForm({ ...form, telephone: value });
    if (value && !isValidPhone(value)) {
      setPhoneError('Numéro invalide (ex : 06 12 34 56 78 ou +33 6 12 34 56 78)');
    } else {
      setPhoneError(null);
    }
  };

  const handleSave = async () => {
    if (!isValidPhone(form.telephone)) {
      setPhoneError('Numéro invalide (ex : 06 12 34 56 78 ou +33 6 12 34 56 78)');
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

  const inputCls = 'h-10 text-[14px] bg-card border-border focus:border-primary focus:ring-primary/10 font-sans';
  const labelCls = 'text-[13px] font-medium text-foreground font-sans';

  return (
    <div className="h-full flex flex-col gap-4">
      <PageHeader
        title="Mon profil"
        description="Gérez vos informations et préférences"
      />

      {/* ═══════ TOP: Personal info — full width ═══════ */}
      <Panel>
        <PanelHeader
          icon={<div className="w-7 h-7 rounded-lg bg-secondary flex items-center justify-center"><IconCompte className="h-4 w-4 text-primary" strokeWidth={1.8} /></div>}
          title="Informations personnelles"
        />
        <div className="px-6 py-4">
          <div className="flex gap-8">
            {/* Left column */}
            <div className="flex-1 space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label htmlFor="nom" className={labelCls}>Nom</Label>
                  <Input id="nom" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} className={inputCls} />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="prenom" className={labelCls}>Prénom</Label>
                  <Input id="prenom" value={form.prenom} onChange={(e) => setForm({ ...form, prenom: e.target.value })} className={inputCls} />
                </div>
              </div>
              <div className="space-y-1">
                <Label htmlFor="telephone" className={labelCls}>Téléphone</Label>
                <Input
                  id="telephone"
                  value={form.telephone}
                  onChange={(e) => handlePhoneChange(e.target.value)}
                  placeholder="06 12 34 56 78"
                  className={`${inputCls}${phoneError ? ' border-destructive focus:border-destructive focus:ring-destructive/10' : ''}`}
                />
                {phoneError && <p className="text-[12px] text-destructive mt-0.5">{phoneError}</p>}
              </div>
            </div>

            {/* Separator */}
            <div className="w-px bg-border self-stretch" />

            {/* Right column */}
            <div className="flex-1 space-y-3">
              <div className="space-y-1">
                <Label className={labelCls}>Email</Label>
                <p className="h-10 flex items-center text-[14px] text-foreground font-sans">{currentUser.email}</p>
              </div>
              <div className="space-y-1">
                <Label className={labelCls}>Mot de passe</Label>
                <button
                  className="w-full h-10 flex items-center justify-center gap-2 text-[13px] font-medium border border-border rounded-lg text-muted-foreground hover:bg-muted hover:border-accent/30 hover:text-accent transition-all duration-200 font-sans"
                >
                  <IconCle className="h-3.5 w-3.5" strokeWidth={1.8} />
                  Changer le mot de passe
                </button>
              </div>
            </div>
          </div>

          {/* Save button */}
          <div className="mt-4 pt-3 border-t border-border">
            <button
              onClick={handleSave}
              disabled={saving || !!phoneError}
              className="inline-flex items-center gap-2 px-6 py-2.5 text-[13px] font-semibold text-white rounded-lg transition-all duration-300 disabled:opacity-50 hover:shadow-md bg-primary"
            >
              <IconEnregistrer className="h-3.5 w-3.5" strokeWidth={1.8} />
              {saving ? 'Enregistrement…' : 'Enregistrer les modifications'}
            </button>
          </div>
        </div>
      </Panel>

      {/* ═══════ BOTTOM ROW: Commune + Notifications ═══════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1">
        {/* Segment info */}
        <Panel>
          <PanelHeader
            icon={
              <div className="w-7 h-7 rounded-lg bg-warning-muted flex items-center justify-center">
                {isCommune
                  ? <IconMonument className="h-4 w-4 text-accent" strokeWidth={1.8} />
                  : <IconMaison className="h-4 w-4 text-accent" strokeWidth={1.8} />}
              </div>
            }
            title={isCommune ? 'Ma commune' : 'Mon profil propriétaire'}
          />
          <div className="px-6 py-4 space-y-2.5 font-sans">
            <div className="flex items-center gap-2">
              <span className="text-[13px] text-muted-foreground font-sans">Segment :</span>
              <Badge variant="outline" className="text-[12px] border-border text-foreground font-sans">
                {isCommune ? 'Commune' : 'Propriétaire privé'}
              </Badge>
            </div>

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

        {/* Notification preferences — 2x2 grid with separator */}
        <Panel>
          <PanelHeader
            icon={<div className="w-7 h-7 rounded-lg bg-secondary flex items-center justify-center"><IconNotification className="h-4 w-4 text-primary" strokeWidth={1.8} /></div>}
            title="Préférences de notification"
          />
          <div className="px-6 py-4">
            <div className="flex gap-8">
              {/* Left column */}
              <div className="flex-1 space-y-3">
                <NotifToggle
                  label="Échéances urgentes"
                  description="Alertes quand une date limite approche"
                  checked={notifPrefs.urgentDeadlines}
                  onChange={(v) => updateNotifPref({ urgentDeadlines: v })}
                />
                <NotifToggle
                  label="Nouvelles aides identifiées"
                  description="Quand une aide correspond à votre monument"
                  checked={notifPrefs.newAidesMatched}
                  onChange={(v) => updateNotifPref({ newAidesMatched: v })}
                />
              </div>

              {/* Separator */}
              <div className="w-px bg-border self-stretch" />

              {/* Right column */}
              <div className="flex-1 space-y-3">
                <NotifToggle
                  label="Mises à jour des dossiers"
                  description="Progression et actions de collaborateurs"
                  checked={notifPrefs.dossierUpdates}
                  onChange={(v) => updateNotifPref({ dossierUpdates: v })}
                />
                <NotifToggle
                  label="Notifications par email"
                  description="Recevoir aussi les notifications par email"
                  checked={notifPrefs.emailNotifications}
                  onChange={(v) => updateNotifPref({ emailNotifications: v })}
                />
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-card rounded-xl border border-border/80 overflow-hidden flex flex-col">
      {children}
    </div>
  );
}

function PanelHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2.5 px-6 py-3 border-b border-border">
      {icon}
      <h3 className="text-[15px] font-normal text-foreground" style={{ fontFamily: FONT }}>{title}</h3>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2 text-[13px] font-sans">
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
        <p className="text-[13px] font-medium text-foreground font-sans">{label}</p>
        <p className="text-[12px] text-muted-foreground font-sans">{description}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}
