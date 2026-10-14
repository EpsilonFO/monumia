import { authFetch, handleResponse } from '@/lib/auth-fetch';
import type { ProjectMember, ProjectMembersResponse } from '@/types';
import { suivre } from '@/lib/posthog';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

interface RawMember {
  user_id: string;
  role: ProjectMember['role'];
  prenom: string;
  nom: string;
  email: string;
  metier: string | null;
  telephone: string | null;
  joined_at: string;
  source?: ProjectMember['source'];
}

interface RawInvitation {
  id: string;
  email: string;
  status: ProjectMembersResponse['invitations'][number]['status'];
  created_at: string;
  expires_at: string;
}

function toMember(r: RawMember): ProjectMember {
  return {
    userId: r.user_id,
    role: r.role,
    prenom: r.prenom,
    nom: r.nom,
    email: r.email,
    metier: r.metier,
    telephone: r.telephone,
    joinedAt: r.joined_at,
    source: r.source,
  };
}

/**
 * Les deux portées de partage partagent la même API, à la racine près :
 *   * `/projects/{monumentId}/...` — l'équipe du MONUMENT, qui voit tout ;
 *   * `/projets/{projetId}/...`    — l'équipe d'un CHANTIER, qui ne voit que lui.
 *
 * Un seul jeu de fonctions, paramétré par la racine : les écrans sont les mêmes
 * et les faire diverger ferait dériver l'un des deux.
 */
function scopedSharing(root: 'projects' | 'projets') {
  return {
    async getMembers(scopeId: string): Promise<ProjectMembersResponse> {
      const res = await authFetch(`${BASE}/${root}/${scopeId}/members`);
      const data = await handleResponse<{ members: RawMember[]; invitations: RawInvitation[] }>(res);
      return {
        members: data.members.map(toMember),
        invitations: (data.invitations ?? []).map((i) => ({
          id: i.id,
          email: i.email,
          status: i.status,
          createdAt: i.created_at,
          expiresAt: i.expires_at,
        })),
      };
    },

    async invite(scopeId: string, email: string, message?: string): Promise<void> {
      const res = await authFetch(`${BASE}/${root}/${scopeId}/invitations`, {
        method: 'POST',
        body: JSON.stringify({ email, message }),
      });
      await handleResponse(res);
      suivre({
        nom: 'invitation_envoyee',
        proprietes: { niveau: root === 'projets' ? 'projet' : 'monument' },
      });
    },

    async revokeInvitation(scopeId: string, invitationId: string): Promise<void> {
      const res = await authFetch(`${BASE}/${root}/${scopeId}/invitations/${invitationId}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    },

    async promote(scopeId: string, userId: string): Promise<void> {
      const res = await authFetch(`${BASE}/${root}/${scopeId}/members/${userId}/promote`, { method: 'POST' });
      await handleResponse(res);
    },

    async demote(scopeId: string, userId: string): Promise<void> {
      const res = await authFetch(`${BASE}/${root}/${scopeId}/members/${userId}/demote`, { method: 'POST' });
      await handleResponse(res);
    },

    async removeMember(scopeId: string, userId: string): Promise<void> {
      const res = await authFetch(`${BASE}/${root}/${scopeId}/members/${userId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    },

    async leave(scopeId: string): Promise<void> {
      const res = await authFetch(`${BASE}/${root}/${scopeId}/leave`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    },
  };
}

export type SharingApi = ReturnType<typeof scopedSharing>;

/** Équipe d'un MONUMENT : accès à la fiche, à tous ses projets, à ses documents. */
export const sharingService = scopedSharing('projects');

/** Équipe d'UN PROJET de travaux : accès au seul chantier. */
export const projetSharingService = scopedSharing('projets');

