/**
 * Administration du catalogue (page `/admin`, réservée aux fondateurs).
 *
 * Miroir de `backend/services/catalogue_admin.py`. Le vocabulaire est celui du
 * produit : une aide est « retirée du catalogue » ou « republiée » (jamais
 * « masquée », qui désigne le paywall Veille, ni « non éligible », qui est un
 * verdict du moteur) ; une question est « surchargée » ou « rétablie ».
 */

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

/** Les quatre opérateurs que l'éditeur sait rendre. Pas de combinateur. */
export type OperateurPredicat = 'eq' | 'neq' | 'in' | 'not_in';

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
