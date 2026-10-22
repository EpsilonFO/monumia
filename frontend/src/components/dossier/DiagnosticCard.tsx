import { Link } from 'react-router';
import { Trans, useTranslation } from 'react-i18next';
import { ChevronRight } from 'lucide-react';
import { IconDiagnostic, IconCalendrier } from '@/components/icons';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ROUTES } from '@/constants/routes';
import { formatDate } from '@/lib/date-utils';
import { localeIntl } from '@/i18n/format';
import type { AideDiagnosticResult, Monument } from '@/types';

interface DiagnosticCardProps {
  diagnostic: AideDiagnosticResult;
  monument: Monument;
}

export function DiagnosticCard({ diagnostic, monument }: DiagnosticCardProps) {
  const { t } = useTranslation('dossier');
  const nbEligibles = diagnostic.aidesPotentiellementEligibles.length;
  const nbTotal = diagnostic.totalAidesAnalysees;

  return (
    <Card className="hover:shadow-md hover:border-primary/30 transition-all group">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm leading-tight">{monument.nom}</CardTitle>
          <Badge variant="outline" className="bg-success-muted text-success border-success/30 shrink-0">
            <IconDiagnostic className="h-3 w-3 mr-1" />
            {t('DiagnosticCard.fait')}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-sm space-y-1">
          <p>
            <Trans
              t={t}
              i18nKey="DiagnosticCard.eligibles"
              count={nbEligibles}
              values={{ analysees: t('DiagnosticCard.analysees', { count: nbTotal }) }}
              components={{
                nb: <span className="font-semibold text-primary" />,
                gris: <span className="text-muted-foreground" />,
              }}
            />
          </p>
          {diagnostic.montantPotentielTotal != null && diagnostic.montantPotentielTotal > 0 && (
            <p className="text-muted-foreground">
              <Trans
                t={t}
                i18nKey="DiagnosticCard.montant"
                values={{
                  montant: new Intl.NumberFormat(localeIntl(), { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(diagnostic.montantPotentielTotal),
                }}
                components={{ valeur: <span className="font-medium text-foreground" /> }}
              />
            </p>
          )}
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <IconCalendrier className="h-3 w-3" />
            {formatDate(diagnostic.timestamp)}
          </span>
          <Button asChild size="sm" variant="outline">
            <Link to={`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=projets`}>
              {t('DiagnosticCard.voirAides')}
              <ChevronRight className="h-4 w-4 ml-1" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
