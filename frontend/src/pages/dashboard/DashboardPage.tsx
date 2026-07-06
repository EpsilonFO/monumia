import { useMemo, useEffect } from 'react';
import { Link } from 'react-router';
import { ArrowUpRight } from 'lucide-react';
import { IconAjouter } from '@/components/icons';
import { C } from '@/lib/brand';
import { NextActionCard } from '@/components/dashboard/NextActionCard';
import { StatChips } from '@/components/dashboard/StatChips';
import { buildUpcomingRows } from '@/components/dashboard/echeances-alertes-utils';
import { ProjectsInProgress } from '@/components/dashboard/ProjectsInProgress';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { projectStage } from '@/lib/project-stats';
import type { ProjectStage } from '@/lib/project-stats';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useNotificationStore } from '@/stores/useNotificationStore';
import { monumentService } from '@/services/monument.service';
import { dossierService } from '@/services/dossier.service';
import { aideService } from '@/services/aide.service';
import { suiviService } from '@/services/suivi.service';
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
  const setMonuments = useMonumentStore((s) => s.setMonuments);
  const dossiers = useDossierStore((s) => s.dossiers);
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);
  const notifications = useNotificationStore((s) => s.notifications);

  // Rafraîchir au montage : revenir au tableau de bord reflète les changements
  // (projets/dossiers) faits par les autres membres, sans recharger la page.
  useEffect(() => {
    if (!user) return;
    monumentService.getAll().then(setMonuments).catch(console.error);
    dossierService.fetchAll().catch(console.error);
  }, [user, setMonuments]);

  const userMonuments = useMemo(
    () => (user ? monuments.filter((m) => m.userId === user.id) : []),
    [monuments, user],
  );

  // Grille « Projets en cours » : vos projets + ceux partagés avec vous.
  // (Le store ne contient que des monuments accessibles à l'utilisateur.)
  // Les KPI, le bandeau d'échéance et l'échéancier restent basés sur `userMonuments`.
  const displayMonuments = monuments;

  // Recalcule le diagnostic déterministe par monument qui n'en a pas encore,
  // à chaque changement de liste. On dépend uniquement de `[displayMonuments]` :
  // inclure `diagnosticsByMonument` relancerait l'effet à chaque stockage. Le
  // moteur étant déterministe, le résultat est toujours défini et stocké — le
  // garde par-id dédoublonne donc les recalculs.
  useEffect(() => {
    for (const m of displayMonuments) {
      if (!diagnosticsByMonument[m.id]) {
        aideService
          .runProjectDiagnostic(m.id, m.questionnaire)
          .then((result) => setDiagnostic(m.id, result))
          .catch(console.error);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayMonuments]);

  // Charge les suivis (par monument) absents du store, pour que le parcours
  // puisse atteindre l'étape « Suivi ». Gardé par loadedMonuments → une fois
  // par monument et par session (comme le diagnostic).
  useEffect(() => {
    for (const m of displayMonuments) {
      if (!loadedSuivis[m.id]) {
        suiviService.fetchByMonument(m.id).catch(console.error);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayMonuments]);

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
  // (échéances suivantes, monuments en péril, notifications non lues).
  const upcomingRows = useMemo(
    () => buildUpcomingRows(allDeadlines, nextDeadlines, userMonuments, userNotifications),
    [allDeadlines, nextDeadlines, userMonuments, userNotifications],
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
  const loadedSuivis = useSuiviStore((s) => s.loadedMonuments);

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
            <p className="mt-1 text-[14px]" style={{ color: C.grayFg }}>
              {summaryLine}
            </p>
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
      <NextActionCard deadlines={nextDeadlines} upcoming={upcomingRows} />

      {/* ─── KPI ─── */}
      <StatChips stats={dashboardStats} />

      {/* ─── VOS PROJETS (parcours) ─── */}
      <section>
        <SectionHeading eyebrow="Vos monuments" title="Vos projets" />
        <ProjectsInProgress monuments={displayMonuments} statsByMonument={statsByMonument} stageByMonument={stageByMonument} />
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
