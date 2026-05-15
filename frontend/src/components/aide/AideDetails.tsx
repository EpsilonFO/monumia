import {
  ExternalLink, Clock, Building2, FileText,
  CheckCircle2, XCircle, HelpCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { AIDE_CATEGORIES } from '@/constants/aide-categories';
import { formatCurrency, formatPercentage } from '@/lib/format-utils';
import type { Aide, AideMatchResult } from '@/types';

const decodeHtml = (text: string | null | undefined): string => {
  if (!text) return '';
  const el = document.createElement('textarea');
  el.innerHTML = text;
  return el.value;
};

interface AideDetailsProps {
  aide: Aide;
  matchResult?: AideMatchResult | null;
  monumentName?: string;
  showHeader?: boolean;
}

export function AideDetails({ aide, matchResult, monumentName, showHeader = true }: AideDetailsProps) {
  const categoryConfig = AIDE_CATEGORIES.find((c) => c.value === aide.categorie);

  return (
    <div className="space-y-6">
      {showHeader && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge className={categoryConfig?.color ?? ''}>
              {categoryConfig?.label ?? aide.categorie}
            </Badge>
            {matchResult && <EligibilityBadge matchResult={matchResult} />}
          </div>
          <h2 className="text-2xl font-bold">{decodeHtml(aide.nom)}</h2>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed whitespace-pre-line">
                {decodeHtml(aide.descriptionLongue || aide.description)}
              </p>
            </CardContent>
          </Card>

          {matchResult && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Analyse d'éligibilité
                  {monumentName && (
                    <span className="text-muted-foreground font-normal ml-1">
                      pour {monumentName}
                    </span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {matchResult.criteresRemplis.map((c, i) => (
                  <div key={`crit-ok-${i}`} className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                    <span>{c}</span>
                  </div>
                ))}
                {matchResult.criteresNonRemplis.map((c, i) => (
                  <div key={`crit-ko-${i}`} className="flex items-center gap-2 text-sm">
                    <XCircle className="h-4 w-4 text-red-500 shrink-0" />
                    <span className="text-red-700">{c}</span>
                  </div>
                ))}
                {matchResult.llmEvaluation?.evaluations?.map((e, i) => {
                  const isClarified = e.verdict === 'incertitude' && e.clarified;
                  const Icon = e.verdict === 'oui' || isClarified
                    ? CheckCircle2
                    : e.verdict === 'non'
                      ? XCircle
                      : HelpCircle;
                  const iconClass = e.verdict === 'oui' || isClarified
                    ? 'text-green-600'
                    : e.verdict === 'non'
                      ? 'text-red-500'
                      : 'text-amber-500';
                  const textClass = e.verdict === 'non'
                    ? 'text-red-700'
                    : e.verdict === 'incertitude' && !isClarified
                      ? 'text-amber-700'
                      : '';
                  return (
                    <div key={`eval-${i}`} className="space-y-0.5">
                      <div className="flex items-start gap-2 text-sm">
                        <Icon className={`h-4 w-4 shrink-0 mt-0.5 ${iconClass}`} />
                        <span className={textClass}>{e.critere}</span>
                      </div>
                      {e.explication && (
                        <p className="pl-6 text-xs text-muted-foreground">{e.explication}</p>
                      )}
                    </div>
                  );
                })}
                {matchResult.llmEvaluation?.explication && (
                  <p className="pt-2 text-sm text-muted-foreground italic">
                    {matchResult.llmEvaluation.explication}
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Documents requis</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1.5 text-sm">
                {aide.documentsRequis.map((doc, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    {doc}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Informations clés</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div>
                <p className="text-muted-foreground">Organisme</p>
                <p className="font-medium flex items-center gap-1.5">
                  <Building2 className="h-3.5 w-3.5" />
                  {aide.organisme}
                </p>
              </div>

              {aide.tauxMax && (
                <div>
                  <p className="text-muted-foreground">Taux maximum</p>
                  <p className="font-medium text-lg text-primary">
                    {formatPercentage(aide.tauxMax)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Base {aide.baseTTC ? 'TTC' : 'HT'}
                  </p>
                </div>
              )}

              {aide.montantMax && (
                <div>
                  <p className="text-muted-foreground">Montant maximum</p>
                  <p className="font-medium text-lg text-primary">
                    {formatCurrency(aide.montantMax)}
                  </p>
                </div>
              )}

              <Separator />

              <div>
                <p className="text-muted-foreground">Disponibilité</p>
                <p className="font-medium flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  {aide.permanent ? 'Appel permanent' : `Date limite : ${aide.dateLimite ?? 'NC'}`}
                </p>
              </div>

              <div>
                <p className="text-muted-foreground">Délai d'instruction</p>
                <p className="font-medium">{aide.delaiInstruction}</p>
              </div>

              {aide.urlOfficielle && (
                <>
                  <Separator />
                  <Button asChild variant="outline" size="sm" className="w-full">
                    <a href={aide.urlOfficielle} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                      Site officiel
                    </a>
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function EligibilityBadge({ matchResult }: { matchResult: AideMatchResult }) {
  const hasPendingIncertitudes = matchResult.llmEvaluation?.incertitudes?.some(
    (inc) => typeof inc === 'string' || !inc.clarified
  );
  const status = matchResult.eligible && hasPendingIncertitudes
    ? 'potential'
    : matchResult.eligible
      ? 'eligible'
      : 'non-eligible';

  const className =
    status === 'eligible'
      ? 'border-green-300 text-green-700 bg-green-50'
      : status === 'potential'
        ? 'border-amber-300 text-amber-700 bg-amber-50'
        : 'border-red-200 text-red-600 bg-red-50';

  return (
    <Badge variant="outline" className={className}>
      {status === 'eligible' ? (
        <><CheckCircle2 className="h-3 w-3 mr-1" />Éligible</>
      ) : status === 'potential' ? (
        <><HelpCircle className="h-3 w-3 mr-1" />Potentiellement éligible</>
      ) : (
        <><XCircle className="h-3 w-3 mr-1" />Non éligible</>
      )}
    </Badge>
  );
}
