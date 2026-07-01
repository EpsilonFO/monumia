import type { User } from '@/types';

export interface ProfileCompletion {
  /** Pourcentage de complétion, entier 0–100. */
  percent: number;
  /** Libellés des champs manquants, en langage clair, par priorité. */
  missing: string[];
}

interface CompletionField {
  label: string;
  done: (u: User) => boolean;
}

const isFilled = (v?: string | null) => !!v && v.trim().length > 0;

/** Champs qui composent la complétion du profil, dans l'ordre de priorité. */
const FIELDS: CompletionField[] = [
  { label: 'votre prénom', done: (u) => isFilled(u.prenom) },
  { label: 'votre nom', done: (u) => isFilled(u.nom) },
  { label: 'votre téléphone', done: (u) => isFilled(u.telephone) },
];

export function computeProfileCompletion(user: User): ProfileCompletion {
  const done = FIELDS.filter((f) => f.done(user)).length;
  const percent = Math.round((done / FIELDS.length) * 100);
  const missing = FIELDS.filter((f) => !f.done(user)).map((f) => f.label);
  return { percent, missing };
}
