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

const MONUMENT_COLORS = [
  'bg-blue-100 text-blue-700',
  'bg-purple-100 text-purple-700',
  'bg-amber-100 text-amber-700',
  'bg-emerald-100 text-emerald-700',
  'bg-rose-100 text-rose-700',
  'bg-cyan-100 text-cyan-700',
  'bg-indigo-100 text-indigo-700',
  'bg-teal-100 text-teal-700',
  'bg-orange-100 text-orange-700',
  'bg-fuchsia-100 text-fuchsia-700',
];

export function DossierCard({ dossier }: DossierCardProps) {
  const nextDeadline = dossier.echeances.find((e) => !e.accomplie);
  const [aide, monument, travaux] = dossier.titre.split(' — ');

  // Couleur par position du monument dans la liste (garantit des couleurs distinctes)
  const monuments = useMonumentStore((s) => s.monuments);
  const monumentIndex = monuments.findIndex((m) => m.id === dossier.monumentId);
  const badgeColor = MONUMENT_COLORS[(monumentIndex >= 0 ? monumentIndex : 0) % MONUMENT_COLORS.length];

  return (
    <Link to={ROUTES.DOSSIER_DETAIL(dossier.id)}>
      <div className="flex items-center gap-3 p-3 rounded-lg border hover:bg-muted/50 transition-colors group">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge className={`text-xs font-semibold shrink-0 ${badgeColor}`}>{monument}</Badge>
            <span className="text-sm font-medium text-foreground">{aide}</span>
            {travaux && (
              <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{travaux}</span>
            )}
          </div>
          {nextDeadline && (
            <p className={`text-xs ${isUrgent(nextDeadline.date) ? 'text-red-600 font-medium' : 'text-muted-foreground'}`}>
              <Calendar className="h-3 w-3 inline mr-1" />
              {nextDeadline.label} — {formatDate(nextDeadline.date)}
              {isUrgent(nextDeadline.date) && ` (${daysUntil(nextDeadline.date)}j)`}
            </p>
          )}
        </div>
        <Progress value={dossier.progressionPourcentage} className="w-20 h-1.5 shrink-0" />
        <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-primary shrink-0" />
      </div>
    </Link>
  );
}
