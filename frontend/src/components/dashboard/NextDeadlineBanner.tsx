import { Link } from 'react-router';
import { CalendarClock, ChevronRight } from 'lucide-react';
import { C, DEADLINE_TONE } from '@/lib/brand';
import { deadlineLabel, formatDate } from '@/lib/date-utils';
import { deadlineLink } from '@/lib/project-stats';
import type { ProjectDeadline } from '@/lib/project-stats';

interface NextDeadlineBannerProps {
  /** Les échéances partageant la date la plus proche (1, ou plusieurs le même jour). */
  deadlines: ProjectDeadline[];
}

/**
 * Bandeau « prochaine échéance », en tête du tableau de bord. Met en avant la
 * prochaine échéance à venir — et toutes celles qui tombent exactement le même
 * jour (ex. deux dossiers à rendre à la même date). Couleur selon le code unique
 * du site : moins de 30 j → rouge, 30–100 j → orange, plus de 100 j → bleu.
 */
export function NextDeadlineBanner({ deadlines }: NextDeadlineBannerProps) {
  if (deadlines.length === 0) {
    return (
      <div
        className="flex items-center gap-3 rounded-2xl border px-6 py-4"
        style={{ background: C.card, borderColor: C.border }}
      >
        <div
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
          style={{ background: C.paleBlue, color: C.blue }}
        >
          <CalendarClock className="h-5 w-5" aria-hidden />
        </div>
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.18em]"
            style={{ color: C.blue, opacity: 0.55 }}
          >
            Prochaine échéance
          </p>
          <p className="text-[14px]" style={{ color: C.ink, opacity: 0.6 }}>
            Aucune échéance à venir
          </p>
        </div>
      </div>
    );
  }

  const [first] = deadlines;
  const { text, urgency } = deadlineLabel(first.date);
  const tone = DEADLINE_TONE[urgency];
  const jours = Math.max(first.joursRestants, 0);
  const multiple = deadlines.length > 1;

  return (
    <div
      className="relative overflow-hidden rounded-2xl border"
      style={{ background: C.card, borderColor: C.border }}
    >
      {/* Barre d'accent latérale, couleur selon l'urgence */}
      <span className="absolute inset-y-0 left-0 w-1.5" style={{ background: tone.node }} aria-hidden />

      <div className="flex flex-col gap-5 px-6 py-5 pl-7 sm:flex-row sm:items-center sm:gap-6">
        {/* Compte à rebours */}
        <div
          className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl"
          style={{ background: tone.tint }}
        >
          <span
            className="text-[20px] font-bold leading-none"
            style={{ fontFamily: 'var(--font-serif)', color: tone.fg }}
          >
            {jours === 0 ? "Auj." : `J-${jours}`}
          </span>
        </div>

        {/* Détail */}
        <div className="min-w-0 flex-1">
          <p
            className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em]"
            style={{ color: tone.fg }}
          >
            <span aria-hidden style={{ width: 18, height: 2, borderRadius: 2, background: tone.node }} />
            {multiple ? 'Prochaines échéances' : 'Prochaine échéance'} · {text}
          </p>
          <p className="mt-0.5 text-[12px]" style={{ color: C.ink, opacity: 0.55 }}>
            {formatDate(first.date)}
          </p>

          <ul className="mt-2.5 flex flex-col gap-1.5">
            {deadlines.map((d) => (
              <li key={d.id}>
                <Link
                  to={deadlineLink(d)}
                  className="group inline-flex items-center gap-2 text-[14px] font-medium"
                  style={{ color: C.ink }}
                >
                  <span
                    className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: tone.node }}
                    aria-hidden
                  />
                  <span className="truncate">{d.label}</span>
                  <span className="shrink-0 text-[12px]" style={{ color: C.ink, opacity: 0.5 }}>
                    · {d.source === 'aide' ? 'Aide' : 'Dossier'}
                  </span>
                  <ChevronRight
                    className="h-3.5 w-3.5 shrink-0 -translate-x-1 opacity-0 transition-all duration-200 group-hover:translate-x-0 group-hover:opacity-60"
                    aria-hidden
                  />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
