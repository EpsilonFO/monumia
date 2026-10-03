import { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { AllClear } from '@/components/illustrations';
import { EcranQuestion } from '@/components/project/wizard/EcranQuestion';
import { ReponsesQuestion } from '@/components/project/wizard/ReponsesQuestion';
import { Picto } from '@/components/shared/ecrans/Picto';
import {
  computeEliminatedAideIds,
  isQuestionServingLiveAide,
  isVisible,
  partitionnerQuestions,
} from '@/lib/qcm';
import { reponsesChoisies } from '@/lib/question-reponse';
import type { RepriseDurable } from '@/services/projet.service';
import type { BilanDiagnostic } from '@/lib/diagnostic-bilan';
import { formatCurrency } from '@/lib/format-utils';
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
  /**
   * Avancement du questionnaire (0 à 100), remonté à la coquille du wizard qui
   * le dessine en tête de page et sous l'étape de la colonne. Appelé à chaque
   * changement.
   */
  onProgression?: (pct: number) => void;
}

/**
 * La rubrique d'une question, lue sur le `scope` de son fait : le bien, le
 * chantier ou celui qui dépose. C'est la seule classification que l'ontologie
 * porte (`categorie` n'est que la clé du fait) ; sans scope, pas de rubrique.
 */
const RUBRIQUE_PAR_SCOPE: Record<NonNullable<QcmQuestion['scope']>, string> = {
  monument: 'Le monument',
  projet: 'Le projet',
  proprietaire: 'Le porteur',
};

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
    <details className="reprises">
      <summary>
        {n} réponse{n > 1 ? 's' : ''} reprise{n > 1 ? 's' : ''} de{provenance} sur ce monument :
        voir {n > 1 ? 'lesquelles' : 'laquelle'}
      </summary>
      <ul>
        {reprises.map((r) => (
          <li key={r.fact}>
            {r.question}
            {r.reponse && (
              <>
                {' '}
                <b>{r.reponse}</b>
              </>
            )}
          </li>
        ))}
      </ul>
      <p>
        Vous avez accepté de les reprendre&nbsp;: elles ne vous sont donc pas reposées.
        Pour les corriger, refaites le questionnaire depuis la page du projet.
      </p>
    </details>
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
    <div className="bilan">
      <div className="chiffres">
        {chiffres.map((c) => (
          <div key={c.libelle}>
            <strong>{c.valeur}</strong>
            <span>{c.libelle}</span>
          </div>
        ))}
      </div>
      <p>
        sur {complet.aPortee} aide{complet.aPortee > 1 ? 's' : ''} à portée de votre monument
        {complet.aConfirmerUneQuestion > 0 && (
          <>
            {' '}&middot; dont {complet.aConfirmerUneQuestion} à une seule question d&rsquo;un verdict
          </>
        )}
        {/* La page projet range sous « Disponibles bientôt » toute aide dont la
            fenêtre est fermée, quel que soit son statut. Sans cette ligne, le
            chiffre ci-dessus promet des aides que l'écran suivant n'affiche pas
            là où on les cherche. */}
        {complet.eligibles > complet.eligiblesMaintenant && (
          <>
            {' '}&middot;{' '}
            {complet.eligiblesMaintenant === 0
              ? complet.eligibles > 1
                ? 'leurs guichets ouvrent plus tard'
                : 'son guichet ouvre plus tard'
              : `dont ${complet.eligibles - complet.eligiblesMaintenant} dont le guichet ouvre plus tard`}
          </>
        )}
      </p>
    </div>
  );
}

