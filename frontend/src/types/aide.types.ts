import type { ID, ProtectionLevel, OwnershipType, Region, WorkType } from './common.types';

export type AideCategory =
  | 'etat_drac'
  | 'region'
  | 'departement'
  | 'fondation_patrimoine'
  | 'europe'
  | 'mecenat'
  | 'fiscalite'
  | 'autre';

export type AideType = 'subvention' | 'avance' | 'pret' | 'deduction_fiscale'
  | 'label' | 'mecenat' | 'souscription' | 'autre';

/** Pièce du dossier à constituer pour une aide. */
export interface AideDocument {
  nom: string;
  /** Lien de téléchargement / remplissage (formulaire, Cerfa, modèle). */
  url?: string;
  /** False = pièce requise seulement dans certains cas (cf. note). */
  obligatoire?: boolean;
  /** Conditionnalité, ex. « si propriétaire public ». */
  note?: string;
}

export interface Aide {
  id: ID;
  nom: string;
  nomCourt: string;
  description: string;
  descriptionLongue: string;

  categorie: AideCategory;
  type: AideType;
  organisme: string;
  organismeContact?: string;

  montantMax?: number;
  tauxMax?: number;
  montantMin?: number;
  plancher?: number;

  criteres: AideEligibilityCriteria;

  demarcheDescription: string;
  /** Pièce du dossier : chaîne simple (legacy) ou objet structuré avec son
   * lien de téléchargement/remplissage et une note de conditionnalité. */
  documentsRequis: (string | AideDocument)[];
  delaiInstruction: string;

  dateOuverture?: string;
  dateLimite?: string;
  permanent: boolean;

  urlOfficielle?: string;
  formulaireUrl?: string;

  baseTTC: boolean;
}

export interface AideEligibilityCriteria {
  protectionRequise?: ProtectionLevel[];
  proprietaireEligible?: OwnershipType[];
  travauxEligibles?: WorkType[];

  regionEligible?: Region[];
  departementEligible?: string[];

  communeDeMoins10000Hab?: boolean;
  communeMaxPopulation?: number;
  diagnosticPrealableRequis?: boolean;
  architecteRequis?: boolean;
  cofinancementRequis?: boolean;

  etatConservationRequis?: ('bon' | 'moyen' | 'mauvais' | 'peril')[];

  criteresSupplementaires?: {
    label: string;
    description: string;
  }[];
}

export type EvaluationVerdict = 'oui' | 'non' | 'incertitude' | 'info';

export interface AideEvaluation {
  critere: string;
  verdict: EvaluationVerdict;
  explication: string;
  /** Only set when verdict === 'incertitude' (drives QCM matching). */
  categorie?: string;
  /** Only set when verdict === 'incertitude' (concise text for the QCM). */
  detail?: string;
  /** Becomes true once the user answers the matching QCM question. */
  clarified?: boolean;
  /** Nature de la condition (moteur déterministe) : pilote le regroupement de
   * l'analyse en sections. auto | user_fact | manual_check | discretionary |
   * modulateur | info. Absent sur l'ancien chemin LLM. */
  nature?: 'auto' | 'user_fact' | 'manual_check' | 'discretionary' | 'modulateur' | 'info';
  /** Échec sur un critère ACTIONNABLE : à afficher comme démarche à engager,
   *  jamais comme motif de refus. Le plan détaillé est dans `AideMatchResult.leviers`. */
  levier?: boolean;
}

/** Statut d'éligibilité rendu par le moteur déterministe (absent sur le chemin LLM). */
export type AideStatut = 'eligible' | 'atteignable' | 'potentiel' | 'non_eligible';

/**
 * Démarche qui débloque une aide bloquée sur un seul critère actionnable :
 * obtenir un label, s'engager à ouvrir, choisir une entreprise certifiée…
 * C'est ce qui distingue « non éligible » de « à débloquer ».
 */
export interface AideLevier {
  /** Clé du fait de l'ontologie sur lequel porte le levier. */
  factId?: string;
  /** Critère de l'aide, tel qu'écrit dans son règlement. */
  critere: string;
  resume: string;
  demarche?: string | null;
  organisme?: string | null;
  cout?: string | null;
  delai?: string | null;
  url?: string | null;
  /** Écart chiffré à combler, sur un critère numérique (« Il en manque 8 jours/an »). */
  ecart?: string;
}

