import { useMemo } from 'react';
import { Link } from 'react-router';
import {
  TrendingUp, Users, Euro, Target, ArrowRight,
  ChevronRight, AlertCircle, CheckCircle2, Clock, Phone,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { PageHeader } from '@/components/shared/PageHeader';
import { useAuthStore } from '@/stores/useAuthStore';
import { useProspectStore } from '@/stores/useProspectStore';
import { formatCurrency } from '@/lib/format-utils';
import { cn } from '@/lib/utils';
import type { ProspectStatus } from "@/types";

const STATUS_CONFIG: Record<ProspectStatus, { label: string; color: string; icon: typeof Clock }> = {
  a_contacter: { label: 'À contacter', color: 'bg-gray-100 text-gray-700', icon: Clock },
  contacte: { label: 'Contacté', color: 'bg-blue-100 text-blue-700', icon: Phone },
  en_discussion: { label: 'En discussion', color: 'bg-amber-100 text-amber-700', icon: Users },
  devis_envoye: { label: 'Devis envoyé', color: 'bg-purple-100 text-purple-700', icon: Target },
  gagne: { label: 'Gagné', color: 'bg-emerald-100 text-emerald-700', icon: CheckCircle2 },
  perdu: { label: 'Perdu', color: 'bg-red-100 text-red-700', icon: AlertCircle },
};

export function BtpDashboardPage() {
  const user = useAuthStore((s) => s.user);
  const prospects = useProspectStore((s) => s.prospects);

  const userProspects = useMemo(
    () => prospects.filter((p) => p.btpUserId === user?.id),
    [prospects, user?.id]
  );

  const stats = useMemo(() => {
    const actifs = userProspects.filter(
      (p) => !['gagne', 'perdu'].includes(p.statut)
    );
    const gagnes = userProspects.filter((p) => p.statut === 'gagne');
    const avecFinancement = userProspects.filter((p) => p.financementIdentifie);
    const caGagne = gagnes.reduce((sum, p) => sum + (p.montantTravaux ?? 0), 0);
    const caPotentiel = actifs.reduce((sum, p) => sum + (p.montantTravaux ?? 0), 0);
    const financementTotal = avecFinancement.reduce(
      (sum, p) => sum + p.totalFinancementPotentiel,
      0
    );
    return { actifs, gagnes, avecFinancement, caGagne, caPotentiel, financementTotal };
  }, [userProspects]);

  const urgentProspects = useMemo(
    () =>
      userProspects
        .filter((p) => p.dateProchainContact && !['gagne', 'perdu'].includes(p.statut))
        .sort(
          (a, b) =>
            new Date(a.dateProchainContact!).getTime() -
            new Date(b.dateProchainContact!).getTime()
        )
        .slice(0, 4),
    [userProspects]
  );

  const recentWins = useMemo(
    () => userProspects.filter((p) => p.statut === 'gagne').slice(0, 3),
    [userProspects]
  );

  const pipelineByStatus = useMemo(() => {
    const order: ProspectStatus[] = ['a_contacter', 'contacte', 'en_discussion', 'devis_envoye'];
    return order.map((status) => ({
      status,
      prospects: userProspects.filter((p) => p.statut === status),
    }));
  }, [userProspects]);

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Bonjour, ${user?.prenom ?? 'Thomas'}`}
        description={`${user?.btp?.raisonSociale ?? 'Votre entreprise'} — Vue d'ensemble de vos opportunités patrimoine`}
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          icon={Users}
          label="Prospects actifs"
          value={stats.actifs.length}
          sub={`${userProspects.length} au total`}
          variant="default"
          linkTo="/btp/prospects"
        />
        <KPICard
          icon={Euro}
          label="CA potentiel"
          value={formatCurrency(stats.caPotentiel)}
          sub="en cours de négociation"
          variant="accent"
        />
        <KPICard
          icon={TrendingUp}
          label="Financement identifié"
          value={formatCurrency(stats.financementTotal)}
          sub={`${stats.avecFinancement.length} monuments qualifiés`}
          variant="success"
        />
        <KPICard
          icon={CheckCircle2}
          label="Marchés gagnés"
          value={formatCurrency(stats.caGagne)}
          sub={`${stats.gagnes.length} contrat${stats.gagnes.length > 1 ? 's' : ''}`}
          variant="warning"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Pipeline + Actions urgentes */}
        <div className="lg:col-span-2 space-y-6">
          {/* Relances urgentes */}
          {urgentProspects.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-amber-500" />
                  Relances à prévoir
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {urgentProspects.map((p) => {
                  const conf = STATUS_CONFIG[p.statut];
                  const StatusIcon = conf.icon;
                  const daysUntil = p.dateProchainContact
                    ? Math.ceil(
                        (new Date(p.dateProchainContact).getTime() - Date.now()) /
                          (1000 * 60 * 60 * 24)
                      )
                    : null;
                  return (
                    <Link key={p.id} to={`/btp/prospects/${p.id}`}>
                      <div className="flex items-center justify-between p-2.5 rounded-lg border hover:bg-muted/50 transition-colors">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium truncate">{p.monumentNom}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <Badge className={cn('text-xs', conf.color)}>
                              <StatusIcon className="h-3 w-3 mr-1" />
                              {conf.label}
                            </Badge>
                            <span className="text-xs text-muted-foreground truncate">
                              {p.contactNom}
                            </span>
                          </div>
                        </div>
                        {daysUntil !== null && (
                          <Badge
                            className={cn(
                              'shrink-0 ml-2 text-xs',
                              daysUntil <= 3
                                ? 'bg-red-100 text-red-700'
                                : daysUntil <= 7
                                  ? 'bg-amber-100 text-amber-700'
                                  : 'bg-gray-100 text-gray-700'
                            )}
                          >
                            {daysUntil <= 0 ? 'Aujourd\'hui' : `J-${daysUntil}`}
                          </Badge>
                        )}
                      </div>
                    </Link>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {/* Pipeline visuel */}
          <Card>
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-base">Pipeline commercial</CardTitle>
              <Button asChild variant="ghost" size="sm">
                <Link to="/btp/prospects">
                  Gérer les prospects
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {pipelineByStatus.map(({ status, prospects: ps }) => {
                  const conf = STATUS_CONFIG[status];
                  const montant = ps.reduce((s, p) => s + (p.montantTravaux ?? 0), 0);
                  return (
                    <div
                      key={status}
                      className="rounded-lg border bg-muted/30 p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-muted-foreground">
                          {conf.label}
                        </span>
                        <span className="text-lg font-bold">{ps.length}</span>
                      </div>
                      {montant > 0 && (
                        <p className="text-xs text-muted-foreground">
                          {formatCurrency(montant)}
                        </p>
                      )}
                      {ps.slice(0, 2).map((p) => (
                        <div
                          key={p.id}
                          className="text-xs truncate text-muted-foreground bg-background rounded px-1.5 py-0.5"
                        >
                          {p.monumentNom}
                        </div>
                      ))}
                      {ps.length > 2 && (
                        <p className="text-xs text-muted-foreground">+{ps.length - 2} autres</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Affaire gagnées */}
          {recentWins.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                  Marchés gagnés
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {recentWins.map((p) => (
                  <div
                    key={p.id}
                    className="flex items-center justify-between p-2.5 rounded-lg border bg-emerald-50/50"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{p.monumentNom}</p>
                      <p className="text-xs text-muted-foreground">{p.commune}</p>
                    </div>
                    <div className="text-right shrink-0 ml-3">
                      <p className="text-sm font-bold text-emerald-700">
                        {formatCurrency(p.montantTravaux ?? 0)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {p.tauxCouvertureEstime}% financé
                      </p>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right: Quick stats + actions */}
        <div className="space-y-6">
          {/* Taux de conversion */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Performance</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <ConversionStat
                label="Taux de conversion"
                value={
                  userProspects.length > 0
                    ? Math.round((stats.gagnes.length / userProspects.length) * 100)
                    : 0
                }
                color="text-emerald-600"
                barColor="bg-emerald-500"
              />
              <ConversionStat
                label="Avec financement identifié"
                value={
                  userProspects.length > 0
                    ? Math.round(
                        (stats.avecFinancement.length / userProspects.length) * 100
                      )
                    : 0
                }
                color="text-blue-600"
                barColor="bg-blue-500"
              />
              <div className="pt-2 border-t">
                <p className="text-xs text-muted-foreground mb-1">Financement moyen couvert</p>
                <p className="text-xl font-bold">
                  {stats.avecFinancement.length > 0
                    ? Math.round(
                        stats.avecFinancement.reduce(
                          (s, p) => s + p.tauxCouvertureEstime,
                          0
                        ) / stats.avecFinancement.length
                      )
                    : 0}
                  %
                </p>
                <p className="text-xs text-muted-foreground">des travaux couverts en moyenne</p>
              </div>
            </CardContent>
          </Card>

          {/* Actions rapides */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Actions rapides</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button asChild variant="default" className="w-full justify-start">
                <Link to="/btp/prospects/new">
                  <Users className="h-4 w-4 mr-2" />
                  Ajouter un prospect
                </Link>
              </Button>
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to="/btp/aides">
                  <Target className="h-4 w-4 mr-2" />
                  Catalogue des aides
                </Link>
              </Button>
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to="/btp/documents">
                  <ArrowRight className="h-4 w-4 mr-2" />
                  Mes documents
                </Link>
              </Button>
            </CardContent>
          </Card>

          {/* Spécialités */}
          {user?.btp && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Vos spécialités</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {user.btp.specialites.map((s) => (
                    <Badge key={s} variant="secondary" className="text-xs capitalize">
                      {s.replace(/_/g, ' ')}
                    </Badge>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-3">
                  Zones d'intervention : {user.btp.regions.join(', ')}
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

interface KPICardProps {
  icon: typeof Users;
  label: string;
  value: string | number;
  sub?: string;
  variant: 'default' | 'accent' | 'success' | 'warning';
  linkTo?: string;
}

function KPICard({ icon: Icon, label, value, sub, variant, linkTo }: KPICardProps) {
  const variantClasses = {
    default: { bg: 'bg-primary/10', icon: 'text-primary' },
    accent: { bg: 'bg-blue-100', icon: 'text-blue-600' },
    success: { bg: 'bg-emerald-100', icon: 'text-emerald-600' },
    warning: { bg: 'bg-amber-100', icon: 'text-amber-600' },
  };
  const cls = variantClasses[variant];

  const card = (
    <Card className={cn('transition-all', linkTo && 'hover:shadow-md hover:border-primary/30 cursor-pointer')}>
      <CardContent className="pt-5 pb-4">
        <div className="flex items-start gap-3">
          <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center shrink-0', cls.bg)}>
            <Icon className={cn('h-5 w-5', cls.icon)} />
          </div>
          <div className="min-w-0">
            <p className="text-xl font-bold leading-tight truncate">{value}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
            {sub && <p className="text-xs text-muted-foreground/70 mt-0.5">{sub}</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  );

  if (linkTo) return <Link to={linkTo}>{card}</Link>;
  return card;
}

function ConversionStat({
  label,
  value,
  color,
  barColor,
}: {
  label: string;
  value: number;
  color: string;
  barColor: string;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={cn('text-sm font-bold', color)}>{value}%</span>
      </div>
      <Progress value={value} className={cn('h-1.5', barColor)} />
    </div>
  );
}
