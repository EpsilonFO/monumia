import { useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router';
import { ArrowRight, Loader2 } from 'lucide-react';
import { ProjectQuestionnaire } from '@/components/project/ProjectQuestionnaire';
import { ProjectIntentStep } from '@/components/project/wizard/ProjectIntentStep';
import { ProjectTravauxStep } from '@/components/project/wizard/ProjectTravauxStep';
import { PerilStep } from '@/components/project/wizard/PerilStep';
import { InscriptionStep } from '@/components/project/wizard/InscriptionStep';
import { WizardShell } from '@/components/project/wizard/WizardShell';
import { DiagnosticLoader } from '@/components/project/wizard/DiagnosticLoader';
import {
  PERIL_RATTRAPAGE_STEP,
  PROJET_WIZARD_STEPS,
  PROJET_WIZARD_STEPS_INVITE,
  type WizardStepKey,
} from '@/components/project/wizard/WizardRail';
import { AllClear } from '@/components/illustrations';
import { IconAttention, IconRafraichir } from '@/components/icons';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useAideStore } from '@/stores/useAideStore';
import { useBrouillonInviteStore } from '@/stores/useBrouillonInviteStore';
import { monumentDepuisBrouillon } from '@/lib/brouillon-invite';
import { monumentService } from '@/services/monument.service';
import { projetService } from '@/services/projet.service';
import { aideService } from '@/services/aide.service';
import { sanitizeQcmQuestions } from '@/lib/qcm';
import {
  RAISONS_KEY,
  questionnaireDeCadrage,
  raisonProposee,
  readRaisons,
  sansClesReservees,
  sansEtapeTravaux,
} from '@/constants/raisons';
import type { EtatConservation } from '@/constants/monument-options';
import { ROUTES } from '@/constants/routes';
import { C, SERIF } from '@/lib/brand';
import { toast } from 'sonner';
import type {
  Monument,
  ProjectQuestionnaireAnswers,
  QcmQuestion,
  SyntheseInvite,
  WorkType,
} from '@/types';

/**
 * Création (ou reprise) d'un PROJET de travaux sur un monument déjà décrit.
 *
 * Le monument vient de l'URL ; on ne redemande donc ni son identification ni sa
 * protection. Le parcours part directement de l'intention (« Que voulez-vous
 * faire ? »), puis des travaux, puis du questionnaire.
 *
 * Trois entrées :
 *  - sans paramètre : nouveau projet, créé par POST à la fin de l'étape travaux ;
 *  - `?projet=<id>` : « Refaire le questionnaire » d'un projet existant —
 *    intentions et travaux préremplis, PATCH au lieu de POST. Avec
 *    `&reprendre=passees`, les réponses déjà données sont conservées et seules
 *    celles restées sans réponse sont reposées (on démarre alors directement
 *    sur le questionnaire) ;
 *  - route INVITÉE (`ROUTES.PROJET_NEW_INVITE`, sans `:monumentId`) : le
 *    parcours découverte. Rien ne s'écrit en base, tout va dans le brouillon
 *    `localStorage`, le questionnaire vient de l'endpoint public, et une étape
 *    « Créer mon compte » s'insère avant le diagnostic.
 *
 * `modeInvite` se lit sur l'ABSENCE du paramètre d'URL et non sur l'état
 * d'authentification : c'est la route qui décide du parcours. Un connecté qui
 * arriverait sur la route invitée en sortira par l'écran de reprise, où sa
 * session est déjà là.
 *
 * Rattrapage : si le monument n'a jamais répondu à la question du péril (fiche
 * créée avant qu'elle n'existe), un écran la pose en préambule. Sans lui, elle
 * ne serait plus jamais posée — le wizard monument ne repasse pas. Le mode
 * invité n'en a jamais besoin : `MonumentForm` impose l'état sanitaire.
 */
