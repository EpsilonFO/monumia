import { authFetch, handleResponse } from '@/lib/auth-fetch';
import type { ProjectMember, ProjectMembersResponse } from '@/types';

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
  };
}

export const sharingService = {
  async getMembers(monumentId: string): Promise<ProjectMembersResponse> {
    const res = await authFetch(`${BASE}/projects/${monumentId}/members`);
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

  async invite(monumentId: string, email: string, message?: string): Promise<void> {
    const res = await authFetch(`${BASE}/projects/${monumentId}/invitations`, {
      method: 'POST',
      body: JSON.stringify({ email, message }),
    });
    await handleResponse(res);
  },

  async revokeInvitation(monumentId: string, invitationId: string): Promise<void> {
    const res = await authFetch(`${BASE}/projects/${monumentId}/invitations/${invitationId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },

  async promote(monumentId: string, userId: string): Promise<void> {
    const res = await authFetch(`${BASE}/projects/${monumentId}/members/${userId}/promote`, { method: 'POST' });
    await handleResponse(res);
  },

  async demote(monumentId: string, userId: string): Promise<void> {
    const res = await authFetch(`${BASE}/projects/${monumentId}/members/${userId}/demote`, { method: 'POST' });
    await handleResponse(res);
  },

  async removeMember(monumentId: string, userId: string): Promise<void> {
    const res = await authFetch(`${BASE}/projects/${monumentId}/members/${userId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },

  async leave(monumentId: string): Promise<void> {
    const res = await authFetch(`${BASE}/projects/${monumentId}/leave`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },
};
