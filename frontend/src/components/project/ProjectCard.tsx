import { Link } from 'react-router';
import { ArrowUpRight } from 'lucide-react';
import {
  IconLocalisation,
  IconProtection,
  IconAccompagnement,
  IconEcheance,
  IconSubvention,
  IconDiagnostic,
} from '@/components/icons';
import { Clover } from '@/components/illustrations';
import { ParcoursTrail } from '@/components/project/ParcoursTrail';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { deadlineLabel } from '@/lib/date-utils';
import { formatCurrency } from '@/lib/format-utils';
import { montantTileMode } from '@/lib/project-card-view';
import { RoleBadge } from '@/components/sharing/RoleBadge';
import { SharedBadge } from '@/components/sharing/SharedBadge';
import { MemberAvatarStack } from '@/components/sharing/MemberAvatarStack';
import { isProjectShared } from '@/lib/project-permissions';
import type { ProjectStats, ProjectStage } from '@/lib/project-stats';
import type { Monument } from '@/types';

interface ProjectCardProps {
  monument: Monument;
  stats?: ProjectStats;
  stage?: ProjectStage;
}

const protectionLabels: Record<string, string> = {
  classe: 'Classé MH',
  inscrit: 'Inscrit MH',
  abords: 'Abords MH',
  spr: 'SPR',
  non_protege: 'Non protégé',
};

const etatStyles: Record<string, { bg: string; text: string; label: string }> = {
  bon: { bg: 'var(--success-muted)', text: 'var(--success)', label: 'Bon état' },
  moyen: { bg: 'var(--warning-muted)', text: 'var(--warning)', label: 'État moyen' },
  mauvais: { bg: 'var(--cat-2-soft)', text: 'var(--cat-2)', label: 'Mauvais état' },
  peril: { bg: 'var(--destructive-muted)', text: 'var(--destructive)', label: 'En péril' },
};

// Code couleur unique des échéances : < 30 j (ou dépassée) → rouge · 30–100 j → orange · > 100 j → bleu
const urgencyColor: Record<string, string> = {
  past: C.danger,
  urgent: C.danger,
  warning: C.orange,
  normal: C.blue,
};

/** Petit intitulé éditorial (filet orange + petites caps), repris de la landing/dashboard. */
function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em]"
      style={{ color: C.blue }}
    >
      <span aria-hidden style={{ width: 18, height: 2, borderRadius: 2, background: C.orange }} />
      {children}
    </span>
  );
}

export function ProjectCard({ monument, stats, stage }: ProjectCardProps) {
  const etat = etatStyles[monument.etatConservation] ?? etatStyles.moyen;
  const shared = isProjectShared(monument);
  const role = shared ? monument.myRole ?? null : null;
  const members = monument.members ?? [];
  const next = stats?.prochaineEcheance ?? null;
  const nextLabel = next ? deadlineLabel(next.date) : null;
  const tileMode = montantTileMode(stats);

  return (
    <Link to={ROUTES.PROJET_DETAIL(monument.id)}>
      <div
        className="group relative flex h-full flex-col overflow-hidden rounded-2xl border transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_24px_50px_-28px_rgba(7,42,114,0.6)]"
        style={{ background: C.card, borderColor: C.border }}
      >
        {/* Filigrane décoratif (quadrilobe), jamais de photo */}
        <Clover
          size={150}
          className="pointer-events-none absolute -right-10 -top-12"
          style={{ color: C.blue, opacity: 0.04 }}
        />

        {/* 1 · En-tête identité */}
        <div className="relative px-5 pt-5">
          <h3
            className="line-clamp-2 text-[17px] leading-tight"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
            {monument.nom}
          </h3>
          <div className="mt-1.5 flex items-center gap-1.5 text-[12px] text-muted-foreground">
            <IconLocalisation className="h-3.5 w-3.5 shrink-0" strokeWidth={1.8} aria-hidden />
            <span className="truncate">
              {monument.commune ?? '—'}
              {monument.departement ? ` (${monument.departement})` : ''}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {shared && <SharedBadge count={monument.memberCount} />}
            {role && <RoleBadge role={role} />}
            <span
              className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium"
              style={{ background: C.paleBlue, color: C.blue }}
            >
              <IconProtection className="h-3 w-3" strokeWidth={2} aria-hidden />
              {protectionLabels[monument.protection] ?? monument.protection}
            </span>
            <span
              className="inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-medium"
              style={{ background: etat.bg, color: etat.text }}
            >
              {etat.label}
            </span>
          </div>
        </div>

        {/* 2 · Parcours illustré */}
        {stage && (
          <div className="relative mt-5 px-5">
            <Kicker>Votre parcours</Kicker>
            <div className="mt-3">
              <ParcoursTrail stage={stage} />
            </div>
          </div>
        )}

        {/* 3 · Tuile motivation (montant) */}
        <div className="relative mt-5 px-5">
          <div className="rounded-xl px-4 py-3" style={{ background: C.paleBlue }}>
            {tileMode === 'money' && stats ? (
              <div className="flex items-center gap-3">
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                  style={{ background: '#fff', color: C.orange }}
                >
                  <IconSubvention className="h-5 w-5" strokeWidth={2} aria-hidden />
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-muted-foreground">Jusqu'à</p>
                  <p
                    className="leading-none"
                    style={{ fontFamily: SERIF, color: C.blue }}
                  >
                    <span className="text-[22px] font-bold">{formatCurrency(stats.montantPotentiel)}</span>
                  </p>
                  <p className="mt-1 text-[12px] text-muted-foreground">
                    {stats.aidesIdentifiees} aide{stats.aidesIdentifiees > 1 ? 's' : ''} identifiée
                    {stats.aidesIdentifiees > 1 ? 's' : ''}
                  </p>
                </div>
              </div>
            ) : tileMode === 'count' && stats ? (
              <div className="flex items-center gap-3">
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                  style={{ background: '#fff', color: C.blue }}
                >
                  <IconAccompagnement className="h-5 w-5" strokeWidth={2} aria-hidden />
                </span>
                <p className="text-[13px] font-semibold" style={{ color: C.ink }}>
                  {stats.aidesIdentifiees} aide{stats.aidesIdentifiees > 1 ? 's' : ''} identifiée
                  {stats.aidesIdentifiees > 1 ? 's' : ''}
                </p>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                  style={{ background: '#fff', color: C.orange }}
                >
                  <IconDiagnostic className="h-5 w-5" strokeWidth={2} aria-hidden />
                </span>
                <p className="text-[13px] font-medium" style={{ color: C.ink }}>
                  Lancez l'estimation pour découvrir vos aides
                </p>
              </div>
            )}
          </div>
        </div>

        {/* 4 · Pied : échéance / avatars + affordance d'ouverture */}
        <div
          className="relative mt-5 flex items-center justify-between gap-3 border-t px-5 py-4"
          style={{ borderColor: C.border }}
        >
          <div className="min-w-0 text-[12px]">
            {shared && members.length > 0 ? (
              <MemberAvatarStack people={members} size="sm" />
            ) : next && nextLabel ? (
              <span
                className="inline-flex items-center gap-1.5 font-medium"
                style={{ color: urgencyColor[nextLabel.urgency] ?? 'var(--muted-foreground)' }}
              >
                <IconEcheance className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
                {nextLabel.text}
              </span>
            ) : (
              <span className="text-muted-foreground">Aucune échéance</span>
            )}
          </div>
          <span
            className="inline-flex shrink-0 items-center gap-1 text-[12px] font-semibold"
            style={{ color: C.orange }}
          >
            Ouvrir
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </span>
        </div>
      </div>
    </Link>
  );
}
