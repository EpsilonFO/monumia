import type { ID, ProtectionLevel, OwnershipType, Region, WorkType, UserSegment } from './common.types';

export type AideCategory =
  | 'etat_drac'
  | 'region'
  | 'departement'
  | 'fondation_patrimoine'
  | 'europe'
  | 'mecenat'
  | 'fiscalite'
  | 'autre';

export type AideType = 'subvention' | 'avance' | 'pret' | 'deduction_fiscale'
  | 'label' | 'mecenat' | 'souscription' | 'autre';

export interface Aide {
  id: ID;
  nom: string;
  nomCourt: string;
  description: string;
  descriptionLongue: string;

  categorie: AideCategory;
  type: AideType;
  organisme: string;
  organismeContact?: string;

  montantMax?: number;
  tauxMax?: number;
  montantMin?: number;
  plancher?: number;

  criteres: AideEligibilityCriteria;

  demarcheDescription: string;
  documentsRequis: string[];
  delaiInstruction: string;

  dateOuverture?: string;
  dateLimite?: string;
  permanent: boolean;

  urlOfficielle?: string;
  formulaireUrl?: string;

  tags: string[];
  baseTTC: boolean;
}

export interface AideEligibilityCriteria {
  protectionRequise?: ProtectionLevel[];
  proprietaireEligible?: OwnershipType[];
  travauxEligibles?: WorkType[];

  regionEligible?: Region[];
  departementEligible?: string[];

  segmentEligible?: UserSegment[];

  communeDeMoins10000Hab?: boolean;
  communeMaxPopulation?: number;
  diagnosticPrealableRequis?: boolean;
  architecteRequis?: boolean;
  cofinancementRequis?: boolean;

  etatConservationRequis?: ('bon' | 'moyen' | 'mauvais' | 'peril')[];

  criteresSupplementaires?: {
    label: string;
    description: string;
  }[];
}

export interface AideMatchResult {
  aide: Aide;
  eligible: boolean;
  criteresRemplis: string[];
  criteresNonRemplis: string[];
  raisonIneligibilite?: string;
}

export interface AideDiagnosticRequest {
  monumentId: ID;
  modeProjet: boolean;
  travauxFiltres?: WorkType[];
}

export interface AideDiagnosticResult {
  id?: string;
  monumentId: ID;
  timestamp: string;
  modeProjet?: boolean;
  travauxFiltres?: string[];
  totalAidesAnalysees: number;
  aidesEligibles: AideMatchResult[];
  aidesNonEligibles: AideMatchResult[];
  montantPotentielTotal?: number;
}