export function ProjetWizardPage() {
  const navigate = useNavigate();
  const { monumentId } = useParams();
  const [searchParams] = useSearchParams();
  const existingProjetId = searchParams.get('projet');
  /**
   * « Refaire le questionnaire » → seulement les questions restées sans
   * réponse. On garde alors le questionnaire enregistré et on le TRANSMET au
   * moteur : un fait répondu n'est plus une incertitude, il ne ressort donc pas
   * dans `qcmQuestions` — la liste rendue est exactement celle des questions
   * passées. Sans ce mode, la requête ne porte que les intentions et le moteur
   * repose tout.
   */
  const reprendrePassees =
    existingProjetId !== null && searchParams.get('reprendre') === 'passees';

  const upsertProjet = useProjetStore((s) => s.upsertProjet);
  const updateMonument = useMonumentStore((s) => s.updateMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);

  // Parcours découverte : la route invitée n'a pas de `:monumentId`.
  const modeInvite = !monumentId;
  const brouillon = useBrouillonInviteStore();

  const [monument, setMonument] = useState<Monument | null>(null);
  const [projetId, setProjetId] = useState<string | null>(existingProjetId);
  const [saving, setSaving] = useState(false);
  // En invité, l'état initial vient du brouillon : un F5 en plein
  // questionnaire ne doit rien perdre.
  const [answers, setAnswers] = useState<ProjectQuestionnaireAnswers>(
    modeInvite ? brouillon.answers : {},
  );
  // Intentions de l'étape « Votre projet » (finalités du catalogue). Elles
  // préfiltrent les aides candidates AVANT la génération du questionnaire.
  const [raisons, setRaisons] = useState<string[]>(modeInvite ? brouillon.raisons : []);
  // `travaux === null` : pas de réponse ; `[]` : « Pas encore déterminé ».
  const [travaux, setTravaux] = useState<WorkType[] | null>(
    modeInvite ? brouillon.travaux : null,
  );
  // Rattrapage du péril : `null` tant qu'on ne sait pas si la question a déjà
  // été posée (fiche en cours de chargement) ou qu'elle ne l'a jamais été. En
  // invité, la réponse est dans le brouillon dès l'étape 3 du wizard monument.
  const [etatConservation, setEtatConservation] = useState<EtatConservation | null>(
    (modeInvite ? brouillon.monument?.etatConservation : null) ?? null,
  );
  const [besoinPeril, setBesoinPeril] = useState(false);
  // « Seulement les questions passées » démarre sur le questionnaire : le
  // cadrage n'est pas en cause, le repasser ferait perdre du temps.
  const [step, setStep] = useState<WizardStepKey>(() => {
    if (!modeInvite) return reprendrePassees ? 'questionnaire' : 'intention';
    // Brouillon laissé sur l'étape des travaux avant qu'elle ne soit sautée
    // pour « Faire vivre » : on reprend à l'intention, qui enchaîne d'elle-même.
    if (brouillon.etape === 'travaux' && sansEtapeTravaux(brouillon.raisons)) return 'intention';
    return brouillon.etape;
  });
  // Accroche de l'écran d'inscription. `null` tant que le diagnostic complet
  // n'a pas répondu : son absence ne bloque pas l'inscription.
  const [synthese, setSynthese] = useState<SyntheseInvite | null>(null);
  // Questionnaire du moteur d'aides : on lance un premier diagnostic déterministe
  // (intentions seules, sans réponses) dès l'étape 3 pour obtenir les questions à
  // poser (faits manquants) et le résultat de base.
  const [questions, setQuestions] = useState<QcmQuestion[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [loadedCadrageKey, setLoadedCadrageKey] = useState<string | null>(null);

  // Le questionnaire dépend du cadrage du PROJET : les intentions filtrent les
  // aides candidates, les travaux en font tomber par hard_filter. Le péril n'y
  // figure plus — il appartient au monument et ne change pas d'un projet à
  // l'autre. Revenir en arrière et changer l'un des deux régénère.
  const cleCadrage = (travauxChoisis: WorkType[] | null) =>
    [
      raisons.join('|'),
      travauxChoisis === null ? '?' : travauxChoisis.join('|'),
      // À cadrage identique, « tout refaire » et « seulement les questions
      // passées » ne rendent pas le même jeu de questions.
      reprendrePassees ? 'passees' : 'tout',
    ].join('#');
  const cadrageKey = cleCadrage(travaux);

  // « Faire vivre et ouvrir le lieu » n'est pas un chantier : l'étape des
  // travaux disparaît du rail, et l'intention enchaîne sur le questionnaire.
  const sauterTravaux = sansEtapeTravaux(raisons);
  const steps = useMemo(() => {
    const base = modeInvite
      ? PROJET_WIZARD_STEPS_INVITE
      : besoinPeril
        ? [PERIL_RATTRAPAGE_STEP, ...PROJET_WIZARD_STEPS]
        : PROJET_WIZARD_STEPS;
    // Le rail travaille par rang : retirer l'étape suffit.
    return sauterTravaux ? base.filter((s) => s.key !== 'travaux') : base;
  }, [modeInvite, besoinPeril, sauterTravaux]);

  const eyebrow = existingProjetId ? 'Questionnaire' : 'Nouveau projet';

  // Le rail montre le bien : la fiche chargée, ou le brouillon en invité.
  const monumentAffiche = modeInvite
    ? brouillon.monument
      ? monumentDepuisBrouillon(brouillon.monument)
      : null
    : monument;

  // Hors AppLayout, les stores peuvent être vides (arrivée directe par URL) :
  // on charge la fiche pour la mini-fiche du rail et le rattrapage du péril.
  useEffect(() => {
    if (!monumentId) return;
    monumentService
      .getById(monumentId)
      .then((m) => {
        setMonument(m);
        if (m.etatConservation) {
          setEtatConservation(m.etatConservation);
        } else {
          setBesoinPeril(true);
          setStep('peril');
        }
      })
      .catch(() => {
        // Non bloquant : le rail affiche simplement moins de contexte.
      });
  }, [monumentId]);

  // Questionnaire DÉJÀ ENREGISTRÉ sur le projet repris. Un ref, pas un état :
  // il ne sert qu'à ne pas effacer des réponses en réécrivant le cadrage, et
  // rien à l'écran n'en dépend. Vide pour un nouveau projet.
  const questionnaireEnregistre = useRef<ProjectQuestionnaireAnswers>({});

  // « Refaire le questionnaire » : on reprend le cadrage du projet existant.
  const prefilled = useRef(false);
  useEffect(() => {
    if (!existingProjetId) return;
    projetService
      .getById(existingProjetId)
      .then((p) => {
        // Préremplissage unique : ne jamais écraser ce que l'utilisateur vient
        // de cocher si le projet arrive en retard.
        if (prefilled.current) return;
        prefilled.current = true;
        questionnaireEnregistre.current = p.questionnaire ?? {};
        // Filtré sur ce que l'écran propose ENCORE : un projet cadré sur
        // « Optimiser la fiscalité » rouvrirait sinon sur quatre tuiles
        // décochées et un « Continuer » actif. Rien ne reste ⇒ l'étape
        // redemande l'intention.
        const previous = readRaisons(p.questionnaire).filter(raisonProposee);
        if (previous.length > 0) setRaisons(previous);
        setTravaux(p.travauxEnvisages);
        // Ne compléter que les questions passées suppose de repartir des
        // réponses existantes — sans les clés réservées, qui voyagent à part
        // et sont recomposées à l'enregistrement.
        if (reprendrePassees) setAnswers(sansClesReservees(p.questionnaire));
      })
      .catch(() => {
        toast.error('Ce projet est introuvable.');
      });
    // `reprendrePassees` vient de l'URL : il ne bouge pas pendant la vie du
    // wizard, et `prefilled` garantit de toute façon un seul préremplissage.
  }, [existingProjetId, reprendrePassees]);

  // Dès l'entrée dans le questionnaire, on calcule le diagnostic déterministe de
  // base (intentions seules, sans réponses) pour en déduire les questions à
  // poser — les faits manquants qui bloquent le plus d'aides, restreints aux
  // aides qui servent le projet déclaré. Le moteur étant pur et rapide, c'est
  // immédiat.
  useEffect(() => {
    if (step !== 'questionnaire' || loadedCadrageKey === cadrageKey || loadError) return;
    // Hors invité, le cadrage est relu SUR LE SERVEUR depuis le projet : pas
    // de projet, pas de questionnaire. En invité il n'y a pas de projet du
    // tout, tout part dans le corps de la requête.
    if (!modeInvite && !projetId) return;
    const monumentBrouillon = brouillon.monument;
    if (modeInvite && !monumentBrouillon) return;

    let cancelled = false;
    setLoadingQuestions(true);
    // Deux endpoints, une seule forme exploitée : `qcmQuestions`. Les aideIds
    // de la version invitée sont pseudonymisés, ce qui ne change rien à
    // `sanitizeQcmQuestions` ni à la résolution des éliminations côté client
    // (de simples tests d'appartenance).
    const requete = modeInvite
      ? aideService
          .runDiagnosticInvite({
            monument: monumentBrouillon!,
            travauxEnvisages: travaux ?? [],
            answers: { [RAISONS_KEY]: raisons },
          })
          .then((r) => r.qcmQuestions)
      : aideService
          .runDeterministicDiagnostic(projetId!, {
            // Les réponses connues ne partent QUE dans le mode « questions
            // passées » : ailleurs, le moteur les tiendrait pour résolues et
            // les retirerait de sa liste — l'inverse de « tout refaire ».
            ...(reprendrePassees ? answers : {}),
            [RAISONS_KEY]: raisons,
          })
          .then((r) => r.qcmQuestions);

    requete
      .then((qcmQuestions) => {
        if (cancelled) return;
        setQuestions(sanitizeQcmQuestions(qcmQuestions));
        setLoadedCadrageKey(cadrageKey);
      })
      .catch((err) => {
        console.error('Erreur diagnostic déterministe:', err);
        if (!cancelled) setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setLoadingQuestions(false);
      });
    return () => {
      cancelled = true;
    };
    // `brouillon.monument` est volontairement hors des dépendances : il ne
    // change pas pendant le wizard projet (le wizard monument est en amont),
    // et l'objet est recréé à chaque réhydratation du store.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    step,
    projetId,
    raisons,
    travaux,
    cadrageKey,
    loadedCadrageKey,
    loadError,
    modeInvite,
    reprendrePassees,
  ]);

  // Accroche chiffrée de l'étape « Votre compte » : le diagnostic complet,
  // relancé avec TOUTES les réponses.
  //
  // En effet plutôt qu'à la fin du questionnaire, parce que `synthese` est un
  // état de composant que le brouillon ne persiste pas : un F5 sur cette étape
  // — ou une reprise le lendemain, qui rouvre le wizard directement là —
  // afficherait sinon la variante sans chiffres. Non bloquant : un échec ne
  // coûte que l'accroche, l'écran garde son bouton.
  const accrocheDemandee = useRef(false);
  useEffect(() => {
    if (step !== 'inscription') {
      // Quitter puis revenir au questionnaire, répondre, revenir : la synthèse
      // doit repartir des nouvelles réponses.
      accrocheDemandee.current = false;
      return;
    }
    if (!modeInvite || accrocheDemandee.current) return;
    const monumentBrouillon = brouillon.monument;
    if (!monumentBrouillon) return;
    accrocheDemandee.current = true;

    // Le garde `useRef` SEUL, sans drapeau d'annulation au démontage : les deux
    // ensemble s'annulent sous StrictMode. Le premier passage lance l'appel,
    // son nettoyage marquerait la réponse comme périmée, et le second passage
    // ne relancerait rien (le ref est déjà posé) — l'accroche n'arriverait
    // jamais. Même idiome que `AuthCallbackPage` et `RepriseBrouillonPage` ;
    // un `setState` après démontage n'avertit plus depuis React 18.
    aideService
      .runDiagnosticInvite({
        monument: monumentBrouillon,
        travauxEnvisages: travaux ?? [],
        answers: { ...answers, [RAISONS_KEY]: raisons },
      })
      .then((r) => setSynthese(r.synthese))
      .catch((err) => console.error('Erreur accroche invité (ignorée):', err));
    // Les réponses et le cadrage sont figés à ce stade (le questionnaire est
    // derrière) : les lire une fois suffit, et les mettre en dépendances
    // relancerait l'appel à chaque frappe des étapes précédentes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modeInvite, step]);

  /**
   * Fin du parcours invité : l'écran « Votre compte ».
   *
   * Deux chemins y mènent — avoir répondu à tout, ou QUITTER le questionnaire
   * en cours de route. Dans les deux cas les réponses partent dans le
   * brouillon, et l'accroche chiffrée est recalculée par l'effet ci-dessus (le
   * brouillon ne persiste pas la synthèse).
   */
  const allerAInscription = () => {
    brouillon.setAnswers(answers);
    brouillon.setEtape('inscription');
    setStep('inscription');
  };

  /** Retour au questionnaire depuis l'écran de fin, quand on l'a quitté en
   *  cours de route : sans ça, « Quitter » serait une porte à sens unique. */
  const revenirAuQuestionnaire = () => {
    brouillon.setEtape('questionnaire');
    setStep('questionnaire');
  };

  // Rattrapage du péril : la réponse va sur le MONUMENT (elle décrit le bien).
  const handlePerilNext = async () => {
    if (!monumentId || etatConservation === null) return;
    setSaving(true);
    try {
      const updated = await monumentService.update(monumentId, {
        etatConservation,
      });
      setMonument(updated);
      updateMonument(monumentId, updated);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Erreur lors de l’enregistrement de l’état du monument"
      );
      return;
    } finally {
      setSaving(false);
    }
    setStep('intention');
  };

  // Fin de l'étape travaux : le cadrage vit sur le PROJET — les travaux, que le
  // moteur relit côté serveur pour ses hard_filters, et la finalité, qui écarte
  // les aides d'un autre métier. On le persiste donc AVANT de générer le
  // questionnaire. En cas d'échec on reste sur l'écran : partir avec des
  // travaux non enregistrés donnerait un diagnostic calculé sur l'état
  // précédent, sans que rien ne le signale.
  //
  // `travauxChoisis` : l'état par défaut, ou `[]` quand l'étape est sautée
  // depuis l'intention — le `setTravaux` qui l'accompagne n'est pas encore
  // visible dans cette fermeture.
  const handleTravauxNext = async (travauxChoisis: WorkType[] | null = travaux) => {
    if (travauxChoisis === null) return;
    const nouvelleCle = cleCadrage(travauxChoisis);
    // En invité, rien à persister : le cadrage va dans le brouillon, et le
    // questionnaire est calculé à partir de ce qu'on envoie dans le corps.
    if (modeInvite) {
      brouillon.setCadrage(raisons, travauxChoisis);
      brouillon.setEtape('questionnaire');
      if (loadedCadrageKey !== null && loadedCadrageKey !== nouvelleCle) {
        setAnswers({});
        setQuestions([]);
        brouillon.setAnswers({});
      }
      setStep('questionnaire');
      return;
    }
    if (!monumentId) return;
    setSaving(true);
    // Le cadrage part ENTIER : les travaux ET la finalité. Cette dernière est
    // ce qui écarte du diagnostic les aides d'un autre métier (`hors_projet`
    // côté serveur) ; ne l'écrire qu'à la sortie du questionnaire laissait la
    // page d'un projet quitté en route lister « Hauts-de-France en fête » à
    // qui venait de cocher « Restaurer ou faire des travaux ».
    const questionnaire = questionnaireDeCadrage(questionnaireEnregistre.current, raisons);
    try {
      const projet = projetId
        ? await projetService.update(projetId, {
            travauxEnvisages: travauxChoisis,
            questionnaire,
          })
        : await projetService.create(monumentId, {
            travauxEnvisages: travauxChoisis,
            questionnaire,
          });
      upsertProjet(projet);
      setProjetId(projet.id);
      questionnaireEnregistre.current = projet.questionnaire;
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Erreur lors de l’enregistrement de votre projet"
      );
      return;
    } finally {
      setSaving(false);
    }
    // Changer le cadrage périme les réponses déjà données (leurs questions
    // peuvent disparaître) — on repart d'un questionnaire propre.
    if (loadedCadrageKey !== null && loadedCadrageKey !== nouvelleCle) {
      setAnswers({});
      setQuestions([]);
    }
    setStep('questionnaire');
  };

  // Questionnaire → page du projet : on persiste réponses ET intentions sur le
  // projet (la page recalcule le même diagnostic à partir de là), puis on amorce
  // le store pour éviter un écran vide.
  const handleQuestionnaireNext = async () => {
    // En invité, la fin du questionnaire mène à l'inscription, pas au
    // diagnostic : c'est là que le compte se crée, et c'est l'écran de reprise
    // qui écrira monument et projet.
    if (modeInvite) {
      allerAInscription();
      return;
    }

    if (!projetId) return;
    const questionnaire: ProjectQuestionnaireAnswers = { ...answers, [RAISONS_KEY]: raisons };
    setSaving(true);
    setStep('diagnostic');
    try {
      upsertProjet(await projetService.update(projetId, { questionnaire }));
    } catch (err) {
      console.error('Erreur enregistrement questionnaire (ignorée):', err);
    }
    try {
      setDiagnostic(projetId, await aideService.runProjectDiagnostic(projetId, questionnaire));
    } catch (err) {
      console.error('Erreur diagnostic:', err);
    }
    // Leave `saving` true through the navigation — the component unmounts.
    navigate(ROUTES.PROJET_DETAIL(projetId));
  };

  // Quitter : le projet n'est créé qu'à la fin de l'étape travaux, et les
  // réponses au questionnaire ne sont écrites qu'à la toute fin. En invité, il
  // n'y a pas d'espace où retourner — la connexion, donc, et sans alarmer : le
  // brouillon reste sur l'appareil.
  const exitTo = modeInvite
    ? '/login'
    : projetId
      ? ROUTES.PROJET_DETAIL(projetId)
      : monumentId
        ? `${ROUTES.MONUMENT_DETAIL(monumentId)}?tab=projets`
        : ROUTES.MONUMENTS;

  // Quitter le questionnaire en invité ne fait pas sortir : on montre l'écran
  // de fin avec ce que les réponses déjà données ont trouvé.
  const quitterVersInscription = modeInvite && step === 'questionnaire';

  // Arrivée directe sur la route invitée sans brouillon (favori, lien
  // partagé) : le prérequis est le monument, on renvoie le décrire.
  if (modeInvite && !brouillon.monument) {
    return <Navigate to={ROUTES.MONUMENT_NEW} replace />;
  }

  return (
    <WizardShell
      steps={steps}
      step={step}
      monument={monumentAffiche}
      // Rien à confirmer quand quitter mène à l'écran de fin : les réponses
      // sont dans le brouillon et le questionnaire reste reprenable.
      confirmQuit={
        !quitterVersInscription && step === 'questionnaire' && Object.keys(answers).length > 0
      }
      quitDisabled={step === 'diagnostic'}
      exitTo={exitTo}
      onQuit={quitterVersInscription ? allerAInscription : undefined}
      quitMessage={
        modeInvite
          ? 'Votre brouillon reste sur cet appareil : vous pourrez reprendre ici.'
          : undefined
      }
      // L'étape « Votre compte » est entièrement centrée sur son chiffre : le
      // trèfle en filigrane venait s'y poser juste à côté.
      sansFiligrane={step === 'inscription'}
    >
      {step === 'peril' && (
        <PerilStep
          eyebrow={eyebrow}
          value={etatConservation}
          onChange={setEtatConservation}
          onNext={handlePerilNext}
          saving={saving}
        />
      )}

      {step === 'intention' && (
        <ProjectIntentStep
          value={raisons}
          onChange={setRaisons}
          onNext={() => {
            // Pas de chantier : le projet est cadré sur « Pas encore
            // déterminé » et l'on passe directement au questionnaire (création
            // ou mise à jour du projet comprise, comme après l'étape travaux).
            if (sauterTravaux) {
              setTravaux([]);
              void handleTravauxNext([]);
              return;
            }
            // En invité, les intentions vont dans le brouillon dès maintenant :
            // un F5 à l'étape des travaux ne doit pas ramener à une page
            // d'intentions vide. Les travaux, eux, sont encore inconnus.
            if (modeInvite) {
              brouillon.setCadrage(raisons, travaux);
              brouillon.setEtape('travaux');
            }
            setStep('travaux');
          }}
          retake={!!existingProjetId}
        />
      )}

      {step === 'travaux' && (
        <ProjectTravauxStep
          eyebrow={eyebrow}
          value={travaux}
          onChange={setTravaux}
          onNext={() => void handleTravauxNext()}
          onBack={() => setStep('intention')}
          saving={saving}
        />
      )}

      {step === 'questionnaire' && (
        <div className="space-y-5">
          {/* Pendant le questionnaire lui-même, pas d'en-tête : la question est
              la vedette et tout doit tenir à l'écran — le rail situe déjà
              l'étape. L'en-tête ne sert que les états d'attente/erreur/vide. */}
          {(loadingQuestions || loadError || questions.length === 0) && (
            <div className="space-y-1.5">
              <div
                className="text-[12px] font-semibold uppercase tracking-[0.2em]"
                style={{ color: C.orange }}
              >
                {eyebrow}
              </div>
              <h1
                className="text-[clamp(1.4rem,3vw,1.8rem)] leading-tight"
                style={{ fontFamily: SERIF, color: C.ink }}
              >
                Précisons votre projet
              </h1>
              <p className="max-w-lg text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
                Vos réponses affinent la liste des aides. Répondez librement&nbsp;—
                passer une question est tout à fait valable.
              </p>
            </div>
          )}

          {loadingQuestions ? (
            <div
              className="flex items-center gap-3 py-10 text-[14px]"
              style={{ color: C.grayMuted }}
            >
              <Loader2 className="h-4 w-4 animate-spin" style={{ color: C.blueLight }} />
              Analyse de votre monument…
            </div>
          ) : loadError ? (
            <div
              className="flex flex-col items-start gap-4 rounded-2xl border p-6"
              style={{ borderColor: C.border, background: C.card }}
            >
              <span
                className="flex h-11 w-11 items-center justify-center rounded-xl"
                style={{ background: 'var(--destructive-muted)', color: 'var(--destructive)' }}
              >
                <IconAttention className="h-5 w-5" />
              </span>
              <div>
                <p className="text-[15px] font-semibold" style={{ color: C.ink }}>
                  Le questionnaire n&rsquo;a pas pu être chargé.
                </p>
                <p className="mt-1 text-[14px]" style={{ color: C.grayFg }}>
                  {modeInvite
                    ? 'Vérifiez votre connexion puis réessayez — vos réponses restent sur cet appareil.'
                    : 'Vérifiez votre connexion puis réessayez — votre projet est bien enregistré.'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setLoadError(false)}
                className="inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-[14px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)]"
                style={{ background: C.orange }}
              >
                <IconRafraichir className="h-4 w-4" />
                Réessayer
              </button>
            </div>
          ) : questions.length === 0 ? (
            <div className="flex flex-col items-center gap-5 py-8 text-center">
              <AllClear />
              <p
                className="max-w-md text-[15px] leading-relaxed"
                style={{ color: C.grayFg }}
              >
                Aucune précision supplémentaire n&rsquo;est nécessaire pour ce projet.
                Lancez le diagnostic pour découvrir les aides mobilisables.
              </p>
              <button
                type="button"
                disabled={saving}
                onClick={handleQuestionnaireNext}
                className="group inline-flex items-center gap-2 rounded-2xl px-7 py-3.5 text-[16px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)] disabled:opacity-60"
                style={{ background: C.orange }}
              >
                {modeInvite ? 'Découvrir mes financements' : 'Voir les aides'}
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </button>
            </div>
          ) : (
            <ProjectQuestionnaire
              questions={questions}
              value={answers}
              // En invité, chaque réponse part aussi dans le brouillon : un F5
              // au milieu du questionnaire ne perd rien.
              onChange={(a) => {
                setAnswers(a);
                if (modeInvite) brouillon.setAnswers(a);
              }}
              onComplete={handleQuestionnaireNext}
              submitting={saving}
              completeLabel={modeInvite ? 'Découvrir mes financements' : undefined}
            />
          )}
        </div>
      )}

      {step === 'inscription' && (
        <InscriptionStep synthese={synthese} onRetour={revenirAuQuestionnaire} />
      )}

      {step === 'diagnostic' && <DiagnosticLoader />}
    </WizardShell>
  );
}
