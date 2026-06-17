import { authFetch, handleResponse } from '@/lib/auth-fetch';
import type { InvitationPreview } from '@/types';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

interface RawPreview {
  monument_id: string;
  monument_nom: string;
  inviter_nom: string;
  email: string;
  expires_at: string;
  status: InvitationPreview['status'];
  already_member: boolean;
}

export const invitationService = {
  async getByToken(token: string): Promise<InvitationPreview> {
    const res = await fetch(`${BASE}/invitations/${token}`);
    const r = await handleResponse<RawPreview>(res);
    return {
      monumentId: r.monument_id,
      monumentNom: r.monument_nom,
      inviterNom: r.inviter_nom,
      email: r.email,
      expiresAt: r.expires_at,
      status: r.status,
      alreadyMember: r.already_member,
    };
  },

  async accept(token: string): Promise<{ monumentId: string }> {
    const res = await authFetch(`${BASE}/invitations/${token}/accept`, { method: 'POST' });
    const r = await handleResponse<{ monument_id: string }>(res);
    return { monumentId: r.monument_id };
  },
};
