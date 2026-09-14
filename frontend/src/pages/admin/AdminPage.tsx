import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';
import { PageHeader } from '@/components/shared/PageHeader';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AdminAidesPanel } from '@/components/admin/AdminAidesPanel';
import { AdminConditionsPanel } from '@/components/admin/AdminConditionsPanel';
import { AdminFaitsPanel } from '@/components/admin/AdminFaitsPanel';
import { ApiError } from '@/lib/api-error';
import { ROUTES } from '@/constants/routes';

/**
 * Administration du catalogue : retirer une aide, reformuler une question,
 * modifier le critère d'une condition.
 *
 * Hors de `/app/...` et absente de la navigation : c'est une page
 * d'exploitation pour les deux fondateurs, pas une fonctionnalité du produit.
 * On y arrive par le lien discret de la page Profil.
 *
 * Les modifications prennent effet au PROCHAIN chargement de page des
 * utilisateurs : le serveur invalide son cache dès l'enregistrement, et les
 * pages recalculent leur diagnostic à chaque montage. Rien à pousser.
 */
export function AdminPage() {
  const navigate = useNavigate();
  const [onglet, setOnglet] = useState('aides');

  /**
   * Un 403 veut dire que le compte n'est (plus) dans `ADMIN_USER_IDS` côté
   * serveur, alors que le profil chargé disait l'inverse. On sort de la page
   * plutôt que de laisser l'utilisateur devant des panneaux vides.
   */
  const signalerErreur = useCallback(
    (err: unknown, repli: string) => {
      if (err instanceof ApiError && err.status === 403) {
        toast.error('Accès réservé à l’administration');
        navigate(ROUTES.DASHBOARD, { replace: true });
        return;
      }
      toast.error(err instanceof Error ? err.message : repli);
    },
    [navigate],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Administration du catalogue"
        description="Retirer une aide du catalogue, reformuler une question du questionnaire, modifier le critère d’une condition. Les modifications s’appliquent au prochain chargement de page des utilisateurs."
      />

      <Tabs value={onglet} onValueChange={setOnglet}>
        <TabsList>
          <TabsTrigger value="aides">Aides</TabsTrigger>
          <TabsTrigger value="questions">Questions</TabsTrigger>
          <TabsTrigger value="conditions">Conditions</TabsTrigger>
        </TabsList>

        <TabsContent value="aides" className="mt-4">
          <AdminAidesPanel onErreur={signalerErreur} />
        </TabsContent>

        <TabsContent value="questions" className="mt-4">
          <AdminFaitsPanel onErreur={signalerErreur} />
        </TabsContent>

        <TabsContent value="conditions" className="mt-4">
          <AdminConditionsPanel onErreur={signalerErreur} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
