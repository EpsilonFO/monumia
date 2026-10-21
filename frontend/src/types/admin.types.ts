/**
 * Administration du catalogue (page `/admin`, réservée aux fondateurs).
 *
 * Miroir de `backend/services/catalogue_admin.py`. Le vocabulaire est celui du
 * produit : une aide est « retirée du catalogue » ou « republiée » (jamais
 * « masquée », qui désigne le paywall Veille, ni « non éligible », qui est un
 * verdict du moteur) ; une question est « surchargée » ou « rétablie ».
 */

import i18n from '@/i18n';

/** Une réponse possible à une question du QCM. */
export interface OptionSurchargee {
  /** Figé pour une réponse existante : les prédicats des aides le citent. */
  id: string;
  label: string;
  /** Réponse neutre (« je ne sais pas ») : n'écarte aucune aide. */
  unknown: boolean;
  /**
   * Questions Oui/Non seulement : la valeur de vérité envoyée aux prédicats des
   * aides. `null` = « ne tranche pas », la réponse n'écarte alors rien. Sur un
   * fait à choix, l'identifiant EST la valeur et le serveur refuse ce champ.
   */
  valeur?: boolean | null;
}

/** Ce qui est réellement stocké en base, c'est-à-dire ce qui DIFFÈRE du YAML. */
export interface SurchargeFait {
  question: string | null;
  help: string | null;
  /** Liste complète effective : elle remplace celle du YAML, elle ne s'y ajoute pas. */
  options: OptionSurchargee[] | null;
}

export interface AdminAide {
  slug: string;
  nom: string;
  organisme: string;
  categorie: string;
  regions: string[];
  /** Aide entièrement typée : les seules que le moteur déterministe traite. */
  engineReady: boolean;
  disponibilite: 'maintenant' | 'bientot';
  retiree: boolean;
  motif: string | null;
  retireeLe: string | null;
  /** Vrai pour une ligne de retrait dont l'aide a depuis quitté le corpus. */
  absenteDuCorpus?: boolean;
}

/** Une aide citée dans un impact. */
export interface AideCitee {
  slug: string;
  nom: string;
}

export interface ImpactOptions {
  factKey: string;
  parOption: {
    id: string;
    label: string;
    unknown: boolean;
    /** Valeur envoyée au moteur (questions Oui/Non). `null` = ne tranche pas. */
    valeur?: boolean | null;
    /** Aides qu'un utilisateur perd en choisissant cette réponse. */
    ecarte: AideCitee[];
  }[];
  /** Réponses d'origine absentes du brouillon, et ce qu'elles casseraient. */
  supprimees: {
    id: string;
    label: string;
    referenceePar: AideCitee[];
  }[];
}

export interface AdminFait {
  key: string;
  type: 'boolean' | 'integer' | 'number' | 'enum' | 'multi_enum';
  scope: 'monument' | 'projet' | 'proprietaire';
  /** Fait encore en attente de validation humaine (`facts_pending.yaml`). */
  pending: boolean;
  nbAides: number;
  /** Dépendance INTRINSÈQUE du fait (`pertinent_si` du YAML) : la question ne
   *  se pose que si cette autre réponse le permet. LECTURE SEULE — elle vaut
   *  pour toutes les aides à la fois, et relève de l'éditorial, pas de
   *  l'exploitation. `null` : la question se pose toujours. */
  pertinentSi: { fact: string; predicate: Record<string, unknown> } | null;
  original: {
    question: string;
    help: string | null;
    options: OptionSurchargee[];
  };
  surcharge: SurchargeFait | null;
  impactParOption: ImpactOptions;
}


// ---------------------------------------------------------------------------
// Prédicats de conditions
// ---------------------------------------------------------------------------

/** Les opérateurs que l'éditeur sait rendre. Pas de combinateur. `none_in`
 *  (exclusion stricte) ne vaut que sur un fait à choix multiple. */
export type OperateurPredicat = 'eq' | 'neq' | 'in' | 'not_in' | 'none_in';

/** États d'une surcharge de prédicat, miroir de `ETATS_PREDICAT`. */
export type EtatPredicat =
  | 'active'
  | 'a_revoir'
  | 'perimee_texte'
  | 'perimee_fait'
  | 'aide_absente'
  | 'condition_absente'
  | 'hors_mandat'
  | 'invalide';

