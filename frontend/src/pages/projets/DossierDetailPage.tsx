import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router';
import { Loader2 } from 'lucide-react';
import { IconSupprimer } from '@/components/icons';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { AideStatutSelect } from '@/components/aide/AideStatutSelect';
import { DossierChecklist } from '@/components/dossier/DossierChecklist';
import { ReprisesReviewDialog } from '@/components/dossier/ReprisesReviewDialog';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { UploadDocumentDialog, type PieceAPreremplir } from '@/components/document/UploadDocumentDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { BoutonRetour } from '@/components/shared/ecrans/BoutonRetour';
import { Picto } from '@/components/shared/ecrans/Picto';
import { DossierDetailSkeleton } from '@/components/skeletons';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useTemplateStore } from '@/stores/useTemplateStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { useAideStore } from '@/stores/useAideStore';
import { matchTemplates } from '@/lib/template-matching';
import { projectPermissions } from '@/lib/project-permissions';
import { chapeauAide, financeurAide, guichet, montantAide, titreAide } from '@/lib/fiche-aide';
import { monumentService } from '@/services/monument.service';
import { projetService } from '@/services/projet.service';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { documentService } from '@/services/document.service';
import { suiviService } from '@/services/suivi.service';
import { projetTitre } from '@/lib/projet-titre';
import { C } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { ACCEPT_ATTR } from '@/constants/file-types';
import { isAccessLostError } from '@/lib/api-error';
import { toast } from 'sonner';
import type { Aide, ChecklistItem, Document, DocumentType, Dossier } from '@/types';
import './projet.css';
import './dossier.css';

/**
 * Le sélecteur d'avancement (« À faire », « En préparation », « Déposé »…) est
 * masqué pour l'instant, en haut du dossier ouvert. Rien d'autre ne change : le
 * suivi continue d'exister en base, de se charger ici et d'alimenter les
 * vignettes et l'échéancier — seul son éditeur disparaît de cette page.
 *
 * Remettre `true` le rend tel quel.
 */
const AVANCEMENT_MODIFIABLE = false;

/**
 * Un dossier de candidature ouvert, avec l'habillage des écrans (`.ec`) : même
 * en-tête que la page du projet, les pièces en emplacements comme dans
 * l'onglet Documents, et l'aide résumée en une carte qui mène à sa fiche.
 */
