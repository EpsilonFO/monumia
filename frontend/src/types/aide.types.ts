import type { ID, ProtectionLevel, OwnershipType, Region, WorkType } from './common.types';

/**
 * Financeur de l'aide. Miroir EXACT du tuple `CATEGORIES` de
 * [aides_schema.py](backend/aides_schema.py) : la valeur vient des YAML et
 * traverse le moteur telle quelle. Toute divergence se voit à l'écran — un
 * libellé introuvable retombe sur le slug brut dans le badge de l'aide.
 */
export type AideCategory =
  | 'etat_drac'
  | 'region'
  | 'departement'
  | 'fondation'
  | 'europe'
  | 'mecenat'
  | 'fiscalite'
  | 'autre';

/** Nature du concours. Miroir du tuple `TYPES` de aides_schema.py. */
export type AideType =
  | 'subvention'
  | 'appel_a_projets'
  | 'pret'
  | 'deduction_fiscale'
  | 'exoneration'
  | 'label'
  | 'mecenat'
  | 'souscription';

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

  /** Familles thématiques de l'aide (liste fermée, cf. `constants/familles`).
   *  Vide ou absente = l'aide concerne tout projet (fail-open). Sert au cadrage
   *  « faire vivre le lieu » côté serveur, et aux facettes de la page projet. */
  familles?: string[];
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
  /** Nature de la condition : pilote le regroupement de l'analyse en sections.
   * auto | user_fact | manual_check | discretionary | modulateur | info. */
  nature?: 'auto' | 'user_fact' | 'manual_check' | 'discretionary' | 'modulateur' | 'info';
  /** Échec sur un critère ACTIONNABLE : à afficher comme démarche à engager,
   *  jamais comme motif de refus. Le plan détaillé est dans `AideMatchResult.leviers`. */
  levier?: boolean;
}

/** Statut d'éligibilité rendu par le moteur. */
export type AideStatut = 'eligible' | 'atteignable' | 'potentiel' | 'non_eligible';

/**
 * Fenêtre de candidature à la date du diagnostic, orthogonale au statut :
 * « maintenant » = déposable aujourd'hui · « bientot » = fenêtre pas encore
 * ouverte ou déjà refermée (dispositif annuel dont la session est passée).
 */
export type AideDisponibilite = 'maintenant' | 'bientot';

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
  /** Fenêtre de candidature du jour. Lire via `getDisponibilite`, qui retombe
   *  sur « maintenant » quand le champ est absent. */
  disponibilite?: AideDisponibilite;
  eligible: boolean;
  criteresRemplis: string[];
  criteresNonRemplis: string[];
  raisonIneligibilite?: string;
  /** Le refus vient-il d'une réponse au questionnaire (`true`) ou des seuls
   *  filtres automatiques déduits de la fiche du monument (`false`) ? Toujours
   *  `false` hors statut « non éligible ». */
  elimineParReponse?: boolean;
  /** Plans d'action des critères à débloquer (statut « atteignable »). */
  leviers?: AideLevier[];
  /** Entrée RÉSUMÉE par le serveur : une aide non éligible que le front
   *  n'affiche pas (elle n'a pas été écartée par une réponse). Elle ne porte ni
   *  `llmEvaluation` ni le détail de l'aide (pièces, démarche, conditions) —
   *  de quoi la retrouver par son id, pas l'afficher. La fiche complète se
   *  demande à `GET /aides/{id}`. */
  resume?: boolean;
  /** Nom vestigial : ce sont les verdicts déterministes, condition par
   *  condition. Rien de LLM ici. */
  llmEvaluation?: {
    explication: string;
    /** Un verdict par condition évaluée. */
    evaluations?: AideEvaluation[];
    /** Derived view: the evaluations with verdict === 'incertitude'. Drives the QCM. */
    incertitudes: (string | { categorie: string; detail: string; clarified?: boolean })[];
  };
}