/** Une surcharge de prédicat, confrontée au YAML d'aujourd'hui. */
export interface SurchargePredicat {
  etat: EtatPredicat;
  /** Raison lisible, à afficher telle quelle. */
  detail: string | null;
  /** `a_revoir` est appliquée AUSSI : l'ignorer re-casserait le correctif. */
  appliquee: boolean;
  predicate: Record<string, unknown>;
  predicateOrigine: Record<string, unknown>;
  /** Le prédicat du YAML aujourd'hui, pour l'afficher à côté du nouveau. */
  predicateYaml: Record<string, unknown> | null;
  /** Le texte au moment de la décision, et celui d'aujourd'hui. */
  conditionText: string;
  conditionTextActuel: string | null;
  factKey: string;
  motif: string | null;
}

/** Une condition modifiable, telle que le panneau l'affiche. */
export interface AdminCondition {
  aideSlug: string;
  aideNom: string;
  conditionId: string;
  /** Le texte de la condition — LECTURE SEULE : il vient de la source. */
  text: string;
  factKey: string;
  question: string | null;
  reponses: { id: string; label: string }[];
  /** Fait à choix multiple : les opérateurs s'y lisent case par case, et
   *  l'exclusion stricte `none_in` n'est proposée que là. */
  choixMultiple: boolean;
  /** Opérateur et valeurs SERVIS (surcharge comprise). */
  operateur: OperateurPredicat | '';
  valeurs: string[];
  engineReady: boolean;
  retiree: boolean;
  derogationPossible: boolean;
  surcharge: SurchargePredicat | null;
}

/** Une surcharge dont l'aide ou la condition a disparu : invisible ailleurs. */
export interface ConditionOrpheline {
  aideSlug: string;
  conditionId: string;
  surcharge: SurchargePredicat | null;
}

export interface InventaireConditions {
  conditions: AdminCondition[];
  orphelines: ConditionOrpheline[];
}

/** Ce que le nouveau prédicat change, réponse par réponse. */
export interface ImpactPredicat {
  aideSlug: string;
  conditionId: string;
  factKey: string;
  avant: Record<string, unknown>;
  apres: Record<string, unknown>;
  parReponse: {
    id: string;
    label: string;
    avantEcarte: boolean;
    apresEcarte: boolean;
    changement: boolean;
  }[];
  /** Ce qui rend l'impact honnête : dérogation, applies_if, autres gates… */
  avertissements: string[];
}

/** Ce que la route d'écriture rend : la ligne à jour, ou une entrée minimale
 *  quand la condition a quitté le mandat (rétablissement de nettoyage). */
export type AdminConditionCourante = AdminCondition | (ConditionOrpheline & { absenteDuMandat: true });

/* ───────────────────────── Le catalogue en chiffres ─────────────────────────
 *
 * Miroir de `backend/services/catalogue_stats.py`. Un `null` de chiffrage veut
 * dire « la source n'annonce rien », jamais « zéro » : la page l'écrit `n.c.`
 * et ne le fait entrer dans aucune moyenne.
 *
 * Les lignes classent par FINANCEUR, pas par périmètre : « les aides du
 * département de l'Isère » sont celles du Conseil départemental, pas celles
 * qui s'appliquent en Isère (qui sont aussi celles de la Région et de l'État).
 *
 * Les noms ne voyagent PAS dans les groupes : chaque groupe ne porte que des
 * slugs, et `StatistiquesCatalogue.aides` les résout. Une aide de fondation
 * ouverte à huit départements verrait sinon son nom recopié huit fois.
 */

/** Un groupe d'aides : son compte, ses slugs, son chiffrage. Les aides
 *  retirées du catalogue n'y sont ni comptées ni listées. */
export interface GroupeStats {
  nb: number;
  /** Déjà triés par nom, côté serveur : c'est l'ordre du dépliant. */
  slugs: string[];
  nbAvecTaux: number;
  tauxMin: number | null;
  tauxMax: number | null;
  tauxMedian: number | null;
  nbAvecMontant: number;
  montantMedian: number | null;
  montantMax: number | null;
}

/** Une région ou un département, et les aides de SA collectivité.
 *  `regionLabel` n'est posé que sur un département — c'est son rattachement. */
export interface StatsTerritoire extends GroupeStats {
  code: string;
  label: string;
  region?: string;
  regionLabel?: string;
}

/** Une catégorie de financeur ou un type de dispositif. */
export interface StatsNature extends GroupeStats {
  code: string;
  label: string;
}

/**
 * Les quatre échelons sont DISJOINTS et somment à `nb` : une aide tombe dans
 * exactement un seau, ce qui rend les quatre chiffres de tête additionnables.
 */
