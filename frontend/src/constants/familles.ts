import type { ProjectQuestionnaireAnswers } from '@/types';

/**
 * Familles thématiques d'une aide (colonne `aides_v3.familles`, constante
 * `FAMILLES` côté backend, dérivée de `labels.FAMILLES_LABELS`).
 *
 * L'axe que `raison` ne sait pas dire : ses quatre valeurs mettent dans le même
 * sac un festival, un gîte et un outil de médiation. Un projet « faire vivre et
 * ouvrir le lieu » coche donc ses familles, et le moteur écarte les aides d'un
 * autre thème — sans ça, monter un festival fait demander si le projet est un
 * hébergement touristique.
 *
 * Liste FERMÉE, fermée en trois endroits qui doivent rester d'accord : ici, le
 * `FAMILLES_LABELS` du backend et le CHECK SQL de la migration
 * `ajouter_familles_aides_v3`. Des tests des deux côtés le vérifient.
 */
export type Famille =
  | 'restauration_bati'
  | 'energie_climat'
  | 'eau_nature_domaine'
  | 'securite_risques'
  | 'parcs_jardins_paysages'
  | 'tourisme_hebergement'
  | 'activite_economique_lieu'
  | 'spectacles_manifestations'
  | 'vie_locale_associative'
  | 'mediation_numerique_expositions'
  | 'accessibilite_publics'
  | 'etudes_ingenierie'
  | 'labels_passerelles';

/**
 * Les treize familles, LIBELLÉS COMPRIS — miroir de `FAMILLES_LABELS`. Sert à
 * relire ce qui est déjà en base (les facettes d'une liste d'aides) ; ce que
 * l'étape « Votre projet » propose, c'est `FAMILLES_CHOIX`, plus court.
 */
export const FAMILLE_OPTIONS: { value: Famille; label: string; hint: string }[] = [
  {
    value: 'restauration_bati',
    label: 'Restauration du bâti',
    hint: 'Travaux sur le bâti, protégé ou non, et le mobilier attaché.',
  },
  {
    value: 'energie_climat',
    label: 'Énergie et climat',
    hint: 'Rénovation énergétique, chauffage, matériaux biosourcés.',
  },
  {
    value: 'eau_nature_domaine',
    label: 'Eau, nature et domaine',
    hint: 'Cours d’eau, douves, biodiversité, forêt, vergers, haies.',
  },
  {
    value: 'securite_risques',
    label: 'Sécurité et risques',
    hint: 'Incendie, foudre, inondation, sûreté, mise en sécurité.',
  },
  {
    value: 'parcs_jardins_paysages',
    label: 'Parcs, jardins et paysages',
    hint: 'Parcs et jardins, arbres remarquables, paysages, abords.',
  },
  {
    value: 'tourisme_hebergement',
    label: 'Tourisme et hébergement',
    hint: 'Gîtes, chambres d’hôtes, site de visite, itinérance.',
  },
  {
    value: 'activite_economique_lieu',
    label: 'Activité économique dans le lieu',
    hint: 'Reconversion, tiers-lieu, commerce ou artisanat installé.',
  },
  {
    value: 'spectacles_manifestations',
    label: 'Spectacles et manifestations',
    hint: 'Festivals, saisons, résidences, évènements accueillis.',
  },
  {
    value: 'vie_locale_associative',
    label: 'Vie locale et associative',
    hint: 'Vie associative, fêtes locales, mémoire, cultures régionales.',
  },
  {
    value: 'mediation_numerique_expositions',
    label: 'Médiation, expositions, musée, numérique',
    hint: 'Signalétique, scénographie, expositions, musée, numérique.',
  },
  {
    value: 'accessibilite_publics',
    label: 'Accessibilité et accueil des publics',
    hint: 'Accessibilité, handicap, confort d’accueil des visiteurs.',
  },
  {
    value: 'etudes_ingenierie',
    label: 'Études et ingénierie',
    hint: 'Études préalables, diagnostics, ingénierie, AMO.',
  },
  {
    value: 'labels_passerelles',
    label: 'Labels et passerelles',
    hint: 'Labels et dispositifs qui ouvrent l’accès à d’autres aides.',
  },
];

