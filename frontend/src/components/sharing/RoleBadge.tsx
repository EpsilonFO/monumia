import type { ProjectRole } from '@/types';

export const ROLE_LABELS: Record<ProjectRole, string> = {
  owner: 'Chef de projet',
  co_owner: 'Chef de projet adjoint',
  member: 'Collaborateur',
};

const ROLE_STYLES: Record<ProjectRole, string> = {
  owner:    'bg-secondary text-primary',
  co_owner: 'bg-warning-muted text-accent',
  member:   'bg-muted text-muted-foreground',
};

export function RoleBadge({ role }: { role: ProjectRole }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[13px] font-semibold ${ROLE_STYLES[role]}`}
    >
      {ROLE_LABELS[role]}
    </span>
  );
}