export interface AideMatchResult {
  aide: Aide;
  /** Statut explicite du moteur déterministe : à préférer à toute dérivation. */
  statut?: AideStatut;
  eligible: boolean;
  criteresRemplis: string[];
  criteresNonRemplis: string[];
  raisonIneligibilite?: string;
  /** Plans d'action des critères à débloquer (statut « atteignable »). */
  leviers?: AideLevier[];
  llmEvaluation?: {
    explication: string;
    /** One verdict per bullet of conditions_eligibilite_detail. */
    evaluations?: AideEvaluation[];
    /** Derived view: the evaluations with verdict === 'incertitude'. Drives the QCM. */
    incertitudes: (string | { categorie: string; detail: string; clarified?: boolean })[];
  };
}

export interface AideDiagnosticRequest {
  monumentId: ID;
  modeProjet: boolean;
  travauxFiltres?: WorkType[];
}

export interface QcmOption {
  id: string;
  label: string;
}

/**
 * Branchement conditionnel : la question ne concerne que les profils ayant
 * répondu à `questionId` par l'une des `showForOptionIds`. Émis par le moteur
 * déterministe quand toutes les conditions candidates du fait partagent la même
 * clause `applies_if`. Fail-closed côté front : tant que la question dont elle
 * dépend n'est pas répondue (ou est passée), la question reste posée.
 */
export interface QcmDependsOn {
  questionId: string;
  showForOptionIds: string[];
}

export interface QcmQuestion {
  id: string;
  question: string;
  /** Texte d'aide du fait (ontologie) : lève l'ambiguïté sans quitter l'écran. */
  help?: string | null;
  options: QcmOption[];
  aideIds: string[];
  eliminatingOptionIds: string[];
  /** Fine-grained elimination: optionId -> aideIds eliminated when that option is selected. */
  eliminationsParOption?: Record<string, string[]>;
  categorie?: string;
  incertitudesGroupees?: string[];
  dependsOn?: QcmDependsOn;
  /** Montants max cumulés des aides suspendues à cette question (0 si aucune chiffrée). */
  enjeuMax?: number;
}

export interface AideDiagnosticResult {
  id?: string;
  monumentId: ID;
  timestamp: string;
  modeProjet?: boolean;
  travauxFiltres?: string[];
  totalAidesAnalysees: number;
  aidesEligibles: AideMatchResult[];
  aidesPotentiellementEligibles: AideMatchResult[];
  /** « À débloquer » : bloquées sur un seul critère actionnable, triées par enjeu
   *  décroissant. Absent sur l'ancien chemin LLM. */
  aidesAtteignables?: AideMatchResult[];
  aidesNonEligibles: AideMatchResult[];
  montantPotentielTotal?: number;
  montantAtteignableTotal?: number;
  qcmQuestions?: QcmQuestion[];
  qcmAnswers?: Record<string, string>;
}

/** Vue allégée d'une aide : ce qu'une vignette de projet en montre. */
export interface AideDigest {
  id: ID;
  nom: string;
  categorie: AideCategory;
  permanent: boolean;
  dateLimite?: string;
  montantMax?: number;
}

/**
 * Ce que le dashboard et la liste des projets consomment réellement d'un
 * diagnostic : des compteurs, deux montants, des dates limites. Servi tel quel
 * par `GET /dashboard`, qui évite ainsi d'envoyer les ~95 aides non éligibles
 * et leurs conditions détaillées par projet (1,7 Mo contre quelques kilo-octets).
 *
 * `AideDiagnosticResult` en est un sur-ensemble structurel : les fonctions de
 * `project-stats` acceptent les deux indifféremment.
 */
export interface ProjectDigest {
  monumentId: ID;
  aidesEligibles: { aide: AideDigest }[];
  aidesPotentiellementEligibles: { aide: AideDigest }[];
  aidesAtteignables?: { aide: AideDigest }[];
  montantPotentielTotal?: number;
  montantAtteignableTotal?: number;
}
