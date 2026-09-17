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
   * serveur depuis le rôle `admin` de la table `comptes_roles`, uni au socle
   * `ADMIN_USER_IDS`. Un bêta-testeur répond faux : son rôle n'ouvre que l'offre.
   * Confort d'affichage seulement : chaque route d'administration revérifie, et
   * répond 403 sinon.
   *
   * Ce rôle ouvre aussi l'offre Multi-monuments d'office — mais l'offre se lit
   * sur `GET /billing/access` comme pour tout le monde, jamais ici.
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
