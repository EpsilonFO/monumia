import { Link } from 'react-router';
import { Calendar, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { ROUTES } from '@/constants/routes';
import { formatDate, daysUntil, isUrgent } from '@/lib/date-utils';
import type { Dossier } from '@/types';

interface DossierCardProps {
  dossier: Dossier;
}

const MONUMENT_ACCENTS = [
  { bg: '#E8EAF6', text: '#1A237E' },
  { bg: '#FBF0EC', text: '#C75B3A' },
  { bg: '#FEF3C7', text: '#92400E' },
  { bg: '#ECFDF5', text: '#065F46' },
  { bg: '#F3E8FF', text: '#7C3AED' },
  { bg: '#E0F7FA', text: '#006064' },
  { bg: '#FCE4EC', text: '#880E4F' },
  { bg: '#FFF3E0', text: '#BF360C' },
];

export function DossierCard({ dossier }: DossierCardProps) {
  const nextDeadline = dossier.echeances.find((e) => !e.accomplie);
  const [aide, monument, travaux] = dossier.titre.split(' — ');

  const monuments = useMonumentStore((s) => s.monuments);
  const monumentIndex = monuments.findIndex((m) => m.id === dossier.monumentId);
  const accent = MONUMENT_ACCENTS[(monumentIndex >= 0 ? monumentIndex : 0) % MONUMENT_ACCENTS.length];

  return (
    <Link to={ROUTES.DOSSIER_DETAIL(dossier.id)}>
      <div className="group bg-white rounded-xl border border-[#E4E2DC]/80 overflow-hidden transition-all duration-200 hover:shadow-md hover:shadow-black/[0.03] hover:border-[#E4E2DC] flex items-center gap-4 p-4">
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              className="text-[10px] font-semibold shrink-0 border-0"
              style={{ background: accent.bg, color: accent.text }}
            >
              {monument}
            </Badge>
            <span className="text-[13px] font-medium text-[#1B1E2E]">{aide}</span>
            {travaux && (
              <span className="text-[11px] text-[#8E92A4] bg-[#F8F7F4] px-1.5 py-0.5 rounded">{travaux}</span>
            )}
          </div>
          {nextDeadline && (
            <p className={`text-[12px] flex items-center gap-1 ${isUrgent(nextDeadline.date) ? 'text-red-600 font-medium' : 'text-[#8E92A4]'}`}>
              <Calendar className="h-3 w-3" strokeWidth={1.8} />
              {nextDeadline.label} — {formatDate(nextDeadline.date)}
              {isUrgent(nextDeadline.date) && ` (${daysUntil(nextDeadline.date)}j)`}
            </p>
          )}
        </div>
        <div className="w-20 shrink-0">
          <Progress value={dossier.progressionPourcentage} className="h-1.5" />
          <p className="text-[11px] font-semibold text-[#5C6178] text-right mt-0.5 tabular-nums">
            {dossier.progressionPourcentage}%
          </p>
        </div>
        <ChevronRight className="h-4 w-4 text-[#E4E2DC] group-hover:text-[#1A237E] shrink-0 transition-colors" />
      </div>
    </Link>
  );
}
