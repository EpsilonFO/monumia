import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowRight, ArrowLeft, Loader2 } from 'lucide-react';
import { AllClear } from '@/components/illustrations';
import { QuestionOptions } from '@/components/project/wizard/QuestionOptions';
import {
  computeEliminatedAideIds,
  isQuestionServingLiveAide,
  isVisible,
  partitionnerQuestions,
  selectedIds,
} from '@/lib/qcm';
import type { RepriseDurable } from '@/services/projet.service';
import type { BilanDiagnostic } from '@/lib/diagnostic-bilan';
import { C, SERIF } from '@/lib/brand';
import { formatCurrency } from '@/lib/format-utils';
import { cn } from '@/lib/utils';
import type { ProjectQuestionnaireAnswers, QcmQuestion } from '@/types';

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
  /**
   * `'tronc'` ne pose que les questions PARTAGÉES par au moins deux aides
   * vivantes ; celles qui ne servent qu'une aide se posent sur sa carte et sa
   * fiche. `'toutes'` (défaut) garde le comportement historique — c'est ce que
   * veut « Refaire → seulement les questions passées », où l'on redemande
   * justement tout ce qui reste.
   */
  portee?: 'tronc' | 'toutes';
  /**
   * Écran de fin du tronc commun, affiché À LA PLACE du « C'est tout ! » quand
   * il reste des questions propres à une aide. Deux options de même poids, et
   * un bilan CALCULÉ (spinner tant qu'il vaut `null`) : promettre « 40 aides à
   * confirmer » qui tombent à 10 au premier clic serait pire que se taire.
   */
  finTronc?: {
    bilan: BilanDiagnostic | Pick<BilanDiagnostic, 'questionsRestantes' | 'minutesEstimees'> | null;
    onDecouvrir: () => void;
    onContinuer: () => void;
  };
  /** Appelé à CHAQUE passage de l'écran de questions à l'écran de fin du tronc. */
  onFinTronc?: () => void;
  /**
   * Contexte d'une question du COMPLÉMENT : l'aide qu'elle débloque et son
   * enjeu. Absent en mode invité, où les `aideIds` sont des pseudonymes.
   */
  contexteAide?: (q: QcmQuestion) => { nom: string; montantMax?: number | null; nbAides: number } | null;
  /**
   * Réponses REPRISES des autres projets du monument (faits durables : le bien,
   * le propriétaire), telles que la route les nomme. Affichées en bandeau
   * dépliable sur la PREMIÈRE question et sur l'écran de fin.
   *
   * Le dire est la contrepartie de la reprise : un questionnaire qui commence
   * par « question 1 » alors qu'il en a déjà neuf de répondues dans le dos se
   * lit comme une perte de données. Et il faut pouvoir dire LESQUELLES : une
   * réponse reprise n'étant plus une incertitude, le moteur ne rend plus sa
   * question et aucune fiche d'aide ne l'offre à la correction — cette liste
   * est le seul endroit où l'utilisateur peut vérifier ce qu'on a supposé pour
   * lui. Liste vide ⇒ rien n'est affiché.
   */
  reprises?: RepriseDurable[];
}

/** Délai avant l'auto-avance : laisse voir sa réponse se cocher. */
const ADVANCE_MS = 420;

/**
 * Bandeau des réponses reprises d'un autre projet du même monument.
 *
 * Discret, et jamais une alerte : ce n'est pas un avertissement, c'est une
 * explication — sans lui, le questionnaire semble avoir sauté des questions.
 *
 * Il DÉPLIE la liste, et ce n'est pas un ornement : une réponse reprise n'est
 * plus une incertitude, donc le moteur ne rend plus sa question, donc aucune
 * fiche d'aide ne l'offre à la correction. Le renvoi vers « Refaire le
 * questionnaire » est le seul geste qui les repose vraiment.
 *
 * C'est un RAPPEL, pas une découverte : l'accord a été demandé explicitement
 * avant le questionnaire (`ProjectReprisesStep`), et ce bandeau n'apparaît que
 * si l'utilisateur a dit oui.
 */
