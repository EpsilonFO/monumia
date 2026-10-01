import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { useParams, Link, useNavigate, useSearchParams, Navigate } from 'react-router';
import { ChevronLeft, Loader2 } from 'lucide-react';
import { IconAide, IconDossier, IconSupprimer } from '@/components/icons';
import { Onglets, type Onglet } from '@/components/shared/ecrans/Onglets';
import { Picto, type NomPicto } from '@/components/shared/ecrans/Picto';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { EmptyState } from '@/components/shared/EmptyState';
import { AideCarte } from '@/components/aide/AideCarte';
import './projet.css';
import { AideFamilleBar } from '@/components/aide/AideFamilleBar';
import { AideFiltreBar } from '@/components/aide/AideFiltreBar';
import { DossierCard } from '@/components/dossier/DossierCard';
import { OngletDocuments } from '@/components/document/OngletDocuments';
import { projetTitre } from '@/lib/projet-titre';
import { TeamPanel } from '@/components/sharing/TeamPanel';
import { projectPermissions } from '@/lib/project-permissions';
import { useOffreMonument, useOffreMonumentConnue } from '@/hooks/useOffre';
import { estOffreGratuite } from '@/lib/offres';
import { montantAide, titreAide } from '@/lib/fiche-aide';
import { PaywallOverlay } from '@/components/shared/Paywall';
import { formatCurrency } from '@/lib/format-utils';
import { ProjetSummaryBar } from '@/components/projet/ProjetSummaryBar';
import { AidesTabSkeleton, ProjectDetailSkeleton } from '@/components/skeletons';
import { ProjectEcheancier } from '@/components/project/ProjectEcheancier';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { monumentService } from '@/services/monument.service';
import { projetService } from '@/services/projet.service';
import { documentService } from '@/services/document.service';
import { projetSharingService } from '@/services/sharing.service';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { suiviService } from '@/services/suivi.service';
import { resolveLegacyProjetId } from '@/lib/legacy-id';
import { AIDE_FILTRES, filtresDisponibles, filtrerAides, type AideFiltreKey } from '@/lib/aide-filtres';
import { famillesDisponibles, filtrerParFamille } from '@/lib/aide-familles';
import { computeProjectStats, mergeProjectDeadlines } from '@/lib/project-stats';
import { questionsPourAide } from '@/lib/diagnostic-bilan';
import { sanitizeQcmQuestions } from '@/lib/qcm';
import { daysUntil } from '@/lib/date-utils';
import { C, SERIF } from '@/lib/brand';
import { getDisponibilite } from '@/components/aide/eligibility-status';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import { isAccessLostError } from '@/lib/api-error';
import { BoutonRetour } from '@/components/shared/ecrans/BoutonRetour';
import type {
  AideDiagnosticResult, AideMatchResult, Document, ProjectInvitation, ProjectMember,
  ProjectQuestionnaireAnswers,
} from '@/types';

/** Tri : aides avec une échéance à venir d'abord (de la plus proche à la plus lointaine),
 *  puis les permanentes / sans date / échéances dépassées. */
function byDeadline(a: AideMatchResult, b: AideMatchResult): number {
  const key = (m: AideMatchResult) => {
    if (m.aide.permanent || !m.aide.dateLimite) return Infinity;
    const d = daysUntil(m.aide.dateLimite);
    return d < 0 ? Infinity : d;
  };
  return key(a) - key(b);
}

/** Rang des statuts dans « Disponibles bientôt », qui les mélange : les aides
 *  déjà acquises sur le fond remontent avant celles qui demandent encore une
 *  démarche ou une vérification. */
const BIENTOT_RANK: Record<string, number> = { eligible: 0, atteignable: 1, potentiel: 2 };

/** Tri des « disponibles bientôt » : statut, puis la prochaine fenêtre à
 *  s'ouvrir. `byDeadline` ne convient pas ici — ces aides ont justement une
 *  date limite passée ou absente, et c'est l'ouverture qui les départage. */
function byBientot(a: AideMatchResult, b: AideMatchResult): number {
  const rank = (m: AideMatchResult) => BIENTOT_RANK[m.statut ?? ''] ?? 3;
  const ouverture = (m: AideMatchResult) =>
    m.aide.dateOuverture ? new Date(m.aide.dateOuverture).getTime() : Infinity;
  return (
    rank(a) - rank(b)
    || ouverture(a) - ouverture(b)
    || a.aide.nomCourt.localeCompare(b.aide.nomCourt, 'fr')
  );
}

/** Au-delà, « À confirmer » se déplie sur demande : c'est la section la plus
 *  longue, et ses premières cartes sont les plus proches d'un verdict. */
const A_CONFIRMER_VISIBLES = 12;

/** Une section d'aides de la maquette : pastille ronde, titre serif, phrase
 *  d'explication, puis la grille de cartes. */
function Groupe({
  ton,
  picto,
  titre,
  sous,
  children,
}: {
  ton: 'ok' | 'ck' | 'db' | 'bt';
  picto: NomPicto;
  titre: string;
  sous: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grp">
      <div className="grp-h">
        <span className={`gi ${ton}`}>
          <Picto nom={picto} />
        </span>
        <h3>{titre}</h3>
      </div>
      <p className="grp-sub">{sous}</p>
      {children}
    </div>
  );
}

