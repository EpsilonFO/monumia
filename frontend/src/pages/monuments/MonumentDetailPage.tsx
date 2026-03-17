import { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router';
import {
  Shield, Calendar, AlertTriangle, Wrench, Building2,
  FileText, ChevronLeft, Edit2, Eye, Trash2, Loader2,
  Sparkles, CheckCircle2, XCircle, Search,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { AideMatchBanner } from '@/components/aide/AideMatchBanner';
import { AideCard } from '@/components/aide/AideCard';
import { AideFilterBar } from '@/components/aide/AideFilterBar';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { monumentService } from '@/services/monument.service';
import { aideService } from '@/services/aide.service';
import { dossierService } from '@/services/dossier.service';
import { formatDate } from '@/lib/date-utils';
import { ROUTES } from '@/constants/routes';
import { WORK_TYPES } from '@/constants/monument-options';
import { toast } from 'sonner';
import type { Monument, AideDiagnosticResult } from '@/types';

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
  const dossiers = useMemo(
    () => allDossiers.filter((d) => d.monumentId === monumentId),
    [allDossiers, monumentId]
  );
  const diagnosticsByMonument = useAideStore((s) => s.diagnosticsByMonument);
  const filters = useAideStore((s) => s.filters);
  const diagnostic = monumentId ? diagnosticsByMonument[monumentId] ?? null : null;

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
      await aideService.runDiagnostic(
        monumentId,
        filters.modeProjet,
        filters.travauxFiltres.length > 0 ? filters.travauxFiltres : undefined
      );
    } catch (err) {
      console.error('Diagnostic error:', err);
    } finally {
      setIsRunningDiagnostic(false);
    }
  }, [monumentId, filters.modeProjet, filters.travauxFiltres]);

  const aideIdsWithDossier = useMemo(
    () => new Set(dossiers.map((d) => d.aideId)),
    [dossiers]
  );

  const filteredDiagnostic = useMemo((): AideDiagnosticResult | null => {
    if (!diagnostic) return null;
    const catFilter = filters.categories;
    const query = filters.searchQuery.toLowerCase();

    const filterMatches = (matches: typeof diagnostic.aidesEligibles) => {
      let filtered = matches.filter((m) => !aideIdsWithDossier.has(m.aide.id));
      if (catFilter.length > 0) {
        filtered = filtered.filter((m) => catFilter.includes(m.aide.categorie));
      }
      if (query) {
        filtered = filtered.filter(
          (m) =>
            m.aide.nom.toLowerCase().includes(query) ||
            m.aide.nomCourt.toLowerCase().includes(query) ||
            m.aide.organisme.toLowerCase().includes(query)
        );
      }
      return filtered;
    };

    return {
      ...diagnostic,
      aidesEligibles: filterMatches(diagnostic.aidesEligibles),
      aidesNonEligibles: filterMatches(diagnostic.aidesNonEligibles),
    };
  }, [diagnostic, filters.categories, filters.searchQuery, aideIdsWithDossier]);

  // If the monument isn't in the store yet (direct URL), fetch it
  const [notFound, setNotFound] = useState(false);
  const addMonument = useMonumentStore((s) => s.addMonument);
  useEffect(() => {
    if (!monument && monumentId) {
      monumentService.getById(monumentId)
        .then(addMonument)
        .catch(() => setNotFound(true));
    }
  }, [monumentId]);

  // Fetch dossiers from API if not loaded yet
  useEffect(() => {
    if (!dossierLoaded) {
      dossierService.fetchAll().catch(console.error);
    }
  }, [dossierLoaded]);

  if (notFound || (!monument && !monumentId)) {
    return (
      <div className="space-y-4">
        <PageHeader title="Monument introuvable" />
        <p className="text-muted-foreground">Ce monument n'existe pas ou a été supprimé.</p>
        <Button asChild variant="outline">
          <Link to={ROUTES.MONUMENTS}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Retour aux monuments
          </Link>
        </Button>
      </div>
    );
  }

  if (!monument) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const handleSave = async (data: Partial<Monument>) => {
    setSaving(true);
    try {
      const updated = await monumentService.update(monument.id, data);
      updateMonument(monument.id, updated);
      setIsEditing(false);
      toast.success('Monument mis à jour');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Supprimer "${monument.nom}" ? Cette action est irréversible.`)) return;
    setDeleting(true);
    try {
      await monumentService.delete(monument.id);
      deleteMonument(monument.id);
      toast.success('Monument supprimé');
      navigate(ROUTES.MONUMENTS);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erreur lors de la suppression');
    } finally {
      setDeleting(false);
    }
  };

  if (isEditing) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setIsEditing(false)}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Retour
          </Button>
          <h1 className="text-xl font-bold">Modifier — {monument.nom}</h1>
        </div>
        <MonumentForm initialData={monument} onSubmit={handleSave} isEditing saving={saving} />
      </div>
    );
  }

  const workTypeLabels = WORK_TYPES.reduce<Record<string, string>>((acc, w) => {
    acc[w.value] = w.label;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to={ROUTES.MONUMENTS} className="hover:text-foreground transition-colors">
          Monuments
        </Link>
        <span>/</span>
        <span className="text-foreground">{monument.nom}</span>
      </div>

      <PageHeader
        title={monument.nom}
        description={`${monument.commune} (${monument.departement}) — ${protectionLabels[monument.protection] ?? monument.protection}`}
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleDelete} disabled={deleting}>
              {deleting
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <Trash2 className="h-4 w-4" />}
            </Button>
            <Button onClick={() => setIsEditing(true)}>
              <Edit2 className="h-4 w-4 mr-2" />
              Modifier la fiche
            </Button>
          </div>
        }
      />

      <div className="space-y-1">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Fiche complétée</span>
          <span className="font-medium">{monument.completionPercentage} %</span>
        </div>
        <Progress value={monument.completionPercentage} className="h-2" />
      </div>

      <Tabs defaultValue={defaultTab}>
        <TabsList>
          <TabsTrigger value="informations" className="gap-1.5">
            <Eye className="h-4 w-4" />
            Informations
          </TabsTrigger>
          <TabsTrigger value="dossiers" className="gap-1.5">
            <FileText className="h-4 w-4" />
            Dossiers ({dossiers.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="informations" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  Identification
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <InfoRow label="Dénomination" value={monument.denomination} />
                {monument.referenceMerimee && (
                  <InfoRow label="Réf. Mérimée" value={monument.referenceMerimee} />
                )}
                <InfoRow
                  label="Localisation"
                  value={[monument.codePostal, monument.commune].filter(Boolean).join(', ')}
                />
                <InfoRow label="Département" value={monument.departement} />
                {monument.siecleConstruction && (
                  <InfoRow label="Siècle" value={monument.siecleConstruction} />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  Statut juridique
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <InfoRow
                  label="Protection"
                  value={protectionLabels[monument.protection] ?? monument.protection}
                />
                {monument.dateProtection && (
                  <InfoRow label="Date" value={formatDate(monument.dateProtection)} />
                )}
                <InfoRow label="Propriétaire" value={monument.proprietaire} />
                {monument.affectataire && (
                  <InfoRow label="Affectation" value={monument.affectataire} />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  État actuel
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">Conservation :</span>
                  <Badge variant="outline">
                    {etatLabels[monument.etatConservation] ?? monument.etatConservation}
                  </Badge>
                </div>
                {monument.urgenceTravaux && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">Urgence :</span>
                    <Badge className={urgenceColors[monument.urgenceTravaux] ?? ''}>
                      {monument.urgenceTravaux}
                    </Badge>
                  </div>
                )}
                {monument.descriptionEtat && (
                  <p className="text-muted-foreground leading-relaxed">
                    {monument.descriptionEtat}
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Wrench className="h-4 w-4" />
                  Travaux envisagés
                </CardTitle>
              </CardHeader>
              <CardContent>
                {monument.travauxEnvisages && monument.travauxEnvisages.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {monument.travauxEnvisages.map((t) => (
                      <Badge key={t} variant="secondary">
                        {workTypeLabels[t] ?? t}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Aucun travail envisagé</p>
                )}
              </CardContent>
            </Card>
          </div>

          {monument.descriptionGenerale && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Description générale</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed">{monument.descriptionGenerale}</p>
              </CardContent>
            </Card>
          )}

          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              Créé le {formatDate(monument.createdAt)}
            </div>
            <div className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              Modifié le {formatDate(monument.updatedAt)}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="dossiers" className="mt-4 space-y-6">
          {/* Existing dossiers */}
          {dossiers.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Dossiers en cours
              </h3>
              {dossiers.map((dossier) => (
                <Link key={dossier.id} to={ROUTES.DOSSIER_DETAIL(dossier.id)}>
                  <div className="flex items-center justify-between gap-3 p-2.5 rounded-lg border hover:bg-muted/50 transition-colors">
                    <p className="font-medium text-sm truncate">{dossier.titre}</p>
                    <Progress value={dossier.progressionPourcentage} className="w-20 h-1.5 shrink-0" />
                  </div>
                </Link>
              ))}
            </div>
          )}

          {/* Diagnostic section */}
          {showDiagnostic || diagnostic ? (
            <div className="space-y-6">
              <AideMatchBanner
                result={diagnostic}
                isRunning={isRunningDiagnostic}
                onLaunch={handleLaunchDiagnostic}
                monumentName={monument.nom}
              />

              {filteredDiagnostic && (
                <>
                  <AideFilterBar />

                  <Tabs defaultValue="eligible">
                    <TabsList>
                      <TabsTrigger value="eligible" className="gap-1.5">
                        <CheckCircle2 className="h-4 w-4" />
                        Éligibles ({filteredDiagnostic.aidesEligibles.length})
                      </TabsTrigger>
                      <TabsTrigger value="non-eligible" className="gap-1.5">
                        <XCircle className="h-4 w-4" />
                        Non éligibles ({filteredDiagnostic.aidesNonEligibles.length})
                      </TabsTrigger>
                    </TabsList>

                    <TabsContent value="eligible" className="mt-4">
                      {filteredDiagnostic.aidesEligibles.length === 0 ? (
                        <EmptyState
                          icon={Search}
                          title="Aucune aide éligible trouvée"
                          description="Essayez de modifier les filtres ou vérifiez les informations de votre monument."
                        />
                      ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                          {filteredDiagnostic.aidesEligibles.map((match) => (
                            <AideCard key={match.aide.id} match={match} />
                          ))}
                        </div>
                      )}
                    </TabsContent>

                    <TabsContent value="non-eligible" className="mt-4">
                      {filteredDiagnostic.aidesNonEligibles.length === 0 ? (
                        <EmptyState
                          icon={CheckCircle2}
                          title="Toutes les aides sont éligibles"
                          description="Votre monument est éligible à toutes les aides analysées."
                        />
                      ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                          {filteredDiagnostic.aidesNonEligibles.map((match) => (
                            <AideCard key={match.aide.id} match={match} />
                          ))}
                        </div>
                      )}
                    </TabsContent>
                  </Tabs>
                </>
              )}
            </div>
          ) : (
            <Card className="border-primary/20 bg-primary/5">
              <CardContent className="py-8 text-center space-y-4">
                <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                  <Sparkles className="h-8 w-8 text-primary" />
                </div>
                <div>
                  <h2 className="text-xl font-bold">
                    Découvrez les aides disponibles pour {monument.nom}
                  </h2>
                  <p className="text-muted-foreground mt-1">
                    Notre moteur analyse toutes les aides publiques et privées applicables à votre monument.
                  </p>
                </div>
                <Button size="lg" onClick={() => { setShowDiagnostic(true); if (!diagnostic) handleLaunchDiagnostic(); }}>
                  <Sparkles className="h-4 w-4 mr-2" />
                  {diagnostic || dossiers.length > 0 ? 'Voir le diagnostic' : 'Lancer un diagnostic'}
                </Button>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-muted-foreground shrink-0">{label} :</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
