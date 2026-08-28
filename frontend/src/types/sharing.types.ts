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
  /**
   * D'où vient le droit, dans l'équipe d'un PROJET : « monument » = hérité de
   * l'équipe du bien, non modifiable depuis le chantier ; « projet » = invité
   * ici. Absent sur l'équipe d'un monument, où la question ne se pose pas.
   */
  source?: 'monument' | 'projet';
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
  /** Renseigné = l'invitation ne porte que sur CE chantier, pas sur le monument. */
  projetId?: ID | null;
  projetTitre?: string | null;
  inviterNom: string;
  email: string;
  expiresAt: string;
  status: 'pending' | 'accepted' | 'revoked' | 'expired';
  alreadyMember: boolean;
}