export interface QcmOption {
  id: string;
  label: string;
  /** Réponse « je ne sais pas / pas encore décidé » : le fait reste inconnu.
   *  N'élimine aucune aide, et exclut les autres cases en choix multiple. */
  unknown?: boolean;
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
  /** Fait `multi_enum` : plusieurs options cochables, la réponse est un tableau
   *  d'ids. Une aide reste retenue dès qu'UNE case cochée satisfait son critère. */
  multiple?: boolean;
  options: QcmOption[];
  aideIds: string[];
  eliminatingOptionIds: string[];
  /** Fine-grained elimination: optionId -> aideIds eliminated when that option is selected. */
  eliminationsParOption?: Record<string, string[]>;
  categorie?: string;
  /** Où la réponse vaut : le bien, le projet, ou le propriétaire. Une réponse
   *  de scope `monument` ou `proprietaire` est DURABLE — elle se reprend d'un
   *  projet à l'autre du même monument (cf. `projetService.faitsDurables`). */
  scope?: 'monument' | 'projet' | 'proprietaire';
  incertitudesGroupees?: string[];
  dependsOn?: QcmDependsOn;
  /** Montants max cumulés des aides suspendues à cette question (0 si aucune chiffrée). */
  enjeuMax?: number;
}

export interface AideDiagnosticResult {
  /** Le PROJET de travaux diagnostiqué — clé du store de diagnostics et des
   *  liens d'échéance. Absent sur le chemin de compatibilité `monument_id`
   *  (onglet SPA non rechargé) quand le monument n'a encore aucun projet. */
  projetId?: ID;
  /** Le monument parent, tel que rendu par le moteur. Reste la clé du paywall. */
  monumentId: ID;
  timestamp: string;
  totalAidesAnalysees: number;
  aidesEligibles: AideMatchResult[];
  aidesPotentiellementEligibles: AideMatchResult[];
  /** « À débloquer » : bloquées sur un seul critère actionnable, triées par enjeu
   *  décroissant. */
  aidesAtteignables?: AideMatchResult[];
  aidesNonEligibles: AideMatchResult[];
  montantPotentielTotal?: number;
  montantAtteignableTotal?: number;
  /** Part maximale du coût des travaux couverte, en %. Somme des taux des trois
   *  seaux affichés (maintenant / à confirmer / à débloquer), écrêtée à 80 % :
   *  le maître d'ouvrage garde au moins 20 % à sa charge. N'agrège que les aides
   *  qui subventionnent les travaux — dispositifs fiscaux (Denormandie,
   *  Malraux…), prêts et labels en sont exclus. */
  tauxTravauxMaxPct?: number;
  qcmQuestions?: QcmQuestion[];
  /** Réponses renvoyées telles quelles par le moteur : un id d'option, ou un
   *  tableau d'ids sur une question à choix multiple. */
  qcmAnswers?: Record<string, string | string[]>;
}

/**
 * L'accroche chiffrée du parcours découverte : ce qu'un VISITEUR sans compte
 * apprend de son diagnostic. Des compteurs et des montants, jamais un nom
 * d'aide — la liste l'attend derrière l'inscription, recalculée sous l'offre
 * réelle du compte.
 */
export interface SyntheseInvite {
  eligibles: number;
  potentielles: number;
  atteignables: number;
  totalAnalysees: number;
  montantPotentielTotal?: number | null;
  montantAtteignableTotal?: number | null;
  tauxTravauxMaxPct?: number | null;
}

/**
 * Réponse de `POST /aides/diagnostic-invite`. Volontairement PAUVRE face à
 * `AideDiagnosticResult` : de quoi poser le questionnaire, de quoi donner
 * envie, rien de plus.
 *
 * Les `aideIds` des questions sont pseudonymisés côté serveur (« a1 », « a2 »…) :
 * `computeEliminatedAideIds` et `isQuestionServingLiveAide` ne font que des
 * tests d'appartenance entre `aideIds` et `eliminationsParOption`, des alias
 * stables à l'échelle d'une réponse leur suffisent.
 */
export interface DiagnosticInviteResult {
  qcmQuestions: QcmQuestion[];
  synthese: SyntheseInvite;
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
  /** Un digest décrit un PROJET : c'est par lui que le front l'indexe.
   *  Optionnel comme sur `AideDiagnosticResult`, qui doit en rester un
   *  sur-ensemble structurel (project-stats consomme les deux). */
  projetId?: ID;
  /** Monument parent — clé du paywall et de l'agrégation par monument. */
  monumentId: ID;
  aidesEligibles: { aide: AideDigest; disponibilite?: AideDisponibilite }[];
  aidesPotentiellementEligibles: { aide: AideDigest; disponibilite?: AideDisponibilite }[];
  aidesAtteignables?: { aide: AideDigest; disponibilite?: AideDisponibilite }[];
  montantPotentielTotal?: number;
  montantAtteignableTotal?: number;
  tauxTravauxMaxPct?: number;
}