function BandeauReprises({ reprises }: { reprises: RepriseDurable[] }) {
  if (reprises.length === 0) return null;
  const n = reprises.length;
  // Un seul projet source dans l'immense majorité des cas : on le nomme.
  const titres = [...new Set(reprises.map((r) => r.projetTitre).filter(Boolean))];
  const provenance = titres.length === 1 ? ` « ${titres[0]} »` : ' vos autres projets';
  return (
    <details className="mb-3 text-[12.5px]" style={{ color: C.grayMuted }}>
      <summary className="cursor-pointer">
        {n} réponse{n > 1 ? 's' : ''} reprise{n > 1 ? 's' : ''} de{provenance} sur ce monument
        {' '}— voir {n > 1 ? 'lesquelles' : 'laquelle'}
      </summary>
      <ul className="mt-1.5 space-y-1 border-l pl-3" style={{ borderColor: C.border }}>
        {reprises.map((r) => (
          <li key={r.fact}>
            {r.question}
            {r.reponse && (
              <>
                {' '}
                <span style={{ color: C.ink }}>— {r.reponse}</span>
              </>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-1.5">
        Vous avez accepté de les reprendre&nbsp;: elles ne vous sont donc pas reposées.
        Pour les corriger, refaites le questionnaire depuis la page du projet.
      </p>
    </details>
  );
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

/**
 * Le bilan chiffré de fin de tronc commun.
 *
 * Tout y est CALCULÉ par une relance du moteur avec les réponses données, et
 * les deux nombres qui se confondent facilement sont séparés à dessein :
 * ce que les réponses ont écarté, et ce que le monument met à portée (le reste
 * ayant été écarté par les filtres automatiques, sans qu'on ait rien demandé).
 */
function BilanTronc({
  bilan,
}: {
  bilan: BilanDiagnostic | Pick<BilanDiagnostic, 'questionsRestantes' | 'minutesEstimees'>;
}) {
  const complet = 'aPortee' in bilan ? bilan : null;
  if (!complet) return null;
  const chiffres: { valeur: number; libelle: string }[] = [
    { valeur: complet.eligibles, libelle: complet.eligibles > 1 ? 'aides mobilisables' : 'aide mobilisable' },
    { valeur: complet.aConfirmer, libelle: 'à confirmer' },
    { valeur: complet.ecarteesParReponses, libelle: 'écartées par vos réponses' },
  ];
  return (
    <div
      className="w-full max-w-md rounded-2xl border p-4"
      style={{ borderColor: C.border, background: C.card }}
    >
      <div className="grid grid-cols-3 gap-2 text-center">
        {chiffres.map((c) => (
          <div key={c.libelle}>
            <div
              className="text-[22px] font-semibold tabular-nums leading-none"
              style={{ color: C.ink }}
            >
              {c.valeur}
            </div>
            <div className="mt-1 text-[12px] leading-snug" style={{ color: C.grayFg }}>
              {c.libelle}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 border-t pt-2.5 text-[12.5px]" style={{ borderColor: C.border, color: C.grayMuted }}>
        sur {complet.aPortee} aide{complet.aPortee > 1 ? 's' : ''} à portée de votre monument
        {complet.aConfirmerUneQuestion > 0 && (
          <>
            {' '}&middot; dont {complet.aConfirmerUneQuestion} à une seule question d&rsquo;un verdict
          </>
        )}
      </p>
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
  portee = 'toutes',
  finTronc,
  onFinTronc,
  contexteAide,
  reprises = [],
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
  const { questions, propres } = useMemo(() => {
    // Une réponse peut écarter d'un coup toutes les aides que d'autres questions
    // servaient : les poser quand même ferait perdre du temps sans rien changer
    // au résultat. Une seule passe sur l'ensemble des réponses — répondue ou
    // déjà vue, la question reste affichée, si bien que le couple
    // visibilité/élimination a un point fixe et que seules des questions encore
    // à venir peuvent tomber. Les réponses des questions masquées restent dans
    // le payload (même comportement que `dependsOn`) : le moteur ré-évalue tout
    // côté serveur.
    const eliminated = new Set(computeEliminatedAideIds(value, allQuestions));
    // Tronc commun : la troisième branche se resserre sur les questions
    // partagées. Le filtre reste DANS le composant, jamais en amont — `seenRef`
    // est clé sur l'identité du tableau `questions`, et le remplacer à chaque
    // réponse remettrait le parcours à zéro.
    const { tronc, propres } =
      portee === 'tronc'
        ? partitionnerQuestions(allQuestions, value)
        : { tronc: allQuestions, propres: [] as QcmQuestion[] };
    const troncIds = portee === 'tronc' ? new Set(tronc.map((q) => q.id)) : null;
    return {
      propres,
      questions: allQuestions.filter(
        (q) =>
          isVisible(q, value) &&
          (value[q.id] !== undefined ||
            seenRef.current.ids.has(q.id) ||
            (troncIds ? troncIds.has(q.id) : isQuestionServingLiveAide(q, eliminated))),
      ),
    };
  }, [allQuestions, value, portee]);
  const total = questions.length;
  // Questions du complément qui n'ont pas déjà été posées dans le tronc : une
  // question vue puis passée reste affichée ici, elle ne doit pas compter deux
  // fois. Le serveur la reposera au complément — c'est la sémantique de
  // « seulement les questions passées ».
  const restantes = propres.filter((q) => !seenRef.current.ids.has(q.id)).length;
  const [index, setIndex] = useState(0);
  const [dir, setDir] = useState<'fwd' | 'back'>('fwd');
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Plus haute progression atteinte À CET ÉCRAN (cf. le calcul de `pct`).
  const progressHighWater = useRef({ index: 0, pct: 0 });
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

  // Changement d'écran : on note la question comme VUE et on donne le focus.
  // Celui des réponses appartient à `QuestionOptions` (`autoFocus`), qui possède
  // les refs de ses boutons ; ici il ne reste que l'écran de fin.
  useEffect(() => {
    clearTimer();
    if (onFinish) {
      finishRef.current?.focus();
      return;
    }
    const current = questions[index];
    if (current) seenRef.current.ids.add(current.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, onFinish]);

  // Fin du tronc : on redemande un bilan au moteur À CHAQUE arrivée sur l'écran.
  // « Revoir mes réponses », corriger, puis revenir repartirait sinon d'un bilan
  // périmé — et ce sont justement ses chiffres qui décident du clic suivant.
  const finTroncActif = portee === 'tronc' && !!finTronc && restantes > 0;
  const cleReponses = JSON.stringify(value);
  useEffect(() => {
    if (onFinish && finTroncActif) onFinTronc?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onFinish, finTroncActif, cleReponses]);

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

  /**
   * Une réponse du bloc de question. Le composant ne connaît que la réponse ;
   * c'est ici qu'on décide d'avancer — et la règle n'a pas bougé : en choix
   * simple, cocher fait glisser à la question suivante après un court délai
   * (le temps de voir sa réponse se cocher) ; en choix multiple, rien ne bouge
   * tant que « Continuer » n'est pas cliqué.
   */
  const repondre = (answer: string | string[] | undefined) => {
    if (!q) return;
    const answers = { ...value };
    if (answer === undefined) delete answers[q.id];
    else answers[q.id] = answer;
    onChange(answers);
    if (q.multiple) return;
    clearTimer();
    advanceTimer.current = setTimeout(goNext, prefersReducedMotion() ? 180 : ADVANCE_MS);
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

  // ─── Écran de fin du TRONC COMMUN ───
  // Il reste des questions, mais elles ne concernent chacune qu'une seule aide :
  // les poser ici serait le tunnel qu'on cherche à éviter. Deux options de même
  // poids, et le prix de chacune écrit noir sur blanc.
  if (onFinish && finTroncActif && finTronc) {
    const bilan = finTronc.bilan;
    const r = bilan?.questionsRestantes ?? restantes;
    return (
      <div>
        <Progression pct={pct} />
        <div className={cn('flex flex-col items-center gap-5 py-8 text-center', slideClass)}>
          <AllClear />
          <h2
            ref={finishRef}
            tabIndex={-1}
            className="text-[clamp(1.4rem,3.2vw,1.9rem)] leading-tight outline-none"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
            Le tronc commun est terminé
          </h2>
          <p className="max-w-md text-[15px] leading-relaxed" style={{ color: C.grayFg }}>
            Les questions suivantes ne concernent plus qu&rsquo;une aide chacune. Vous
            pouvez les garder pour plus tard&nbsp;: elles vous seront reposées sur la
            carte de l&rsquo;aide concernée.
          </p>
          <BandeauReprises reprises={reprises} />

          {bilan === null ? (
            <div
              className="flex items-center gap-2 py-2 text-[13.5px]"
              style={{ color: C.grayMuted }}
            >
              <Loader2 className="h-4 w-4 animate-spin" style={{ color: C.blueLight }} />
              Calcul de votre diagnostic…
            </div>
          ) : (
            <BilanTronc bilan={bilan} />
          )}

          {/* Deux boutons de même poids : ce sont deux intentions, pas une
              action et son annulation. */}
          <div className="flex w-full max-w-md flex-col gap-2.5">
            <button
              type="button"
              onClick={finTronc.onDecouvrir}
              disabled={submitting}
              className="group inline-flex min-h-[3.25rem] items-center justify-center gap-2 rounded-2xl px-6 py-3.5 text-[16px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)] disabled:opacity-60"
              style={{ background: C.orange }}
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Analyse des aides en cours…
                </>
              ) : (
                <>
                  Découvrir mon diagnostic
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </>
              )}
            </button>
            <button
              type="button"
              onClick={finTronc.onContinuer}
              disabled={submitting || bilan === null}
              className="rounded-2xl border-[1.5px] px-5 py-3 text-[15px] font-semibold transition-colors hover:bg-warning-muted disabled:opacity-50"
              style={{ borderColor: C.orange, color: C.ink, background: C.card }}
            >
              Répondre aux {r} question{r > 1 ? 's' : ''} restante{r > 1 ? 's' : ''}
              <span className="ml-1.5 font-normal tabular-nums" style={{ color: C.orange }}>
                (≈ {bilan?.minutesEstimees ?? 0} min)
              </span>
            </button>
          </div>

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
              : total === 0
                ? 'Aucune précision supplémentaire n’était nécessaire. '
                : 'Pas de souci si vous avez passé des questions. '}
            On met à jour vos aides.
          </p>
          <BandeauReprises reprises={reprises} />
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
  // Choix multiple : pas d'auto-avance possible (l'utilisateur n'a pas fini de
  // cocher), donc un bouton « Continuer » explicite dans la barre du bas.
  const multiple = !!q!.multiple;
  const chosen = selectedIds(q!, value);
  const contexte = contexteAide?.(q!) ?? null;

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
        {/* Sur la PREMIÈRE question seulement : dire ce qui a été repris des
            autres projets. Le répéter à chaque question serait du bruit. */}
        {index === 0 && <BandeauReprises reprises={reprises} />}
        {/* Hors tronc commun, chaque question ne sert plus qu'une aide ou deux :
            on dit laquelle, et ce qu'elle pèse. Sans ce contexte, la question
            paraît sortie de nulle part — c'est exactement le hors-sujet que le
            tronc commun vient d'écarter. */}
        {contexte && (
          <p
            className="mb-2 text-[12.5px] font-medium uppercase tracking-[0.12em]"
            style={{ color: C.orange }}
          >
            Pour {contexte.nom}
            {contexte.nbAides > 1 && ` et ${contexte.nbAides - 1} autre${contexte.nbAides > 2 ? 's' : ''} aide${contexte.nbAides > 2 ? 's' : ''}`}
            {typeof contexte.montantMax === 'number' && contexte.montantMax > 0 && (
              <span className="normal-case tracking-normal" style={{ color: C.grayFg }}>
                {' '}&middot; jusqu&rsquo;à {formatCurrency(contexte.montantMax)}
              </span>
            )}
          </p>
        )}
        <QuestionOptions
          question={q!}
          value={value[q!.id]}
          onAnswer={repondre}
          onSkip={skip}
          autoFocus
        />
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
