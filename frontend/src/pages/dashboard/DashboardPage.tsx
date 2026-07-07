import { useMemo } from 'react';
import { Link } from 'react-router';
import { ArrowUpRight } from 'lucide-react';
import { IconAjouter } from '@/components/icons';
import { C } from '@/lib/brand';
import { NextActionCard } from '@/components/dashboard/NextActionCard';
import { StatChips } from '@/components/dashboard/StatChips';
import { buildUpcomingRows } from '@/components/dashboard/echeances-alertes-utils';
import { ProjectsInProgress } from '@/components/dashboard/ProjectsInProgress';
import {
  NextActionCardSkeleton,
  StatChipsSkeleton,
  ProjectsInProgressSkeleton,
} from '@/components/skeletons';
import { Skeleton } from '@/components/ui/skeleton';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { projectStage } from '@/lib/project-stats';
import type { ProjectStage } from '@/lib/project-stats';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useNotificationStore } from '@/stores/useNotificationStore';
import { useProjectsData } from '@/hooks/useProjectsData';
import { ROUTES } from '@/constants/routes';
import {
  aggregateDashboardStats,
  mergeProjectDeadlines,
  computeProjectStats,
} from '@/lib/project-stats';
import type { ProjectStats } from '@/lib/project-stats';
import type { AideDiagnosticResult } from '@/types';

