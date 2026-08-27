import { IconLocalisation, IconAjouter } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { C, SERIF } from '@/lib/brand';
import { isEnPeril, perilLabel } from '@/constants/monument-options';
import type { Monument, ProjectMember } from '@/types';
import { isProjectShared, projectPermissions } from '@/lib/project-permissions';
import { SharedBadge } from '@/components/sharing/SharedBadge';
import { MemberAvatarStack } from '@/components/sharing/MemberAvatarStack';
import { RoleBadge } from '@/components/sharing/RoleBadge';

interface MonumentSummaryBarProps {
  monument: Monument;
  members?: ProjectMember[];
  onNouveauProjet: () => void;
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
  const location = [monument.commune, monument.departement].filter(Boolean).join(' · ');

  const shared = isProjectShared({
    myRole: monument.myRole,
    memberCount: members.length || monument.memberCount,
  });
  // Monument partagé : on montre le rôle réel, y compris « Chef de projet » (owner).
  const showRole = shared && !!monument.myRole;

  return (
    <div
      className="rounded-2xl border p-6 sm:p-7"
      style={{ background: C.card, borderColor: C.border }}
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3 min-w-0">
          <h1 className="text-[clamp(1.5rem,3vw,2rem)] leading-tight" style={{ fontFamily: SERIF, color: C.ink }}>
            {monument.nom}
          </h1>
          {location && (
            <div className="flex items-center gap-1.5 text-[14px] text-muted-foreground">
              <IconLocalisation className="h-3.5 w-3.5" style={{ color: C.blueLight }} />
              <span>{location}</span>
            </div>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            {isEnPeril(monument.etatConservation) && (
              <Badge variant="outline" style={{ borderColor: C.border, color: C.ink }}>
                {perilLabel(monument.etatConservation)}
              </Badge>
            )}
            {shared && <SharedBadge count={members.length || monument.memberCount} />}
            {showRole && monument.myRole && <RoleBadge role={monument.myRole} />}
          </div>
          {shared && members.length > 0 && (
            <div className="flex items-center gap-2 pt-1">
              <MemberAvatarStack people={members} size="sm" />
            </div>
          )}
        </div>

        {projectPermissions(monument.myRole ?? null).canEditProject && (
          <button
            onClick={onNouveauProjet}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md shrink-0"
            style={{ background: C.orange }}
          >
            <IconAjouter className="h-4 w-4" strokeWidth={2} />
            Nouveau projet de travaux
          </button>
        )}
      </div>
    </div>
  );
}
