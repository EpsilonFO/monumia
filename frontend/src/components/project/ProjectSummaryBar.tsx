import { IconLocalisation, IconProtection, IconAide, IconSubvention, IconEcheance, IconRafraichir } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { C, SERIF } from '@/lib/brand';
import { formatCurrency } from '@/lib/format-utils';
import { enjeuLabel } from '@/lib/aides-enjeu';
import { deadlineLabel } from '@/lib/date-utils';
import { PROTECTION_LABELS_SHORT, ETAT_LABELS } from '@/constants/monument-options';
import type { ProjectStats } from '@/lib/project-stats';
import type { Monument, ProjectMember } from '@/types';
import { isProjectShared, projectPermissions } from '@/lib/project-permissions';
import { SharedBadge } from '@/components/sharing/SharedBadge';
import { MemberAvatarStack } from '@/components/sharing/MemberAvatarStack';
import { RoleBadge } from '@/components/sharing/RoleBadge';

interface ProjectSummaryBarProps {
  monument: Monument;
  stats: ProjectStats;
  members?: ProjectMember[];
  onRefaireQuestionnaire: () => void;
}

export function ProjectSummaryBar({ monument, stats, members = [], onRefaireQuestionnaire }: ProjectSummaryBarProps) {
  const echeance = stats.prochaineEcheance;
  const echeanceLabel = echeance ? deadlineLabel(echeance.date) : null;
  // Code couleur unique : < 30 j (ou dépassée) → rouge · 30–100 j → orange · > 100 j → bleu
  const echeanceColor =
    echeanceLabel?.urgency === 'urgent' || echeanceLabel?.urgency === 'past'
      ? C.danger
      : echeanceLabel?.urgency === 'warning'
        ? C.orange
        : C.blue;

  const enjeu = enjeuLabel(stats);

  const location = [monument.commune, monument.departement].filter(Boolean).join(' · ');

  const shared = isProjectShared({ myRole: monument.myRole, memberCount: members.length || monument.memberCount });
  // Projet partagé : on montre le rôle réel, y compris « Chef de projet » (owner).
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
            <Badge variant="outline" className="gap-1" style={{ borderColor: C.border, color: C.blue, background: C.paleBlue }}>
              <IconProtection className="h-3 w-3" />
              {PROTECTION_LABELS_SHORT[monument.protection] ?? monument.protection}
            </Badge>
            <Badge variant="outline" style={{ borderColor: C.border, color: C.ink }}>
              {ETAT_LABELS[monument.etatConservation] ?? monument.etatConservation}
            </Badge>
            {shared && <SharedBadge count={members.length || monument.memberCount} />}
            {showRole && monument.myRole && <RoleBadge role={monument.myRole} />}
          </div>
          {shared && members.length > 0 && (
            <div className="flex items-center gap-2 pt-1">
              <MemberAvatarStack people={members} size="sm" />
            </div>
          )}
        </div>

        {projectPermissions(monument.myRole ?? null).canAccessAides && (
          <button
            onClick={onRefaireQuestionnaire}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 text-[13px] font-semibold text-white rounded-lg transition-all duration-200 hover:shadow-md shrink-0"
            style={{ background: C.orange }}
          >
            <IconRafraichir className="h-4 w-4" strokeWidth={2} />
            Refaire le questionnaire
          </button>
        )}
      </div>

      <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <KpiTile
          icon={<IconAide className="h-4 w-4" style={{ color: C.blue }} />}
          label="Aides identifiées"
          value={String(stats.aidesIdentifiees)}
        />
        <KpiTile
          icon={<IconSubvention className="h-4 w-4" style={{ color: C.orange }} />}
          label="Financement mobilisable"
          value={enjeu.value}
          // « et / ou X % des travaux » : le second registre de chiffrage, dans
          // la même case — les deux plafonds ne s'additionnent pas.
          sub={enjeu.sub}
          // Le montant à débloquer reste HORS du chiffre principal : il suppose
          // une démarche encore à faire. Mentionné à côté, jamais additionné.
          note={
            stats.montantAtteignable > 0
              ? `+ ${formatCurrency(stats.montantAtteignable)} à débloquer`
              : undefined
          }
        />
        <KpiTile
          icon={<IconEcheance className="h-4 w-4" style={{ color: echeanceColor }} />}
          label="Prochaine échéance"
          value={echeanceLabel ? echeanceLabel.text : 'Aucune'}
          valueColor={echeanceLabel ? echeanceColor : undefined}
        />
      </div>
    </div>
  );
}

function KpiTile({ icon, label, value, valueColor, sub, note }: { icon: React.ReactNode; label: string; value: string; valueColor?: string; sub?: string; note?: string }) {
  return (
    <div className="rounded-xl border px-4 py-3" style={{ borderColor: C.border, background: C.cream }}>
      <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <p className="mt-1 text-[18px] font-semibold" style={{ color: valueColor ?? C.ink }}>
        {value}
      </p>
      {sub && <p className="text-[13px] font-semibold" style={{ color: valueColor ?? C.ink }}>{sub}</p>}
      {note && <p className="text-[12px] font-medium" style={{ color: 'var(--info)' }}>{note}</p>}
    </div>
  );
}
