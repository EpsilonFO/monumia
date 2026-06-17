import { useLocation, useNavigate } from 'react-router';
import { CheckCircle2, XCircle, HelpCircle, ExternalLink, Clock, CalendarClock, AlarmClock, ChevronRight, Lock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AIDE_CATEGORIES } from '@/constants/aide-categories';
import { ROUTES } from '@/constants/routes';
import { formatCurrency, formatPercentage } from '@/lib/format-utils';
import { daysUntil, formatDateShort } from '@/lib/date-utils';
import type { AideMatchResult } from '@/types';

interface AideCardProps {
  match: AideMatchResult;
  showEligibility?: boolean;
  locked?: boolean;
  monumentId?: string;
}

type Urgency = 'urgent' | 'warning' | 'normal' | 'past';

// Seuils adaptés au patrimoine (instruction des dossiers longue) :
// dépassée / < 30 j → rouge · 30–100 j → orange · > 100 j → bleu.
function deadlineInfo(date: string): { urgency: Urgency; text: string } {
  const days = daysUntil(date);
  if (days < 0) return { urgency: 'past', text: 'Échéance dépassée' };
  if (days === 0) return { urgency: 'urgent', text: "Dernier jour" };
  if (days === 1) return { urgency: 'urgent', text: 'Demain' };
  if (days < 30) return { urgency: 'urgent', text: `Dans ${days} jours` };
  if (days <= 100) return { urgency: 'warning', text: `Avant le ${formatDateShort(date)}` };
  return { urgency: 'normal', text: `Avant le ${formatDateShort(date)}` };
}

// Pastille : l'intensité visuelle suit l'urgence.
// Rouge proche/dépassé → pleine + halo (attire l'œil) ; orange → légère ; bleu lointain → calme.
const DEADLINE_PILL: Record<Urgency, string> = {
  urgent: 'px-3 py-1.5 rounded-lg text-sm font-bold bg-red-600 text-white shadow-md shadow-red-500/40',
  past: 'px-3 py-1.5 rounded-lg text-sm font-bold bg-red-600 text-white shadow-md shadow-red-500/40 line-through',
  warning: 'px-2.5 py-1 rounded-lg border text-xs font-semibold bg-orange-50 text-orange-700 border-orange-300',
  normal: 'px-2.5 py-1 rounded-lg border text-xs font-semibold bg-blue-50 text-blue-700 border-blue-200',
};

// Barre d'accent latérale : repère dans la grille pour les échéances proches.
// Rien pour le lointain (bleu) afin de ne pas surcharger.
const DEADLINE_STRIPE: Record<Urgency, string> = {
  urgent: 'bg-red-500',
  past: 'bg-red-500',
  warning: 'bg-orange-400',
  normal: 'bg-blue-300',
};

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
  const deadline = !aide.permanent && aide.dateLimite ? deadlineInfo(aide.dateLimite) : null;
  const redAlert = deadline?.urgency === 'urgent' || deadline?.urgency === 'past';
  const DeadlineIcon = redAlert ? AlarmClock : CalendarClock;
  const aideDetailUrl = monumentId
    ? ROUTES.PROJET_AIDE(monumentId, aide.id)
    : ROUTES.PROJETS;

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
      className={`group relative overflow-hidden cursor-pointer transition-all duration-200 hover:shadow-lg hover:shadow-black/[0.06] hover:-translate-y-0.5 ${hoverClass} ${redAlert ? 'ring-2 ring-red-400/70' : ''} ${locked ? 'bg-gray-50/50' : ''}`}
      onClick={handleCardClick}
    >
      {deadline && DEADLINE_STRIPE[deadline.urgency] && (
        <div
          className={`absolute inset-y-0 left-0 ${redAlert ? 'w-1.5' : 'w-1'} ${DEADLINE_STRIPE[deadline.urgency]}`}
          aria-hidden
        />
      )}
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
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:text-[#f17105]" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className={`text-sm text-muted-foreground line-clamp-2 ${locked ? 'blur-sm select-none pointer-events-none' : ''}`}>
          {aide.description}
        </p>

        {/* Deadline */}
        {deadline && (
          <span className={`inline-flex items-center gap-1.5 ${DEADLINE_PILL[deadline.urgency]}`}>
            <DeadlineIcon className={redAlert ? 'h-4 w-4' : 'h-3.5 w-3.5'} />
            {deadline.text}
          </span>
        )}

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
          {aide.permanent && (
            <span className="text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Permanent
            </span>
          )}
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
