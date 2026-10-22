import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, MoreVertical } from 'lucide-react';
import { IconContact, IconEquipe, IconDeconnexion } from '@/components/icons';
import { Input } from '@/components/ui/input';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import { projetSharingService, sharingService } from '@/services/sharing.service';
import { projectPermissions } from '@/lib/project-permissions';
import { OffreUpsell } from '@/components/shared/OffreUpsell';
import { RoleBadge } from './RoleBadge';
import { MemberAvatar } from './MemberAvatar';
import { useAuthStore } from '@/stores/useAuthStore';
import { libelleMetier } from '@/constants/metiers';
import { C, SERIF } from '@/lib/brand';
import type { ProjectMember, ProjectInvitation, ProjectRole } from '@/types';

interface TeamPanelProps {
  /** Portée du partage : le bien, ou l'un de ses chantiers. */
  scope: 'monument' | 'projet';
  /** Id du monument ou du projet, selon `scope`. */
  scopeId: string;
  /**
   * L'offre du bien permet-elle d'AJOUTER quelqu'un ? Le retrait, lui, reste
   * toujours ouvert : après une résiliation, l'équipe garde son accès, et
   * couper un accès qu'on ne contrôle plus n'est pas un service mais une
   * sécurité. D'où deux droits distincts là où il n'y en avait qu'un.
   */
  invitationsOuvertes: boolean;
  myRole: ProjectRole | null;
  members: ProjectMember[];
  invitations: ProjectInvitation[];
  onChanged: () => void;
  onLeft?: () => void;
}

/**
 * Panneau d'équipe, pour un MONUMENT ou pour un PROJET de travaux.
 *
 * Un seul composant, paramétré par la portée : les deux écrans font exactement
 * les mêmes gestes (inviter, promouvoir, retirer, quitter) et les dupliquer les
 * ferait dériver. Ce qui change, ce sont les mots — parce que l'enjeu, lui,
 * n'est pas le même : sur un projet, ce panneau ouvre un accès CLOISONNÉ, et le
 * dire est la moitié du travail. Ces mots vivent dans `shell:TeamPanel.monument`
 * et `shell:TeamPanel.projet`, mêmes clés des deux côtés.
 */
