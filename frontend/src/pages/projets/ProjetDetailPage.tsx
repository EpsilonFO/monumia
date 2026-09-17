import { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate, useSearchParams, Navigate } from 'react-router';
import { ChevronLeft, ChevronDown, Loader2 } from 'lucide-react';
import {
  type IconComponent,
  IconDiagnostic, IconSucces, IconHelp, IconErreur, IconCle, IconCalendrier,
  IconAide, IconDossier, IconDocuments, IconDepot, IconEquipe, IconSupprimer,
} from '@/components/icons';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { EmptyState } from '@/components/shared/EmptyState';
import { InfoBulle } from '@/components/shared/InfoBulle';
import { AideCard } from '@/components/aide/AideCard';
import { AideFamilleBar } from '@/components/aide/AideFamilleBar';
import { AideFiltreBar } from '@/components/aide/AideFiltreBar';
import { DossierCard } from '@/components/dossier/DossierCard';
import { DocumentCard } from '@/components/document/DocumentCard';
import { DocumentGrid } from '@/components/document/DocumentGrid';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { TeamPanel } from '@/components/sharing/TeamPanel';
import { projectPermissions } from '@/lib/project-permissions';
import { useOffre, useOffreMonument } from '@/hooks/useOffre';
import { estOffreGratuite, libelleMonuments } from '@/lib/offres';
import { PaywallOverlay } from '@/components/shared/Paywall';
import { formatCurrency } from '@/lib/format-utils';
import { ProjetSummaryBar } from '@/components/projet/ProjetSummaryBar';
import { ProjectDetailSkeleton } from '@/components/skeletons';
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
import { aideGridSpans } from '@/lib/aide-grid';
import { getDisponibilite } from '@/components/aide/eligibility-status';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import { isAccessLostError } from '@/lib/api-error';
import type {
  AideMatchResult, Document, ProjectInvitation, ProjectMember, ProjectQuestionnaireAnswers,
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
  const repondreFait = useProjetStore((s) => s.repondreFait);

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
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [accessDoc, setAccessDoc] = useState<Document | null>(null);
  const [addDocOpen, setAddDocOpen] = useState(false);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [invitations, setInvitations] = useState<ProjectInvitation[]>([]);

  const tabParam = searchParams.get('tab');
  // Les droits se lisent sur le PROJET : un collaborateur invité sur le seul
  // chantier n'a aucun rôle sur le monument, mais bien un rôle ici.
  const perms = projectPermissions(projet?.myRole ?? null);
  // L'onglet « Aides » est réservé au chef de projet et à son adjoint. Pour un
  // collaborateur, on retombe sur « Dossiers ».
  const canAccessAides = perms.canAccessAides;
  // L'offre qui gouverne le BIEN, et non le compte : un collaborateur invité
  // par un client abonné voit le même calendrier que son client. Elle décide
  // ici de trois choses — l'échéancier, les aides encore à venir, et la
  // suppression du chantier.
  const offre = useOffreMonument(monumentId);
  const offreCompte = useOffre();
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

  // Monument parent : entête, fil d'Ariane, rôle et paywall.
  useEffect(() => {
    if (!monumentId || monument) return;
    monumentService.getById(monumentId).then(upsertMonument).catch(console.error);
  }, [monumentId, monument, upsertMonument]);

  // Diagnostic déterministe : recalculé à l'arrivée (et quand les réponses du
  // questionnaire changent). Le moteur est pur et rapide — pas de persistance ;
  // les réponses (projet.questionnaire) se résolvent côté client via
  // eliminationsParOption.
  const questionnaireKey = projet ? JSON.stringify(projet.questionnaire ?? {}) : '';
  useEffect(() => {
    if (!projetId || !questionnaireKey) return;
    let cancelled = false;
    const answers: ProjectQuestionnaireAnswers = JSON.parse(questionnaireKey);
    aideService.runProjectDiagnostic(projetId, answers)
      .then((result) => { if (!cancelled) setDiagnostic(projetId, result); })
      .catch(console.error);
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

  // Les questions du diagnostic, telles que les cartes et la fiche d'une aide
  // les reposent. Mémorisées sur l'objet `diagnostic` : sans ça, chaque rendu
  // rendrait un nouveau tableau et ferait remonter les cartes.
  const questionsDiagnostic = useMemo(
    () => sanitizeQcmQuestions(diagnostic?.qcmQuestions),
    [diagnostic],
  );

  /**
   * Répondre à une question depuis la carte d'une aide.
   *
   * Le droit est `canEditProject` (= co_owner), miroir exact de ce qu'exige
   * `update_projet` côté serveur (routers/projets.py) : afficher des réponses
   * qu'un 403 refuserait serait le pire des deux mondes. L'écriture est
   * sérialisée par le store — `questionnaire` est remplacé en bloc.
   *
   * Pas de relance explicite du diagnostic : le projet mis à jour change
   * `questionnaireKey`, et l'effet ci-dessus recalcule tout seul.
   */
  const [envoiReponse, setEnvoiReponse] = useState(false);
  const handleRepondre = useCallback(
    async (factKey: string, value: string | string[] | undefined) => {
      if (!projetId) return;
      setEnvoiReponse(true);
      try {
        await repondreFait(projetId, factKey, value);
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Votre réponse n'a pas pu être enregistrée",
        );
      } finally {
        setEnvoiReponse(false);
      }
    },
    [projetId, repondreFait],
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
        <h1 className="text-[20px]" style={{ fontFamily: SERIF, color: C.ink }}>Projet introuvable</h1>
        <p className="text-[14px] text-muted-foreground">Ce projet n'existe pas ou a été supprimé.</p>
        <Link to={ROUTES.MONUMENTS} className="inline-flex items-center gap-1.5 text-[13px] font-medium" style={{ color: C.blue }}>
          <ChevronLeft className="h-3.5 w-3.5" /> Retour à mes monuments
        </Link>
      </div>
    );
  }

  if (!projet || !monument || !stats) return <ProjectDetailSkeleton />;

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
  const potentielsUneQuestion = toutesPotentiels.filter((m) => reste(m) === 1).length;
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

  // L'affichage des aides s'adapte au nombre : 1 → bandeau pleine largeur, sinon
  // grille 6 colonnes où chaque carte s'étale (rangées de deux ou de trois) pour
  // que chaque rangée soit pleine — jamais de case vide (voir aideGridSpans).
  // Les cartes ne portent plus de verrou : le paywall des aides à venir vit au
  // niveau de la SECTION, qui les floute et les rend inertes d'un bloc. Un
  // cadenas par carte, derrière ce flou, n'aurait fait que brouiller l'aperçu.
  // Le bandeau chiffré des cartes, lui, ne s'affiche qu'à partir de Veille —
  // c'est l'offre du MONUMENT qui décide, comme pour ses projets et son
  // calendrier. Rien n'est retenu pour autant : montant, taux et échéance
  // restent sur la fiche de l'aide, qui est gratuite.
  const chiffresAides = !estOffreGratuite(offre);
  // Répondre depuis une carte suppose le droit d'écrire sur le projet ; sinon
  // les cartes restent en lecture seule et renvoient à la fiche.
  const propsReponse = perms.canEditProject
    ? {
        questions: questionsDiagnostic,
        answers: projet.questionnaire ?? {},
        onRepondre: handleRepondre,
        envoiEnCours: envoiReponse,
      }
    : {};
  const renderAideList = (list: AideMatchResult[]) => {
    if (list.length === 1)
      return (
        <AideCard
          match={list[0]}
          projetId={projet.id}
          layout="hero"
          showChiffres={chiffresAides}
          {...propsReponse}
        />
      );
    const spans = aideGridSpans(list.length);
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
        {list.map((match, i) => (
          <div key={match.aide.id} className={spans[i]}>
            <AideCard
              match={match}
              projetId={projet.id}
              layout="grid"
              showChiffres={chiffresAides}
              {...propsReponse}
            />
          </div>
        ))}
      </div>
    );
  };

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
  const monumentNames = { [monument.id]: monument.nom };

  const handleRenameDoc = async (id: string, newName: string) => {
    try { await documentService.update(id, { nom: newName }); reloadProjetDocuments(); toast.success('Document renommé'); }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors du renommage'); }
  };
  const handleDeleteDoc = async (id: string) => {
    try { await documentService.delete(id); reloadProjetDocuments(); toast.success('Document supprimé'); }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression'); }
  };
  // Ajouter un document au PROJET : tout membre du chantier peut déposer. Le
  // document est rattaché au projet — pas au monument : le déposer ici ne doit
  // pas l'exposer à l'équipe du bien au-delà de ce qu'elle voit déjà.
  const handleAddDocument = async (doc: Document) => {
    if (!projetId) return;
    try {
      if (!doc.projetIds.includes(projetId)) {
        await documentService.addToProjects(doc.id, [], [projetId]);
      }
      reloadProjetDocuments();
      toast.success('Document ajouté au projet');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur lors de l'ajout");
      throw err;
    }
  };

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

  const projectTabs: { value: string; label: string; icon: IconComponent; count: number | null }[] = [
    // Les aides à débloquer comptent : ce sont des pistes vivantes, pas des refus.
    ...(canAccessAides ? [{ value: 'aides', label: 'Aides', icon: IconAide, count: aidesAPortee.length }] : []),
    { value: 'dossiers', label: 'Dossiers', icon: IconDossier, count: dossiers.length },
    { value: 'documents', label: 'Documents', icon: IconDocuments, count: projetDocuments.length },
    { value: 'equipe', label: 'Équipe', icon: IconEquipe, count: members.length },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 overflow-hidden text-[13px] text-muted-foreground">
        <Link to={ROUTES.MONUMENTS} className="shrink-0 hover:opacity-70 transition-opacity">{libelleMonuments(offreCompte)}</Link>
        <span>/</span>
        <Link
          to={`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=projets`}
          className="truncate hover:opacity-70 transition-opacity"
        >
          {monument.nom}
        </Link>
      </div>

      <ProjetSummaryBar
        projet={projet}
        monument={monument}
        onRefaireQuestionnaire={() => setConfirmRefaireOpen(true)}
        onRenommer={handleRenommerProjet}
      />

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <div role="tablist" aria-label="Sections du projet" className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          {projectTabs.map(({ value, label, icon: Icon, count }) => {
            const active = activeTab === value;
            return (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => handleTabChange(value)}
                className={`relative flex items-center justify-center gap-2 overflow-hidden rounded-xl px-4 py-3.5 text-[15px] font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                  active
                    ? 'bg-primary text-primary-foreground shadow-pop'
                    : 'border border-border bg-card text-foreground hover:-translate-y-0.5 hover:border-primary hover:shadow-md'
                }`}
              >
                <Icon className={`h-5 w-5 shrink-0 ${active ? 'text-primary-foreground' : 'text-primary'}`} strokeWidth={2} />
                <span className="truncate">{label}</span>
                {count !== null && (
                  <span
                    className={`inline-flex min-w-[1.5rem] items-center justify-center rounded-full px-1.5 py-0.5 text-[12px] font-bold tabular-nums ${
                      active ? 'bg-white/25 text-primary-foreground' : 'bg-secondary text-primary'
                    }`}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* AIDES */}
        <TabsContent value="aides" className="mt-4 space-y-6">
          {!diagnostic ? (
            <div className="rounded-2xl border py-10 text-center space-y-4" style={{ background: C.paleBlue, borderColor: C.border }}>
              <div className="mx-auto w-14 h-14 rounded-full flex items-center justify-center" style={{ background: '#fff' }}>
                <IconDiagnostic className="h-7 w-7" style={{ color: C.blue }} />
              </div>
              <div>
                <h2 className="text-[18px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  Découvrez les aides pour <em className="italic" style={{ color: C.orange }}>{monument.nom}</em>
                </h2>
                <p className="text-[14px] mt-1 text-muted-foreground">Notre moteur analyse les aides publiques et privées applicables à ce projet.</p>
              </div>
              <button
                onClick={handleRunDiagnostic}
                disabled={running}
                className="inline-flex items-center gap-2 px-6 py-3 text-[13px] font-semibold text-white rounded-lg transition-all duration-300 hover:shadow-md disabled:opacity-60"
                style={{ background: C.orange }}
              >
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <IconDiagnostic className="h-4 w-4" strokeWidth={1.8} />}
                Lancer le moteur
              </button>
            </div>
          ) : (
            <div className="space-y-8">
              {offre.echeancier ? (
                <ProjectEcheancier deadlines={deadlines} />
              ) : (
                <PaywallOverlay
                  offre="Veille"
                  titre="Ne laissez plus passer une date limite"
                  description="L'échéancier réunit les dates limites de vos aides et de vos dossiers, de la plus proche à la plus lointaine. L'offre Veille vous les rappelle aussi par email."
                  monumentId={monument.id}
                  chiffres={
                    deadlines.length > 0
                      ? [
                          {
                            valeur: String(deadlines.length),
                            libelle: `échéance${deadlines.length > 1 ? 's' : ''} sur ce chantier`,
                          },
                        ]
                      : undefined
                  }
                >
                  <ProjectEcheancier deadlines={deadlines} />
                </PaywallOverlay>
              )}

              <AideFiltreBar options={filtreOptions} value={filtreKey} onChange={setFiltreKey} />

              <AideFamilleBar
                options={familleOptions}
                value={familleFacette}
                onChange={setFamilleFacette}
              />

              <section className="space-y-3">
                <h3 className="flex items-center gap-2 text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  <IconSucces className="h-4 w-4 text-success" />Disponibles maintenant ({eligiblesMaintenant.length})
                  <InfoBulle libelle="Disponibles maintenant">
                    Nous passons en revue, une par une, toutes les conditions publiées par
                    chaque aide et nous les confrontons à la fiche de votre monument et à vos
                    réponses. Ici&nbsp;: aucune condition ne manque et aucune n'est contredite,
                    et le guichet est ouvert aujourd'hui.
                  </InfoBulle>
                </h3>
                {eligiblesMaintenant.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground">
                    {filtre.key === 'toutes'
                      ? 'Aucune aide pleinement éligible pour le moment.'
                      : `Aucune aide pleinement éligible chez « ${filtre.label} ».`}
                  </p>
                ) : renderAideList(eligiblesMaintenant)}
              </section>

              {atteignablesMaintenant.length > 0 && (
                <section className="space-y-3">
                  <h3 className="flex items-center gap-2 text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
                    <IconCle className="h-4 w-4 text-info" />À débloquer ({atteignablesMaintenant.length})
                    <InfoBulle libelle="À débloquer">
                      Une condition n'est pas remplie, mais elle dépend d'une démarche que vous
                      pouvez engager (une protection, un label, un accord, une adhésion). Ce
                      n'est donc pas un refus&nbsp;: c'est une étape.
                    </InfoBulle>
                  </h3>
                  <p className="text-[13px] text-muted-foreground">
                    Une démarche vous sépare de ces aides. Ouvrez la fiche pour voir laquelle,
                    auprès de qui et en combien de temps.
                  </p>
                  {renderAideList(atteignablesMaintenant)}
                </section>
              )}

              <section className="space-y-3">
                <h3 className="flex items-center gap-2 text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  <IconHelp className="h-4 w-4" style={{ color: C.orangeVif }} />À confirmer ({potentielsMaintenant.length})
                  <InfoBulle libelle="À confirmer">
                    Rien ne les écarte, mais vos réponses ne suffisent pas encore à trancher&nbsp;:
                    une ou plusieurs conditions restent en suspens. Nous ne les éliminons jamais
                    dans le doute. Complétez le questionnaire, ou ouvrez la fiche pour voir ce
                    qu'il reste à vérifier auprès de l'organisme.
                  </InfoBulle>
                </h3>
                {potentielsMaintenant.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground">
                    {filtre.key === 'toutes'
                      ? 'Aucune aide à confirmer.'
                      : `Aucune aide à confirmer chez « ${filtre.label} ».`}
                  </p>
                ) : (
                  <>
                    {/* Le chiffre qui compte n'est pas le nombre d'aides mais ce
                        qu'il en coûte de trancher : les plus proches d'un
                        verdict sont en tête, et celles à une seule question se
                        répondent sans quitter la page. */}
                    {potentielsUneQuestion > 0 && perms.canEditProject && (
                      <p className="text-[13px] text-muted-foreground">
                        Dont {potentielsUneQuestion} à une seule question&nbsp;: répondez
                        directement sur la carte.
                      </p>
                    )}
                    {renderAideList(potentielsMaintenant)}
                  </>
                )}
              </section>

              {bientot.length > 0 && (
                <section className="space-y-3">
                  <h3 className="flex items-center gap-2 text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
                    <IconCalendrier className="h-4 w-4 text-info" />Disponibles bientôt ({bientot.length})
                    <InfoBulle libelle="Disponibles bientôt">
                      Leurs conditions sont examinées exactement comme celles des autres&nbsp;:
                      c'est leur calendrier qui les met à part, pas votre dossier. La fenêtre de
                      candidature est fermée, ou pas encore ouverte.
                    </InfoBulle>
                  </h3>
                  <p className="text-[13px] text-muted-foreground">
                    La fenêtre de candidature est fermée ou pas encore ouverte. Préparez votre
                    dossier pour la prochaine session : la pastille de chaque aide indique où vous
                    en êtes sur ses critères.
                  </p>
                  {offre.aidesBientot ? (
                    renderAideList(bientot)
                  ) : (
                    <PaywallOverlay
                      offre="Veille"
                      titre="Soyez prévenu le jour où le guichet ouvre"
                      description="Ces aides ne sont pas encore déposables. L'offre Veille vous envoie un email dès que l'une d'elles ouvre, et donne accès à sa fiche : son organisme, ses critères et les pièces à fournir."
                      monumentId={monument.id}
                      chiffres={chiffresBientot}
                      flou="10px"
                    >
                      {renderAideList(bientot)}
                    </PaywallOverlay>
                  )}
                </section>
              )}

              <section className="space-y-3">
                {/* Le « i » est HORS du bouton : imbriqué dedans, il replierait
                    la section au moment même où on lui demande une explication. */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowNonEligibles((v) => !v)}
                    className="flex items-center gap-2 text-[15px]"
                    style={{ fontFamily: SERIF, color: C.ink }}
                  >
                    <IconErreur className="h-4 w-4 text-destructive" />Non éligibles ({nonEligibles.length})
                    <ChevronDown className={`h-4 w-4 transition-transform ${showNonEligibles ? 'rotate-180' : ''}`} />
                  </button>
                  <InfoBulle libelle="Non éligibles">
                    Au moins une condition est ici contredite par la fiche du monument ou par vos
                    réponses — un critère de protection, de propriétaire, de territoire. Nous les
                    laissons visibles pour que vous puissiez voir ce qui bloque, et parce qu'une
                    réponse corrigée peut faire revenir une aide dans les autres listes.
                  </InfoBulle>
                </div>
                {showNonEligibles && (
                  nonEligibles.length === 0 ? (
                    <p className="text-[13px] text-muted-foreground">
                      {filtre.key === 'toutes'
                        ? 'Aucune aide écartée par vos réponses.'
                        : `Aucune aide écartée par vos réponses chez « ${filtre.label} ».`}
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                      {nonEligibles.map((match) => (<AideCard key={match.aide.id} match={match} projetId={projet.id} />))}
                    </div>
                  )
                )}
              </section>
            </div>
          )}
        </TabsContent>

        {/* DOSSIERS */}
        <TabsContent value="dossiers" className="mt-4 space-y-4">
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
                <button onClick={() => handleTabChange('aides')} className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md" style={{ background: C.blue }}>
                  <IconAide className="h-4 w-4" strokeWidth={1.8} />Voir les aides
                </button>
              }
            />
          )}
        </TabsContent>

        {/* DOCUMENTS DU CHANTIER */}
        <TabsContent value="documents" className="mt-4 space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[13px] text-muted-foreground">
              Les pièces de CE chantier. Celles qui décrivent le monument (arrêté de
              protection, cadastre, photos) restent sur sa fiche.
            </p>
            <button onClick={() => setAddDocOpen(true)} className="inline-flex shrink-0 items-center justify-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md" style={{ background: C.blue }}>
              <IconDepot className="h-3.5 w-3.5" strokeWidth={1.8} />Ajouter un document
            </button>
          </div>
          {projetDocuments.length > 0 ? (
            <DocumentGrid
              items={projetDocuments}
              keyOf={(doc) => doc.id}
              renderItem={(doc) => (
                <DocumentCard
                  document={doc}
                  dossierNames={dossierNames}
                  monumentNames={monumentNames}
                  onClick={() => setPreviewDoc(doc)}
                  onRename={handleRenameDoc}
                  onDelete={handleDeleteDoc}
                  myRole={projet.myRole ?? null}
                  uploaderName={uploaderNames[doc.userId]}
                  onDocumentUpdated={reloadProjetDocuments}
                />
              )}
            />
          ) : (
            <EmptyState
              icon={IconDocuments}
              title="Aucun document sur ce projet"
              description="Devis, plans, photos du chantier : déposez ici les pièces propres à ce projet de travaux."
            />
          )}
        </TabsContent>

        {/* ÉQUIPE DU CHANTIER */}
        <TabsContent value="equipe" className="mt-4">
          {equipeAccessible ? (
            equipePanel
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

      <DocumentPreviewDialog
        document={previewDoc}
        open={!!previewDoc}
        onOpenChange={(open) => { if (!open) setPreviewDoc(null); }}
      />
      <AttachDocumentDialog
        open={addDocOpen}
        onOpenChange={setAddDocOpen}
        projetId={projet.id}
        onAttach={handleAddDocument}
        onUploaded={(doc) => setAccessDoc(doc)}
      />
      {accessDoc && (
        <ManageDocumentAccessDialog
          document={accessDoc}
          myRole={projet.myRole ?? null}
          open={!!accessDoc}
          onOpenChange={(open) => { if (!open) setAccessDoc(null); }}
          onSaved={reloadProjetDocuments}
        />
      )}

      {/* Deux conditions distinctes : le rôle dit « ce compte a-t-il le droit »,
          l'offre dit « ce produit le permet-il ». Un plafond de deux projets
          qu'on pourrait vider en boucle ne serait pas un plafond. */}
      {perms.canEditProject && offre.suppressionProjet && (
        <div className="flex justify-end pt-2">
          <button
            onClick={() => setConfirmDeleteOpen(true)}
            disabled={deleting}
            className="inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[13px] font-semibold transition-colors hover:bg-destructive-muted disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
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
                <span className="block text-[14.5px] font-semibold" style={{ color: C.ink }}>
                  Seulement les questions passées
                  <span className="ml-1.5 font-normal tabular-nums" style={{ color: C.orange }}>
                    ({questionsRestantes})
                  </span>
                </span>
                <span className="mt-0.5 block text-[13px]" style={{ color: C.grayFg }}>
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
              <span className="block text-[14.5px] font-semibold" style={{ color: C.ink }}>
                Tout refaire depuis le début
              </span>
              <span className="mt-0.5 block text-[13px]" style={{ color: C.grayFg }}>
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
