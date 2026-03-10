import type { Aide } from '@/types';

export const mockAides: Aide[] = [
  // =========================================================================
  // SUBVENTIONS DRAC
  // =========================================================================
  {
    id: 'aide-1',
    nom: 'Subvention DRAC — Travaux sur monuments historiques classés',
    nomCourt: 'DRAC MH Classé',
    description: 'Subvention de l\'État pour la restauration des monuments historiques classés, versée par la Direction Régionale des Affaires Culturelles.',
    descriptionLongue: 'La DRAC peut accorder des subventions pour les travaux d\'entretien, de réparation et de restauration des monuments historiques classés n\'appartenant pas à l\'État. Le taux de base est d\'environ 40 % du montant HT des travaux. Les travaux doivent être réalisés sous le contrôle scientifique et technique de la DRAC et ne doivent pas avoir commencé avant l\'accord de subvention. Les lots techniques courants (électricité, plomberie, chauffage) sont exclus sauf s\'ils relèvent de la sécurité incendie.',
    categorie: 'etat_drac',
    type: 'subvention',
    organisme: 'Direction Régionale des Affaires Culturelles (DRAC)',
    montantMax: undefined,
    tauxMax: 50,
    plancher: 3000,
    criteres: {
      protectionRequise: ['classe'],
      // PDF: tout propriétaire d'un MH peut déposer, SAUF l'État
      proprietaireEligible: ['public_commune', 'public_departement', 'public_region', 'prive_personne_physique', 'prive_sci', 'association'],
      // PDF: entretien, réparation, restauration — exclut électricité, plomberie, chauffage, accessibilité
      travauxEligibles: ['toiture', 'charpente', 'maconnerie', 'vitraux', 'peintures_murales', 'menuiserie', 'facade', 'restauration_generale', 'mise_en_securite', 'couverture', 'etude_prealable'],
      architecteRequis: true,
    },
    demarcheDescription: '1. Contacter la CRMH de votre DRAC pour un rendez-vous préalable\n2. Constituer le dossier avec le formulaire CERFA de demande de subvention\n3. Joindre le programme de travaux établi par un architecte du patrimoine\n4. Déposer le dossier auprès de la DRAC de votre région\n5. Attendre l\'instruction (3 à 6 mois) et la notification de la décision',
    documentsRequis: ['Formulaire CERFA de demande de subvention', 'Extrait cadastral', 'Titre de propriété ou délibération du conseil municipal', 'Programme détaillé des travaux', 'Devis détaillé des entreprises (HT)', 'Plan de financement prévisionnel', 'Photos de l\'état actuel', 'Plan de situation', 'Avis de l\'ABF'],
    delaiInstruction: '3 à 6 mois',
    permanent: true,
    tags: ['restauration', 'état', 'monument classé'],
    baseTTC: false,
  },
  {
    id: 'aide-2',
    nom: 'Subvention DRAC — Travaux sur monuments historiques inscrits',
    nomCourt: 'DRAC MH Inscrit',
    description: 'Subvention de l\'État pour la restauration des monuments historiques inscrits, avec un taux de base d\'environ 20 %.',
    descriptionLongue: 'Les monuments historiques inscrits peuvent bénéficier de subventions de la DRAC pour leurs travaux de restauration. Le taux de base avoisine 20 % du montant des travaux éligibles. Comme pour les classés, les travaux ne doivent pas avoir commencé avant l\'accord et doivent être réalisés sous contrôle de la DRAC. Les lots techniques courants sont exclus.',
    categorie: 'etat_drac',
    type: 'subvention',
    organisme: 'Direction Régionale des Affaires Culturelles (DRAC)',
    tauxMax: 40,
    criteres: {
      protectionRequise: ['inscrit'],
      proprietaireEligible: ['public_commune', 'public_departement', 'public_region', 'prive_personne_physique', 'prive_sci', 'association'],
      travauxEligibles: ['toiture', 'charpente', 'maconnerie', 'vitraux', 'peintures_murales', 'menuiserie', 'facade', 'restauration_generale', 'mise_en_securite', 'couverture', 'etude_prealable'],
      architecteRequis: true,
    },
    demarcheDescription: '1. Prendre contact avec la CRMH de votre DRAC\n2. Constituer le dossier avec le formulaire CERFA\n3. Joindre les devis et le programme de travaux\n4. Déposer auprès de la DRAC\n5. Attendre l\'instruction et la notification',
    documentsRequis: ['Formulaire CERFA', 'Extrait cadastral', 'Titre de propriété ou délibération', 'Programme des travaux', 'Devis détaillé', 'Plan de financement', 'Photos état actuel', 'Avis ABF'],
    delaiInstruction: '3 à 6 mois',
    permanent: true,
    tags: ['restauration', 'état', 'monument inscrit'],
    baseTTC: false,
  },
  {
    id: 'aide-3',
    nom: 'Subvention DRAC — Études préalables',
    nomCourt: 'DRAC Études',
    description: 'Aide au financement des études préalables (diagnostics, études architecturales) sur les monuments historiques, jusqu\'à 60 % du coût.',
    descriptionLongue: 'Avant d\'engager des travaux de restauration, une étude préalable est souvent indispensable. La DRAC peut financer jusqu\'à 60 % du coût de ces études : diagnostic structurel, étude sanitaire, étude historique, relevé architectural. Cette aide est cruciale car elle conditionne souvent l\'obtention des subventions de travaux.',
    categorie: 'etat_drac',
    type: 'subvention',
    organisme: 'Direction Régionale des Affaires Culturelles (DRAC)',
    tauxMax: 60,
    criteres: {
      protectionRequise: ['classe', 'inscrit'],
      proprietaireEligible: ['public_commune', 'public_departement', 'public_region', 'prive_personne_physique', 'prive_sci', 'association'],
      travauxEligibles: ['etude_prealable'],
    },
    demarcheDescription: '1. Contacter la CRMH pour valider le besoin d\'étude\n2. Obtenir un devis d\'un architecte du patrimoine ou d\'un bureau d\'études\n3. Déposer la demande auprès de la DRAC\n4. L\'étude ne doit pas avoir commencé avant l\'accord',
    documentsRequis: ['Lettre de demande', 'Devis de l\'étude', 'Justificatif de propriété', 'Photos du monument', 'Description du besoin'],
    delaiInstruction: '2 à 4 mois',
    permanent: true,
    tags: ['étude', 'diagnostic', 'état'],
    baseTTC: false,
  },

  // =========================================================================
  // FIP — PDF: communes ≤ 2 000 hab, MH classé ou inscrit, état de péril
  // =========================================================================
  {
    id: 'aide-4',
    nom: 'Fonds Incitatif et Partenarial (FIP)',
    nomCourt: 'FIP',
    description: 'Aide majorée de l\'État pour les communes de moins de 2 000 habitants possédant un monument historique en péril, avec contrepartie régionale obligatoire.',
    descriptionLongue: 'Le FIP est un dispositif national géré par les DRAC, reposant sur le principe des financements croisés. Il s\'adresse aux petites communes (≤ 2 000 hab.) possédant un monument classé ou inscrit en état de péril ou présentant des besoins sanitaires structurels. Le Conseil régional doit s\'engager à hauteur d\'au moins 15 % du coût global. Le patrimoine privé peut aussi en bénéficier si le monument est situé dans une commune de moins de 2 000 hab. et que la restauration participe à l\'attractivité du territoire.',
    categorie: 'etat_drac',
    type: 'subvention',
    organisme: 'État (via DRAC) + Région',
    tauxMax: 80,
    criteres: {
      protectionRequise: ['classe', 'inscrit'],
      proprietaireEligible: ['public_commune'],
      segmentEligible: ['commune'],
      communeMaxPopulation: 2000,
      communeDeMoins10000Hab: true,
      cofinancementRequis: true,
      etatConservationRequis: ['mauvais', 'peril'],
      travauxEligibles: ['toiture', 'charpente', 'maconnerie', 'vitraux', 'peintures_murales', 'restauration_generale', 'mise_en_securite', 'facade', 'couverture'],
    },
    demarcheDescription: '1. Vérifier l\'éligibilité auprès de la DRAC (commune ≤ 2 000 hab.)\n2. S\'assurer de la contrepartie régionale (15 % minimum)\n3. Constituer le dossier FIP spécifique\n4. Déposer auprès de la DRAC avec copie à la Région',
    documentsRequis: ['Formulaire FIP', 'Délibération du conseil municipal', 'Justificatif de population INSEE', 'Programme de travaux', 'Devis détaillé HT', 'Plan de financement avec engagement régional', 'Photos état actuel', 'Extrait cadastral'],
    delaiInstruction: '4 à 8 mois',
    permanent: true,
    tags: ['commune rurale', 'état', 'monument historique', 'co-financement', 'péril'],
    baseTTC: false,
  },

  // =========================================================================
  // LABEL FONDATION DU PATRIMOINE
  // PDF: patrimoine non protégé rural (<20k hab) ou en SPR, visible de la voie publique,
  // travaux extérieurs uniquement, validé par ABF
  // =========================================================================
  {
    id: 'aide-5',
    nom: 'Label Fondation du Patrimoine',
    nomCourt: 'Label FdP',
    description: 'Label fiscal permettant aux propriétaires privés de déduire de 50 à 100 % des travaux extérieurs de restauration de leur bien patrimonial non protégé.',
    descriptionLongue: 'Le Label Fondation du Patrimoine est un outil fiscal pour les propriétaires privés de patrimoine non protégé (ou en SPR). Il permet de déduire de 50 à 100 % du montant des travaux extérieurs éligibles. Le label est accordé pour 3 ans. Conditions : le bien doit être en zone rurale (commune < 20 000 hab.) ou en SPR, être visible depuis la voie publique, et les travaux doivent concerner uniquement l\'extérieur (façade, toiture, menuiseries). Le programme de travaux doit être validé par l\'ABF.',
    categorie: 'fondation_patrimoine',
    type: 'label',
    organisme: 'Fondation du Patrimoine',
    criteres: {
      protectionRequise: ['non_protege', 'spr'],
      proprietaireEligible: ['prive_personne_physique', 'prive_sci'],
      segmentEligible: ['prive'],
      // PDF: travaux extérieurs uniquement
      travauxEligibles: ['toiture', 'charpente', 'maconnerie', 'facade', 'menuiserie', 'couverture'],
      criteresSupplementaires: [
        { label: 'Visibilité depuis la voie publique', description: 'Le bien doit être visible depuis la voie publique ou le propriétaire doit s\'engager à le rendre accessible.' },
        { label: 'Zone rurale ou SPR', description: 'Le bien doit être situé en zone rurale (commune < 20 000 hab.) ou au sein d\'un Site Patrimonial Remarquable (SPR).' },
        { label: 'Travaux extérieurs uniquement', description: 'Seuls les travaux extérieurs (façade, toiture, menuiseries) sont éligibles. Les travaux intérieurs sont exclus.' },
      ],
    },
    demarcheDescription: '1. Contacter le délégué régional de la Fondation du Patrimoine\n2. Obtenir un avis favorable de l\'ABF\n3. Déposer le dossier de demande de label\n4. Présentation en commission régionale\n5. Attribution du label (durée 3 ans)',
    documentsRequis: ['Formulaire de demande de label', 'Titre de propriété', 'Photos extérieures du bien', 'Description des travaux extérieurs envisagés', 'Devis estimatif TTC', 'Avis de l\'ABF'],
    delaiInstruction: '2 à 3 mois',
    permanent: true,
    tags: ['fiscal', 'privé', 'fondation', 'non protégé'],
    baseTTC: true,
  },

  // =========================================================================
  // SOUSCRIPTION PUBLIQUE — Fondation du Patrimoine
  // Pas de critères de protection stricts, ouvert largement
  // =========================================================================
  {
    id: 'aide-6',
    nom: 'Souscription publique — Fondation du Patrimoine',
    nomCourt: 'Souscription FdP',
    description: 'Collecte de dons publics organisée par la Fondation du Patrimoine pour financer la restauration d\'un monument.',
    descriptionLongue: 'La Fondation du Patrimoine peut organiser une souscription publique pour financer les travaux de restauration. Les dons des particuliers ouvrent droit à une réduction d\'impôt de 66 % et ceux des entreprises à 60 %. La Fondation verse ensuite les fonds collectés au propriétaire. Ce dispositif est particulièrement efficace pour les projets ayant une forte dimension locale et communautaire.',
    categorie: 'fondation_patrimoine',
    type: 'souscription',
    organisme: 'Fondation du Patrimoine',
    criteres: {
      proprietaireEligible: ['public_commune', 'public_departement', 'prive_personne_physique', 'prive_sci', 'association'],
      travauxEligibles: ['toiture', 'charpente', 'maconnerie', 'vitraux', 'peintures_murales', 'facade', 'restauration_generale', 'couverture'],
    },
    demarcheDescription: '1. Contacter la délégation régionale de la Fondation du Patrimoine\n2. Présenter le projet de restauration\n3. La Fondation évalue l\'intérêt patrimonial et le potentiel de collecte\n4. Signature d\'une convention de souscription\n5. Lancement de la campagne de dons',
    documentsRequis: ['Dossier de présentation du projet', 'Photos du monument', 'Devis des travaux', 'Plan de financement', 'Justificatif de propriété'],
    delaiInstruction: '1 à 2 mois',
    permanent: true,
    tags: ['dons', 'collecte', 'fondation', 'fiscal'],
    baseTTC: false,
  },

  // =========================================================================
  // AIDES RÉGIONALES
  // =========================================================================
  {
    id: 'aide-7',
    nom: 'Subvention du Conseil Régional de Normandie — Patrimoine',
    nomCourt: 'Région Normandie',
    description: 'Aide régionale pour la restauration du patrimoine bâti en Normandie, protégé ou non protégé.',
    descriptionLongue: 'Le Conseil Régional de Normandie soutient la restauration du patrimoine bâti à travers un programme dédié. Les subventions peuvent couvrir jusqu\'à 30 % du coût des travaux pour les monuments protégés et jusqu\'à 20 % pour le patrimoine non protégé présentant un intérêt architectural.',
    categorie: 'region',
    type: 'subvention',
    organisme: 'Conseil Régional de Normandie',
    tauxMax: 30,
    montantMax: 100000,
    criteres: {
      regionEligible: ['normandie'],
      proprietaireEligible: ['public_commune', 'public_departement', 'prive_personne_physique', 'prive_sci', 'association'],
      travauxEligibles: ['toiture', 'charpente', 'maconnerie', 'vitraux', 'facade', 'restauration_generale', 'couverture', 'menuiserie'],
    },
    demarcheDescription: '1. Télécharger le formulaire sur le site du Conseil Régional\n2. Constituer le dossier complet\n3. Déposer en ligne ou par courrier\n4. Instruction par les services de la Région\n5. Passage en commission permanente',
    documentsRequis: ['Formulaire régional', 'Délibération ou titre de propriété', 'Extrait cadastral', 'Programme de travaux', 'Devis détaillé', 'Plan de financement', 'Photos état actuel', 'RIB', 'Attestation URSSAF'],
    delaiInstruction: '3 à 6 mois',
    permanent: true,
    tags: ['région', 'normandie', 'restauration'],
    baseTTC: false,
  },
  {
    id: 'aide-8',
    nom: 'Subvention du Conseil Régional Auvergne-Rhône-Alpes — Patrimoine',
    nomCourt: 'Région AURA',
    description: 'Programme régional de soutien à la restauration du patrimoine monumental en Auvergne-Rhône-Alpes.',
    descriptionLongue: 'La Région Auvergne-Rhône-Alpes dispose d\'un fonds régional dédié à la restauration du patrimoine. Sont éligibles les monuments protégés (classés ou inscrits) et le patrimoine non protégé présentant un intérêt architectural reconnu.',
    categorie: 'region',
    type: 'subvention',
    organisme: 'Conseil Régional Auvergne-Rhône-Alpes',
    tauxMax: 25,
    montantMax: 80000,
    criteres: {
      regionEligible: ['auvergne-rhone-alpes'],
      proprietaireEligible: ['public_commune', 'public_departement', 'prive_personne_physique', 'prive_sci', 'association'],
      travauxEligibles: ['toiture', 'charpente', 'maconnerie', 'vitraux', 'facade', 'restauration_generale', 'couverture'],
    },
    demarcheDescription: '1. Déposer la demande en ligne sur la plateforme de la Région\n2. Joindre tous les justificatifs requis\n3. Instruction par les services patrimoine de la Région',
    documentsRequis: ['Formulaire régional', 'Justificatif de propriété', 'Extrait cadastral', 'Devis', 'Plan de financement', 'Photos', 'RIB'],
    delaiInstruction: '3 à 6 mois',
    permanent: true,
    tags: ['région', 'auvergne-rhône-alpes', 'restauration'],
    baseTTC: false,
  },
  {
    id: 'aide-9',
    nom: 'Subvention du Conseil Régional Centre-Val de Loire — Patrimoine',
    nomCourt: 'Région CVL',
    description: 'Aide régionale pour la sauvegarde et la restauration du patrimoine en Centre-Val de Loire.',
    descriptionLongue: 'Le Centre-Val de Loire, riche de ses châteaux de la Loire et de son patrimoine religieux, propose un programme de soutien à la restauration pour les propriétaires publics et privés.',
    categorie: 'region',
    type: 'subvention',
    organisme: 'Conseil Régional Centre-Val de Loire',
    tauxMax: 20,
    montantMax: 60000,
    criteres: {
      regionEligible: ['centre-val-de-loire'],
      proprietaireEligible: ['public_commune', 'public_departement', 'prive_personne_physique', 'prive_sci', 'association'],
      travauxEligibles: ['toiture', 'charpente', 'maconnerie', 'vitraux', 'facade', 'restauration_generale', 'couverture'],
    },
    demarcheDescription: '1. Contacter le service patrimoine de la Région\n2. Constituer le dossier avec les pièces requises\n3. Déposer la demande',
    documentsRequis: ['Formulaire régional', 'Justificatif de propriété', 'Devis', 'Plan de financement', 'Photos', 'RIB'],
    delaiInstruction: '3 à 5 mois',
    permanent: true,
    tags: ['région', 'centre-val-de-loire', 'restauration'],
    baseTTC: false,
  },

  // =========================================================================
  // AIDES DÉPARTEMENTALES
  // =========================================================================
  {
    id: 'aide-10',
    nom: 'Aide du Conseil Départemental de la Manche',
    nomCourt: 'Département Manche',
    description: 'Subvention départementale pour le patrimoine dans la Manche.',
    descriptionLongue: 'Le Conseil Départemental de la Manche propose des aides pour la restauration du patrimoine protégé et non protégé. Les dossiers sont plus simples que les dossiers régionaux.',
    categorie: 'departement',
    type: 'subvention',
    organisme: 'Conseil Départemental de la Manche',
    tauxMax: 15,
    montantMax: 30000,
    dateLimite: '2026-03-12',
    permanent: false,
    criteres: {
      departementEligible: ['50'],
      proprietaireEligible: ['public_commune', 'prive_personne_physique', 'prive_sci', 'association'],
      travauxEligibles: ['toiture', 'charpente', 'maconnerie', 'facade', 'restauration_generale', 'couverture', 'menuiserie'],
    },
    demarcheDescription: '1. Télécharger le formulaire départemental\n2. Joindre les pièces demandées\n3. Envoyer par courrier ou déposer en ligne',
    documentsRequis: ['Formulaire départemental', 'Justificatif de propriété', 'Devis', 'Photos', 'Plan de financement'],
    delaiInstruction: '1 à 2 mois',
    tags: ['département', 'manche', 'normandie'],
    baseTTC: false,
  },
  {
    id: 'aide-11',
    nom: 'Aide du Conseil Départemental d\'Indre-et-Loire',
    nomCourt: 'Département 37',
    description: 'Programme départemental de soutien au patrimoine en Indre-et-Loire.',
    descriptionLongue: 'L\'Indre-et-Loire, département riche en châteaux et patrimoine religieux, propose des aides aux propriétaires pour la restauration de leurs monuments.',
    categorie: 'departement',
    type: 'subvention',
    organisme: 'Conseil Départemental d\'Indre-et-Loire',
    tauxMax: 10,
    montantMax: 20000,
    permanent: true,
    criteres: {
      departementEligible: ['37'],
      proprietaireEligible: ['public_commune', 'prive_personne_physique', 'prive_sci', 'association'],
      travauxEligibles: ['toiture', 'charpente', 'maconnerie', 'facade', 'restauration_generale', 'couverture'],
    },
    demarcheDescription: '1. Contacter le service patrimoine du Département\n2. Déposer le dossier de demande',
    documentsRequis: ['Formulaire départemental', 'Justificatif de propriété', 'Devis', 'Photos'],
    delaiInstruction: '2 à 3 mois',
    tags: ['département', 'indre-et-loire', 'centre-val-de-loire'],
    baseTTC: false,
  },

  // =========================================================================
  // DÉDUCTION FISCALE MH
  // PDF: classé ou inscrit, propriétaire privé personne physique (ou SCI familiale
  // non soumise à l'IS), conservation 15 ans, 100% déductible sans plafond
  // =========================================================================
  {
    id: 'aide-12',
    nom: 'Déduction fiscale au titre des monuments historiques (Loi MH)',
    nomCourt: 'Défiscalisation MH',
    description: 'Déduction de 100 % des charges de restauration et d\'entretien du revenu global imposable, sans plafond.',
    descriptionLongue: 'Le régime fiscal des Monuments Historiques permet aux propriétaires privés de monuments classés ou inscrits de déduire 100 % des charges foncières (travaux, entretien, intérêts d\'emprunt) directement de leur revenu global imposable, sans aucun plafond. Ce dispositif est totalement exclu du plafonnement global des niches fiscales (10 000 €). Conditions strictes : le propriétaire doit détenir le bien en direct (ou via une SCI familiale transparente non soumise à l\'IS), s\'engager à conserver la propriété pendant 15 ans minimum, et les travaux doivent être validés par la DRAC/UDAP.',
    categorie: 'fiscalite',
    type: 'deduction_fiscale',
    organisme: 'Direction Générale des Finances Publiques',
    criteres: {
      protectionRequise: ['classe', 'inscrit'],
      segmentEligible: ['prive'],
      proprietaireEligible: ['prive_personne_physique', 'prive_sci'],
      criteresSupplementaires: [
        { label: 'Conservation 15 ans minimum', description: 'Engagement écrit de conserver la propriété pendant au moins 15 ans à compter de l\'acquisition.' },
        { label: 'Détention en direct ou SCI familiale', description: 'Le bien doit être détenu en direct ou via une SCI familiale transparente (non soumise à l\'IS). La propriété démembrée est exclue sauf SCI familiale.' },
        { label: 'Travaux validés par la DRAC', description: 'Les travaux doivent consister en une véritable restauration ou entretien, validés par les services de l\'État (DRAC/UDAP).' },
      ],
    },
    demarcheDescription: '1. S\'assurer que le monument est classé ou inscrit MH\n2. Vérifier le mode de détention (direct ou SCI familiale non IS)\n3. Conserver tous les justificatifs de dépenses\n4. Déclarer les charges dans la déclaration de revenus (formulaire 2044 spécial)',
    documentsRequis: ['Arrêté de classement ou inscription', 'Factures des travaux', 'Relevé des charges foncières', 'Déclaration de revenus fonciers 2044', 'Attestation de détention depuis 15 ans (si revente)'],
    delaiInstruction: 'Annuel (déclaration fiscale)',
    permanent: true,
    tags: ['fiscal', 'privé', 'déduction', 'sans plafond'],
    baseTTC: true,
  },

  // =========================================================================
  // AIDE SPR / ABORDS
  // PDF: immeuble non protégé MH situé en SPR ou dans le périmètre des abords
  // d'un MH classé/inscrit, ~15 % du montant des travaux
  // =========================================================================
  {
    id: 'aide-16',
    nom: 'Aide aux travaux en Site Patrimonial Remarquable et Abords',
    nomCourt: 'Aide SPR/Abords',
    description: 'Subvention de l\'État pour la restauration d\'immeubles non protégés situés en SPR ou dans le périmètre des abords d\'un monument historique.',
    descriptionLongue: 'Le ministère de la Culture soutient la restauration d\'immeubles non protégés au titre des MH mais situés dans un environnement urbain ou paysager protégé (SPR avec PSMV/PVAP, ou périmètre des abords d\'un MH classé/inscrit). Le taux moyen est d\'environ 15 % du montant des travaux. Ce dispositif vise les travaux présentant une technicité particulière nécessitant le recours à des savoir-faire artisanaux rares.',
    categorie: 'etat_drac',
    type: 'subvention',
    organisme: 'Ministère de la Culture (via DRAC)',
    tauxMax: 15,
    criteres: {
      protectionRequise: ['spr', 'abords'],
      proprietaireEligible: ['prive_personne_physique', 'prive_sci', 'association', 'public_commune', 'public_departement'],
      travauxEligibles: ['toiture', 'charpente', 'maconnerie', 'facade', 'menuiserie', 'couverture', 'restauration_generale'],
    },
    demarcheDescription: '1. Vérifier que l\'immeuble est bien situé en SPR ou périmètre des abords\n2. Contacter la DRAC pour évaluer l\'éligibilité\n3. Constituer le dossier avec programme de travaux\n4. Ne pas commencer les travaux avant réception de la demande',
    documentsRequis: ['Justificatif de situation en SPR ou abords', 'Programme de travaux', 'Devis détaillé', 'Photos', 'Plan de financement'],
    delaiInstruction: '3 à 6 mois',
    permanent: true,
    tags: ['SPR', 'abords', 'non protégé', 'patrimoine urbain'],
    baseTTC: false,
  },

  // =========================================================================
  // MÉCÉNAT D'ENTREPRISE
  // =========================================================================
  {
    id: 'aide-13',
    nom: 'Mécénat d\'entreprise pour le patrimoine',
    nomCourt: 'Mécénat',
    description: 'Les entreprises peuvent financer la restauration de monuments et bénéficier d\'une réduction d\'impôt de 60 % du montant du don.',
    descriptionLongue: 'Le mécénat d\'entreprise est un levier de financement puissant pour la restauration du patrimoine. Les dons des entreprises ouvrent droit à une réduction d\'impôt sur les sociétés de 60 % dans la limite de 0,5 % du chiffre d\'affaires. Les fonds privés (mécénat) ne sont pas comptés dans le plafond de 80 % des aides publiques.',
    categorie: 'mecenat',
    type: 'mecenat',
    organisme: 'Entreprises mécènes',
    criteres: {
      proprietaireEligible: ['public_commune', 'public_departement', 'prive_personne_physique', 'prive_sci', 'association'],
      criteresSupplementaires: [
        { label: 'Projet d\'intérêt général', description: 'Le projet doit présenter un intérêt général (patrimoine, culture, éducation).' },
      ],
    },
    demarcheDescription: '1. Identifier des entreprises locales ou nationales intéressées par le patrimoine\n2. Préparer un dossier de mécénat (projet, budget, contreparties)\n3. Signer une convention de mécénat\n4. L\'entreprise verse le don et reçoit un reçu fiscal',
    documentsRequis: ['Dossier de présentation du projet', 'Budget prévisionnel', 'Plan de contreparties', 'Convention de mécénat'],
    delaiInstruction: 'Variable',
    permanent: true,
    tags: ['entreprise', 'mécénat', 'RSE', 'fiscal'],
    baseTTC: false,
  },

  // =========================================================================
  // LOTO DU PATRIMOINE
  // PDF: monument en péril (mauvais/peril), intérêt patrimonial, projet mature
  // Tous types de protection, tous propriétaires
  // =========================================================================
  {
    id: 'aide-14',
    nom: 'Loto du Patrimoine — Mission Patrimoine',
    nomCourt: 'Loto du Patrimoine',
    description: 'Programme national de la Fondation du Patrimoine financé par le Loto. Cible les monuments en péril avec un projet de restauration mature.',
    descriptionLongue: 'La Mission Patrimoine portée par Stéphane Bern sélectionne chaque année environ 100 sites en péril. Les critères sont stricts : l\'édifice doit être en état de péril avéré (risque d\'effondrement, dégradation irréversible), présenter un intérêt patrimonial significatif, disposer d\'un projet opérationnel à court terme (études préalables, devis, plan de financement bouclé), et démontrer un impact territorial (tourisme, lien social, réemploi). Tous les types de patrimoine sont éligibles, protégés ou non.',
    categorie: 'autre',
    type: 'subvention',
    organisme: 'Fondation du Patrimoine / Mission Patrimoine',
    montantMax: 500000,
    dateLimite: '2026-04-30',
    permanent: false,
    criteres: {
      // PDF: pas de restriction de protection, mais péril requis
      proprietaireEligible: ['public_commune', 'public_departement', 'prive_personne_physique', 'prive_sci', 'association'],
      etatConservationRequis: ['mauvais', 'peril'],
      criteresSupplementaires: [
        { label: 'Projet opérationnel', description: 'Le projet doit être prêt à démarrer : études techniques, autorisations, plan de financement bouclé, devis existants.' },
        { label: 'Impact territorial', description: 'Potentiel de développement touristique, création de lien social, réutilisation pour de nouveaux usages.' },
      ],
    },
    demarcheDescription: '1. Répondre à l\'appel à candidatures annuel (généralement ouvert en début d\'année)\n2. Constituer un dossier complet avec photos et descriptif du péril\n3. Sélection par une commission nationale\n4. Annonce des lauréats lors des Journées du Patrimoine',
    documentsRequis: ['Formulaire de candidature Mission Patrimoine', 'Photos montrant l\'état de péril', 'Descriptif historique et patrimonial', 'Estimation des travaux', 'Plan de financement', 'Autorisations d\'urbanisme'],
    delaiInstruction: '6 à 9 mois',
    tags: ['loto', 'mission patrimoine', 'péril', 'fondation'],
    baseTTC: false,
  },

  // =========================================================================
  // DETR — PDF: communes < 20 000 hab, tous patrimoines (y compris non protégé)
  // =========================================================================
  {
    id: 'aide-15',
    nom: 'Dotation d\'Équipement des Territoires Ruraux (DETR)',
    nomCourt: 'DETR',
    description: 'Dotation de l\'État pour les communes rurales (< 20 000 hab.), pouvant couvrir des travaux sur le patrimoine communal, y compris non protégé.',
    descriptionLongue: 'La DETR est une dotation d\'investissement de l\'État destinée aux communes de moins de 20 000 habitants et aux EPCI de moins de 75 000 habitants. La rénovation du patrimoine bâti communal (églises, bâtiments publics anciens) y figure parmi les priorités. Le taux varie de 20 à 50 % du montant des travaux. Ce dispositif est cumulable avec la DSIL et le Fonds Vert.',
    categorie: 'etat_drac',
    type: 'subvention',
    organisme: 'Préfecture (État)',
    tauxMax: 50,
    plancher: 15000,
    criteres: {
      segmentEligible: ['commune'],
      proprietaireEligible: ['public_commune'],
      communeMaxPopulation: 20000,
      communeDeMoins10000Hab: true,
    },
    demarcheDescription: '1. Déposer la demande auprès de la sous-préfecture ou préfecture\n2. La commission DETR examine les demandes\n3. Le préfet arrête la liste des subventions',
    documentsRequis: ['Formulaire DETR', 'Délibération du conseil municipal', 'Devis des travaux', 'Plan de financement', 'Fiche descriptive du projet'],
    delaiInstruction: '2 à 4 mois',
    dateLimite: '2026-03-31',
    permanent: false,
    tags: ['commune rurale', 'état', 'investissement', 'non protégé'],
    baseTTC: false,
  },
];
