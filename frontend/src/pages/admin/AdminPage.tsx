import { useCallback, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { toast } from 'sonner';
import { IconTendance } from '@/components/icons';
import { PageHeader } from '@/components/shared/PageHeader';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AdminAidesPanel } from '@/components/admin/AdminAidesPanel';
import { AdminConditionsPanel } from '@/components/admin/AdminConditionsPanel';
import { AdminFaitsPanel } from '@/components/admin/AdminFaitsPanel';
import { AdminRolesPanel } from '@/components/admin/AdminRolesPanel';
import { ApiError } from '@/lib/api-error';
import { C } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';

/**
 * Administration du catalogue : retirer une aide, reformuler une question,
 * modifier le critère d'une condition — et dire qui a la main sur tout cela,
 * ou simplement l'offre le temps d'un bêta-test.
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
   * Un 403 veut dire que le compte n'est (plus) administrateur côté serveur,
   * alors que le profil chargé disait l'inverse — un autre fondateur vient de
   * l'en retirer, par exemple. On sort de la page plutôt que de laisser
   * l'utilisateur devant des panneaux vides.
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
        action={
          /* Vers la même matière, vue par les nombres : où le catalogue couvre,
             où il est creux. Lecture seule, d'où le bouton discret plutôt qu'un
             quatrième onglet — ce n'est pas un geste d'administration de plus. */
          <Link
            to={ROUTES.ADMIN_STATS}
            className="inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-[14px] font-medium transition-colors hover:bg-[var(--secondary)]"
            style={{ borderColor: C.border, color: C.blue }}
          >
            <IconTendance className="h-4 w-4" />
            Le catalogue en chiffres
          </Link>
        }
      />

      <Tabs value={onglet} onValueChange={setOnglet}>
        <TabsList>
          <TabsTrigger value="aides">Aides</TabsTrigger>
          <TabsTrigger value="questions">Questions</TabsTrigger>
          <TabsTrigger value="conditions">Conditions</TabsTrigger>
          <TabsTrigger value="roles">Rôles</TabsTrigger>
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

        <TabsContent value="roles" className="mt-4">
          <AdminRolesPanel onErreur={signalerErreur} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
