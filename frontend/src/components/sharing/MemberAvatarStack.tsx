import { useTranslation } from 'react-i18next';
import { MemberAvatar, type AvatarPerson } from './MemberAvatar';

const SIZES = {
  sm: { box: 'h-7 w-7', text: 'text-[12px]' },
  md: { box: 'h-9 w-9', text: 'text-[14px]' },
} as const;

export function MemberAvatarStack({
  people,
  max = 3,
  size = 'sm',
}: {
  people: AvatarPerson[];
  max?: number;
  size?: keyof typeof SIZES;
}) {
  const { t } = useTranslation('shell');
  if (people.length === 0) return null;
  const shown = people.slice(0, max);
  const overflow = people.length - shown.length;
  const s = SIZES[size];
  return (
    <div className="flex items-center gap-1.5">
      {shown.map((p, i) => (
        <MemberAvatar key={p.userId} person={p} size={size} colorIndex={i} />
      ))}
      {overflow > 0 && (
        <span
          className={`inline-flex items-center justify-center rounded-full font-semibold bg-muted text-gray-fg ${s.box} ${s.text}`}
          title={t('MemberAvatarStack.autres', { count: overflow })}
        >
          +{overflow}
        </span>
      )}
    </div>
  );
}
