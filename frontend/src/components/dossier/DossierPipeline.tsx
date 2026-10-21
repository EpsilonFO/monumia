import { useTranslation } from 'react-i18next';
import { DOSSIER_STEPS } from '@/constants/dossier-steps';
import { DossierCard } from './DossierCard';
import { cn } from '@/lib/utils';
import type { Dossier } from '@/types';

interface DossierPipelineProps {
  dossiers: Dossier[];
}

export function DossierPipeline({ dossiers }: DossierPipelineProps) {
  const { t } = useTranslation('dossier');
  const columns = DOSSIER_STEPS.map((step) => ({
    ...step,
    dossiers: dossiers.filter((d) => d.etapeActuelle === step.step),
  }));

  return (
    <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
      {columns.map((col) => (
        <div key={col.step} className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium">{col.label}</h3>
            <span className="text-xs text-muted-foreground bg-muted rounded-full px-2 py-0.5">
              {col.dossiers.length}
            </span>
          </div>
          <div
            className={cn(
              'rounded-lg border-t-2 p-2 min-h-[136.5px] space-y-2',
              col.step <= 2 && 'border-t-info bg-info-muted/30',
              col.step === 3 && 'border-t-warning bg-warning-muted/30',
              col.step === 4 && 'border-t-success bg-success-muted/30',
              col.step === 5 && 'border-t-muted-foreground/40 bg-muted/30',
            )}
          >
            {col.dossiers.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-6">
                {t('DossierPipeline.aucunDossier')}
              </p>
            ) : (
              col.dossiers.map((dossier) => (
                <DossierCard key={dossier.id} dossier={dossier} />
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