/**
 * Page d'un PROJET de travaux : ses aides et ses dossiers.
 *
 * Le monument parent est chargé pour l'en-tête, le fil d'Ariane et les
 * permissions — l'équipe et le paywall vivent sur lui, jamais sur le projet.
 *
 * L'URL `/app/projets/:id` désignait un MONUMENT avant l'inversion de
 * hiérarchie : les vieux liens (emails, notifications) en portent encore. On les
 * résout à l'exécution — le projet d'abord, le monument en repli.
 */
export function ProjetDetailPage() {
  const { projetId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const projet = useProjetStore((s) => s.projets.find((p) => p.id === projetId));
  const upsertProjet = useProjetStore((s) => s.upsertProjet);
  const deleteProjetLocal = useProjetStore((s) => s.deleteProjet);

  const monumentId = projet?.monumentId;
  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId));
  const upsertMonument = useMonumentStore((s) => s.upsertMonument);

  const allDossiers = useDossierStore((s) => s.dossiers);
  const dossiers = useMemo(
    // Repli legacy : les dossiers d'avant l'inversion peuvent arriver sans
    // `projetId` d'un client non rechargé. On les rattache alors au monument,
    // plutôt que de les faire disparaître de la vue.
    () => allDossiers.filter((d) => (d.projetId ? d.projetId === projetId : d.monumentId === monumentId)),
    [allDossiers, projetId, monumentId],
  );

  // Chargé pour que les cartes dossier affichent leur avancement (lecture via le store).
  const suiviLoaded = useSuiviStore((s) => (projetId ? s.loadedProjets[projetId] : false));

  const diagnosticsByProjet = useAideStore((s) => s.diagnosticsByProjet);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);
  const diagnostic = projetId ? diagnosticsByProjet[projetId] ?? null : null;

  // Résolution de l'id : 'projet' | 'monument' | 'introuvable', ou null tant
  // que les deux tentatives ne sont pas retombées.
  const [resolution, setResolution] = useState<'projet' | 'monument' | 'introuvable' | null>(null);
  const [running, setRunning] = useState(false);
  const [showNonEligibles, setShowNonEligibles] = useState(false);
  const [toutAConfirmer, setToutAConfirmer] = useState(false);
  const [confirmRefaireOpen, setConfirmRefaireOpen] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // Filtre par financeur, appliqué à TOUTES les sections d'aides de la page.
  const [filtreKey, setFiltreKey] = useState<AideFiltreKey>('toutes');
  // Facette de FAMILLE, second axe de tri (le thème, là où le filtre ci-dessus
  // porte sur le financeur). `null` = aucune facette, tout passe — y compris
  // les aides sans famille, qu'aucune facette ne compte.
  const [familleFacette, setFamilleFacette] = useState<string | null>(null);

  // Documents et équipe DU CHANTIER : deux périmètres propres au projet, que
  // l'équipe du monument voit en plus des siens, et qu'un collaborateur invité
  // ici est le seul à voir avec elle.
  const [projetDocuments, setProjetDocuments] = useState<Document[]>([]);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [invitations, setInvitations] = useState<ProjectInvitation[]>([]);

  const tabParam = searchParams.get('tab');
  // Les droits se lisent sur le PROJET : un collaborateur invité sur le seul
  // chantier n'a aucun rôle sur le monument, mais bien un rôle ici.
  const perms = projectPermissions(projet?.myRole ?? null);
  // L'onglet « Aides » est réservé au chef de projet et à son adjoint. Pour un
  // collaborateur, on retombe sur « Dossiers ».
  //
  // Pas de repli tant que le rôle est inconnu : un projet relu du cache local
  // n'a pas de `myRole` (cf. `projetPourLeCache`), et ce n'est pas un rôle nul.
  // Retomber sur « Dossiers » pour revenir sur « Aides » à la réponse de
  // `GET /projets/{id}` ferait sauter la page.
  const canAccessAides = perms.canAccessAides || !!projet?.depuisLeCache;
  // L'offre qui gouverne le BIEN, et non le compte : un collaborateur invité
  // par un client abonné voit le même calendrier que son client. Elle décide
  // ici de trois choses — l'échéancier, les aides encore à venir, et la
  // suppression du chantier.
  const offre = useOffreMonument(monumentId);
  const offreConnue = useOffreMonumentConnue(monumentId);
  // Travailler à plusieurs est un service de l'offre Veille. L'onglet Équipe
  // reste VISIBLE au gratuit — c'est une porte, pas un vide — mais il mène aux
  // tarifs plutôt qu'à un formulaire que le serveur refuserait (402).
  //
  // Il s'ouvre quand même si une équipe existe déjà, et ce n'est pas une
  // politesse : après une résiliation, les collaborateurs gardent leur accès.
  // Renvoyer alors vers les tarifs le rendrait irrévocable. On laisse donc
  // gérer ce qui est là, sans pouvoir y ajouter (cf. TeamPanel).
  const equipeAccessible = offre.equipe || members.length > 1 || invitations.length > 0;
  const requestedTab =
    tabParam === 'dossiers' || tabParam === 'documents' || tabParam === 'equipe'
      ? tabParam
      : 'aides';
  // Deux replis vers « Dossiers », le seul onglet toujours ouvert : l'onglet
  // Aides est réservé au chef de projet et à son adjoint, et l'onglet Équipe à
  // l'offre Veille. Arriver par un lien gardé en favori affiche le projet, là
  // où un clic délibéré mène aux tarifs : on n'éjecte pas quelqu'un qui voulait
  // simplement ouvrir son chantier.
  const activeTab =
    (requestedTab === 'aides' && !canAccessAides)
      ? 'dossiers'
      : requestedTab;
  const handleTabChange = useCallback((value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', value);
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  // Chargement du projet, avec la résolution des vieux liens en repli. Rafraîchi
  // au montage : revenir sur la page doit refléter les changements des autres
  // membres, sans recharger le navigateur.
  useEffect(() => {
    if (!projetId) return;
    let cancelled = false;
    projetService
      .getById(projetId)
      .then((p) => {
        if (cancelled) return;
        upsertProjet(p);
        setResolution('projet');
      })
      .catch(async () => {
        // 404 sur le projet : l'id désigne peut-être un MONUMENT (vieux lien).
        const estMonument = await monumentService
          .getById(projetId)
          .then(() => true)
          .catch(() => false);
        if (cancelled) return;
        setResolution(resolveLegacyProjetId(false, estMonument).kind);
      });
    return () => { cancelled = true; };
  }, [projetId, upsertProjet]);

  // Monument parent : entête, fil d'Ariane, rôle et paywall. Relu aussi quand il
  // vient du cache local, qui ne garde pas son offre : sans cela, l'onglet Aides
  // attendait que `GET /dashboard`, la plus lente des requêtes, la rapporte — et
  // restait en squelette pour de bon si elle échouait.
  const monumentARelire = !monument || !!monument.depuisLeCache;
  useEffect(() => {
    if (!monumentId || !monumentARelire) return;
    monumentService.getById(monumentId).then(upsertMonument).catch(console.error);
  }, [monumentId, monumentARelire, upsertMonument]);

  // Diagnostic déterministe : recalculé à l'arrivée (et quand les réponses du
  // questionnaire changent). Le moteur est pur et rapide — pas de persistance ;
  // les réponses (projet.questionnaire) se résolvent côté client via
  // eliminationsParOption.
  const questionnaireKey = projet ? JSON.stringify(projet.questionnaire ?? {}) : '';
  // Le projet dont le diagnostic est RETOMBÉ (réussi ou en erreur). On mémorise
  // la tentative plutôt qu'un simple booléen « en cours » : posé par l'effet,
  // ce booléen serait encore faux au premier rendu qui suit l'arrivée du
  // projet, et l'invitation à lancer le moteur clignoterait avant le squelette.
  const [diagnosticTente, setDiagnosticTente] = useState<string | null>(null);
  // Le diagnostic est le plus lourd des appels de la page : il part TOUT DE
  // SUITE, sans attendre `GET /projets/{id}`. Sans projet en main, le serveur
  // relit lui-même le questionnaire enregistré, et le résultat dit lequel
  // (`qcmAnswers`). Quand le projet arrive ensuite, on ne relance le moteur que
  // si ses réponses diffèrent de celles-là — sinon la page paierait deux fois
  // le même diagnostic à chaque ouverture.
  const diagnosticEnregistre = useRef<{
    projetId: string;
    promesse: Promise<AideDiagnosticResult | null>;
  } | null>(null);
  useEffect(() => {
    if (!projetId) return;
    let cancelled = false;
    let promesse: Promise<AideDiagnosticResult | null>;
    const enVol =
      diagnosticEnregistre.current?.projetId === projetId ? diagnosticEnregistre.current.promesse : null;
    if (!questionnaireKey) {
      promesse = aideService.runProjectDiagnosticEnregistre(projetId);
      // Un échec se relance avec les réponses du projet, une fois qu'il est là.
      diagnosticEnregistre.current = { projetId, promesse: promesse.catch(() => null) };
    } else {
      const answers: ProjectQuestionnaireAnswers = JSON.parse(questionnaireKey);
      const relancer = () => aideService.runProjectDiagnostic(projetId, answers);
      diagnosticEnregistre.current = null;
      promesse = enVol
        ? enVol.then((r) =>
            r && JSON.stringify(r.qcmAnswers ?? {}) === questionnaireKey ? r : relancer(),
          )
        : relancer();
    }
    promesse
      .then((result) => { if (!cancelled && result) setDiagnostic(projetId, result); })
      .catch(console.error)
      .finally(() => { if (!cancelled) setDiagnosticTente(projetId); });
    return () => { cancelled = true; };
  }, [projetId, questionnaireKey, setDiagnostic]);

  useEffect(() => { dossierService.fetchAll().catch(console.error); }, []);
  useEffect(() => {
    if (projetId && !suiviLoaded) suiviService.fetchByProjet(projetId).catch(console.error);
  }, [projetId, suiviLoaded]);

  const reloadProjetDocuments = useCallback(() => {
    if (!projetId) return;
    documentService.getAll({ projetId }).then(setProjetDocuments).catch(() => {});
  }, [projetId]);
  useEffect(() => { reloadProjetDocuments(); }, [reloadProjetDocuments]);

  const reloadMembers = useCallback(() => {
    if (!projetId) return;
    projetSharingService
      .getMembers(projetId)
      .then((data) => {
        setMembers(data.members);
        setInvitations(data.invitations);
      })
      .catch((err) => {
        // Perte d'accès définitive (projet supprimé, retrait de l'équipe) : on
        // bascule sur « introuvable ». Une erreur transitoire ne touche à rien.
        if (isAccessLostError(err)) setResolution('introuvable');
      });
  }, [projetId]);
  useEffect(() => { reloadMembers(); }, [reloadMembers]);

  const uploaderNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const m of members) map[m.userId] = `${m.prenom} ${m.nom}`.trim();
    return map;
  }, [members]);

  const stats = useMemo(
    () => (projet ? computeProjectStats(projet, diagnostic, dossiers) : null),
    [projet, diagnostic, dossiers],
  );
  const deadlines = useMemo(() => mergeProjectDeadlines(diagnostic, dossiers), [diagnostic, dossiers]);

  const handleRunDiagnostic = useCallback(async () => {
    if (!projetId) return;
    setRunning(true);
    try {
      setDiagnostic(projetId, await aideService.runProjectDiagnostic(projetId, projet?.questionnaire ?? {}));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors du diagnostic');
    } finally {
      setRunning(false);
    }
  }, [projetId, setDiagnostic, projet?.questionnaire]);

  // « Refaire le questionnaire », deux façons :
  //
  //  - 'tout'    : on repart d'un questionnaire vierge (les réponses actuelles
  //                sont remplacées) — le comportement historique.
  //  - 'passees' : on garde les réponses données et on ne repose que les
  //                questions restées sans réponse. C'est le cas courant : on a
  //                passé trois questions faute de savoir, on revient avec la
  //                réponse. Tout resaisir pour trois questions décourage.
  const confirmRefaire = useCallback(
    (mode: 'tout' | 'passees') => {
      if (!projetId || !monumentId) return;
      setConfirmRefaireOpen(false);
      const base = `${ROUTES.PROJET_NEW(monumentId)}?projet=${projetId}`;
      navigate(mode === 'passees' ? `${base}&reprendre=passees` : base);
    },
    [projetId, monumentId, navigate],
  );

  // Les questions que le moteur pose ENCORE sont exactement celles restées sans
  // réponse : un fait répondu n'est plus une incertitude, il sort donc de
  // `qcmQuestions`. Ce compteur dit s'il y a matière à ne refaire que celles-là.
  const questionsRestantes = diagnostic?.qcmQuestions?.length ?? 0;

  // Les questions du diagnostic, dont les cartes comptent celles qui restent
  // par aide (elles se posent sur la fiche). Mémorisées sur l'objet
  // `diagnostic` : sans ça, chaque rendu rendrait un nouveau tableau et ferait
  // remonter les cartes.
  const questionsDiagnostic = useMemo(
    () => sanitizeQcmQuestions(diagnostic?.qcmQuestions),
    [diagnostic],
  );

  /** Renommage en place depuis l'en-tête. On relaie l'erreur : l'en-tête garde
   *  alors la saisie et reste en édition. */
  const handleRenommerProjet = useCallback(
    async (titre: string) => {
      if (!projetId) return;
      try {
        upsertProjet(await projetService.update(projetId, { titre }));
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Erreur lors du renommage');
        throw err;
      }
    },
    [projetId, upsertProjet],
  );

  const handleDeleteProjet = useCallback(async () => {
    if (!projetId || !monumentId) return;
    setConfirmDeleteOpen(false);
    setDeleting(true);
    try {
      await projetService.delete(projetId);
      deleteProjetLocal(projetId);
      toast.success('Projet supprimé');
      navigate(`${ROUTES.MONUMENT_DETAIL(monumentId)}?tab=projets`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression');
      setDeleting(false);
    }
  }, [projetId, monumentId, deleteProjetLocal, navigate]);

  // Vieux lien portant un id de monument : on redirige sans rien afficher.
  if (resolution === 'monument' && projetId) {
    return <Navigate to={ROUTES.MONUMENT_DETAIL(projetId)} replace />;
  }

  if (resolution === 'introuvable') {
    return (
      <div className="space-y-4">
        <h1 className="text-[23px]" style={{ fontFamily: SERIF, color: C.ink }}>Projet introuvable</h1>
        <p className="text-[16px] text-muted-foreground">Ce projet n'existe pas ou a été supprimé.</p>
        <Link to={ROUTES.MONUMENTS} className="inline-flex items-center gap-1.5 text-[15px] font-medium" style={{ color: C.blue }}>
          <ChevronLeft className="h-3.5 w-3.5" /> Retour à mes monuments
        </Link>
      </div>
    );
  }

  if (!projet || !monument || !stats) return <ProjectDetailSkeleton />;

  // Le moteur tourne : on dessine le gabarit de l'onglet plutôt que l'invitation
  // à le lancer, qui donnait à croire qu'il restait un geste à faire. Le bloc
  // « Lancer le moteur » ne reste que pour une tentative retombée sans résultat.
  //
  // Même gabarit tant que l'offre du monument n'est pas connue (monument relu
  // du cache local) : l'échéancier et les aides « bientôt » se floutent ou non
  // selon elle, et trancher sur l'offre gratuite par défaut poserait un paywall
  // qu'un abonné verrait clignoter à chaque rechargement.
  const chargementDiagnostic = (!diagnostic && diagnosticTente !== projetId) || !offreConnue;

  // Une aide déjà passée en dossier disparaît de la liste des aides : elle vit
  // désormais dans l'onglet « Dossiers ». Supprimer le dossier l'y fait réapparaître.
  const dossierAideIds = new Set(dossiers.map((d) => d.aideId));
  const toutesEligibles = [...(diagnostic?.aidesEligibles ?? [])].filter((m) => !dossierAideIds.has(m.aide.id)).sort(byDeadline);
  // « À confirmer » se trie sur la DISTANCE À UN VERDICT, pas sur l'échéance :
  // une aide qu'une seule question sépare d'une réponse vaut mieux en tête
  // qu'une aide qui en demande cinq. À égalité, l'échéance départage.
  const reste = (m: AideMatchResult) =>
    questionsPourAide(m.aide.id, questionsDiagnostic, projet.questionnaire ?? {}).length;
  const toutesPotentiels = [...(diagnostic?.aidesPotentiellementEligibles ?? [])]
    .filter((m) => !dossierAideIds.has(m.aide.id))
    .sort((a, b) => reste(a) - reste(b) || byDeadline(a, b));
  // « À débloquer » : ordre du backend conservé (enjeu décroissant) — c'est le
  // montant en jeu qui décide si la démarche vaut la peine, pas l'échéance.
  const toutesAtteignables = (diagnostic?.aidesAtteignables ?? []).filter((m) => !dossierAideIds.has(m.aide.id));
  // Non éligibles : on ne montre QUE les aides écartées par une réponse au
  // questionnaire. Celles qu'un filtre automatique élimine (région, protection,
  // type de propriétaire… déduits de la fiche) n'apprennent rien à personne et
  // noyaient la liste. Elles restent dans la réponse du backend : la page de
  // détail d'une aide s'y sert encore par lien direct.
  const toutesNonEligibles = (diagnostic?.aidesNonEligibles ?? []).filter(
    (m) => m.elimineParReponse && !dossierAideIds.has(m.aide.id),
  );

  // Le filtre par financeur se compte sur les aides À PORTÉE, pas sur les non
  // éligibles : ce qu'on cherche à départager, ce sont les pistes vivantes.
  const filtreOptions = filtresDisponibles(
    [...toutesEligibles, ...toutesAtteignables, ...toutesPotentiels],
    filtreKey,
  );
  const filtre = AIDE_FILTRES.find((f) => f.key === filtreKey) ?? AIDE_FILTRES[0];
  // Les facettes de famille se comptent sur les mêmes aides que les filtres de
  // financeur, et APRÈS eux : les deux axes se cumulent, et une facette qui
  // annonce 4 aides doit en laisser 4 avec le financeur en cours.
  const familleOptions = famillesDisponibles(
    filtrerAides([...toutesEligibles, ...toutesAtteignables, ...toutesPotentiels], filtre),
    familleFacette,
  );
  const parFiltres = (aides: typeof toutesEligibles) =>
    filtrerParFamille(filtrerAides(aides, filtre), familleFacette);
  const eligibles = parFiltres(toutesEligibles);
  const potentiels = parFiltres(toutesPotentiels);
  const atteignables = parFiltres(toutesAtteignables);
  const nonEligibles = parFiltres(toutesNonEligibles);

  // La fenêtre de candidature prime sur le statut : quelle que soit l'avancée du
  // dossier sur le fond, une aide qu'on ne peut pas déposer aujourd'hui part en
  // « Disponibles bientôt », où sa pastille continue de dire où elle en est. Les
  // non éligibles restent à part : le calendrier ne rattrape pas un critère qui
  // ne colle pas.
  const ouvertAujourdhui = (m: AideMatchResult) => getDisponibilite(m) === 'maintenant';
  const eligiblesMaintenant = eligibles.filter(ouvertAujourdhui);
  const atteignablesMaintenant = atteignables.filter(ouvertAujourdhui);
  const potentielsMaintenant = potentiels.filter(ouvertAujourdhui);
  const bientot = [...eligibles, ...atteignables, ...potentiels]
    .filter((m) => !ouvertAujourdhui(m))
    .sort(byBientot);

  // Les cartes sont celles de l'index des fiches de la maquette, en grille qui
  // se remplit d'elle-même (`.fa.grid`, colonnes de 320 px au moins).
  // Les cartes ne portent plus de verrou : le paywall des aides à venir vit au
  // niveau de la SECTION, qui les floute et les rend inertes d'un bloc. Un
  // cadenas par carte, derrière ce flou, n'aurait fait que brouiller l'aperçu.
  // Le montant des cartes, lui, ne s'affiche qu'à partir de Veille — c'est
  // l'offre du MONUMENT qui décide, comme pour ses projets et son calendrier.
  // Rien n'est retenu pour autant : montant, taux et échéance restent sur la
  // fiche de l'aide, qui est gratuite.
  const chiffresAides = !estOffreGratuite(offre);
  const renderAideList = (list: AideMatchResult[]) => (
    <div className="cartes">
      {list.map((match) => (
        <AideCarte
          key={match.aide.id}
          match={match}
          projetId={projet.id}
          showMontant={chiffresAides}
          questions={questionsDiagnostic}
          answers={projet.questionnaire ?? {}}
        />
      ))}
    </div>
  );

  const aidesAPortee = [...toutesEligibles, ...toutesAtteignables, ...toutesPotentiels];
  // Enjeu chiffré du paywall : la somme des plafonds des SEULES aides encore à
  // venir. Le montant total du diagnostic ne dirait rien de ce que l'offre
  // débloque — l'essentiel en vient d'aides déjà consultables.
  //
  // Ces chiffres sont RÉELS et vont dans la carte, devant le flou : le montant
  // et le nombre sont l'argumentaire, les laisser derrière les rendrait
  // illisibles. Ce qui reste derrière, ce sont les vrais noms des aides, floutés
  // plus fort qu'ailleurs (`flou`) pour ne pas se lire d'un coup d'œil.
  const montantBientot = bientot.reduce((sum, m) => sum + (m.aide.montantMax ?? 0), 0);
  const chiffresBientot = [
    ...(montantBientot > 0
      ? [{ valeur: formatCurrency(montantBientot), libelle: 'à venir, au mieux' }]
      : []),
    {
      valeur: String(bientot.length),
      libelle: `aide${bientot.length > 1 ? 's' : ''} à venir`,
    },
  ];

  const dossierNames = Object.fromEntries(allDossiers.map((d) => [d.id, d.titre]));


  // Monté une seule fois, que l'offre l'ouvre ou non : c'est le même panneau,
  // seul son habillage change.
  const equipePanel = (
    <TeamPanel
      scope="projet"
      scopeId={projet.id}
      invitationsOuvertes={offre.equipe}
      myRole={projet.myRole ?? null}
      members={members}
      invitations={invitations}
      onChanged={reloadMembers}
      onLeft={() => navigate(ROUTES.MONUMENTS)}
    />
  );

  const projectTabs: Onglet<string>[] = [
    // Les aides à débloquer comptent : ce sont des pistes vivantes, pas des refus.
    ...(canAccessAides ? [{ value: 'aides', label: 'Aides', picto: 'main' as const, count: aidesAPortee.length }] : []),
    { value: 'dossiers', label: 'Dossiers', picto: 'dossier', count: dossiers.length },
    { value: 'documents', label: 'Documents', picto: 'doc', count: projetDocuments.length },
    { value: 'equipe', label: 'Équipe', picto: 'equipe', count: members.length },
  ];

  // Titre et montant écrits de chaque aide à portée, pour les cartes de
  // l'échéancier : il ne connaît que les dates.
  const redaction = new Map(
    aidesAPortee.map((m) => [m.aide.id, { titre: titreAide(m.aide), montant: montantAide(m.aide)?.valeur ?? null }]),
  );
  const potentielsVisibles = toutAConfirmer ? potentielsMaintenant : potentielsMaintenant.slice(0, A_CONFIRMER_VISIBLES);
  const chezFiltre = filtre.key === 'toutes' ? '' : ` chez « ${filtre.label} »`;
  const aucuneSection =
    eligiblesMaintenant.length + atteignablesMaintenant.length + potentielsMaintenant.length + bientot.length === 0;

  return (
    <div className="ec pproj">
      <BoutonRetour to={`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=projets`} libelle={`Retour à ${monument.nom}`} />

      <ProjetSummaryBar
        projet={projet}
        monument={monument}
        onRefaireQuestionnaire={() => setConfirmRefaireOpen(true)}
        questionsPassees={questionsRestantes}
        onRenommer={handleRenommerProjet}
      />

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <Onglets onglets={projectTabs} actif={activeTab} onChange={handleTabChange} label="Rubriques du projet" />

        {/* AIDES */}
        <TabsContent value="aides">
          {chargementDiagnostic ? (
            <div className="onglet">
              <AidesTabSkeleton />
            </div>
          ) : !diagnostic ? (
            <div className="vide onglet" style={{ textAlign: 'center' }}>
              <h2 style={{ fontSize: 26 }}>Découvrez les aides de ce projet</h2>
              <p style={{ marginTop: 9 }}>
                Notre moteur analyse les aides publiques et privées applicables à {monument.nom}.
              </p>
              <button
                className="btn b-orange"
                type="button"
                onClick={handleRunDiagnostic}
                disabled={running}
                style={{ marginTop: 18 }}
              >
                {running && <Loader2 className="h-4 w-4 animate-spin" />}
                Lancer le moteur
              </button>
            </div>
          ) : (
            <>
              {deadlines.length > 0 &&
                (offre.echeancier ? (
                  <ProjectEcheancier deadlines={deadlines} aide={(id) => redaction.get(id) ?? null} />
                ) : (
                  <div style={{ marginTop: 26 }}>
                    <PaywallOverlay
                      offre="Veille"
                      titre="Ne laissez plus passer une date limite"
                      description="L'échéancier réunit les dates limites de vos aides et de vos dossiers, de la plus proche à la plus lointaine. L'offre Veille vous les rappelle aussi par email."
                      monumentId={monument.id}
                      chiffres={[
                        {
                          valeur: String(deadlines.length),
                          libelle: `échéance${deadlines.length > 1 ? 's' : ''} sur ce chantier`,
                        },
                      ]}
                    >
                      <ProjectEcheancier deadlines={deadlines} aide={(id) => redaction.get(id) ?? null} />
                    </PaywallOverlay>
                  </div>
                ))}

              <section className="sec" aria-labelledby="at">
                <div className="sec-h">
                  <h2 id="at">Toutes vos aides</h2>
                  <p>
                    {aidesAPortee.length} aide{aidesAPortee.length > 1 ? 's' : ''} repérée
                    {aidesAPortee.length > 1 ? 's' : ''} pour ce projet
                  </p>
                </div>

                <AideFiltreBar options={filtreOptions} value={filtreKey} onChange={setFiltreKey} />
                <AideFamilleBar options={familleOptions} value={familleFacette} onChange={setFamilleFacette} />

                {/* Une section vide se tait, comme « À débloquer » et « Disponibles
                    bientôt » : un titre suivi de « Aucune aide » n'apprend rien.
                    Si les quatre se taisent, une seule phrase le dit. */}
                {aucuneSection && <p className="empty">Aucune aide à proposer pour le moment{chezFiltre}.</p>}

                {eligiblesMaintenant.length > 0 && (
                  <Groupe
                    ton="ok"
                    picto="coche"
                    titre="Disponibles maintenant"
                    sous="Votre projet remplit les conditions publiées par le financeur, et le guichet est ouvert. Vous pouvez monter le dossier."
                  >
                    {renderAideList(eligiblesMaintenant)}
                  </Groupe>
                )}

                {atteignablesMaintenant.length > 0 && (
                  <Groupe
                    ton="db"
                    picto="cadenas"
                    titre="À débloquer"
                    sous="Une démarche vous sépare de ces aides : une protection, un label, un accord ou une adhésion. Ouvrez la fiche pour voir laquelle, auprès de qui et en combien de temps."
                  >
                    {renderAideList(atteignablesMaintenant)}
                  </Groupe>
                )}

                {potentielsMaintenant.length > 0 && (
                  <Groupe
                    ton="ck"
                    picto="question"
                    titre="À confirmer"
                    sous="Il nous manque une ou plusieurs réponses pour savoir si votre projet est éligible. Elles se posent dans la fiche de chaque aide."
                  >
                    {/* Le chiffre qui compte n'est pas le nombre d'aides mais ce
                        qu'il en coûte de trancher : les plus proches d'un
                        verdict sont en tête. */}
                    {renderAideList(potentielsVisibles)}
                    {potentielsMaintenant.length > A_CONFIRMER_VISIBLES && (
                      <div className="more">
                        <button className="btn b-line" type="button" onClick={() => setToutAConfirmer((v) => !v)}>
                          {toutAConfirmer
                            ? "Ne montrer que les plus proches d'un verdict"
                            : `Voir les ${potentielsMaintenant.length - A_CONFIRMER_VISIBLES} autres aides à confirmer`}
                        </button>
                      </div>
                    )}
                  </Groupe>
                )}

                {bientot.length > 0 && (
                  <Groupe
                    ton="bt"
                    picto="cloche"
                    titre="Disponibles bientôt"
                    sous="La fenêtre de candidature est fermée ou pas encore ouverte. Préparez votre dossier pour la prochaine session : la pastille de chaque aide indique où vous en êtes sur ses critères."
                  >
                    {offre.aidesBientot ? (
                      renderAideList(bientot)
                    ) : (
                      <PaywallOverlay
                        offre="Veille"
                        titre="Soyez prévenu le jour où le guichet ouvre"
                        description="Ces aides ne sont pas encore déposables. L'offre Veille vous envoie un email dès que l'une d'elles ouvre, et donne accès à sa fiche : son organisme, ses critères et les pièces à fournir."
                        monumentId={monument.id}
                        chiffres={chiffresBientot}
                        flou="11px"
                      >
                        {renderAideList(bientot)}
                      </PaywallOverlay>
                    )}
                  </Groupe>
                )}

                {nonEligibles.length > 0 && (
                  <>
                    <div className="ko">
                      <span className="gi">
                        <Picto nom="croix" />
                      </span>
                      <span>
                        <b>
                          {nonEligibles.length} aide{nonEligibles.length > 1 ? 's' : ''} écartée
                          {nonEligibles.length > 1 ? 's' : ''}
                        </b>{' '}
                        par vos réponses, avec la raison pour chacune.
                      </span>
                      <button type="button" aria-expanded={showNonEligibles} onClick={() => setShowNonEligibles((v) => !v)}>
                        {showNonEligibles ? 'Masquer' : 'Voir pourquoi'}
                      </button>
                    </div>
                    {showNonEligibles && (
                      <div className="cartes ko-liste">
                        {nonEligibles.map((match) => (
                          <AideCarte key={match.aide.id} match={match} projetId={projet.id} showMontant={chiffresAides} />
                        ))}
                      </div>
                    )}
                  </>
                )}
              </section>
            </>
          )}
        </TabsContent>

        {/* DOSSIERS */}
        <TabsContent value="dossiers" className="onglet space-y-4">
          {dossiers.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {dossiers.map((dossier) => (<DossierCard key={dossier.id} dossier={dossier} monumentColor={C.blue} />))}
            </div>
          ) : (
            <EmptyState
              icon={IconDossier}
              title="Aucun dossier pour ce projet"
              description="Ouvrez une aide depuis l'onglet « Aides » pour démarrer une candidature."
              action={
                <button onClick={() => handleTabChange('aides')} className="btn b-blue b-sm">
                  <IconAide className="h-4 w-4" strokeWidth={1.8} />Voir les aides
                </button>
              }
            />
          )}
        </TabsContent>

        {/* DOCUMENTS DU CHANTIER */}
        <TabsContent value="documents" className="onglet">
          {/* Les pièces de CE chantier, lues sur `documentService.getAll({ projetId })` ;
              un dépôt ici pend au projet, pas au monument. Droits : `projet.myRole`. */}
          <OngletDocuments
            ici={{ type: 'projet', id: projet.id, nom: projetTitre(projet, monument.nom) }}
            monumentId={monument.id}
            documents={projetDocuments}
            onChange={reloadProjetDocuments}
            role={projet.myRole ?? null}
            auteurs={uploaderNames}
            dossierNames={dossierNames}
            intro="Les pièces de ce chantier. Celles qui décrivent le monument (arrêté de protection, cadastre, photos) restent sur sa fiche."
            vide="Devis, plans, photos du chantier : déposez ici les pièces propres à ce projet de travaux."
          />
        </TabsContent>

        {/* ÉQUIPE DU CHANTIER */}
        <TabsContent value="equipe" className="onglet">
          {equipeAccessible ? (
            equipePanel
          ) : !offreConnue ? (
            // Offre pas encore connue : ni formulaire ni paywall, cf. plus haut.
            <div className="flex justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin" style={{ color: C.blueLight }} />
            </div>
          ) : (
            <PaywallOverlay
              offre="Veille"
              titre="Travaillez à plusieurs sur ce chantier"
              description="Invitez votre architecte ou vos artisans sur ce seul projet. Ils y voient ses aides, ses dossiers et ses documents, et rien des autres chantiers."
              monumentId={monument.id}
            >
              {equipePanel}
            </PaywallOverlay>
          )}
        </TabsContent>
      </Tabs>


      {/* Deux conditions distinctes : le rôle dit « ce compte a-t-il le droit »,
          l'offre dit « ce produit le permet-il ». Un plafond de deux projets
          qu'on pourrait vider en boucle ne serait pas un plafond. */}
      {perms.canEditProject && offre.suppressionProjet && (
        <div className="flex justify-end pt-2">
          <button
            onClick={() => setConfirmDeleteOpen(true)}
            disabled={deleting}
            className="inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[15px] font-semibold transition-colors hover:bg-destructive-muted disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            style={{ borderColor: C.border, color: C.danger }}
          >
            {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <IconSupprimer className="h-4 w-4" strokeWidth={1.8} />}
            Supprimer ce projet
          </button>
        </div>
      )}

      <AlertDialog open={confirmRefaireOpen} onOpenChange={setConfirmRefaireOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Refaire le questionnaire&nbsp;?</AlertDialogTitle>
            <AlertDialogDescription>
              Le cadrage du projet (vos intentions, les travaux) est conservé dans les
              deux cas&nbsp;; seul le questionnaire est repris, et le diagnostic
              d&rsquo;aides recalculé ensuite.
            </AlertDialogDescription>
          </AlertDialogHeader>

          {/* Deux boutons de même poids, pas une action et son annulation : ce
              sont deux intentions distinctes, et la plus fréquente — revenir sur
              les questions qu'on avait passées — est offerte en premier. */}
          <div className="flex flex-col gap-2.5">
            {questionsRestantes > 0 && (
              <button
                type="button"
                onClick={() => confirmRefaire('passees')}
                className="rounded-xl border-[1.5px] px-4 py-3 text-left transition-colors hover:bg-warning-muted"
                style={{ borderColor: C.orange, background: C.card }}
              >
                <span className="block text-[16.5px] font-semibold" style={{ color: C.ink }}>
                  Seulement les questions passées
                  <span className="ml-1.5 font-normal tabular-nums" style={{ color: C.orange }}>
                    ({questionsRestantes})
                  </span>
                </span>
                <span className="mt-0.5 block text-[15px]" style={{ color: C.grayFg }}>
                  Vos réponses actuelles sont conservées&nbsp;: on ne repose que celles
                  restées sans réponse.
                </span>
              </button>
            )}
            <button
              type="button"
              onClick={() => confirmRefaire('tout')}
              className="rounded-xl border px-4 py-3 text-left transition-colors hover:bg-muted"
              style={{ borderColor: C.border, background: C.card }}
            >
              <span className="block text-[16.5px] font-semibold" style={{ color: C.ink }}>
                Tout refaire depuis le début
              </span>
              <span className="mt-0.5 block text-[15px]" style={{ color: C.grayFg }}>
                Le questionnaire repart vierge&nbsp;: vos réponses actuelles seront
                remplacées.
              </span>
            </button>
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce projet&nbsp;?</AlertDialogTitle>
            <AlertDialogDescription>
              Ses dossiers et leur suivi seront également supprimés. La fiche du
              monument, ses documents et son équipe ne sont pas touchés. Cette action
              est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Annuler</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleDeleteProjet} disabled={deleting}>
              {deleting ? 'Suppression…' : 'Supprimer'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
