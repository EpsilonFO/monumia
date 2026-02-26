import type { ID, WorkType } from './common.types';

export type DossierStep = 1 | 2 | 3 | 4 | 5;

export type DossierStatus =
  | 'brouillon'
  | 'en_cours'
  | 'complet'
  | 'pret'
  | 'soumis';

export type ChecklistItemStatus = 'fourni' | 'en_attente' | 'manquant';

export interface Dossier {
  id: ID;
  monumentId: ID;
  aideId: ID;
  userId: ID;

  titre: string;
  description?: string;

  etapeActuelle: DossierStep;
  statut: DossierStatus;
  progressionPourcentage: number;

  travauxPrevus: WorkType[];
  montantEstime?: number;

  checklist: ChecklistItem[];
  sections: DossierSection[];
  echeances: DossierEcheance[];
  collaborateurs: DossierCollaborateur[];

  dateCreation: string;
  dateDerniereModification: string;
  dateSoumission?: string;
}

export interface ChecklistItem {
  id: ID;
  label: string;
  description: string;
  statut: ChecklistItemStatus;
  documentId?: ID;
  obligatoire: boolean;
  categorie: 'administratif' | 'technique' | 'financier' | 'photographique';
  ordre: number;
}

export interface DossierSection {
  id: ID;
  titre: string;
  type: 'texte_libre' | 'formulaire' | 'tableau';
  contenu: string;
  champsAutoremplis?: {
    champ: string;
    valeur: string;
    source: 'monument' | 'merimee' | 'utilisateur';
  }[];
  ordre: number;
}

export interface DossierEcheance {
  id: ID;
  label: string;
  date: string;
  type: 'ouverture' | 'limite' | 'instruction' | 'notification' | 'travaux';
  accomplie: boolean;
}

export interface DossierCollaborateur {
  id: ID;
  email: string;
  nom: string;
  role: 'proprietaire' | 'adjoint' | 'architecte' | 'secretaire' | 'autre';
  permissions: 'lecture' | 'edition';
  inviteAcceptee: boolean;
}
