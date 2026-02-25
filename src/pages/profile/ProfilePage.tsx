import { PageHeader } from '@/components/shared/PageHeader';

export function ProfilePage() {
  return (
    <div>
      <PageHeader
        title="Mon profil"
        description="Gérez vos informations et préférences"
      />
      <p className="text-muted-foreground">Profil utilisateur à venir.</p>
    </div>
  );
}
