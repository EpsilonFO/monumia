const decodeHtml = (text: string | null | undefined): string => {
  if (!text) return '';
  const el = document.createElement('textarea');
  el.innerHTML = text;
  return el.value;
};
import { Link, useLocation } from 'react-router';
import { CheckCircle2, XCircle, HelpCircle, ExternalLink, Clock, ChevronRight, Lock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AIDE_CATEGORIES } from '@/constants/aide-categories';
import { ROUTES } from '@/constants/routes';
import { formatCurrency, formatPercentage } from '@/lib/format-utils';
import type { AideMatchResult } from '@/types';

interface AideCardProps {
  match: AideMatchResult;
  showEligibility?: boolean;
  locked?: boolean;
}

function getEligibilityStatus(match: AideMatchResult) {
  const hasIncertitudes = match.llmEvaluation?.incertitudes && match.llmEvaluation.incertitudes.length > 0;
  if (match.eligible && hasIncertitudes) return 'potential';
  if (match.eligible) return 'eligible';
  return 'non-eligible';
}

export function AideCard({ match, showEligibility = true, locked = false }: AideCardProps) {
  const { aide, criteresRemplis, criteresNonRemplis } = match;
  const { pathname } = useLocation();
  const categoryConfig = AIDE_CATEGORIES.find((c) => c.value === aide.categorie);
  const status = getEligibilityStatus(match);

  const hoverClass = locked
    ? 'hover:border-amber-200'
    : status === 'eligible'
      ? 'hover:border-green-300'
      : status === 'potential'
        ? 'hover:border-amber-300'
        : 'hover:border-border';

  const tarifsTo = { pathname: '/tarifs' };
  const tarifsState = { from: pathname };

  return (
    <Card className={`transition-all hover:shadow-md ${hoverClass} ${locked ? 'bg-gray-50/50' : ''}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1.5 flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge className={categoryConfig?.color ?? 'bg-gray-100 text-gray-800'}>
                {categoryConfig?.label ?? aide.categorie}
              </Badge>
              {showEligibility && (
                <Badge
                  variant="outline"
                  className={
                    status === 'eligible'
                      ? 'border-green-300 text-green-700 bg-green-50'
                      : status === 'potential'
                        ? 'border-amber-300 text-amber-700 bg-amber-50'
                        : 'border-red-200 text-red-600 bg-red-50'
                  }
                >
                  {status === 'eligible' ? (
                    <>
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      Éligible
                    </>
                  ) : status === 'potential' ? (
                    <>
                      <HelpCircle className="h-3 w-3 mr-1" />
                      Potentiellement éligible
                    </>
                  ) : (
                    <>
                      <XCircle className="h-3 w-3 mr-1" />
                      Non éligible
                    </>
                  )}
                </Badge>
              )}
              {locked && (
                <Badge variant="outline" className="border-amber-300 text-amber-700 bg-amber-50 gap-1">
                  <Lock className="h-2.5 w-2.5" />
                  Accès premium
                </Badge>
              )}
            </div>
            <CardTitle className="text-base leading-tight">
              <span className={locked ? 'blur-sm select-none pointer-events-none' : undefined}>
                {aide.nomCourt}
              </span>
            </CardTitle>
          </div>
          <Link to={locked ? tarifsTo : ROUTES.AIDE_DETAIL(aide.id)} state={locked ? tarifsState : undefined}>
            <ChevronRight className="h-4 w-4 text-muted-foreground hover:text-primary" />
          </Link>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className={`text-sm text-muted-foreground line-clamp-2 ${locked ? 'blur-sm select-none pointer-events-none' : ''}`}>
          {aide.description}
        </p>

        {/* Amounts */}
        <div className="flex items-center gap-3 flex-wrap text-sm">
          {aide.tauxMax && (
            <span className="font-medium text-primary">
              Jusqu'à {formatPercentage(aide.tauxMax)}
            </span>
          )}
          {aide.montantMax && (
            <span className="font-medium text-primary">
              Max {formatCurrency(aide.montantMax)}
            </span>
          )}
          {aide.permanent ? (
            <span className="text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Permanent
            </span>
          ) : aide.dateLimite ? (
            <span className="text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Limite : {aide.dateLimite}
            </span>
          ) : null}
        </div>

        {/* Eligibility breakdown */}
        {showEligibility && (
          <div className="space-y-1">
            {criteresRemplis.slice(0, 3).map((c, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-green-700">
                <CheckCircle2 className="h-3 w-3 shrink-0" />
                <span>{c}</span>
              </div>
            ))}
            {criteresNonRemplis.slice(0, 2).map((c, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-red-600">
                <XCircle className="h-3 w-3 shrink-0" />
                <span>{c}</span>
              </div>
            ))}
            {status === 'potential' && match.llmEvaluation?.incertitudes.slice(0, 2).map((c, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-amber-700">
                <HelpCircle className="h-3 w-3 shrink-0" />
                <span>{typeof c === 'string' ? c : c.detail}</span>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2 pt-1">
          <Button asChild size="sm" variant={locked ? 'outline' : status === 'eligible' ? 'default' : 'outline'}>
            <Link to={locked ? tarifsTo : ROUTES.AIDE_DETAIL(aide.id)} state={locked ? tarifsState : undefined}>
              {locked ? 'Découvrir les aides' : 'Voir le détail'}
            </Link>
          </Button>
          {!locked && aide.urlOfficielle && (
            <Button asChild size="sm" variant="ghost">
              <a href={aide.urlOfficielle} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-3 w-3 mr-1" />
                Site officiel
              </a>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
