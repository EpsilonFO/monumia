import { useMemo, useEffect } from 'react';
import { Link } from 'react-router';
import { ArrowUpRight, FolderKanban } from 'lucide-react';
import { C } from '@/lib/brand';
import { KpiCards } from '@/components/dashboard/KpiCards';
import { NextDeadlineBanner } from '@/components/dashboard/NextDeadlineBanner';
import { ProjectsInProgress } from '@/components/dashboard/ProjectsInProgress';
import { EcheancesAlertesPanel } from '@/components/dashboard/EcheancesAlertesPanel';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useNotificationStore } from '@/stores/useNotificationStore';
import { monumentService } from '@/services/monument.service';
import { dossierService } from '@/services/dossier.service';
import { aideService } from '@/services/aide.service';
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

  // Lazy-load the latest diagnostic per monument that doesn't have one yet,
  // whenever the monument list changes. We intentionally depend only on
  // `[userMonuments]`: including `diagnosticsByMonument` would re-run the effect
  // every time any diagnostic is stored, and monuments whose `getDiagnostics`
  // returned `[]` (no saved diagnostic) would be re-fetched forever because
  // their `diagnosticsByMonument[m.id]` stays `undefined`. The per-id guard
  // below dedupes fetches for monuments that DO have a stored diagnostic.
  useEffect(() => {
    for (const m of displayMonuments) {
      if (!diagnosticsByMonument[m.id]) {
        aideService
          .getDiagnostics(m.id)
          .then((diagnostics) => {
            if (diagnostics.length > 0) setDiagnostic(m.id, diagnostics[0]);
          })
          .catch(console.error);
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

  if (!user) return null;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Bonjour' : hour < 18 ? 'Bon après-midi' : 'Bonsoir';

  return (
    <div className="space-y-9">
      {/* ─── HERO GREETING ─── */}
      <div
        className="relative overflow-hidden rounded-2xl px-8 py-9"
        style={{ background: C.paleBlue, border: `1px solid ${C.border}` }}
      >
        {/* Atmosphère : halos diffus + fines règles horizontales (esprit landing) */}
        <div className="pointer-events-none absolute inset-0" aria-hidden>
          <div
            className="absolute -right-16 -top-28 h-72 w-72 rounded-full blur-[120px]"
            style={{ background: 'rgba(92,149,255,0.35)' }}
          />
          <div
            className="absolute -bottom-28 left-1/3 h-64 w-64 rounded-full blur-[120px]"
            style={{ background: 'rgba(241,113,5,0.16)' }}
          />
          <div
            className="absolute inset-0 opacity-[0.04]"
            style={{
              backgroundImage: `repeating-linear-gradient(0deg, transparent, transparent 31px, ${C.blue} 31px, ${C.blue} 32px)`,
            }}
          />
        </div>

        <div className="relative z-10 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <span
              className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em]"
              style={{ color: C.blue }}
            >
              <span aria-hidden style={{ width: 22, height: 2, borderRadius: 2, background: C.orange }} />
              {new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}
            </span>
            <h1
              className="mt-3 text-[clamp(1.8rem,4vw,2.6rem)] leading-[1.1]"
              style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
            >
              {greeting}, <span style={{ color: C.blue }}>{user.prenom}</span>
            </h1>
          </div>

          <Link
            to={userMonuments.length === 0 ? ROUTES.PROJET_NEW : ROUTES.PROJETS}
            className="group inline-flex shrink-0 items-center gap-2 rounded-lg px-5 py-2.5 text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: C.orange }}
          >
            <FolderKanban className="h-4 w-4" />
            {userMonuments.length === 0 ? 'Créer un projet' : 'Mes projets'}
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>

      {/* ─── PROCHAINE ÉCHÉANCE (bandeau) ─── */}
      <NextDeadlineBanner deadlines={nextDeadlines} />

      {/* ─── KPI ─── */}
      <KpiCards stats={dashboardStats} />

      {/* ─── MES PROJETS (pleine largeur) ─── */}
      <section>
        <SectionHeading eyebrow="Vos monuments" title="Projets en cours" />
        <ProjectsInProgress monuments={displayMonuments} statsByMonument={statsByMonument} />
      </section>

      {/* ─── ÉCHÉANCIER (toutes les échéances, pleine largeur) ─── */}
      <section>
        <SectionHeading eyebrow="Ne rien laisser passer" title="Échéancier" />
        <EcheancesAlertesPanel
          deadlines={allDeadlines}
          monuments={userMonuments}
          notifications={userNotifications}
        />
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
