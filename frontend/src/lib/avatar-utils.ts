/** Initiales lisibles : 1re lettre du prénom + 1re du nom, repli email puis « ? ». */
export function initials(prenom: string, nom: string, fallback = ''): string {
  const p = prenom.trim();
  const n = nom.trim();
  if (p || n) {
    return `${p.charAt(0)}${n.charAt(0)}`.toUpperCase();
  }
  const f = fallback.trim();
  return f ? f.charAt(0).toUpperCase() : '?';
}

/** Palette d'avatars dérivée de l'identité de marque (fond pâle + texte soutenu). */
const AVATAR_PALETTE: ReadonlyArray<{ bg: string; fg: string }> = [
  { bg: 'var(--cat-1-soft)', fg: 'var(--cat-1)' },
  { bg: 'var(--cat-2-soft)', fg: 'var(--cat-2)' },
  { bg: 'var(--cat-9-soft)', fg: 'var(--cat-9)' },
  { bg: 'var(--cat-4-soft)', fg: 'var(--cat-4)' },
  { bg: 'var(--cat-3-soft)', fg: 'var(--cat-3)' },
  { bg: 'var(--cat-8-soft)', fg: 'var(--cat-8)' },
  { bg: 'var(--cat-7-soft)', fg: 'var(--cat-7)' },
  { bg: 'var(--cat-10-soft)', fg: 'var(--cat-10)' },
];

/** Couleur déterministe à partir d'une graine (userId ou nom). */
export function avatarColor(seed: string): { bg: string; fg: string } {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % AVATAR_PALETTE.length;
  return AVATAR_PALETTE[idx];
}

/**
 * Couleur par position dans une liste — garantit une couleur distincte pour
 * chaque membre d'une même équipe (au-delà de la taille de la palette, on boucle).
 */
export function avatarColorByIndex(index: number): { bg: string; fg: string } {
  const len = AVATAR_PALETTE.length;
  return AVATAR_PALETTE[((index % len) + len) % len];
}
