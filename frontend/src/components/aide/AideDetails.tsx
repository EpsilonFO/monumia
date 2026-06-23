import type { ReactNode } from 'react';
import {
  ExternalLink, Clock, Building2, FileText,
  CheckCircle2, XCircle, HelpCircle, Info,
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
  /** Masquer la carte « Documents requis » (redondante quand une checklist est déjà affichée). */
  showDocumentsRequis?: boolean;
  /** Contenu rendu dans la colonne de droite, juste sous la carte « Informations clés ». */
  aside?: ReactNode;
}

type Evaluation = NonNullable<NonNullable<AideMatchResult['llmEvaluation']>['evaluations']>[number];
type Tone = 'green' | 'red' | 'amber' | 'muted';

function EvalLine({ critere, explication, tone }: { critere: string; explication?: string; tone: Tone }) {
  const Icon = tone === 'green' ? CheckCircle2 : tone === 'red' ? XCircle : tone === 'amber' ? HelpCircle : Info;
  const iconClass = tone === 'green' ? 'text-green-600' : tone === 'red' ? 'text-red-500' : tone === 'amber' ? 'text-amber-500' : 'text-muted-foreground';
  const textClass = tone === 'red' ? 'text-red-700' : tone === 'amber' ? 'text-amber-700' : tone === 'muted' ? 'text-muted-foreground' : '';
  return (
    <div className="space-y-0.5">
      <div className="flex items-start gap-2 text-sm">
        <Icon className={`h-4 w-4 shrink-0 mt-0.5 ${iconClass}`} />
        <span className={textClass}>{critere}</span>
      </div>
      {explication && <p className="pl-6 text-xs text-muted-foreground">{explication}</p>}
    </div>
  );
}

function Section({ title, count, children }: { title: string; count?: number; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}{count != null ? ` (${count})` : ''}
      </p>
      {children}
    </div>
  );
}

/**
 * Analyse d'éligibilité groupée en sections selon la nature des conditions.
 * Si les évaluations ne portent pas de `nature` (ancien chemin LLM), bascule
 * sur un rendu à plat.
 */
function EligibilityAnalysis({ matchResult }: { matchResult: AideMatchResult }) {
  const evals: Evaluation[] = matchResult.llmEvaluation?.evaluations ?? [];
  const eliminatoires = matchResult.criteresNonRemplis ?? [];
  const hasNature = evals.some((e) => !!e.nature);

  // Ancien chemin LLM (pas de nature) : rendu à plat, comme avant.
  if (!hasNature) {
    return (
      <div className="space-y-2">
        {matchResult.criteresRemplis.map((c, i) => <EvalLine key={`ok-${i}`} critere={c} tone="green" />)}
        {eliminatoires.map((c, i) => <EvalLine key={`ko-${i}`} critere={c} tone="red" />)}
        {evals.map((e, i) => {
          const clarified = e.verdict === 'incertitude' && e.clarified;
          const tone: Tone = e.verdict === 'oui' || clarified ? 'green' : e.verdict === 'non' ? 'red' : e.verdict === 'info' ? 'muted' : 'amber';
          return <EvalLine key={`ev-${i}`} critere={e.critere} explication={e.explication} tone={tone} />;
        })}
      </div>
    );
  }

  const isClarified = (e: Evaluation) => e.verdict === 'incertitude' && e.clarified;
  const aVerifier = evals.filter((e) => e.verdict === 'incertitude' && e.nature === 'user_fact' && !e.clarified);
  const financeur = evals.filter((e) => e.nature === 'discretionary' || e.nature === 'manual_check' || (e.nature === 'auto' && e.verdict === 'incertitude'));
  const valides = evals.filter((e) => e.nature === 'user_fact' && (e.verdict === 'oui' || isClarified(e)));
  const autos = evals.filter((e) => e.nature === 'auto' && e.verdict === 'oui');
  const infos = evals.filter((e) => e.nature === 'info' || e.nature === 'modulateur');

  return (
    <>
      {eliminatoires.length > 0 && (
        <Section title="Critères éliminatoires">
          {eliminatoires.map((c, i) => <EvalLine key={i} critere={c} tone="red" />)}
        </Section>
      )}
      {aVerifier.length > 0 && (
        <Section title="À vérifier" count={aVerifier.length}>
          {aVerifier.map((e, i) => <EvalLine key={i} critere={e.critere} tone="amber" />)}
        </Section>
      )}
      {financeur.length > 0 && (
        <Section title="À confirmer auprès du financeur" count={financeur.length}>
          {financeur.map((e, i) => (
            <EvalLine key={i} critere={e.critere} explication={e.explication} tone={e.verdict === 'incertitude' ? 'amber' : 'muted'} />
          ))}
        </Section>
      )}
      {valides.length > 0 && (
        <Section title="Validé par vos réponses" count={valides.length}>
          {valides.map((e, i) => <EvalLine key={i} critere={e.critere} tone="green" />)}
        </Section>
      )}
      {autos.length > 0 && (
        <Section title="Vérifié automatiquement" count={autos.length}>
          {autos.map((e, i) => <EvalLine key={i} critere={e.critere} tone="green" />)}
        </Section>
      )}
      {infos.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Bon à savoir ({infos.length})
          </summary>
          <div className="mt-1.5 space-y-1.5">
            {infos.map((e, i) => <EvalLine key={i} critere={e.critere} tone="muted" />)}
          </div>
        </details>
      )}
    </>
  );
}

export function AideDetails({ aide, matchResult, monumentName, showHeader = true, showDocumentsRequis = true, aside }: AideDetailsProps) {
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
              <CardContent className="space-y-4">
                <EligibilityAnalysis matchResult={matchResult} />
              </CardContent>
            </Card>
          )}

          {showDocumentsRequis && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Documents requis</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {aide.documentsRequis.map((raw, i) => {
                    const doc = typeof raw === 'string' ? { nom: raw } : raw;
                    return (
                      <li key={i} className="flex items-start gap-2">
                        <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
                        <div className="flex flex-col">
                          <span className="flex items-center gap-1.5 flex-wrap">
                            {doc.url ? (
                              <a
                                href={doc.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-primary underline inline-flex items-center gap-1"
                              >
                                {doc.nom}
                                <ExternalLink className="h-3 w-3" />
                              </a>
                            ) : (
                              <span>{doc.nom}</span>
                            )}
                            {doc.obligatoire === false && (
                              <Badge variant="outline" className="text-[10px]">selon le cas</Badge>
                            )}
                          </span>
                          {doc.note && (
                            <span className="text-xs text-muted-foreground">{doc.note}</span>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </CardContent>
            </Card>
          )}
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
          {aside}
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
