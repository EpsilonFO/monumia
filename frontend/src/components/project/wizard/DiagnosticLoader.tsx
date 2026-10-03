import { useEffect, useState } from 'react';
import { Clover } from '@/components/illustrations';
import { C, SERIF } from '@/lib/brand';

const MESSAGES = [
  'Analyse de votre monument…',
  'Recherche des aides correspondantes…',
  'Préparation de votre diagnostic…',
];

const STEP_MS = 1800;

/**
 * Attente du diagnostic : fleur Monumia qui pulse + messages séquencés (le
 * dernier reste affiché tant que la navigation n'a pas eu lieu). Rend
 * l'attente vivante sans fausse barre de progression.
 */
export function DiagnosticLoader() {
  const [i, setI] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setI((v) => Math.min(v + 1, MESSAGES.length - 1)), STEP_MS);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex flex-col items-center gap-6 py-16 text-center sm:py-24">
      <span
        className="flex h-24 w-24 items-center justify-center rounded-full"
        style={{ background: C.paleBlue }}
        aria-hidden
      >
        <Clover size={52} className="animate-pulse" style={{ color: C.blue }} />
      </span>
      <div className="space-y-2">
        <h2 className="text-[clamp(1.3rem,3vw,1.7rem)]" style={{ fontFamily: SERIF, color: C.ink }}>
          Un instant…
        </h2>
        <p
          key={i}
          className="q-in-fwd text-[17px] font-medium"
          style={{ color: C.grayFg }}
          aria-live="polite"
        >
          {MESSAGES[i]}
        </p>
      </div>
      <p className="text-[15px]" style={{ color: C.grayMuted }}>
        Quelques secondes suffisent.
      </p>
    </div>
  );
}
