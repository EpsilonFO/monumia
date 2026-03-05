import type { ID, Region, ProtectionLevel, WorkType, OwnershipType } from './common.types';
import type { AideMatchResult } from './aide.types';

export type ProspectStatus =
  | 'a_contacter'
  | 'contacte'
  | 'en_discussion'
  | 'devis_envoye'
  | 'gagne'
  | 'perdu';

export interface Prospect {
  id: ID;
  btpUserId: ID;

  // Monument info (from Mérimée or manual)
  monumentNom: string;
  referenceMerimee?: string;
  adresse: string;
  commune: string;
  codePostal: string;
  departement: string;
  region: Region;
  protection: ProtectionLevel;
  proprietaire: OwnershipType;
  travauxEnvisages: WorkType[];
  superficie?: number;
  descriptionEtat?: string;
  etatConservation?: 'bon' | 'moyen' | 'mauvais' | 'critique';

  // Contact info
  contactNom?: string;
  contactEmail?: string;
  contactTelephone?: string;
  contactFonction?: string;

  // BTP pipeline
  statut: ProspectStatus;
  priorite: 'haute' | 'moyenne' | 'basse';
  dateProchainContact?: string;
  notes?: string;

  // Financement (calculé)
  financementIdentifie: boolean;
  aidesMatchees: AideMatchResult[];
  totalFinancementPotentiel: number;
  tauxCouvertureEstime: number; // % du projet couvert par les aides
  montantTravaux?: number; // estimation du marché potentiel

  createdAt: string;
  updatedAt: string;
}
