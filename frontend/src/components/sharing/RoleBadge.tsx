import { C } from '@/lib/brand';
import type { ProjectRole } from '@/types';

export const ROLE_LABELS: Record<ProjectRole, string> = {
  owner: 'Chef de projet',
  co_owner: 'Chef de projet adjoint',
  member: 'Collaborateur',
};

const TONES: Record<ProjectRole, { bg: string; fg: string }> = {
  owner: { bg: C.paleBlue, fg: C.blue },
  co_owner: { bg: C.paleOrange, fg: C.orange },
  member: { bg: '#f0efe9', fg: '#5C6178' },
};

export function RoleBadge({ role }: { role: ProjectRole }) {
  const tone = TONES[role];
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
      style={{ backgroundColor: tone.bg, color: tone.fg }}
    >
      {ROLE_LABELS[role]}
    </span>
  );
}
