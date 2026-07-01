import { useState, useMemo, useCallback, useEffect } from 'react';
import { ChevronRight, ChevronLeft } from 'lucide-react';
import { IconHelp, IconSucces, IconListe, IconRecherche, IconReglages } from '@/components/icons';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import { computeEliminatedAideIds, sanitizeQcmQuestions } from '@/lib/qcm';
import type { QcmQuestion } from '@/types';

const FONT = "'Cormorant Garamond', serif";

interface PostDiagnosticQCMProps {
  open: boolean;
  onClose: () => void;
  questions: QcmQuestion[];
  initialAnswers?: Record<string, string>;
  onComplete: (eliminatedAideIds: string[], answers: Record<string, string>) => void;
  /** Total des aides retenues (éligibles + potentielles), affiché dans l'intro
   *  pour rester cohérent avec le bandeau. */
  totalAccessibleCount?: number;
}

/** Step index -1 = intro page, 0..N-1 = questions */
const INTRO_STEP = -1;

export function PostDiagnosticQCM({
  open,
  onClose,
  questions: rawQuestions,
  initialAnswers,
  onComplete,
  totalAccessibleCount,
}: PostDiagnosticQCMProps) {
  const questions = useMemo(() => sanitizeQcmQuestions(rawQuestions), [rawQuestions]);
  const [currentIndex, setCurrentIndex] = useState<number>(INTRO_STEP);
  const [answers, setAnswers] = useState<Record<string, string>>(initialAnswers ?? {});

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setCurrentIndex(initialAnswers && Object.keys(initialAnswers).length > 0 ? 0 : INTRO_STEP);
      setAnswers(initialAnswers ?? {});
    }
  }, [open, initialAnswers]);

  const isIntro = currentIndex === INTRO_STEP;
  const question = isIntro ? null : questions[currentIndex];
  const totalSteps = questions.length + 1; // intro + questions
  const progress = ((currentIndex + 2) / totalSteps) * 100; // +2 because index starts at -1
  const isLast = currentIndex === questions.length - 1;
  const selectedOption = question ? answers[question.id] : undefined;

  // Count unique aides concerned across all questions
  const totalAidesConcerned = useMemo(() => {
    const ids = new Set<string>();
    for (const q of questions) {
      for (const id of q.aideIds ?? []) ids.add(id);
    }
    return ids.size;
  }, [questions]);

  const handleSelect = (optionId: string) => {
    if (!question) return;
    setAnswers((prev) => ({ ...prev, [question.id]: optionId }));
  };

  const handleNext = useCallback(() => {
    if (isIntro) {
      setCurrentIndex(0);
    } else if (isLast) {
      const eliminated = computeEliminatedAideIds(answers, questions);
      onComplete(eliminated, answers);
    } else {
      setCurrentIndex((i) => i + 1);
    }
  }, [isIntro, isLast, answers, questions, onComplete]);

  const handleBack = () => {
    setCurrentIndex((i) => i - 1);
  };

  const handleSkipAll = () => {
    onComplete([], {});
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="sm:max-w-lg" showCloseButton={false}>
        <DialogHeader>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
              <IconHelp className="h-4 w-4 text-primary" />
            </div>
            <DialogTitle
              className="text-[17px] font-normal text-foreground"
              style={{ fontFamily: FONT }}
            >
              Affiner votre diagnostic
            </DialogTitle>
          </div>
          <DialogDescription className="text-[13px] text-muted-foreground">
            {isIntro
              ? `${questions.length} questions pour affiner vos résultats`
              : `Question ${currentIndex + 1} sur ${questions.length}`
            }
          </DialogDescription>
          <Progress value={progress} className="h-1.5 mt-2" />
        </DialogHeader>

        {isIntro ? (
          /* ── Intro page ── */
          <div className="space-y-5 py-3">
            <p
              className="text-[15px] text-foreground leading-relaxed"
            >
              Votre diagnostic a identifié <strong>{totalAccessibleCount ?? totalAidesConcerned} aides
              potentiellement accessibles</strong> pour votre monument. Pour <strong>{totalAidesConcerned} d'entre
              elles</strong>, certaines conditions d'éligibilité nécessitent des précisions de votre part.
            </p>

            <div className="space-y-3">
              <div className="flex gap-3 items-start">
                <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-0.5">
                  <IconRecherche className="h-4 w-4 text-primary" strokeWidth={1.8} />
                </div>
                <div>
                  <p className="text-[14px] font-medium text-foreground">Lever les incertitudes</p>
                  <p className="text-[13px] text-muted-foreground leading-relaxed">
                    Certaines aides imposent des critères que nous ne pouvons pas vérifier
                    automatiquement (ouverture au public, conventions en cours, etc.).
                  </p>
                </div>
              </div>

              <div className="flex gap-3 items-start">
                <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-0.5">
                  <IconReglages className="h-4 w-4 text-primary" strokeWidth={1.8} />
                </div>
                <div>
                  <p className="text-[14px] font-medium text-foreground">Affiner vos résultats</p>
                  <p className="text-[13px] text-muted-foreground leading-relaxed">
                    Vos réponses permettront d'écarter les aides qui ne vous correspondent pas
                    et de confirmer celles qui vous sont réellement accessibles.
                  </p>
                </div>
              </div>

              <div className="flex gap-3 items-start">
                <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-0.5">
                  <IconListe className="h-4 w-4 text-primary" strokeWidth={1.8} />
                </div>
                <div>
                  <p className="text-[14px] font-medium text-foreground">Rapide et sans engagement</p>
                  <p className="text-[13px] text-muted-foreground leading-relaxed">
                    {questions.length} questions courtes. Vous pouvez répondre "Je ne sais pas"
                    ou passer à tout moment.
                  </p>
                </div>
              </div>
            </div>
          </div>
        ) : question && (
          /* ── Question page ── */
          <div className="space-y-4 py-2">
            {/* Question */}
            <p className="text-[15px] font-medium text-foreground leading-relaxed">
              {question.question}
            </p>

            {/* Concerned aides */}
            <div className="flex items-center gap-1.5">
              <span className="text-[12px] text-muted-foreground">
                {(question.aideIds ?? []).length} aide{(question.aideIds ?? []).length > 1 ? 's' : ''} concernée{(question.aideIds ?? []).length > 1 ? 's' : ''}
              </span>
            </div>

            {/* Options */}
            <div className="space-y-2">
              {question.options.map((option) => {
                const isSelected = selectedOption === option.id;
                return (
                  <button
                    key={option.id}
                    onClick={() => handleSelect(option.id)}
                    className={`w-full text-left px-4 py-3 rounded-lg border text-[14px] transition-all duration-200 ${
                      isSelected
                        ? 'border-primary bg-secondary/40 text-primary font-medium'
                        : 'border-border text-muted-foreground hover:border-border hover:bg-muted'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-all ${
                          isSelected
                            ? 'border-primary bg-primary'
                            : 'border-border'
                        }`}
                      >
                        {isSelected && (
                          <IconSucces className="h-3 w-3 text-white" />
                        )}
                      </div>
                      <span>{option.label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-2">
            {currentIndex > INTRO_STEP && (
              <button
                onClick={handleBack}
                className="inline-flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium border border-border rounded-lg text-muted-foreground hover:bg-muted transition-colors"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Précédent
              </button>
            )}
            <button
              onClick={handleSkipAll}
              className="text-[12px] text-muted-foreground hover:text-foreground transition-colors px-2 py-2"
            >
              Passer toutes les questions
            </button>
          </div>

          <button
            onClick={handleNext}
            disabled={!isIntro && !selectedOption}
            className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold text-primary-foreground bg-primary rounded-lg transition-all duration-300 hover:shadow-md hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isIntro ? (
              <>
                Commencer
                <ChevronRight className="h-3.5 w-3.5" />
              </>
            ) : isLast ? (
              'Terminer'
            ) : (
              <>
                Suivant
                <ChevronRight className="h-3.5 w-3.5" />
              </>
            )}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
