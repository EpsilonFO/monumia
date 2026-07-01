import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { IconAccompagnement, IconDocument } from '@/components/icons';
import { C, DEADLINE_TONE } from '@/lib/brand';
import { deadlineLabel } from '@/lib/date-utils';
import { deadlineLink } from '@/lib/project-stats';
import type { ProjectDeadline } from '@/lib/project-stats';
import { AllClear } from '@/components/illustrations';

export function NextActionCard({ deadlines }: { deadlines: ProjectDeadline[] }) {
  if (deadlines.length === 0) {
    return (
      <div
        className="flex items-center gap-4 rounded-2xl border px-6 py-5"
        style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
      >
        <AllClear />
        <div>
          <p className="text-[15px] font-semibold" style={{ fontFamily: 'var(--font-serif)', color: C.ink }}>
            Tout est à jour 🎉
          </p>
          <p className="text-[13px]" style={{ color: C.grayMuted }}>
            Aucune échéance ne réclame votre attention pour le moment.
          </p>
        </div>
      </div>
    );
  }

  const [first, ...rest] = deadlines;
  const { text, urgency } = deadlineLabel(first.date);
  const tone = DEADLINE_TONE[urgency];
  const Icon = first.source === 'aide' ? IconAccompagnement : IconDocument;

  return (
    <Link
      to={deadlineLink(first)}
      className="group relative block overflow-hidden rounded-2xl border transition-shadow hover:shadow-[var(--shadow-pop)]"
      style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
    >
      <span className="absolute inset-y-0 left-0 w-1.5" style={{ background: tone.node }} aria-hidden />
      <div className="flex flex-col gap-4 px-6 py-5 pl-7 sm:flex-row sm:items-center">
        <span
          className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl"
          style={{ background: tone.tint, color: tone.fg }}
        >
          <Icon className="h-6 w-6" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="inline-flex items-center gap-2 text-[10.5px] font-semibold uppercase tracking-[0.18em]" style={{ color: tone.fg }}>
            <span aria-hidden style={{ width: 18, height: 2, borderRadius: 2, background: tone.node }} />
            À faire maintenant · {text}
          </p>
          <p className="mt-1 truncate text-[17px] font-semibold" style={{ fontFamily: 'var(--font-serif)', color: C.ink }}>
            {first.label}
          </p>
          <p className="text-[12.5px]" style={{ color: C.grayMuted }}>
            {first.source === 'aide' ? 'Demande d’aide' : 'Dossier'}
            {rest.length > 0 ? ` · et ${rest.length} autre${rest.length > 1 ? 's' : ''} ce jour-là` : ''}
          </p>
        </div>
        <span
          className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-xl px-4 py-2.5 text-[13px] font-semibold text-white sm:self-center"
          style={{ background: C.orange }}
        >
          Je m'en occupe
          <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5" />
        </span>
      </div>
    </Link>
  );
}
