import { useState } from 'react';
import { Save, User, Bell, Building2, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { PageHeader } from '@/components/shared/PageHeader';
import { useAuthStore } from '@/stores/useAuthStore';
import { useSegmentLabel } from '@/hooks/useSegment';
import { toast } from 'sonner';

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
    email: currentUser.email,
    telephone: currentUser.telephone ?? '',
  });

  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateProfile({
        prenom: form.prenom,
        nom: form.nom,
        email: form.email,
        telephone: form.telephone || undefined,
      });
      toast.success('Profil mis à jour');
    } catch (e: any) {
      toast.error(e.message || 'Erreur lors de la mise à jour');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mon profil"
        description="Gérez vos informations et préférences"
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Personal info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <User className="h-4 w-4" />
              Informations personnelles
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="prenom">Prénom</Label>
                <Input
                  id="prenom"
                  value={form.prenom}
                  onChange={(e) => setForm({ ...form, prenom: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="nom">Nom</Label>
                <Input
                  id="nom"
                  value={form.nom}
                  onChange={(e) => setForm({ ...form, nom: e.target.value })}
                />
              </div>
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="telephone">Téléphone</Label>
              <Input
                id="telephone"
                value={form.telephone}
                onChange={(e) => setForm({ ...form, telephone: e.target.value })}
              />
            </div>
            <Button onClick={handleSave} disabled={saving}>
              <Save className="h-4 w-4 mr-2" />
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </CardContent>
        </Card>

        {/* Segment info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              {isCommune ? <Building2 className="h-4 w-4" /> : <Home className="h-4 w-4" />}
              {isCommune ? 'Ma commune' : 'Mon profil propriétaire'}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Segment :</span>
              <Badge variant="outline">
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
          </CardContent>
        </Card>

        {/* Notification preferences */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Bell className="h-4 w-4" />
              Préférences de notification
            </CardTitle>
            <CardDescription>
              Choisissez les notifications que vous souhaitez recevoir
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <NotifToggle
              label="Échéances urgentes"
              description="Alertes quand une date limite approche"
              checked={notifPrefs.urgentDeadlines}
              onChange={(v) => updateNotifPref({ urgentDeadlines: v })}
            />
            <Separator />
            <NotifToggle
              label="Nouvelles aides identifiées"
              description="Quand une nouvelle aide correspond à votre monument"
              checked={notifPrefs.newAidesMatched}
              onChange={(v) => updateNotifPref({ newAidesMatched: v })}
            />
            <Separator />
            <NotifToggle
              label="Mises à jour des dossiers"
              description="Progression des dossiers et actions de collaborateurs"
              checked={notifPrefs.dossierUpdates}
              onChange={(v) => updateNotifPref({ dossierUpdates: v })}
            />
            <Separator />
            <NotifToggle
              label="Notifications par email"
              description="Recevoir les notifications par email en plus de l'application"
              checked={notifPrefs.emailNotifications}
              onChange={(v) => updateNotifPref({ emailNotifications: v })}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2 text-sm">
      <span className="text-muted-foreground">{label} :</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function NotifToggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}
