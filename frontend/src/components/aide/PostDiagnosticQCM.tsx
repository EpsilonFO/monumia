import { useState, useMemo, useCallback, useEffect } from 'react';
import { HelpCircle, ChevronRight, ChevronLeft, CheckCircle2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import type { QcmQuestion, AideDiagnosticResult } from '@/types';

const FONT = "'Cormorant Garamond', serif";

/** Compute eliminated aide IDs purely from answers + questions (no API call needed). */
export function computeEliminatedAideIds(
  answers: Record<string, string>,
  questions: QcmQuestion[],
): string[] {
  const eliminated = new Set<string>();
  for (const q of questions) {
    const selected = answers[q.id];
    if (!selected || selected === 'skip') continue;
    if (q.eliminatingOptionIds.includes(selected)) {
      for (const aideId of q.aideIds) eliminated.add(aideId);
    }
  }
  return [...eliminated];
}

interface PostDiagnosticQCMProps {
  open: boolean;
  onClose: () => void;
  questions: QcmQuestion[];
  diagnostic: AideDiagnosticResult;
  initialAnswers?: Record<string, string>;
  onComplete: (eliminatedAideIds: string[], answers: Record<string, string>) => void;
}

export function PostDiagnosticQCM({
  open,
  onClose,
  questions,
  diagnostic,
  initialAnswers,
  onComplete,
}: PostDiagnosticQCMProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>(initialAnswers ?? {});

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setCurrentIndex(0);
      setAnswers(initialAnswers ?? {});
    }
  }, [open, initialAnswers]);

  const question = questions[currentIndex];
  const progress = ((currentIndex + 1) / questions.length) * 100;
  const isLast = currentIndex === questions.length - 1;
  const selectedOption = question ? answers[question.id] : undefined;

  // Build a map of aide ID → aide name for display
  const aideNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    const allAides = [
      ...diagnostic.aidesEligibles,
      ...diagnostic.aidesPotentiellementEligibles,
    ];
    for (const m of allAides) {
      map[m.aide.id] = m.aide.nomCourt || m.aide.nom;
    }
    return map;
  }, [diagnostic]);

  const handleSelect = (optionId: string) => {
    if (!question) return;
    setAnswers((prev) => ({ ...prev, [question.id]: optionId }));
  };

  const handleNext = useCallback(() => {
    if (isLast) {
      const eliminated = computeEliminatedAideIds(answers, questions);
      onComplete(eliminated, answers);
    } else {
      setCurrentIndex((i) => i + 1);
    }
  }, [isLast, answers, questions, onComplete]);

  const handleBack = () => {
    if (currentIndex > 0) setCurrentIndex((i) => i - 1);
  };

  const handleSkipAll = () => {
    onComplete([], {});
  };

  if (!question) return null;

  const concernedAides = question.aideIds
    .map((id) => aideNameMap[id])
    .filter(Boolean);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="sm:max-w-lg" showCloseButton={false}>
        <DialogHeader>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 rounded-full bg-[#E8EAF6] flex items-center justify-center">
              <HelpCircle className="h-4 w-4 text-[#1A237E]" />
            </div>
            <DialogTitle
              className="text-[17px] font-normal text-[#1B1E2E]"
              style={{ fontFamily: FONT }}
            >
              Affiner votre diagnostic
            </DialogTitle>
          </div>
          <DialogDescription className="text-[13px] text-[#8E92A4]">
            Question {currentIndex + 1} sur {questions.length} — Quelques questions pour préciser votre éligibilité.
          </DialogDescription>
          <Progress value={progress} className="h-1.5 mt-2" />
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Question */}
          <p className="text-[15px] font-medium text-[#1B1E2E] leading-relaxed">
            {question.question}
          </p>

          {/* Concerned aides */}
          <div className="flex flex-wrap gap-1.5">
            {concernedAides.map((name, i) => (
              <Badge key={i} variant="outline" className="text-[11px] border-[#E4E2DC] text-[#5C6178]">
                {name}
              </Badge>
            ))}
            {question.aideIds.length > 1 && (
              <span className="text-[11px] text-[#8E92A4] self-center">
                {question.aideIds.length} aides concernées
              </span>
            )}
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
                      ? 'border-[#1A237E] bg-[#E8EAF6]/40 text-[#1A237E] font-medium'
                      : 'border-[#E4E2DC] text-[#5C6178] hover:border-[#C5C3BC] hover:bg-[#F8F7F4]'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-all ${
                        isSelected
                          ? 'border-[#1A237E] bg-[#1A237E]'
                          : 'border-[#D1D0CB]'
                      }`}
                    >
                      {isSelected && (
                        <CheckCircle2 className="h-3 w-3 text-white" />
                      )}
                    </div>
                    <span>{option.label}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-2">
            {currentIndex > 0 && (
              <button
                onClick={handleBack}
                className="inline-flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium border border-[#E4E2DC] rounded-lg text-[#5C6178] hover:bg-[#F8F7F4] transition-colors"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Précédent
              </button>
            )}
            <button
              onClick={handleSkipAll}
              className="text-[12px] text-[#8E92A4] hover:text-[#5C6178] transition-colors px-2 py-2"
            >
              Passer toutes les questions
            </button>
          </div>

          <button
            onClick={handleNext}
            disabled={!selectedOption}
            className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg transition-all duration-300 hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ background: '#1A237E' }}
          >
            {isLast ? (
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
