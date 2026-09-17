import { useMemo, useState } from 'react';
import type { ComponentType, ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import {
  IconLienExterne,
  IconInstitution,
  IconDocument,
  IconSubvention,
  IconSucces,
  IconErreur,
  IconHelp,
  IconCle,
  IconInfo,
  IconEtapes,
  IconDiagnostic,
  IconEcheance,
  IconRegle,
  IconParchemin,
  IconFiche,
  IconAttention,
  IconTendance,
  IconLivre,
  IconRecherche,
} from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Input } from '@/components/ui/input';
import { QuestionOptions } from '@/components/project/wizard/QuestionOptions';
import { AIDE_CATEGORIES, AIDE_TYPES } from '@/constants/aide-categories';
import { questionsPourAide } from '@/lib/diagnostic-bilan';
import { formatCurrency } from '@/lib/format-utils';
import { deadlineLabel } from '@/lib/date-utils';
import { C, SERIF, DEADLINE_TONE } from '@/lib/brand';
import { getEligibilityStatus, STATUS_BADGE } from './eligibility-status';
import type {
  Aide,
  AideDocument,
  AideLevier,
  AideMatchResult,
  ProjectQuestionnaireAnswers,
  QcmQuestion,
} from '@/types';

export const decodeHtml = (text: string | null | undefined): string => {
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
  /** Contenu rendu dans la colonne de droite, sous la fiche « L'essentiel ». */
  aside?: ReactNode;
  /**
   * Répondre depuis la fiche. Même contrat que sur la carte : sans
   * `onRepondre`, l'analyse reste en lecture seule (c'est le cas d'un
   * collaborateur sans droit d'écriture, et du parcours invité).
   */
  questions?: QcmQuestion[];
  answers?: ProjectQuestionnaireAnswers;
  onRepondre?: (factKey: string, value: string | string[] | undefined) => void;
  envoiEnCours?: boolean;
}

