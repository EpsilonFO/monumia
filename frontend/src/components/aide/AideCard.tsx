import { Link } from 'react-router';
import { CheckCircle2, XCircle, ExternalLink, Clock, ChevronRight } from 'lucide-react';
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
}

export function AideCard({ match, showEligibility = true }: AideCardProps) {
  const { aide, eligible, criteresRemplis, criteresNonRemplis } = match;
  const categoryConfig = AIDE_CATEGORIES.find((c) => c.value === aide.categorie);

  return (
    <Card className={`transition-all hover:shadow-md ${eligible ? 'hover:border-green-300' : 'hover:border-border'}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge className={categoryConfig?.color ?? 'bg-gray-100 text-gray-800'}>
                {categoryConfig?.label ?? aide.categorie}
              </Badge>
              {showEligibility && (
                <Badge
                  variant="outline"
                  className={eligible
                    ? 'border-green-300 text-green-700 bg-green-50'
                    : 'border-red-200 text-red-600 bg-red-50'
                  }
                >
                  {eligible ? (
                    <>
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      Éligible
                    </>
                  ) : (
                    <>
                      <XCircle className="h-3 w-3 mr-1" />
                      Non éligible
                    </>
                  )}
                </Badge>
              )}
            </div>
            <CardTitle className="text-base leading-tight">
              {aide.nomCourt}
            </CardTitle>
          </div>
          <Link to={ROUTES.AIDE_DETAIL(aide.id)}>
            <ChevronRight className="h-4 w-4 text-muted-foreground hover:text-primary" />
          </Link>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground line-clamp-2">
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
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2 pt-1">
          <Button asChild size="sm" variant={eligible ? 'default' : 'outline'}>
            <Link to={ROUTES.AIDE_DETAIL(aide.id)}>
              Voir le détail
            </Link>
          </Button>
          {aide.urlOfficielle && (
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
