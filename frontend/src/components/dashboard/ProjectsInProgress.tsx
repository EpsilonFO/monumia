import { Link } from 'react-router';
import { ArrowUpRight, ChevronRight } from 'lucide-react';
import {
  IconDossier,
  IconEcheance,
  IconProjet,
  IconLocalisation,
  IconEquipe,
} from '@/components/icons';
import { Clover } from '@/components/illustrations';
import { ROLE_LABELS } from '@/components/sharing/RoleBadge';
import { sharedRole } from '@/lib/project-permissions';
import { C, DEADLINE_TONE } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { formatDateShort } from '@/lib/date-utils';
import { formatCurrency } from '@/lib/format-utils';
import { montantTileMode } from '@/lib/project-card-view';
import { ParcoursStepper } from './ParcoursStepper';
import type { Monument } from '@/types';
import type { ProjectStats, ProjectStage } from '@/lib/project-stats';

interface ProjectsInProgressProps {
  monuments: Monument[];
  statsByMonument: Record<string, ProjectStats>;
  stageByMonument?: Record<string, ProjectStage>;
}

/** Voile bleu Monumia posé sur la photo : laisse respirer le cliché en haut, plombe
 *  le bas en bleu profond pour que le titre blanc reste lisible sur n'importe quelle image. */
const PHOTO_SCRIM =
  'linear-gradient(to top, rgba(7,42,114,0.94) 6%, rgba(7,42,114,0.58) 40%, rgba(7,42,114,0.08) 82%)';

/** Photo héros : on privilégie la façade, sinon le premier cliché disponible. */
function heroPhoto(m: Monument): string | null {
  if (!m.photos?.length) return null;
  const facade = m.photos.find((p) => p.type === 'facade');
  return (facade ?? m.photos[0])?.url || null;
}

/** Kicker éditorial : filet orange + petites caps (repris de la landing). */
function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em]"
      style={{ color: 'rgba(255,255,255,0.82)' }}
    >
      <span aria-hidden style={{ width: 18, height: 2, borderRadius: 2, background: C.orange }} />
      {children}
    </span>
  );
}

/** Badge en verre posé sur le héros (rôle sur projet partagé). */
function GlassBadge({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold text-white"
      style={{
        background: 'rgba(255,255,255,0.16)',
        border: '1px solid rgba(255,255,255,0.30)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
      }}
    >
      {children}
    </span>
  );
}

