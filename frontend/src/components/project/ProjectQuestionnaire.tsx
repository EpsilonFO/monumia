import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowRight, ArrowLeft, Loader2 } from 'lucide-react';
import { AllClear } from '@/components/illustrations';
import { AnswerCard } from '@/components/project/wizard/AnswerCard';
import { SkipCard } from '@/components/project/wizard/SkipCard';
import { isUnknownAnswer } from '@/components/project/wizard/unknownAnswer';
import { IconInfo } from '@/components/icons';
import { computeEliminatedAideIds, isQuestionServingLiveAide } from '@/lib/qcm';
import { C, SERIF } from '@/lib/brand';
import { cn } from '@/lib/utils';
import type { ProjectQuestionnaireAnswers, QcmOption, QcmQuestion } from '@/types';

interface ProjectQuestionnaireProps {
  /** Questions générées par le moteur d'aides (faits manquants du diagnostic). */
  questions: QcmQuestion[];
  value: ProjectQuestionnaireAnswers;
  onChange: (answers: ProjectQuestionnaireAnswers) => void;
  /** Appelé sur l'écran de fin, quand l'utilisateur valide. */
  onComplete: () => void;
  /** Vrai pendant l'enregistrement + le diagnostic (spinner sur le bouton final). */
  submitting?: boolean;
  /** Libellé du bouton final. */
  completeLabel?: string;
}

/** Délai avant l'auto-avance : laisse voir sa réponse se cocher. */
const ADVANCE_MS = 420;

/**
 * Au-delà, le texte d'aide est replié à trois lignes. Seuil calé sur la largeur
 * de lecture (62ch) : les textes courts s'affichent en entier, les longs (la
 * moitié de l'ontologie dépasse 190 caractères) ne poussent pas les réponses
 * sous la ligne de flottaison.
 */
const HELP_CLAMP_CHARS = 170;

/**
 * Note explicative d'une question : encart distinct de la question elle-même,
 * en contraste lisible, replié à trois lignes quand il est long. Même geste que
 * « Lire la suite » sur la fiche d'aide.
 */
