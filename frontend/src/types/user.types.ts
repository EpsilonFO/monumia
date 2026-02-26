import type { ID, UserSegment } from './common.types';

export interface User {
  id: ID;
  segment: UserSegment;
  email: string;
  prenom: string;
  nom: string;
  telephone?: string;

  commune?: {
    nom: string;
    codeInsee: string;
    departement: string;
    region: string;
    population: number;
    fonction: 'maire' | 'adjoint_patrimoine' | 'secretaire_mairie' | 'dgs' | 'autre';
  };

  prive?: {
    typeProprietaire: 'personne_physique' | 'sci' | 'association' | 'autre';
    regimeFiscal?: 'monuments_historiques' | 'droit_commun' | 'mecenat';
  };

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
