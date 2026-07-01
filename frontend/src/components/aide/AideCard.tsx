import { useLocation, useNavigate } from 'react-router';
import { ChevronRight, ArrowRight } from 'lucide-react';
import {
  IconSucces,
  IconErreur,
  IconHelp,
  IconLienExterne,
  IconTemps,
  IconEcheance,
  IconCalendrier,
  IconVerrou,
  IconSubvention,
  IconTendance,
  IconMonument,
  IconPublic,
  IconDevis,
  IconAccompagnement,
} from '@/components/icons';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AIDE_CATEGORIES } from '@/constants/aide-categories';
import { ROUTES } from '@/constants/routes';
import { formatCurrency, formatPercentage } from '@/lib/format-utils';
import { daysUntil, formatDateShort } from '@/lib/date-utils';
import { C, SERIF } from '@/lib/brand';
import type { AideMatchResult } from '@/types';

interface AideCardProps {
  match: AideMatchResult;
  showEligibility?: boolean;
  locked?: boolean;
  monumentId?: string;
  /**
   * `tile` = vignette compacte (non éligibles) · `grid` = carte « opportunité »
   * verticale (≥ 2 aides) · `hero` = grande carte pleine largeur (1 seule aide).
   */
  layout?: 'tile' | 'grid' | 'hero';
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
  urgent: 'px-3 py-1.5 rounded-lg text-sm font-bold bg-destructive text-destructive-foreground shadow-md shadow-destructive/40',
  past: 'px-3 py-1.5 rounded-lg text-sm font-bold bg-destructive text-destructive-foreground shadow-md shadow-destructive/40 line-through',
  warning: 'px-2.5 py-1 rounded-lg border text-xs font-semibold bg-warning-muted text-warning border-warning',
  normal: 'px-2.5 py-1 rounded-lg border text-xs font-semibold bg-info-muted text-info border-info',
};

// Barre d'accent latérale : repère dans la grille pour les échéances proches.
// Rien pour le lointain (bleu) afin de ne pas surcharger.
const DEADLINE_STRIPE: Record<Urgency, string> = {
  urgent: 'bg-destructive',
  past: 'bg-destructive',
  warning: 'bg-warning',
  normal: 'bg-info',
};