/**
 * Familles PROPOSÉES par l'étape « Votre projet » d'un projet « faire vivre et
 * ouvrir le lieu ». Les cinq familles de chantier (bâti, énergie, eau et
 * nature, sécurité, parcs et jardins) et les études n'y sont pas : elles
 * relèvent de l'intention « Restaurer » ou « Préparer le projet », qui les
 * implique déjà côté moteur (`FAMILLES_PAR_RAISON`) sans rien demander.
 *
 * `parcs_jardins_paysages` fait exception et reste proposée : ouvrir un jardin
 * à la visite est un projet de « faire vivre » à part entière, pas un chantier.
 *
 * `activite_economique_lieu` n'a encore AUCUNE aide au catalogue : la tuile
 * existe pour le catalogue qui arrive (64 candidates en file d'attente), et
 * `hors_famille` étant fail-open par aide, la cocher ne masque rien.
 *
 * Ordre décroissant du poids attendu au catalogue (regroupement des 60 aides
 * « valorisation seule » du 2026-09-16) : la première tuile est celle qui
 * débloque le plus. `activite_economique_lieu` ferme donc la marche.
 */
export const FAMILLES_CHOIX: Famille[] = [
  'spectacles_manifestations',
  'mediation_numerique_expositions',
  'tourisme_hebergement',
  'vie_locale_associative',
  'labels_passerelles',
  'parcs_jardins_paysages',
  'accessibilite_publics',
  'activite_economique_lieu',
];

/**
 * Famille de la tuile « Des travaux sont nécessaires » de l'étape.
 *
 * Un projet « faire vivre le lieu » comporte souvent un aménagement (créer une
 * billetterie, mettre aux normes une salle). Cocher cette tuile fait deux
 * choses : elle garde les aides de restauration dans le cadrage, et elle
 * ROUVRE l'étape des travaux, que « Faire vivre » saute par défaut. C'est la
 * réponse symétrique de l'option « Aucun » d'`etat_travaux` : l'un dit qu'il
 * n'y a pas de chantier, l'autre qu'il y en a un.
 */
export const FAMILLE_TRAVAUX: Famille = 'restauration_bati';

/** Vrai si la famille est encore proposée par l'étape « Votre projet ». */
export function familleProposee(famille: string): boolean {
  return (FAMILLES_CHOIX as string[]).includes(famille);
}

/** Libellé d'une famille, ou son code si elle est inconnue (fail-open). */
export function libelleFamille(famille: string): string {
  return FAMILLE_OPTIONS.find((o) => o.value === famille)?.label ?? famille;
}

/**
 * Clé RÉSERVÉE portant les familles dans `projet.questionnaire`. Même
 * convention que `RAISONS_KEY` : le préfixe « _ » la distingue des réponses aux
 * faits, et le backend isole ces clés avant d'évaluer.
 */
export const FAMILLES_KEY = '_familles';

/**
 * Familles d'un questionnaire persisté, en TRI-ÉTAT :
 *
 * - `null` — la clé est absente : la question n'a jamais été posée (projet
 *   d'avant l'étape, ou projet de restauration qui ne la voit pas). Le moteur
 *   ne filtre rien.
 * - `[]` — « Je ne sais pas encore, montrez-moi tout » : une réponse à part
 *   entière, qui ne filtre rien non plus, mais que l'utilisateur a donnée.
 * - une liste — les familles cochées.
 *
 * La distinction entre les deux premiers cas ne survit PAS dans
 * `ProjectQuestionnaireAnswers`, qui n'admet pas `null` : le tri-état vit dans
 * l'état du wizard, et le questionnaire ne porte `_familles` que non `null`.
 */
export function readFamilles(answers: ProjectQuestionnaireAnswers | undefined): string[] | null {
  if (!answers || !(FAMILLES_KEY in answers)) return null;
  const raw = answers[FAMILLES_KEY];
  return Array.isArray(raw) ? raw.filter((f): f is string => typeof f === 'string') : null;
}
