import { useMemo } from 'react';
import { Link } from 'react-router';
import {
  Landmark, FileText, Sparkles, Calendar, Bell,
  AlertTriangle, ArrowRight, ChevronRight,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { PageHeader } from '@/components/shared/PageHeader';
import { NotificationItem } from '@/components/notification/NotificationItem';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useNotificationStore } from '@/stores/useNotificationStore';
import { useDeadlines } from '@/hooks/useDeadlines';
import { ROUTES } from '@/constants/routes';
import { DOSSIER_STATUS_LABELS } from '@/constants/dossier-steps';
import { formatDate, deadlineLabel } from '@/lib/date-utils';
import { cn } from '@/lib/utils';
import { mockUsers } from '@/data/mock-users';

export function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const monuments = useMonumentStore((s) => s.monuments);
  const dossiers = useDossierStore((s) => s.dossiers);
  const notifications = useNotificationStore((s) => s.notifications);
  const markAsRead = useNotificationStore((s) => s.markAsRead);
  const deadlines = useDeadlines();

  // Auto-login for demo: pick first mock user if none
  if (!user) {
    setUser(mockUsers[0]);
  }

  const currentUser = user ?? mockUsers[0];

  const userMonuments = useMemo(
    () => monuments.filter((m) => m.userId === currentUser.id),
    [monuments, currentUser.id]
  );

  const userDossiers = useMemo(
    () => dossiers.filter((d) => d.userId === currentUser.id),
    [dossiers, currentUser.id]
  );

  const activeDossiers = useMemo(
    () => userDossiers.filter((d) => d.statut !== 'soumis'),
    [userDossiers]
  );

  const userNotifications = useMemo(
    () => notifications
      .filter((n) => n.userId === currentUser.id)
      .sort((a, b) => new Date(b.dateCreation).getTime() - new Date(a.dateCreation).getTime())
      .slice(0, 5),
    [notifications, currentUser.id]
  );

  const unreadCount = useMemo(
    () => notifications.filter((n) => n.userId === currentUser.id && !n.lue).length,
    [notifications, currentUser.id]
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Bonjour, ${currentUser.prenom}`}
        description="Vue d'ensemble de vos monuments et dossiers"
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          icon={Landmark}
          label="Monuments"
          value={userMonuments.length}
          linkTo={ROUTES.MONUMENTS}
        />
        <KPICard
          icon={FileText}
          label="Dossiers actifs"
          value={activeDossiers.length}
          linkTo={ROUTES.DOSSIERS}
        />
        <KPICard
          icon={Calendar}
          label="Échéances proches"
          value={deadlines.filter((d) => d.estUrgent).length}
          variant={deadlines.some((d) => d.estUrgent) ? 'warning' : 'default'}
        />
        <KPICard
          icon={Bell}
          label="Notifications"
          value={unreadCount}
          variant={unreadCount > 0 ? 'accent' : 'default'}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Actions + Dossiers */}
        <div className="lg:col-span-2 space-y-6">
          {/* Priority actions */}
          {deadlines.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  Actions prioritaires
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {deadlines.slice(0, 3).map((d) => {
                  const dl = deadlineLabel(d.date);
                  return (
                    <Link key={d.id} to={ROUTES.DOSSIER_DETAIL(d.dossierId)}>
                      <div className="flex items-center justify-between p-2.5 rounded-lg border hover:bg-muted/50 transition-colors">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium truncate">
                            {d.label}
                          </p>
                          <p className="text-xs text-muted-foreground truncate">
                            {d.dossierTitre}
                          </p>
                        </div>
                        <Badge
                          className={cn(
                            'shrink-0 ml-2',
                            dl.urgency === 'urgent' && 'bg-red-100 text-red-700',
                            dl.urgency === 'warning' && 'bg-amber-100 text-amber-700',
                            dl.urgency === 'normal' && 'bg-gray-100 text-gray-700',
                          )}
                        >
                          {dl.text}
                        </Badge>
                      </div>
                    </Link>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {/* Active dossiers */}
          <Card>
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-base">Dossiers en cours</CardTitle>
              <Button asChild variant="ghost" size="sm">
                <Link to={ROUTES.DOSSIERS}>
                  Voir tous
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              {activeDossiers.length === 0 ? (
                <div className="text-center py-6">
                  <FileText className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">Aucun dossier en cours</p>
                  <Button asChild variant="outline" size="sm" className="mt-2">
                    <Link to={ROUTES.AIDES}>
                      <Sparkles className="h-4 w-4 mr-1" />
                      Lancer un diagnostic
                    </Link>
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {activeDossiers.slice(0, 4).map((d) => {
                    const statusConfig = DOSSIER_STATUS_LABELS[d.statut];
                    return (
                      <Link key={d.id} to={ROUTES.DOSSIER_DETAIL(d.id)}>
                        <div className="flex items-center gap-3 p-2.5 rounded-lg border hover:bg-muted/50 transition-colors">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium truncate">
                              {d.titre}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge className={cn('text-xs', statusConfig?.color)}>
                                {statusConfig?.label}
                              </Badge>
                              <span className="text-xs text-muted-foreground">
                                Étape {d.etapeActuelle}/5
                              </span>
                            </div>
                          </div>
                          <div className="w-20 shrink-0">
                            <Progress value={d.progressionPourcentage} className="h-1.5" />
                            <p className="text-xs text-muted-foreground text-right mt-0.5">
                              {d.progressionPourcentage} %
                            </p>
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Monuments overview */}
          <Card>
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-base">Mes monuments</CardTitle>
              <Button asChild variant="ghost" size="sm">
                <Link to={ROUTES.MONUMENTS}>
                  Voir tous
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {userMonuments.slice(0, 3).map((m) => (
                  <Link key={m.id} to={ROUTES.MONUMENT_DETAIL(m.id)}>
                    <div className="flex items-center gap-3 p-2.5 rounded-lg border hover:bg-muted/50 transition-colors">
                      <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center shrink-0">
                        <Landmark className="h-4 w-4 text-primary" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{m.nom}</p>
                        <p className="text-xs text-muted-foreground">
                          {m.commune} — {m.protection}
                        </p>
                      </div>
                      <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                    </div>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right column: Notifications */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Bell className="h-4 w-4" />
                Notifications
                {unreadCount > 0 && (
                  <Badge variant="default" className="text-xs">
                    {unreadCount}
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {userNotifications.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  Aucune notification
                </p>
              ) : (
                userNotifications.map((n) => (
                  <NotificationItem
                    key={n.id}
                    notification={n}
                    onRead={markAsRead}
                  />
                ))
              )}
            </CardContent>
          </Card>

          {/* Quick actions */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Actions rapides</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to={ROUTES.AIDES}>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Diagnostic d'aides
                </Link>
              </Button>
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to="/onboarding/monument">
                  <Landmark className="h-4 w-4 mr-2" />
                  Ajouter un monument
                </Link>
              </Button>
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to={ROUTES.DOCUMENTS}>
                  <FileText className="h-4 w-4 mr-2" />
                  Gérer les documents
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

interface KPICardProps {
  icon: typeof Landmark;
  label: string;
  value: number;
  linkTo?: string;
  variant?: 'default' | 'warning' | 'accent';
}

function KPICard({ icon: Icon, label, value, linkTo, variant = 'default' }: KPICardProps) {
  const card = (
    <Card className={cn(
      'transition-all',
      linkTo && 'hover:shadow-md hover:border-primary/30 cursor-pointer',
    )}>
      <CardContent className="pt-5 pb-4">
        <div className="flex items-center gap-3">
          <div className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center',
            variant === 'default' && 'bg-primary/10',
            variant === 'warning' && 'bg-amber-100',
            variant === 'accent' && 'bg-accent/20',
          )}>
            <Icon className={cn(
              'h-5 w-5',
              variant === 'default' && 'text-primary',
              variant === 'warning' && 'text-amber-600',
              variant === 'accent' && 'text-accent',
            )} />
          </div>
          <div>
            <p className="text-2xl font-bold">{value}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  if (linkTo) return <Link to={linkTo}>{card}</Link>;
  return card;
}
