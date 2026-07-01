import { useState } from 'react';
import { IconEnregistrer, IconCompte, IconNotification, IconChantier, IconLocalisation, IconReglages } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { PageHeader } from '@/components/shared/PageHeader';
import { useAuthStore } from '@/stores/useAuthStore';
import { toast } from 'sonner';

const SPECIALITE_LABELS: Record<string, string> = {
  maconnerie: 'Maçonnerie',
  charpente: 'Charpente',
  couverture: 'Couverture',
  restauration_pierre: 'Restauration pierre',
  peintures_murales: 'Peintures murales',
  vitraux: 'Vitraux',
  menuiserie: 'Menuiserie',
  electricite: 'Électricité',
  all: 'Toutes spécialités',
};

export function BtpProfilePage() {
  const user = useAuthStore((s) => s.user);
  const updateProfile = useAuthStore((s) => s.updateProfile);
  const _updateNotifPrefs = useAuthStore((s) => s.updateNotificationPreferences);
  const updateNotifPref = (prefs: Parameters<typeof _updateNotifPrefs>[0]) =>
    _updateNotifPrefs(prefs).catch((e: any) => toast.error(e.message || 'Erreur de mise à jour'));

  const [form, setForm] = useState({
    prenom: user?.prenom ?? '',
    nom: user?.nom ?? '',
    email: user?.email ?? '',
    telephone: user?.telephone ?? '',
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

  if (!user) return null;

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
              <IconCompte className="h-4 w-4" />
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
              <IconEnregistrer className="h-4 w-4 mr-2" />
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </CardContent>
        </Card>

        {/* BTP company info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <IconChantier className="h-4 w-4" />
              Mon entreprise
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {user.btp && (
              <>
                <div>
                  <p className="text-xs text-muted-foreground">Raison sociale</p>
                  <p className="font-semibold">{user.btp.raisonSociale}</p>
                </div>
                {user.btp.siret && (
                  <div>
                    <p className="text-xs text-muted-foreground">SIRET</p>
                    <p className="text-sm font-mono">{user.btp.siret}</p>
                  </div>
                )}
                {user.btp.effectifs && (
                  <div>
                    <p className="text-xs text-muted-foreground">Effectifs</p>
                    <Badge variant="outline">{user.btp.effectifs} salariés</Badge>
                  </div>
                )}

                <div>
                  <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                    <IconReglages className="h-3 w-3" />
                    Spécialités
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {user.btp.specialites.map((s) => (
                      <Badge key={s} variant="secondary" className="text-xs">
                        {SPECIALITE_LABELS[s] ?? s}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                    <IconLocalisation className="h-3 w-3" />
                    Zones d'intervention
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {user.btp.regions.map((r) => (
                      <Badge key={r} variant="outline" className="text-xs capitalize">
                        {r.replace(/-/g, ' ')}
                      </Badge>
                    ))}
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Notification preferences */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <IconNotification className="h-4 w-4" />
              Préférences de notification
            </CardTitle>
            <CardDescription>
              Choisissez les notifications que vous souhaitez recevoir
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <NotifToggle
              label="Nouvelles opportunités identifiées"
              description="Quand de nouveaux monuments avec financement identifié apparaissent dans vos zones"
              checked={user.notificationPreferences.newAidesMatched}
              onChange={(v) => updateNotifPref({ newAidesMatched: v })}
            />
            <Separator />
            <NotifToggle
              label="Relances prospects"
              description="Alertes pour les dates de prochain contact à prévoir"
              checked={user.notificationPreferences.urgentDeadlines}
              onChange={(v) => updateNotifPref({ urgentDeadlines: v })}
            />
            <Separator />
            <NotifToggle
              label="Mises à jour dossiers"
              description="Suivi des dossiers en cours pour vos prospects"
              checked={user.notificationPreferences.dossierUpdates}
              onChange={(v) => updateNotifPref({ dossierUpdates: v })}
            />
            <Separator />
            <NotifToggle
              label="Notifications par email"
              description="Recevoir les notifications par email en plus de l'application"
              checked={user.notificationPreferences.emailNotifications}
              onChange={(v) => updateNotifPref({ emailNotifications: v })}
            />
          </CardContent>
        </Card>
      </div>
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
