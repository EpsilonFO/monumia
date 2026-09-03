import { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router';
import { ChevronLeft } from 'lucide-react';
import {
  type IconComponent,
  IconProjet, IconEquipe, IconDocuments, IconDepot, IconMonument, IconAjouter,
} from '@/components/icons';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { EmptyState } from '@/components/shared/EmptyState';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { MonumentFiche } from '@/components/monument/MonumentFiche';
import { MonumentSummaryBar } from '@/components/monument/MonumentSummaryBar';
import { ProjetCard } from '@/components/projet/ProjetCard';
import { DocumentCard } from '@/components/document/DocumentCard';
import { DocumentGrid } from '@/components/document/DocumentGrid';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { AddToProjectDialog } from '@/components/document/AddToProjectDialog';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { TeamPanel } from '@/components/sharing/TeamPanel';
import { projectPermissions } from '@/lib/project-permissions';
import { ProjectDetailSkeleton } from '@/components/skeletons';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { monumentService } from '@/services/monument.service';
import { projetService } from '@/services/projet.service';
import { documentService } from '@/services/document.service';
import { dossierService } from '@/services/dossier.service';
import { sharingService } from '@/services/sharing.service';
import { computeMonumentStats, computeProjectStats, projectStage } from '@/lib/project-stats';
import { useOffre, useOffreMonument } from '@/hooks/useOffre';
import { libelleMonuments, sousLePlafond } from '@/lib/offres';
import { PaywallDialog, PaywallOverlay } from '@/components/shared/Paywall';
import { C, SERIF } from '@/lib/brand';
import { isAccessLostError } from '@/lib/api-error';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import type { Monument, Document, ProjectMember, ProjectInvitation } from '@/types';

/**
 * Page d'un MONUMENT : la fiche du bien et tout ce qui s'y rattache
 * durablement — sa fiche sanitaire, ses projets de travaux, ses documents, son
 * équipe. Les aides et les dossiers, eux, appartiennent à un chantier précis et
 * vivent sur la page du projet.
 */
export function MonumentDetailPage() {
  const { monumentId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId));
  const upsertMonument = useMonumentStore((s) => s.upsertMonument);
  const updateMonument = useMonumentStore((s) => s.updateMonument);
  const deleteMonument = useMonumentStore((s) => s.deleteMonument);

  const allProjets = useProjetStore((s) => s.projets);
  const setProjets = useProjetStore((s) => s.setProjets);
  const projets = useMemo(
    () => allProjets.filter((p) => p.monumentId === monumentId),
    [allProjets, monumentId],
  );

  const allDossiers = useDossierStore((s) => s.dossiers);
  const dossiers = useMemo(
    () => allDossiers.filter((d) => d.monumentId === monumentId),
    [allDossiers, monumentId],
  );

  const digestsByProjet = useAideStore((s) => s.digestsByProjet);
  const suivis = useSuiviStore((s) => s.suivis);

  // Documents du monument : on charge TOUS les documents qui y sont rattachés
  // (tous les membres confondus) via le fetch monument-scopé, pas le store « mes
  // documents ». Sans ça, un owner/co_owner ne verrait jamais les pièces déposées
  // par un collaborateur.
  const [monumentDocuments, setMonumentDocuments] = useState<Document[]>([]);

  const [notFound, setNotFound] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [addToProjectDoc, setAddToProjectDoc] = useState<Document | null>(null);
  const [addDocOpen, setAddDocOpen] = useState(false);
  const [accessDoc, setAccessDoc] = useState<Document | null>(null);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [invitations, setInvitations] = useState<ProjectInvitation[]>([]);
  const [paywallProjet, setPaywallProjet] = useState(false);

  // L'offre qui gouverne CE bien, et non celle du compte : un architecte
  // invité par un client abonné doit pouvoir lancer un chantier de plus.
  const offre = useOffreMonument(monumentId);
  // Le fil d'Ariane remonte à l'espace du COMPTE : c'est son plafond à lui
  // qui décide du singulier, pas l'offre qui gouverne ce monument-ci.
  const offreCompte = useOffre();
  const peutCreerProjet = sousLePlafond(offre.projetsMax, projets.length);

  // Travailler à plusieurs est un service de l'offre Veille. L'onglet Équipe
  // reste VISIBLE au gratuit — c'est une porte, pas un vide — mais il mène aux
  // tarifs plutôt qu'à un formulaire que le serveur refuserait (402).
  //
  // Il s'ouvre quand même si une équipe existe déjà, et ce n'est pas une
  // politesse : après une résiliation, les collaborateurs gardent leur accès.
  // Renvoyer alors vers les tarifs le rendrait irrévocable. On laisse donc
  // gérer ce qui est là, sans pouvoir y ajouter (cf. TeamPanel).
  const equipeAccessible = offre.equipe || members.length > 1 || invitations.length > 0;

  const tabParam = searchParams.get('tab');
  // Onglet par défaut : les Projets. Ouvrir un monument sert le plus souvent à
  // reprendre un chantier ; la fiche, elle, ne bouge quasiment plus une fois
  // remplie.
  const requestedTab =
    tabParam === 'sanitaire' || tabParam === 'documents' || tabParam === 'equipe'
      ? tabParam
      : 'projets';
  const handleTabChange = useCallback((value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', value);
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  // Rafraîchir au montage (et quand on change de monument) : revenir sur la page
  // doit refléter les changements des autres membres, sans recharger le navigateur.
  useEffect(() => {
    if (!monumentId) return;
    monumentService.getById(monumentId)
      .then(upsertMonument)
      .catch(() => {
        if (!useMonumentStore.getState().monuments.some((m) => m.id === monumentId)) {
          setNotFound(true);
        }
      });
  }, [monumentId, upsertMonument]);

  // Les projets du monument : rafraîchis à l'arrivée, fusionnés dans le store
  // global (qui porte aussi ceux des autres monuments, chargés par le dashboard).
  useEffect(() => {
    if (!monumentId) return;
    projetService
      .listByMonument(monumentId)
      .then((rows) => {
        const autres = useProjetStore.getState().projets.filter((p) => p.monumentId !== monumentId);
        setProjets([...rows, ...autres]);
      })
      .catch(console.error);
  }, [monumentId, setProjets]);

  useEffect(() => { dossierService.fetchAll().catch(console.error); }, []);

  // Réservé à l'équipe du monument : la route refuse les accès par projet, et
  // l'appeler pour rien afficherait une erreur dans la console à chaque visite.
  const peutVoirLeMonument = !!monument?.myRole;
  const reloadMonumentDocuments = useCallback(() => {
    if (!monumentId || !peutVoirLeMonument) return;
    documentService.getAll({ monumentId }).then(setMonumentDocuments).catch(() => {});
  }, [monumentId, peutVoirLeMonument]);
  useEffect(() => { reloadMonumentDocuments(); }, [reloadMonumentDocuments]);

  const reloadMembers = useCallback(() => {
    if (!monumentId || !peutVoirLeMonument) return;
    sharingService
      .getMembers(monumentId)
      .then((data) => {
        setMembers(data.members);
        setInvitations(data.invitations);
      })
      .catch((err) => {
        // Perte d'accès définitive (monument supprimé par le chef, membre retiré,
        // ou départ déjà effectué) : on purge le cache local et on bascule sur
        // l'écran « introuvable ». Sur une erreur transitoire (réseau, 5xx), on
        // ne touche à rien pour ne pas éjecter l'utilisateur à tort.
        if (isAccessLostError(err)) {
          deleteMonument(monumentId);
          setNotFound(true);
        }
      });
  }, [monumentId, peutVoirLeMonument, deleteMonument]);
  useEffect(() => { reloadMembers(); }, [reloadMembers]);

  const uploaderNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const m of members) map[m.userId] = `${m.prenom} ${m.nom}`.trim();
    return map;
  }, [members]);

  // Un onglet réservé à l'équipe du monument demandé par quelqu'un qui n'en est
  // pas membre retombe sur l'onglet par défaut : le serveur refuserait de toute
  // façon. Même repli pour l'onglet Équipe hors offre — arriver par un lien
  // gardé en favori affiche le monument, là où un clic délibéré mène aux
  // tarifs : on n'éjecte pas quelqu'un qui voulait simplement ouvrir sa fiche.
  const activeTab =
    (!monument?.myRole && (requestedTab === 'documents' || requestedTab === 'equipe'))
      ? 'projets'
      : requestedTab;

  const stats = useMemo(
    () => (monument ? computeMonumentStats(monument, projets, digestsByProjet, dossiers) : null),
    [monument, projets, digestsByProjet, dossiers],
  );

  const dossierNames = useMemo(
    () => Object.fromEntries(allDossiers.map((d) => [d.id, d.titre])),
    [allDossiers],
  );
  const monumentNames = useMemo(
    () => (monument ? { [monument.id]: monument.nom } : {}),
    [monument],
  );

  // Le bouton garde son libellé et son geste, et c'est le paywall qui se pose
  // devant quand le plafond est atteint : refermer la modale laisse
  // l'utilisateur là où il était, ce qu'une redirection vers les tarifs ne
  // permet pas.
  const goNouveauProjet = useCallback(() => {
    if (!peutCreerProjet) {
      setPaywallProjet(true);
      return;
    }
    if (monumentId) navigate(ROUTES.PROJET_NEW(monumentId));
  }, [peutCreerProjet, monumentId, navigate]);

  if (notFound || (!monument && !monumentId)) {
    return (
      <div className="space-y-4">
        <h1 className="text-[20px]" style={{ fontFamily: SERIF, color: C.ink }}>Monument introuvable</h1>
        <p className="text-[14px] text-muted-foreground">Ce monument n'existe pas ou a été supprimé.</p>
        <Link to={ROUTES.MONUMENTS} className="inline-flex items-center gap-1.5 text-[13px] font-medium" style={{ color: C.blue }}>
          <ChevronLeft className="h-3.5 w-3.5" /> Retour à mes monuments
        </Link>
      </div>
    );
  }

  if (!monument || !stats) return <ProjectDetailSkeleton />;

  const handleSave = async (data: Partial<Monument>) => {
    setSaving(true);
    try {
      const updated = await monumentService.update(monument.id, data);
      updateMonument(monument.id, updated);
      setIsEditing(false);
      toast.success('Monument mis à jour');
    } catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors de la sauvegarde'); }
    finally { setSaving(false); }
  };

  // Supprimer le monument emporte ses projets, dossiers et suivis (cascade en
  // base). Les dossiers sont supprimés d'abord pour que le store local reste
  // cohérent si la suppression du monument échoue à mi-chemin.
  const handleDelete = async () => {
    setConfirmDeleteOpen(false);
    setDeleting(true);
    try {
      for (const dossier of dossiers) await dossierService.delete(dossier.id);
      await monumentService.delete(monument.id);
      deleteMonument(monument.id);
      toast.success('Monument supprimé');
      navigate(ROUTES.MONUMENTS);
    } catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression'); }
    finally { setDeleting(false); }
  };

  const handleRename = async (id: string, newName: string) => {
    try { await documentService.update(id, { nom: newName }); reloadMonumentDocuments(); toast.success('Document renommé'); }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors du renommage'); }
  };
  const handleDeleteDocument = async (id: string) => {
    try { await documentService.delete(id); reloadMonumentDocuments(); toast.success('Document supprimé'); }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression'); }
  };
  // Ajout d'un document au monument (onglet Documents) : tout membre peut déposer.
  // Le document est associé au monument (s'il ne l'est pas déjà), sans rattachement
  // à un dossier précis. Un document fraîchement téléversé l'est déjà.
  const handleAddDocument = async (doc: Document) => {
    if (!monumentId) return;
    try {
      if (!doc.monumentIds.includes(monumentId)) {
        await documentService.addToProjects(doc.id, [monumentId]);
      }
      reloadMonumentDocuments();
      toast.success('Document ajouté au monument');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur lors de l'ajout");
      throw err;
    }
  };

  if (isEditing) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <button onClick={() => setIsEditing(false)} className="inline-flex items-center gap-1.5 text-[13px] font-medium" style={{ color: C.blue }}>
            <ChevronLeft className="h-3.5 w-3.5" /> Retour
          </button>
          <h1 className="text-[18px]" style={{ fontFamily: SERIF, color: C.ink }}>Modifier — {monument.nom}</h1>
        </div>
        <MonumentForm initialData={monument} onSubmit={handleSave} isEditing saving={saving} />
      </div>
    );
  }

  const canEdit = projectPermissions(monument.myRole ?? null).canEditProject;
  // `myRole` nul = accès obtenu via UN de ses projets : la fiche sanitaire est
  // lisible, le reste du monument non (cf. require_monument_read côté serveur).
  // L'onglet Projets ne liste alors que les chantiers de la personne, filtrés
  // par l'API — on masque simplement ce qui n'a pas de contenu pour elle.
  const equipeDuMonument = !!monument.myRole;

  // Monté une seule fois, que l'offre l'ouvre ou non : c'est le même panneau,
  // seul son habillage change.
  const equipePanel = (
    <TeamPanel
      scope="monument"
      scopeId={monument.id}
      invitationsOuvertes={offre.equipe}
      myRole={monument.myRole ?? null}
      members={members}
      invitations={invitations}
      onChanged={reloadMembers}
      onLeft={() => { deleteMonument(monument.id); navigate(ROUTES.MONUMENTS); }}
    />
  );

  const tabs: { value: string; label: string; icon: IconComponent; count: number | null }[] = [
    { value: 'sanitaire', label: 'Fiche monument', icon: IconMonument, count: null },
    { value: 'projets', label: 'Projets', icon: IconProjet, count: projets.length },
    ...(equipeDuMonument
      ? [
          { value: 'documents', label: 'Documents', icon: IconDocuments, count: monumentDocuments.length },
          { value: 'equipe', label: 'Équipe', icon: IconEquipe, count: members.length },
        ]
      : []),
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
        <Link to={ROUTES.MONUMENTS} className="hover:opacity-70 transition-opacity">{libelleMonuments(offreCompte)}</Link>
        <span>/</span>
        <span style={{ color: C.ink }}>{monument.nom}</span>
      </div>

      <MonumentSummaryBar
        monument={monument}
        members={members}
        onNouveauProjet={goNouveauProjet}
      />

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <div role="tablist" aria-label="Sections du monument" className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          {tabs.map(({ value, label, icon: Icon, count }) => {
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

        {/* FICHE SANITAIRE */}
        <TabsContent value="sanitaire" className="mt-4 space-y-4">
          {canEdit && (
            <div className="flex justify-end">
              <button
                onClick={() => setIsEditing(true)}
                className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-[13px] font-semibold text-white transition-all duration-200 hover:shadow-md"
                style={{ background: C.blue }}
              >
                Modifier la fiche
              </button>
            </div>
          )}
          <MonumentFiche
            monument={monument}
            // Deux conditions, et elles ne disent pas la même chose : le rôle
            // dit « ce compte a-t-il le droit », l'offre dit « ce produit le
            // permet-il ». Aucune ne remplace l'autre.
            canDelete={
              projectPermissions(monument.myRole ?? null).canDeleteProject &&
              offre.suppressionMonument
            }
            deleting={deleting}
            onDelete={() => setConfirmDeleteOpen(true)}
          />
        </TabsContent>

        {/* PROJETS */}
        <TabsContent value="projets" className="mt-4 space-y-4">
          {projets.length > 0 ? (
            <>
              {canEdit && (
                <div className="flex justify-end">
                  <button
                    onClick={goNouveauProjet}
                    className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-[13px] font-semibold text-white transition-all duration-200 hover:shadow-md"
                    style={{ background: C.orange }}
                  >
                    <IconAjouter className="h-3.5 w-3.5" strokeWidth={2} />
                    Nouveau projet
                  </button>
                </div>
              )}
              <div className="space-y-4">
                {projets.map((projet) => (
                  <ProjetCard
                    key={projet.id}
                    projet={projet}
                    stats={computeProjectStats(projet, digestsByProjet[projet.id] ?? null, dossiers)}
                    stage={projectStage(
                      digestsByProjet[projet.id] ?? null,
                      dossiers.filter((d) => d.projetId === projet.id),
                      suivis.filter((s) => s.projetId === projet.id),
                    )}
                  />
                ))}
              </div>
            </>
          ) : (
            <EmptyState
              icon={IconProjet}
              title="Aucun projet de travaux"
              description="Un projet, c'est un chantier : sa description, son questionnaire et les aides qui lui correspondent. Vous pouvez en mener plusieurs de front sur un même monument."
              action={
                canEdit ? (
                  <button
                    onClick={goNouveauProjet}
                    className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md"
                    style={{ background: C.orange }}
                  >
                    <IconAjouter className="h-4 w-4" strokeWidth={2} />
                    Lancer un projet de travaux
                  </button>
                ) : undefined
              }
            />
          )}
        </TabsContent>

        {/* DOCUMENTS */}
        <TabsContent value="documents" className="mt-4 space-y-4">
          <div className="flex justify-end">
            <button onClick={() => setAddDocOpen(true)} className="inline-flex items-center justify-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md" style={{ background: C.blue }}>
              <IconDepot className="h-3.5 w-3.5" strokeWidth={1.8} />Ajouter un document
            </button>
          </div>
          {monumentDocuments.length > 0 ? (
            <DocumentGrid
              items={monumentDocuments}
              keyOf={(doc) => doc.id}
              renderItem={(doc) => (
                <DocumentCard
                  document={doc}
                  dossierNames={dossierNames}
                  monumentNames={monumentNames}
                  onClick={() => setPreviewDoc(doc)}
                  onRename={handleRename}
                  onDelete={handleDeleteDocument}
                  onAddToProject={(doc) => { setPreviewDoc(null); setAddToProjectDoc(doc); }}
                  myRole={monument.myRole ?? null}
                  uploaderName={uploaderNames[doc.userId]}
                  onDocumentUpdated={reloadMonumentDocuments}
                />
              )}
            />
          ) : (
            <EmptyState icon={IconDocuments} title="Aucun document" description="Les documents rattachés à ce monument apparaîtront ici." />
          )}
        </TabsContent>

        {/* ÉQUIPE */}
        <TabsContent value="equipe" className="mt-4">
          {equipeAccessible ? (
            equipePanel
          ) : (
            <PaywallOverlay
              offre="Veille"
              titre="Travaillez à plusieurs sur ce monument"
              description="Invitez votre architecte, vos artisans ou un assistant. Ils accèdent au monument, à ses projets et à ses documents, avec le rôle que vous leur donnez."
              monumentId={monument.id}
            >
              {equipePanel}
            </PaywallOverlay>
          )}
        </TabsContent>
      </Tabs>

      <DocumentPreviewDialog document={previewDoc} open={!!previewDoc} onOpenChange={(open) => { if (!open) setPreviewDoc(null); }} onAddToProject={(doc) => { setPreviewDoc(null); setAddToProjectDoc(doc); }} />
      <AddToProjectDialog
        document={addToProjectDoc}
        open={!!addToProjectDoc}
        onOpenChange={(open) => { if (!open) { setAddToProjectDoc(null); reloadMonumentDocuments(); } }}
      />
      <AttachDocumentDialog
        open={addDocOpen}
        onOpenChange={setAddDocOpen}
        monumentId={monument.id}
        onAttach={handleAddDocument}
        onUploaded={(doc) => setAccessDoc(doc)}
      />
      {accessDoc && (
        <ManageDocumentAccessDialog
          document={accessDoc}
          myRole={monument.myRole ?? null}
          open={!!accessDoc}
          onOpenChange={(open) => { if (!open) setAccessDoc(null); }}
          onSaved={reloadMonumentDocuments}
        />
      )}

      <PaywallDialog
        open={paywallProjet}
        onOpenChange={setPaywallProjet}
        offre="Veille"
        titre="Menez autant de chantiers qu'il en faut"
        description={
          offre.projetsMax === null
            ? 'L’offre Veille rend vos projets de travaux illimités, et vous prévient avant chaque date limite.'
            : `Votre offre couvre ${offre.projetsMax} projets par monument. L’offre Veille les rend illimités, et vous prévient avant chaque date limite.`
        }
        monumentId={monument.id}
      />

      <AlertDialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer « {monument.nom} » ?</AlertDialogTitle>
            <AlertDialogDescription>
              Tous ses projets de travaux et les dossiers associés seront également
              supprimés. Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Annuler</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? 'Suppression…' : 'Supprimer'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
