import type { ID } from './common.types';

export interface User {
  id: ID;
  email: string;
  prenom: string;
  nom: string;
  telephone?: string;
  accountType?: 'proprietaire' | 'collaborateur';
  metier?: string;

  onboardingComplete: boolean;
  hasAidesAccess: boolean;
  notificationPreferences: NotificationPreferences;
  createdAt: string;
}

export interface NotificationPreferences {
  urgentDeadlines: boolean;
  newAidesMatched: boolean;
  dossierUpdates: boolean;
  emailNotifications: boolean;

  /**
   * Rappels calendaires envoyés par email chaque matin
   * (backend/scripts/rappels_aides.py).
   *
   * `rappelsEcheances` — une aide à portée approche de sa date limite.
   * `rappelsOuvertures` — une aide quitte « Disponibles bientôt » : sa date
   *   d'ouverture est franchie, le dépôt devient possible.
   * `rappelDelaisJours` — les paliers de rappel, en jours avant la date
   *   limite. Une liste et non un nombre : « 30 jours ET 7 jours » est le
   *   besoin courant — un rappel pour s'organiser, un pour ne pas oublier.
   */
  rappelsEcheances: boolean;
  rappelsOuvertures: boolean;
  rappelDelaisJours: number[];
}

/** Doit rester aligné sur `_default_notification_preferences` (backend). */
export const RAPPEL_DELAIS_DEFAUT = [30];

/** Bornes acceptées par PATCH /auth/me/notifications. */
export const RAPPEL_PALIER_MIN = 0;
export const RAPPEL_PALIER_MAX = 365;
export const RAPPEL_PALIERS_MAX_NOMBRE = 5;