/**
 * Questionnaire du moteur d'aides, posé **une question à la fois** (style Doctolib).
 * On clique une réponse → elle se coche → si elle écarte des aides, un encart dit
 * pourquoi → « Continuer » mène à la question suivante. Jamais d'auto-avance :
 * l'encart doit pouvoir se lire, et une réponse se corriger avant de partir.
 * La dernière mène à un écran de fin avec le bouton final (jamais de lancement par accident).
 * `value` mappe id de question → id d'option, ou → liste d'ids sur une question à
 * choix multiple (`multiple`). Une question passée n'a simplement pas de clé : le
 * moteur la traite comme inconnue.
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
  onProgression,
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
  // Plus haute progression atteinte À CET ÉCRAN (cf. le calcul de `pct`).
  const progressHighWater = useRef({ index: 0, pct: 0 });
  const finishRef = useRef<HTMLHeadingElement | null>(null);

  const onFinish = index >= total;
  const q = onFinish ? null : questions[index];

  // Changement d'écran : on note la question comme VUE et on donne le focus.
  // Celui des réponses appartient à `ReponsesQuestion` (`autoFocus`), qui possède
  // les refs de ses boutons ; ici il ne reste que l'écran de fin.
  useEffect(() => {
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
    setDir('fwd');
    setIndex((i) => Math.min(i + 1, total));
  };

  const goBack = () => {
    setDir('back');
    setIndex((i) => Math.max(i - 1, 0));
  };

  /**
   * Une réponse du bloc de question. Elle s'enregistre et rien ne bouge : on
   * n'avance qu'au « Continuer », en choix simple comme en choix multiple.
   */
  const repondre = (answer: string | string[] | undefined) => {
    if (!q) return;
    const answers = { ...value };
    if (answer === undefined) delete answers[q.id];
    else answers[q.id] = answer;
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

  // La barre est dessinée par la coquille (tête de page et colonne).
  useEffect(() => {
    onProgression?.(pct);
  }, [pct, onProgression]);

  // ─── Écran de fin du TRONC COMMUN ───
  // Il reste des questions, mais elles ne concernent chacune qu'une seule aide :
  // les poser ici serait le tunnel qu'on cherche à éviter. Deux options de même
  // poids, et le prix de chacune écrit noir sur blanc.
  if (onFinish && finTroncActif && finTronc) {
    const bilan = finTronc.bilan;
    const r = bilan?.questionsRestantes ?? restantes;
    return (
      <div className={`fin ${slideClass}`}>
        <AllClear />
        <h2 ref={finishRef} tabIndex={-1}>
          Le tronc commun est terminé
        </h2>
        <p>
          Les questions suivantes ne concernent plus qu&rsquo;une aide chacune. Vous pouvez les
          garder pour plus tard&nbsp;: elles vous seront reposées sur la carte de l&rsquo;aide
          concernée.
        </p>
        <BandeauReprises reprises={reprises} />

        {bilan === null ? (
          <div className="attente">
            <Loader2 className="spin" aria-hidden="true" />
            Calcul de votre diagnostic…
          </div>
        ) : (
          <BilanTronc bilan={bilan} />
        )}

        {/* Deux boutons de même poids : ce sont deux intentions, pas une
            action et son annulation. */}
        <div className="actions">
          <button
            type="button"
            className="btn b-orange"
            onClick={finTronc.onDecouvrir}
            disabled={submitting}
          >
            {submitting ? (
              <>
                <Loader2 className="spin" aria-hidden="true" />
                Analyse des aides en cours…
              </>
            ) : (
              <>
                Découvrir mon diagnostic
                <Picto nom="fleche" />
              </>
            )}
          </button>
          <button
            type="button"
            className="btn b-line"
            onClick={finTronc.onContinuer}
            disabled={submitting || bilan === null}
          >
            Répondre aux {r} question{r > 1 ? 's' : ''} restante{r > 1 ? 's' : ''}
            <em>(≈ {bilan?.minutesEstimees ?? 0} min)</em>
          </button>
        </div>

        {!submitting && (
          <button type="button" className="retour" onClick={goBack}>
            <Picto nom="retour" />
            Revoir mes réponses
          </button>
        )}
      </div>
    );
  }

  // ─── Écran de fin ───
  if (onFinish) {
    const answered = questions.filter((qq) => value[qq.id] !== undefined).length;
    return (
      <div className={`fin ${slideClass}`}>
        <AllClear />
        <h2 ref={finishRef} tabIndex={-1}>
          C&rsquo;est tout&nbsp;!
        </h2>
        <p>
          {answered > 0
            ? `Vous avez répondu à ${answered} question${answered > 1 ? 's' : ''}. `
            : total === 0
              ? 'Aucune précision supplémentaire n’était nécessaire. '
              : 'Pas de souci si vous avez passé des questions. '}
          On met à jour vos aides.
        </p>
        <BandeauReprises reprises={reprises} />
        <div className="actions">
          <button type="button" className="btn b-orange" onClick={onComplete} disabled={submitting}>
            {submitting ? (
              <>
                <Loader2 className="spin" aria-hidden="true" />
                Analyse des aides en cours…
              </>
            ) : (
              <>
                {completeLabel}
                <Picto nom="fleche" />
              </>
            )}
          </button>
        </div>
        {!submitting && (
          <button type="button" className="retour" onClick={goBack}>
            <Picto nom="retour" />
            Revoir mes réponses
          </button>
        )}
      </div>
    );
  }

  // ─── Une question à la fois ───
  const multiple = !!q!.multiple;
  // Hors pseudo-choix « passer » : une réponse `skip` déjà enregistrée ne
  // coche rien et n'ouvre pas « Continuer ».
  const chosen = reponsesChoisies(value[q!.id]);
  const contexte = contexteAide?.(q!) ?? null;
  const rubrique = q!.scope ? RUBRIQUE_PAR_SCOPE[q!.scope] : null;

  return (
    <EcranQuestion
      // Chaque question glisse à son arrivée, et son encart « Pourquoi »
      // repart replié.
      key={q!.id}
      className={slideClass}
      // Hors tronc commun, chaque question ne sert plus qu'une aide ou deux :
      // on dit laquelle, et ce qu'elle pèse. Sans ce contexte, la question
      // paraît sortie de nulle part.
      rubrique={
        rubrique || contexte ? (
          <>
            {rubrique}
            {rubrique && contexte && ' · '}
            {contexte && (
              <span className="pour">
                Pour {contexte.nom}
                {contexte.nbAides > 1 &&
                  ` et ${contexte.nbAides - 1} autre${contexte.nbAides > 2 ? 's' : ''} aide${contexte.nbAides > 2 ? 's' : ''}`}
                {typeof contexte.montantMax === 'number' &&
                  contexte.montantMax > 0 &&
                  `, jusqu’à ${formatCurrency(contexte.montantMax)}`}
              </span>
            )}
          </>
        ) : null
      }
      titre={q!.question}
      // La consigne doit être lue AVANT de cliquer : la forme carrée des cases
      // ne suffit pas à dire qu'on peut en cocher plusieurs.
      consigne={multiple ? 'Plusieurs réponses possibles.' : null}
      pourquoi={q!.help}
      // Sur la PREMIÈRE question seulement : dire ce qui a été repris des
      // autres projets. Le répéter à chaque question serait du bruit.
      enTete={index === 0 ? <BandeauReprises reprises={reprises} /> : null}
      multiple={multiple}
      onPrecedent={index > 0 ? goBack : undefined}
      // « Passer » efface la réponse : en choix multiple, il effacerait des
      // cases cochées, d'où son retrait dès qu'il y en a (« Continuer » prend
      // le relais). En choix simple, il reste offert sur une question déjà
      // répondue où l'on revient : c'est le seul moyen de se dédire.
      onPasser={multiple && chosen.length > 0 ? undefined : skip}
      // « Continuer » n'avance qu'une fois une réponse donnée : rien de coché
      // ne veut pas dire « aucune de ces réponses » mais « je n'ai pas
      // répondu », et l'échappatoire porte son propre libellé.
      onContinuer={goNext}
      continuerDesactive={chosen.length === 0}
      continuerIndice={multiple ? 'Choisissez au moins une réponse.' : 'Choisissez une réponse.'}
      modifiablePlusTard
    >
      <ReponsesQuestion question={q!} value={value[q!.id]} onAnswer={repondre} autoFocus />
    </EcranQuestion>
  );
}
