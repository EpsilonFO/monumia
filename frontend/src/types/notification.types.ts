import type { ID } from './common.types';

export type NotificationType = 'urgent' | 'opportunite' | 'info';
export type NotificationCategory =
  | 'deadline_proche'
  | 'nouvelle_aide'
  | 'dossier_update'
  | 'document_manquant'
  | 'collaborateur'
  | 'system';

export interface Notification {
  id: ID;
  userId: ID;
  type: NotificationType;
  categorie: NotificationCategory;
  titre: string;
  message: string;
  lue: boolean;

  lienVers?: {
    type: 'aide' | 'dossier' | 'monument' | 'document';
    id: ID;
  };

  dateCreation: string;
}
