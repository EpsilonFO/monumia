import { Link } from 'react-router';
import { ArrowUpRight } from 'lucide-react';
import { IconLocalisation, IconEcheance, IconParchemin } from '@/components/icons';
import { Clover } from '@/components/illustrations';
import { ParcoursTrail } from '@/components/project/ParcoursTrail';
import { MemberAvatarStack } from '@/components/sharing/MemberAvatarStack';
import { ROUTES } from '@/constants/routes';
import { C, DEADLINE_TONE, SERIF } from '@/lib/brand';
import { deadlineLabel } from '@/lib/date-utils';
import { formatCurrency } from '@/lib/format-utils';
import { montantTileMode } from '@/lib/project-card-view';
import { isProjectShared } from '@/lib/project-permissions';
import { PROJECT_STAGES } from '@/lib/project-stats';
import type { ProjectStats, ProjectStage } from '@/lib/project-stats';
import type { Monument } from '@/types';

interface ProjectCardProps {
  monument: Monument;
  stats?: ProjectStats;
  stage?: ProjectStage;
}

/** Voile bleu Monumia posé sur la photo : laisse respirer le cliché en haut, plombe
 *  le bas en bleu profond pour que le titre blanc reste lisible sur n'importe quelle image. */
const PHOTO_SCRIM =
  'linear-gradient(to top, rgba(7,42,114,0.94) 8%, rgba(7,42,114,0.55) 45%, rgba(7,42,114,0.10) 85%)';

/** Photo héros : on privilégie la façade, sinon le premier cliché disponible. */
function heroPhoto(m: Monument): string | null {
  if (!m.photos?.length) return null;
  const facade = m.photos.find((p) => p.type === 'facade');
  return (facade ?? m.photos[0])?.url || null;
}

