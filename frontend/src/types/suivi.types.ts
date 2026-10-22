import i18n from '@/i18n';
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
  /** Le PROJET suivi. Le couple unique en base est (projet, aide). */
  projetId: ID;
  /** Monument parent, dénormalisé côté base pour les requêtes batch. */
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

// Getters : le libellé se lit dans la langue de l'interface au moment de l'affichage.
export const AIDE_SUIVI_STATUT_LABELS: Record<AideSuiviStatut, string> = {
  get a_faire() { return i18n.t('core:suivi.statuts.aFaire'); },
  get en_preparation() { return i18n.t('core:suivi.statuts.enPreparation'); },
  get depose() { return i18n.t('core:suivi.statuts.depose'); },
  get accorde() { return i18n.t('core:suivi.statuts.accorde'); },
  get refuse() { return i18n.t('core:suivi.statuts.refuse'); },
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
  get inegibilite() { return i18n.t('core:suivi.motifsRefus.inegibilite'); },
  get budget_epuise() { return i18n.t('core:suivi.motifsRefus.budgetEpuise'); },
  get dossier_incomplet() { return i18n.t('core:suivi.motifsRefus.dossierIncomplet'); },
  get non_prioritaire() { return i18n.t('core:suivi.motifsRefus.nonPrioritaire'); },
  get hors_delai() { return i18n.t('core:suivi.motifsRefus.horsDelai'); },
  get autre() { return i18n.t('core:suivi.motifsRefus.autre'); },
};
