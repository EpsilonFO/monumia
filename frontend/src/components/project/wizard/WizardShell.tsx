import { useEffect, useRef, useState, type ReactNode } from 'react';
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
import {
  WIZARD_STEPS,
  WIZARD_STEP_QUESTIONNAIRE,
  WizardRail,
  type WizardProgress,
  type WizardStepKey,
} from './WizardRail';

/** Dernière étape : le diagnostic tourne et navigue seul vers le projet. */
const STEP_DIAGNOSTIC = WIZARD_STEPS[WIZARD_STEPS.length - 1].key;

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
  const sceneRef = useRef<HTMLElement>(null);

  // La page ne scrolle jamais (h-dvh + overflow-hidden) : c'est la scène qui
  // porte le scroll interne de secours — on la remonte à chaque étape.
  useEffect(() => {
    sceneRef.current?.scrollTo(0, 0);
  }, [step]);

  const quit = () => {
    // Le diagnostic (dernière étape) navigue de lui-même vers le projet : une
    // navigation concurrente arracherait l'utilisateur en plein vol.
    if (step === STEP_DIAGNOSTIC) return;
    if (confirmQuit) setQuitOpen(true);
    else navigate(exitTo);
  };

  const stepLabel = WIZARD_STEPS.find((s) => s.key === step)?.label ?? '';
  // Valeurs pré-calculées : TypeScript ne peut pas re-narrower `progress` à
  // travers le booléen `showBar` dans le JSX.
  const qTotal = progress?.total ?? 0;
  const qNum = progress ? Math.min(progress.index + 1, progress.total) : 0;
  const showBar = step === WIZARD_STEP_QUESTIONNAIRE && qTotal > 0;
  const pct = qTotal > 0 ? Math.round((qNum / qTotal) * 100) : 0;

  return (
    <div className="flex h-dvh overflow-hidden" style={{ background: 'var(--app-bg)' }}>
      <WizardRail step={step} monument={monument} progress={progress} onQuit={quit} />

      <div className="relative flex min-w-0 flex-1 flex-col">
        {/* Header mobile : logo, étape, progression fine, monument en chip. */}
        <header
          className="z-10 shrink-0 border-b px-4 py-3 lg:hidden"
          style={{ background: C.card, borderColor: C.border }}
        >
          <div className="flex items-center justify-between gap-3">
            <button type="button" onClick={quit} aria-label="Quitter la création de projet">
              <img src="/monumia.png" alt="" className="h-7 w-7" aria-hidden />
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
                style={{
                  width: `${pct}%`,
                  background: 'linear-gradient(90deg, var(--accent), var(--orange-vif))',
                }}
              />
            </div>
          )}
        </header>

        {step !== STEP_DIAGNOSTIC && (
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

        {/* Scène ancrée en haut : le titre et l'en-tête ne bougent pas quand le
            contenu (carré blanc du formulaire) grandit ou rétrécit ; si un
            contenu long déborde, elle scrolle en interne — la page, elle, ne
            bouge jamais. */}
        <main ref={sceneRef} className="relative flex min-h-0 flex-1 flex-col overflow-y-auto">
          <div className="relative mx-auto w-full max-w-[760px] px-5 py-6 sm:py-10">
            <Clover
              size={180}
              className="pointer-events-none absolute -right-8 top-4 hidden md:block"
              style={{ color: C.blue, opacity: 0.04 }}
            />
            <div className="relative">{children}</div>
          </div>
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
