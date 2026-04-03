import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router';
import {
  ChevronLeft, ClipboardList, FileEdit, Calendar, Users,
  Check, AlertTriangle, Loader2,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
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

const FONT = "'Cormorant Garamond', serif";

export function DossierDetailPage() {
  const { dossierId } = useParams();
  const dossier = useDossierStore((s) => s.dossiers.find((d) => d.id === dossierId));
  const addDossier = useDossierStore((s) => s.addDossier);
  const aide = useAideStore((s) => dossier ? s.aides.find((a) => a.id === dossier.aideId) : undefined);
  const monument = useMonumentStore((s) => dossier ? s.monuments.find((m) => m.id === dossier.monumentId) : undefined);

  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!dossier && dossierId && !loading && !notFound) {
      setLoading(true);
      dossierService.getById(dossierId)
        .then((d) => addDossier(d))
        .catch(() => setNotFound(true))
        .finally(() => setLoading(false));
    }
  }, [dossier, dossierId]);

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin text-[#8E92A4]" /></div>;

  if (!dossier || notFound) {
    return (
      <div className="space-y-4">
        <PageHeader title="Dossier introuvable" />
        <p className="text-[14px] text-[#8E92A4]">Ce dossier n'existe pas ou a été supprimé.</p>
        <Link to={ROUTES.DOSSIERS} className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[#1A237E] hover:opacity-70 transition-opacity">
          <ChevronLeft className="h-3.5 w-3.5" /> Retour aux dossiers
        </Link>
      </div>
    );
  }

  const statusConfig = DOSSIER_STATUS_LABELS[dossier.statut];
  const currentStep = DOSSIER_STEPS.find((s) => s.step === dossier.etapeActuelle);

  const handleChecklistChange = (itemId: string, statut: ChecklistItemStatus) => {
    dossierService.updateChecklistItem(dossier.id, itemId, statut).catch(console.error);
  };

  const handleSectionChange = (sectionId: string, contenu: string) => {
    dossierService.updateSection(dossier.id, sectionId, contenu).catch(console.error);
  };

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-[13px] text-[#8E92A4]">
        <Link to={ROUTES.DOSSIERS} className="hover:text-[#1B1E2E] transition-colors">Dossiers</Link>
        <span>/</span>
        <span className="text-[#1B1E2E] truncate">{dossier.titre}</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge className={statusConfig?.color ?? ''}>{statusConfig?.label ?? dossier.statut}</Badge>
            <span className="text-[13px] text-[#8E92A4]">Étape {dossier.etapeActuelle}/5 — {currentStep?.label}</span>
          </div>
          <h1 className="text-[clamp(1.4rem,3vw,1.8rem)] font-light tracking-[-0.02em] text-[#1B1E2E]" style={{ fontFamily: FONT }}>
            {dossier.titre}
          </h1>
          {dossier.description && <p className="text-[14px] text-[#5C6178]">{dossier.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          {monument && (
            <Link to={ROUTES.MONUMENT_DETAIL(monument.id)} className="px-3 py-2 text-[12px] font-medium border border-[#E4E2DC] rounded-lg text-[#5C6178] hover:bg-[#F8F7F4] transition-colors">
              Voir le monument
            </Link>
          )}
          {aide && (
            <Link to={ROUTES.AIDE_DETAIL(aide.id)} className="px-3 py-2 text-[12px] font-medium border border-[#E4E2DC] rounded-lg text-[#5C6178] hover:bg-[#F8F7F4] transition-colors">
              Voir l'aide
            </Link>
          )}
        </div>
      </div>

      {/* Progress */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-[#8E92A4]">Progression</span>
          <span className="font-semibold text-[#1B1E2E]">{dossier.progressionPourcentage} %</span>
        </div>
        <Progress value={dossier.progressionPourcentage} className="h-2" />
      </div>

      {/* Step indicator */}
      <div className="flex items-center justify-between">
        {DOSSIER_STEPS.map((step, i) => (
          <div key={step.step} className="flex items-center flex-1">
            <div className="flex items-center gap-1.5 shrink-0">
              <div className={cn(
                'w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium border-2',
                step.step < dossier.etapeActuelle && 'border-green-600 bg-green-600 text-white',
                step.step === dossier.etapeActuelle && 'border-[#1A237E] bg-[#1A237E] text-white',
                step.step > dossier.etapeActuelle && 'border-[#E4E2DC] text-[#8E92A4]',
              )}>
                {step.step < dossier.etapeActuelle ? <Check className="h-3.5 w-3.5" /> : step.step}
              </div>
              <span className="text-[11px] hidden lg:block text-[#5C6178]">{step.label}</span>
            </div>
            {i < DOSSIER_STEPS.length - 1 && (
              <div className={cn('h-px flex-1 mx-2', step.step < dossier.etapeActuelle ? 'bg-green-600' : 'bg-[#E4E2DC]')} />
            )}
          </div>
        ))}
      </div>

      {/* Main content */}
      <Tabs defaultValue="checklist">
        <TabsList>
          <TabsTrigger value="checklist" className="gap-1.5"><ClipboardList className="h-4 w-4" />Pièces ({dossier.checklist.length})</TabsTrigger>
          <TabsTrigger value="sections" className="gap-1.5"><FileEdit className="h-4 w-4" />Formulaire ({dossier.sections.length})</TabsTrigger>
          <TabsTrigger value="echeances" className="gap-1.5"><Calendar className="h-4 w-4" />Échéances ({dossier.echeances.length})</TabsTrigger>
          <TabsTrigger value="collaborateurs" className="gap-1.5"><Users className="h-4 w-4" />Équipe ({dossier.collaborateurs.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="checklist" className="mt-4">
          <Panel title="Pièces du dossier">
            <DossierChecklist items={dossier.checklist} onStatusChange={handleChecklistChange} readOnly={dossier.statut === 'soumis'} />
          </Panel>
        </TabsContent>

        <TabsContent value="sections" className="mt-4 space-y-4">
          {dossier.sections.sort((a, b) => a.ordre - b.ordre).map((section) => (
            <Panel key={section.id} title={section.titre}>
              {section.champsAutoremplis && section.champsAutoremplis.length > 0 && (
                <div className="text-[12px] space-y-1 p-3 rounded-lg bg-[#E8EAF6]/50 border border-[#E8EAF6] mb-3">
                  <p className="font-semibold text-[#1A237E]">Champs pré-remplis :</p>
                  {section.champsAutoremplis.map((champ, i) => (
                    <div key={i} className="flex gap-2 text-[#3949AB]">
                      <span>{champ.champ} :</span>
                      <span className="font-medium">{champ.valeur}</span>
                      <Badge variant="outline" className="text-[10px] h-4 px-1">{champ.source}</Badge>
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
                className="text-[14px] bg-white border-[#E4E2DC] focus:border-[#1A237E] focus:ring-[#1A237E]/10"
              />
            </Panel>
          ))}
        </TabsContent>

        <TabsContent value="echeances" className="mt-4">
          <Panel title="Échéances">
            {dossier.echeances.length === 0 ? (
              <p className="text-[13px] text-[#8E92A4]">Aucune échéance définie.</p>
            ) : (
              <div className="space-y-2">
                {dossier.echeances.map((ech) => {
                  const days = daysUntil(ech.date);
                  const urgent = isUrgent(ech.date);
                  return (
                    <div key={ech.id} className={cn(
                      'flex items-center gap-3 p-3 rounded-lg border',
                      ech.accomplie && 'bg-green-50 border-green-200',
                      !ech.accomplie && urgent && 'bg-red-50 border-red-200',
                      !ech.accomplie && !urgent && 'border-[#E4E2DC]',
                    )}>
                      {ech.accomplie ? <Check className="h-4 w-4 text-green-600" /> : urgent ? <AlertTriangle className="h-4 w-4 text-red-600" /> : <Calendar className="h-4 w-4 text-[#8E92A4]" />}
                      <div className="flex-1">
                        <p className="text-[13px] font-medium text-[#1B1E2E]">{ech.label}</p>
                        <p className="text-[12px] text-[#8E92A4]">{formatDate(ech.date)}{!ech.accomplie && days >= 0 && ` — dans ${days} jour${days > 1 ? 's' : ''}`}</p>
                      </div>
                      <Badge variant="outline" className="text-[11px] border-[#E4E2DC]">{ech.type}</Badge>
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>
        </TabsContent>

        <TabsContent value="collaborateurs" className="mt-4">
          <Panel title="Équipe du dossier">
            {dossier.collaborateurs.length === 0 ? (
              <p className="text-[13px] text-[#8E92A4]">Aucun collaborateur. Vous travaillez seul sur ce dossier.</p>
            ) : (
              <div className="space-y-2">
                {dossier.collaborateurs.map((collab) => (
                  <div key={collab.id} className="flex items-center justify-between p-3 rounded-lg border border-[#E4E2DC]">
                    <div>
                      <p className="text-[13px] font-medium text-[#1B1E2E]">{collab.nom}</p>
                      <p className="text-[12px] text-[#8E92A4]">{collab.email}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-[11px] border-[#E4E2DC]">{collab.role}</Badge>
                      <Badge className="text-[11px] bg-[#E8EAF6] text-[#1A237E] border-0">{collab.permissions}</Badge>
                      {collab.inviteAcceptee ? <Check className="h-3.5 w-3.5 text-green-600" /> : <Clock className="h-3.5 w-3.5 text-amber-500" />}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </TabsContent>
      </Tabs>

      {/* Disclaimer */}
      {dossier.statut !== 'soumis' && (
        <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-200 bg-amber-50">
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-[13px]">
            <p className="font-semibold text-amber-800">Dépôt manuel obligatoire</p>
            <p className="text-amber-700 mt-0.5">PatriAlta vous aide à préparer votre dossier, mais le dépôt auprès de l'organisme doit être effectué par vos soins.</p>
          </div>
        </div>
      )}

      {dossier.montantEstime && (
        <div className="text-[13px] text-[#8E92A4]">
          Montant estimé des travaux : <span className="font-semibold text-[#1B1E2E]">{formatCurrency(dossier.montantEstime)}</span>
        </div>
      )}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-[#E4E2DC]/80 overflow-hidden">
      <div className="px-5 py-3 border-b border-[#E4E2DC]">
        <h3 className="text-[15px] font-normal text-[#1B1E2E]" style={{ fontFamily: "'Cormorant Garamond', serif" }}>{title}</h3>
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}

function Clock(props: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={props.className}>
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
    </svg>
  );
}
