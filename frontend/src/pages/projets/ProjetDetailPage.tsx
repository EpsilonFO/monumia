import { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate, useSearchParams, Navigate } from 'react-router';
import { ChevronLeft, ChevronDown, Loader2 } from 'lucide-react';
import {
  type IconComponent,
  IconDiagnostic, IconSucces, IconHelp, IconErreur, IconCle, IconCalendrier,
  IconAide, IconDossier, IconDocuments, IconDepot, IconEquipe, IconRafraichir, IconSupprimer,
} from '@/components/icons';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { EmptyState } from '@/components/shared/EmptyState';
import { AideCard } from '@/components/aide/AideCard';
import { AideFiltreBar } from '@/components/aide/AideFiltreBar';
import { AidesPaywallBanner } from '@/components/aide/AidesPaywallBanner';
import { DossierCard } from '@/components/dossier/DossierCard';
import { DocumentCard } from '@/components/document/DocumentCard';
import { DocumentGrid } from '@/components/document/DocumentGrid';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { TeamPanel } from '@/components/sharing/TeamPanel';
import { projectPermissions } from '@/lib/project-permissions';
import { useOffre, useOffreMonument } from '@/hooks/useOffre';
import { libelleMonuments } from '@/lib/offres';
import { OffreUpsell } from '@/components/shared/OffreUpsell';
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
import { computeProjectStats, mergeProjectDeadlines } from '@/lib/project-stats';
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
    (requestedTab === 'aides' && !canAccessAides) ||
    (requestedTab === 'equipe' && !equipeAccessible)
      ? 'dossiers'
      : requestedTab;
  const handleTabChange = useCallback((value: string) => {
    if (value === 'equipe' && !equipeAccessible) {
      navigate(ROUTES.TARIFS(monumentId));
      return;
    }
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', value);
      return next;
    }, { replace: true });
  }, [setSearchParams, equipeAccessible, navigate, monumentId]);

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

  // « Refaire le questionnaire » : on prévient que les réponses et le diagnostic
  // actuels seront effacés, puis on rouvre le wizard projet sur CE projet
  // (intentions et travaux préremplis, questionnaire vierge).
  const confirmRefaire = useCallback(() => {
    if (!projetId || !monumentId) return;
    setConfirmRefaireOpen(false);
    navigate(`${ROUTES.PROJET_NEW(monumentId)}?projet=${projetId}`);
  }, [projetId, monumentId, navigate]);

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
  const toutesPotentiels = [...(diagnostic?.aidesPotentiellementEligibles ?? [])].filter((m) => !dossierAideIds.has(m.aide.id)).sort(byDeadline);
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
  const eligibles = filtrerAides(toutesEligibles, filtre);
  const potentiels = filtrerAides(toutesPotentiels, filtre);
  const atteignables = filtrerAides(toutesAtteignables, filtre);
  const nonEligibles = filtrerAides(toutesNonEligibles, filtre);

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
  // Le verrou porte désormais sur UNE aide et non sur le projet : seules les
  // aides dont le guichet n'est pas encore ouvert sont floutées, et seulement
  // hors offre Veille. Le serveur en a déjà retiré le nom et le financeur
  // (cf. redact_bientot_hors_offre) — le floutage n'en est que la traduction
  // visuelle, il ne cache rien à lui seul.
  const estVerrouillee = (match: AideMatchResult) =>
    !offre.aidesBientot && getDisponibilite(match) === 'bientot';

  const renderAideList = (list: AideMatchResult[]) => {
    if (list.length === 1)
      return <AideCard match={list[0]} projetId={projet.id} monumentId={monument.id} layout="hero" locked={estVerrouillee(list[0])} />;
    const spans = aideGridSpans(list.length);
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
        {list.map((match, i) => (
          <div key={match.aide.id} className={spans[i]}>
            <AideCard match={match} projetId={projet.id} monumentId={monument.id} layout="grid" locked={estVerrouillee(match)} />
          </div>
        ))}
      </div>
    );
  };

  const aidesAPortee = [...toutesEligibles, ...toutesAtteignables, ...toutesPotentiels];
  // Enjeu chiffré du bandeau d'offre : la somme des plafonds des SEULES aides
  // encore à venir. Le montant total du diagnostic ne dirait rien de ce que
  // l'offre débloque — l'essentiel en vient d'aides déjà consultables.
  const montantBientot = bientot.reduce((sum, m) => sum + (m.aide.montantMax ?? 0), 0);

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
                <OffreUpsell
                  variante="bandeau"
                  action="suivre toutes les échéances de ce chantier, et de les rappeler par email avant la date limite"
                  offre="Veille"
                  monumentId={monument.id}
                />
              )}

              <AideFiltreBar options={filtreOptions} value={filtreKey} onChange={setFiltreKey} />

              <section className="space-y-3">
                <h3 className="flex items-center gap-2 text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  <IconSucces className="h-4 w-4 text-success" />Disponibles maintenant ({eligiblesMaintenant.length})
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
                </h3>
                {potentielsMaintenant.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground">
                    {filtre.key === 'toutes'
                      ? 'Aucune aide à confirmer.'
                      : `Aucune aide à confirmer chez « ${filtre.label} ».`}
                  </p>
                ) : renderAideList(potentielsMaintenant)}
              </section>

              {bientot.length > 0 && (
                <section className="space-y-3">
                  <h3 className="flex items-center gap-2 text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
                    <IconCalendrier className="h-4 w-4 text-info" />Disponibles bientôt ({bientot.length})
                  </h3>
                  <p className="text-[13px] text-muted-foreground">
                    La fenêtre de candidature est fermée ou pas encore ouverte. Préparez votre
                    dossier pour la prochaine session : la pastille de chaque aide indique où vous
                    en êtes sur ses critères.
                  </p>
                  {!offre.aidesBientot && (
                    <AidesPaywallBanner
                      monumentId={monument.id}
                      montantTotal={montantBientot}
                      nombreAides={bientot.length}
                    />
                  )}
                  {renderAideList(bientot)}
                </section>
              )}

              <section className="space-y-3">
                <button
                  onClick={() => setShowNonEligibles((v) => !v)}
                  className="flex items-center gap-2 text-[15px]"
                  style={{ fontFamily: SERIF, color: C.ink }}
                >
                  <IconErreur className="h-4 w-4 text-destructive" />Non éligibles ({nonEligibles.length})
                  <ChevronDown className={`h-4 w-4 transition-transform ${showNonEligibles ? 'rotate-180' : ''}`} />
                </button>
                {showNonEligibles && (
                  nonEligibles.length === 0 ? (
                    <p className="text-[13px] text-muted-foreground">
                      {filtre.key === 'toutes'
                        ? 'Aucune aide écartée par vos réponses.'
                        : `Aucune aide écartée par vos réponses chez « ${filtre.label} ».`}
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                      {nonEligibles.map((match) => (<AideCard key={match.aide.id} match={match} projetId={projet.id} monumentId={monument.id} />))}
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
              Vous repartirez du cadrage déjà enregistré pour ce projet&nbsp;: seules les
              réponses au questionnaire seront redemandées. Vos réponses actuelles seront
              remplacées et le diagnostic d&rsquo;aides recalculé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmRefaire}
              className="text-white hover:opacity-90"
              style={{ background: C.orange }}
            >
              <IconRafraichir className="h-4 w-4" />
              Refaire le questionnaire
            </AlertDialogAction>
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
