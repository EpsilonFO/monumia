import type { ID, ProtectionLevel, OwnershipType, Region, WorkType } from './common.types';
import type { ProjectQuestionnaireAnswers } from './project.types';

export interface Monument {
  id: ID;
  userId: ID;
  myRole?: import('./sharing.types').ProjectRole;
  members?: import('./sharing.types').MemberPreview[];
  memberCount?: number;

  // Step 1: Identification
  nom: string;
  referenceMerimee?: string;
  codeInsee: string;
  // Derived from code_insee via communes table (not stored in DB)
  commune?: string;
  departement?: string;
  region?: Region;

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

  // Cadrage du projet (étape « Votre projet » du wizard)
  // Absent tant que la question « le monument est-il en péril ? » n'a pas été
  // posée : la fiche est créée avant. Le wizard n'écrit plus que 'peril' ou
  // 'bon' — 'moyen'/'mauvais' subsistent sur les fiches antérieures.
  etatConservation?: 'bon' | 'moyen' | 'mauvais' | 'peril';
  travauxEnvisages?: WorkType[];
  urgenceTravaux?: 'faible' | 'moyenne' | 'haute' | 'critique';
  diagnosticRealise?: boolean;
  derniersTravaux?: string;
  descriptionEtat?: string;

  // Step 5: Photos
  photos: MonumentPhoto[];

  // Project questionnaire (Phase B) — optional, degrades gracefully if DB column absent
  questionnaire?: ProjectQuestionnaireAnswers;

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
  siecle_de_la_campagne_principale_de_construction?: string;
  type_de_couverture?: string;
  materiaux_de_la_couverture?: string;
  materiaux_du_gros_oeuvre?: string;
  date_et_typologie_de_la_protection?: string;
  precision_de_la_protection?: string;
  format_abrege_du_siecle_de_construction?: string;
  denomination_de_l_edifice?: string;
  statut_juridique_de_l_edifice?: string;
  cog_insee_lors_de_la_protection?: string;
  commune_actuelle?: string | null;
}

export interface MonumentFormState {
  currentStep: 1 | 2 | 3 | 4 | 5;
  isComplete: boolean;
  stepsCompleted: boolean[];
}
