import { useMemo } from 'react';
import { Link } from 'react-router';
import { ChevronRight } from 'lucide-react';
import {
  IconTendance, IconEquipe, IconSubvention, IconDevis, IconDiscussion,
  IconDocuments, IconAjouter, IconAttention, IconSucces, IconTemps, IconContact,
} from '@/components/icons';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useAuthStore } from '@/stores/useAuthStore';
import { useProspectStore } from '@/stores/useProspectStore';
import { formatCurrency } from '@/lib/format-utils';
import { cn } from '@/lib/utils';
import { C } from '@/lib/brand';
import type { ProspectStatus } from "@/types";

const STATUS_CONFIG: Record<ProspectStatus, { label: string; color: string; icon: typeof IconTemps }> = {
  a_contacter: { label: 'À contacter', color: 'bg-muted text-muted-foreground', icon: IconTemps },
  contacte: { label: 'Contacté', color: 'bg-info-muted text-info', icon: IconContact },
  en_discussion: { label: 'En discussion', color: 'bg-warning-muted text-warning', icon: IconDiscussion },
  devis_envoye: { label: 'Devis envoyé', color: 'bg-cat-violet-soft text-cat-violet', icon: IconDevis },
  gagne: { label: 'Gagné', color: 'bg-success-muted text-success', icon: IconSucces },
  perdu: { label: 'Perdu', color: 'bg-destructive-muted text-destructive', icon: IconAttention },
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
      <div>
        <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: C.blue }}>
          <span aria-hidden style={{ width: 22, height: 2, borderRadius: 2, background: C.orange }} />
          {user?.btp?.raisonSociale ?? 'Votre entreprise'}
        </span>
        <h1 className="mt-2 text-[clamp(1.7rem,3.5vw,2.3rem)] leading-tight" style={{ fontFamily: 'var(--font-serif)', color: C.ink }}>
          Bonjour, <span style={{ color: C.blue }}>{user?.prenom ?? ''}</span>
        </h1>
        <p className="mt-1 text-[14px]" style={{ color: C.grayFg }}>
          {urgentProspects.length > 0
            ? `Vous avez ${urgentProspects.length} relance${urgentProspects.length > 1 ? 's' : ''} à prévoir.`
            : 'Aucune relance urgente — bonne prospection !'}
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          icon={IconEquipe}
          label="Prospects actifs"
          value={stats.actifs.length}
          sub={`${userProspects.length} au total`}
          variant="default"
          linkTo="/btp/prospects"
        />
        <KPICard
          icon={IconSubvention}
          label="CA potentiel"
          value={formatCurrency(stats.caPotentiel)}
          sub="en cours de négociation"
          variant="accent"
        />
        <KPICard
          icon={IconTendance}
          label="Financement identifié"
          value={formatCurrency(stats.financementTotal)}
          sub={`${stats.avecFinancement.length} monuments qualifiés`}
          variant="success"
        />
        <KPICard
          icon={IconSucces}
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
                <CardTitle className="text-[17px] flex items-center gap-2" style={{ fontFamily: 'var(--font-serif)' }}>
                  <IconAttention className="h-4 w-4 text-warning" />
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
                                ? 'bg-destructive-muted text-destructive'
                                : daysUntil <= 7
                                  ? 'bg-warning-muted text-warning'
                                  : 'bg-muted text-muted-foreground'
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
              <CardTitle className="text-[17px]" style={{ fontFamily: 'var(--font-serif)' }}>Pipeline commercial</CardTitle>
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
                <CardTitle className="text-[17px] flex items-center gap-2" style={{ fontFamily: 'var(--font-serif)' }}>
                  <IconSucces className="h-4 w-4 text-success" />
                  Marchés gagnés
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {recentWins.map((p) => (
                  <div
                    key={p.id}
                    className="flex items-center justify-between p-2.5 rounded-lg border bg-success-muted/50"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{p.monumentNom}</p>
                      <p className="text-xs text-muted-foreground">{p.commune}</p>
                    </div>
                    <div className="text-right shrink-0 ml-3">
                      <p className="text-sm font-bold text-success">
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
              <CardTitle className="text-[17px]" style={{ fontFamily: 'var(--font-serif)' }}>Performance</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <ConversionStat
                label="Taux de conversion"
                value={
                  userProspects.length > 0
                    ? Math.round((stats.gagnes.length / userProspects.length) * 100)
                    : 0
                }
                color="text-success"
                barColor="bg-success"
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
                color="text-info"
                barColor="bg-info"
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
              <CardTitle className="text-[17px]" style={{ fontFamily: 'var(--font-serif)' }}>Actions rapides</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button asChild variant="default" className="w-full justify-start">
                <Link to="/btp/prospects/new">
                  <IconAjouter className="h-4 w-4 mr-2" />
                  Ajouter un prospect
                </Link>
              </Button>
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to="/btp/aides">
                  <IconSubvention className="h-4 w-4 mr-2" />
                  Catalogue des aides
                </Link>
              </Button>
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to="/btp/documents">
                  <IconDocuments className="h-4 w-4 mr-2" />
                  Mes documents
                </Link>
              </Button>
            </CardContent>
          </Card>

          {/* Spécialités */}
          {user?.btp && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-[17px]" style={{ fontFamily: 'var(--font-serif)' }}>Vos spécialités</CardTitle>
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
  icon: typeof IconEquipe;
  label: string;
  value: string | number;
  sub?: string;
  variant: 'default' | 'accent' | 'success' | 'warning';
  linkTo?: string;
}

function KPICard({ icon: Icon, label, value, sub, variant, linkTo }: KPICardProps) {
  const variantStyle: Record<KPICardProps['variant'], { accent: string; tint: string }> = {
    default: { accent: C.blue, tint: C.paleBlue },
    accent: { accent: C.blueLight, tint: C.paleBlue },
    success: { accent: 'var(--success)', tint: 'var(--success-muted)' },
    warning: { accent: C.orange, tint: C.paleOrange },
  };
  const cls = variantStyle[variant];

  const card = (
    <div
      className={cn('rounded-2xl border px-4 py-3.5 transition-shadow', linkTo && 'hover:shadow-[var(--shadow-pop)] cursor-pointer')}
      style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
    >
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: cls.tint, color: cls.accent }}>
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-[20px] font-bold leading-none tabular-nums" style={{ fontFamily: 'var(--font-serif)', color: cls.accent }}>{value}</p>
          <p className="mt-1 truncate text-[12px] font-medium" style={{ color: C.grayMuted }}>{label}</p>
          {sub && <p className="truncate text-[11px]" style={{ color: C.grayMuted, opacity: 0.8 }}>{sub}</p>}
        </div>
      </div>
    </div>
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