// Pastille ronde par catégorie d'aide — petite touche d'identité reprise de la
// landing (icône dans un cercle teinté).
const CATEGORY_ICON: Record<string, typeof IconMonument> = {
  etat_drac: IconMonument,
  region: IconMonument,
  departement: IconMonument,
  fondation_patrimoine: IconMonument,
  europe: IconPublic,
  mecenat: IconSubvention,
  fiscalite: IconDevis,
  autre: IconAccompagnement,
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

export function AideCard({ match, showEligibility = true, locked = false, monumentId, layout = 'tile' }: AideCardProps) {
  const { aide, criteresRemplis, criteresNonRemplis } = match;
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const categoryConfig = AIDE_CATEGORIES.find((c) => c.value === aide.categorie);
  const status = getEligibilityStatus(match);
  const deadline = !aide.permanent && aide.dateLimite ? deadlineInfo(aide.dateLimite) : null;
  const redAlert = deadline?.urgency === 'urgent' || deadline?.urgency === 'past';
  const DeadlineIcon = redAlert ? IconTemps : IconEcheance;
  const CategoryIcon = CATEGORY_ICON[aide.categorie] ?? IconAccompagnement;
  // Teinte de la pastille ronde selon le statut (vert éligible · orange à confirmer).
  const statusTone =
    status === 'eligible'
      ? { tint: 'var(--success-muted)', accent: 'var(--success)' }
      : status === 'potential'
        ? { tint: 'var(--warning-muted)', accent: 'var(--warning)' }
        : { tint: 'var(--destructive-muted)', accent: 'var(--destructive)' };
  const aideDetailUrl = monumentId
    ? ROUTES.PROJET_AIDE(monumentId, aide.id)
    : ROUTES.PROJETS;

  const hoverClass = locked
    ? 'hover:border-warning'
    : status === 'eligible'
      ? 'hover:border-success'
      : status === 'potential'
        ? 'hover:border-warning'
        : 'hover:border-border';

  const handleCardClick = () => {
    if (locked) {
      navigate('/tarifs', { state: { from: pathname } });
    } else {
      navigate(aideDetailUrl);
    }
  };

  // Animation volontairement minimale : une simple ombre au survol, rien de plus.
  const cardBase = `group relative overflow-hidden cursor-pointer transition duration-200 hover:shadow-md ${hoverClass} ${redAlert ? 'ring-2 ring-destructive/70' : ''} ${locked ? 'bg-muted/50' : ''}`;

  // Pièces partagées entre la vignette (`tile`) et la ligne (`row`) — même contenu,
  // agencement différent.
  const stripe = deadline && DEADLINE_STRIPE[deadline.urgency] ? (
    <div
      className={`absolute inset-y-0 left-0 ${redAlert ? 'w-1.5' : 'w-1'} ${DEADLINE_STRIPE[deadline.urgency]}`}
      aria-hidden
    />
  ) : null;

  const badges = (
    <div className="flex items-center gap-2 flex-wrap">
      <Badge className={categoryConfig?.color ?? 'bg-muted text-muted-foreground'}>
        {categoryConfig?.label ?? aide.categorie}
      </Badge>
      {showEligibility && (
        <Badge
          variant="outline"
          className={
            status === 'eligible'
              ? 'border-success text-success bg-success-muted'
              : status === 'potential'
                ? 'border-warning text-warning bg-warning-muted'
                : 'border-destructive text-destructive bg-destructive-muted'
          }
        >
          {status === 'eligible' ? (
            <>
              <IconSucces className="h-3 w-3 mr-1" />
              Éligible
            </>
          ) : status === 'potential' ? (
            <>
              <IconHelp className="h-3 w-3 mr-1" />
              Potentiellement éligible
            </>
          ) : (
            <>
              <IconErreur className="h-3 w-3 mr-1" />
              Non éligible
            </>
          )}
        </Badge>
      )}
      {locked && (
        <Badge variant="outline" className="border-warning text-warning bg-warning-muted gap-1">
          <IconVerrou className="h-2.5 w-2.5" />
          Accès premium
        </Badge>
      )}
    </div>
  );

  const title = (
    <CardTitle className="text-base leading-tight">
      <span className={locked ? 'blur-sm select-none pointer-events-none' : undefined}>
        {aide.nomCourt}
      </span>
    </CardTitle>
  );

  const description = (
    <p className={`text-sm text-muted-foreground line-clamp-2 ${locked ? 'blur-sm select-none pointer-events-none' : ''}`}>
      {aide.description}
    </p>
  );

  const deadlinePill = deadline ? (
    <span className={`inline-flex items-center gap-1.5 ${DEADLINE_PILL[deadline.urgency]}`}>
      <DeadlineIcon className={redAlert ? 'h-4 w-4' : 'h-3.5 w-3.5'} />
      {deadline.text}
    </span>
  ) : null;

  const criteria = showEligibility ? (
    <div className="space-y-1">
      {criteresRemplis.slice(0, 3).map((c, i) => (
        <div key={i} className="flex items-center gap-1.5 text-xs text-success">
          <IconSucces className="h-3 w-3 shrink-0" />
          <span>{c}</span>
        </div>
      ))}
      {criteresNonRemplis.slice(0, 2).map((c, i) => (
        <div key={i} className="flex items-center gap-1.5 text-xs text-destructive">
          <IconErreur className="h-3 w-3 shrink-0" />
          <span>{c}</span>
        </div>
      ))}
      {status === 'potential' && match.llmEvaluation?.incertitudes.slice(0, 2).map((c, i) => {
        const isClarified = typeof c !== 'string' && c.clarified;
        return (
          <div key={i} className={`flex items-center gap-1.5 text-xs ${isClarified ? 'text-success' : 'text-warning'}`}>
            {isClarified ? <IconSucces className="h-3 w-3 shrink-0" /> : <IconHelp className="h-3 w-3 shrink-0" />}
            <span>{typeof c === 'string' ? c : c.detail}</span>
          </div>
        );
      })}
    </div>
  ) : null;

  const officialLink = !locked && aide.urlOfficielle ? (
    <Button asChild size="sm" variant="ghost" onClick={(e) => e.stopPropagation()}>
      <a href={aide.urlOfficielle} target="_blank" rel="noopener noreferrer">
        <IconLienExterne className="h-3 w-3 mr-1" />
        Site officiel
      </a>
    </Button>
  ) : null;

  // Statut clair façon SaaS grand public : pastille à pré-point coloré.
  // « À confirmer » plutôt que « Potentiellement éligible » — plus simple à lire.
  const statusPill = showEligibility ? (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold" style={{ background: statusTone.tint, color: statusTone.accent }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: statusTone.accent }} />
      {status === 'eligible' ? 'Éligible' : status === 'potential' ? 'À confirmer' : 'Non éligible'}
    </span>
  ) : null;

  // Récap rassurant en une ligne — le détail complet est sur la fiche de l'aide.
  const criteriaSummary = criteresRemplis.length > 0 ? (
    <span className="inline-flex items-center gap-1.5 text-[12.5px] font-medium" style={{ color: 'var(--success)' }}>
      <IconSucces className="h-3.5 w-3.5 shrink-0" />
      {criteresRemplis.length} critère{criteresRemplis.length > 1 ? 's' : ''} rempli{criteresRemplis.length > 1 ? 's' : ''}
    </span>
  ) : null;

  // Informations clés en lignes « icône + libellé + valeur » — lisibles d'un
  // coup d'œil, sans capsules ni traits de séparation.
  const dRed = deadline?.urgency === 'urgent' || deadline?.urgency === 'past';
  const dTone = !deadline
    ? { bg: C.paleBlue, fg: C.blue }
    : dRed
      ? { bg: C.paleDanger, fg: C.danger }
      : deadline.urgency === 'warning'
        ? { bg: C.paleOrange, fg: C.orange }
        : { bg: C.paleBlue, fg: C.blue };
  const facts: { icon: typeof IconSubvention; accent: string; label: string; value: string; valueColor?: string }[] = [];
  if (aide.montantMax != null) facts.push({ icon: IconSubvention, accent: C.orange, label: 'Montant max', value: formatCurrency(aide.montantMax) });
  if (aide.tauxMax != null) facts.push({ icon: IconTendance, accent: C.blue, label: 'des travaux', value: `${aide.tauxMax} %` });
  facts.push({
    icon: deadline ? DeadlineIcon : IconCalendrier,
    accent: dTone.fg,
    label: 'Échéance',
    value: deadline ? deadline.text : aide.permanent ? "Toute l'année" : 'Sur demande',
    valueColor: deadline ? dTone.fg : undefined,
  });

  // Bouton principal clair — signal d'action fort, en bleu charte.
  const detailButton = (fullWidth: boolean) => (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); handleCardClick(); }}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-[13.5px] font-semibold text-white transition-shadow duration-200 hover:shadow-md ${fullWidth ? 'w-full' : ''}`}
      style={{ background: C.blue }}
    >
      Voir l'aide
      <ArrowRight className="h-4 w-4" />
    </button>
  );

  // Montants en ligne — vignette uniquement (la ligne `row` utilise le panneau « gain »).
  const amountsInline = (
    <div className="flex items-center gap-3 flex-wrap text-sm">
      {aide.tauxMax && (
        <span className="font-medium text-primary">Jusqu'à {formatPercentage(aide.tauxMax)}</span>
      )}
      {aide.montantMax && (
        <span className="font-medium text-primary">Max {formatCurrency(aide.montantMax)}</span>
      )}
      {aide.permanent && (
        <span className="text-muted-foreground flex items-center gap-1">
          <IconTemps className="h-3 w-3" />
          Permanent
        </span>
      )}
    </div>
  );

  // HERO — une seule aide : bandeau pleine largeur qui occupe l'espace. Identité +
  // description à gauche, panneau d'infos bleu pâle + bouton à droite. Bleu en
  // accents, sans gros bloc ni trait de séparation.
  if (layout === 'hero') {
    return (
      <Card className={`${cardBase} gap-0 py-0`} onClick={handleCardClick}>
        <div className="flex flex-col gap-6 p-6 sm:p-7 lg:flex-row lg:gap-8">
          <div className="min-w-0 flex-1 space-y-3">
            <div className="flex items-start gap-3">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl" style={{ background: C.paleBlue }}>
                <CategoryIcon className="h-6 w-6" style={{ color: C.blue }} strokeWidth={1.7} />
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-[20px] leading-snug" style={{ fontFamily: SERIF, color: C.blue }}>
                    <span className={locked ? 'blur-sm select-none pointer-events-none' : undefined}>{aide.nomCourt}</span>
                  </h3>
                  {statusPill}
                </div>
                <p className="mt-0.5 text-[12.5px] text-muted-foreground">{categoryConfig?.label ?? aide.categorie}</p>
              </div>
            </div>
            {description}
            {criteriaSummary}
          </div>
          <div className="flex shrink-0 flex-col gap-4 lg:w-72">
            <div className="space-y-3 rounded-xl p-4" style={{ background: C.paleBlue }}>
              {facts.map((f, i) => {
                const Icon = f.icon;
                return (
                  <div key={i} className="flex items-center gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white">
                      <Icon className="h-[18px] w-[18px]" style={{ color: f.accent }} strokeWidth={1.8} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-[15px] font-bold leading-tight" style={{ color: f.valueColor ?? C.ink }}>{f.value}</p>
                      <p className="text-[11px] text-muted-foreground">{f.label}</p>
                    </div>
                  </div>
                );
              })}
            </div>
            {detailButton(true)}
          </div>
        </div>
      </Card>
    );
  }

  // GRID — deux aides ou plus : carte compacte verticale, le bandeau d'infos pâle
  // remplit le bas. Colonnes du bandeau ajustées au nombre d'infos (jamais de vide).
  if (layout === 'grid') {
    return (
      <Card className={`${cardBase} h-full gap-0 py-0`} onClick={handleCardClick}>
        <div className="flex h-full flex-col gap-4 p-5">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl" style={{ background: C.paleBlue }}>
              <CategoryIcon className="h-[22px] w-[22px]" style={{ color: C.blue }} strokeWidth={1.7} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-[17px] leading-snug" style={{ fontFamily: SERIF, color: C.blue }}>
                  <span className={locked ? 'blur-sm select-none pointer-events-none' : undefined}>{aide.nomCourt}</span>
                </h3>
                {statusPill}
              </div>
              <p className="mt-0.5 text-[12px] text-muted-foreground">{categoryConfig?.label ?? aide.categorie}</p>
            </div>
          </div>

          {description}

          <div
            className="grid gap-3 rounded-xl px-3 py-3"
            style={{ background: C.paleBlue, gridTemplateColumns: `repeat(${facts.length}, minmax(0, 1fr))` }}
          >
            {facts.map((f, i) => {
              const Icon = f.icon;
              return (
                <div key={i} className="flex min-w-0 flex-col items-center gap-1 text-center">
                  <Icon className="h-5 w-5" style={{ color: f.accent }} strokeWidth={1.8} />
                  <span className="text-[14px] font-bold leading-tight" style={{ color: f.valueColor ?? C.ink }}>{f.value}</span>
                  <span className="text-[10.5px] leading-tight text-muted-foreground">{f.label}</span>
                </div>
              );
            })}
          </div>

          <div className="mt-auto flex items-center justify-between gap-3 pt-1">
            <div>{criteriaSummary}</div>
            {detailButton(false)}
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className={cardBase} onClick={handleCardClick}>
      {stripe}
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1.5 flex-1 min-w-0">
            {badges}
            {title}
          </div>
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {description}
        {deadlinePill}
        {amountsInline}
        {criteria}
        {officialLink && <div className="pt-1">{officialLink}</div>}
      </CardContent>
    </Card>
  );
}
