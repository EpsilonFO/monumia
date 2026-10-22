import { useTranslation } from 'react-i18next';
import { IconAjouter, IconLocalisation } from '@/components/icons';
import { MonumentPhotoProfil } from '@/components/monument/MonumentPhotoProfil';
import { C, SERIF } from '@/lib/brand';
import type { Monument, ProjectMember } from '@/types';
import { isProjectShared, projectPermissions } from '@/lib/project-permissions';
import { SharedBadge } from '@/components/sharing/SharedBadge';
import { MemberAvatarStack } from '@/components/sharing/MemberAvatarStack';
import { RoleBadge } from '@/components/sharing/RoleBadge';

interface MonumentSummaryBarProps {
  monument: Monument;
  members?: ProjectMember[];
  /**
   * Absent quand l'offre du bien a atteint son plafond de projets. L'en-tête
   * cède alors la place à la porte de sortie : la liste des projets, plus bas,
   * porte déjà le même appel à l'offre — inutile de le doubler ici.
   */
  onNouveauProjet?: () => void;
}

/**
 * En-tête de la page monument : l'identité du bien. Le détail des chantiers
 * vit sur la page du projet.
 */
export function MonumentSummaryBar({
  monument,
  members = [],
  onNouveauProjet,
}: MonumentSummaryBarProps) {
  const { t } = useTranslation('monuments');
  const location = [monument.commune, monument.departement].filter(Boolean).join(', ');

  const shared = isProjectShared({
    myRole: monument.myRole,
    memberCount: members.length || monument.memberCount,
  });
  // Monument partagé : on montre le rôle réel, y compris « Chef de projet » (owner).
  const showRole = shared && !!monument.myRole;
  const canEdit = projectPermissions(monument.myRole ?? null).canEditProject;

  return (
    <div
      className="rounded-2xl border p-6 sm:p-7"
      style={{ background: C.card, borderColor: C.border, boxShadow: 'var(--shadow-card)' }}
    >
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-col gap-5 sm:flex-row sm:items-center">
          {/* Le portrait du bien, celui qu'on retrouve ensuite sur les cartes de
              « Mes monuments ».

              La colonne est bornée à partir de `sm` : le cadre est fluide
              (pleine largeur sur un téléphone), et sans cette borne il
              réclamerait toute la ligne — le nom du monument se replierait
              alors en trois lignes contre la photo. */}
          <div className="w-full shrink-0 sm:w-[241px]">
            <MonumentPhotoProfil monument={monument} canEdit={canEdit} width={212} radius="0.75rem" />
          </div>
          <div className="min-w-0 flex-1 space-y-2.5">
            <h1
              className="text-[clamp(1.6rem,3vw,2.15rem)] leading-[1.15]"
              style={{ fontFamily: SERIF, color: C.ink }}
            >
              {monument.nom}
            </h1>
            {location && (
              <p className="flex items-center gap-1.5 text-[16.5px]" style={{ color: C.grayFg }}>
                <IconLocalisation className="h-4 w-4 shrink-0" style={{ color: C.blueLight }} />
                {location}
              </p>
            )}
            {(shared || showRole) && (
              <div className="flex flex-wrap items-center gap-2 pt-0.5">
                {shared && <SharedBadge count={members.length || monument.memberCount} />}
                {showRole && monument.myRole && <RoleBadge role={monument.myRole} />}
                {shared && members.length > 0 && <MemberAvatarStack people={members} size="sm" />}
              </div>
            )}
          </div>
        </div>

        {canEdit && onNouveauProjet && (
          <button
            onClick={onNouveauProjet}
            className="inline-flex shrink-0 items-center justify-center gap-2 self-start rounded-lg px-5 py-2.5 text-[15px] font-semibold text-white transition-all duration-200 hover:shadow-md sm:self-auto"
            style={{ background: C.orange }}
          >
            <IconAjouter className="h-4 w-4" strokeWidth={2} />
            {t('MonumentSummaryBar.nouveauProjet')}
          </button>
        )}
      </div>
    </div>
  );
}
