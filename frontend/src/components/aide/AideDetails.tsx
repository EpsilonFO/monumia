import { useState } from 'react';
import type { ComponentType, ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import {
  IconLienExterne,
  IconTemps,
  IconInstitution,
  IconDocument,
  IconSubvention,
  IconSucces,
  IconErreur,
  IconHelp,
  IconInfo,
  IconEtapes,
  IconDiagnostic,
  IconEcheance,
  IconRegle,
  IconParchemin,
  IconContact,
} from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { AIDE_CATEGORIES, AIDE_TYPES } from '@/constants/aide-categories';
import { formatCurrency } from '@/lib/format-utils';
import { deadlineLabel } from '@/lib/date-utils';
import { C, SERIF, DEADLINE_TONE } from '@/lib/brand';
import type { Aide, AideDocument, AideMatchResult } from '@/types';

export const decodeHtml = (text: string | null | undefined): string => {
  if (!text) return '';
  const el = document.createElement('textarea');
  el.innerHTML = text;
  return el.value;
};

export type EligibilityStatus = 'eligible' | 'potential' | 'non-eligible';

/** Statut d'éligibilité affichable, partagé entre le bandeau et le badge. */
export function getEligibilityStatus(matchResult: AideMatchResult): EligibilityStatus {
  const hasPendingIncertitudes = matchResult.llmEvaluation?.incertitudes?.some(
    (inc) => typeof inc === 'string' || !inc.clarified,
  );
  return matchResult.eligible && hasPendingIncertitudes
    ? 'potential'
    : matchResult.eligible
      ? 'eligible'
      : 'non-eligible';
}

interface AideDetailsProps {
  aide: Aide;
  matchResult?: AideMatchResult | null;
  monumentName?: string;
  showHeader?: boolean;
  /** Masquer la carte « Documents requis » (redondante quand une checklist est déjà affichée). */
  showDocumentsRequis?: boolean;
  /** Contenu rendu dans la colonne de droite, sous la fiche « L'essentiel ». */
  aside?: ReactNode;
}

type IconType = ComponentType<{ className?: string; strokeWidth?: number; style?: React.CSSProperties }>;

/* ------------------------------------------------------------------ */
/* Carte de section (colonne de lecture)                               */
/* ------------------------------------------------------------------ */

function SectionCard({ icon: Icon, title, tint = 'plain', children }: {
  icon: IconType;
  title: ReactNode;
  /** `success` = cadre vert signature du diagnostic. Le contenu coloré (pastilles,
   *  critères orange/rouge) doit alors vivre sur des surfaces blanches internes,
   *  jamais à même le vert (clash de teintes). */
  tint?: 'plain' | 'success';
  children: ReactNode;
}) {
  const success = tint === 'success';
  return (
    <section
      className="rounded-2xl border p-5 sm:p-6"
      style={{
        background: success ? 'var(--success-muted)' : C.card,
        borderColor: success ? 'rgba(15,122,82,0.22)' : C.border,
        boxShadow: 'var(--shadow-card)',
      }}
    >
      <h3 className="mb-3.5 flex items-center gap-2.5 text-[17px]" style={{ fontFamily: SERIF, color: C.ink }}>
        <span
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
          style={success
            ? { background: 'var(--success)', color: 'var(--success-foreground)' }
            : { background: 'var(--secondary)', color: 'var(--primary)' }}
        >
          <Icon className="h-[16px] w-[16px]" strokeWidth={2} />
        </span>
        {title}
      </h3>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* « En bref » — accroche serif + suite repliable                      */
/* ------------------------------------------------------------------ */

function EnBref({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const cut = text.indexOf('. ');
  const lead = cut > 0 && cut < 220 ? text.slice(0, cut + 1) : '';
  const body = lead ? text.slice(cut + 1).trim() : text;
  const longBody = body.length > 240;

  return (
    <div className="space-y-2.5">
      {lead && <p className="text-[18px] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>{lead}</p>}
      {body && (
        <>
          <p
            className={`text-[14.5px] leading-relaxed whitespace-pre-line text-muted-foreground ${!open && longBody ? 'line-clamp-3' : ''}`}
          >
            {body}
          </p>
          {longBody && (
            <button
              onClick={() => setOpen((o) => !o)}
              className="text-[13px] font-semibold text-primary hover:underline"
            >
              {open ? 'Réduire' : 'Lire la suite'}
            </button>
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Éligibilité : pastilles de comptage + détail groupé                 */
/* ------------------------------------------------------------------ */

type Evaluation = NonNullable<NonNullable<AideMatchResult['llmEvaluation']>['evaluations']>[number];
type EvalTone = 'green' | 'red' | 'amber' | 'muted';

function CountPill({ icon: Icon, tone, children }: { icon: IconType; tone: 'success' | 'warning' | 'destructive'; children: ReactNode }) {
  const map = {
    success: 'bg-success-muted text-success',
    warning: 'bg-warning-muted text-warning',
    destructive: 'bg-destructive-muted text-destructive',
  } as const;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-semibold ${map[tone]}`}>
      <Icon className="h-3.5 w-3.5" strokeWidth={2} />
      {children}
    </span>
  );
}

function EligibilitySummary({ matchResult }: { matchResult: AideMatchResult }) {
  const evals = matchResult.llmEvaluation?.evaluations ?? [];
  const validated = matchResult.criteresRemplis.length
    + evals.filter((e) => e.verdict === 'oui' || (e.verdict === 'incertitude' && e.clarified)).length;
  const toVerify = evals.filter((e) => e.verdict === 'incertitude' && !e.clarified).length;
  const blocking = (matchResult.criteresNonRemplis?.length ?? 0) + evals.filter((e) => e.verdict === 'non').length;
  if (validated + toVerify + blocking === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {validated > 0 && <CountPill icon={IconSucces} tone="success">{validated} remplie{validated > 1 ? 's' : ''}</CountPill>}
      {toVerify > 0 && <CountPill icon={IconHelp} tone="warning">{toVerify} à vérifier</CountPill>}
      {blocking > 0 && <CountPill icon={IconErreur} tone="destructive">{blocking} bloquante{blocking > 1 ? 's' : ''}</CountPill>}
    </div>
  );
}

function EvalLine({ critere, explication, tone }: { critere: string; explication?: string; tone: EvalTone }) {
  const Icon = tone === 'green' ? IconSucces : tone === 'red' ? IconErreur : tone === 'amber' ? IconHelp : IconInfo;
  const iconClass = tone === 'green' ? 'text-success' : tone === 'red' ? 'text-destructive' : tone === 'amber' ? 'text-warning' : 'text-muted-foreground';
  const textClass = tone === 'red' ? 'text-destructive' : tone === 'muted' ? 'text-muted-foreground' : '';
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

const GROUP_TONES: Record<EvalTone, { bg: string; fg: string }> = {
  green: { bg: 'var(--success-muted)', fg: 'var(--success)' },
  amber: { bg: 'var(--warning-muted)', fg: 'var(--warning)' },
  red:   { bg: 'var(--destructive-muted)', fg: 'var(--destructive)' },
  muted: { bg: 'var(--muted)', fg: 'var(--muted-foreground)' },
};

/**
 * Groupe de critères repliable : une rangée blanche qui annonce l'essentiel
 * (nature du groupe + compte) et ne déplie le détail qu'à la demande. Les
 * groupes qui demandent une action au propriétaire s'ouvrent d'eux-mêmes ;
 * le fond blanc garantit la lisibilité des tons orange/rouge dans le cadre vert.
 */
function EvalGroup({ icon: Icon, tone, title, count, defaultOpen = false, children }: {
  icon: IconType;
  tone: EvalTone;
  title: string;
  count: number;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const t = GROUP_TONES[tone];
  return (
    <Collapsible defaultOpen={defaultOpen} className="rounded-xl border bg-card" style={{ borderColor: C.border }}>
      <CollapsibleTrigger className="group flex w-full items-center gap-3 px-4 py-3 text-left">
        <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg" style={{ background: t.bg, color: t.fg }}>
          <Icon className="h-4 w-4" strokeWidth={2} />
        </span>
        <span className="flex-1 text-[14px] font-semibold leading-snug" style={{ color: C.ink }}>{title}</span>
        <span className="rounded-full px-2.5 py-0.5 text-[12px] font-bold tabular-nums" style={{ background: t.bg, color: t.fg }}>
          {count}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="space-y-2 pb-3.5 pl-14 pr-4">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  );
}

/**
 * Détail de l'analyse, groupé selon la nature des conditions. Si les évaluations
 * ne portent pas de `nature` (ancien chemin LLM), bascule sur un rendu à plat.
 */
function EligibilityAnalysis({ matchResult }: { matchResult: AideMatchResult }) {
  const evals: Evaluation[] = matchResult.llmEvaluation?.evaluations ?? [];
  const eliminatoires = matchResult.criteresNonRemplis ?? [];
  const hasNature = evals.some((e) => !!e.nature);

  if (!hasNature) {
    return (
      <div className="space-y-3 rounded-xl border bg-card p-4" style={{ borderColor: C.border }}>
        <EligibilitySummary matchResult={matchResult} />
        <div className="space-y-2">
          {matchResult.criteresRemplis.map((c, i) => <EvalLine key={`ok-${i}`} critere={c} tone="green" />)}
          {eliminatoires.map((c, i) => <EvalLine key={`ko-${i}`} critere={c} tone="red" />)}
          {evals.map((e, i) => {
            const clarified = e.verdict === 'incertitude' && e.clarified;
            const tone: EvalTone = e.verdict === 'oui' || clarified ? 'green' : e.verdict === 'non' ? 'red' : e.verdict === 'info' ? 'muted' : 'amber';
            return <EvalLine key={`ev-${i}`} critere={e.critere} explication={e.explication} tone={tone} />;
          })}
        </div>
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
    <div className="space-y-2.5">
      {eliminatoires.length > 0 && (
        <EvalGroup icon={IconErreur} tone="red" title="Ce qui ne correspond pas" count={eliminatoires.length} defaultOpen>
          {eliminatoires.map((c, i) => <EvalLine key={i} critere={c} tone="red" />)}
        </EvalGroup>
      )}
      {aVerifier.length > 0 && (
        <EvalGroup icon={IconHelp} tone="amber" title="À vérifier de votre côté" count={aVerifier.length} defaultOpen>
          {aVerifier.map((e, i) => <EvalLine key={i} critere={e.critere} tone="amber" />)}
        </EvalGroup>
      )}
      {financeur.length > 0 && (
        <EvalGroup icon={IconContact} tone="muted" title="À confirmer avec l'organisme" count={financeur.length}>
          {financeur.map((e, i) => (
            <EvalLine key={i} critere={e.critere} explication={e.explication} tone={e.verdict === 'incertitude' ? 'amber' : 'muted'} />
          ))}
        </EvalGroup>
      )}
      {valides.length > 0 && (
        <EvalGroup icon={IconSucces} tone="green" title="Déjà validé grâce à vos réponses" count={valides.length}>
          {valides.map((e, i) => <EvalLine key={i} critere={e.critere} tone="green" />)}
        </EvalGroup>
      )}
      {autos.length > 0 && (
        <EvalGroup icon={IconSucces} tone="green" title="Vérifié automatiquement" count={autos.length}>
          {autos.map((e, i) => <EvalLine key={i} critere={e.critere} tone="green" />)}
        </EvalGroup>
      )}
      {infos.length > 0 && (
        <EvalGroup icon={IconInfo} tone="muted" title="Bon à savoir" count={infos.length}>
          {infos.map((e, i) => <EvalLine key={i} critere={e.critere} tone="muted" />)}
        </EvalGroup>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Étapes de la demande — parcours numéroté                            */
/* ------------------------------------------------------------------ */

function DemarcheSteps({ description }: { description: string }) {
  const steps = decodeHtml(description)
    .split('\n')
    .map((s) => s.trim().replace(/^[-•\d.)\s]+/, ''))
    .filter(Boolean);

  if (steps.length <= 1) {
    return <p className="text-[14.5px] leading-relaxed whitespace-pre-line text-muted-foreground">{decodeHtml(description)}</p>;
  }

  return (
    <ol className="space-y-4">
      {steps.map((step, i) => (
        <li key={i} className="relative flex gap-3.5">
          {i < steps.length - 1 && (
            <span className="absolute left-[15px] top-9 h-[calc(100%-2px)] w-px" style={{ background: C.border }} aria-hidden />
          )}
          <span
            className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[13px] font-bold text-white"
            style={{ background: C.blue }}
          >
            {i + 1}
          </span>
          <p className="pt-1 text-[14.5px] leading-relaxed" style={{ color: C.ink }}>{step}</p>
        </li>
      ))}
    </ol>
  );
}

/* ------------------------------------------------------------------ */
/* Fiche « L'essentiel » (signature — colonne de droite)               */
/* ------------------------------------------------------------------ */

function EssentialFact({ icon: Icon, label, value, first }: { icon: IconType; label: string; value: ReactNode; first?: boolean }) {
  return (
    <div className="flex items-start gap-3 px-5 py-3.5" style={first ? undefined : { borderTop: `1px solid ${C.border}` }}>
      <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
        <Icon className="h-[17px] w-[17px]" strokeWidth={1.9} />
      </span>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
        <div className="text-[14px] font-semibold leading-snug" style={{ color: C.ink }}>{value}</div>
      </div>
    </div>
  );
}

function EssentialCard({ aide }: { aide: Aide }) {
  const echeance = !aide.permanent && aide.dateLimite ? deadlineLabel(aide.dateLimite) : null;
  const echeanceTone = echeance ? DEADLINE_TONE[echeance.urgency] : null;
  const typeLabel = AIDE_TYPES.find((t) => t.value === aide.type)?.label;
  const moneyLabel = aide.tauxMax
    ? `Jusqu'à ${aide.tauxMax} %`
    : aide.montantMax ? `Jusqu'à ${formatCurrency(aide.montantMax)}` : null;

  return (
    <div className="overflow-hidden rounded-2xl border" style={{ borderColor: C.border, background: C.card, boxShadow: 'var(--shadow-card)' }}>
      <div className="flex items-center gap-2.5 px-5 py-3.5" style={{ background: 'var(--blue-dark)' }}>
        <IconParchemin className="h-[18px] w-[18px]" style={{ color: 'var(--background)' }} strokeWidth={2} />
        <span className="text-[15px] tracking-wide" style={{ fontFamily: SERIF, color: 'var(--background)' }}>L'essentiel de l'aide</span>
      </div>
      <div className="h-[3px]" style={{ background: C.orange }} />
      <div>
        <EssentialFact first icon={IconInstitution} label="Qui verse l'aide" value={aide.organisme} />
        {moneyLabel && (
          <EssentialFact
            icon={IconSubvention}
            label="Combien"
            value={(
              <>
                {moneyLabel}
                {aide.tauxMax && <span className="block text-[12px] font-normal text-muted-foreground">de vos travaux (base {aide.baseTTC ? 'TTC' : 'HT'})</span>}
              </>
            )}
          />
        )}
        {typeLabel && <EssentialFact icon={IconRegle} label="Type d'aide" value={typeLabel} />}
        <EssentialFact
          icon={IconEcheance}
          label="Jusqu'à quand candidater"
          value={(
            <span style={echeanceTone ? { color: echeanceTone.fg } : undefined}>
              {aide.permanent || !echeance ? "Ouvert toute l'année" : echeance.urgency === 'past' ? 'Candidatures closes' : echeance.text}
            </span>
          )}
        />
        {aide.delaiInstruction && (
          <EssentialFact icon={IconTemps} label="Délai de réponse" value={aide.delaiInstruction} />
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Documents (menu déroulant fermé par défaut)                         */
/* ------------------------------------------------------------------ */

function DocumentLine({ raw }: { raw: string | AideDocument }) {
  const doc = typeof raw === 'string' ? { nom: raw } as AideDocument : raw;
  return (
    <li className="rounded-xl border bg-card px-3.5 py-3" style={{ borderColor: C.border }}>
      <div className="flex items-center gap-3">
        <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
          <IconDocument className="h-[15px] w-[15px]" strokeWidth={2} />
        </span>
        <span className="flex min-w-0 flex-wrap items-center gap-1.5 text-sm">
          {doc.url ? (
            <a
              href={doc.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-medium text-primary underline underline-offset-2"
            >
              {doc.nom}
              <IconLienExterne className="h-3 w-3" />
            </a>
          ) : (
            <span style={{ color: C.ink }}>{doc.nom}</span>
          )}
          {doc.obligatoire === false && (
            <Badge variant="outline" className="text-[10px]">selon le cas</Badge>
          )}
        </span>
      </div>
      {doc.note && <p className="mt-1.5 pl-10 text-xs text-muted-foreground">{doc.note}</p>}
    </li>
  );
}

function DocumentsCollapsible({ docs }: { docs: (string | AideDocument)[] }) {
  if (!docs?.length) return null;
  return (
    <Collapsible className="rounded-2xl border bg-card" style={{ borderColor: C.border, boxShadow: 'var(--shadow-card)' }}>
      <CollapsibleTrigger className="group flex w-full items-center justify-between gap-3 p-5 text-left">
        <span className="flex items-center gap-3">
          <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
            <IconDocument className="h-[18px] w-[18px]" strokeWidth={1.9} />
          </span>
          <span className="flex flex-col">
            <span className="text-[16px]" style={{ fontFamily: SERIF, color: C.ink }}>Les documents à préparer</span>
            <span className="text-[13px] text-muted-foreground">
              {docs.length} document{docs.length > 1 ? 's' : ''} à réunir — cliquez pour voir la liste
            </span>
          </span>
        </span>
        <ChevronDown className="h-5 w-5 shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="px-5 pb-5">
          <ul className="space-y-2">
            {docs.map((raw, i) => <DocumentLine key={i} raw={raw} />)}
          </ul>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export function AideDetails({ aide, matchResult, monumentName, showHeader = true, showDocumentsRequis = true, aside }: AideDetailsProps) {
  const categoryConfig = AIDE_CATEGORIES.find((c) => c.value === aide.categorie);

  return (
    <div className="space-y-6">
      {showHeader && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={categoryConfig?.color ?? ''}>{categoryConfig?.label ?? aide.categorie}</Badge>
            {matchResult && <EligibilityBadge matchResult={matchResult} />}
          </div>
          <h2 className="text-2xl font-bold" style={{ fontFamily: SERIF, color: C.ink }}>{decodeHtml(aide.nom)}</h2>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Colonne de lecture */}
        <div className="space-y-5 lg:col-span-2">
          <SectionCard icon={IconParchemin} title="En bref">
            <EnBref text={decodeHtml(aide.descriptionLongue || aide.description)} />
          </SectionCard>

          {matchResult && (
            <SectionCard
              icon={IconDiagnostic}
              tint="success"
              title={(
                <span>
                  Êtes-vous éligible&nbsp;?
                  {monumentName && <span className="ml-1 text-[13px] font-normal text-muted-foreground" style={{ fontFamily: 'var(--font-sans)' }}>pour {monumentName}</span>}
                </span>
              )}
            >
              <EligibilityAnalysis matchResult={matchResult} />
            </SectionCard>
          )}

          {aide.demarcheDescription && (
            <SectionCard icon={IconEtapes} title="Les étapes de la demande">
              <DemarcheSteps description={aide.demarcheDescription} />
            </SectionCard>
          )}
        </div>

        {/* Colonne de référence — la fiche */}
        <div className="lg:col-span-1">
          <div className="space-y-4 lg:sticky lg:top-20">
            <EssentialCard aide={aide} />

            {aide.urlOfficielle && (
              <a
                href={aide.urlOfficielle}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-[13px] font-semibold transition-colors hover:bg-secondary"
                style={{ borderColor: C.border, color: C.blue }}
              >
                <IconLienExterne className="h-4 w-4" />
                Consulter la page officielle
              </a>
            )}

            <div className="flex items-start gap-2.5 rounded-xl px-4 py-3" style={{ background: 'var(--secondary)' }}>
              <IconContact className="mt-0.5 h-4 w-4 shrink-0" style={{ color: C.blue }} strokeWidth={1.9} />
              <p className="text-[12.5px] leading-snug text-muted-foreground">
                Un doute&nbsp;? On vous accompagne pour monter ce dossier, étape par étape.
              </p>
            </div>

            {aside}
          </div>
        </div>
      </div>

      {showDocumentsRequis && <DocumentsCollapsible docs={aide.documentsRequis} />}
    </div>
  );
}

function EligibilityBadge({ matchResult }: { matchResult: AideMatchResult }) {
  const status = getEligibilityStatus(matchResult);
  const className =
    status === 'eligible'
      ? 'border-success text-success bg-success-muted'
      : status === 'potential'
        ? 'border-warning text-warning bg-warning-muted'
        : 'border-destructive text-destructive bg-destructive-muted';

  return (
    <Badge variant="outline" className={className}>
      {status === 'eligible' ? (
        <><IconSucces className="h-3 w-3 mr-1" />Éligible</>
      ) : status === 'potential' ? (
        <><IconHelp className="h-3 w-3 mr-1" />Potentiellement éligible</>
      ) : (
        <><IconErreur className="h-3 w-3 mr-1" />Non éligible</>
      )}
    </Badge>
  );
}
