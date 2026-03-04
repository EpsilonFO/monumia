import type { ID, ProtectionLevel, OwnershipType, Region, WorkType } from './common.types';

export interface Monument {
  id: ID;
  userId: ID;

  // Step 1: Identification
  nom: string;
  referenceMerimee?: string;
  denomination: string;
  adresse: string;
  codePostal: string;
  commune: string;
  codeInsee: string;
  departement: string;
  region: Region;
  coordonnees?: { lat: number; lng: number };

  // Step 2: Legal Status
  protection: ProtectionLevel;
  dateProtection?: string;
  typeProtection?: string;
  proprietaire: OwnershipType;
  affectataire?: string;

  // Step 3: Physical Description
  siecleConstruction?: string;
  periodeConstruction?: string[];
  superficie?: number;
  materiaux?: string[];
  typeCouverture?: string;
  nombreNiveaux?: number;
  descriptionGenerale?: string;

  // Step 4: Current State
  etatConservation: 'bon' | 'moyen' | 'mauvais' | 'peril';
  travauxEnvisages?: WorkType[];
  urgenceTravaux?: 'faible' | 'moyenne' | 'haute' | 'critique';
  diagnosticRealise?: boolean;
  derniersTravaux?: string;
  descriptionEtat?: string;

  // Step 5: Photos
  photos: MonumentPhoto[];

  // Metadata
  completionPercentage: number;
  createdAt: string;
  updatedAt: string;
}

export interface MonumentPhoto {
  id: ID;
  url: string;
  legende: string;
  type: 'facade' | 'interieur' | 'detail' | 'aerien' | 'degradation' | 'autre';
  datePhoto?: string;
}

export interface MerimeeRecord {
  reference: string;
  region: string;
  commune_forme_index: string;
  departement_en_lettres: string;
  typologie_de_la_protection: string;
  titre_editorial_de_la_notice: string;
}

export interface MonumentFormState {
  currentStep: 1 | 2 | 3 | 4 | 5;
  isComplete: boolean;
  stepsCompleted: boolean[];
}
