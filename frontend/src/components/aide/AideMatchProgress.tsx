import { useEffect, useState } from 'react';
import {
  Check,
  Loader2,
  Sparkles,
  Building2,
  Telescope,
  ListChecks,
  Quote,
  ScrollText,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

const STAGES = [
  {
    id: 'reading',
    label: 'Lecture du dossier monument',
    detail: 'Statut, époque, département, état de conservation…',
    targetPct: 8,
    minMs: 1200,
  },
  {
    id: 'evaluating',
    label: "Analyse des critères d'éligibilité",
    detail: 'Évaluation de chaque aide par le moteur IA',
    targetPct: 52,
    minMs: 36000,
  },
  {
    id: 'qcm',
    label: 'Génération du questionnaire complémentaire',
    detail: 'Questions pour lever les incertitudes restantes',
    targetPct: 97,
    minMs: 12000,
  },
];

const TICKER_AIDS = [
  // DRAC
  'DRAC — MH Classés',
  'DRAC — MH Inscrits',
  'DRAC — Urgence MH',
  'DRAC — Sécurité incendie MH',
  'DRAC — Médiation patrimoine',
  'Résidences artistes DRAC',
  // Mission Bern / Fondation du Patrimoine
  'Mission Patrimoine de Stéphane Bern',
  'Loto du patrimoine',
  'Label Fondation du patrimoine',
  'Souscription Fondation du patrimoine',
  'Mécénat entreprise dirigé (FdP)',
  // Région
  'Patrimoine Remarquable AURA',
  'Aide patrimoine Nouvelle-Aquitaine',
  'Aide patrimoine Île-de-France',
  'Aide PNR patrimoine bâti',
  // Fiscal
  "Crédit d'impôt Monument Historique",
  'TVA 10 % rénovation',
  'TVA 5,5 % réno. énergétique',
  'Éco-PTZ',
  'Dons particuliers (IR)',
  'Mécénat entreprise (Aillagon)',
  // Programmes européens
  'FEDER Patrimoine',
  'FEADER LEADER',
  'Interreg Patrimoine',
  // ADEME / énergie
  'Fonds Chaleur ADEME',
  'Programme SARE',
  'Fonds vert',
  // Tourisme / territoires
  'Patrimoine & Tourisme Local',
  'Prêt Tourisme BPI',
  'PVD Patrimoine',
  'ACV Patrimoine',
  'Hébergement insolite patrimoine',
  // Risques / sécurité
  'Fonds Barnier',
  'FIPD Vidéoprotection patrimoine',
  'Patrimoine en péril (assureurs)',
  // Fondations privées
  'Fondation TotalEnergies',
  'Fondation CA Pays de France',
  'Fondation de France — Patrimoine',
  'Fondation VMF',
  "Fondation La Sauvegarde de l'Art Français",
  'World Monuments Fund',
  // Mécénat & autres
  'Mécénat de compétences',
  'Apprentissage patrimoine',
  'CRTE',
  "Agences de l'eau",
  'Habitat participatif patrimoine',
  'Label Jardin remarquable',
];

const FACTOIDS = [
  {
    title: 'Le saviez-vous',
    body: 'Plus de 45 000 immeubles sont protégés au titre des Monuments Historiques en France.',
  },
  {
    title: 'Mécénat',
    body: "La loi Aillagon ouvre droit à 60 % de réduction d'impôt sur les dons d'entreprise au patrimoine.",
  },
  {
    title: 'Mission Bern',
    body: 'La Mission Patrimoine a mobilisé plus de 250 M€ pour la sauvegarde du patrimoine en péril.',
  },
  {
    title: 'Cumul des aides',
    body: 'Un projet patrimonial combine en moyenne 3 à 5 financeurs : État, Région, Département, fondations, mécénat.',
  },
  {
    title: 'Fiscalité',
    body: 'Les travaux sur un Monument Historique classé peuvent ouvrir droit à 100 % de déduction du déficit foncier.',
  },
  {
    title: 'Souscription',
    body: 'La Fondation du Patrimoine accompagne plus de 3 000 projets de restauration chaque année.',
  },
];

function useElapsed(running: boolean): number {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!running) return;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      setElapsed(now - start);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running]);
  return elapsed;
}

interface AideMatchProgressProps {
  monumentName?: string;
}

