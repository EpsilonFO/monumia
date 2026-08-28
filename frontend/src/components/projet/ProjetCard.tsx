import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { IconEcheance, IconDossier } from '@/components/icons';
import { Clover } from '@/components/illustrations';
import { ParcoursTrail } from '@/components/project/ParcoursTrail';
import { ROUTES } from '@/constants/routes';
import { C, DEADLINE_TONE, SERIF } from '@/lib/brand';
import { deadlineLabel } from '@/lib/date-utils';
import { montantTileMode } from '@/lib/project-card-view';
import { projetTitre } from '@/lib/projet-titre';
import type { ProjectStats, ProjectStage } from '@/lib/project-stats';
import type { Projet } from '@/types';

interface ProjetCardProps {
  projet: Projet;
  stats?: ProjectStats;
  stage?: ProjectStage;
}

/**
 * Verbe d'action selon l'étape atteinte — le bouton dit toujours en clair la
 * prochaine chose à faire (public peu à l'aise : jamais un « Voir » ambigu).
 * Indexé par `reachedIndex` (-1 = rien de commencé).
 */
function ctaLabel(reachedIndex: number): string {
  switch (reachedIndex) {
    case 0:
      return 'Créer mon dossier';
    case 1:
      return 'Continuer mon dossier';
    case 2:
      return 'Suivre mon dépôt';
    case 3:
      return 'Voir le suivi';
    default:
      return 'Estimer mes aides';
  }
}

/**
 * Vignette d'un projet de travaux, dans l'onglet « Projets » d'un monument.
 * Reprend la mécanique de l'ancienne carte projet — nombre d'aides repérées,
 * frise d'avancement, échéance qui presse — sans répéter l'identité du monument :
 * elle est déjà dans l'en-tête de la page.
 */
export function ProjetCard({ projet, stats, stage }: ProjetCardProps) {
  const tileMode = montantTileMode(stats);
  const reached = stage?.reachedIndex ?? -1;
  const cloture = !!projet.clotureAt;

  // Échéance affichée UNIQUEMENT si elle presse (dépassée, urgente, ou proche).
  const next = stats?.prochaineEcheance ?? null;
  const nextLabel = next ? deadlineLabel(next.date) : null;
  const pressing = nextLabel && nextLabel.urgency !== 'normal';
  const tone = nextLabel ? DEADLINE_TONE[nextLabel.urgency] : null;

  const dossiersActifs = stats?.dossiersActifs ?? 0;

  return (
    <Link to={ROUTES.PROJET_DETAIL(projet.id)} className="block">
      <article
        className="group overflow-hidden rounded-2xl border p-5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_20px_45px_-24px_rgba(7,42,114,0.45)] sm:p-6"
        style={{ background: C.card, borderColor: C.border, opacity: cloture ? 0.75 : 1 }}
      >
        <div className="flex items-start justify-between gap-3">
          <h3
            className="min-w-0 text-[19px] font-bold leading-snug"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
            {projetTitre(projet)}
          </h3>
          {cloture && (
            <span
              className="shrink-0 rounded-full px-3 py-1 text-[12px] font-semibold"
              style={{ background: C.cream, color: C.grayFg }}
            >
              Clôturé
            </span>
          )}
        </div>

        {/* ── Deux tuiles teintées : aides repérées + avancement ── */}
        <div className="mt-4 flex flex-col gap-3 lg:flex-row">
          <div
            className="relative flex flex-col justify-center overflow-hidden rounded-xl border px-5 py-4 lg:w-64 lg:shrink-0"
            style={{
              background: `linear-gradient(135deg, ${C.paleOrange}, color-mix(in srgb, ${C.paleOrange} 45%, ${C.card}))`,
              borderColor: `color-mix(in srgb, ${C.orange} 18%, transparent)`,
            }}
          >
            <Clover
              size={86}
              className="pointer-events-none absolute -bottom-6 -right-5"
              style={{ color: C.orange, opacity: 0.08 }}
              aria-hidden
            />
            {tileMode !== 'nudge' && stats ? (
              <>
                <p
                  className="text-[26px] font-bold leading-none tabular-nums"
                  style={{
                    fontFamily: SERIF,
                    // Orange légèrement foncé à l'encre : contraste AA sur la tuile chaude.
                    color: `color-mix(in srgb, ${C.orange} 82%, ${C.ink})`,
                  }}
                >
                  {stats.aidesIdentifiees} aide{stats.aidesIdentifiees > 1 ? 's' : ''}
                </p>
                <p className="mt-1.5 text-[13px] font-medium" style={{ color: C.ink }}>
                  repérée{stats.aidesIdentifiees > 1 ? 's' : ''} pour ce projet
                </p>
              </>
            ) : (
              <>
                <p
                  className="text-[19px] font-bold leading-tight"
                  style={{
                    fontFamily: SERIF,
                    color: `color-mix(in srgb, ${C.orange} 82%, ${C.ink})`,
                  }}
                >
                  Aides à découvrir
                </p>
                <p className="mt-1.5 text-[13px] font-medium" style={{ color: C.ink }}>
                  Quelques questions suffisent
                </p>
              </>
            )}
          </div>

          <div
            className="flex flex-1 flex-col justify-center rounded-xl border px-5 py-4"
            style={{
              background: `linear-gradient(135deg, ${C.paleBlue}, color-mix(in srgb, ${C.paleBlue} 45%, ${C.card}))`,
              borderColor: `color-mix(in srgb, ${C.blue} 14%, transparent)`,
            }}
          >
            <p className="text-[12.5px] font-semibold" style={{ color: C.blue }}>
              Votre avancement
              {reached >= 0 ? ` — étape ${reached + 1} sur 4` : ' — à commencer'}
            </p>
            <div className="mt-3">{stage && <ParcoursTrail stage={stage} />}</div>
          </div>
        </div>

        {/* ── Pied : faits en toutes lettres + bouton d'action évident ── */}
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
            {dossiersActifs > 0 && (
              <span
                className="inline-flex items-center gap-1.5 text-[13px] font-medium"
                style={{ color: C.grayFg }}
              >
                <IconDossier className="h-4 w-4 shrink-0" aria-hidden />
                {dossiersActifs} dossier{dossiersActifs > 1 ? 's' : ''} en cours
              </span>
            )}
            {pressing && nextLabel && tone && (
              <span
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold"
                style={{ color: tone.fg, background: tone.tint }}
              >
                <IconEcheance className="h-4 w-4 shrink-0" strokeWidth={2} aria-hidden />
                {nextLabel.urgency === 'past'
                  ? 'Échéance dépassée'
                  : `Échéance : ${nextLabel.text.toLowerCase()}`}
              </span>
            )}
          </div>
          <span
            className="inline-flex shrink-0 items-center justify-center gap-2 self-stretch rounded-lg px-5 py-2.5 text-[14px] font-semibold text-white transition-all group-hover:shadow-md sm:self-auto"
            style={{ background: C.orange }}
          >
            {ctaLabel(reached)}
            <ArrowRight
              className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5"
              aria-hidden
            />
          </span>
        </div>
      </article>
    </Link>
  );
}
