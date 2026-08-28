import { useState } from 'react';
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
import { RoleBadge } from './RoleBadge';
import { MemberAvatar } from './MemberAvatar';
import { useAuthStore } from '@/stores/useAuthStore';
import { C, SERIF } from '@/lib/brand';
import type { ProjectMember, ProjectInvitation, ProjectRole } from '@/types';

interface TeamPanelProps {
  /** Portée du partage : le bien, ou l'un de ses chantiers. */
  scope: 'monument' | 'projet';
  /** Id du monument ou du projet, selon `scope`. */
  scopeId: string;
  myRole: ProjectRole | null;
  members: ProjectMember[];
  invitations: ProjectInvitation[];
  onChanged: () => void;
  onLeft?: () => void;
}

const TEXTES = {
  monument: {
    titre: 'Équipe du monument',
    intro:
      'Les personnes ci-dessous peuvent consulter et travailler sur ce monument et sur tous ses projets de travaux.',
    solo: 'Vous êtes seul sur ce monument pour l’instant.',
    retirer: 'Retirer du monument',
    quitter: 'Quitter ce monument',
    quitterTitre: 'Quitter ce monument ?',
    quitterTexte:
      'Vous perdrez l’accès à ce monument et à ses projets. Il faudra une nouvelle invitation pour y revenir.',
    quitterOk: 'Vous avez quitté le monument',
    retirerTexte:
      'Cette personne perdra immédiatement l’accès au monument et à ses projets. Vous pourrez l’inviter à nouveau plus tard.',
  },
  projet: {
    titre: 'Équipe du projet',
    intro:
      'Les personnes invitées ici ne voient QUE ce projet de travaux : ses aides, ses dossiers, ses documents, et la fiche du monument en lecture. Ni les autres chantiers, ni les documents du monument.',
    solo: 'Personne n’est encore invité sur ce chantier.',
    retirer: 'Retirer du projet',
    quitter: 'Quitter ce projet',
    quitterTitre: 'Quitter ce projet ?',
    quitterTexte:
      'Vous perdrez l’accès à ce projet de travaux. Il faudra une nouvelle invitation pour y revenir.',
    quitterOk: 'Vous avez quitté le projet',
    retirerTexte:
      'Cette personne perdra immédiatement l’accès à ce projet. Vous pourrez l’inviter à nouveau plus tard.',
  },
} as const;

/**
 * Panneau d'équipe, pour un MONUMENT ou pour un PROJET de travaux.
 *
 * Un seul composant, paramétré par la portée : les deux écrans font exactement
 * les mêmes gestes (inviter, promouvoir, retirer, quitter) et les dupliquer les
 * ferait dériver. Ce qui change, ce sont les mots — parce que l'enjeu, lui,
 * n'est pas le même : sur un projet, ce panneau ouvre un accès CLOISONNÉ, et le
 * dire est la moitié du travail.
 */
