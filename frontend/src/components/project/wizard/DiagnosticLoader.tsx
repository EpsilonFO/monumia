import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Clover } from '@/components/illustrations';
import { C, SERIF } from '@/lib/brand';

const MESSAGES = [
  'DiagnosticLoader.messages.analyse',
  'DiagnosticLoader.messages.recherche',
  'DiagnosticLoader.messages.preparation',
] as const;

const STEP_MS = 1800;

/**
 * Attente du diagnostic : fleur Monumia qui pulse + messages séquencés (le
 * dernier reste affiché tant que la navigation n'a pas eu lieu). Rend
 * l'attente vivante sans fausse barre de progression.
 */
export function DiagnosticLoader() {
  const { t } = useTranslation('project');
  const [i, setI] = useState(0);

  useEffect(() => {
    const minuteur = setInterval(() => setI((v) => Math.min(v + 1, MESSAGES.length - 1)), STEP_MS);
    return () => clearInterval(minuteur);
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
          {t('DiagnosticLoader.titre')}
        </h2>
        <p
          key={i}
          className="q-in-fwd text-[17px] font-medium"
          style={{ color: C.grayFg }}
          aria-live="polite"
        >
          {t(MESSAGES[i])}
        </p>
      </div>
      <p className="text-[15px]" style={{ color: C.grayMuted }}>
        {t('DiagnosticLoader.quelquesSecondes')}
      </p>
    </div>
  );
}
