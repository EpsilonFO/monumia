import { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router';
import {
  Shield, Calendar, AlertTriangle, Wrench, Building2,
  FileText, ChevronLeft, Edit2, Eye,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeader } from '@/components/shared/PageHeader';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { monumentService } from '@/services/monument.service';
import { formatDate } from '@/lib/date-utils';
import { ROUTES } from '@/constants/routes';
import { WORK_TYPES } from '@/constants/monument-options';
import type { Monument } from '@/types';

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
  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId));
  const allDossiers = useDossierStore((s) => s.dossiers);
  const dossiers = useMemo(
    () => allDossiers.filter((d) => d.monumentId === monumentId),
    [allDossiers, monumentId]
  );
  const [isEditing, setIsEditing] = useState(false);

  if (!monument) {
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

  const handleSave = (data: Partial<Monument>) => {
    monumentService.update(monument.id, data);
    setIsEditing(false);
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
        <MonumentForm initialData={monument} onSubmit={handleSave} isEditing />
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
          <Button onClick={() => setIsEditing(true)}>
            <Edit2 className="h-4 w-4 mr-2" />
            Modifier la fiche
          </Button>
        }
      />

      <div className="space-y-1">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Fiche complétée</span>
          <span className="font-medium">{monument.completionPercentage} %</span>
        </div>
        <Progress value={monument.completionPercentage} className="h-2" />
      </div>

      <Tabs defaultValue="informations">
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
                  label="Adresse"
                  value={`${monument.adresse}, ${monument.codePostal} ${monument.commune}`}
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

        <TabsContent value="dossiers" className="mt-4 space-y-3">
          {dossiers.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <FileText className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">
                  Aucun dossier pour ce monument.
                </p>
                <Button asChild variant="outline" size="sm" className="mt-3">
                  <Link to={ROUTES.AIDES}>Lancer un diagnostic d'aides</Link>
                </Button>
              </CardContent>
            </Card>
          ) : (
            dossiers.map((dossier) => (
              <Link key={dossier.id} to={ROUTES.DOSSIER_DETAIL(dossier.id)}>
                <Card className="hover:border-primary/30 transition-colors">
                  <CardContent className="py-4 flex items-center justify-between gap-4">
                    <div>
                      <p className="font-medium text-sm">{dossier.titre}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Étape {dossier.etapeActuelle}/5 — {dossier.statut}
                      </p>
                    </div>
                    <Progress value={dossier.progressionPourcentage} className="w-24 h-1.5" />
                  </CardContent>
                </Card>
              </Link>
            ))
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
