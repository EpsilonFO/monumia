import { useParams, Link } from 'react-router';
import {
  ChevronLeft, ClipboardList, FileEdit, Calendar, Users,
  Check, AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { PageHeader } from '@/components/shared/PageHeader';
import { DossierChecklist } from '@/components/dossier/DossierChecklist';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { dossierService } from '@/services/dossier.service';
import { DOSSIER_STEPS, DOSSIER_STATUS_LABELS } from '@/constants/dossier-steps';
import { ROUTES } from '@/constants/routes';
import { formatDate, daysUntil, isUrgent } from '@/lib/date-utils';
import { formatCurrency } from '@/lib/format-utils';
import { cn } from '@/lib/utils';
import type { ChecklistItemStatus } from '@/types';

export function DossierDetailPage() {
  const { dossierId } = useParams();
  const dossier = useDossierStore((s) => s.dossiers.find((d) => d.id === dossierId));
  const aide = useAideStore((s) => dossier ? s.aides.find((a) => a.id === dossier.aideId) : undefined);
  const monument = useMonumentStore((s) => dossier ? s.monuments.find((m) => m.id === dossier.monumentId) : undefined);

  if (!dossier) {
    return (
      <div className="space-y-4">
        <PageHeader title="Dossier introuvable" />
        <p className="text-muted-foreground">Ce dossier n'existe pas ou a été supprimé.</p>
        <Button asChild variant="outline">
          <Link to={ROUTES.DOSSIERS}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Retour aux dossiers
          </Link>
        </Button>
      </div>
    );
  }

  const statusConfig = DOSSIER_STATUS_LABELS[dossier.statut];
  const currentStep = DOSSIER_STEPS.find((s) => s.step === dossier.etapeActuelle);

  const handleChecklistChange = (itemId: string, statut: ChecklistItemStatus) => {
    dossierService.updateChecklistItem(dossier.id, itemId, statut);
  };

  const handleSectionChange = (sectionId: string, contenu: string) => {
    dossierService.updateSection(dossier.id, sectionId, contenu);
  };

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to={ROUTES.DOSSIERS} className="hover:text-foreground transition-colors">
          Dossiers
        </Link>
        <span>/</span>
        <span className="text-foreground truncate">{dossier.titre}</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge className={statusConfig?.color ?? ''}>
              {statusConfig?.label ?? dossier.statut}
            </Badge>
            <span className="text-sm text-muted-foreground">
              Étape {dossier.etapeActuelle}/5 — {currentStep?.label}
            </span>
          </div>
          <h1 className="text-2xl font-bold">{dossier.titre}</h1>
          {dossier.description && (
            <p className="text-muted-foreground">{dossier.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {monument && (
            <Button asChild variant="outline" size="sm">
              <Link to={ROUTES.MONUMENT_DETAIL(monument.id)}>
                Voir le monument
              </Link>
            </Button>
          )}
          {aide && (
            <Button asChild variant="outline" size="sm">
              <Link to={ROUTES.AIDE_DETAIL(aide.id)}>
                Voir l'aide
              </Link>
            </Button>
          )}
        </div>
      </div>

      {/* Progress */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Progression</span>
          <span className="font-medium">{dossier.progressionPourcentage} %</span>
        </div>
        <Progress value={dossier.progressionPourcentage} className="h-2" />
      </div>

      {/* Step indicator */}
      <div className="flex items-center justify-between">
        {DOSSIER_STEPS.map((step, i) => (
          <div key={step.step} className="flex items-center flex-1">
            <div className="flex items-center gap-1.5 shrink-0">
              <div
                className={cn(
                  'w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium border-2',
                  step.step < dossier.etapeActuelle && 'border-green-600 bg-green-600 text-white',
                  step.step === dossier.etapeActuelle && 'border-primary bg-primary text-primary-foreground',
                  step.step > dossier.etapeActuelle && 'border-muted-foreground/30 text-muted-foreground',
                )}
              >
                {step.step < dossier.etapeActuelle ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  step.step
                )}
              </div>
              <span className="text-xs hidden lg:block">{step.label}</span>
            </div>
            {i < DOSSIER_STEPS.length - 1 && (
              <div className={cn('h-px flex-1 mx-2', step.step < dossier.etapeActuelle ? 'bg-green-600' : 'bg-border')} />
            )}
          </div>
        ))}
      </div>

      {/* Main content */}
      <Tabs defaultValue="checklist">
        <TabsList>
          <TabsTrigger value="checklist" className="gap-1.5">
            <ClipboardList className="h-4 w-4" />
            Pièces ({dossier.checklist.length})
          </TabsTrigger>
          <TabsTrigger value="sections" className="gap-1.5">
            <FileEdit className="h-4 w-4" />
            Formulaire ({dossier.sections.length})
          </TabsTrigger>
          <TabsTrigger value="echeances" className="gap-1.5">
            <Calendar className="h-4 w-4" />
            Échéances ({dossier.echeances.length})
          </TabsTrigger>
          <TabsTrigger value="collaborateurs" className="gap-1.5">
            <Users className="h-4 w-4" />
            Équipe ({dossier.collaborateurs.length})
          </TabsTrigger>
        </TabsList>

        {/* Checklist tab */}
        <TabsContent value="checklist" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Pièces du dossier</CardTitle>
            </CardHeader>
            <CardContent>
              <DossierChecklist
                items={dossier.checklist}
                onStatusChange={handleChecklistChange}
                readOnly={dossier.statut === 'soumis'}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sections tab */}
        <TabsContent value="sections" className="mt-4 space-y-4">
          {dossier.sections
            .sort((a, b) => a.ordre - b.ordre)
            .map((section) => (
              <Card key={section.id}>
                <CardHeader>
                  <CardTitle className="text-base">{section.titre}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {section.champsAutoremplis && section.champsAutoremplis.length > 0 && (
                    <div className="text-xs space-y-1 p-2 rounded bg-blue-50 border border-blue-100">
                      <p className="font-medium text-blue-700">Champs pré-remplis :</p>
                      {section.champsAutoremplis.map((champ, i) => (
                        <div key={i} className="flex gap-2 text-blue-600">
                          <span>{champ.champ} :</span>
                          <span className="font-medium">{champ.valeur}</span>
                          <Badge variant="outline" className="text-[10px] h-4 px-1">
                            {champ.source}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                  <Textarea
                    value={section.contenu}
                    onChange={(e) => handleSectionChange(section.id, e.target.value)}
                    placeholder="Rédigez cette section..."
                    rows={6}
                    disabled={dossier.statut === 'soumis'}
                  />
                </CardContent>
              </Card>
            ))}
        </TabsContent>

        {/* Echéances tab */}
        <TabsContent value="echeances" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Échéances</CardTitle>
            </CardHeader>
            <CardContent>
              {dossier.echeances.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune échéance définie.</p>
              ) : (
                <div className="space-y-3">
                  {dossier.echeances.map((ech) => {
                    const days = daysUntil(ech.date);
                    const urgent = isUrgent(ech.date);

                    return (
                      <div
                        key={ech.id}
                        className={cn(
                          'flex items-center gap-3 p-3 rounded-lg border',
                          ech.accomplie && 'bg-green-50 border-green-200',
                          !ech.accomplie && urgent && 'bg-red-50 border-red-200',
                        )}
                      >
                        {ech.accomplie ? (
                          <Check className="h-4 w-4 text-green-600" />
                        ) : urgent ? (
                          <AlertTriangle className="h-4 w-4 text-red-600" />
                        ) : (
                          <Calendar className="h-4 w-4 text-muted-foreground" />
                        )}
                        <div className="flex-1">
                          <p className="text-sm font-medium">{ech.label}</p>
                          <p className="text-xs text-muted-foreground">
                            {formatDate(ech.date)}
                            {!ech.accomplie && days >= 0 && ` — dans ${days} jour${days > 1 ? 's' : ''}`}
                          </p>
                        </div>
                        <Badge variant="outline" className="text-xs">
                          {ech.type}
                        </Badge>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Collaborateurs tab */}
        <TabsContent value="collaborateurs" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Équipe du dossier</CardTitle>
            </CardHeader>
            <CardContent>
              {dossier.collaborateurs.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Aucun collaborateur. Vous travaillez seul sur ce dossier.
                </p>
              ) : (
                <div className="space-y-3">
                  {dossier.collaborateurs.map((collab) => (
                    <div
                      key={collab.id}
                      className="flex items-center justify-between p-3 rounded-lg border"
                    >
                      <div>
                        <p className="text-sm font-medium">{collab.nom}</p>
                        <p className="text-xs text-muted-foreground">{collab.email}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          {collab.role}
                        </Badge>
                        <Badge
                          variant="secondary"
                          className="text-xs"
                        >
                          {collab.permissions}
                        </Badge>
                        {collab.inviteAcceptee ? (
                          <Check className="h-3.5 w-3.5 text-green-600" />
                        ) : (
                          <Clock className="h-3.5 w-3.5 text-amber-500" />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Disclaimer for step 5 */}
      {dossier.statut !== 'soumis' && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="py-4 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-amber-800">Dépôt manuel obligatoire</p>
              <p className="text-amber-700 mt-0.5">
                PatriAlta vous aide à préparer votre dossier, mais le dépôt auprès de l'organisme
                doit être effectué par vos soins. Nous ne soumettons jamais de dossier automatiquement.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Amount info */}
      {dossier.montantEstime && (
        <div className="text-sm text-muted-foreground">
          Montant estimé des travaux : <span className="font-medium text-foreground">{formatCurrency(dossier.montantEstime)}</span>
        </div>
      )}
    </div>
  );
}

function Clock(props: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}
