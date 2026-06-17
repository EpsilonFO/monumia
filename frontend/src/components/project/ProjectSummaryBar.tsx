import { MapPin, Shield, Sparkles, Coins, CalendarClock, RefreshCw, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { C, SERIF } from '@/lib/brand';
import { formatCurrency } from '@/lib/format-utils';
import { deadlineLabel } from '@/lib/date-utils';
import { PROTECTION_LABELS_SHORT, ETAT_LABELS } from '@/constants/monument-options';
import type { ProjectStats } from '@/lib/project-stats';
import type { Monument } from '@/types';

interface ProjectSummaryBarProps {
  monument: Monument;
  stats: ProjectStats;
  onRelancer: () => void;
  relancing?: boolean;
}

export function ProjectSummaryBar({ monument, stats, onRelancer, relancing = false }: ProjectSummaryBarProps) {
  const echeance = stats.prochaineEcheance;
  const echeanceLabel = echeance ? deadlineLabel(echeance.date) : null;
  // Code couleur unique : < 30 j (ou dépassée) → rouge · 30–100 j → orange · > 100 j → bleu
  const echeanceColor =
    echeanceLabel?.urgency === 'urgent' || echeanceLabel?.urgency === 'past'
      ? C.danger
      : echeanceLabel?.urgency === 'warning'
        ? C.orange
        : C.blue;

  const location = [monument.commune, monument.departement].filter(Boolean).join(' · ');

  return (
    <div
      className="rounded-2xl border p-6 sm:p-7"
      style={{ background: C.card, borderColor: C.border }}
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3 min-w-0">
          <h1 className="text-[clamp(1.5rem,3vw,2rem)] leading-tight" style={{ fontFamily: SERIF, color: C.ink }}>
            {monument.nom}
          </h1>
          {location && (
            <div className="flex items-center gap-1.5 text-[14px]" style={{ color: '#6a7180' }}>
              <MapPin className="h-3.5 w-3.5" style={{ color: C.blueLight }} />
              <span>{location}</span>
            </div>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className="gap-1" style={{ borderColor: C.border, color: C.blue, background: C.paleBlue }}>
              <Shield className="h-3 w-3" />
              {PROTECTION_LABELS_SHORT[monument.protection] ?? monument.protection}
            </Badge>
            <Badge variant="outline" style={{ borderColor: C.border, color: C.ink }}>
              {ETAT_LABELS[monument.etatConservation] ?? monument.etatConservation}
            </Badge>
          </div>
        </div>

        <button
          onClick={onRelancer}
          disabled={relancing}
          className="inline-flex items-center justify-center gap-2 px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md disabled:opacity-60 shrink-0"
          style={{ background: C.orange }}
        >
          {relancing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" strokeWidth={2} />}
          Relancer le moteur
        </button>
      </div>

      <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <KpiTile
          icon={<Sparkles className="h-4 w-4" style={{ color: C.blue }} />}
          label="Aides identifiées"
          value={String(stats.aidesIdentifiees)}
        />
        <KpiTile
          icon={<Coins className="h-4 w-4" style={{ color: C.orange }} />}
          label="Montant potentiel"
          value={stats.montantPotentiel > 0 ? formatCurrency(stats.montantPotentiel) : '—'}
        />
        <KpiTile
          icon={<CalendarClock className="h-4 w-4" style={{ color: echeanceColor }} />}
          label="Prochaine échéance"
          value={echeanceLabel ? echeanceLabel.text : 'Aucune'}
          valueColor={echeanceLabel ? echeanceColor : undefined}
        />
      </div>
    </div>
  );
}

function KpiTile({ icon, label, value, valueColor }: { icon: React.ReactNode; label: string; value: string; valueColor?: string }) {
  return (
    <div className="rounded-xl border px-4 py-3" style={{ borderColor: C.border, background: C.cream }}>
      <div className="flex items-center gap-1.5 text-[12px]" style={{ color: '#6a7180' }}>
        {icon}
        <span>{label}</span>
      </div>
      <p className="mt-1 text-[18px] font-semibold" style={{ color: valueColor ?? C.ink }}>
        {value}
      </p>
    </div>
  );
}
