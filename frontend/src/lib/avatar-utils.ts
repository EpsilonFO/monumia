import { C } from '@/lib/brand';

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
  { bg: C.paleBlue, fg: C.blue },
  { bg: C.paleOrange, fg: C.orange },
  { bg: '#e7f3ec', fg: '#1f7a4d' },
  { bg: '#efe9f6', fg: '#6b3fa0' },
  { bg: '#e2f1f3', fg: '#1f6b75' },
  { bg: '#fbe9ef', fg: '#a83a5b' },
  { bg: '#f6efdc', fg: '#8a6d1f' },
  { bg: '#f0efe9', fg: '#5C6178' },
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