export function AideMatchProgress({ monumentName }: AideMatchProgressProps) {
  const elapsed = useElapsed(true);

  let progress = 0;
  let currentStageIdx = 0;
  let prevTarget = 0;
  let acc = 0;
  let found = false;
  for (let i = 0; i < STAGES.length; i++) {
    const s = STAGES[i];
    const startMs = acc;
    const endMs = acc + s.minMs;
    if (elapsed >= startMs && elapsed < endMs) {
      const t = (elapsed - startMs) / s.minMs;
      const eased = 1 - Math.pow(1 - t, 2);
      progress = prevTarget + (s.targetPct - prevTarget) * eased;
      currentStageIdx = i;
      found = true;
      break;
    }
    prevTarget = s.targetPct;
    acc = endMs;
  }
  if (!found) {
    const overflow = elapsed - acc;
    const lastTarget = STAGES[STAGES.length - 1].targetPct;
    const approach = 1 - Math.exp(-overflow / 25000);
    progress = lastTarget + (99 - lastTarget) * approach;
    currentStageIdx = STAGES.length - 1;
  }

  const totalCorpus = 142;
  const scanned = Math.min(Math.floor((progress / 72) * totalCorpus), totalCorpus);

  const safeMod = (n: number, m: number) => {
    if (!Number.isFinite(n) || m <= 0) return 0;
    return ((Math.floor(n) % m) + m) % m;
  };
  const tickerIdx = safeMod(elapsed / 1100, TICKER_AIDS.length);
  const factoidIdx = safeMod(elapsed / 7000, FACTOIDS.length);
  const tickerLine = TICKER_AIDS[tickerIdx] ?? TICKER_AIDS[0];
  const factoid = FACTOIDS[factoidIdx] ?? FACTOIDS[0];

  const seconds = Math.floor(elapsed / 1000);

  return (
    <Card className="border-primary/15 bg-gradient-to-br from-background via-background to-primary/[0.04] overflow-hidden shadow-sm">
      <CardContent className="py-10 px-6 sm:px-10 space-y-9">
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-accent font-medium">
            <Sparkles className="h-3 w-3" />
            Diagnostic en cours
          </div>
          <h2 className="font-serif text-3xl sm:text-4xl leading-[1.1] text-foreground">
            Nous explorons les aides disponibles
            {monumentName && (
              <>
                {' '}
                <span className="text-primary italic">pour {monumentName}</span>
              </>
            )}
          </h2>
          <p className="text-sm text-muted-foreground max-w-xl">
            Notre moteur croise votre dossier monument avec l'ensemble des aides publiques,
            privées et fiscales référencées.
          </p>
        </div>

        <div className="space-y-3">
          <div className="flex items-baseline justify-between gap-4">
            <span className="text-sm text-muted-foreground truncate">
              {STAGES[currentStageIdx].detail}
            </span>
            <span className="font-serif text-3xl text-primary tabular-nums leading-none">
              {Math.round(progress)}
              <span className="text-base text-muted-foreground ml-0.5">%</span>
            </span>
          </div>
          <div
            className="h-1.5 rounded-full bg-primary/10 overflow-hidden relative"
            role="progressbar"
            aria-valuenow={Math.round(progress)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Progression du diagnostic"
          >
            <div
              className="absolute inset-y-0 left-0 bg-gradient-to-r from-primary via-primary to-accent rounded-full transition-[width] duration-700 ease-out"
              style={{ width: `${progress}%` }}
            />
            <div className="absolute inset-0 progress-shimmer pointer-events-none" />
          </div>
        </div>

        <ol className="space-y-3.5">
          {STAGES.map((s, i) => {
            const isDone = i < currentStageIdx;
            const isCurrent = i === currentStageIdx;
            const isFuture = i > currentStageIdx;
            return (
              <li
                key={s.id}
                className="flex items-center gap-3.5 transition-opacity duration-700"
                style={{ opacity: isFuture ? 0.35 : 1 }}
                aria-current={isCurrent ? 'step' : undefined}
              >
                <span
                  className={`flex h-8 w-8 items-center justify-center rounded-full border transition-all duration-500 shrink-0 ${
                    isDone
                      ? 'bg-accent border-accent text-accent-foreground'
                      : isCurrent
                      ? 'border-primary bg-primary/5 text-primary'
                      : 'border-muted-foreground/25 text-muted-foreground/50'
                  }`}
                >
                  {isDone ? (
                    <Check className="h-4 w-4" strokeWidth={2.5} />
                  ) : isCurrent ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <span className="text-xs font-medium tabular-nums">{i + 1}</span>
                  )}
                </span>
                <div className="flex-1 min-w-0">
                  <p
                    className={`text-base leading-tight ${
                      isCurrent
                        ? 'text-foreground font-medium'
                        : isDone
                        ? 'text-foreground'
                        : 'text-muted-foreground'
                    }`}
                  >
                    {s.label}
                  </p>
                  {isCurrent && (
                    <p className="text-xs text-muted-foreground mt-0.5 animate-fade-in">
                      {s.detail}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>

        <div className="rounded-xl border border-primary/15 bg-primary/[0.025] px-5 py-4">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-primary/70 font-medium mb-2">
            <Telescope className="h-3 w-3" />
            Aide examinée à l'instant
          </div>
          <div className="relative h-7 overflow-hidden">
            <div
              key={tickerIdx}
              className="absolute inset-0 flex items-center font-serif text-lg sm:text-xl text-foreground italic ticker-in"
            >
              {tickerLine}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-xl border border-border bg-card px-5 py-4 flex flex-col">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-muted-foreground font-medium">
              <ListChecks className="h-3 w-3" />
              Aides analysées
            </div>
            <div className="font-serif text-4xl text-primary tabular-nums mt-2 leading-none">
              {scanned}
              <span className="text-base text-muted-foreground ml-1">/ {totalCorpus}</span>
            </div>
          </div>

          <div
            key={factoidIdx}
            className="rounded-xl border border-accent/20 bg-accent/[0.04] px-5 py-4 factoid-in"
          >
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-accent font-medium">
              <Quote className="h-3 w-3" />
              {factoid.title}
            </div>
            <p className="font-serif text-[15px] leading-snug text-foreground mt-2 italic">
              {factoid.body}
            </p>
          </div>

          <div className="rounded-xl border border-border bg-card px-5 py-4 flex flex-col">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-muted-foreground font-medium">
              <Building2 className="h-3 w-3" />
              Dossier
            </div>
            <p className="font-serif text-lg leading-snug text-foreground mt-2 truncate">
              {monumentName ?? 'Monument'}
            </p>
            <p className="text-xs text-muted-foreground mt-auto pt-2 flex items-center gap-1.5">
              <ScrollText className="h-3 w-3" />
              {seconds < 60
                ? `${seconds}s d'analyse`
                : `${Math.floor(seconds / 60)} min ${seconds % 60}s`}
            </p>
          </div>
        </div>

        <p className="text-xs text-center text-muted-foreground/70 italic">
          L'analyse peut prendre jusqu'à deux minutes pour les dossiers les plus complexes.
        </p>
      </CardContent>
    </Card>
  );
}
