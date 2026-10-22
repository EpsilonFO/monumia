import i18n from '@/i18n';
import type { DocumentVisibility, ID, ProjectRole } from '@/types';

const RANK: Record<ProjectRole, number> = { member: 1, co_owner: 2, owner: 3 };

function atLeast(role: ProjectRole | null, min: ProjectRole): boolean {
  return role !== null && RANK[role] >= RANK[min];
}

/** Visibilités qu'un rôle a le droit de poser. Un collaborateur n'a pas toute l'équipe. */
export function allowedVisibilities(role: ProjectRole | null): DocumentVisibility[] {
  return atLeast(role, 'co_owner')
    ? ['team', 'responsables', 'custom']
    : ['responsables', 'custom'];
}

/** Changer la visibilité : l'auteur, ou un owner/co_owner. */
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

/** Sous-ensemble des membres qui peuvent consulter un document, selon sa visibilité.
 *  Le chef (owner) et l'auteur voient toujours — miroir de `canViewDocument`. */
export function whoCanView(
  members: { userId: ID; role: ProjectRole }[],
  visibility: DocumentVisibility,
  allowedUserIds: ID[],
  uploaderId?: ID,
): ID[] {
  const ids = new Set<ID>();
  for (const m of members) {
    if (
      m.role === 'owner' ||
      (uploaderId && m.userId === uploaderId) ||
      visibility === 'team' ||
      (visibility === 'responsables' && m.role === 'co_owner') ||
      (visibility === 'custom' && allowedUserIds.includes(m.userId))
    ) {
      ids.add(m.userId);
    }
  }
  return [...ids];
}

/** Pré-coche la liste « personnes choisies » selon le réglage précédent. */
export function customIdsForPreset(
  prior: DocumentVisibility,
  members: { userId: ID; role: ProjectRole }[],
): ID[] {
  if (prior === 'team') return members.filter((m) => m.role !== 'owner').map((m) => m.userId);
  if (prior === 'responsables') return members.filter((m) => m.role === 'co_owner').map((m) => m.userId);
  return [];
}

export const VISIBILITY_META: Record<DocumentVisibility, { label: string; help: string }> = {
  team: {
    get label() { return i18n.t('core:documentVisibility.team.libelle'); },
    get help() { return i18n.t('core:documentVisibility.team.aide'); },
  },
  responsables: {
    get label() { return i18n.t('core:documentVisibility.responsables.libelle'); },
    get help() { return i18n.t('core:documentVisibility.responsables.aide'); },
  },
  custom: {
    get label() { return i18n.t('core:documentVisibility.custom.libelle'); },
    get help() { return i18n.t('core:documentVisibility.custom.aide'); },
  },
};
