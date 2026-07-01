import { Link } from 'react-router';
import { IconLocalisation, IconProtection, IconEcheance } from '@/components/icons';
import { Clover } from '@/components/illustrations';
import { ParcoursTrail } from '@/components/project/ParcoursTrail';
import { MemberAvatarStack } from '@/components/sharing/MemberAvatarStack';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
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

const protectionLabels: Record<string, string> = {
  classe: 'Classé Monument Historique',
  inscrit: 'Inscrit Monument Historique',
  abords: 'Abords Monument Historique',
  spr: 'Site patrimonial remarquable',
};

// Code couleur des échéances : dépassée/urgent → rouge · 30–100 j → orange.
const urgencyColor: Record<string, string> = {
  past: C.danger,
  urgent: C.danger,
  warning: C.orange,
};

export function ProjectCard({ monument, stats, stage }: ProjectCardProps) {
  const shared = isProjectShared(monument);
  const members = monument.members ?? [];
  const protection = protectionLabels[monument.protection];

  const tileMode = montantTileMode(stats);

  // Ligne d'étape en clair (une seule) : « Étape 3 sur 4 · Dépôt du dossier ».
  const stepText =
    stage && stage.reachedIndex >= 0
      ? `Étape ${stage.reachedIndex + 1} sur ${PROJECT_STAGES.length} · ${PROJECT_STAGES[stage.reachedIndex].label}`
      : 'À commencer : Estimation';

  // Échéance affichée UNIQUEMENT si elle presse (dépassée, urgente, ou proche).
  const next = stats?.prochaineEcheance ?? null;
  const nextLabel = next ? deadlineLabel(next.date) : null;
  const pressing = nextLabel && nextLabel.urgency !== 'normal';
  const dlColor = nextLabel ? urgencyColor[nextLabel.urgency] : undefined;

  return (
    <Link to={ROUTES.PROJET_DETAIL(monument.id)} className="block h-full">
      <div
        className="group flex h-full flex-col overflow-hidden rounded-2xl border transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_24px_50px_-28px_rgba(7,42,114,0.55)]"
        style={{ background: C.card, borderColor: C.border }}
      >
        {/* En-tête bleu institutionnel */}
        <div
          className="relative px-6 pt-6 pb-7"
          style={{ background: `linear-gradient(135deg, ${C.blue}, ${C.blueDark})` }}
        >
          <div className="flex items-start justify-between gap-3">
            <h3
              className="line-clamp-2 text-[21px] font-bold leading-tight text-white"
              style={{ fontFamily: SERIF }}
            >
              {monument.nom}
            </h3>
            {shared && members.length > 0 && (
              <MemberAvatarStack people={members} size="sm" />
            )}
          </div>
          {(monument.commune || monument.departement) && (
            <p className="mt-2 flex items-center gap-1.5 text-[13.5px] text-white/85">
              <IconLocalisation className="h-4 w-4 shrink-0" strokeWidth={1.8} aria-hidden />
              <span className="truncate">
                {monument.commune ?? '—'}
                {monument.departement ? ` · ${monument.departement}` : ''}
              </span>
            </p>
          )}
          {protection && (
            <span
              className="mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-semibold text-white"
              style={{
                background: 'rgba(255,255,255,0.18)',
                border: '1px solid rgba(255,255,255,0.34)',
              }}
            >
              <IconProtection className="h-3.5 w-3.5" strokeWidth={2.2} aria-hidden />
              {protection}
            </span>
          )}

          {/* Sceau quadrilobe (motif du logo) à cheval sur la couture — signature de marque */}
          <span
            className="absolute bottom-0 right-6 z-10 flex h-12 w-12 translate-y-1/2 items-center justify-center rounded-full border"
            style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
            aria-hidden
          >
            <Clover size={26} style={{ color: C.orange }} />
          </span>
        </div>

        {/* Corps crème, aéré */}
        <div className="flex flex-1 flex-col px-6 pb-6 pt-7">
          {/* Point focal : le montant d'aides, en orange (couleur d'action) */}
          {tileMode === 'money' && stats ? (
            <div>
              <p
                className="text-[11px] font-semibold uppercase tracking-[0.12em]"
                style={{ color: C.orange }}
              >
                Jusqu'à
              </p>
              <p
                className="mt-1 text-[34px] font-bold leading-none tabular-nums"
                style={{ fontFamily: SERIF, color: C.orange }}
              >
                {formatCurrency(stats.montantPotentiel)}
              </p>
              <p className="mt-2 text-[13.5px] font-medium" style={{ color: C.ink }}>
                d'aides à mobiliser
              </p>
            </div>
          ) : tileMode === 'count' && stats ? (
            <div>
              <p
                className="text-[27px] font-bold leading-none tabular-nums"
                style={{ fontFamily: SERIF, color: C.orange }}
              >
                {stats.aidesIdentifiees} aide{stats.aidesIdentifiees > 1 ? 's' : ''}
              </p>
              <p className="mt-2 text-[13.5px] font-medium" style={{ color: C.ink }}>
                repérée{stats.aidesIdentifiees > 1 ? 's' : ''} pour ce monument
              </p>
            </div>
          ) : (
            <div>
              <p
                className="text-[21px] font-bold leading-tight"
                style={{ fontFamily: SERIF, color: C.orange }}
              >
                Estimez vos aides
              </p>
              <p className="mt-2 text-[13.5px] font-medium" style={{ color: C.ink }}>
                Lancez l'estimation, c'est rapide
              </p>
            </div>
          )}

          {/* Bas de carte : progression toujours présente + échéance si elle presse.
              mt-auto colle le bloc en bas → cartes d'égale hauteur sur une ligne. */}
          <div className="mt-auto pt-7">
            {stage && (
              <>
                <ParcoursTrail stage={stage} accent={C.orange} />
                <p className="mt-3 text-[13.5px] font-semibold" style={{ color: C.ink }}>
                  {stepText}
                </p>
              </>
            )}

            {/* Emplacement d'échéance TOUJOURS réservé (hauteur fixe) pour que la
                présence/absence d'échéance ne change pas la hauteur de la carte. */}
            <div className="mt-3 flex min-h-[30px] items-center">
              {pressing && nextLabel && (
                <span
                  className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold"
                  style={{
                    color: dlColor,
                    background: `color-mix(in srgb, ${dlColor} 14%, transparent)`,
                  }}
                >
                  <IconEcheance className="h-4 w-4" strokeWidth={2} aria-hidden />
                  {nextLabel.urgency === 'past' ? 'En retard : ' : 'À faire avant le '}
                  {nextLabel.text}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}
