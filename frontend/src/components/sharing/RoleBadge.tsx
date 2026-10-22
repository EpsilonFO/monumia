import i18n from '@/i18n';
import type { ProjectRole } from '@/types';

// Getters : le libellé se lit dans la langue de la page au moment de l'affichage
// (cf. i18n/README.md, jamais de traduction calculée à l'import).
export const ROLE_LABELS: Record<ProjectRole, string> = {
  get owner() { return i18n.t('shell:RoleBadge.owner'); },
  get co_owner() { return i18n.t('shell:RoleBadge.co_owner'); },
  get member() { return i18n.t('shell:RoleBadge.member'); },
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
