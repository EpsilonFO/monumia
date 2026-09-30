import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router';
import { ChevronLeft, Loader2 } from 'lucide-react';
import { IconDocument, IconAttention, IconSupprimer, IconLivre, IconRafraichir } from '@/components/icons';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { EmptyState } from '@/components/shared/EmptyState';
import { AideDetails } from '@/components/aide/AideDetails';
import { AideStatutSelect } from '@/components/aide/AideStatutSelect';
import { DossierChecklist } from '@/components/dossier/DossierChecklist';
import { ReprisesReviewDialog } from '@/components/dossier/ReprisesReviewDialog';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { DossierDetailSkeleton } from '@/components/skeletons';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useTemplateStore } from '@/stores/useTemplateStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { useOffre } from '@/hooks/useOffre';
import { libelleMonuments } from '@/lib/offres';
import { matchTemplates } from '@/lib/template-matching';
import { projectPermissions } from '@/lib/project-permissions';
import { monumentService } from '@/services/monument.service';
import { projetService } from '@/services/projet.service';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { documentService } from '@/services/document.service';
import { suiviService } from '@/services/suivi.service';
import { projetTitre } from '@/lib/projet-titre';
import { C, SERIF } from '@/lib/brand';
import { ROUTES } from '@/constants/routes';
import { isAccessLostError } from '@/lib/api-error';
import { toast } from 'sonner';
import type { Aide, ChecklistItem, Document, Dossier } from '@/types';
import { BoutonRetour } from '@/components/shared/ecrans/BoutonRetour';

/**
 * Le sélecteur d'avancement (« À faire », « En préparation », « Déposé »…) est
 * masqué pour l'instant, en haut du dossier ouvert. Rien d'autre ne change : le
 * suivi continue d'exister en base, de se charger ici et d'alimenter les
 * vignettes et l'échéancier — seul son éditeur disparaît de cette page.
 *
 * Remettre `true` le rend tel quel.
 */
const AVANCEMENT_MODIFIABLE = false;

