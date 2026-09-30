import type { ID, ProtectionLevel, OwnershipType, Region } from './common.types';
import type { Offre } from '@/lib/offres';
import type { TypeEdifice } from '@/constants/monument-options';

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

  /**
   * Posé sur un monument relu depuis le cache local (cf. stores/persistance),
   * jamais sur une réponse du serveur. Un tel monument n'a ni `offre`, ni
   * `myRole`, ni `members` — le cache ne les garde pas — et ces absences ne
   * veulent donc rien dire : ce n'est pas « offre gratuite » ni « accès
   * restreint », c'est « pas encore connu ». Disparaît dès que le serveur
   * répond, puisque sa ligne remplace celle du cache.
   */
  depuisLeCache?: true;

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
  /**
   * Un ou plusieurs propriétaires (choix multiple, migration 20260930084241) :
   * une aide est proposée dès qu'UN d'eux peut la déposer. Lire par
   * `proprietairesCoches` (lib/fiche-monument), qui accepte aussi la chaîne
   * seule d'un cache ou d'un brouillon d'avant.
   */
  proprietaire: OwnershipType[];

  // Step 3: Physical Description
  siecleConstruction?: string;
  descriptionGenerale?: string;

  /**
   * Natures du bien, en choix multiple (migrations 20260930072800 puis
   * 20260930082523), et leurs deux précisions. Le moteur en déduit, à
   * l'unanimité des types cochés, les réponses aux questions sur la nature de
   * l'édifice, qui ne sont alors plus posées. `null` EFFACE la valeur en base sur un PATCH
   * (`undefined` n'envoie rien). Les précisions n'ont de sens que pour certains
   * types (`TYPES_AVEC_AFFECTATION_CULTE`, `TYPES_AVEC_ARCHITECTURE_ROMANE`).
   */
  typeEdifice?: TypeEdifice[] | null;
  /** Édifice religieux toujours affecté au culte (true) ou désaffecté (false). */
  affecteAuCulte?: boolean | null;
  /** Architecture romane, en tout ou en partie (true), ou non (false). */
  architectureRomane?: boolean | null;

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

/**
 * Le monument tel qu'on le SAISIT : la fiche sans ce que le serveur y ajoute
 * (identifiant, propriétaire, dates, complétion, photos).
 *
 * Nommé plutôt qu'inline dans `monument.service.ts` parce que le parcours
 * découverte le garde en brouillon `localStorage` AVANT toute inscription, et
 * le rejoue tel quel sur `POST /monuments` après. Un type nommé, c'est la
 * garantie que ce qui a été mis de côté est exactement ce que la création
 * attend.
 */
export type MonumentInput = Omit<
  Monument,
  'id' | 'userId' | 'createdAt' | 'updatedAt' | 'completionPercentage' | 'photos'
>;

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
