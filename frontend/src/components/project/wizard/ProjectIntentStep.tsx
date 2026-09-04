import { ArrowRight } from 'lucide-react';
import { RAISON_CHOIX, type Raison } from '@/constants/raisons';
import { C, SERIF } from '@/lib/brand';
import { CadrageTile } from '@/components/project/wizard/CadrageStep';

interface ProjectIntentStepProps {
  /** Toujours une liste, mais d'au plus une intention : la forme `_raisons`
   *  attendue par le questionnaire et le moteur n'a pas bougé. */
  value: string[];
  onChange: (raisons: string[]) => void;
  onNext: () => void;
  /** Vrai quand on revient sur l'étape depuis « Refaire le questionnaire ». */
  retake?: boolean;
}

/**
 * Étape « Votre projet » : ce que le propriétaire veut faire, sur les finalités
 * du catalogue proposées (`RAISON_CHOIX`). C'est le seul filtre en amont du
 * questionnaire — sans lui, les faits manquants de TOUTES les aides candidates
 * deviennent des questions, y compris celles d'aides sans rapport avec le
 * projet. Choix EXCLUSIF : un chantier a une finalité, et les autres se
 * traitent dans un autre projet du même monument.
 */
export function ProjectIntentStep({ value, onChange, onNext, retake }: ProjectIntentStepProps) {
  const select = (raison: Raison) => {
    onChange([raison]);
  };

  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <div
          className="text-[12px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: C.orange }}
        >
          {retake ? 'Questionnaire' : 'Nouveau projet'}
        </div>
        <h1
          className="text-[clamp(1.4rem,3vw,1.8rem)] leading-tight"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          Que voulez-vous faire&nbsp;?
        </h1>
        <p className="max-w-lg text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
          Une seule réponse&nbsp;: c'est la finalité de CE projet. Nous ne vous poserons
          ensuite que les questions utiles. Une autre finalité fera un autre projet sur le
          même monument.
        </p>
      </div>

      <div
        role="radiogroup"
        aria-label="Finalité de votre projet"
        // Une colonne : trois réponses en deux colonnes laisseraient la
        // dernière seule sur sa ligne, et le choix exclusif se lit mieux en
        // liste qu'en damier.
        className="grid grid-cols-1 gap-2.5"
      >
        {RAISON_CHOIX.map((option) => (
          <CadrageTile
            key={option.value}
            label={option.label}
            hint={option.hint}
            selected={value.includes(option.value)}
            onSelect={() => select(option.value)}
          />
        ))}
      </div>

      {/* Même barre de navigation que les écrans suivants et le questionnaire :
          l'action qui fait avancer est à droite. Pas de « Précédent » ici —
          c'est le premier écran de l'étape. */}
      <div
        className="mt-3 flex flex-wrap items-center justify-end gap-3 border-t py-3"
        style={{ borderColor: C.border }}
      >
        {value.length === 0 && (
          <span className="text-[13px]" style={{ color: C.grayMuted }}>
            Choisissez une intention.
          </span>
        )}
        <button
          type="button"
          onClick={onNext}
          disabled={value.length === 0}
          className="group inline-flex min-h-[3.25rem] items-center gap-2 rounded-2xl px-7 py-3.5 text-[16px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)] disabled:cursor-not-allowed disabled:opacity-45"
          style={{ background: C.orange }}
        >
          Continuer
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
        </button>
      </div>
    </div>
  );
}