export function ProjectCard({ monument, stats, stage }: ProjectCardProps) {
  const shared = isProjectShared(monument);
  const members = monument.members ?? [];
  const photo = heroPhoto(monument);

  const tileMode = montantTileMode(stats);

  // Kicker : l'étape du parcours en petites capitales — l'info de progression
  // sert d'« eyebrow » éditorial, la frise en bas reste purement visuelle.
  const kickerText =
    stage && stage.reachedIndex >= 0
      ? `Étape ${stage.reachedIndex + 1} sur ${PROJECT_STAGES.length} · ${PROJECT_STAGES[stage.reachedIndex].label}`
      : 'À commencer · Estimation';

  // Échéance affichée UNIQUEMENT si elle presse (dépassée, urgente, ou proche).
  const next = stats?.prochaineEcheance ?? null;
  const nextLabel = next ? deadlineLabel(next.date) : null;
  const pressing = nextLabel && nextLabel.urgency !== 'normal';
  const tone = nextLabel ? DEADLINE_TONE[nextLabel.urgency] : null;

  const dossiersActifs = stats?.dossiersActifs ?? 0;

  return (
    <Link to={ROUTES.PROJET_DETAIL(monument.id)} className="block h-full">
      <div
        className="group flex h-full flex-col overflow-hidden rounded-2xl border transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_24px_50px_-28px_rgba(7,42,114,0.55)]"
        style={{ background: C.card, borderColor: C.border }}
      >
        {/* ── Héros : photo du monument (zoom doux au survol), sinon bleu + quadrilobe ── */}
        <div
          className="relative h-44 shrink-0 overflow-hidden"
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
              size={230}
              className="pointer-events-none absolute -right-16 -top-20 text-white transition-transform duration-700 ease-out group-hover:scale-110"
              style={{ opacity: 0.09 }}
            />
          )}

          {shared && members.length > 0 && (
            <div className="absolute right-3 top-3">
              <MemberAvatarStack people={members} size="sm" />
            </div>
          )}

          {/* Titre en surimpression, ancré en bas → hauteur de héros constante */}
          <div className="absolute inset-x-0 bottom-0 p-5">
            <p
              className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em]"
              style={{ color: 'rgba(255,255,255,0.82)' }}
            >
              <span aria-hidden style={{ width: 18, height: 2, borderRadius: 2, background: C.orange }} />
              {kickerText}
            </p>
            <h3
              className="mt-2 line-clamp-2 text-[21px] font-bold leading-tight text-white"
              style={{ fontFamily: SERIF }}
            >
              {monument.nom}
            </h3>
            {(monument.commune || monument.departement) && (
              <p
                className="mt-1.5 flex items-center gap-1.5 text-[12.5px]"
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

        {/* ── Corps clair : le montant d'aides en point focal (couleur d'action) ── */}
        <div className="flex flex-1 flex-col p-5">
          {tileMode === 'money' && stats ? (
            <div>
              <p
                className="text-[11px] font-semibold uppercase tracking-[0.12em]"
                style={{ color: C.orange }}
              >
                Jusqu'à
              </p>
              <p
                className="mt-1 text-[32px] font-bold leading-none tabular-nums"
                style={{ fontFamily: SERIF, color: C.orange }}
              >
                {formatCurrency(stats.montantPotentiel)}
              </p>
              <p className="mt-1.5 text-[13.5px] font-medium" style={{ color: C.ink }}>
                d'aides à mobiliser
              </p>
            </div>
          ) : tileMode === 'count' && stats ? (
            <div>
              <p
                className="text-[26px] font-bold leading-none tabular-nums"
                style={{ fontFamily: SERIF, color: C.orange }}
              >
                {stats.aidesIdentifiees} aide{stats.aidesIdentifiees > 1 ? 's' : ''}
              </p>
              <p className="mt-1.5 text-[13.5px] font-medium" style={{ color: C.ink }}>
                repérée{stats.aidesIdentifiees > 1 ? 's' : ''} pour ce monument
              </p>
            </div>
          ) : (
            <div>
              <p
                className="text-[20px] font-bold leading-tight"
                style={{ fontFamily: SERIF, color: C.orange }}
              >
                Estimez vos aides
              </p>
              <p className="mt-1.5 text-[13.5px] font-medium" style={{ color: C.ink }}>
                Lancez l'estimation, c'est rapide
              </p>
            </div>
          )}

          {/* ── Bas de carte : frise + échéance (emplacement réservé) + pied ──
              mt-auto colle le bloc en bas → cartes d'égale hauteur sur une ligne. */}
          <div className="mt-auto pt-6">
            {stage && <ParcoursTrail stage={stage} accent={C.orange} />}

            {/* Emplacement d'échéance TOUJOURS réservé (hauteur fixe) pour que la
                présence/absence d'échéance ne change pas la hauteur de la carte. */}
            <div className="mt-3.5 flex min-h-[30px] items-center">
              {pressing && nextLabel && tone && (
                <span
                  className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold"
                  style={{ color: tone.fg, background: tone.tint }}
                >
                  <IconEcheance className="h-4 w-4" strokeWidth={2} aria-hidden />
                  {nextLabel.urgency === 'past'
                    ? 'Échéance dépassée'
                    : `Échéance : ${nextLabel.text.toLowerCase()}`}
                </span>
              )}
            </div>

            <div
              className="mt-3.5 flex items-center justify-between gap-4 border-t pt-3.5"
              style={{ borderColor: C.border }}
            >
              <span className="inline-flex items-center gap-1.5 text-[12px]" style={{ color: C.grayFg }}>
                <IconParchemin className="h-3.5 w-3.5" aria-hidden />
                {dossiersActifs > 0
                  ? `${dossiersActifs} dossier${dossiersActifs > 1 ? 's' : ''} en cours`
                  : 'Aucun dossier en cours'}
              </span>
              <span
                className="inline-flex shrink-0 items-center gap-1 text-[12px] font-semibold"
                style={{ color: C.orange }}
              >
                Voir le projet
                <ArrowUpRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
              </span>
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}
