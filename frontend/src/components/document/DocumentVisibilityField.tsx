import { Globe, Lock, Users, Check } from 'lucide-react';
import { RoleBadge } from '@/components/sharing/RoleBadge';
import { MemberAvatar } from '@/components/sharing/MemberAvatar';
import { allowedVisibilities, customIdsForPreset, VISIBILITY_META } from '@/lib/document-visibility';
import { C } from '@/lib/brand';
import type { DocumentVisibility, ID, ProjectMember, ProjectRole } from '@/types';

const ICONS: Record<DocumentVisibility, typeof Globe> = {
  team: Globe,
  responsables: Lock,
  custom: Users,
};

export interface DocumentVisibilityValue {
  visibility: DocumentVisibility;
  allowedUserIds: ID[];
}

interface Props {
  value: DocumentVisibilityValue;
  onChange: (v: DocumentVisibilityValue) => void;
  currentUserRole: ProjectRole | null;
  members: ProjectMember[];
}

export function DocumentVisibilityField({ value, onChange, currentUserRole, members }: Props) {
  const options = allowedVisibilities(currentUserRole);

  const select = (visibility: DocumentVisibility) => {
    if (visibility === 'custom') {
      onChange({ visibility, allowedUserIds: customIdsForPreset(value.visibility, members) });
    } else {
      onChange({ visibility, allowedUserIds: [] });
    }
  };

  const toggleMember = (userId: ID) => {
    const set = new Set(value.allowedUserIds);
    if (set.has(userId)) set.delete(userId);
    else set.add(userId);
    onChange({ visibility: 'custom', allowedUserIds: [...set] });
  };

  return (
    <div className="space-y-1.5">
      <p className="text-[13px] font-semibold" style={{ color: C.ink }}>
        Qui peut voir ce document&nbsp;?
      </p>

      <div className="space-y-1.5">
        {options.map((opt) => {
          const Icon = ICONS[opt];
          const active = value.visibility === opt;
          const meta = VISIBILITY_META[opt];
          return (
            <button
              key={opt}
              type="button"
              onClick={() => select(opt)}
              className="flex w-full items-start gap-2.5 rounded-lg border px-3 py-2 text-left transition-colors"
              style={{ borderColor: active ? C.blue : C.border, background: active ? C.paleBlue : C.card }}
            >
              <span
                className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border"
                style={{ borderColor: active ? C.blue : C.border, background: active ? C.blue : 'transparent' }}
              >
                {active && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
              </span>
              <Icon className="mt-0.5 h-4 w-4 shrink-0" style={{ color: active ? C.blue : C.grayMuted }} strokeWidth={1.8} />
              <span className="min-w-0">
                <span className="block text-[13px] font-medium" style={{ color: C.ink }}>{meta.label}</span>
                <span className="block text-[11px] text-muted-foreground">{meta.help}</span>
              </span>
            </button>
          );
        })}
      </div>

      {value.visibility === 'custom' && (
        <div className="max-h-44 overflow-y-auto rounded-lg border" style={{ borderColor: C.border }}>
          {members.map((m, i) => {
            const isOwner = m.role === 'owner';
            const checked = isOwner || value.allowedUserIds.includes(m.userId);
            return (
              <button
                key={m.userId}
                type="button"
                disabled={isOwner}
                onClick={() => !isOwner && toggleMember(m.userId)}
                className="flex w-full items-center gap-2.5 px-2.5 py-1.5 text-left transition-colors hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent"
              >
                <span
                  className="flex h-4 w-4 shrink-0 items-center justify-center rounded border"
                  style={
                    checked
                      ? { background: C.blue, borderColor: C.blue }
                      : { borderColor: C.border }
                  }
                >
                  {checked && <Check className="h-3 w-3 text-white" />}
                </span>
                <MemberAvatar person={m} size="sm" colorIndex={i} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px]" style={{ color: C.ink }}>
                    {m.prenom} {m.nom}
                  </span>
                </span>
                {isOwner ? (
                  <span className="text-[11px] font-medium text-muted-foreground">Toujours</span>
                ) : (
                  <RoleBadge role={m.role} />
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
