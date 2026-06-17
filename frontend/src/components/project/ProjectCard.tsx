import { Link } from 'react-router';
import { MapPin, Shield, ChevronRight, Sparkles, CalendarClock } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { deadlineLabel } from '@/lib/date-utils';
import type { ProjectStats } from '@/lib/project-stats';
import type { Monument } from '@/types';

interface ProjectCardProps {
  monument: Monument;
  stats?: ProjectStats;
}

const protectionLabels: Record<string, string> = {
  classe: 'Classé MH',
  inscrit: 'Inscrit MH',
  abords: 'Abords MH',
  spr: 'SPR',
  non_protege: 'Non protégé',
};

const etatStyles: Record<string, { bg: string; text: string; label: string }> = {
  bon: { bg: '#ECFDF5', text: '#065F46', label: 'Bon état' },
  moyen: { bg: '#FEF3C7', text: '#92400E', label: 'État moyen' },
  mauvais: { bg: C.paleOrange, text: C.orange, label: 'Mauvais état' },
  peril: { bg: '#FFEBEE', text: '#B71C1C', label: 'En péril' },
};

// Code couleur unique des échéances : < 30 j (ou dépassée) → rouge · 30–100 j → orange · > 100 j → bleu
const urgencyColor: Record<string, string> = {
  past: C.danger,
  urgent: C.danger,
  warning: C.orange,
  normal: C.blue,
};

export function ProjectCard({ monument, stats }: ProjectCardProps) {
  const etat = etatStyles[monument.etatConservation] ?? etatStyles.moyen;
  const next = stats?.prochaineEcheance ?? null;
  const nextLabel = next ? deadlineLabel(next.date) : null;

  return (
    <Link to={ROUTES.PROJET_DETAIL(monument.id)}>
      <div
        className="group flex h-full flex-col overflow-hidden rounded-xl border transition-all duration-200 hover:shadow-md"
        style={{ background: C.card, borderColor: C.border }}
      >
        <div className="px-5 pt-5 pb-3">
          <div className="mb-2 flex items-start justify-between gap-2">
            <h3
              className="line-clamp-2 h-[2.6em] text-[16px] leading-tight"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {monument.nom}
            </h3>
            <ChevronRight
              className="mt-0.5 h-4 w-4 shrink-0 transition-colors"
              style={{ color: C.border }}
            />
          </div>
          <div className="flex items-center gap-1.5 text-[12px]" style={{ color: '#6a7180' }}>
            <MapPin className="h-3 w-3 shrink-0" strokeWidth={1.8} />
            <span>
              {monument.commune ?? '—'}
              {monument.departement ? ` (${monument.departement})` : ''}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5 px-5 pb-3">
          <span
            className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium"
            style={{ background: C.paleBlue, color: C.blue }}
          >
            <Shield className="h-3 w-3" strokeWidth={2} />
            {protectionLabels[monument.protection] ?? monument.protection}
          </span>
          <span
            className="inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-medium"
            style={{ background: etat.bg, color: etat.text }}
          >
            {etat.label}
          </span>
        </div>

        <div className="mt-auto space-y-3 px-5 pb-5">
          <div>
            <div className="mb-1 flex items-center justify-between text-[11px]" style={{ color: '#6a7180' }}>
              <span>Complétude</span>
              <span className="tabular-nums">{monument.completionPercentage}%</span>
            </div>
            <Progress value={monument.completionPercentage} className="h-1.5" />
          </div>

          {stats && (
            <div className="flex items-center justify-between border-t pt-3 text-[12px]" style={{ borderColor: C.border }}>
              <span className="inline-flex items-center gap-1.5" style={{ color: C.blue }}>
                <Sparkles className="h-3.5 w-3.5" strokeWidth={2} />
                {stats.aidesIdentifiees} aide{stats.aidesIdentifiees > 1 ? 's' : ''}
              </span>
              {next && nextLabel && (
                <span
                  className="inline-flex items-center gap-1.5 font-medium"
                  style={{ color: urgencyColor[nextLabel.urgency] ?? '#6a7180' }}
                >
                  <CalendarClock className="h-3.5 w-3.5" strokeWidth={2} />
                  {nextLabel.text}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
