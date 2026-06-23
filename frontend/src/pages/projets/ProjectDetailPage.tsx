import { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router';
import {
  Shield, Calendar, AlertTriangle, Wrench, Building2, Eye, Compass,
  ScrollText, FolderOpen, ChevronLeft, ChevronDown, Edit2, Trash2, Loader2,
  CheckCircle2, HelpCircle, XCircle, Users, FilePlus2,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { EmptyState } from '@/components/shared/EmptyState';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { AideCard } from '@/components/aide/AideCard';
import { DossierCard } from '@/components/dossier/DossierCard';
import { DocumentCard } from '@/components/document/DocumentCard';
import { DocumentPreviewDialog } from '@/components/document/DocumentPreviewDialog';
import { AddToProjectDialog } from '@/components/document/AddToProjectDialog';
import { AttachDocumentDialog } from '@/components/dossier/AttachDocumentDialog';
import { TeamPanel } from '@/components/sharing/TeamPanel';
import { projectPermissions } from '@/lib/project-permissions';
import { ProjectSummaryBar } from '@/components/project/ProjectSummaryBar';
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
import { formatDate, daysUntil } from '@/lib/date-utils';
import { C, SERIF } from '@/lib/brand';
import { isAccessLostError } from '@/lib/api-error';
import { ROUTES } from '@/constants/routes';
import { WORK_TYPES, OWNERSHIP_TYPES, PROTECTION_LABELS, ETAT_LABELS } from '@/constants/monument-options';
import { toast } from 'sonner';
import type { Monument, Document, AideMatchResult, ProjectMember, ProjectInvitation } from '@/types';

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
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [invitations, setInvitations] = useState<ProjectInvitation[]>([]);

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
    const answers: Record<string, string> = questionnaireKey ? JSON.parse(questionnaireKey) : {};
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
      const answers = (monument?.questionnaire ?? {}) as Record<string, string>;
      setDiagnostic(projetId, await aideService.runProjectDiagnostic(projetId, answers));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors du diagnostic');
    } finally {
      setRunning(false);
    }
  }, [projetId, setDiagnostic, monument?.questionnaire]);

  if (notFound || (!monument && !projetId)) {
    return (
      <div className="space-y-4">
        <h1 className="text-[20px]" style={{ fontFamily: SERIF, color: C.ink }}>Projet introuvable</h1>
        <p className="text-[14px]" style={{ color: '#6a7180' }}>Ce projet n'existe pas ou a été supprimé.</p>
        <Link to={ROUTES.PROJETS} className="inline-flex items-center gap-1.5 text-[13px] font-medium" style={{ color: C.blue }}>
          <ChevronLeft className="h-3.5 w-3.5" /> Retour aux projets
        </Link>
      </div>
    );
  }

  if (!monument || !stats) return <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin" style={{ color: C.blueLight }} /></div>;

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

  const workTypeLabels = WORK_TYPES.reduce<Record<string, string>>((acc, w) => { acc[w.value] = w.label; return acc; }, {});
  // Une aide déjà passée en dossier disparaît de la liste des aides : elle vit
  // désormais dans l'onglet « Dossiers ». Supprimer le dossier l'y fait réapparaître.
  const dossierAideIds = new Set(dossiers.map((d) => d.aideId));
  const eligibles = [...(diagnostic?.aidesEligibles ?? [])].filter((m) => !dossierAideIds.has(m.aide.id)).sort(byDeadline);
  const potentiels = [...(diagnostic?.aidesPotentiellementEligibles ?? [])].filter((m) => !dossierAideIds.has(m.aide.id)).sort(byDeadline);
  const nonEligibles = (diagnostic?.aidesNonEligibles ?? []).filter((m) => !dossierAideIds.has(m.aide.id));

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-[13px]" style={{ color: '#6a7180' }}>
        <Link to={ROUTES.PROJETS} className="hover:opacity-70 transition-opacity">Projets</Link>
        <span>/</span>
        <span style={{ color: C.ink }}>{monument.nom}</span>
      </div>

      <ProjectSummaryBar monument={monument} stats={stats} members={members} onRelancer={handleRunDiagnostic} relancing={running} />

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          {canAccessAides && (
            <TabsTrigger value="aides" className="gap-1.5"><Compass className="h-4 w-4" />Aides ({eligibles.length + potentiels.length})</TabsTrigger>
          )}
          <TabsTrigger value="monument" className="gap-1.5"><Eye className="h-4 w-4" />Monument</TabsTrigger>
          <TabsTrigger value="dossiers" className="gap-1.5"><ScrollText className="h-4 w-4" />Dossiers ({dossiers.length})</TabsTrigger>
          <TabsTrigger value="documents" className="gap-1.5"><FolderOpen className="h-4 w-4" />Documents ({projectDocuments.length})</TabsTrigger>
          <TabsTrigger value="equipe" className="gap-1.5"><Users className="h-4 w-4" />Équipe ({members.length})</TabsTrigger>
        </TabsList>

        {/* AIDES */}
        <TabsContent value="aides" className="mt-4 space-y-6">
          {!diagnostic ? (
            <div className="rounded-2xl border py-10 text-center space-y-4" style={{ background: C.paleBlue, borderColor: C.border }}>
              <div className="mx-auto w-14 h-14 rounded-full flex items-center justify-center" style={{ background: '#fff' }}>
                <Compass className="h-7 w-7" style={{ color: C.blue }} />
              </div>
              <div>
                <h2 className="text-[18px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  Découvrez les aides pour <em className="italic" style={{ color: C.orange }}>{monument.nom}</em>
                </h2>
                <p className="text-[14px] mt-1" style={{ color: '#6a7180' }}>Notre moteur analyse les aides publiques et privées applicables.</p>
              </div>
              <button
                onClick={handleRunDiagnostic}
                disabled={running}
                className="inline-flex items-center gap-2 px-6 py-3 text-[13px] font-semibold text-white rounded-lg transition-all duration-300 hover:shadow-md disabled:opacity-60"
                style={{ background: C.orange }}
              >
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Compass className="h-4 w-4" strokeWidth={1.8} />}
                Lancer le moteur
              </button>
            </div>
          ) : (
            <div className="space-y-8">
              <ProjectEcheancier deadlines={deadlines} />

              <section className="space-y-3">
                <h3 className="flex items-center gap-2 text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  <CheckCircle2 className="h-4 w-4 text-green-600" />Éligibles ({eligibles.length})
                </h3>
                {eligibles.length === 0 ? (
                  <p className="text-[13px]" style={{ color: '#6a7180' }}>Aucune aide pleinement éligible pour le moment.</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {eligibles.map((match) => (<AideCard key={match.aide.id} match={match} monumentId={monument.id} />))}
                  </div>
                )}
              </section>

              <section className="space-y-3">
                <h3 className="flex items-center gap-2 text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  <HelpCircle className="h-4 w-4" style={{ color: C.orangeVif }} />À confirmer ({potentiels.length})
                </h3>
                {potentiels.length === 0 ? (
                  <p className="text-[13px]" style={{ color: '#6a7180' }}>Aucune aide à confirmer.</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {potentiels.map((match) => (<AideCard key={match.aide.id} match={match} monumentId={monument.id} />))}
                  </div>
                )}
              </section>

              <section className="space-y-3">
                <button
                  onClick={() => setShowNonEligibles((v) => !v)}
                  className="flex items-center gap-2 text-[15px]"
                  style={{ fontFamily: SERIF, color: C.ink }}
                >
                  <XCircle className="h-4 w-4 text-red-500" />Non éligibles ({nonEligibles.length})
                  <ChevronDown className={`h-4 w-4 transition-transform ${showNonEligibles ? 'rotate-180' : ''}`} />
                </button>
                {showNonEligibles && (
                  nonEligibles.length === 0 ? (
                    <p className="text-[13px]" style={{ color: '#6a7180' }}>Aucune aide non éligible.</p>
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
        <TabsContent value="monument" className="mt-4 space-y-4">
          <div className="flex justify-end gap-2">
            {projectPermissions(monument?.myRole ?? null).canDeleteProject && (
              <button onClick={() => setConfirmDeleteOpen(true)} disabled={deleting} aria-label="Supprimer le projet" className="flex items-center justify-center w-9 h-9 shrink-0 border rounded-lg transition-colors hover:text-red-600 hover:border-red-200" style={{ borderColor: C.border, color: '#6a7180' }}>
                {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" strokeWidth={1.8} />}
              </button>
            )}
            {projectPermissions(monument?.myRole ?? null).canEditProject && (
              <button onClick={() => setIsEditing(true)} className="inline-flex items-center justify-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md" style={{ background: C.blue }}>
                <Edit2 className="h-3.5 w-3.5" strokeWidth={1.8} />Éditer
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Panel title="Identification" icon={<Building2 className="h-4 w-4" style={{ color: C.blue }} strokeWidth={1.8} />}>
              <div className="space-y-2 text-[13px]">
                {monument.referenceMerimee && <InfoRow label="Réf. Mérimée" value={monument.referenceMerimee} />}
                <InfoRow label="Localisation" value={monument.commune ?? ''} />
                <InfoRow label="Département" value={monument.departement ?? ''} />
                {monument.siecleConstruction && <InfoRow label="Siècle" value={monument.siecleConstruction} />}
              </div>
            </Panel>

            <Panel title="Statut juridique" icon={<Shield className="h-4 w-4" style={{ color: C.blue }} strokeWidth={1.8} />}>
              <div className="space-y-2 text-[13px]">
                <InfoRow label="Protection" value={PROTECTION_LABELS[monument.protection] ?? monument.protection} />
                {monument.dateProtection && <InfoRow label="Date" value={formatDate(monument.dateProtection)} />}
                <InfoRow label="Propriétaire" value={OWNERSHIP_TYPES.find((o) => o.value === monument.proprietaire)?.label ?? monument.proprietaire} />
                {monument.affectataire && <InfoRow label="Affectation" value={monument.affectataire} />}
              </div>
            </Panel>

            <Panel title="État actuel" icon={<AlertTriangle className="h-4 w-4" style={{ color: C.orangeVif }} strokeWidth={1.8} />}>
              <div className="space-y-3 text-[13px]">
                <div className="flex items-center gap-2">
                  <span style={{ color: '#6a7180' }}>Conservation :</span>
                  <Badge variant="outline" className="text-[12px]" style={{ borderColor: C.border }}>{ETAT_LABELS[monument.etatConservation] ?? monument.etatConservation}</Badge>
                </div>
                {monument.descriptionEtat && <p className="leading-relaxed" style={{ color: '#6a7180' }}>{monument.descriptionEtat}</p>}
              </div>
            </Panel>

            <Panel title="Travaux envisagés" icon={<Wrench className="h-4 w-4" style={{ color: C.orange }} strokeWidth={1.8} />}>
              {monument.travauxEnvisages && monument.travauxEnvisages.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {monument.travauxEnvisages.map((t) => (
                    <Badge key={t} className="text-[12px] border-0" style={{ background: C.paleOrange, color: C.orange }}>{workTypeLabels[t] ?? t}</Badge>
                  ))}
                </div>
              ) : (
                <p className="text-[13px]" style={{ color: '#6a7180' }}>Aucun travail envisagé</p>
              )}
            </Panel>
          </div>

          {monument.descriptionGenerale && (
            <Panel title="Description générale de la protection">
              <p className="text-[13px] leading-relaxed" style={{ color: '#6a7180' }}>{monument.descriptionGenerale}</p>
            </Panel>
          )}

          {monument.photos && monument.photos.length > 0 && (
            <Panel title="Photos">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                {monument.photos.map((p) => (
                  <div key={p.url} className="aspect-square rounded-lg overflow-hidden border" style={{ borderColor: C.border }}>
                    <img src={p.url} alt={p.legende ?? monument.nom} className="w-full h-full object-cover" />
                  </div>
                ))}
              </div>
            </Panel>
          )}

          <div className="flex items-center gap-4 text-[12px]" style={{ color: '#6a7180' }}>
            <div className="flex items-center gap-1"><Calendar className="h-3 w-3" />Créé le {formatDate(monument.createdAt)}</div>
            <div className="flex items-center gap-1"><Calendar className="h-3 w-3" />Modifié le {formatDate(monument.updatedAt)}</div>
          </div>
        </TabsContent>

        {/* DOSSIERS */}
        <TabsContent value="dossiers" className="mt-4 space-y-4">
          {dossiers.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {dossiers.map((dossier) => (<DossierCard key={dossier.id} dossier={dossier} monumentColor={C.blue} />))}
            </div>
          ) : (
            <EmptyState
              icon={ScrollText}
              title="Aucun dossier pour ce projet"
              description="Ouvrez une aide depuis l'onglet « Aides » pour démarrer une candidature."
              action={
                <button onClick={() => handleTabChange('aides')} className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md" style={{ background: C.blue }}>
                  <Compass className="h-4 w-4" strokeWidth={1.8} />Voir les aides
                </button>
              }
            />
          )}
        </TabsContent>

        {/* DOCUMENTS */}
        <TabsContent value="documents" className="mt-4 space-y-4">
          <div className="flex justify-end">
            <button onClick={() => setAddDocOpen(true)} className="inline-flex items-center justify-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md" style={{ background: C.blue }}>
              <FilePlus2 className="h-3.5 w-3.5" strokeWidth={1.8} />Ajouter un document
            </button>
          </div>
          {projectDocuments.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {projectDocuments.map((doc) => (
                <DocumentCard
                  key={doc.id}
                  document={doc}
                  dossierNames={dossierNames}
                  monumentNames={monumentNames}
                  onClick={() => setPreviewDoc(doc)}
                  onRename={handleRename}
                  onDelete={handleDeleteDocument}
                  onAddToProject={(doc) => { setPreviewDoc(null); setAddToProjectDoc(doc); }}
                  myRole={monument.myRole ?? null}
                  uploaderName={uploaderNames[doc.userId]}
                />
              ))}
            </div>
          ) : (
            <EmptyState icon={FolderOpen} title="Aucun document" description="Les documents rattachés à ce projet apparaîtront ici." />
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
      />

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
    </div>
  );
}

function Panel({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border overflow-hidden" style={{ background: C.card, borderColor: C.border }}>
      <div className="flex items-center gap-2 px-5 py-3 border-b" style={{ borderColor: C.border }}>
        {icon && <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: C.cream }}>{icon}</div>}
        <h3 className="text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>{title}</h3>
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="shrink-0" style={{ color: '#6a7180' }}>{label} :</span>
      <span className="font-medium" style={{ color: C.ink }}>{value}</span>
    </div>
  );
}
