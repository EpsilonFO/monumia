import { initials, avatarColor, avatarColorByIndex } from '@/lib/avatar-utils';

export interface AvatarPerson {
  userId: string;
  prenom: string;
  nom: string;
  email?: string;
}

const SIZES = {
  sm: { box: 'h-7 w-7', text: 'text-[12px]' },
  md: { box: 'h-9 w-9', text: 'text-[14px]' },
} as const;

export function MemberAvatar({
  person,
  size = 'md',
  ring = false,
  colorIndex,
}: {
  person: AvatarPerson;
  size?: keyof typeof SIZES;
  ring?: boolean;
  /** Position dans l'équipe : garantit une couleur distincte par membre. */
  colorIndex?: number;
}) {
  const color =
    colorIndex != null
      ? avatarColorByIndex(colorIndex)
      : avatarColor(person.userId || `${person.prenom}${person.nom}`);
  const label = `${person.prenom} ${person.nom}`.trim() || person.email || 'Membre';
  const s = SIZES[size];
  return (
    <span
      title={label}
      aria-label={label}
      className={`inline-flex items-center justify-center rounded-full font-semibold select-none ${s.box} ${s.text} ${ring ? 'ring-2 ring-white' : ''}`}
      style={{ backgroundColor: color.bg, color: color.fg }}
    >
      {initials(person.prenom, person.nom, person.email)}
    </span>
  );
}
