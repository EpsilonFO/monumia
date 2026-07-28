import { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router';
import { ChevronLeft, ChevronDown, Loader2 } from 'lucide-react';
import {
  type IconComponent,
  IconDiagnostic, IconSucces, IconHelp, IconErreur, IconCle,
  IconEquipe, IconAide, IconDossier, IconDocuments, IconDepot, IconMonument,
} from '@/components/icons';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { EmptyState } from '@/components/shared/EmptyState';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { MonumentFiche } from '@/components/monument/MonumentFiche';
import { AideCard } from '@/components/aide/AideCard';
import { DossierCard } from '@/components/dossier/DossierCard';
import { DocumentCard } from '@/components/document/DocumentCard';
import { DocumentGrid } from '@/components/document/DocumentGrid';
import { ManageDocumentAccessDialog } from '@/components/document/ManageDocumentAccessDialog';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { AddToProjectDialog } from '@/components/document/AddToProjectDialog';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { TeamPanel } from '@/components/sharing/TeamPanel';
import { projectPermissions } from '@/lib/project-permissions';
import { ProjectSummaryBar } from '@/components/project/ProjectSummaryBar';
import { ProjectDetailSkeleton } from '@/components/skeletons';
import { ProjectEcheancier } from '@/components/project/ProjectEcheancier';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { monumentService } from '@/services/monument.service';
import { documentService } from '@/services/document.service';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { suiviService } from '@/services/suivi.service';
import { sharingService } from '@/services/sharing.service';
import { computeProjectStats, mergeProjectDeadlines } from '@/lib/project-stats';
import { daysUntil } from '@/lib/date-utils';
import { C, SERIF } from '@/lib/brand';
import { aideGridSpans } from '@/lib/aide-grid';
import { isAccessLostError } from '@/lib/api-error';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import type {
  Monument, Document, AideMatchResult, ProjectMember, ProjectInvitation,
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

export function ProjectDetailPage() {
  const { projetId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === projetId));
  const upsertMonument = useMonumentStore((s) => s.upsertMonument);
  const updateMonument = useMonumentStore((s) => s.updateMonument);
  const deleteMonument = useMonumentStore((s) => s.deleteMonument);

  const allDossiers = useDossierStore((s) => s.dossiers);
  const dossiers = useMemo(() => allDossiers.filter((d) => d.monumentId === projetId), [allDossiers, projetId]);

  // Chargé pour que les cartes dossier affichent leur avancement (lecture via le store).
  const suiviLoaded = useSuiviStore((s) => (projetId ? s.loadedMonuments[projetId] : false));

  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);
  const diagnostic = projetId ? diagnosticsByMonument[projetId] ?? null : null;

  // Documents du projet : on charge TOUS les documents rattachés à ce projet
  // (tous les membres confondus) via le fetch projet-scopé, pas le store « mes
  // documents ». Sans ça, un owner/co_owner ne verrait jamais les pièces déposées
  // par un collaborateur.
  const [projectDocuments, setProjectDocuments] = useState<Document[]>([]);

  const [notFound, setNotFound] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [showNonEligibles, setShowNonEligibles] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [addToProjectDoc, setAddToProjectDoc] = useState<Document | null>(null);
  const [addDocOpen, setAddDocOpen] = useState(false);
  const [accessDoc, setAccessDoc] = useState<Document | null>(null);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [invitations, setInvitations] = useState<ProjectInvitation[]>([]);
  const [confirmRefaireOpen, setConfirmRefaireOpen] = useState(false);

  const tabParam = searchParams.get('tab');
  // L'onglet « Aides » est réservé au chef de projet et à son adjoint. Pour un
  // collaborateur, on retombe sur « Dossiers ».
  const canAccessAides = projectPermissions(monument?.myRole ?? null).canAccessAides;
  const requestedTab =
    tabParam === 'monument' || tabParam === 'dossiers' || tabParam === 'documents' || tabParam === 'equipe'
      ? tabParam
      : 'aides';
  const activeTab = requestedTab === 'aides' && !canAccessAides ? 'dossiers' : requestedTab;
  const handleTabChange = useCallback((value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', value);
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  // Rafraîchir au montage (et quand on change de projet) : revenir sur la page
  // doit refléter les changements des autres membres, sans recharger le navigateur.
  useEffect(() => {
    if (!projetId) return;
    monumentService.getById(projetId)
      .then(upsertMonument)
      .catch(() => { if (!useMonumentStore.getState().monuments.some((m) => m.id === projetId)) setNotFound(true); });
  }, [projetId, upsertMonument]);
  // Diagnostic déterministe : recalculé à l'arrivée (et quand les réponses du
  // questionnaire changent). Le moteur est pur et rapide — pas de persistance ;
  // les réponses (monument.questionnaire) se résolvent côté client via
  // eliminationsParOption.
  const questionnaireKey = monument?.questionnaire ? JSON.stringify(monument.questionnaire) : '';
  useEffect(() => {
    if (!projetId) return;
    let cancelled = false;
    const answers: ProjectQuestionnaireAnswers = questionnaireKey ? JSON.parse(questionnaireKey) : {};
    aideService.runProjectDiagnostic(projetId, answers)
      .then((result) => { if (!cancelled) setDiagnostic(projetId, result); })
      .catch(console.error);
    return () => { cancelled = true; };
  }, [projetId, questionnaireKey, setDiagnostic]);
  useEffect(() => { dossierService.fetchAll().catch(console.error); }, []);
  useEffect(() => { if (projetId && !suiviLoaded) suiviService.fetchByMonument(projetId).catch(console.error); }, [projetId, suiviLoaded]);
  const reloadProjectDocuments = useCallback(() => {
    if (!projetId) return;
    documentService.getAll({ monumentId: projetId }).then(setProjectDocuments).catch(() => {});
  }, [projetId]);
  useEffect(() => { reloadProjectDocuments(); }, [reloadProjectDocuments]);
  const reloadMembers = useCallback(() => {
    const id = monument?.id;
    if (!id) return;
    sharingService
      .getMembers(id)
      .then((data) => {
        setMembers(data.members);
        setInvitations(data.invitations);
      })
      .catch((err) => {
        // Perte d'accès définitive (projet supprimé par le chef, membre retiré,
        // ou départ déjà effectué) : on purge le cache local et on bascule sur
        // l'écran « introuvable ». Sur une erreur transitoire (réseau, 5xx), on
        // ne touche à rien pour ne pas éjecter l'utilisateur à tort.
        if (isAccessLostError(err)) {
          deleteMonument(id);
          setNotFound(true);
        }
      });
  }, [monument?.id, deleteMonument]);

  useEffect(() => { reloadMembers(); }, [reloadMembers]);

  const uploaderNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const m of members) map[m.userId] = `${m.prenom} ${m.nom}`.trim();
    return map;
  }, [members]);

  const stats = useMemo(() => (monument ? computeProjectStats(monument, diagnostic, dossiers) : null), [monument, diagnostic, dossiers]);
  const deadlines = useMemo(() => mergeProjectDeadlines(diagnostic, dossiers), [diagnostic, dossiers]);
  const dossierNames = useMemo(() => Object.fromEntries(allDossiers.map((d) => [d.id, d.titre])), [allDossiers]);
  const monumentNames = useMemo(() => (monument ? { [monument.id]: monument.nom } : {}), [monument]);

  const handleRunDiagnostic = useCallback(async () => {
    if (!projetId) return;
    setRunning(true);
    try {
      const answers = monument?.questionnaire ?? {};
      setDiagnostic(projetId, await aideService.runProjectDiagnostic(projetId, answers));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors du diagnostic');
    } finally {
      setRunning(false);
    }
  }, [projetId, setDiagnostic, monument?.questionnaire]);

  // « Refaire le questionnaire » : on prévient que les réponses et le diagnostic
  // actuels seront effacés, puis on renvoie sur l'étape 2 du wizard (questionnaire
  // vierge), exactement comme juste après la saisie de la fiche monument.
  const confirmRefaire = useCallback(() => {
    if (!projetId) return;
    setConfirmRefaireOpen(false);
    navigate(`${ROUTES.PROJET_NEW}?monument=${projetId}`);
  }, [projetId, navigate]);

  if (notFound || (!monument && !projetId)) {
    return (
      <div className="space-y-4">
        <h1 className="text-[20px]" style={{ fontFamily: SERIF, color: C.ink }}>Projet introuvable</h1>
        <p className="text-[14px] text-muted-foreground">Ce projet n'existe pas ou a été supprimé.</p>
        <Link to={ROUTES.PROJETS} className="inline-flex items-center gap-1.5 text-[13px] font-medium" style={{ color: C.blue }}>
          <ChevronLeft className="h-3.5 w-3.5" /> Retour aux projets
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
      toast.success('Projet mis à jour');
    } catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors de la sauvegarde'); }
    finally { setSaving(false); }
  };

  const handleDelete = async () => {
    setConfirmDeleteOpen(false);
    setDeleting(true);
    try {
      for (const dossier of dossiers) await dossierService.delete(dossier.id);
      await monumentService.delete(monument.id);
      deleteMonument(monument.id);
      toast.success('Projet supprimé');
      navigate(ROUTES.PROJETS);
    } catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression'); }
    finally { setDeleting(false); }
  };

  const handleRename = async (id: string, newName: string) => {
    try { await documentService.update(id, { nom: newName }); reloadProjectDocuments(); toast.success('Document renommé'); }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors du renommage'); }
  };
  const handleDeleteDocument = async (id: string) => {
    try { await documentService.delete(id); reloadProjectDocuments(); toast.success('Document supprimé'); }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression'); }
  };
  // Ajout d'un document au projet (onglet Documents) : tout membre peut déposer.
  // Le document est associé au projet (s'il ne l'est pas déjà), sans rattachement
  // à un dossier précis. Un document fraîchement téléversé l'est déjà.
  const handleAddDocument = async (doc: Document) => {
    if (!projetId) return;
    try {
      if (!doc.monumentIds.includes(projetId)) {
        await documentService.addToProjects(doc.id, [projetId]);
      }
      reloadProjectDocuments();
      toast.success('Document ajouté au projet');
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

  // Une aide déjà passée en dossier disparaît de la liste des aides : elle vit
  // désormais dans l'onglet « Dossiers ». Supprimer le dossier l'y fait réapparaître.
  const dossierAideIds = new Set(dossiers.map((d) => d.aideId));
  const eligibles = [...(diagnostic?.aidesEligibles ?? [])].filter((m) => !dossierAideIds.has(m.aide.id)).sort(byDeadline);
  const potentiels = [...(diagnostic?.aidesPotentiellementEligibles ?? [])].filter((m) => !dossierAideIds.has(m.aide.id)).sort(byDeadline);
  // « À débloquer » : ordre du backend conservé (enjeu décroissant) — c'est le
  // montant en jeu qui décide si la démarche vaut la peine, pas l'échéance.
  const atteignables = (diagnostic?.aidesAtteignables ?? []).filter((m) => !dossierAideIds.has(m.aide.id));
  const nonEligibles = (diagnostic?.aidesNonEligibles ?? []).filter((m) => !dossierAideIds.has(m.aide.id));

  // L'affichage des aides s'adapte au nombre : 1 → bandeau pleine largeur, sinon
  // grille 6 colonnes où chaque carte s'étale (rangées de deux ou de trois) pour
  // que chaque rangée soit pleine — jamais de case vide (voir aideGridSpans).
  const renderAideList = (list: AideMatchResult[]) => {
    if (list.length === 1) return <AideCard match={list[0]} monumentId={monument.id} layout="hero" />;
    const spans = aideGridSpans(list.length);
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
        {list.map((match, i) => (
          <div key={match.aide.id} className={spans[i]}>
            <AideCard match={match} monumentId={monument.id} layout="grid" />
          </div>
        ))}
      </div>
    );
  };

  // Onglets du projet — chaque entrée = un grand bouton lisible (icône + libellé + compteur).
  const projectTabs: { value: string; label: string; icon: IconComponent; count: number | null }[] = [
    // Les aides à débloquer comptent : ce sont des pistes vivantes, pas des refus.
    ...(canAccessAides ? [{ value: 'aides', label: 'Aides', icon: IconAide, count: eligibles.length + atteignables.length + potentiels.length }] : []),
    { value: 'monument', label: 'Monument', icon: IconMonument, count: null },
    { value: 'dossiers', label: 'Dossiers', icon: IconDossier, count: dossiers.length },
    { value: 'documents', label: 'Documents', icon: IconDocuments, count: projectDocuments.length },
    { value: 'equipe', label: 'Équipe', icon: IconEquipe, count: members.length },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
        <Link to={ROUTES.PROJETS} className="hover:opacity-70 transition-opacity">Projets</Link>
        <span>/</span>
        <span style={{ color: C.ink }}>{monument.nom}</span>
      </div>

      <ProjectSummaryBar monument={monument} stats={stats} members={members} onRefaireQuestionnaire={() => setConfirmRefaireOpen(true)} />

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <div role="tablist" aria-label="Sections du projet" className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
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
                <p className="text-[14px] mt-1 text-muted-foreground">Notre moteur analyse les aides publiques et privées applicables.</p>
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
              <ProjectEcheancier deadlines={deadlines} />

              <section className="space-y-3">
                <h3 className="flex items-center gap-2 text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  <IconSucces className="h-4 w-4 text-success" />Éligibles ({eligibles.length})
                </h3>
                {eligibles.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground">Aucune aide pleinement éligible pour le moment.</p>
                ) : renderAideList(eligibles)}
              </section>

              <section className="space-y-3">
                <h3 className="flex items-center gap-2 text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  <IconHelp className="h-4 w-4" style={{ color: C.orangeVif }} />À confirmer ({potentiels.length})
                </h3>
                {potentiels.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground">Aucune aide à confirmer.</p>
                ) : renderAideList(potentiels)}
              </section>

              {atteignables.length > 0 && (
                <section className="space-y-3">
                  <h3 className="flex items-center gap-2 text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
                    <IconCle className="h-4 w-4 text-info" />À débloquer ({atteignables.length})
                  </h3>
                  <p className="text-[13px] text-muted-foreground">
                    Une démarche vous sépare de ces aides. Ouvrez la fiche pour voir laquelle,
                    auprès de qui et en combien de temps.
                  </p>
                  {renderAideList(atteignables)}
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
                    <p className="text-[13px] text-muted-foreground">Aucune aide non éligible.</p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                      {nonEligibles.map((match) => (<AideCard key={match.aide.id} match={match} monumentId={monument.id} />))}
                    </div>
                  )
                )}
              </section>
            </div>
          )}
        </TabsContent>

        {/* MONUMENT */}
        <TabsContent value="monument" className="mt-4">
          <MonumentFiche
            monument={monument}
            canDelete={projectPermissions(monument.myRole ?? null).canDeleteProject}
            deleting={deleting}
            onDelete={() => setConfirmDeleteOpen(true)}
          />
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

        {/* DOCUMENTS */}
        <TabsContent value="documents" className="mt-4 space-y-4">
          <div className="flex justify-end">
            <button onClick={() => setAddDocOpen(true)} className="inline-flex items-center justify-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md" style={{ background: C.blue }}>
              <IconDepot className="h-3.5 w-3.5" strokeWidth={1.8} />Ajouter un document
            </button>
          </div>
          {projectDocuments.length > 0 ? (
            <DocumentGrid
              items={projectDocuments}
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
                  onDocumentUpdated={reloadProjectDocuments}
                />
              )}
            />
          ) : (
            <EmptyState icon={IconDocuments} title="Aucun document" description="Les documents rattachés à ce projet apparaîtront ici." />
          )}
        </TabsContent>

        {/* ÉQUIPE */}
        <TabsContent value="equipe" className="mt-4">
          <TeamPanel
            monumentId={monument.id}
            myRole={monument.myRole ?? null}
            members={members}
            invitations={invitations}
            onChanged={reloadMembers}
            onLeft={() => { deleteMonument(monument.id); navigate(ROUTES.PROJETS); }}
          />
        </TabsContent>
      </Tabs>

      <DocumentPreviewDialog document={previewDoc} open={!!previewDoc} onOpenChange={(open) => { if (!open) setPreviewDoc(null); }} onAddToProject={(doc) => { setPreviewDoc(null); setAddToProjectDoc(doc); }} />
      <AddToProjectDialog
        document={addToProjectDoc}
        open={!!addToProjectDoc}
        onOpenChange={(open) => { if (!open) { setAddToProjectDoc(null); reloadProjectDocuments(); } }}
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
          onSaved={reloadProjectDocuments}
        />
      )}

      <AlertDialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer « {monument.nom} » ?</AlertDialogTitle>
            <AlertDialogDescription>
              Tous les dossiers associés seront également supprimés. Cette action est irréversible.
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

      <AlertDialog open={confirmRefaireOpen} onOpenChange={setConfirmRefaireOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Refaire le questionnaire&nbsp;?</AlertDialogTitle>
            <AlertDialogDescription>
              Vous repartirez de vos informations monument déjà enregistrées&nbsp;: seules
              les réponses au questionnaire seront redemandées. Vos réponses actuelles
              seront remplacées et le diagnostic d&rsquo;aides recalculé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmRefaire}
              className="text-white hover:opacity-90"
              style={{ background: C.orange }}
            >
              Refaire le questionnaire
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

    </div>
  );
}
