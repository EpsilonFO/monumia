import type { ProjectRole } from '@/types';

export interface ProjectPermissions {
  canViewMembers: boolean;
  canInvite: boolean;
  canManageMembers: boolean; // promouvoir / rétrograder / retirer
  canEditProject: boolean; // éditer fiche monument + dossiers
  canAccessAides: boolean; // consulter l'onglet « Aides » et ouvrir un dossier
  canDeleteAnyDoc: boolean;
  canDeleteProject: boolean;
  canLeave: boolean;
}

const RANK: Record<ProjectRole, number> = { member: 1, co_owner: 2, owner: 3 };

function atLeast(role: ProjectRole | null, min: ProjectRole): boolean {
  return role !== null && RANK[role] >= RANK[min];
}

export function projectPermissions(role: ProjectRole | null): ProjectPermissions {
  return {
    canViewMembers: role !== null,
    canInvite: atLeast(role, 'co_owner'),
    canManageMembers: atLeast(role, 'co_owner'),
    canEditProject: atLeast(role, 'co_owner'),
    canAccessAides: atLeast(role, 'co_owner'),
    canDeleteAnyDoc: atLeast(role, 'co_owner'),
    canDeleteProject: role === 'owner',
    canLeave: role === 'member' || role === 'co_owner',
  };
}

/**
 * Suppression / remplacement d'un document : autorisé à son auteur (celui qui
 * l'a déposé) OU à un owner / co_owner du projet, qui a tous les droits sur les
 * documents quel qu'en soit l'auteur. Un simple membre ne peut agir que sur les
 * siens. La consultation reste ouverte à tous les membres du projet.
 */
export function canDeleteDocument(isUploader: boolean, role?: ProjectRole | null): boolean {
  return isUploader || atLeast(role ?? null, 'co_owner');
}

/**
 * Rôle à afficher comme « mention de projet partagé » sur une carte.
 * Renvoie le rôle pour un projet partagé (co_owner / member), sinon null
 * (projet personnel : myRole `owner`, `undefined` ou `null`).
 */
export function sharedRole(role: ProjectRole | null | undefined): ProjectRole | null {
  return role && role !== 'owner' ? role : null;
}

/**
 * Un projet est « partagé » si l'utilisateur courant y est collaborateur
 * (rôle ≠ owner) ou s'il compte plus d'un membre.
 */
export function isProjectShared(m: {
  myRole?: ProjectRole | null;
  memberCount?: number;
  members?: unknown[];
}): boolean {
  if (m.myRole && m.myRole !== 'owner') return true;
  const count = m.memberCount ?? m.members?.length ?? 1;
  return count > 1;
}
