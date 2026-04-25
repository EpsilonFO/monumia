import { useLocation, useNavigate } from 'react-router';
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
  monumentId?: string;
}

function getEligibilityStatus(match: AideMatchResult) {
  // Only unresolved incertitudes (not yet clarified by QCM) count as "potential" status
  const hasPendingIncertitudes = match.llmEvaluation?.incertitudes?.some(
    (inc) => typeof inc === 'string' || !inc.clarified
  );
  if (match.eligible && hasPendingIncertitudes) return 'potential';
  if (match.eligible) return 'eligible';
  return 'non-eligible';
}

export function AideCard({ match, showEligibility = true, locked = false, monumentId }: AideCardProps) {
  const { aide, criteresRemplis, criteresNonRemplis } = match;
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const categoryConfig = AIDE_CATEGORIES.find((c) => c.value === aide.categorie);
  const status = getEligibilityStatus(match);
  const aideDetailUrl = ROUTES.AIDE_DETAIL(aide.id, monumentId);

  const hoverClass = locked
    ? 'hover:border-amber-300'
    : status === 'eligible'
      ? 'hover:border-green-400'
      : status === 'potential'
        ? 'hover:border-amber-400'
        : 'hover:border-[#C0BDBA]';

  const handleCardClick = () => {
    if (locked) {
      navigate('/tarifs', { state: { from: pathname } });
    } else {
      navigate(aideDetailUrl);
    }
  };

  return (
    <Card
      className={`group cursor-pointer transition-all duration-200 hover:shadow-lg hover:shadow-black/[0.06] hover:-translate-y-0.5 ${hoverClass} ${locked ? 'bg-gray-50/50' : ''}`}
      onClick={handleCardClick}
    >
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
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:text-[#C75B3A]" />
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
            {status === 'potential' && match.llmEvaluation?.incertitudes.slice(0, 2).map((c, i) => {
              const isClarified = typeof c !== 'string' && c.clarified;
              return (
                <div key={i} className={`flex items-center gap-1.5 text-xs ${isClarified ? 'text-green-700' : 'text-amber-700'}`}>
                  {isClarified ? <CheckCircle2 className="h-3 w-3 shrink-0" /> : <HelpCircle className="h-3 w-3 shrink-0" />}
                  <span>{typeof c === 'string' ? c : c.detail}</span>
                </div>
              );
            })}
          </div>
        )}

        {/* Actions */}
        {!locked && aide.urlOfficielle && (
          <div className="pt-1">
            <Button
              asChild
              size="sm"
              variant="ghost"
              onClick={(e) => e.stopPropagation()}
            >
              <a href={aide.urlOfficielle} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-3 w-3 mr-1" />
                Site officiel
              </a>
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