function QuestionHelp({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > HELP_CLAMP_CHARS;
  return (
    <div
      className="flex max-w-[62ch] gap-2.5 rounded-xl border-l-[3px] py-2.5 pl-3 pr-3.5"
      style={{ borderColor: C.blueLight, background: 'var(--secondary)' }}
    >
      <IconInfo className="mt-[3px] h-4 w-4 shrink-0" style={{ color: C.blue }} />
      <div className="min-w-0">
        <p
          className={cn('text-[14px] leading-relaxed', !open && long && 'line-clamp-3')}
          style={{ color: C.grayFg }}
        >
          {text}
        </p>
        {long && (
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="mt-1 text-[13px] font-semibold underline-offset-2 hover:underline"
            style={{ color: C.blue }}
          >
            {open ? 'Réduire' : 'Lire la suite'}
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Ordre d'affichage des options : les vraies réponses d'abord, les
 * échappatoires (« je ne sais pas ») en bas, sous forme de carte pointillée.
 * Sert aussi de parcours au clavier, pour que les flèches suivent ce qu'on voit.
 */
function displayOrder(question: QcmQuestion): QcmOption[] {
  return [
    ...question.options.filter((o) => !isUnknownAnswer(o)),
    ...question.options.filter(isUnknownAnswer),
  ];
}

/**
 * Réponse à une question, toujours vue comme une liste d'ids : une seule case
 * pour une question simple, plusieurs pour une question à choix multiple.
 */
function selectedIds(question: QcmQuestion, answers: ProjectQuestionnaireAnswers): string[] {
  const answer = answers[question.id];
  if (Array.isArray(answer)) return answer;
  return typeof answer === 'string' ? [answer] : [];
}

/**
 * Une question conditionnelle n'est posée que si la réponse à la question dont
 * elle dépend la rend pertinente. Fail-closed : tant que cette question n'est
 * pas répondue (ou qu'elle est passée), on pose quand même — mieux vaut une
 * question de trop qu'une aide écartée sans que l'utilisateur l'ait su.
 * Le moteur garantit que la question porteuse est posée AVANT ses dépendantes.
 * Sur une question porteuse à choix multiple, une seule case pertinente suffit.
 */
function isVisible(question: QcmQuestion, answers: ProjectQuestionnaireAnswers): boolean {
  const dep = question.dependsOn;
  if (!dep) return true;
  const answer = answers[dep.questionId];
  const given = (Array.isArray(answer) ? answer : [answer]).filter(
    (id): id is string => typeof id === 'string' && id !== 'skip',
  );
  if (given.length === 0) return true;
  return given.some((id) => dep.showForOptionIds.includes(id));
}

/**
 * Barre de progression du questionnaire — une jauge, et RIEN d'écrit.
 *
 * Le nombre de questions dépend des aides encore candidates et peut dépasser
 * cinquante : l'annoncer (« Question 3 sur 52 ») décourage avant la première
 * réponse. Une barre dit la même chose sans le chiffre, et elle dit vrai —
 * son dénominateur fond à mesure que les réponses écartent des aides, donc
 * elle avance plus vite que le rang de la question.
 */
function Progression({ pct }: { pct: number }) {
  return (
    <div
      role="progressbar"
      aria-label="Progression du questionnaire"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-valuetext={`${pct}\u00a0% du questionnaire parcouru`}
      className="mb-5 h-1.5 w-full overflow-hidden rounded-full"
      style={{ background: `color-mix(in srgb, ${C.blue} 12%, transparent)` }}
    >
      {/* Un plancher visible : à la première question d'une longue liste, le
          ratio réel ne ferait qu'un ou deux pixels, qu'on lirait comme une
          barre vide. `aria-valuenow` reste, lui, la valeur exacte. */}
      <div
        className="h-full rounded-full transition-[width] duration-500 ease-out motion-reduce:transition-none"
        style={{
          width: `${Math.max(pct, 3)}%`,
          background: `linear-gradient(90deg, ${C.orange}, ${C.orangeVif})`,
        }}
      />
    </div>
  );
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

/**
 * Questionnaire du moteur d'aides, posé **une question à la fois** (style Doctolib).
 * On clique une réponse → elle se coche → la question suivante glisse automatiquement.
 * La dernière mène à un écran de fin avec le bouton final (jamais de lancement par accident).
 * `value` mappe id de question → id d'option, ou → liste d'ids sur une question à
 * choix multiple (`multiple`), qui attend alors un « Continuer » explicite. Une
 * question passée n'a simplement pas de clé : le moteur la traite comme inconnue.
 */
export function ProjectQuestionnaire({
  questions: allQuestions,
  value,
  onChange,
  onComplete,
  submitting,
  completeLabel = 'Lancer le diagnostic',
}: ProjectQuestionnaireProps) {
  // Questions déjà affichées, par id. Une question que le curseur a dépassée ne
  // doit plus jamais disparaître, même passée : le parcours se repère à un
  // index positionnel, et retirer une question SITUÉE AVANT le décalerait — on
  // sauterait alors silencieusement la suivante. Remis à zéro quand le moteur
  // renvoie un autre jeu de questions.
  const seenRef = useRef<{ source: QcmQuestion[]; ids: Set<string> }>({
    source: allQuestions,
    ids: new Set(),
  });
  if (seenRef.current.source !== allQuestions) {
    seenRef.current = { source: allQuestions, ids: new Set() };
  }

  // Le parcours ne connaît que les questions PERTINENTES pour les réponses déjà
  // données : la navigation et l'écran de fin se calculent dessus. Une question porteuse répondue peut en faire disparaître d'autres —
  // toujours situées après elle, donc l'index courant reste valide.
  const questions = useMemo(() => {
    // Une réponse peut écarter d'un coup toutes les aides que d'autres questions
    // servaient : les poser quand même ferait perdre du temps sans rien changer
    // au résultat. Une seule passe sur l'ensemble des réponses — répondue ou
    // déjà vue, la question reste affichée, si bien que le couple
    // visibilité/élimination a un point fixe et que seules des questions encore
    // à venir peuvent tomber. Les réponses des questions masquées restent dans
    // le payload (même comportement que `dependsOn`) : le moteur ré-évalue tout
    // côté serveur.
    const eliminated = new Set(computeEliminatedAideIds(value, allQuestions));
    return allQuestions.filter(
      (q) =>
        isVisible(q, value) &&
        (value[q.id] !== undefined ||
          seenRef.current.ids.has(q.id) ||
          isQuestionServingLiveAide(q, eliminated)),
    );
  }, [allQuestions, value]);
  const total = questions.length;
  const [index, setIndex] = useState(0);
  const [dir, setDir] = useState<'fwd' | 'back'>('fwd');
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Plus haute progression atteinte À CET ÉCRAN (cf. le calcul de `pct`).
  const progressHighWater = useRef({ index: 0, pct: 0 });
  const optionRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const finishRef = useRef<HTMLHeadingElement | null>(null);

  const onFinish = index >= total;
  const q = onFinish ? null : questions[index];

  const clearTimer = () => {
    if (advanceTimer.current) {
      clearTimeout(advanceTimer.current);
      advanceTimer.current = null;
    }
  };

  useEffect(() => clearTimer, []);

  // Focus à chaque changement d'écran (accessibilité + clavier).
  useEffect(() => {
    clearTimer();
    if (onFinish) {
      finishRef.current?.focus();
      return;
    }
    const current = questions[index];
    if (!current) return;
    seenRef.current.ids.add(current.id);
    const targetId = selectedIds(current, value)[0] ?? current.options[0]?.id;
    if (targetId) optionRefs.current[`${current.id}:${targetId}`]?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, onFinish]);

  const goNext = () => {
    clearTimer();
    setDir('fwd');
    setIndex((i) => Math.min(i + 1, total));
  };

  const goBack = () => {
    clearTimer();
    setDir('back');
    setIndex((i) => Math.max(i - 1, 0));
  };

  /** Sélectionne une réponse puis avance automatiquement après un court délai. */
  const commit = (optionId: string) => {
    if (!q) return;
    onChange({ ...value, [q.id]: optionId });
    clearTimer();
    advanceTimer.current = setTimeout(goNext, prefersReducedMotion() ? 180 : ADVANCE_MS);
  };

  /**
   * Choix multiple : coche/décoche, sans jamais avancer tout seul (c'est
   * « Continuer » qui le fait). Les réponses « je ne sais pas » sont exclusives
   * des autres — cocher « pas encore décidé » ET « association » n'aurait aucun
   * sens. Sélection vide ⇒ on efface la clé : la question est passée.
   */
  const toggle = (option: QcmOption) => {
    if (!q) return;
    const current = selectedIds(q, value);
    const optionOf = (id: string) => q.options.find((o) => o.id === id);
    let next: string[];
    if (current.includes(option.id)) {
      next = current.filter((id) => id !== option.id);
    } else if (isUnknownAnswer(option)) {
      next = [option.id];
    } else {
      const kept = current.filter((id) => {
        const o = optionOf(id);
        return o ? !isUnknownAnswer(o) : true;
      });
      next = [...kept, option.id];
    }
    // Ordre du moteur : la réponse persistée ne dépend pas de l'ordre des clics.
    const rank = (id: string) => q.options.findIndex((o) => o.id === id);
    next.sort((a, b) => rank(a) - rank(b));

    const answers = { ...value };
    if (next.length === 0) delete answers[q.id];
    else answers[q.id] = next;
    onChange(answers);
  };

  /** « Passer cette question » : on efface l'éventuelle réponse et on avance (le moteur gère). */
  const skip = () => {
    if (!q) return;
    if (value[q.id] !== undefined) {
      const next = { ...value };
      delete next[q.id];
      onChange(next);
    }
    goNext();
  };

  const onOptionKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, optionIndex: number) => {
    if (!q) return;
    const isNext = e.key === 'ArrowDown' || e.key === 'ArrowRight';
    const isPrev = e.key === 'ArrowUp' || e.key === 'ArrowLeft';
    if (!isNext && !isPrev) return;
    e.preventDefault();
    const order = displayOrder(q);
    const n = isNext
      ? (optionIndex + 1) % order.length
      : (optionIndex - 1 + order.length) % order.length;
    optionRefs.current[`${q.id}:${order[n].id}`]?.focus();
  };

  const slideClass = dir === 'fwd' ? 'q-in-fwd' : 'q-in-back';

  // Rang de la question courante sur les questions ENCORE pertinentes (l'écran
  // de fin vaut 100 %). Sur place, la barre ne recule jamais : cocher une case
  // de plus sur une question à choix multiple LIBÈRE des aides (sémantique
  // existentielle, cf. `computeEliminatedAideIds`) et peut donc rallonger la
  // liste — voir la jauge redescendre pendant qu'on répond se lirait comme une
  // punition. Changer d'écran la relâche : « Précédent » doit bien faire
  // reculer la barre.
  const rawPct = total === 0 ? 100 : Math.round((Math.min(index + 1, total) / total) * 100);
  const highWater = progressHighWater.current;
  if (highWater.index !== index) {
    highWater.index = index;
    highWater.pct = rawPct;
  } else if (rawPct > highWater.pct) {
    highWater.pct = rawPct;
  }
  const pct = highWater.pct;

  // ─── Écran de fin ───
  if (onFinish) {
    const answered = questions.filter((qq) => value[qq.id] !== undefined).length;
    return (
      <div>
        <Progression pct={pct} />
        <div className={cn('flex flex-col items-center gap-5 py-10 text-center', slideClass)}>
          <AllClear />
          <h2
            ref={finishRef}
            tabIndex={-1}
            className="text-[clamp(1.5rem,3.4vw,2rem)] leading-tight outline-none"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
            C&rsquo;est tout&nbsp;!
          </h2>
          <p className="max-w-sm text-[15px] leading-relaxed" style={{ color: C.grayFg }}>
            {answered > 0
              ? `Vous avez répondu à ${answered} question${answered > 1 ? 's' : ''}. `
              : 'Pas de souci si vous avez passé des questions. '}
            On met à jour vos aides.
          </p>
          <button
            type="button"
            onClick={onComplete}
            disabled={submitting}
            className="group mt-1 inline-flex min-h-[3.25rem] items-center gap-2 rounded-2xl px-7 py-3.5 text-[16px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)] disabled:opacity-60"
            style={{ background: C.orange }}
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyse des aides en cours…
              </>
            ) : (
              <>
                {completeLabel}
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </>
            )}
          </button>
          {!submitting && (
            <button
              type="button"
              onClick={goBack}
              className="inline-flex items-center gap-1.5 text-[13px] font-medium underline-offset-2 hover:underline"
              style={{ color: C.grayMuted }}
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Revoir mes réponses
            </button>
          )}
        </div>
      </div>
    );
  }

  // ─── Une question à la fois ───
  // Les options « je ne sais pas » du moteur descendent en bas de la liste,
  // rendues comme le bouton « Passer cette question » : même forme pour la même
  // intention. Quand le moteur n'en fournit aucune, on ajoute notre « passer ».
  const answerOptions = q!.options.filter((o) => !isUnknownAnswer(o));
  const unknownOptions = q!.options.filter(isUnknownAnswer);
  const showSkipCard = unknownOptions.length === 0;
  // Choix multiple : pas d'auto-avance possible (l'utilisateur n'a pas fini de
  // cocher), donc un bouton « Continuer » explicite dans la barre du bas.
  const multiple = !!q!.multiple;
  const chosen = selectedIds(q!, value);

  return (
    <div>
      {/* Une barre, mais jamais de compteur « Question N sur M » : le nombre
          de questions dépend des aides candidates et peut dépasser cinquante,
          ce qui décourage avant même la première réponse. Le rail annonce
          « Quelques minutes », et les questions sans objet tombent au fil
          des réponses — d'où une barre qui accélère. */}
      <Progression pct={pct} />

      {/* Question (glisse à chaque changement) */}
      <div key={q!.id} className={cn(slideClass, 'pb-1')}>
        <fieldset role={multiple ? 'group' : 'radiogroup'} className="space-y-4">
          {/* La légende ne porte QUE la question : c'est elle qui nomme le
              groupe de boutons radio pour les lecteurs d'écran. La note
              explicative vit à côté, où elle peut être repliée. */}
          <legend className="w-full">
            <span
              className="block text-[clamp(1.25rem,2.8vw,1.6rem)] leading-snug"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {q!.question}
            </span>
            {/* La consigne doit être lue AVANT de cliquer : la forme carrée des
                cases ne suffit pas à dire qu'on peut en cocher plusieurs. */}
            {multiple && (
              <span
                className="mt-1.5 block text-[13px] font-semibold"
                style={{ color: C.orange }}
              >
                Plusieurs réponses possibles
              </span>
            )}
          </legend>

          {q!.help && <QuestionHelp text={q!.help} />}

          <div
            className={cn(
              'grid gap-2.5',
              answerOptions.length > 3 ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1',
            )}
          >
            {answerOptions.map((option, optionIndex) => {
              const selected = chosen.includes(option.id);
              const refKey = `${q!.id}:${option.id}`;
              const roving = selected || (chosen.length === 0 && optionIndex === 0);
              return (
                <AnswerCard
                  key={option.id}
                  option={option}
                  selected={selected}
                  roving={roving}
                  multiple={multiple}
                  onSelect={() => (multiple ? toggle(option) : commit(option.id))}
                  onKeyDown={(e) => onOptionKeyDown(e, optionIndex)}
                  buttonRef={(el) => {
                    optionRefs.current[refKey] = el;
                  }}
                />
              );
            })}
          </div>

          {/* Les « je ne sais pas » du moteur : mêmes cartes pointillées que le
              « passer », mais ce sont de vraies réponses — elles restent dans le
              groupe radio et se cochent. */}
          {unknownOptions.map((option, unknownIndex) => {
            const selected = chosen.includes(option.id);
            const refKey = `${q!.id}:${option.id}`;
            return (
              <SkipCard
                key={option.id}
                label={option.label}
                asOption
                selected={selected}
                roving={
                  selected ||
                  (chosen.length === 0 && answerOptions.length === 0 && unknownIndex === 0)
                }
                multiple={multiple}
                onSelect={() => (multiple ? toggle(option) : commit(option.id))}
                onKeyDown={(e) => onOptionKeyDown(e, answerOptions.length + unknownIndex)}
                buttonRef={(el) => {
                  optionRefs.current[refKey] = el;
                }}
              />
            );
          })}

          {/* En choix multiple, « passer » effacerait des cases cochées : on ne
              le propose plus dès qu'il y en a (« Continuer » prend le relais).
              En choix simple il reste offert, y compris sur une question déjà
              répondue où l'on revient — c'est le seul moyen de se dédire. */}
          {showSkipCard && (!multiple || chosen.length === 0) && (
            <SkipCard label="Passer cette question" onSelect={skip} />
          )}
        </fieldset>
      </div>

      {/* Navigation bas */}
      <div
        className="mt-3 flex items-center justify-between border-t py-3"
        style={{ borderColor: C.border }}
      >
        <button
          type="button"
          onClick={goBack}
          disabled={index === 0}
          className="inline-flex min-h-11 items-center gap-1.5 text-[14px] font-medium transition-opacity disabled:pointer-events-none disabled:opacity-0"
          style={{ color: C.grayFg }}
        >
          <ArrowLeft className="h-4 w-4" />
          Précédent
        </button>
        {multiple ? (
          /* « Continuer » n'avance qu'une fois quelque chose de coché : en choix
             multiple, rien de coché ne veut pas dire « aucune de ces réponses »
             mais « je n'ai pas répondu », et l'échappatoire porte son propre
             libellé — « Passer cette question », ou le « je ne sais pas » du
             moteur juste au-dessus. */
          <div className="flex flex-wrap items-center justify-end gap-3">
            {chosen.length === 0 && (
              <span className="text-[13px]" style={{ color: C.grayMuted }}>
                Choisissez au moins une réponse.
              </span>
            )}
            <button
              type="button"
              onClick={goNext}
              disabled={chosen.length === 0}
              className="group inline-flex min-h-11 items-center gap-2 rounded-xl px-5 py-2.5 text-[15px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)] disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:shadow-none"
              style={{ background: C.orange }}
            >
              Continuer
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </button>
          </div>
        ) : (
          <span className="hidden text-[12px] sm:block" style={{ color: C.grayMuted }}>
            Vous pourrez refaire ce questionnaire plus tard
          </span>
        )}
      </div>
    </div>
  );
}
