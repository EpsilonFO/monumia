import { useMemo } from 'react';
import { Link } from 'react-router';
import { ArrowUpRight } from 'lucide-react';
import { IconAjouter } from '@/components/icons';
import { C } from '@/lib/brand';
import { NextActionCard } from '@/components/dashboard/NextActionCard';
import { buildUpcomingRows } from '@/components/dashboard/echeances-alertes-utils';
import { MonumentsInProgress } from '@/components/dashboard/MonumentsInProgress';
import { NextActionCardSkeleton, ProjectsInProgressSkeleton } from '@/components/skeletons';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { projectStage } from '@/lib/project-stats';
import type { ProjectStage } from '@/lib/project-stats';
import { useProjetStore } from '@/stores/useProjetStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useNotificationStore } from '@/stores/useNotificationStore';
import { useProjectsData } from '@/hooks/useProjectsData';
import { ROUTES } from '@/constants/routes';
import { mergeProjectDeadlines, computeMonumentStats } from '@/lib/project-stats';
import type { MonumentStats } from '@/lib/project-stats';
import type { ProjectDigest } from '@/types';

export function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const monuments = useMonumentStore((s) => s.monuments);
  const dossiers = useDossierStore((s) => s.dossiers);
  const projets = useProjetStore((s) => s.projets);
  const digestsByProjet = useAideStore((s) => s.digestsByProjet);
  const notifications = useNotificationStore((s) => s.notifications);

  // Charge monuments, dossiers, digests d'aides et suivis en un seul appel :
  // tout arrive ensemble, donc les squelettes couvrent aussi le nombre d'aides
  // et l'avancement sans que les cartes « sautent ».
  const { loading } = useProjectsData();

  const userMonuments = useMemo(
    () => (user ? monuments.filter((m) => m.userId === user.id) : []),
    [monuments, user],
  );

  // Grille « Vos monuments » : les vôtres + ceux partagés avec vous.
  // (Le store ne contient que des monuments accessibles à l'utilisateur.)
  // Le bandeau d'échéance et l'échéancier restent basés sur `userMonuments`.
  const displayMonuments = monuments;

  // Digests par PROJET, restreints à ceux dont le monument est affiché.
  const diagMap = useMemo<Record<string, ProjectDigest | null>>(() => {
    const out: Record<string, ProjectDigest | null> = {};
    for (const p of projets) {
      out[p.id] = digestsByProjet[p.id] ?? null;
    }
    return out;
  }, [projets, digestsByProjet]);

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

  // Toutes les échéances, triées de la plus proche à la plus lointaine.
  // L'échéancier vertical les reprend toutes, même très éloignées.
  const allDeadlines = useMemo(() => {
    const monumentIds = new Set(userMonuments.map((m) => m.id));
    return projets
      .filter((p) => monumentIds.has(p.monumentId))
      .flatMap((p) =>
        mergeProjectDeadlines(diagMap[p.id] ?? null, userDossiers.filter((d) => d.projetId === p.id)),
      )
      .sort((a, b) => a.joursRestants - b.joursRestants);
  }, [userMonuments, projets, diagMap, userDossiers]);

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

  const statsByMonument = useMemo<Record<string, MonumentStats>>(() => {
    const out: Record<string, MonumentStats> = {};
    for (const m of displayMonuments) {
      out[m.id] = computeMonumentStats(m, projets, diagMap, dossiers);
    }
    return out;
  }, [displayMonuments, projets, diagMap, dossiers]);

  const suivis = useSuiviStore((s) => s.suivis);

  // Avancement affiché par monument : celui de son projet le PLUS avancé — la
  // vignette dit où en est le monument, pas la moyenne de ses chantiers.
  const stageByMonument = useMemo<Record<string, ProjectStage>>(() => {
    const out: Record<string, ProjectStage> = {};
    for (const m of displayMonuments) {
      const stages = projets
        .filter((p) => p.monumentId === m.id)
        .map((p) =>
          projectStage(
            diagMap[p.id] ?? null,
            dossiers.filter((d) => d.projetId === p.id),
            suivis.filter((s) => s.projetId === p.id),
          ),
        );
      out[m.id] =
        stages.sort((a, b) => b.reachedIndex - a.reachedIndex)[0] ??
        projectStage(null, [], []);
    }
    return out;
  }, [displayMonuments, projets, diagMap, dossiers, suivis]);

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
            
          </div>
          <Link
            to={ROUTES.MONUMENT_NEW}
            className="group inline-flex shrink-0 items-center gap-2 rounded-xl px-5 py-2.5 text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: C.orange }}
          >
            <IconAjouter className="h-4 w-4" />
            {userMonuments.length === 0 ? 'Créer un monument' : 'Nouveau monument'}
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

      {/* ─── VOS MONUMENTS (parcours) ─── */}
      <section>
        <SectionHeading eyebrow="Votre patrimoine" title="Vos monuments" />
        {loading ? (
          <ProjectsInProgressSkeleton />
        ) : (
          <MonumentsInProgress monuments={displayMonuments} statsByMonument={statsByMonument} stageByMonument={stageByMonument} />
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