export function DossierDetailPage() {
  const { projetId, dossierId } = useParams();
  const navigate = useNavigate();

  const projet = useProjetStore((s) => s.projets.find((p) => p.id === projetId));
  const upsertProjet = useProjetStore((s) => s.upsertProjet);
  const dossier = useDossierStore((s) => s.dossiers.find((d) => d.id === dossierId));
  // Le dossier porte aussi l'id du monument (dénormalisé côté serveur) : on
  // n'attend pas le projet pour aller chercher le monument, les deux partent
  // ensemble.
  const monumentId = projet?.monumentId ?? dossier?.monumentId;
  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId));
  const upsertMonument = useMonumentStore((s) => s.upsertMonument);

  const dossierLoaded = useDossierStore((s) => s.loaded);
  const setDossiers = useDossierStore((s) => s.setDossiers);

  const templates = useTemplateStore((s) => s.templates);
  const templatesLoaded = useTemplateStore((s) => s.loaded);
  const fetchTemplates = useTemplateStore((s) => s.fetchAll);

  const documents = useDocumentStore((s) => s.documents);
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments);
  const linkToDossierStore = useDocumentStore((s) => s.linkToDossier);
  const unlinkFromDossierStore = useDocumentStore((s) => s.unlinkFromDossier);
  const addToProjectsStore = useDocumentStore((s) => s.addToProjects);

  // Les pièces que citent les aides du projet (digest du tableau de bord) :
  // c'est d'elles qu'on tire le dossier où ranger un fichier déposé ici.
  const digest = useAideStore((s) => (projetId ? s.digestsByProjet[projetId] : undefined));

  const currentUserId = useAuthStore((s) => s.user?.id);

  // Avancement (statut / montant obtenu / motif de refus) du dossier. Le suivi est
  // indexé par (projet, aide) ; il vit là où un dossier existe — donc ici.
  const allSuivis = useSuiviStore((s) => s.suivis);
  const suiviLoaded = useSuiviStore((s) => (projetId ? s.loadedProjets[projetId] : false));
  const suivi = useMemo(
    () => allSuivis.find((s) => s.projetId === projetId && s.aideId === dossier?.aideId),
    [allSuivis, projetId, dossier?.aideId],
  );

  const [aide, setAide] = useState<Aide | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [attachingItem, setAttachingItem] = useState<ChecklistItem | null>(null);
  const [depot, setDepot] = useState<{ item: ChecklistItem; fichiers: File[] } | null>(null);
  const [busyItemId, setBusyItemId] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [accessDoc, setAccessDoc] = useState<Document | null>(null);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  // Pièces en cours de vérification guidée (null = fenêtre fermée). Le tableau
  // est figé à l'ouverture pour que l'ordre des étapes ne bouge pas pendant
  // que les confirmations modifient la checklist.
  const [reviewItems, setReviewItems] = useState<ChecklistItem[] | null>(null);

  const projetFetchedRef = useRef(false);
  const autoVerifRef = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);
  // La pièce pour laquelle le sélecteur de fichiers est ouvert : gardée hors de
  // l'état, la fenêtre d'ajout se referme AVANT de rendre le document déposé.
  const itemADeposer = useRef<ChecklistItem | null>(null);

  // Relu aussi quand il vient du cache local, qui ne garde pas le rôle : c'est
  // lui qui ouvre la gestion du dossier et de ses pièces.
  const projetARelire = !projet || !!projet.depuisLeCache;
  useEffect(() => {
    if (!projetARelire || !projetId || projetFetchedRef.current) return;
    projetFetchedRef.current = true;
    projetService.getById(projetId).then(upsertProjet).catch((err) => {
      const enStore = useProjetStore.getState().projets.some((p) => p.id === projetId);
      if (!enStore || isAccessLostError(err)) setNotFound(true);
    });
  }, [projetARelire, projetId, upsertProjet]);

  // Monument parent : nom de l'en-tête, rôle, rattachement des documents.
  // Relu aussi quand il vient du cache local, qui ne garde ni son offre ni le
  // rôle : une panne passagère ne dit « introuvable » que s'il n'y a rien à
  // montrer.
  const monumentARelire = !monument || !!monument.depuisLeCache;
  useEffect(() => {
    if (!monumentId || !monumentARelire) return;
    monumentService.getById(monumentId).then(upsertMonument).catch((err) => {
      const enStore = useMonumentStore.getState().monuments.some((m) => m.id === monumentId);
      if (!enStore || isAccessLostError(err)) setNotFound(true);
    });
  }, [monumentId, monumentARelire, upsertMonument]);

  // Rafraîchir les dossiers au montage (deep link + freshness inter-comptes).
  useEffect(() => {
    dossierService.fetchAll().then(setDossiers).catch(console.error);
  }, [setDossiers]);

  useEffect(() => {
    if (dossierLoaded && !dossier) setNotFound(true);
  }, [dossierLoaded, dossier]);

  useEffect(() => { fetchDocuments().catch(() => {}); }, [fetchDocuments]);
  useEffect(() => { if (!templatesLoaded) fetchTemplates().catch(() => {}); }, [templatesLoaded, fetchTemplates]);
  useEffect(() => { if (projetId && !suiviLoaded) suiviService.fetchByProjet(projetId).catch(console.error); }, [projetId, suiviLoaded]);

  // Charge l'aide (pour rapprocher les modèles de la bibliothèque des pièces).
  useEffect(() => {
    if (!dossier?.aideId) return;
    aideService.getById(dossier.aideId).then(setAide).catch(() => {});
  }, [dossier?.aideId]);

  const templatesByItemId = useMemo(() => {
    if (!dossier || templates.length === 0) return {};
    const map: Record<string, typeof templates> = {};
    for (const item of dossier.checklist) {
      const matches = matchTemplates(templates, item.label, aide?.categorie);
      if (matches.length > 0) map[item.id] = matches;
    }
    return map;
  }, [dossier, templates, aide?.categorie]);

  // Lien de téléchargement officiel de la pièce (Cerfa / formulaire / modèle),
  // affiché en hypertexte dans « Les documents à préparer » de l'aide. Le lien est
  // perdu à la création du dossier (la checklist ne stocke que le libellé), on le
  // retrouve en rapprochant le libellé de la pièce du nom du document requis.
  const documentUrlByItemId = useMemo(() => {
    if (!dossier || !aide) return {};
    const urlByNom = new Map<string, string>();
    for (const doc of aide.documentsRequis ?? []) {
      if (typeof doc === 'object' && doc.url) urlByNom.set(doc.nom, doc.url);
    }
    const map: Record<string, string> = {};
    for (const item of dossier.checklist) {
      const url = urlByNom.get(item.label);
      if (url) map[item.id] = url;
    }
    return map;
  }, [dossier, aide]);

  // Le nom brut reste la clé de la checklist ; seul le libellé affiché vient de
  // la fiche rédigée (même règle que `piecesAide`).
  const libellePiece = useCallback(
    (label: string) => aide?.fiche?.pieces?.[label] || label,
    [aide],
  );
  const nomDocument = useCallback(
    (id: string) => documents.find((d) => d.id === id)?.nom,
    [documents],
  );

  /** Le dossier où ranger le fichier d'une pièce, quand on le sait. */
  const typeDePiece = (item: ChecklistItem): DocumentType | undefined => {
    const duReferentiel = item.pieceId
      ? digest?.piecesDemandees?.find((p) => p.pieceId === item.pieceId)?.typeDocument
      : undefined;
    return duReferentiel ?? (item.categorie === 'photographique' ? 'photo' : undefined);
  };
  const pieceDe = (item: ChecklistItem): PieceAPreremplir => ({
    pieceId: item.pieceId,
    nom: libellePiece(item.label),
    typeDocument: typeDePiece(item),
  });

  /**
   * Joindre un document à une pièce. Lève en cas d'échec : la fenêtre de choix
   * s'en sert pour rester ouverte.
   */
  const attacher = async (item: ChecklistItem, document: Document) => {
    if (!dossier || !projet) return;
    setBusyItemId(item.id);
    try {
      // Rattacher une pièce au dossier l'associe aussi au PROJET : elle apparaît
      // dans l'onglet « Documents » du chantier (et donc dans celui du monument,
      // pour son équipe) — et pas au-delà.
      if (!document.projetIds.includes(projet.id)) {
        await addToProjectsStore(document.id, [], [projet.id]);
      }
      if (!document.dossiersUtilises.includes(dossier.id)) {
        await linkToDossierStore(document.id, dossier.id);
      }
      await dossierService.updateChecklistItem(dossier.id, item.id, 'fourni', document.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors du rattachement');
      throw err;
    } finally {
      setBusyItemId(null);
    }
  };

  /** « Déposer » : le sélecteur de fichiers d'abord, puis la fenêtre d'ajout. */
  const deposer = (item: ChecklistItem) => {
    itemADeposer.current = item;
    const input = inputRef.current;
    if (!input) return;
    input.value = '';
    input.click();
  };

  const handleDeleteItem = async (item: ChecklistItem) => {
    if (!item.documentId || !dossier) return;
    const documentId = item.documentId;
    setBusyItemId(item.id);
    try {
      try { await unlinkFromDossierStore(documentId, dossier.id); }
      catch (err) {
        const msg = err instanceof Error ? err.message.toLowerCase() : '';
        const isMissing = msg.includes('404') || msg.includes('not found') || msg.includes('introuvable') || msg.includes('non trouvé') || msg.includes('failed to fetch');
        if (!isMissing) throw err;
      }
      // `detacher` plutôt qu'un simple passage à « manquant » : le retrait est
      // mémorisé sur la pièce, la reprise automatique ne reproposera pas le
      // fichier qu'on vient d'enlever.
      await dossierService.detacherChecklistItem(dossier.id, item.id);
      toast.success('Document retiré du dossier');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression');
    } finally {
      setBusyItemId(null);
    }
  };

  // Confirmer une pièce reprise n'est pas un remplacement : ouvert à tout membre
  // du projet (le backend l'exempte de la garde « auteur du document »).
  //
  // La confirmation reproduit les DEUX associations du rattachement manuel (cf.
  // attacher) : le document rejoint le projet et le dossier. C'est fait ici,
  // et non au moment de la reprise, à dessein — associer automatiquement le
  // document au projet rendrait un document « équipe » visible par toute
  // l'équipe sans que personne ne l'ait décidé. À la confirmation, l'utilisateur
  // est l'acteur explicite, comme dans le flux manuel. Sans le lien au dossier,
  // le document pourrait aussi partir en corbeille (_should_auto_trash) alors
  // qu'une pièce « fournie » le référence encore.
  const handleConfirmItem = async (item: ChecklistItem) => {
    if (!dossier || !projet || !item.documentId) return;
    const documentId = item.documentId;
    setBusyItemId(item.id);
    try {
      const doc = documents.find((d) => d.id === documentId)
        ?? await documentService.getById(documentId);
      // Au PROJET, pas au monument : même périmètre que le rattachement manuel
      // (attacher) — la pièce apparaît pour l'équipe du chantier, pas au-delà.
      if (!doc.projetIds.includes(projet.id)) {
        await addToProjectsStore(doc.id, [], [projet.id]);
      }
      if (!doc.dossiersUtilises.includes(dossier.id)) {
        await linkToDossierStore(doc.id, dossier.id);
      }
      await dossierService.updateChecklistItem(dossier.id, item.id, 'fourni');
      // Le document venait d'ailleurs : il n'était pas dans le store, les mises à
      // jour optimistes ci-dessus n'ont donc rien pu y refléter. Sans ce rechargement,
      // `canModifyItem` le croirait absent et masquerait « Remplacer ».
      fetchDocuments().catch(() => {});
      toast.success('Pièce confirmée');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la confirmation');
    } finally {
      setBusyItemId(null);
    }
  };

  // Rejeter une pièce reprise détache son document : contrairement à la
  // confirmation, cette action reste soumise à la garde d'accès du backend
  // (seul l'auteur du document, ou un chef de projet/adjoint, peut la retirer —
  // 403 sinon).
  const handleRejectItem = async (item: ChecklistItem) => {
    if (!dossier) return;
    setBusyItemId(item.id);
    try {
      await dossierService.detacherChecklistItem(dossier.id, item.id);
      toast.success('Pièce retirée du dossier');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors du rejet de la pièce');
    } finally {
      setBusyItemId(null);
    }
  };

  const ouvrirVerification = useCallback((d: Dossier) => {
    const repris = d.checklist.filter((i) => i.statut === 'repris');
    if (repris.length > 0) setReviewItems(repris);
    return repris.length;
  }, []);

  // Remplacer / supprimer une pièce : l'auteur du document, OU un chef de projet /
  // adjoint (tous les droits sur les docs). Un collaborateur ne peut agir que sur
  // les siens. Consultation ouverte à tous.
  const canManageAnyDoc = projectPermissions(projet?.myRole ?? null).canDeleteAnyDoc;
  const canModifyItem = useCallback(
    (item: ChecklistItem) =>
      !!item.documentId &&
      (canManageAnyDoc ||
        documents.some((d) => d.id === item.documentId && d.userId === currentUserId)),
    [documents, currentUserId, canManageAnyDoc],
  );

  const canManageDossier = projectPermissions(projet?.myRole ?? null).canEditProject;

  // Reprise automatique à l'arrivée sur le dossier : c'est le SEUL déclencheur,
  // il n'y a volontairement aucun bouton à connaître. L'appel est silencieux
  // (la reprise est un confort, son échec ne doit rien casser) et tourne à
  // chaque visite pour attraper les fichiers déposés entre-temps. La fenêtre de
  // vérification, elle, ne s'ouvre d'office qu'une fois par session et par
  // dossier — la fermer vaut « plus tard », et la bannière reste le chemin
  // volontaire pour y revenir.
  useEffect(() => {
    if (!dossier || !monument || autoVerifRef.current) return;
    autoVerifRef.current = true;
    const dejaVue = !!sessionStorage.getItem(`verif-reprises-${dossier.id}`);
    if (canManageDossier && dossier.statut !== 'soumis') {
      dossierService
        .reprendrePieces(dossier.id)
        .then((maj) => { if (!dejaVue) ouvrirVerification(maj); })
        .catch(() => { if (!dejaVue) ouvrirVerification(dossier); });
    } else if (!dejaVue) {
      // Membre simple : pas le droit de relancer la reprise, mais il peut
      // confirmer les pièces déjà reprises — on lui ouvre la vérification.
      ouvrirVerification(dossier);
    }
  }, [dossier, monument, canManageDossier, ouvrirVerification]);

  const handleDeleteDossier = async () => {
    if (!dossier || !projetId) return;
    setDeleting(true);
    try {
      await dossierService.delete(dossier.id);
      toast.success('Dossier supprimé — l’aide redevient disponible');
      navigate(`${ROUTES.PROJET_DETAIL(projetId)}?tab=dossiers`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression du dossier');
      setDeleting(false);
    }
  };

  const handlePreview = async (documentId: string) => {
    const existing = documents.find((d) => d.id === documentId);
    if (existing) { setPreviewDoc(existing); return; }
    try {
      const doc = await documentService.getById(documentId);
      setPreviewDoc(doc);
      fetchDocuments().catch(() => {});
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Document introuvable');
    }
  };

  // Téléchargement de l'ensemble des pièces en un zip. Le backend n'y met que
  // les documents que l'appelant a le droit de consulter : une pièce « Réservé »
  // est absente de l'archive, sans erreur.
  const handleDownloadAll = async () => {
    if (!dossier) return;
    setDownloading(true);
    try {
      await dossierService.downloadArchive(dossier.id, dossier.titre);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Téléchargement impossible');
    } finally {
      setDownloading(false);
    }
  };

  if (notFound) {
    return (
      <div className="ec pproj pdos">
        <BoutonRetour
          to={projetId ? ROUTES.PROJET_DETAIL(projetId) : ROUTES.MONUMENTS}
          libelle={projetId ? 'Retour au projet' : 'Retour à mes monuments'}
        />
        <div className="vide pdos-introuvable">
          <h1>Dossier introuvable</h1>
          <p>Il a peut-être été supprimé, ou vous n'avez plus accès à ce projet.</p>
        </div>
      </div>
    );
  }

  if (!dossier || !projet || !monument) return <DossierDetailSkeleton />;

  const [aideName] = dossier.titre.split(' — ');
  const nomProjet = projetTitre(projet, monument.nom);
  const aRepris = dossier.checklist.filter((i) => i.statut === 'repris').length;
  const aDesPieces = dossier.checklist.some((i) => i.documentId);
  const lienAide = dossier.aideId ? ROUTES.PROJET_AIDE(projet.id, dossier.aideId) : null;
  const montant = aide ? montantAide(aide) : null;
  const chapeau = aide ? chapeauAide(aide) : '';

  return (
    <div className="ec pproj pdos">
      <BoutonRetour to={`${ROUTES.PROJET_DETAIL(projet.id)}?tab=dossiers`} libelle={`Retour à ${nomProjet}`} />

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTR}
        className="sr"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          const fichier = e.target.files?.[0];
          const item = itemADeposer.current;
          if (fichier && item) setDepot({ item, fichiers: [fichier] });
        }}
      />

      <section className="phead" aria-labelledby="dt">
        <div>
          <p className="pdos-lieu">
            <Link className="lieu" to={`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=projets`}>{monument.nom}</Link>
            <span aria-hidden="true">/</span>
            <Link className="lieu" to={`${ROUTES.PROJET_DETAIL(projet.id)}?tab=dossiers`}>{nomProjet}</Link>
          </p>
          <h1 id="dt">
            {aideName}
            {dossier.statut === 'soumis' && <span className="clos">Déposé</span>}
          </h1>
          <p className="pdos-sous">Dossier de candidature</p>
        </div>
        <div className="proj-act">
          {aDesPieces && (
            <button className="btn b-blue" type="button" onClick={handleDownloadAll} disabled={downloading}>
              {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Picto nom="telecharger" />}
              {downloading ? 'Préparation…' : 'Télécharger le dossier'}
            </button>
          )}
          {lienAide && (
            <Link className="btn b-line" to={lienAide}>
              <Picto nom="livre" />Voir la fiche de l'aide
            </Link>
          )}
        </div>
      </section>

      {AVANCEMENT_MODIFIABLE && projetId && dossier.aideId && (
        <AideStatutSelect projetId={projetId} aideId={dossier.aideId} suivi={suivi} />
      )}

      {aRepris > 0 && (
        <div className="pdos-rep">
          <span className="gi"><Picto nom="refaire" /></span>
          <div>
            <b>
              {aRepris === 1
                ? 'Une pièce a été remplie avec un fichier déjà envoyé'
                : `${aRepris} pièces ont été remplies avec des fichiers déjà envoyés`}
            </b>
            <p>Vérifiez que ce sont les bons : tant qu’ils ne sont pas confirmés, ces pièces ne comptent pas dans votre dossier.</p>
          </div>
          <button className="btn b-blue b-sm" type="button" onClick={() => ouvrirVerification(dossier)}>
            Vérifier maintenant
          </button>
        </div>
      )}

      <DossierChecklist
        items={dossier.checklist}
        projetId={projet.id}
        templatesByItemId={templatesByItemId}
        documentUrlByItemId={documentUrlByItemId}
        libelle={libellePiece}
        nomDocument={nomDocument}
        onRequestDeposer={deposer}
        onRequestAttach={(item) => setAttachingItem(item)}
        onPreview={handlePreview}
        onRequestDelete={handleDeleteItem}
        onConfirm={handleConfirmItem}
        onReject={handleRejectItem}
        canModifyItem={canModifyItem}
        busyItemId={busyItemId}
        readOnly={dossier.statut === 'soumis'}
      />

      <div className="pdos-manuel">
        <span className="gi"><Picto nom="main" /></span>
        <p>
          <b>Le dépôt reste à faire par vos soins.</b> Monumia vous aide à préparer le dossier ;
          c'est à vous de l'envoyer à l'organisme, par son guichet ou par courrier.
        </p>
      </div>

      {aide && lienAide && (
        <section className="sec" aria-labelledby="pdos-aide">
          <div className="sec-h">
            <div>
              <h2 id="pdos-aide">L'aide</h2>
              <p>Ses conditions, son montant et la marche à suivre sont sur sa fiche.</p>
            </div>
          </div>
          <Link className="pdos-aide" to={lienAide}>
            <div className="c-tags">
              {financeurAide(aide) && <span className="c-tag f">{financeurAide(aide)}</span>}
              <span className="c-tag d">{guichet(aide).libelle}</span>
            </div>
            <h3>{titreAide(aide)}</h3>
            {chapeau && <p className="desc">{chapeau}</p>}
            <span className="pdos-aide-f">
              {montant?.valeur && <b>{montant.valeur}</b>}
              <span className="q-l">Ouvrir la fiche<Picto nom="fleche" /></span>
            </span>
          </Link>
        </section>
      )}

      {canManageDossier && (
        <div className="flex justify-end pt-8">
          <button
            onClick={() => setConfirmDeleteOpen(true)}
            disabled={deleting}
            className="inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[15px] font-semibold transition-colors hover:bg-destructive-muted disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            style={{ borderColor: C.border, color: C.danger }}
          >
            {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <IconSupprimer className="h-4 w-4" strokeWidth={1.8} />}
            Supprimer le dossier
          </button>
        </div>
      )}

      <AlertDialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce dossier ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le dossier et ses pièces rattachées seront retirés. L'aide redeviendra disponible dans l'onglet « Aides ». Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Annuler</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleDeleteDossier} disabled={deleting}>
              {deleting ? 'Suppression…' : 'Supprimer'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* « Déposer » : la pièce déposée pend au chantier et à lui seul, comme
          depuis l'onglet Documents du projet, et porte la pièce du référentiel. */}
      <UploadDocumentDialog
        open={!!depot}
        onOpenChange={(o) => { if (!o) setDepot(null); }}
        fichiers={depot?.fichiers}
        piece={depot ? pieceDe(depot.item) : null}
        projetIds={[projet.id]}
        choixMonuments={false}
        onUploaded={(docs) => {
          const item = itemADeposer.current;
          const doc = docs[0];
          if (!item || !doc) return;
          // Créé avec un défaut sûr (chef + adjoints) : « Gérer l'accès » s'ouvre
          // aussitôt pour que l'auteur choisisse qui peut le voir.
          attacher(item, doc).then(() => setAccessDoc(doc)).catch(() => {});
        }}
      />
      <AttachDocumentDialog
        open={!!attachingItem}
        onOpenChange={(open) => { if (!open) setAttachingItem(null); }}
        projetId={projet.id}
        defaultName={attachingItem ? libellePiece(attachingItem.label) : undefined}
        pieceId={attachingItem?.pieceId}
        typeParDefaut={attachingItem ? typeDePiece(attachingItem) : null}
        onAttach={async (doc) => {
          if (!attachingItem) return;
          await attacher(attachingItem, doc);
          toast.success('Document joint au dossier');
        }}
        onUploaded={(doc) => setAccessDoc(doc)}
      />
      {accessDoc && (
        <ManageDocumentAccessDialog
          document={accessDoc}
          myRole={projet.myRole ?? null}
          open={!!accessDoc}
          onOpenChange={(open) => { if (!open) setAccessDoc(null); }}
          onSaved={() => { fetchDocuments().catch(() => {}); }}
        />
      )}

      <DocumentPreviewDialog
        document={previewDoc}
        open={!!previewDoc}
        onOpenChange={(open) => { if (!open) setPreviewDoc(null); }}
      />

      <ReprisesReviewDialog
        open={!!reviewItems}
        onOpenChange={(open) => {
          if (!open) {
            setReviewItems(null);
            if (dossier) sessionStorage.setItem(`verif-reprises-${dossier.id}`, '1');
          }
        }}
        items={reviewItems ?? []}
        onConfirm={handleConfirmItem}
        onReject={handleRejectItem}
      />
    </div>
  );
}
