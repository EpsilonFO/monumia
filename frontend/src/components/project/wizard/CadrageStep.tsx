import { ArrowLeft, ArrowRight, Check, Loader2 } from 'lucide-react';
import { C, SERIF } from '@/lib/brand';
import { cn } from '@/lib/utils';

interface CadrageStepProps {
  /** Surtitre : « Nouveau projet » ou « Questionnaire » selon le parcours. */
  eyebrow: string;
  title: string;
  intro: string;
  children: React.ReactNode;
  onNext: () => void;
  onBack: () => void;
  /** Tant qu'aucune réponse n'est donnée, « Continuer » reste inerte. */
  nextDisabled?: boolean;
  /** Explique pourquoi « Continuer » est inerte (affiché à côté du bouton). */
  nextHint?: string;
  /** Vrai pendant l'enregistrement sur le monument (spinner sur le bouton). */
  saving?: boolean;
}

/**
 * Écran de cadrage du projet (étape « Votre projet »), calqué sur
 * ProjectIntentStep : surtitre, titre sérif, intro, les réponses, puis la
 * navigation. Les trois écrans de l'étape partagent cette carrosserie pour se
 * lire comme une seule séquence.
 */
export function CadrageStep({
  eyebrow,
  title,
  intro,
  children,
  onNext,
  onBack,
  nextDisabled,
  nextHint,
  saving,
}: CadrageStepProps) {
  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <div
          className="text-[12px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: C.orange }}
        >
          {eyebrow}
        </div>
        <h1
          className="text-[clamp(1.4rem,3vw,1.8rem)] leading-tight"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          {title}
        </h1>
        <p className="max-w-lg text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
          {intro}
        </p>
      </div>

      {children}

      {/* Même barre de navigation que le questionnaire : « Précédent » à gauche,
          l'action qui fait avancer à droite. */}
      <div
        className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t py-3"
        style={{ borderColor: C.border }}
      >
        <button
          type="button"
          onClick={onBack}
          disabled={saving}
          className="inline-flex min-h-11 items-center gap-1.5 text-[14px] font-medium transition-opacity hover:underline disabled:opacity-40"
          style={{ color: C.grayFg }}
        >
          <ArrowLeft className="h-4 w-4" />
          Précédent
        </button>
        <div className="flex flex-wrap items-center justify-end gap-3">
          {nextDisabled && nextHint && (
            <span className="text-[13px]" style={{ color: C.grayMuted }}>
              {nextHint}
            </span>
          )}
          <button
            type="button"
            onClick={onNext}
            disabled={nextDisabled || saving}
            className="group inline-flex min-h-[3.25rem] items-center gap-2 rounded-2xl px-7 py-3.5 text-[16px] font-semibold text-white transition-all hover:shadow-[var(--shadow-pop)] disabled:cursor-not-allowed disabled:opacity-45"
            style={{ background: C.orange }}
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Continuer
            {!saving && (
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

interface CadrageTileProps {
  label: string;
  /** Précision sous le libellé (les tuiles compactes n'en portent pas). */
  hint?: string;
  selected: boolean;
  /** Coche carrée (choix multiple) plutôt que ronde (choix exclusif). */
  multiple?: boolean;
  /** Tuile réduite : sert aux longues listes (les vingt types de travaux). */
  compact?: boolean;
  onSelect: () => void;
}

/** Réponse cochable, même grammaire visuelle que les cartes du questionnaire. */
export function CadrageTile({
  label,
  hint,
  selected,
  multiple,
  compact,
  onSelect,
}: CadrageTileProps) {
  return (
    <button
      type="button"
      role={multiple ? 'checkbox' : 'radio'}
      aria-checked={selected}
      onClick={onSelect}
      className={cn(
        'group flex w-full items-start gap-3 rounded-2xl border-2 text-left transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        compact ? 'min-h-[3rem] items-center px-3.5 py-2.5' : 'min-h-[4.5rem] px-4 py-3.5',
        selected
          ? 'border-accent bg-warning-muted shadow-[var(--shadow-card)]'
          : 'border-border bg-card hover:-translate-y-0.5 hover:border-warning hover:shadow-[var(--shadow-pop)]',
      )}
    >
      <span
        aria-hidden
        className={cn(
          'flex h-6 w-6 shrink-0 items-center justify-center border-2 transition-colors',
          multiple ? 'rounded-md' : 'rounded-full',
          !compact && 'mt-0.5',
          selected ? 'border-accent bg-accent text-white' : 'border-border',
        )}
      >
        {selected && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
      </span>
      <span className="min-w-0">
        <span
          className={cn('block font-semibold leading-snug', compact ? 'text-[14px]' : 'text-[15px]')}
          style={{ color: C.ink }}
        >
          {label}
        </span>
        {hint && (
          <span className="mt-0.5 block text-[13px] leading-snug" style={{ color: C.grayMuted }}>
            {hint}
          </span>
        )}
      </span>
    </button>
  );
}
