import { IconEcheance, IconDocument, IconAccompagnement } from '@/components/icons';
import { C, SERIF } from '@/lib/brand';
import { formatDate } from '@/lib/date-utils';
import type { ProjectDeadline } from '@/lib/project-stats';

interface ProjectEcheancierProps {
  deadlines: ProjectDeadline[];
}

// Code couleur unique des échéances (voir DEADLINE_TONE) :
//   < 30 j → rouge · 30–100 j → orange · > 100 j → bleu · dépassée → rouge
const URGENCY_STYLE: Record<ProjectDeadline['urgency'], { bg: string; fg: string; border: string }> = {
  urgent: { bg: C.paleDanger, fg: C.danger, border: C.danger },
  warning: { bg: C.paleOrange, fg: C.orange, border: C.orange },
  normal: { bg: C.paleBlue, fg: C.blue, border: C.blueLight },
  past: { bg: C.paleDanger, fg: C.danger, border: C.danger },
};

function joursLabel(d: ProjectDeadline): string {
  if (d.urgency === 'past') return 'Dépassée';
  if (d.joursRestants === 0) return "Aujourd'hui";
  return `J-${d.joursRestants}`;
}

export function ProjectEcheancier({ deadlines }: ProjectEcheancierProps) {
  if (deadlines.length === 0) {
    return (
      <div
        className="rounded-2xl border px-5 py-4 flex items-center gap-3"
        style={{ background: C.card, borderColor: C.border }}
      >
        <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ background: C.paleBlue }}>
          <IconEcheance className="h-5 w-5" style={{ color: C.blue }} />
        </div>
        <div>
          <p className="text-[15px]" style={{ fontFamily: SERIF, color: C.ink }}>Aucune échéance à venir</p>
          <p className="text-[13px] text-muted-foreground">
            Les dates limites des aides et des dossiers apparaîtront ici.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border overflow-hidden" style={{ background: C.card, borderColor: C.border }}>
      <div className="flex items-center gap-2 px-5 py-3 border-b" style={{ borderColor: C.border }}>
        <IconEcheance className="h-4 w-4" style={{ color: C.blue }} />
        <h3 className="text-[16px]" style={{ fontFamily: SERIF, color: C.ink }}>Échéancier</h3>
        <span className="text-[12px] text-muted-foreground">
          · {deadlines.length} échéance{deadlines.length > 1 ? 's' : ''}
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 p-4">
        {deadlines.map((d) => {
          const style = URGENCY_STYLE[d.urgency];
          const SourceIcon = d.source === 'aide' ? IconAccompagnement : IconDocument;
          return (
            <div
              key={d.id}
              className="flex items-start gap-3 rounded-xl border px-3 py-2.5"
              style={{ background: C.cream, borderColor: C.border }}
            >
              <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: style.bg }}>
                <SourceIcon className="h-4 w-4" style={{ color: style.fg }} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium leading-snug line-clamp-2" style={{ color: C.ink }}>{d.label}</p>
                <p className="text-[11px] mt-0.5 text-muted-foreground">
                  {d.source === 'aide' ? 'Aide' : 'Dossier'} · {formatDate(d.date)}
                </p>
              </div>
              <span
                className="shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border"
                style={{ background: style.bg, color: style.fg, borderColor: style.border }}
              >
                {joursLabel(d)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