export interface StatsCorpus {
  /** Retirées comprises, contrairement à `nb`. */
  total: number;
  nb: number;
  retirees: number;
  /** Aucun filtre géographique : État, fiscalité, fondations nationales. */
  nationales: number;
  /** Financées par un Conseil régional, quel que soit leur périmètre. */
  regionales: number;
  /** Financées par un Conseil départemental. */
  departementales: number;
  /** Financeurs sans échelon territorial mais à périmètre local — fondations,
   *  Europe, mécénat. Sans ce seau, elles seraient soit invisibles, soit
   *  comptées comme des aides de Département, ce qu'elles ne sont pas. */
  autres: number;
}

/**
 * L'écart entre le corpus servi et `aides_v3`. Une aide absente de la table
 * est proposée par le diagnostic mais répond « Aide introuvable » à la
 * création de dossier : c'est une panne, pas une statistique.
 */
export interface StatsSynchronisation {
  /** Faux si la table n'a pas répondu : la page retire le bloc plutôt que de
   *  réclamer tout le catalogue. */
  lisible: boolean;
  enBase: number | null;
  nbManquantes: number;
  /** Tronquée côté serveur : `nbManquantes` fait foi. */
  manquantes: string[];
}

export interface StatistiquesCatalogue {
  genereLe: string;
  corpus: StatsCorpus;
  /** slug → nom de l'aide, pour tout le catalogue servi. */
  aides: Record<string, string>;
  national: GroupeStats;
  /** Les financeurs sans échelon territorial, à périmètre local. */
  autres: GroupeStats;
  regions: StatsTerritoire[];
  departements: StatsTerritoire[];
  categories: StatsNature[];
  types: StatsNature[];
  synchronisation: StatsSynchronisation;
}

/* ───────────────────────────── Les rôles de compte ──────────────────────────
 *
 * Miroir de `backend/services/roles.py`. À ne pas confondre avec les rôles
 * d'ÉQUIPE (`co_owner` / `member`, propres à un monument ou un projet) : ceux-ci
 * portent sur le compte entier.
 *
 * Un seul des deux est un droit d'administration — `admin` ouvre `/admin`,
 * `beta_testeur` n'ouvre que l'offre. C'est toute la raison d'en avoir deux :
 * donner l'offre sans donner le catalogue.
 */

export type RoleCompte = 'admin' | 'beta_testeur';

/** Comment chaque rôle se dit dans l'interface. Le serveur a le sien, pour ses
 *  messages d'erreur et ses journaux. */
export const LIBELLE_ROLE: Record<RoleCompte, string> = {
  get admin() { return i18n.t('core:rolesCompte.admin'); },
  get beta_testeur() { return i18n.t('core:rolesCompte.betaTesteur'); },
};

/** L'état d'une bascule pour un compte. */
export interface EtatRole {
  actif: boolean;
  /**
   * D'où vient le rôle quand il est actif. `socle` = la variable
   * `ADMIN_USER_IDS` du serveur, et il l'emporte sur la base quand un compte
   * est dans les deux : c'est lui qui bloque la bascule.
   */
  source: 'socle' | 'base' | null;
  /**
   * Décidé par le SERVEUR (`roles._verrou`), miroir exact de ses deux 409 : un
   * bouton qui part en erreur est un bouton qui n'aurait pas dû être cliquable.
   */
  modifiable: boolean;
  /** Pourquoi c'est bloqué, à afficher en infobulle. Nul si modifiable. */
  raison: string | null;
  motif: string | null;
  ajouteLe: string | null;
  /** L'email de qui a attribué le rôle. */
  ajoutePar: string | null;
}

/** Un compte et l'état de ses deux bascules. */
export interface UtilisateurAdmin {
  userId: string;
  email: string | null;
  prenom: string | null;
  nom: string | null;
  createdAt: string | null;
  /**
   * Vrai pour un identifiant du socle sans ligne `users` : compte supprimé, ou
   * UUID recopié de travers dans le `.env`. La ligne s'affiche quand même — la
   * cacher laisserait un administrateur invisible.
   */
  compteIntrouvable: boolean;
  roles: Record<RoleCompte, EtatRole>;
}

export interface ListeUtilisateurs {
  utilisateurs: UtilisateurAdmin[];
  /** La page le dit à l'écran : une liste tronquée en silence ferait croire
   *  qu'un compte n'existe pas. */
  tronquee: boolean;
  limite: number;
}
