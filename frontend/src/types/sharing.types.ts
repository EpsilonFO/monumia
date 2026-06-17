import type { ID } from './common.types';

export type ProjectRole = 'owner' | 'co_owner' | 'member';

/** Aperçu léger d'un membre (liste des projets : avatars + compteur). */
export interface MemberPreview {
  userId: ID;
  prenom: string;
  nom: string;
  role: ProjectRole;
}

export interface ProjectMember {
  userId: ID;
  role: ProjectRole;
  prenom: string;
  nom: string;
  email: string;
  metier: string | null;
  telephone: string | null;
  joinedAt: string;
}

export interface ProjectInvitation {
  id: ID;
  email: string;
  status: 'pending' | 'accepted' | 'revoked' | 'expired';
  createdAt: string;
  expiresAt: string;
}

export interface ProjectMembersResponse {
  members: ProjectMember[];
  invitations: ProjectInvitation[];
}

export interface InvitationPreview {
  monumentId: ID;
  monumentNom: string;
  inviterNom: string;
  email: string;
  expiresAt: string;
  status: 'pending' | 'accepted' | 'revoked' | 'expired';
  alreadyMember: boolean;
}
