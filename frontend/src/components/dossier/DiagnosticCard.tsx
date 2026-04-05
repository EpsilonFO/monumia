import { Link } from 'react-router';
import { Compass, ChevronRight, Calendar } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ROUTES } from '@/constants/routes';
import { formatDate } from '@/lib/date-utils';
import type { AideDiagnosticResult, Monument } from '@/types';

interface DiagnosticCardProps {
  diagnostic: AideDiagnosticResult;
  monument: Monument;
}

export function DiagnosticCard({ diagnostic, monument }: DiagnosticCardProps) {
  const nbEligibles = diagnostic.aidesPotentiellementEligibles.length;
  const nbTotal = diagnostic.totalAidesAnalysees;

  return (
    <Card className="hover:shadow-md hover:border-primary/30 transition-all group">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm leading-tight">{monument.nom}</CardTitle>
          <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 shrink-0">
            <Compass className="h-3 w-3 mr-1" />
            Diagnostic fait
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-sm space-y-1">
          <p>
            <span className="font-semibold text-primary">{nbEligibles}</span>
            <span className="text-muted-foreground"> aide{nbEligibles > 1 ? 's' : ''} éligible{nbEligibles > 1 ? 's' : ''} sur {nbTotal} analysée{nbTotal > 1 ? 's' : ''}</span>
          </p>
          {diagnostic.montantPotentielTotal != null && diagnostic.montantPotentielTotal > 0 && (
            <p className="text-muted-foreground">
              Montant potentiel : <span className="font-medium text-foreground">{new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(diagnostic.montantPotentielTotal)}</span>
            </p>
          )}
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {formatDate(diagnostic.timestamp)}
          </span>
          <Button asChild size="sm" variant="outline">
            <Link to={`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=dossiers`}>
              Voir les aides
              <ChevronRight className="h-4 w-4 ml-1" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