function ProjectCard({
  monument,
  stats,
  stage,
  featured = false,
}: {
  monument: Monument;
  stats?: ProjectStats;
  stage?: ProjectStage;
  featured?: boolean;
}) {
  const dossiersActifs = stats?.dossiersActifs ?? 0;
  const next = stats?.prochaineEcheance ?? null;
  const photo = heroPhoto(monument);
  const role = sharedRole(monument.myRole);

  // Kicker du héros : l'accroche aides du projet (montant si estimé, sinon le
  // nombre d'aides repérées, sinon l'invitation à estimer) — plutôt qu'un
  // « En cours » identique sur toutes les cartes.
  const aidesMode = montantTileMode(stats);
  const kicker =
    aidesMode === 'money' && stats
      ? `Jusqu’à ${formatCurrency(stats.montantPotentiel)} d’aides`
      : aidesMode === 'count' && stats
        ? `${stats.aidesIdentifiees} aide${stats.aidesIdentifiees > 1 ? 's' : ''} repérée${stats.aidesIdentifiees > 1 ? 's' : ''}`
        : 'Aides à estimer';

  return (
    <Link
      to={ROUTES.PROJET_DETAIL(monument.id)}
      className="group relative flex h-full flex-col overflow-hidden rounded-2xl border transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_24px_50px_-28px_rgba(7,42,114,0.6)]"
      style={{ borderColor: C.border, background: C.card }}
    >
      {/* ── Héros : photo du monument, sinon dégradé bleu + quadrilobe ── */}
      <div
        className={`relative overflow-hidden ${featured ? 'h-60 sm:h-72' : 'h-48'}`}
        style={photo ? undefined : { background: `linear-gradient(135deg, ${C.blue}, ${C.blueDark})` }}
      >
        {photo ? (
          <>
            <div
              className="absolute inset-0 bg-cover bg-center transition-transform duration-700 ease-out group-hover:scale-[1.06]"
              style={{ backgroundImage: `url(${photo})` }}
            />
            <div className="absolute inset-0" style={{ background: PHOTO_SCRIM }} />
          </>
        ) : (
          <Clover
            size={featured ? 320 : 220}
            className="pointer-events-none absolute -right-16 -top-20 text-white"
            style={{ opacity: 0.08 }}
          />
        )}

        {/* Badge rôle (haut) : uniquement si le projet est partagé avec moi */}
        {role && (
          <div className="absolute left-0 top-0 p-4">
            <GlassBadge>
              <IconEquipe className="h-3 w-3" strokeWidth={2.4} aria-hidden />
              {ROLE_LABELS[role]}
            </GlassBadge>
          </div>
        )}

        {/* Titre en surimpression (ancré en bas → hauteur de héros constante) */}
        <div className="absolute inset-x-0 bottom-0 p-5">
          <Kicker>{kicker}</Kicker>
          <p
            className={`mt-2 line-clamp-2 font-bold leading-tight text-white ${
              featured ? 'text-[clamp(1.6rem,3vw,2.4rem)]' : 'text-[20px]'
            }`}
            style={{ fontFamily: 'var(--font-serif)' }}
          >
            {monument.nom}
          </p>
          {(monument.commune || monument.departement) && (
            <p
              className="mt-1.5 inline-flex items-center gap-1.5 text-[12px]"
              style={{ color: 'rgba(255,255,255,0.78)' }}
            >
              <IconLocalisation className="h-3.5 w-3.5 shrink-0" strokeWidth={1.8} aria-hidden />
              <span className="truncate">
                {monument.commune ?? '—'}
                {monument.departement ? ` · ${monument.departement}` : ''}
              </span>
            </p>
          )}
        </div>
      </div>

      {/* ── Corps crème : parcours + métadonnées ── */}
      <div className={`flex flex-1 flex-col gap-3 ${featured ? 'px-6 py-5 md:px-7' : 'px-5 py-4'}`}>
        {stage && (
          <div className="border-b pb-3" style={{ borderColor: C.border }}>
            <ParcoursStepper stage={stage} />
          </div>
        )}
        <div className="flex items-end justify-between gap-4">
          <div
            className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] text-foreground/70"
          >
            <span className="inline-flex items-center gap-1.5">
              <IconDossier className="h-3.5 w-3.5" aria-hidden />
              {dossiersActifs} dossier{dossiersActifs > 1 ? 's' : ''}
            </span>
            {next && (
              <span
                className="inline-flex items-center gap-1.5"
                style={{
                  color: DEADLINE_TONE[next.urgency].fg,
                  fontWeight: next.urgency === 'urgent' || next.urgency === 'past' ? 600 : undefined,
                }}
              >
                <IconEcheance className="h-3.5 w-3.5" aria-hidden />
                {next.label} · {formatDateShort(next.date)}
              </span>
            )}
          </div>

          <span
            className="inline-flex shrink-0 items-center gap-1 text-[12px] font-semibold"
            style={{ color: C.orange }}
          >
            Voir le projet
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </span>
        </div>
      </div>
    </Link>
  );
}

export function ProjectsInProgress({ monuments, statsByMonument, stageByMonument }: ProjectsInProgressProps) {
  if (monuments.length === 0) {
    return (
      <div
        className="relative flex flex-col items-center justify-center gap-3 overflow-hidden rounded-2xl border px-6 py-12 text-center"
        style={{ background: C.card, borderColor: C.border }}
      >
        <div
          className="relative mb-1 flex h-14 w-14 items-center justify-center overflow-hidden rounded-2xl"
          style={{ background: `linear-gradient(135deg, ${C.blue}, ${C.blueDark})` }}
        >
          <Clover size={70} className="pointer-events-none absolute -right-4 -top-5 text-white" style={{ opacity: 0.12 }} />
          <IconProjet className="relative h-6 w-6 text-white" aria-hidden />
        </div>
        <p className="text-[15px] font-semibold" style={{ fontFamily: 'var(--font-serif)', color: C.ink }}>
          Aucun projet en cours
        </p>
        <p className="max-w-xs text-[12px]" style={{ color: C.ink, opacity: 0.55 }}>
          Créez un projet pour estimer vos aides et suivre vos dossiers au même endroit.
        </p>
        <Link
          to={ROUTES.PROJET_NEW}
          className="mt-1 inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-[12px] font-semibold text-white transition-opacity hover:opacity-90"
          style={{ background: C.orange }}
        >
          Nouveau projet
          <ChevronRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    );
  }

  if (monuments.length === 1) {
    const m = monuments[0];
    return <ProjectCard monument={m} stats={statsByMonument[m.id]} stage={stageByMonument?.[m.id]} featured />;
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 2xl:grid-cols-3">
      {monuments.map((m) => (
        <ProjectCard key={m.id} monument={m} stats={statsByMonument[m.id]} stage={stageByMonument?.[m.id]} />
      ))}
    </div>
  );
}
