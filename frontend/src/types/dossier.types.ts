import type { ID, WorkType } from './common.types';

export type DossierStep = 1 | 2 | 3 | 4 | 5;

export type DossierStatus =
  | 'brouillon'
  | 'en_cours'
  | 'complet'
  | 'pret'
  | 'soumis';

export type ChecklistItemStatus = 'fourni' | 'repris' | 'en_attente' | 'manquant';

export interface Dossier {
  id: ID;
  /** Le PROJET de travaux auquel ce dossier appartient. */
  projetId: ID;
  /** Monument parent, dénormalisé : c'est lui qui porte les droits et le paywall. */
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

  /** Posé par le serveur quand l'aide a quitté le catalogue (`services/aides_fermees.py`). */
  aideFermee?: AideFermee;
}

/** Une aide sortie du catalogue alors que ce dossier était ouvert dessus. */
export interface AideFermee {
  nom: string;
  /** AAAA-MM-JJ */
  fermeeLe: string;
  /** La demande est déjà partie chez le financeur : elle suit son cours, le dossier reste. */
  deposee: boolean;
}

export interface ChecklistItem {
  id: ID;
  label: string;
  description: string;
  statut: ChecklistItemStatus;
  documentId?: ID;
  /** Pièce canonique du référentiel (backend/data/pieces.yaml), si rattachée. */
  pieceId?: string;
  /** 'repris' : rattaché automatiquement depuis un autre dossier, à confirmer. */
  origine?: 'repris';
  /** Pièce périssable dont le document dépasse son seuil d'alerte. */
  perime?: boolean;
  /** Fichiers explicitement retirés de cette pièce : la reprise automatique ne
   *  les repropose plus (rattacher l'un d'eux à la main annule son refus). */
  refuses?: string[];
  obligatoire: boolean;
  categorie: 'administratif' | 'technique' | 'financier' | 'photographique' | 'document';
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
