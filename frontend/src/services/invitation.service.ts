import { authFetch, handleResponse } from '@/lib/auth-fetch';
import type { InvitationPreview } from '@/types';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

interface RawPreview {
  monument_id: string;
  monument_nom: string;
  projet_id: string | null;
  projet_titre: string | null;
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
      projetId: r.projet_id,
      projetTitre: r.projet_titre,
      inviterNom: r.inviter_nom,
      email: r.email,
      expiresAt: r.expires_at,
      status: r.status,
      alreadyMember: r.already_member,
    };
  },

  /** Accepte l'invitation. `projetId` renseigné = elle ne portait que sur ce chantier. */
  async accept(token: string): Promise<{ monumentId: string; projetId: string | null }> {
    const res = await authFetch(`${BASE}/invitations/${token}/accept`, { method: 'POST' });
    const r = await handleResponse<{ monument_id: string; projet_id: string | null }>(res);
    return { monumentId: r.monument_id, projetId: r.projet_id ?? null };
  },
};
