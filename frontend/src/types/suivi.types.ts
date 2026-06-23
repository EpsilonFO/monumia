import type { ID } from './common.types';

export type AideSuiviStatut =
  | 'a_faire'
  | 'en_preparation'
  | 'depose'
  | 'accorde'
  | 'refuse';

export type AideRefusMotif =
  | 'inegibilite'
  | 'budget_epuise'
  | 'dossier_incomplet'
  | 'non_prioritaire'
  | 'hors_delai'
  | 'autre';

export type EtatProjet = 'ouvert' | 'pret_a_cloturer' | 'boucle';

export interface AideSuiviHistoriqueEntry {
  statut: AideSuiviStatut;
  at: string;
}

export interface AideSuivi {
  id: ID;
  monumentId: ID;
  aideId: ID;
  userId: ID;
  statut: AideSuiviStatut;
  montantObtenu?: number;
  motifRefusCode?: AideRefusMotif;
  motifRefusDetail?: string;
  note?: string;
  historique: AideSuiviHistoriqueEntry[];
  createdAt: string;
  updatedAt: string;
}

export const AIDE_SUIVI_STATUTS: AideSuiviStatut[] = [
  'a_faire',
  'en_preparation',
  'depose',
  'accorde',
  'refuse',
];

export const AIDE_SUIVI_STATUTS_TERMINAUX: AideSuiviStatut[] = ['accorde', 'refuse'];

export const AIDE_SUIVI_STATUT_LABELS: Record<AideSuiviStatut, string> = {
  a_faire: 'À faire',
  en_preparation: 'En préparation',
  depose: 'Déposé',
  accorde: 'Accordé',
  refuse: 'Refusé',
};

export const AIDE_REFUS_MOTIFS: AideRefusMotif[] = [
  'inegibilite',
  'budget_epuise',
  'dossier_incomplet',
  'non_prioritaire',
  'hors_delai',
  'autre',
];

export const AIDE_REFUS_MOTIF_LABELS: Record<AideRefusMotif, string> = {
  inegibilite: 'Finalement inéligible',
  budget_epuise: 'Enveloppe épuisée',
  dossier_incomplet: 'Dossier incomplet',
  non_prioritaire: 'Projet non prioritaire',
  hors_delai: 'Hors délai',
  autre: 'Autre',
};
