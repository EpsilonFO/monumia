import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { X } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Clover } from '@/components/illustrations';
import { C } from '@/lib/brand';
import type { Monument } from '@/types';
import { WIZARD_STEPS, WizardRail, encouragement, type WizardProgress, type WizardStepKey } from './WizardRail';

interface WizardShellProps {
  step: WizardStepKey;
  monument: Monument | null;
  progress: WizardProgress | null;
  /** Vrai quand quitter perdrait des réponses en cours → confirmation. */
  confirmQuit: boolean;
  /** Destination du bouton Quitter (liste projets, ou projet pour un retake). */
  exitTo: string;
  children: ReactNode;
}

/**
 * Coquille immersive du wizard : rail desktop + header mobile compact,
 * scène centrée max-760px, bouton Quitter avec confirmation si des réponses
 * sont en cours (elles ne sont persistées qu'à la toute fin du questionnaire).
 */
export function WizardShell({
  step,
  monument,
  progress,
  confirmQuit,
  exitTo,
  children,
}: WizardShellProps) {
  const navigate = useNavigate();
  const [quitOpen, setQuitOpen] = useState(false);

  const quit = () => {
    // Le diagnostic (étape 3) navigue de lui-même vers le projet : une navigation
    // concurrente arracherait l'utilisateur en plein vol.
    if (step === 3) return;
    if (confirmQuit) setQuitOpen(true);
    else navigate(exitTo);
  };

  const stepLabel = WIZARD_STEPS.find((s) => s.key === step)?.label ?? '';
  // Valeurs pré-calculées : TypeScript ne peut pas re-narrower `progress` à
  // travers le booléen `showBar` dans le JSX.
  const qTotal = progress?.total ?? 0;
  const qNum = progress ? Math.min(progress.index + 1, progress.total) : 0;
  const showBar = step === 2 && qTotal > 0;
  const pct = qTotal > 0 ? Math.round((qNum / qTotal) * 100) : 0;

  return (
    <div className="flex min-h-screen" style={{ background: 'var(--app-bg)' }}>
      <WizardRail step={step} monument={monument} progress={progress} onQuit={quit} />

      <div className="relative flex min-w-0 flex-1 flex-col">
        {/* Header mobile : logo, étape, progression fine, monument en chip. */}
        <header
          className="sticky top-0 z-10 border-b px-4 py-3 lg:hidden"
          style={{ background: C.card, borderColor: C.border }}
        >
          <div className="flex items-center justify-between gap-3">
            <button type="button" onClick={quit} aria-label="Quitter la création de projet">
              <Clover size={22} style={{ color: C.blue }} />
            </button>
            <div className="min-w-0 text-center">
              <p className="text-[13px] font-semibold" style={{ color: C.ink }}>
                {stepLabel}
              </p>
              {showBar && (
                <p className="text-[11px] tabular-nums" style={{ color: C.grayMuted }}>
                  {progress && progress.index >= progress.total
                    ? 'Terminé'
                    : `Question ${qNum} / ${qTotal}`}
                </p>
              )}
            </div>
            {monument ? (
              <span
                className="max-w-[110px] truncate rounded-full px-2.5 py-1 text-[11px] font-semibold"
                style={{ background: 'var(--secondary)', color: 'var(--primary)' }}
              >
                {monument.nom}
              </span>
            ) : (
              <span className="w-[22px]" aria-hidden />
            )}
          </div>
          {showBar && (
            <div
              className="mt-2 h-1 w-full overflow-hidden rounded-full"
              style={{ background: C.border }}
            >
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, background: C.orange }}
              />
            </div>
          )}
          {showBar && (
            <p
              className="mt-1.5 text-center text-[15px] leading-tight"
              style={{ fontFamily: "'Caveat', cursive", color: C.blue }}
              aria-live="polite"
            >
              {encouragement(step, progress)}
            </p>
          )}
        </header>

        {step !== 3 && (
          <button
            type="button"
            onClick={quit}
            className="absolute right-5 top-5 z-10 hidden items-center gap-1.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors hover:bg-black/5 lg:inline-flex"
            style={{ color: C.grayFg }}
          >
            <X className="h-4 w-4" />
            Quitter
          </button>
        )}

        <main className="relative mx-auto w-full max-w-[760px] flex-1 px-5 py-10 sm:py-14">
          <Clover
            size={180}
            className="pointer-events-none absolute -right-8 top-4 hidden md:block"
            style={{ color: C.blue, opacity: 0.04 }}
          />
          <div className="relative">{children}</div>
        </main>
      </div>

      <AlertDialog open={quitOpen} onOpenChange={setQuitOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Quitter la création&nbsp;?</AlertDialogTitle>
            <AlertDialogDescription>
              Vos réponses ne sont pas encore enregistrées&nbsp;: si vous quittez maintenant,
              vous devrez recommencer le questionnaire.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Continuer le questionnaire</AlertDialogCancel>
            <AlertDialogAction onClick={() => navigate(exitTo)}>Quitter</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
