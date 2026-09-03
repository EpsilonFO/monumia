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
  notificationPreferences: NotificationPreferences;
  createdAt: string;
}

export interface NotificationPreferences {
  urgentDeadlines: boolean;
  newAidesMatched: boolean;
  dossierUpdates: boolean;
  emailNotifications: boolean;
}
