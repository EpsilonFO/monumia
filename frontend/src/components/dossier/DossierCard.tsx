import { Link } from 'react-router';
import { Calendar, ChevronRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { DOSSIER_STATUS_LABELS, DOSSIER_STEPS } from '@/constants/dossier-steps';
import { ROUTES } from '@/constants/routes';
import { formatDate, daysUntil, isUrgent } from '@/lib/date-utils';
import type { Dossier } from '@/types';

interface DossierCardProps {
  dossier: Dossier;
}

export function DossierCard({ dossier }: DossierCardProps) {
  const statusConfig = DOSSIER_STATUS_LABELS[dossier.statut];
  const stepConfig = DOSSIER_STEPS.find((s) => s.step === dossier.etapeActuelle);
  const nextDeadline = dossier.echeances.find((e) => !e.accomplie);

  return (
    <Link to={ROUTES.DOSSIER_DETAIL(dossier.id)}>
      <Card className="hover:shadow-md hover:border-primary/30 transition-all group">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-sm leading-tight">
              {dossier.titre}
            </CardTitle>
            <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors shrink-0 mt-0.5" />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge className={statusConfig?.color ?? ''}>
              {statusConfig?.label ?? dossier.statut}
            </Badge>
            <span className="text-xs text-muted-foreground">
              Étape {dossier.etapeActuelle}/5
              {stepConfig && <> — {stepConfig.label}</>}
            </span>
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Progression</span>
              <span className="font-medium">{dossier.progressionPourcentage} %</span>
            </div>
            <Progress value={dossier.progressionPourcentage} className="h-1.5" />
          </div>

          {nextDeadline && (
            <div className={`flex items-center gap-1.5 text-xs ${isUrgent(nextDeadline.date) ? 'text-red-600 font-medium' : 'text-muted-foreground'}`}>
              <Calendar className="h-3 w-3" />
              <span>
                {nextDeadline.label} — {formatDate(nextDeadline.date)}
                {isUrgent(nextDeadline.date) && ` (${daysUntil(nextDeadline.date)} j)`}
              </span>
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