export function DossierDetailPage() {
  const { projetId, dossierId } = useParams();
  const navigate = useNavigate();
  const offreCompte = useOffre();

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
  const [busyItemId, setBusyItemId] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [accessDoc, setAccessDoc] = useState<Document | null>(null);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // Pièces en cours de vérification guidée (null = fenêtre fermée). Le tableau
  // est figé à l'ouverture pour que l'ordre des étapes ne bouge pas pendant
  // que les confirmations modifient la checklist.
  const [reviewItems, setReviewItems] = useState<ChecklistItem[] | null>(null);

  const projetFetchedRef = useRef(false);
  const autoVerifRef = useRef(false);

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

  // Monument parent : nom du fil d'Ariane, rôle, rattachement des documents.
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

  const handleAttach = async (document: Document) => {
    if (!attachingItem || !dossier || !projet) return;
    const itemId = attachingItem.id;
    setBusyItemId(itemId);
    try {
      // Rattacher une pièce au dossier l'associe aussi au PROJET : elle apparaît
      // dans l'onglet « Documents » du chantier, pour son équipe — et pas au-delà.
      if (!document.projetIds.includes(projet.id)) {
        await addToProjectsStore(document.id, [], [projet.id]);
      }
      if (!document.dossiersUtilises.includes(dossier.id)) {
        await linkToDossierStore(document.id, dossier.id);
      }
      await dossierService.updateChecklistItem(dossier.id, itemId, 'fourni', document.id);
      toast.success('Document rattaché');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors du rattachement');
      throw err;
    } finally {
      setBusyItemId(null);
    }
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
  // handleAttach) : le document rejoint le projet et le dossier. C'est fait ici,
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
      // (handleAttach) — la pièce apparaît pour l'équipe du chantier, pas au-delà.
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

  if (notFound) {
    return (
      <div className="space-y-4">
        <h1 className="text-[23px]" style={{ fontFamily: SERIF, color: C.ink }}>Dossier introuvable</h1>
        <Link to={projetId ? ROUTES.PROJET_DETAIL(projetId) : ROUTES.MONUMENTS} className="inline-flex items-center gap-1.5 text-[15px] font-medium" style={{ color: C.blue }}>
          <ChevronLeft className="h-3.5 w-3.5" /> Retour au projet
        </Link>
      </div>
    );
  }

  if (!dossier || !projet || !monument) return <DossierDetailSkeleton />;

  const [aideName] = dossier.titre.split(' — ');

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <BoutonRetour to={`${ROUTES.PROJET_DETAIL(projet.id)}?tab=dossiers`} libelle={`Retour à ${projetTitre(projet, monument.nom)}`} />
        <div className="flex items-center gap-2 overflow-hidden text-[15px] text-muted-foreground">
          <Link to={ROUTES.MONUMENTS} className="shrink-0 hover:opacity-70 transition-opacity">{libelleMonuments(offreCompte)}</Link>
          <span>/</span>
          <Link to={`${ROUTES.MONUMENT_DETAIL(monument.id)}?tab=projets`} className="truncate hover:opacity-70 transition-opacity">{monument.nom}</Link>
          <span>/</span>
          <Link to={`${ROUTES.PROJET_DETAIL(projet.id)}?tab=dossiers`} className="truncate hover:opacity-70 transition-opacity">{projetTitre(projet, monument.nom)}</Link>
          <span>/</span>
          <span className="truncate" style={{ color: C.ink }}>{aideName}</span>
        </div>
      </div>

      <h1 className="text-[clamp(1.4rem,3vw,1.9rem)] leading-tight" style={{ fontFamily: SERIF, color: C.ink }}>{dossier.titre}</h1>

      {AVANCEMENT_MODIFIABLE && projetId && dossier.aideId && (
        <AideStatutSelect projetId={projetId} aideId={dossier.aideId} suivi={suivi} />
      )}

      <div className="space-y-6">
        {dossier.checklist.some((i) => i.statut === 'repris') && (
          <div className="flex flex-wrap items-center gap-4 p-4 sm:p-5 rounded-xl border" style={{ borderColor: C.border, background: C.paleBlue }}>
            <IconRafraichir className="h-5 w-5 shrink-0" style={{ color: C.blue }} />
            <div className="min-w-0 flex-1 text-[16px]">
              <p className="font-semibold" style={{ color: C.ink }}>
                {(() => {
                  const n = dossier.checklist.filter((i) => i.statut === 'repris').length;
                  return n === 1
                    ? 'Une pièce a été remplie avec un fichier déjà envoyé'
                    : `${n} pièces ont été remplies avec des fichiers déjà envoyés`;
                })()}
              </p>
              <p className="mt-0.5" style={{ color: C.grayFg }}>
                Vérifiez que ce sont les bons — tant qu’ils ne sont pas confirmés, ces pièces ne comptent pas dans votre dossier.
              </p>
            </div>
            <button
              type="button"
              onClick={() => ouvrirVerification(dossier)}
              className="inline-flex shrink-0 items-center gap-2 rounded-xl px-5 py-3 text-[17px] font-semibold text-white transition-opacity hover:opacity-90"
              style={{ background: C.blue }}
            >
              Vérifier maintenant
            </button>
          </div>
        )}

        <div className="rounded-2xl border overflow-hidden" style={{ background: C.card, borderColor: C.border }}>
          <div className="px-5 py-3 border-b" style={{ borderColor: C.border }}>
            <h3 className="text-[18px]" style={{ fontFamily: SERIF, color: C.ink }}>Pièces du dossier</h3>
          </div>
          <div className="px-5 py-4">
            {dossier.checklist.length === 0 ? (
              <EmptyState icon={IconDocument} title="Aucune pièce" description="Ce dossier ne comporte aucune pièce à fournir." />
            ) : (
              <DossierChecklist
                items={dossier.checklist}
                templatesByItemId={templatesByItemId}
                documentUrlByItemId={documentUrlByItemId}
                onRequestAttach={(item) => setAttachingItem(item)}
                onPreview={handlePreview}
                onRequestDelete={handleDeleteItem}
                onConfirm={handleConfirmItem}
                onReject={handleRejectItem}
                canModifyItem={canModifyItem}
                archiveName={dossier.titre}
                busyItemId={busyItemId}
                readOnly={dossier.statut === 'soumis'}
              />
            )}
          </div>
        </div>

        <div className="flex items-start gap-3 p-4 rounded-xl border" style={{ borderColor: C.orangeVif, background: C.paleOrange }}>
          <IconAttention className="h-5 w-5 shrink-0 mt-0.5" style={{ color: C.orange }} />
          <div className="text-[15px]">
            <p className="font-semibold" style={{ color: C.ink }}>Dépôt manuel obligatoire</p>
            <p className="mt-0.5 text-muted-foreground">Monumia vous aide à préparer votre dossier, mais le dépôt auprès de l'organisme doit être effectué par vos soins.</p>
          </div>
        </div>

        {aide && (
          <div className="space-y-3 pt-2">
            <h3 className="flex items-center gap-2 text-[18px]" style={{ fontFamily: SERIF, color: C.ink }}>
              <IconLivre className="h-4 w-4" style={{ color: C.blue }} />À propos de l'aide
            </h3>
            <AideDetails
              aide={aide}
              monumentName={monument.nom}
              showHeader={false}
              showDocumentsRequis={false}
              aside={canManageDossier ? (
                <button
                  onClick={() => setConfirmDeleteOpen(true)}
                  disabled={deleting}
                  className="inline-flex w-full items-center justify-center gap-2 px-4 py-2 text-[15px] font-semibold rounded-lg border transition-colors hover:bg-destructive-muted disabled:opacity-60 text-destructive border-destructive/30"
                >
                  {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <IconSupprimer className="h-4 w-4" strokeWidth={1.8} />}
                  Supprimer le dossier
                </button>
              ) : undefined}
            />
          </div>
        )}
      </div>

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

      <AttachDocumentDialog
        open={!!attachingItem}
        onOpenChange={(open) => { if (!open) setAttachingItem(null); }}
        projetId={projet.id}
        defaultName={attachingItem?.label}
        onAttach={handleAttach}
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
