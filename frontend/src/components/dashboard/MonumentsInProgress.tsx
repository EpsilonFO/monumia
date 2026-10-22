import { useTranslation } from 'react-i18next';
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
import { monumentPhotoUrl } from '@/lib/monument-photo';
import { sharedRole } from '@/lib/project-permissions';
import { C, DEADLINE_TONE } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { formatDateShort } from '@/lib/date-utils';
import { ParcoursStepper } from './ParcoursStepper';
import type { Monument } from '@/types';
import type { MonumentStats, ProjectStage } from '@/lib/project-stats';

interface MonumentsInProgressProps {
  monuments: Monument[];
  statsByMonument: Record<string, MonumentStats>;
  /** Avancement du projet le plus avancé du monument, quand il en a un. */
  stageByMonument?: Record<string, ProjectStage>;
}

/**
 * Ombre posée sous le titre, et rien d'autre : la photo garde ses couleurs, le
 * bleu Monumia ne la teinte plus. Le dégradé reste neutre et confiné au tiers
 * bas — le titre blanc doit rester lisible sur un ciel clair.
 */
const PHOTO_SCRIM =
  'linear-gradient(to top, rgba(0,0,0,0.72) 0%, rgba(0,0,0,0.34) 28%, rgba(0,0,0,0) 58%)';

/** Badge en verre posé sur le héros (rôle sur projet partagé). */
function GlassBadge({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[13px] font-semibold text-white"
      style={{
        background: 'rgba(255,255,255,0.16)',
        border: '1px solid rgba(255,255,255,0.30)',
        backdropFilter: 'blur(9px)',
        WebkitBackdropFilter: 'blur(9px)',
      }}
    >
      {children}
    </span>
  );
}

function MonumentTile({
  monument,
  stats,
  stage,
  featured = false,
}: {
  monument: Monument;
  stats?: MonumentStats;
  stage?: ProjectStage;
  featured?: boolean;
}) {
  const { t } = useTranslation('dashboard');
  const dossiersActifs = stats?.dossiersActifs ?? 0;
  const next = stats?.prochaineEcheance ?? null;
  const photo = monumentPhotoUrl(monument);
  const role = sharedRole(monument.myRole);

  return (
    <Link
      to={ROUTES.MONUMENT_DETAIL(monument.id)}
      className="group relative flex h-full flex-col overflow-hidden rounded-2xl border transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_24px_50px_-28px_rgba(7,42,114,0.6)]"
      style={{ borderColor: C.border, background: C.card }}
    >
      {/* ── Héros : photo du monument, sinon dégradé bleu + fleur Monumia ── */}
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
          <p
            className={`line-clamp-2 font-bold leading-tight text-white ${
              featured ? 'text-[clamp(1.6rem,3vw,2.4rem)]' : 'text-[23px]'
            }`}
            style={{ fontFamily: 'var(--font-serif)' }}
          >
            {monument.nom}
          </p>
          {(monument.commune || monument.departement) && (
            <p
              className="mt-1.5 inline-flex items-center gap-1.5 text-[14px]"
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
            className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[14px] text-foreground/70"
          >
            <span className="inline-flex items-center gap-1.5">
              <IconDossier className="h-3.5 w-3.5" aria-hidden />
              {t('MonumentsInProgress.dossiers', { count: dossiersActifs })}
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
            className="inline-flex shrink-0 items-center gap-1 text-[14px] font-semibold"
            style={{ color: C.orange }}
          >
            {t('voirMonument')}
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </span>
        </div>
      </div>
    </Link>
  );
}

export function MonumentsInProgress({ monuments, statsByMonument, stageByMonument }: MonumentsInProgressProps) {
  const { t } = useTranslation('dashboard');
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
        <p className="text-[17px] font-semibold" style={{ fontFamily: 'var(--font-serif)', color: C.ink }}>
          {t('MonumentsInProgress.aucunMonument')}
        </p>
        <p className="max-w-xs text-[14px]" style={{ color: C.ink, opacity: 0.55 }}>
          {t('MonumentsInProgress.aucunMonumentIndice')}
        </p>
        <Link
          to={ROUTES.MONUMENT_NEW}
          className="mt-1 inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-[14px] font-semibold text-white transition-opacity hover:opacity-90"
          style={{ background: C.orange }}
        >
          {t('nouveauMonument')}
          <ChevronRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    );
  }

  if (monuments.length === 1) {
    const m = monuments[0];
    return <MonumentTile monument={m} stats={statsByMonument[m.id]} stage={stageByMonument?.[m.id]} featured />;
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 2xl:grid-cols-3">
      {monuments.map((m) => (
        <MonumentTile key={m.id} monument={m} stats={statsByMonument[m.id]} stage={stageByMonument?.[m.id]} />
      ))}
    </div>
  );
}
