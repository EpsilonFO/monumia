import type { ID, UserSegment } from './common.types';

export interface User {
  id: ID;
  segment: UserSegment;
  email: string;
  prenom: string;
  nom: string;
  telephone?: string;
  accountType?: 'proprietaire' | 'collaborateur';
  metier?: string;

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

  btp?: {
    raisonSociale: string;
    siret?: string;
    specialites: BtpSpecialite[];
    regions: string[];
    effectifs?: '<10' | '10-49' | '50-199' | '200+';
    caAnnuel?: number;
  };

  onboardingComplete: boolean;
  hasAidesAccess: boolean;
  notificationPreferences: NotificationPreferences;
  createdAt: string;
}

export type BtpSpecialite =
  | 'maconnerie'
  | 'charpente'
  | 'couverture'
  | 'restauration_pierre'
  | 'peintures_murales'
  | 'vitraux'
  | 'menuiserie'
  | 'electricite'
  | 'all';

export interface NotificationPreferences {
  urgentDeadlines: boolean;
  newAidesMatched: boolean;
  dossierUpdates: boolean;
  emailNotifications: boolean;
}
