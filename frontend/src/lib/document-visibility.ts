import type { DocumentVisibility, ID, ProjectRole } from '@/types';

const RANK: Record<ProjectRole, number> = { member: 1, co_owner: 2, owner: 3 };

function atLeast(role: ProjectRole | null, min: ProjectRole): boolean {
  return role !== null && RANK[role] >= RANK[min];
}

/** Visibilites qu'un role a le droit de poser. Un collaborateur n'a pas toute l'equipe. */
export function allowedVisibilities(role: ProjectRole | null): DocumentVisibility[] {
  return atLeast(role, 'co_owner')
    ? ['team', 'responsables', 'custom']
    : ['responsables', 'custom'];
}

/** Changer la visibilite : l'auteur, ou un owner/co_owner. */
export function canEditVisibility(isUploader: boolean, role?: ProjectRole | null): boolean {
  return isUploader || atLeast(role ?? null, 'co_owner');
}

/** Miroir client de `can_view_document` (backend). */
export function canViewDocument(
  doc: { visibility: DocumentVisibility; allowedUserIds: ID[]; userId: ID },
  viewerId: ID | undefined,
  viewerRole: ProjectRole | null,
): boolean {
  if (viewerId && viewerId === doc.userId) return true;
  if (viewerRole === 'owner') return true;
  if (viewerRole === null) return false;
  if (viewerId && doc.allowedUserIds.includes(viewerId)) return true;
  if (doc.visibility === 'team') return true;
  if (doc.visibility === 'responsables') return atLeast(viewerRole, 'co_owner');
  return false;
}

/** Pre-coche la liste personnnes choisies selon le prerequisglage quitte. */
export function customIdsForPreset(
  prior: DocumentVisibility,
  members: { userId: ID; role: ProjectRole }[],
): ID[] {
  if (prior === 'team') return members.filter((m) => m.role !== 'owner').map((m) => m.userId);
  if (prior === 'responsables') return members.filter((m) => m.role === 'co_owner').map((m) => m.userId);
  return [];
}

export const VISIBILITY_META: Record<DocumentVisibility, { label: string; help: string }> = {
  team: { label: 'Toute l\'equipe', help: 'Tous les collaborateurs du projet' },
  responsables: { label: 'Le chef de projet et ses adjoints', help: 'Les responsables du projet' },
  custom: { label: 'Personnes choisies', help: 'Vous choisissez qui peut le voir' },
};
