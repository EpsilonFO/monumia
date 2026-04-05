import { useMemo, useEffect } from 'react';
import { Link } from 'react-router';
import {
  Castle, ScrollText, Compass, Calendar, Bell,
  AlertTriangle, ChevronRight, ArrowUpRight, Sparkles,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { NotificationItem } from '@/components/notification/NotificationItem';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useNotificationStore } from '@/stores/useNotificationStore';
import { dossierService } from '@/services/dossier.service';
import { useDeadlines } from '@/hooks/useDeadlines';
import { ROUTES } from '@/constants/routes';
import { DOSSIER_STATUS_LABELS } from '@/constants/dossier-steps';
import { deadlineLabel } from '@/lib/date-utils';
import { cn } from '@/lib/utils';

const FONT = "'Cormorant Garamond', serif";

export function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const dossiers = useDossierStore((s) => s.dossiers);
  const dossierLoaded = useDossierStore((s) => s.loaded);
  const notifications = useNotificationStore((s) => s.notifications);
  const markAsRead = useNotificationStore((s) => s.markAsRead);
  const deadlines = useDeadlines();

  useEffect(() => {
    if (user && !dossierLoaded) {
      dossierService.fetchAll().catch(console.error);
    }
  }, [user, dossierLoaded]);

  if (!user) return null;
  const u = user;

  const userMonuments = useMemo(() => monuments.filter((m) => m.userId === u.id), [monuments, u.id]);
  const userDossiers = useMemo(() => dossiers.filter((d) => d.userId === u.id), [dossiers, u.id]);
  const activeDossiers = useMemo(() => userDossiers.filter((d) => d.statut !== 'soumis'), [userDossiers]);
  const userNotifications = useMemo(
    () => notifications
      .filter((n) => n.userId === u.id)
      .sort((a, b) => new Date(b.dateCreation).getTime() - new Date(a.dateCreation).getTime())
      .slice(0, 5),
    [notifications, u.id],
  );
  const unreadCount = useMemo(() => notifications.filter((n) => n.userId === u.id && !n.lue).length, [notifications, u.id]);

  const now = new Date();
  const hour = now.getHours();
  const greeting = hour < 12 ? 'Bonjour' : hour < 18 ? 'Bon après-midi' : 'Bonsoir';

  return (
    <div className="space-y-6">

      {/* ═══════════ HERO GREETING ═══════════ */}
      <div className="relative overflow-hidden rounded-2xl px-8 py-7" style={{ background: 'rgba(199, 91, 58, 0.12)' }}>
        {/* decorative elements */}
        <div className="pointer-events-none absolute -top-16 -right-16 h-48 w-48 rounded-full blur-[80px]" style={{ background: 'rgba(199, 91, 58, 0.15)' }} />
        <div className="pointer-events-none absolute -bottom-10 -left-10 h-32 w-32 rounded-full blur-[60px]" style={{ background: 'rgba(26, 35, 126, 0.08)' }} />
        <div className="pointer-events-none absolute top-0 right-0 bottom-0 w-1/3 opacity-[0.04]" style={{
          backgroundImage: `repeating-linear-gradient(90deg, transparent, transparent 29px, #C75B3A 29px, #C75B3A 30px)`,
        }} />

        <div className="relative z-10 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] mb-2" style={{ color: 'rgba(199, 91, 58, 0.5)' }}>
              {now.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}
            </p>
            <h1
              className="text-[clamp(1.8rem,4vw,2.8rem)] font-light leading-[1.1] tracking-[-0.02em]"
              style={{ fontFamily: FONT, color: '#1B1E2E' }}
            >
              {greeting}, <em className="italic" style={{ color: '#1A237E' }}>{u.prenom}</em>
            </h1>
            <p className="mt-2 text-[14px] max-w-md" style={{ color: 'rgba(199, 91, 58, 0.6)' }}>
              {userMonuments.length === 0
                ? 'Commencez par ajouter votre premier monument pour découvrir les aides disponibles.'
                : `${userMonuments.length} monument${userMonuments.length > 1 ? 's' : ''} · ${activeDossiers.length} dossier${activeDossiers.length > 1 ? 's' : ''} en cours`}
            </p>
          </div>

          {userMonuments.length === 0 && (
            <Link
              to={ROUTES.MONUMENTS}
              className="group inline-flex items-center gap-2 text-[13px] font-semibold px-5 py-2.5 rounded-lg transition-all duration-300 shrink-0"
              style={{ background: 'rgba(199, 91, 58, 0.12)', border: '1px solid rgba(199, 91, 58, 0.2)', color: '#C75B3A' }}
            >
              <Sparkles className="h-4 w-4" style={{ color: '#1A237E' }} />
              Ajouter un monument
              <ArrowUpRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
            </Link>
          )}
        </div>
      </div>

      {/* ═══════════ KPI STRIP ═══════════ */}
      <div className="grid grid-cols-3 gap-4">
        <KPICard
          icon={Castle}
          label="Monuments"
          value={userMonuments.length}
          linkTo={ROUTES.MONUMENTS}
          accentColor="#C75B3A"
          bgColor="#FBF0EC"
        />
        <KPICard
          icon={ScrollText}
          label="Dossiers actifs"
          value={activeDossiers.length}
          linkTo={ROUTES.DOSSIERS}
          accentColor="#1A237E"
          bgColor="#E8EAF6"
        />
        <KPICard
          icon={Calendar}
          label="Échéances proches"
          value={deadlines.filter((d) => d.estUrgent).length}
          accentColor="#C75B3A"
          bgColor="#FBF0EC"
        />
      </div>

      {/* ═══════════ MAIN GRID ═══════════ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* ── LEFT: Monuments ── */}
        <div>
          <Panel className="h-full">
            <PanelHeader
              icon={<Castle className="h-4 w-4" />}
              iconColor="#C75B3A"
              title="Monuments"
              action={
                <Link to={ROUTES.MONUMENTS} className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#C75B3A] hover:opacity-70 transition-opacity flex items-center gap-0.5">
                  Tous <ChevronRight className="h-3 w-3" />
                </Link>
              }
            />
            {userMonuments.length === 0 ? (
              <div className="px-5 py-8 text-center">
                <p className="text-[13px] text-[#8E92A4]">Aucun monument</p>
              </div>
            ) : (
              <div className="divide-y divide-[#E4E2DC]">
                {userMonuments.slice(0, 5).map((m) => (
                  <Link key={m.id} to={ROUTES.MONUMENT_DETAIL(m.id)} className="block">
                    <div className="flex items-center gap-3 px-5 py-3 transition-colors duration-200 hover:bg-[#F8F7F4]">
                      <div className="min-w-0 flex-1">
                        <p className="text-[13px] font-medium text-[#1B1E2E] truncate">{m.nom}</p>
                        <p className="text-[11px] text-[#8E92A4] truncate">{m.commune}</p>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Panel>
        </div>

        {/* ── CENTER: Dossiers ── */}
        <div>
          <Panel className="h-full">
            <PanelHeader
              icon={<ScrollText className="h-4 w-4" />}
              iconColor="#1A237E"
              title="Dossiers en cours"
              action={
                <Link to={ROUTES.DOSSIERS} className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#1A237E] hover:opacity-70 transition-opacity flex items-center gap-0.5">
                  Tous <ChevronRight className="h-3 w-3" />
                </Link>
              }
            />
            {activeDossiers.length === 0 ? (
              <div className="px-5 py-8 text-center">
                <div className="mx-auto mb-3 w-12 h-12 rounded-full bg-[#E8EAF6] flex items-center justify-center">
                  <Compass className="h-5 w-5 text-[#1A237E]" />
                </div>
                <p className="text-[14px] font-medium text-[#1B1E2E] mb-1">Aucun dossier</p>
                <p className="text-[12px] text-[#8E92A4] mb-4">Lancez un diagnostic pour identifier les aides disponibles</p>
                <Link
                  to={ROUTES.AIDES}
                  className="inline-flex items-center gap-2 px-4 py-2 text-[12px] font-semibold text-white rounded-lg transition-all duration-300 hover:shadow-md"
                  style={{ background: '#1A237E' }}
                >
                  <Compass className="h-3.5 w-3.5" />
                  Lancer un diagnostic
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-[#E4E2DC]">
                {activeDossiers.slice(0, 5).map((d) => {
                  const statusConfig = DOSSIER_STATUS_LABELS[d.statut];
                  return (
                    <Link key={d.id} to={ROUTES.DOSSIER_DETAIL(d.id)} className="block">
                      <div className="px-5 py-3 transition-colors duration-200 hover:bg-[#F8F7F4]">
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-[13px] font-medium text-[#1B1E2E] truncate flex-1 mr-2" style={{ fontFamily: FONT }}>{d.titre}</p>
                          <Badge className={cn('text-[10px] border-0 shrink-0', statusConfig?.color)}>
                            {statusConfig?.label}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-3">
                          <Progress value={d.progressionPourcentage} className="h-1.5 flex-1" />
                          <span className="text-[11px] font-semibold text-[#5C6178] tabular-nums w-8 text-right">
                            {d.progressionPourcentage}%
                          </span>
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </Panel>
        </div>

        {/* ── RIGHT: Échéances + Notifications ── */}
        <div className="space-y-4">
          {deadlines.length > 0 && (
            <Panel>
              <PanelHeader
                icon={<AlertTriangle className="h-4 w-4" />}
                iconColor="#D97706"
                title="Échéances"
              />
              <div className="divide-y divide-[#E4E2DC]">
                {deadlines.slice(0, 4).map((d) => {
                  const dl = deadlineLabel(d.date);
                  return (
                    <Link key={d.id} to={ROUTES.DOSSIER_DETAIL(d.dossierId)} className="block">
                      <div className="flex items-center justify-between px-5 py-3 transition-colors duration-200 hover:bg-[#F8F7F4]">
                        <div className="min-w-0 flex-1">
                          <p className="text-[13px] font-medium text-[#1B1E2E] truncate">{d.label}</p>
                          <p className="text-[11px] text-[#8E92A4] truncate">{d.dossierTitre}</p>
                        </div>
                        <Badge className={cn(
                          'shrink-0 ml-3 text-[10px] font-semibold border-0',
                          dl.urgency === 'urgent' && 'bg-red-100 text-red-700',
                          dl.urgency === 'warning' && 'bg-amber-100 text-amber-700',
                          dl.urgency === 'normal' && 'bg-[#E8EAF6] text-[#1A237E]',
                        )}>
                          {dl.text}
                        </Badge>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </Panel>
          )}

          <Panel>
            <PanelHeader
              icon={<Bell className="h-4 w-4" />}
              iconColor="#1A237E"
              title="Notifications"
              badge={unreadCount}
            />
            {userNotifications.length === 0 ? (
              <div className="px-5 py-6 text-center">
                <Bell className="h-5 w-5 mx-auto mb-2 text-[#E0DDD6]" />
                <p className="text-[13px] text-[#8E92A4]">Aucune notification</p>
              </div>
            ) : (
              <div className="divide-y divide-[#E4E2DC]">
                {userNotifications.map((n) => (
                  <div key={n.id} className="px-2 py-0.5">
                    <NotificationItem notification={n} onRead={markAsRead} />
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────
   Sub-components
   ──────────────────────────────────────────── */

interface KPICardProps {
  icon: typeof Castle;
  label: string;
  value: number;
  linkTo?: string;
  accentColor: string;
  bgColor: string;
}

function KPICard({ icon: Icon, label, value, linkTo, accentColor, bgColor }: KPICardProps) {
  const inner = (
    <div
      className={cn(
        'relative overflow-hidden rounded-xl px-5 py-4 transition-all duration-300',
        linkTo && 'cursor-pointer hover:shadow-lg hover:shadow-black/[0.04] hover:scale-[1.01]',
      )}
      style={{ background: bgColor }}
    >
      <div className="relative z-10 flex items-center gap-4">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: accentColor }}
        >
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div>
          <p
            className="text-[28px] font-light leading-none tracking-[-0.02em]"
            style={{ color: accentColor, fontFamily: FONT }}
          >
            {value}
          </p>
          <p className="text-[12px] font-medium text-[#5C6178] mt-0.5">{label}</p>
        </div>
      </div>
    </div>
  );

  if (linkTo) return <Link to={linkTo}>{inner}</Link>;
  return inner;
}

function Panel({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-xl border border-[#E4E2DC]/80 overflow-hidden ${className}`}>
      {children}
    </div>
  );
}

interface PanelHeaderProps {
  icon: React.ReactNode;
  iconColor: string;
  title: string;
  action?: React.ReactNode;
  badge?: number;
}

function PanelHeader({ icon, iconColor, title, action, badge }: PanelHeaderProps) {
  return (
    <div className="flex items-center justify-between px-5 py-3 border-b border-[#E4E2DC]">
      <div className="flex items-center gap-2.5">
        <div
          className="flex items-center justify-center w-7 h-7 rounded-lg"
          style={{ background: `${iconColor}10`, color: iconColor }}
        >
          {icon}
        </div>
        <h3
          className="text-[15px] font-normal text-[#1B1E2E]"
          style={{ fontFamily: FONT }}
        >
          {title}
        </h3>
        {badge !== undefined && badge > 0 && (
          <span className="inline-flex items-center justify-center h-5 min-w-5 px-1.5 rounded-full bg-[#C75B3A] text-white text-[10px] font-bold">
            {badge}
          </span>
        )}
      </div>
      {action}
    </div>
  );
}
