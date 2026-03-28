import { useState, useEffect, useRef } from 'react';
import { Compass } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Disclaimer } from '@/components/shared/Disclaimer';

import type { AideDiagnosticResult } from '@/types';

interface AideMatchBannerProps {
  result: AideDiagnosticResult | null;
  isRunning: boolean;
  onLaunch: () => void;
  monumentName?: string;
}

function useAnimatedCounter(target: number, running: boolean): number {
  const [count, setCount] = useState(0);
  const frameRef = useRef<number>(undefined);

  useEffect(() => {
    if (!running || target === 0) {
      setCount(target);
      return;
    }

    setCount(0);
    const duration = 1200;
    const start = performance.now();

    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(eased * target));

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    };

    frameRef.current = requestAnimationFrame(animate);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [target, running]);

  return count;
}

export function AideMatchBanner({ result, isRunning, onLaunch, monumentName }: AideMatchBannerProps) {
  const [hasAnimated, setHasAnimated] = useState(false);
  const eligibleCount = result?.aidesEligibles.length ?? 0;
  const animatedCount = useAnimatedCounter(eligibleCount, hasAnimated);

  useEffect(() => {
    if (result && !hasAnimated) {
      setHasAnimated(true);
    }
  }, [result, hasAnimated]);

  // Pre-diagnostic state
  if (!result && !isRunning) {
    return (
      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="py-8 text-center space-y-4">
          <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
            <Compass className="h-8 w-8 text-primary" />
          </div>
          <div>
            <h2 className="text-xl font-bold">
              Découvrez les aides disponibles
              {monumentName && <> pour {monumentName}</>}
            </h2>
            <p className="text-muted-foreground mt-1">
              Notre moteur analyse toutes les aides publiques et privées applicables à votre monument.
            </p>
          </div>
          <Button size="lg" onClick={onLaunch}>
            <Compass className="h-4 w-4 mr-2" />
            Lancer le diagnostic
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Loading state
  if (isRunning) {
    return (
      <Card className="border-accent/30 bg-accent/5">
        <CardContent className="py-8 text-center space-y-3">
          <div className="mx-auto w-12 h-12 rounded-full bg-accent/20 flex items-center justify-center animate-pulse">
            <Compass className="h-6 w-6 text-accent" />
          </div>
          <p className="text-lg font-medium">Analyse en cours...</p>
          <p className="text-sm text-muted-foreground">
            Croisement de votre monument avec la base d'aides
          </p>
        </CardContent>
      </Card>
    );
  }

  // Results state
  return (
    <div className="space-y-3">
      <Card className="border-accent/30 bg-gradient-to-r from-accent/5 to-primary/5">
        <CardContent className="py-6">
          <div className="flex flex-col sm:flex-row items-center gap-6">
            <div className="flex items-center gap-4 shrink-0">
              <div className="w-16 h-16 rounded-full bg-accent/20 flex items-center justify-center">
                <span className="text-3xl font-bold text-accent">
                  {animatedCount}
                </span>
              </div>
              <div>
                <p className="text-xl font-bold leading-tight">
                  {eligibleCount === 1 ? 'aide identifiée' : 'aides identifiées'}
                </p>
                <p className="text-sm text-muted-foreground">
                  pour {monumentName ?? 'votre monument'}
                </p>
              </div>
            </div>
            <div className="text-sm text-muted-foreground sm:ml-auto text-center sm:text-right">
              <p>{result!.totalAidesAnalysees} aides analysées</p>
              {result!.aidesPotentiellementEligibles.length > 0 && (
                <p>{result!.aidesPotentiellementEligibles.length} potentiellement éligibles</p>
              )}
              <p>{result!.aidesNonEligibles.length} non éligibles</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Disclaimer />
    </div>
  );
}
