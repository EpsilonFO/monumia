import { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router';
import {
  Shield, Calendar, AlertTriangle, Wrench, Building2,
  ScrollText, ChevronLeft, Edit2, Eye, Trash2, Loader2,
  Compass, CheckCircle2, XCircle, HelpCircle, Search, RefreshCw,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { MonumentForm, type PendingPhoto } from '@/components/monument/MonumentForm';
import { AideMatchBanner } from '@/components/aide/AideMatchBanner';
import { AideCard } from '@/components/aide/AideCard';
import { AideFilterBar } from '@/components/aide/AideFilterBar';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useDocumentStore } from '@/stores/useDocumentStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { monumentService } from '@/services/monument.service';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { formatDate } from '@/lib/date-utils';
import { ROUTES } from '@/constants/routes';
import { WORK_TYPES, OWNERSHIP_TYPES } from '@/constants/monument-options';
import { toast } from 'sonner';
import type { Monument, AideDiagnosticResult } from '@/types';

const FONT = "'Cormorant Garamond', serif";

const protectionLabels: Record<string, string> = {
  classe: 'Classé Monument Historique',
  inscrit: 'Inscrit Monument Historique',
  abords: 'En périmètre d\'un MH',
  spr: 'Site Patrimonial Remarquable',
  non_protege: 'Non protégé',
};

const etatLabels: Record<string, string> = {
  bon: 'Bon état',
  moyen: 'État moyen',
  mauvais: 'Mauvais état',
  peril: 'En péril',
};

const urgenceColors: Record<string, string> = {
  faible: 'bg-green-100 text-green-800',
  moyenne: 'bg-yellow-100 text-yellow-800',
  haute: 'bg-orange-100 text-orange-800',
  critique: 'bg-red-100 text-red-800',
};

export function MonumentDetailPage() {
  const { monumentId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId));
  const updateMonument = useMonumentStore((s) => s.updateMonument);
  const deleteMonument = useMonumentStore((s) => s.deleteMonument);
  const allDossiers = useDossierStore((s) => s.dossiers);
  const dossierLoaded = useDossierStore((s) => s.loaded);
  const dossiers = useMemo(() => allDossiers.filter((d) => d.monumentId === monumentId), [allDossiers, monumentId]);
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const filters = useAideStore((s) => s.filters);
  const diagnostic = monumentId ? diagnosticsByMonument[monumentId] ?? null : null;

  const user = useAuthStore((s) => s.user);
  const uploadDocument = useDocumentStore((s) => s.uploadDocument);

  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [isRunningDiagnostic, setIsRunningDiagnostic] = useState(false);
  const [showDiagnostic, setShowDiagnostic] = useState(!!diagnostic);

  const defaultTab = searchParams.get('tab') === 'dossiers' ? 'dossiers' : 'informations';

  const handleLaunchDiagnostic = useCallback(async () => {
    if (!monumentId) return;
    setIsRunningDiagnostic(true);
    setShowDiagnostic(true);
    try {
      await aideService.runDiagnostic(monumentId, filters.modeProjet, filters.travauxFiltres.length > 0 ? filters.travauxFiltres : undefined);
    } catch (err) { console.error('Diagnostic error:', err); }
    finally { setIsRunningDiagnostic(false); }
  }, [monumentId, filters.modeProjet, filters.travauxFiltres]);

  const aideIdsWithDossier = useMemo(() => new Set(dossiers.map((d) => d.aideId)), [dossiers]);

  const filteredDiagnostic = useMemo((): AideDiagnosticResult | null => {
    if (!diagnostic) return null;
    const catFilter = filters.categories;
    const query = filters.searchQuery.toLowerCase();
    const filterMatches = (matches: typeof diagnostic.aidesEligibles) => {
      let filtered = matches.filter((m) => !aideIdsWithDossier.has(m.aide.id));
      if (catFilter.length > 0) filtered = filtered.filter((m) => catFilter.includes(m.aide.categorie));
      if (query) filtered = filtered.filter((m) => m.aide.nom.toLowerCase().includes(query) || m.aide.nomCourt.toLowerCase().includes(query) || m.aide.organisme.toLowerCase().includes(query));
      return filtered;
    };
    return { ...diagnostic, aidesEligibles: filterMatches(diagnostic.aidesEligibles), aidesPotentiellementEligibles: filterMatches(diagnostic.aidesPotentiellementEligibles), aidesNonEligibles: filterMatches(diagnostic.aidesNonEligibles) };
  }, [diagnostic, filters.categories, filters.searchQuery, aideIdsWithDossier]);

  const [notFound, setNotFound] = useState(false);
  const addMonument = useMonumentStore((s) => s.addMonument);
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);

  useEffect(() => { if (!monument && monumentId) monumentService.getById(monumentId).then(addMonument).catch(() => setNotFound(true)); }, [monumentId]);
  useEffect(() => { if (monumentId && !diagnostic) aideService.getDiagnostics(monumentId).then((d) => { if (d.length > 0) setDiagnostic(monumentId, d[0]); }).catch(console.error); }, [monumentId]);
  useEffect(() => { if (!dossierLoaded) dossierService.fetchAll().catch(console.error); }, [dossierLoaded]);

  if (notFound || (!monument && !monumentId)) {
    return (
      <div className="space-y-4">
        <PageHeader title="Monument introuvable" />
        <p className="text-[14px] text-[#8E92A4]">Ce monument n'existe pas ou a été supprimé.</p>
        <Link to={ROUTES.MONUMENTS} className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#1A237E] hover:opacity-70 transition-opacity">
          <ChevronLeft className="h-3.5 w-3.5" /> Retour aux monuments
        </Link>
      </div>
    );
  }

  if (!monument) return <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin text-[#8E92A4]" /></div>;

  const handleSave = async (data: Partial<Monument>, pendingPhotos: PendingPhoto[]) => {
    setSaving(true);
    try {
      const updated = await monumentService.update(monument.id, data);
      updateMonument(monument.id, updated);
      if (user && pendingPhotos.length > 0) {
        for (const photo of pendingPhotos) {
          try {
            const doc = await uploadDocument({ file: photo.file, nom: photo.nom || `Photo — ${monument.nom}`, type: 'photo', monumentId: monument.id }, user.id);
            await monumentService.addPhoto(monument.id, { url: doc.url, legende: photo.nom || photo.file.name.replace(/\.[^.]+$/, ''), type: 'autre' });
          } catch (err) { console.error('Erreur upload photo:', err); }
        }
      }
      setIsEditing(false);
      toast.success('Monument mis à jour');
    } catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors de la sauvegarde'); }
    finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!confirm(`Supprimer "${monument.nom}" ? Cette action est irréversible.`)) return;
    setDeleting(true);
    try { await monumentService.delete(monument.id); deleteMonument(monument.id); toast.success('Monument supprimé'); navigate(ROUTES.MONUMENTS); }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression'); }
    finally { setDeleting(false); }
  };

  if (isEditing) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <button onClick={() => setIsEditing(false)} className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#1A237E] hover:opacity-70 transition-opacity">
            <ChevronLeft className="h-3.5 w-3.5" /> Retour
          </button>
          <h1 className="text-[18px] font-light text-[#1B1E2E]" style={{ fontFamily: FONT }}>Modifier — {monument.nom}</h1>
        </div>
        <MonumentForm initialData={monument} onSubmit={handleSave} isEditing saving={saving} />
      </div>
    );
  }

  const workTypeLabels = WORK_TYPES.reduce<Record<string, string>>((acc, w) => { acc[w.value] = w.label; return acc; }, {});

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-[13px] text-[#8E92A4]">
        <Link to={ROUTES.MONUMENTS} className="hover:text-[#1B1E2E] transition-colors">Monuments</Link>
        <span>/</span>
        <span className="text-[#1B1E2E]">{monument.nom}</span>
      </div>

      <PageHeader
        title={monument.nom}
        description={`${monument.commune} (${monument.departement}) — ${protectionLabels[monument.protection] ?? monument.protection}`}
        action={
          <div className="flex gap-2">
            <button onClick={handleDelete} disabled={deleting} className="flex items-center justify-center w-9 h-9 border border-[#E4E2DC] rounded-lg text-[#8E92A4] hover:text-red-600 hover:border-red-200 transition-colors">
              {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" strokeWidth={1.8} />}
            </button>
            <button onClick={() => setIsEditing(true)} className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg transition-all duration-300 hover:shadow-md" style={{ background: '#1A237E' }}>
              <Edit2 className="h-3.5 w-3.5" strokeWidth={1.8} />
              Modifier
            </button>
          </div>
        }
      />

      {/* Progress */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-[#8E92A4]">Fiche complétée</span>
          <span className="font-semibold text-[#1B1E2E]">{monument.completionPercentage} %</span>
        </div>
        <Progress value={monument.completionPercentage} className="h-2" />
      </div>

      <Tabs defaultValue={defaultTab}>
        <TabsList>
          <TabsTrigger value="informations" className="gap-1.5"><Eye className="h-4 w-4" />Informations</TabsTrigger>
          <TabsTrigger value="dossiers" className="gap-1.5"><ScrollText className="h-4 w-4" />Dossiers ({dossiers.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="informations" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Panel title="Identification" icon={<Building2 className="h-4 w-4 text-[#1A237E]" strokeWidth={1.8} />}>
              <div className="space-y-2 text-[13px]">
                <InfoRow label="Dénomination" value={monument.denomination} />
                {monument.referenceMerimee && <InfoRow label="Réf. Mérimée" value={monument.referenceMerimee} />}
                <InfoRow label="Localisation" value={monument.commune} />
                <InfoRow label="Département" value={monument.departement} />
                {monument.siecleConstruction && <InfoRow label="Siècle" value={monument.siecleConstruction} />}
              </div>
            </Panel>

            <Panel title="Statut juridique" icon={<Shield className="h-4 w-4 text-[#1A237E]" strokeWidth={1.8} />}>
              <div className="space-y-2 text-[13px]">
                <InfoRow label="Protection" value={protectionLabels[monument.protection] ?? monument.protection} />
                {monument.dateProtection && <InfoRow label="Date" value={formatDate(monument.dateProtection)} />}
                <InfoRow label="Propriétaire" value={OWNERSHIP_TYPES.find((o) => o.value === monument.proprietaire)?.label ?? monument.proprietaire} />
                {monument.affectataire && <InfoRow label="Affectation" value={monument.affectataire} />}
              </div>
            </Panel>

            <Panel title="État actuel" icon={<AlertTriangle className="h-4 w-4 text-[#D97706]" strokeWidth={1.8} />}>
              <div className="space-y-3 text-[13px]">
                <div className="flex items-center gap-2">
                  <span className="text-[#8E92A4]">Conservation :</span>
                  <Badge variant="outline" className="text-[12px] border-[#E4E2DC]">{etatLabels[monument.etatConservation] ?? monument.etatConservation}</Badge>
                </div>
                {monument.urgenceTravaux && (
                  <div className="flex items-center gap-2">
                    <span className="text-[#8E92A4]">Urgence :</span>
                    <Badge className={urgenceColors[monument.urgenceTravaux] ?? ''}>{monument.urgenceTravaux}</Badge>
                  </div>
                )}
                {monument.descriptionEtat && <p className="text-[#5C6178] leading-relaxed">{monument.descriptionEtat}</p>}
              </div>
            </Panel>

            <Panel title="Travaux envisagés" icon={<Wrench className="h-4 w-4 text-[#C75B3A]" strokeWidth={1.8} />}>
              {monument.travauxEnvisages && monument.travauxEnvisages.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {monument.travauxEnvisages.map((t) => (
                    <Badge key={t} className="text-[12px] bg-[#FBF0EC] text-[#C75B3A] border-0">{workTypeLabels[t] ?? t}</Badge>
                  ))}
                </div>
              ) : (
                <p className="text-[13px] text-[#8E92A4]">Aucun travail envisagé</p>
              )}
            </Panel>
          </div>

          {monument.descriptionGenerale && (
            <Panel title="Description générale">
              <p className="text-[13px] leading-relaxed text-[#5C6178]">{monument.descriptionGenerale}</p>
            </Panel>
          )}

          <div className="flex items-center gap-4 text-[12px] text-[#8E92A4]">
            <div className="flex items-center gap-1"><Calendar className="h-3 w-3" />Créé le {formatDate(monument.createdAt)}</div>
            <div className="flex items-center gap-1"><Calendar className="h-3 w-3" />Modifié le {formatDate(monument.updatedAt)}</div>
          </div>
        </TabsContent>

        <TabsContent value="dossiers" className="mt-4 space-y-6">
          {dossiers.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-[12px] font-semibold uppercase tracking-[0.1em] text-[#8E92A4]">Dossiers en cours</h3>
              {dossiers.map((dossier) => (
                <Link key={dossier.id} to={ROUTES.DOSSIER_DETAIL(dossier.id)}>
                  <div className="flex items-center justify-between gap-3 p-3 rounded-lg border border-[#E4E2DC] hover:bg-[#F8F7F4] transition-colors">
                    <p className="font-medium text-[13px] text-[#1B1E2E] truncate">{dossier.titre}</p>
                    <Progress value={dossier.progressionPourcentage} className="w-20 h-1.5 shrink-0" />
                  </div>
                </Link>
              ))}
            </div>
          )}

          {showDiagnostic || diagnostic ? (
            <div className="space-y-6">
              <AideMatchBanner result={diagnostic} isRunning={isRunningDiagnostic} onLaunch={handleLaunchDiagnostic} monumentName={monument.nom} />

              {diagnostic && !isRunningDiagnostic && (
                <div className="flex justify-end">
                  <button onClick={handleLaunchDiagnostic} className="inline-flex items-center gap-2 px-3 py-2 text-[12px] font-medium border border-[#E4E2DC] rounded-lg text-[#5C6178] hover:bg-[#F8F7F4] transition-colors">
                    <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.8} /> Refaire le diagnostic
                  </button>
                </div>
              )}

              {filteredDiagnostic && (
                <>
                  <AideFilterBar />
                  <Tabs defaultValue="eligible">
                    <TabsList>
                      <TabsTrigger value="eligible" className="gap-1.5"><CheckCircle2 className="h-4 w-4" />Éligibles ({filteredDiagnostic.aidesEligibles.length})</TabsTrigger>
                      <TabsTrigger value="potentially-eligible" className="gap-1.5"><HelpCircle className="h-4 w-4" />Potentiellement éligibles ({filteredDiagnostic.aidesPotentiellementEligibles.length})</TabsTrigger>
                      <TabsTrigger value="non-eligible" className="gap-1.5"><XCircle className="h-4 w-4" />Non éligibles ({filteredDiagnostic.aidesNonEligibles.length})</TabsTrigger>
                    </TabsList>
                    <TabsContent value="eligible" className="mt-4">
                      {filteredDiagnostic.aidesEligibles.length === 0 ? (
                        <EmptyState icon={Search} title="Aucune aide éligible trouvée" description="Essayez de modifier les filtres ou vérifiez les informations de votre monument." />
                      ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">{filteredDiagnostic.aidesEligibles.map((match) => (<AideCard key={match.aide.id} match={match} />))}</div>
                      )}
                    </TabsContent>
                    <TabsContent value="potentially-eligible" className="mt-4">
                      {filteredDiagnostic.aidesPotentiellementEligibles.length === 0 ? (
                        <EmptyState icon={HelpCircle} title="Aucune aide potentiellement éligible" description="Toutes les aides ont pu être classées avec certitude." />
                      ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">{filteredDiagnostic.aidesPotentiellementEligibles.map((match) => (<AideCard key={match.aide.id} match={match} />))}</div>
                      )}
                    </TabsContent>
                    <TabsContent value="non-eligible" className="mt-4">
                      {filteredDiagnostic.aidesNonEligibles.length === 0 ? (
                        <EmptyState icon={CheckCircle2} title="Toutes les aides sont éligibles" description="Votre monument est éligible à toutes les aides analysées." />
                      ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">{filteredDiagnostic.aidesNonEligibles.map((match) => (<AideCard key={match.aide.id} match={match} />))}</div>
                      )}
                    </TabsContent>
                  </Tabs>
                </>
              )}
            </div>
          ) : (
            <div className="bg-[#E8EAF6]/30 border border-[#E8EAF6] rounded-xl py-10 text-center space-y-4">
              <div className="mx-auto w-14 h-14 rounded-full bg-[#E8EAF6] flex items-center justify-center">
                <Compass className="h-7 w-7 text-[#1A237E]" />
              </div>
              <div>
                <h2 className="text-[18px] font-light text-[#1B1E2E]" style={{ fontFamily: FONT }}>
                  Découvrez les aides disponibles pour <em className="italic" style={{ color: '#C75B3A' }}>{monument.nom}</em>
                </h2>
                <p className="text-[14px] text-[#8E92A4] mt-1">Notre moteur analyse toutes les aides publiques et privées applicables à votre monument.</p>
              </div>
              <button
                onClick={() => { setShowDiagnostic(true); if (!diagnostic) handleLaunchDiagnostic(); }}
                className="inline-flex items-center gap-2 px-6 py-3 text-[13px] font-semibold text-white rounded-lg transition-all duration-300 hover:shadow-md"
                style={{ background: '#1A237E' }}
              >
                <Compass className="h-4 w-4" strokeWidth={1.8} />
                {diagnostic || dossiers.length > 0 ? 'Voir le diagnostic' : 'Lancer un diagnostic'}
              </button>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Panel({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-[#E4E2DC]/80 overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-[#E4E2DC]">
        {icon && <div className="w-7 h-7 rounded-lg bg-[#F8F7F4] flex items-center justify-center">{icon}</div>}
        <h3 className="text-[15px] font-normal text-[#1B1E2E]" style={{ fontFamily: "'Cormorant Garamond', serif" }}>{title}</h3>
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-[#8E92A4] shrink-0">{label} :</span>
      <span className="font-medium text-[#1B1E2E]">{value}</span>
    </div>
  );
}