export function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const dossiers = useDossierStore((s) => s.dossiers);
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const notifications = useNotificationStore((s) => s.notifications);

  // Charge monuments, dossiers, diagnostics et suivis ; `loading` ne retombe
  // qu'une fois TOUT arrivé, pour que les squelettes couvrent aussi le nombre
  // d'aides et l'avancement (sinon les cartes s'affichent vides puis sautent).
  const { loading } = useProjectsData();

  const userMonuments = useMemo(
    () => (user ? monuments.filter((m) => m.userId === user.id) : []),
    [monuments, user],
  );

  // Grille « Projets en cours » : vos projets + ceux partagés avec vous.
  // (Le store ne contient que des monuments accessibles à l'utilisateur.)
  // Les KPI, le bandeau d'échéance et l'échéancier restent basés sur `userMonuments`.
  const displayMonuments = monuments;

  const diagMap = useMemo<Record<string, AideDiagnosticResult | null>>(() => {
    const out: Record<string, AideDiagnosticResult | null> = {};
    for (const m of displayMonuments) {
      out[m.id] = diagnosticsByMonument[m.id] ?? null;
    }
    return out;
  }, [displayMonuments, diagnosticsByMonument]);

  const userDossiers = useMemo(
    () => (user ? dossiers.filter((d) => d.userId === user.id) : []),
    [dossiers, user],
  );

  const userNotifications = useMemo(
    () =>
      user
        ? notifications
            .filter((n) => n.userId === user.id)
            .sort((a, b) => new Date(b.dateCreation).getTime() - new Date(a.dateCreation).getTime())
        : [],
    [notifications, user],
  );

  const dashboardStats = useMemo(
    () => aggregateDashboardStats(userMonuments, diagMap, userDossiers),
    [userMonuments, diagMap, userDossiers],
  );

  // Toutes les échéances, triées de la plus proche à la plus lointaine.
  // L'échéancier vertical les reprend toutes, même très éloignées.
  const allDeadlines = useMemo(
    () =>
      userMonuments
        .flatMap((m) =>
          mergeProjectDeadlines(diagMap[m.id] ?? null, userDossiers.filter((d) => d.monumentId === m.id)),
        )
        .sort((a, b) => a.joursRestants - b.joursRestants),
    [userMonuments, diagMap, userDossiers],
  );

  // Bandeau « prochaine échéance » : la plus proche à venir, et toutes celles
  // qui tombent exactement à la même date (ex. deux dossiers le même jour).
  const nextDeadlines = useMemo(() => {
    const future = allDeadlines.filter((d) => d.joursRestants >= 0);
    if (future.length === 0) return [];
    const soonest = future[0].date;
    return future.filter((d) => d.date === soonest);
  }, [allDeadlines]);

  // Section « Ensuite » de la carte agenda unifiée : le reste du flux
  // (échéances suivantes, notifications non lues).
  const upcomingRows = useMemo(
    () => buildUpcomingRows(allDeadlines, nextDeadlines, userNotifications),
    [allDeadlines, nextDeadlines, userNotifications],
  );

  const statsByMonument = useMemo<Record<string, ProjectStats>>(() => {
    const out: Record<string, ProjectStats> = {};
    for (const m of displayMonuments) {
      out[m.id] = computeProjectStats(
        m,
        diagMap[m.id] ?? null,
        userDossiers.filter((d) => d.monumentId === m.id),
      );
    }
    return out;
  }, [displayMonuments, diagMap, userDossiers]);

  const suivis = useSuiviStore((s) => s.suivis);

  const stageByMonument = useMemo<Record<string, ProjectStage>>(() => {
    const out: Record<string, ProjectStage> = {};
    for (const m of displayMonuments) {
      out[m.id] = projectStage(
        diagMap[m.id] ?? null,
        userDossiers.filter((d) => d.monumentId === m.id),
        suivis.filter((s) => s.monumentId === m.id),
      );
    }
    return out;
  }, [displayMonuments, diagMap, userDossiers, suivis]);

  const semaineCount = useMemo(
    () => allDeadlines.filter((d) => d.joursRestants >= 0 && d.joursRestants <= 7).length,
    [allDeadlines],
  );
  const summaryLine =
    semaineCount > 0
      ? `Vous avez ${semaineCount} action${semaineCount > 1 ? 's' : ''} prioritaire${semaineCount > 1 ? 's' : ''} cette semaine.`
      : 'Rien d’urgent cette semaine — vous êtes à jour.';

  if (!user) return null;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Bonjour' : hour < 18 ? 'Bon après-midi' : 'Bonsoir';

  return (
    <div className="space-y-8">
      {/* ─── EN-TÊTE ─── */}
      <div>
        <span
          className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: C.blue }}
        >
          <span aria-hidden style={{ width: 22, height: 2, borderRadius: 2, background: C.orange }} />
          {new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}
        </span>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-[clamp(1.8rem,4vw,2.5rem)] leading-[1.1]" style={{ fontFamily: 'var(--font-serif)', color: C.ink }}>
              {greeting}, <span style={{ color: C.blue }}>{user.prenom}</span>
            </h1>
            {loading ? (
              // La phrase de synthèse dépend des échéances : ne rien affirmer
              // (« vous êtes à jour ») tant qu'elles ne sont pas chargées.
              <Skeleton className="mt-2 h-4 w-72 max-w-full" />
            ) : (
              <p className="mt-1 text-[14px]" style={{ color: C.grayFg }}>
                {summaryLine}
              </p>
            )}
          </div>
          <Link
            to={ROUTES.PROJET_NEW}
            className="group inline-flex shrink-0 items-center gap-2 rounded-xl px-5 py-2.5 text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: C.orange }}
          >
            <IconAjouter className="h-4 w-4" />
            {userMonuments.length === 0 ? 'Créer un projet' : 'Nouveau projet'}
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>

      {/* ─── À FAIRE MAINTENANT (carte agenda unifiée) ─── */}
      {loading ? (
        <NextActionCardSkeleton />
      ) : (
        <NextActionCard deadlines={nextDeadlines} upcoming={upcomingRows} />
      )}

      {/* ─── KPI ─── */}
      {loading ? <StatChipsSkeleton /> : <StatChips stats={dashboardStats} />}

      {/* ─── VOS PROJETS (parcours) ─── */}
      <section>
        <SectionHeading eyebrow="Vos monuments" title="Vos projets" />
        {loading ? (
          <ProjectsInProgressSkeleton />
        ) : (
          <ProjectsInProgress monuments={displayMonuments} statsByMonument={statsByMonument} stageByMonument={stageByMonument} />
        )}
      </section>

    </div>
  );
}

/** En-tête de section éditorial : filet orange + petites caps + titre serif (repris de la landing). */
function SectionHeading({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="mb-4">
      <span
        className="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em]"
        style={{ color: C.blue }}
      >
        <span aria-hidden style={{ width: 18, height: 2, borderRadius: 2, background: C.orange }} />
        {eyebrow}
      </span>
      <h2
        className="mt-1.5 text-[clamp(1.15rem,2vw,1.5rem)] leading-tight"
        style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
      >
        {title}
      </h2>
    </div>
  );
}
