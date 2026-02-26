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
import { mockUsers } from '@/data/mock-users';

export function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const updateProfile = useAuthStore((s) => s.updateProfile);
  const updateNotificationPreferences = useAuthStore((s) => s.updateNotificationPreferences);
  const { isCommune, isPrive } = useSegmentLabel();

  // Auto-login for demo
  if (!user) {
    setUser(mockUsers[0]);
  }

  const currentUser = user ?? mockUsers[0];

  const [form, setForm] = useState({
    prenom: currentUser.prenom,
    nom: currentUser.nom,
    email: currentUser.email,
    telephone: currentUser.telephone ?? '',
  });

  const handleSave = () => {
    updateProfile({
      prenom: form.prenom,
      nom: form.nom,
      email: form.email,
      telephone: form.telephone || undefined,
    });
    toast.success('Profil mis à jour');
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
            <Button onClick={handleSave}>
              <Save className="h-4 w-4 mr-2" />
              Enregistrer
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
                <InfoRow label="Fonction" value={currentUser.commune.fonction} />
              </>
            )}

            {isPrive && currentUser.prive && (
              <>
                <InfoRow label="Type" value={currentUser.prive.typeProprietaire} />
                {currentUser.prive.regimeFiscal && (
                  <InfoRow label="Régime fiscal" value={currentUser.prive.regimeFiscal} />
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
              checked={currentUser.notificationPreferences.urgentDeadlines}
              onChange={(v) => updateNotificationPreferences({ urgentDeadlines: v })}
            />
            <Separator />
            <NotifToggle
              label="Nouvelles aides identifiées"
              description="Quand une nouvelle aide correspond à votre monument"
              checked={currentUser.notificationPreferences.newAidesMatched}
              onChange={(v) => updateNotificationPreferences({ newAidesMatched: v })}
            />
            <Separator />
            <NotifToggle
              label="Mises à jour des dossiers"
              description="Progression des dossiers et actions de collaborateurs"
              checked={currentUser.notificationPreferences.dossierUpdates}
              onChange={(v) => updateNotificationPreferences({ dossierUpdates: v })}
            />
            <Separator />
            <NotifToggle
              label="Notifications par email"
              description="Recevoir les notifications par email en plus de l'application"
              checked={currentUser.notificationPreferences.emailNotifications}
              onChange={(v) => updateNotificationPreferences({ emailNotifications: v })}
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
