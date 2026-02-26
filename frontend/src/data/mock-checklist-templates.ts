import type { ChecklistItem } from '@/types';

type ChecklistTemplate = Omit<ChecklistItem, 'id' | 'statut' | 'documentId'>[];

export const checklistTemplates: Record<string, ChecklistTemplate> = {
  drac_subvention: [
    { label: 'Formulaire CERFA de demande de subvention', description: 'Formulaire officiel de demande de subvention pour travaux sur monument historique. Téléchargeable sur le site de la DRAC.', obligatoire: true, categorie: 'administratif', ordre: 1 },
    { label: 'Extrait cadastral', description: 'Extrait du plan cadastral identifiant la parcelle du monument. Disponible en mairie ou sur cadastre.gouv.fr.', obligatoire: true, categorie: 'administratif', ordre: 2 },
    { label: 'Titre de propriété ou délibération du conseil municipal', description: 'Pour les communes : délibération autorisant les travaux et le dépôt de la demande. Pour les privés : titre de propriété.', obligatoire: true, categorie: 'administratif', ordre: 3 },
    { label: 'Programme détaillé des travaux', description: 'Description technique des travaux envisagés, établie par un architecte du patrimoine ou un ACMH.', obligatoire: true, categorie: 'technique', ordre: 4 },
    { label: 'Devis détaillé des entreprises', description: 'Devis détaillé (hors taxes pour les communes) des entreprises pressenties pour les travaux.', obligatoire: true, categorie: 'financier', ordre: 5 },
    { label: 'Plan de financement prévisionnel', description: 'Tableau récapitulatif de toutes les sources de financement envisagées (État, Région, Département, autofinancement).', obligatoire: true, categorie: 'financier', ordre: 6 },
    { label: 'Photos de l\'état actuel', description: 'Reportage photographique montrant l\'état actuel du monument et les dégradations justifiant les travaux.', obligatoire: true, categorie: 'photographique', ordre: 7 },
    { label: 'Plan de situation', description: 'Plan de localisation du monument dans la commune.', obligatoire: true, categorie: 'technique', ordre: 8 },
    { label: 'Avis de l\'ABF', description: 'Avis de l\'Architecte des Bâtiments de France. Obligatoire pour les MH inscrits.', obligatoire: true, categorie: 'technique', ordre: 9 },
    { label: 'Note historique', description: 'Courte notice historique du monument (peut être extraite de la base Mérimée).', obligatoire: false, categorie: 'technique', ordre: 10 },
  ],
  fip: [
    { label: 'Formulaire de demande FIP', description: 'Formulaire spécifique au Fonds Incitatif et Partenarial. Disponible auprès de la DRAC.', obligatoire: true, categorie: 'administratif', ordre: 1 },
    { label: 'Délibération du conseil municipal', description: 'Délibération autorisant les travaux, le plan de financement et le dépôt de la demande FIP.', obligatoire: true, categorie: 'administratif', ordre: 2 },
    { label: 'Justificatif de population', description: 'Attestation INSEE confirmant que la commune a moins de 10 000 habitants.', obligatoire: true, categorie: 'administratif', ordre: 3 },
    { label: 'Programme de travaux', description: 'Description technique des travaux, idéalement validée par la CRMH.', obligatoire: true, categorie: 'technique', ordre: 4 },
    { label: 'Devis détaillé HT', description: 'Devis détaillé hors taxes des travaux prévus.', obligatoire: true, categorie: 'financier', ordre: 5 },
    { label: 'Plan de financement avec co-financement régional', description: 'Le FIP exige une contrepartie régionale d\'au moins 15 %. Joindre l\'engagement de la Région.', obligatoire: true, categorie: 'financier', ordre: 6 },
    { label: 'Photos état actuel', description: 'Documentation photographique de l\'état du monument.', obligatoire: true, categorie: 'photographique', ordre: 7 },
    { label: 'Extrait cadastral', description: 'Plan cadastral de la parcelle.', obligatoire: true, categorie: 'administratif', ordre: 8 },
  ],
  fondation_label: [
    { label: 'Formulaire de demande de label', description: 'Formulaire disponible sur le site de la Fondation du Patrimoine ou auprès du délégué régional.', obligatoire: true, categorie: 'administratif', ordre: 1 },
    { label: 'Titre de propriété', description: 'Document prouvant la propriété du bien.', obligatoire: true, categorie: 'administratif', ordre: 2 },
    { label: 'Photos du bien', description: 'Photographies de l\'extérieur du bâtiment montrant son intérêt patrimonial.', obligatoire: true, categorie: 'photographique', ordre: 3 },
    { label: 'Description des travaux envisagés', description: 'Description des travaux de restauration prévus.', obligatoire: true, categorie: 'technique', ordre: 4 },
    { label: 'Devis estimatif', description: 'Estimation du coût des travaux (TTC pour les particuliers).', obligatoire: true, categorie: 'financier', ordre: 5 },
    { label: 'Avis de l\'ABF', description: 'Avis favorable de l\'Architecte des Bâtiments de France.', obligatoire: true, categorie: 'technique', ordre: 6 },
  ],
  region_subvention: [
    { label: 'Formulaire de demande régionale', description: 'Formulaire spécifique de la Région. Téléchargeable sur le site du Conseil Régional.', obligatoire: true, categorie: 'administratif', ordre: 1 },
    { label: 'Pièce d\'identité ou délibération', description: 'Pour les privés : pièce d\'identité. Pour les communes : délibération du conseil municipal.', obligatoire: true, categorie: 'administratif', ordre: 2 },
    { label: 'Extrait cadastral', description: 'Plan cadastral de la parcelle du monument.', obligatoire: true, categorie: 'administratif', ordre: 3 },
    { label: 'Programme de travaux', description: 'Description détaillée des travaux envisagés.', obligatoire: true, categorie: 'technique', ordre: 4 },
    { label: 'Devis détaillé', description: 'Devis des entreprises pour les travaux prévus.', obligatoire: true, categorie: 'financier', ordre: 5 },
    { label: 'Plan de financement', description: 'Tableau des financements (État, Région, Département, autofinancement).', obligatoire: true, categorie: 'financier', ordre: 6 },
    { label: 'Photos état actuel', description: 'Documentation photographique.', obligatoire: true, categorie: 'photographique', ordre: 7 },
    { label: 'RIB', description: 'Relevé d\'identité bancaire pour le versement de la subvention.', obligatoire: true, categorie: 'administratif', ordre: 8 },
    { label: 'Attestation URSSAF', description: 'Attestation de régularité URSSAF de moins de 6 mois (pour les communes).', obligatoire: true, categorie: 'administratif', ordre: 9 },
  ],
  departement_subvention: [
    { label: 'Formulaire de demande départementale', description: 'Formulaire du Conseil Départemental. Généralement plus simple que les dossiers régionaux.', obligatoire: true, categorie: 'administratif', ordre: 1 },
    { label: 'Titre de propriété ou délibération', description: 'Justificatif de propriété du monument.', obligatoire: true, categorie: 'administratif', ordre: 2 },
    { label: 'Devis des travaux', description: 'Devis des travaux envisagés.', obligatoire: true, categorie: 'financier', ordre: 3 },
    { label: 'Photos du monument', description: 'Photos de l\'état actuel.', obligatoire: true, categorie: 'photographique', ordre: 4 },
    { label: 'Plan de financement', description: 'Récapitulatif des sources de financement.', obligatoire: true, categorie: 'financier', ordre: 5 },
  ],
};
