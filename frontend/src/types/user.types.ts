import type { ID } from './common.types';

export interface User {
  id: ID;
  email: string;
  prenom: string;
  nom: string;
  telephone?: string;
  accountType?: 'proprietaire' | 'collaborateur';
  metier?: string;
  /**
   * Ce compte administre-t-il le catalogue (page `/admin`) ? Posé par le
   * serveur depuis `ADMIN_USER_IDS`. Confort d'affichage seulement : chaque
   * route d'administration revérifie, et répond 403 sinon.
   */
  estAdmin?: boolean;

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