export function TeamPanel({
  scope,
  scopeId,
  invitationsOuvertes,
  myRole,
  members,
  invitations,
  onChanged,
  onLeft,
}: TeamPanelProps) {
  const { t } = useTranslation(['shell', 'common']);
  const currentUserId = useAuthStore((s) => s.user?.id);
  const perms = projectPermissions(myRole);
  const api = scope === 'projet' ? projetSharingService : sharingService;
  const [email, setEmail] = useState('');
  const [inviting, setInviting] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState<ProjectMember | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const isSolo = members.length === 1 && invitations.length === 0;
  const peutInviter = perms.canInvite && invitationsOuvertes;

  const handleInvite = async () => {
    const target = email.trim();
    if (!target) return;
    setInviting(true);
    try {
      await api.invite(scopeId, target);
      toast.success(t('TeamPanel.invitationEnvoyeeA', { email: target }));
      setEmail('');
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : t('TeamPanel.echecInvitation'));
    } finally {
      setInviting(false);
    }
  };

  const act = async (fn: () => Promise<void>, okMsg: string) => {
    try {
      await fn();
      toast.success(okMsg);
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : t('TeamPanel.actionImpossible'));
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-[20.5px]" style={{ fontFamily: SERIF, color: C.ink }}>
          {t(`TeamPanel.${scope}.titre`)}
        </h2>
        <p className="text-[15px] text-muted-foreground">{t(`TeamPanel.${scope}.intro`)}</p>
      </div>

      {/* Le formulaire cède la place à la porte de sortie quand l'offre ne
          permet plus d'ajouter : on n'arrive ici, dans ce cas, que parce qu'une
          équipe est déjà constituée et reste à gérer. */}
      {perms.canInvite && !invitationsOuvertes && (
        <OffreUpsell
          action={t(`TeamPanel.${scope}.upsell`)}
          offre="Veille"
        />
      )}

      {peutInviter && (
        <div
          className="rounded-xl border p-4 space-y-2"
          style={{ background: C.card, borderColor: C.border }}
        >
          <label className="flex items-center gap-1.5 text-[15px] font-semibold" style={{ color: C.ink }}>
            <IconEquipe className="h-4 w-4" style={{ color: C.blue }} strokeWidth={1.8} />
            {t('TeamPanel.inviterPersonne')}
          </label>
          <div className="flex gap-2">
            <Input
              type="email"
              placeholder={t('TeamPanel.emailPlaceholder')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleInvite()}
              className="h-10 text-[16px] bg-card"
              style={{ borderColor: C.border }}
            />
            <button
              type="button"
              onClick={handleInvite}
              disabled={inviting || !email.trim()}
              aria-label={t('common:actions.inviter')}
              className="inline-flex items-center gap-2 px-4 py-2 text-[15px] font-semibold text-white rounded-lg disabled:opacity-50"
              style={{ background: C.orange }}
            >
              {inviting ? <Loader2 className="h-4 w-4 animate-spin" /> : t('common:actions.inviter')}
            </button>
          </div>
          <p className="text-[13px] text-muted-foreground">
            {t('TeamPanel.emailEnvoye')}
          </p>
        </div>
      )}

      {isSolo && (
        <p className="text-[15px] text-muted-foreground">
          {t(`TeamPanel.${scope}.solo`)}
          {peutInviter ? ` ${t('TeamPanel.inviterCiDessus')}` : ''}
        </p>
      )}

      <div className="space-y-2">
        <p className="text-[14px] font-semibold uppercase tracking-wide text-muted-foreground">
          {t('TeamPanel.personnesAcces', { nombre: members.length })}
        </p>
        {members.map((m, mi) => {
          const isMe = m.userId === currentUserId;
          // Sur un projet, un membre HÉRITÉ de l'équipe du monument n'est pas
          // gérable ici : son droit vient d'un cran au-dessus, le retirer du
          // chantier ne le lui ôterait pas.
          const herite = scope === 'projet' && m.source === 'monument';
          const canManageThis =
            perms.canManageMembers && m.role !== 'owner' && !isMe && !herite;
          return (
            <div
              key={m.userId}
              className="flex items-center gap-3 rounded-lg border px-3 py-2.5"
              style={{ borderColor: C.border, background: C.card }}
            >
              <MemberAvatar person={m} size="md" colorIndex={mi} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-[16px] font-medium truncate" style={{ color: C.ink }}>
                    {m.prenom} {m.nom} {isMe && <span className="text-muted-foreground">{t('TeamPanel.vous')}</span>}
                  </p>
                  <RoleBadge role={m.role} />
                  {herite && (
                    <span
                      className="rounded-full px-2 py-0.5 text-[13px] font-semibold"
                      style={{ background: C.paleBlue, color: C.blue }}
                      title={t('TeamPanel.accesHerite')}
                    >
                      {t('TeamPanel.equipeMonument')}
                    </span>
                  )}
                </div>
                <p className="text-[14px] truncate text-muted-foreground">
                  {[m.metier && libelleMetier(m.metier), m.email].filter(Boolean).join(' · ')}
                </p>
              </div>
              {canManageThis && (
                <DropdownMenu>
                  <DropdownMenuTrigger
                    aria-label={t('TeamPanel.gererMembre')}
                    className="inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[14px] font-medium hover:bg-muted text-gray-fg"
                    style={{ borderColor: C.border }}
                  >
                    {t('TeamPanel.gerer')} <MoreVertical className="h-3.5 w-3.5" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {m.role === 'member' ? (
                      <DropdownMenuItem
                        onClick={() => act(() => api.promote(scopeId, m.userId), t('TeamPanel.promu'))}
                      >
                        {t('TeamPanel.promouvoir')}
                      </DropdownMenuItem>
                    ) : (
                      <DropdownMenuItem
                        onClick={() => act(() => api.demote(scopeId, m.userId), t('TeamPanel.retrograde'))}
                      >
                        {t('TeamPanel.retrograder')}
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem className="text-destructive" onClick={() => setConfirmRemove(m)}>
                      {t(`TeamPanel.${scope}.retirer`)}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          );
        })}
      </div>

      {invitations.length > 0 && (
        <div className="space-y-2">
          <p className="text-[14px] font-semibold uppercase tracking-wide text-muted-foreground">
            {t('TeamPanel.invitationsEnAttente', { nombre: invitations.length })}
          </p>
          {invitations.map((inv) => (
            <div
              key={inv.id}
              className="flex items-center gap-3 rounded-lg border border-dashed px-3 py-2.5"
              style={{ borderColor: C.border }}
            >
              <IconContact className="h-4 w-4 text-muted-foreground" />
              <p className="text-[15px] flex-1 truncate text-gray-fg">{inv.email}</p>
              <span className="text-[13px] text-muted-foreground">{t('TeamPanel.invitationEnvoyee')}</span>
              {perms.canInvite && (
                <button
                  type="button"
                  className="text-[14px] hover:underline text-destructive"
                  onClick={() => act(() => api.revokeInvitation(scopeId, inv.id), t('TeamPanel.invitationAnnulee'))}
                >
                  {t('common:actions.annuler')}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {perms.canLeave && (
        <div className="pt-2 border-t" style={{ borderColor: C.border }}>
          <button
            type="button"
            onClick={() => setConfirmLeave(true)}
            className="inline-flex items-center gap-2 rounded-lg border px-3.5 py-2 text-[15px] font-semibold transition-colors hover:bg-destructive-muted text-destructive border-destructive-muted"
          >
            <IconDeconnexion className="h-4 w-4" strokeWidth={1.8} />
            {t(`TeamPanel.${scope}.quitter`)}
          </button>
        </div>
      )}

      <AlertDialog open={!!confirmRemove} onOpenChange={(o) => !o && setConfirmRemove(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('TeamPanel.retirerQui', { prenom: confirmRemove?.prenom ?? '', nom: confirmRemove?.nom ?? '' })}
            </AlertDialogTitle>
            <AlertDialogDescription>{t(`TeamPanel.${scope}.retirerTexte`)}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common:actions.annuler')}</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                const target = confirmRemove;
                setConfirmRemove(null);
                if (target) act(() => api.removeMember(scopeId, target.userId), t('TeamPanel.membreRetire'));
              }}
            >
              {t('TeamPanel.retirer')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={confirmLeave} onOpenChange={setConfirmLeave}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t(`TeamPanel.${scope}.quitterTitre`)}</AlertDialogTitle>
            <AlertDialogDescription>{t(`TeamPanel.${scope}.quitterTexte`)}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common:actions.annuler')}</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                setConfirmLeave(false);
                void act(() => api.leave(scopeId), t(`TeamPanel.${scope}.quitterOk`)).then(() => onLeft?.());
              }}
            >
              {t('TeamPanel.quitter')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
