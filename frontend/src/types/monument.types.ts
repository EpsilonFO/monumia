import type { ID, ProtectionLevel, OwnershipType, Region } from './common.types';
import type { Offre } from '@/lib/offres';

export interface Monument {
  id: ID;
  userId: ID;
  myRole?: import('./sharing.types').ProjectRole;
  members?: import('./sharing.types').MemberPreview[];
  memberCount?: number;

  /**
   * L'offre qui gouverne CE bien : celle de son propriétaire unie à celle de
   * l'appelant (cf. backend/services/quotas.py). C'est elle qui décide des
   * boutons de la fiche et de ses projets — pas l'offre du compte, sinon
   * l'architecte invité par un client abonné perdrait l'échéancier que son
   * client paye. Pour ce qui relève du COMPTE (second monument, tableau de
   * bord), lire `useOffre()`.
   *
   * Absente d'un monument construit localement avant le premier aller-retour
   * serveur : `useOffreMonument` retombe alors sur l'offre gratuite.
   */
  offre?: Offre;

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

  // Step 3: Physical Description
  siecleConstruction?: string;
  descriptionGenerale?: string;

  // État sanitaire — décrit le BIEN, pas un chantier : tous les projets du
  // monument le partagent. Absent tant que la question « le monument est-il en
  // péril ? » n'a pas été posée (la fiche est créée avant l'étape 2 du wizard).
  // On n'écrit plus que 'peril' ou 'bon' — 'moyen'/'mauvais' subsistent sur les
  // fiches antérieures, et `isEnPeril` les range du côté péril dès 'mauvais'.
  etatConservation?: 'bon' | 'moyen' | 'mauvais' | 'peril';

  // Step 5: Photos
  photos: MonumentPhoto[];

  // Metadata
  completionPercentage: number;
  createdAt: string;
  updatedAt: string;
}

export interface MonumentPhoto {
  id: ID;
  /** CHEMIN de stockage dans le bucket privé — jamais affichable tel quel. */
  url: string;
  /** Lien signé posé par le backend à la lecture : c'est lui qu'on affiche. */
  signedUrl?: string;
  legende: string;
  type: 'profil' | 'facade' | 'interieur' | 'detail' | 'aerien' | 'degradation' | 'autre';
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