export function TeamPanel({ scope, scopeId, myRole, members, invitations, onChanged, onLeft }: TeamPanelProps) {
  const currentUserId = useAuthStore((s) => s.user?.id);
  const perms = projectPermissions(myRole);
  const api = scope === 'projet' ? projetSharingService : sharingService;
  const t = TEXTES[scope];
  const [email, setEmail] = useState('');
  const [inviting, setInviting] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState<ProjectMember | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const isSolo = members.length === 1 && invitations.length === 0;

  const handleInvite = async () => {
    const target = email.trim();
    if (!target) return;
    setInviting(true);
    try {
      await api.invite(scopeId, target);
      toast.success(`Invitation envoyée à ${target}`);
      setEmail('');
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Échec de l'invitation");
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
      toast.error(e instanceof Error ? e.message : 'Action impossible');
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-[18px]" style={{ fontFamily: SERIF, color: C.ink }}>
          {t.titre}
        </h2>
        <p className="text-[13px] text-muted-foreground">{t.intro}</p>
      </div>

      {perms.canInvite && (
        <div
          className="rounded-xl border p-4 space-y-2"
          style={{ background: C.card, borderColor: C.border }}
        >
          <label className="flex items-center gap-1.5 text-[13px] font-semibold" style={{ color: C.ink }}>
            <IconEquipe className="h-4 w-4" style={{ color: C.blue }} strokeWidth={1.8} />
            Inviter une personne
          </label>
          <div className="flex gap-2">
            <Input
              type="email"
              placeholder="architecte@exemple.fr"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleInvite()}
              className="h-10 text-[14px] bg-card"
              style={{ borderColor: C.border }}
            />
            <button
              type="button"
              onClick={handleInvite}
              disabled={inviting || !email.trim()}
              aria-label="Inviter"
              className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold text-white rounded-lg disabled:opacity-50"
              style={{ background: C.orange }}
            >
              {inviting ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Inviter'}
            </button>
          </div>
          <p className="text-[11px] text-muted-foreground">
            Un email d'invitation lui sera envoyé.
          </p>
        </div>
      )}

      {isSolo && (
        <p className="text-[13px] text-muted-foreground">
          {t.solo}
          {perms.canInvite ? ' Invitez vos collaborateurs ci-dessus.' : ''}
        </p>
      )}

      <div className="space-y-2">
        <p className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
          Personnes ayant accès ({members.length})
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
                  <p className="text-[14px] font-medium truncate" style={{ color: C.ink }}>
                    {m.prenom} {m.nom} {isMe && <span className="text-muted-foreground">(vous)</span>}
                  </p>
                  <RoleBadge role={m.role} />
                  {herite && (
                    <span
                      className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                      style={{ background: C.paleBlue, color: C.blue }}
                      title="Accès hérité de l’équipe du monument"
                    >
                      Équipe du monument
                    </span>
                  )}
                </div>
                <p className="text-[12px] truncate text-muted-foreground">
                  {[m.metier, m.email].filter(Boolean).join(' · ')}
                </p>
              </div>
              {canManageThis && (
                <DropdownMenu>
                  <DropdownMenuTrigger
                    aria-label="Gérer ce membre"
                    className="inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-[12px] font-medium hover:bg-muted text-gray-fg"
                    style={{ borderColor: C.border }}
                  >
                    Gérer <MoreVertical className="h-3.5 w-3.5" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {m.role === 'member' ? (
                      <DropdownMenuItem
                        onClick={() => act(() => api.promote(scopeId, m.userId), 'Promu chef de projet adjoint')}
                      >
                        Promouvoir chef de projet adjoint
                      </DropdownMenuItem>
                    ) : (
                      <DropdownMenuItem
                        onClick={() => act(() => api.demote(scopeId, m.userId), 'Rétrogradé collaborateur')}
                      >
                        Rétrograder collaborateur
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem className="text-destructive" onClick={() => setConfirmRemove(m)}>
                      {t.retirer}
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
          <p className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
            Invitations en attente ({invitations.length})
          </p>
          {invitations.map((inv) => (
            <div
              key={inv.id}
              className="flex items-center gap-3 rounded-lg border border-dashed px-3 py-2.5"
              style={{ borderColor: C.border }}
            >
              <IconContact className="h-4 w-4 text-muted-foreground" />
              <p className="text-[13px] flex-1 truncate text-gray-fg">{inv.email}</p>
              <span className="text-[11px] text-muted-foreground">Invitation envoyée</span>
              {perms.canInvite && (
                <button
                  type="button"
                  className="text-[12px] hover:underline text-destructive"
                  onClick={() => act(() => api.revokeInvitation(scopeId, inv.id), 'Invitation annulée')}
                >
                  Annuler
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
            className="inline-flex items-center gap-2 rounded-lg border px-3.5 py-2 text-[13px] font-semibold transition-colors hover:bg-destructive-muted text-destructive border-destructive-muted"
          >
            <IconDeconnexion className="h-4 w-4" strokeWidth={1.8} />
            {t.quitter}
          </button>
        </div>
      )}

      <AlertDialog open={!!confirmRemove} onOpenChange={(o) => !o && setConfirmRemove(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Retirer {confirmRemove?.prenom} {confirmRemove?.nom}&nbsp;?
            </AlertDialogTitle>
            <AlertDialogDescription>{t.retirerTexte}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                const target = confirmRemove;
                setConfirmRemove(null);
                if (target) act(() => api.removeMember(scopeId, target.userId), 'Membre retiré');
              }}
            >
              Retirer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={confirmLeave} onOpenChange={setConfirmLeave}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t.quitterTitre}</AlertDialogTitle>
            <AlertDialogDescription>{t.quitterTexte}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                setConfirmLeave(false);
                void act(() => api.leave(scopeId), t.quitterOk).then(() => onLeft?.());
              }}
            >
              Quitter
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