/** Ce qu'il faut pour poser une question dans l'analyse — rien ou tout. */
interface ReponseEnPlace {
  questions?: QcmQuestion[];
  answers?: ProjectQuestionnaireAnswers;
  onRepondre?: (factKey: string, value: string | string[] | undefined) => void;
  envoiEnCours?: boolean;
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
type EvalTone = 'green' | 'red' | 'amber' | 'info' | 'muted';

function CountPill({ icon: Icon, tone, children }: { icon: IconType; tone: 'success' | 'warning' | 'info' | 'destructive'; children: ReactNode }) {
  const map = {
    success: 'bg-success-muted text-success',
    warning: 'bg-warning-muted text-warning',
    info: 'bg-info-muted text-info',
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
  // Un critère à débloquer n'est pas bloquant : il a une démarche en face.
  const toUnlock = matchResult.leviers?.length ?? 0;
  const blocking = (matchResult.criteresNonRemplis?.length ?? 0)
    + evals.filter((e) => e.verdict === 'non' && !e.levier).length;
  if (validated + toVerify + toUnlock + blocking === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {validated > 0 && <CountPill icon={IconSucces} tone="success">{validated} remplie{validated > 1 ? 's' : ''}</CountPill>}
      {toUnlock > 0 && <CountPill icon={IconCle} tone="info">{toUnlock} à débloquer</CountPill>}
      {toVerify > 0 && <CountPill icon={IconHelp} tone="warning">{toVerify} à vérifier</CountPill>}
      {blocking > 0 && <CountPill icon={IconErreur} tone="destructive">{blocking} bloquante{blocking > 1 ? 's' : ''}</CountPill>}
    </div>
  );
}

/**
 * Plan d'action d'un critère à débloquer : ce qu'il faut faire, auprès de qui,
 * pour combien et en combien de temps. C'est la différence entre « vous n'y
 * avez pas droit » et « voilà comment y avoir droit ».
 */
function LevierPlan({ levier }: { levier: AideLevier }) {
  const facts = [
    levier.organisme && { label: 'Auprès de', value: levier.organisme },
    levier.cout && { label: 'Coût', value: levier.cout },
    levier.delai && { label: 'Délai', value: levier.delai },
  ].filter((f): f is { label: string; value: string } => !!f);

  return (
    <div className="space-y-1.5">
      <div className="flex items-start gap-2 text-sm">
        <IconCle className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <span style={{ color: C.ink }}>{levier.critere}</span>
      </div>
      <div className="space-y-1.5 pl-6">
        <p className="text-[13px] font-medium leading-snug" style={{ color: C.ink }}>
          {levier.resume}
        </p>
        {levier.ecart && (
          <p className="text-[12.5px] font-semibold text-info">{levier.ecart}</p>
        )}
        {levier.demarche && (
          <p className="text-xs leading-relaxed text-muted-foreground">{levier.demarche}</p>
        )}
        {facts.length > 0 && (
          <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
            {facts.map((f) => (
              <div key={f.label} className="flex gap-1.5">
                <dt className="text-muted-foreground">{f.label}</dt>
                <dd style={{ color: C.ink }}>{f.value}</dd>
              </div>
            ))}
          </dl>
        )}
        {levier.url && (
          <a
            href={levier.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs font-semibold text-info underline underline-offset-2"
          >
            Ouvrir la démarche
            <IconLienExterne className="h-3 w-3" />
          </a>
        )}
      </div>
    </div>
  );
}

/**
 * Ligne de verdict. Le critère porte la couleur d'encre pleine (14,21:1) et
 * l'explication le gris lisible `--gray-fg` (7,9:1) : la hiérarchie se lit
 * sans que le texte secondaire tombe sous le seuil de confort. Ne jamais
 * remettre `text-muted-foreground` (4,86:1) sur le critère lui-même.
 */
function EvalLine({ critere, explication, tone }: { critere: string; explication?: string; tone: EvalTone }) {
  const Icon = tone === 'green' ? IconSucces : tone === 'red' ? IconErreur : tone === 'amber' ? IconHelp : tone === 'info' ? IconCle : IconInfo;
  const iconClass = tone === 'green' ? 'text-success' : tone === 'red' ? 'text-destructive' : tone === 'amber' ? 'text-warning' : tone === 'info' ? 'text-info' : 'text-muted-foreground';
  return (
    <div className="space-y-0.5">
      <div className="flex items-start gap-2 text-sm leading-snug">
        <Icon className={`h-4 w-4 shrink-0 mt-0.5 ${iconClass}`} />
        <span style={{ color: tone === 'red' ? 'var(--destructive)' : C.ink }}>{critere}</span>
      </div>
      {explication && <p className="pl-6 text-xs leading-relaxed" style={{ color: 'var(--gray-fg)' }}>{explication}</p>}
    </div>
  );
}

const GROUP_TONES: Record<EvalTone, { bg: string; fg: string }> = {
  green: { bg: 'var(--success-muted)', fg: 'var(--success)' },
  amber: { bg: 'var(--warning-muted)', fg: 'var(--warning)' },
  info:  { bg: 'var(--info-muted)', fg: 'var(--info)' },
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
 * Détail de l'analyse, groupé selon la nature des conditions. Si aucune
 * évaluation ne porte de `nature`, bascule sur un rendu à plat.
 */
function EligibilityAnalysis({
  matchResult,
  questions,
  answers,
  onRepondre,
  envoiEnCours,
}: { matchResult: AideMatchResult } & ReponseEnPlace) {
  const evals: Evaluation[] = matchResult.llmEvaluation?.evaluations ?? [];
  const eliminatoires = matchResult.criteresNonRemplis ?? [];
  const leviers = matchResult.leviers ?? [];
  const hasNature = evals.some((e) => !!e.nature);

  // SOURCE DE VÉRITÉ des questions de cette aide : `q.aideIds`, jamais
  // `evaluations[].categorie`. Une condition bloquée par une passerelle
  // `applies_if` n'a pas de `categorie` quand son propre fait est connu
  // (eligibility_engine.py) : s'appuyer sur elle laisserait des questions
  // invisibles, alors qu'elles sont ce qui sépare l'aide d'un verdict.
  const restantes =
    onRepondre && questions ? questionsPourAide(matchResult.aide.id, questions, answers ?? {}) : [];
  const parFait = new Map(restantes.map((q) => [q.id, q]));
  const poser = (q: QcmQuestion, sousUnCritere = false) => (
    <div className={sousUnCritere ? 'pl-6 pt-1' : 'pt-0.5'}>
      <QuestionOptions
        question={q}
        value={answers?.[q.id]}
        onAnswer={(v) => onRepondre?.(q.id, v)}
        compact
        disabled={envoiEnCours}
      />
    </div>
  );

  if (!hasNature) {
    return (
      <div className="space-y-3 rounded-xl border bg-card p-4" style={{ borderColor: C.border }}>
        <EligibilitySummary matchResult={matchResult} />
        <div className="space-y-2">
          {matchResult.criteresRemplis.map((c, i) => <EvalLine key={`ok-${i}`} critere={c} tone="green" />)}
          {eliminatoires.map((c, i) => <EvalLine key={`ko-${i}`} critere={c} tone="red" />)}
          {evals.map((e, i) => {
            const clarified = e.verdict === 'incertitude' && e.clarified;
            const tone: EvalTone = e.verdict === 'oui' || clarified ? 'green' : e.levier ? 'info' : e.verdict === 'non' ? 'red' : e.verdict === 'info' ? 'muted' : 'amber';
            return <EvalLine key={`ev-${i}`} critere={e.critere} explication={e.explication} tone={tone} />;
          })}
        </div>
      </div>
    );
  }

  const isClarified = (e: Evaluation) => e.verdict === 'incertitude' && e.clarified;
  // Les critères à débloquer ont leur propre groupe, alimenté par `leviers` :
  // ils ne doivent apparaître ni en rouge, ni parmi les critères validés.
  const aVerifier = evals.filter((e) => e.verdict === 'incertitude' && e.nature === 'user_fact' && !e.clarified);
  // Gate `auto` qu'on n'a pas pu trancher : vraie incertitude sur l'éligibilité,
  // mais aucune question à poser (ce n'est pas un fait du propriétaire).
  const aConfirmer = evals.filter((e) => e.nature === 'auto' && e.verdict === 'incertitude');
  const valides = evals.filter((e) => e.nature === 'user_fact' && (e.verdict === 'oui' || isClarified(e)));
  const autos = evals.filter((e) => e.nature === 'auto' && e.verdict === 'oui');

  // Appariement question ↔ critère affiché. On le calcule AVANT le rendu : une
  // question posée deux fois (sous son critère et dans les orphelines) ferait
  // deux formulaires concurrents pour un seul fait.
  const appariees = new Set(
    aVerifier.map((e) => e.categorie).filter((k): k is string => !!k && parFait.has(k)),
  );
  const orphelines = restantes.filter((q) => !appariees.has(q.id));

  return (
    <div className="space-y-2.5">
      {eliminatoires.length > 0 && (
        <EvalGroup icon={IconErreur} tone="red" title="Ce qui ne correspond pas" count={eliminatoires.length} defaultOpen>
          {eliminatoires.map((c, i) => <EvalLine key={i} critere={c} tone="red" />)}
        </EvalGroup>
      )}
      {leviers.length > 0 && (
        <EvalGroup icon={IconCle} tone="info" title="À débloquer" count={leviers.length} defaultOpen>
          {leviers.map((levier, i) => <LevierPlan key={i} levier={levier} />)}
        </EvalGroup>
      )}
      {aVerifier.length > 0 && (
        <EvalGroup icon={IconHelp} tone="amber" title="À vérifier de votre côté" count={aVerifier.length} defaultOpen>
          {aVerifier.map((e, i) => {
            const q = e.categorie ? parFait.get(e.categorie) : undefined;
            return (
              <div key={i} className="space-y-1">
                <EvalLine critere={e.critere} tone="amber" />
                {q && poser(q, true)}
              </div>
            );
          })}
        </EvalGroup>
      )}
      {/* Les questions de l'aide qu'aucun critère affiché ne porte : conditions
          suspendues à une passerelle, dont l'évaluation n'a pas de `categorie`.
          Sans ce bloc elles resteraient invisibles ici alors même qu'elles
          gouvernent le verdict. */}
      {orphelines.length > 0 && (
        <EvalGroup icon={IconHelp} tone="amber" title="Précisez votre situation" count={orphelines.length} defaultOpen>
          {orphelines.map((q) => (
            <div key={q.id}>{poser(q)}</div>
          ))}
        </EvalGroup>
      )}
      {aConfirmer.length > 0 && (
        <EvalGroup icon={IconInstitution} tone="amber" title="À confirmer auprès de l'organisme" count={aConfirmer.length} defaultOpen>
          {aConfirmer.map((e, i) => <EvalLine key={i} critere={e.critere} tone="amber" />)}
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
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* « Le règlement de cette aide » — document de référence              */
/* ------------------------------------------------------------------ */

/**
 * Les conditions non dirimantes (`discretionary`, `manual_check`,
 * `modulateur`, `info`) ne sont pas des verdicts : les enfermer dans le cadre
 * vert du diagnostic les condamnait à rester discrètes pour ne pas concurrencer
 * les vrais verdicts — d'où la liste de quinze lignes grises que personne ne
 * lisait. Sorties dans leur propre carte, elles récupèrent la pleine puissance
 * typographique et un registre de « document de référence » : sous-titres réels,
 * recherche, tout déplier.
 */

const RULE_GROUPS: { nature: string; icon: IconType; tone: EvalTone; title: string; hint: string }[] = [
  {
    nature: 'discretionary',
    icon: IconAttention,
    tone: 'amber',
    title: 'Ce que le financeur va apprécier',
    hint: "Rien d'automatique ici : ces points se jouent dans la qualité du dossier.",
  },
  {
    nature: 'manual_check',
    icon: IconInstitution,
    tone: 'info',
    title: 'À confirmer au montage du dossier',
    hint: 'Sans incidence sur votre éligibilité — à vérifier avec l’organisme le moment venu.',
  },
  {
    nature: 'modulateur',
    icon: IconTendance,
    tone: 'info',
    title: 'Ce qui peut moduler le montant',
    hint: "N'affecte pas l'éligibilité, mais joue sur le taux ou le plafond accordé.",
  },
  {
    nature: 'info',
    icon: IconLivre,
    tone: 'muted',
    title: 'Les autres règles à connaître',
    hint: 'Bénéficiaires, plafonds, exclusions, calendrier, obligations après octroi.',
  },
];

/** Aplatit un texte pour une recherche insensible à la casse et aux accents. */
const flatten = (text: string): string =>
  text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/**
 * Surligne les occurrences de la requête. Le texte source n'est jamais modifié,
 * seulement découpé ; si la normalisation décale les index (ligature, caractère
 * exotique), on rend le texte brut plutôt qu'un surlignage faux.
 */
function Highlight({ text, query }: { text: string; query: string }) {
  const flat = flatten(text);
  const q = flatten(query);
  if (!q || flat.length !== text.length) return <>{text}</>;
  const parts: ReactNode[] = [];
  let from = 0;
  for (let i = flat.indexOf(q); i !== -1; i = flat.indexOf(q, from)) {
    if (i > from) parts.push(text.slice(from, i));
    parts.push(
      <mark key={i} className="rounded bg-warning-muted px-0.5" style={{ color: 'inherit' }}>
        {text.slice(i, i + q.length)}
      </mark>,
    );
    from = i + q.length;
  }
  if (!parts.length) return <>{text}</>;
  parts.push(text.slice(from));
  return <>{parts}</>;
}

/**
 * Une rubrique du règlement. Pas d'icône répétée en tête de chaque ligne (la
 * même vingt fois n'informe personne) : un filet de séparation suffit à donner
 * le rythme, et la marge récupérée va au texte. L'explication n'est rendue par
 * ligne que si elle varie dans la rubrique — sinon elle est hissée en tête,
 * une fois, au lieu d'être répétée à l'identique sous chaque item.
 */
function RuleGroup({ group, items, open, onOpenChange, query }: {
  group: (typeof RULE_GROUPS)[number];
  items: Evaluation[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  query: string;
}) {
  const t = GROUP_TONES[group.tone];
  const Icon = group.icon;
  const distinctExpl = new Set(items.map((e) => e.explication).filter(Boolean));
  const perLineExpl = distinctExpl.size > 1;

  return (
    <Collapsible open={open} onOpenChange={onOpenChange} className="border-t first:border-t-0" style={{ borderColor: C.border }}>
      <CollapsibleTrigger className="group flex w-full items-start gap-3 py-3.5 text-left">
        <span className="mt-px inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg" style={{ background: t.bg, color: t.fg }}>
          <Icon className="h-4 w-4" strokeWidth={2} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="text-[15px] font-semibold leading-snug" style={{ color: C.ink }}>{group.title}</span>
            <span className="rounded-full px-2 py-0.5 text-[11.5px] font-bold tabular-nums" style={{ background: t.bg, color: t.fg }}>
              {items.length}
            </span>
          </span>
          <span className="mt-0.5 block text-[12.5px] leading-snug" style={{ color: 'var(--gray-fg)' }}>{group.hint}</span>
        </span>
        <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ul className="mb-1 divide-y pl-10" style={{ borderColor: C.border }}>
          {items.map((e, i) => (
            <li key={i} className="py-2.5 first:border-t first:pt-3" style={{ borderColor: C.border }}>
              <p className="text-[14px] leading-relaxed" style={{ color: C.ink }}>
                <Highlight text={e.critere} query={query} />
              </p>
              {perLineExpl && e.explication && (
                <p className="mt-0.5 text-[12.5px] leading-relaxed" style={{ color: 'var(--gray-fg)' }}>{e.explication}</p>
              )}
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  );
}

/** Seuil au-delà duquel une rubrique s'ouvre repliée, et la recherche apparaît. */
const RULES_SEARCH_THRESHOLD = 12;
const GROUP_AUTO_OPEN_MAX = 6;

function RulesReference({ matchResult }: { matchResult: AideMatchResult }) {
  const [query, setQuery] = useState('');
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});

  const groups = useMemo(() => {
    const evals: Evaluation[] = matchResult.llmEvaluation?.evaluations ?? [];
    const q = flatten(query.trim());
    return RULE_GROUPS.map((group) => {
      const all = evals.filter((e) => e.nature === group.nature);
      const items = q ? all.filter((e) => flatten(e.critere).includes(q)) : all;
      return { group, items, total: all.length };
    }).filter((g) => g.total > 0);
  }, [matchResult, query]);

  const total = groups.reduce((n, g) => n + g.total, 0);
  const matching = groups.reduce((n, g) => n + g.items.length, 0);
  if (total === 0) return null;

  const searching = query.trim().length > 0;
  const isOpen = (nature: string, count: number) =>
    searching ? true : (overrides[nature] ?? count <= GROUP_AUTO_OPEN_MAX);
  const allOpen = groups.every((g) => isOpen(g.group.nature, g.total));

  return (
    <SectionCard icon={IconRegle} title="Le règlement de cette aide">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[13.5px] leading-snug" style={{ color: 'var(--gray-fg)' }}>
            {total} point{total > 1 ? 's' : ''} issu{total > 1 ? 's' : ''} du règlement officiel. Aucun ne décide de votre
            éligibilité&nbsp;: ils servent à préparer le dossier.
          </p>
          <button
            onClick={() => setOverrides(Object.fromEntries(groups.map((g) => [g.group.nature, !allOpen])))}
            className="shrink-0 text-[13px] font-semibold text-primary hover:underline"
          >
            {allOpen ? 'Tout replier' : 'Tout déplier'}
          </button>
        </div>

        {total > RULES_SEARCH_THRESHOLD && (
          <div className="relative">
            <IconRecherche className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher dans le règlement (taux, délai, cumul…)"
              aria-label="Rechercher dans le règlement de l'aide"
              className="h-9 bg-card pl-9 text-[13.5px]"
            />
          </div>
        )}

        {searching && (
          <p className="text-[12.5px]" style={{ color: 'var(--gray-fg)' }}>
            {matching === 0 ? 'Aucun point ne correspond.' : `${matching} point${matching > 1 ? 's' : ''} sur ${total}.`}
          </p>
        )}

        <div>
          {groups
            .filter((g) => !searching || g.items.length > 0)
            .map(({ group, items, total: count }) => (
              <RuleGroup
                key={group.nature}
                group={group}
                items={items}
                query={query.trim()}
                open={isOpen(group.nature, count)}
                onOpenChange={(open) => setOverrides((o) => ({ ...o, [group.nature]: open }))}
              />
            ))}
        </div>
      </div>
    </SectionCard>
  );
}

/* ------------------------------------------------------------------ */
/* Étapes de la demande — parcours numéroté                            */
/* ------------------------------------------------------------------ */

/**
 * Découpe une démarche écrite en un seul paragraphe « 1. … 2. … 3. … » en
 * étapes. On ne coupe que sur des numéros séquentiels (1, 2, 3…) suivis d'un
 * point : « 4 000 € », « avant le 15 juillet » ou un « 2. » isolé au milieu du
 * texte ne déclenchent donc pas de coupe. L'éventuel préambule avant « 1. »
 * devient la première ligne.
 */
function splitInlineSteps(text: string): string[] {
  const starts: number[] = [];
  let expected = 1;
  for (const m of text.matchAll(/(?:^|\s)(\d{1,2})[.)]\s+/g)) {
    if (Number(m[1]) === expected) {
      starts.push(m.index);
      expected += 1;
    }
  }
  if (starts.length < 2) return [text];
  const parts = starts.map((s, i) => text.slice(s, starts[i + 1]));
  if (starts[0] > 0) parts.unshift(text.slice(0, starts[0]));
  return parts;
}

function DemarcheSteps({ description }: { description: string }) {
  const decoded = decodeHtml(description);
  const lines = decoded.split('\n').map((s) => s.trim()).filter(Boolean);
  // Une seule « ligne » : la démarche est probablement numérotée inline.
  const parts = lines.length > 1 ? lines : splitInlineSteps(decoded.trim());
  const steps = parts
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
      <div className="flex items-center gap-2.5 px-5 py-3.5" style={{ background: C.blue }}>
        <IconFiche className="h-[18px] w-[18px]" style={{ color: 'var(--background)' }} strokeWidth={2} />
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
              {docs.length} document{docs.length > 1 ? 's' : ''} à réunir
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

export function AideDetails({ aide, matchResult, monumentName, showHeader = true, showDocumentsRequis = true, aside, questions, answers, onRepondre, envoiEnCours }: AideDetailsProps) {
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
          <SectionCard icon={IconParchemin} title="Présentation de l'aide">
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
              <EligibilityAnalysis
                matchResult={matchResult}
                questions={questions}
                answers={answers}
                onRepondre={onRepondre}
                envoiEnCours={envoiEnCours}
              />
            </SectionCard>
          )}

          {matchResult && <RulesReference matchResult={matchResult} />}

          {showDocumentsRequis && <DocumentsCollapsible docs={aide.documentsRequis} />}

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

            {aside}
          </div>
        </div>
      </div>

    </div>
  );
}

function EligibilityBadge({ matchResult }: { matchResult: AideMatchResult }) {
  const { className, label, icon: Icon } = STATUS_BADGE[getEligibilityStatus(matchResult)];
  return (
    <Badge variant="outline" className={className}>
      <Icon className="h-3 w-3 mr-1" />
      {label}
    </Badge>
  );
}
