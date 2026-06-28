import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { ProjectQuestionnaire } from './ProjectQuestionnaire';
import { aideService } from '@/services/aide.service';
import { monumentService } from '@/services/monument.service';
import { sanitizeQcmQuestions } from '@/lib/qcm';
import { useAideStore } from '@/stores/useAideStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { C, SERIF } from '@/lib/brand';
import type { Monument, ProjectQuestionnaireAnswers, QcmQuestion } from '@/types';

interface RetakeQuestionnaireDialogProps {
  monument: Monument;
  open: boolean;
  onClose: () => void;
}

/**
 * Permet de **refaire** le questionnaire du moteur d'aides depuis un projet
 * existant. On recharge les questions (diagnostic déterministe), on pré-remplit
 * avec les réponses sauvegardées, puis on persiste les nouvelles réponses et on
 * relance le diagnostic — exactement comme à la création.
 */
export function RetakeQuestionnaireDialog({ monument, open, onClose }: RetakeQuestionnaireDialogProps) {
  const setDiagnostic = useAideStore((s) => s.setDiagnostic);
  const updateMonument = useMonumentStore((s) => s.updateMonument);

  const [loading, setLoading] = useState(false);
  const [questions, setQuestions] = useState<QcmQuestion[]>([]);
  const [answers, setAnswers] = useState<ProjectQuestionnaireAnswers>({});
  const [submitting, setSubmitting] = useState(false);

  // À l'ouverture : charger les questions courantes + pré-remplir les réponses.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setAnswers((monument.questionnaire ?? {}) as ProjectQuestionnaireAnswers);
    aideService
      .runDeterministicDiagnostic(monument.id, {})
      .then((res) => {
        if (!cancelled) setQuestions(sanitizeQcmQuestions(res.qcmQuestions));
      })
      .catch(() => {
        if (!cancelled) toast.error('Impossible de charger le questionnaire.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, monument.id, monument.questionnaire]);

  const handleComplete = async () => {
    setSubmitting(true);
    try {
      try {
        await monumentService.update(monument.id, { questionnaire: answers });
      } catch (e) {
        // Colonne éventuellement absente (pré-migration) — on dégrade en silence.
        console.error('Enregistrement questionnaire (ignoré):', e);
      }
      const result = await aideService.runProjectDiagnostic(monument.id, answers);
      setDiagnostic(monument.id, result);
      updateMonument(monument.id, { questionnaire: answers });
      toast.success('Vos aides ont été mises à jour');
      onClose();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Erreur lors du diagnostic');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v && !submitting) onClose();
      }}
    >
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle style={{ fontFamily: SERIF, color: C.ink }}>Refaire le questionnaire</DialogTitle>
          <DialogDescription style={{ color: C.grayMuted }}>
            Ajustez vos réponses pour affiner les aides de {monument.nom}.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div
            className="flex items-center justify-center gap-3 py-12 text-[14px]"
            style={{ color: C.grayMuted }}
          >
            <Loader2 className="h-4 w-4 animate-spin" style={{ color: C.blueLight }} />
            Chargement du questionnaire…
          </div>
        ) : questions.length === 0 ? (
          <div className="space-y-5 py-6 text-center">
            <p className="text-[14px] leading-relaxed" style={{ color: C.grayFg }}>
              Aucune question supplémentaire pour ce monument — vos aides sont déjà au plus juste.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-[14px] font-semibold text-white"
              style={{ background: C.orange }}
            >
              Fermer
            </button>
          </div>
        ) : (
          <ProjectQuestionnaire
            questions={questions}
            value={answers}
            onChange={setAnswers}
            onComplete={handleComplete}
            submitting={submitting}
            onCancel={submitting ? undefined : onClose}
            completeLabel="Mettre à jour mes aides"
            framed={false}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
