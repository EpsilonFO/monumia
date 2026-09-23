import type { ID, WorkType } from './common.types';
import type { ProjectQuestionnaireAnswers } from './project.types';

/**
 * Un PROJET de travaux : le chantier qu'on mène sur un monument. Un monument en
 * porte N — chacun avec son cadrage, son questionnaire et son diagnostic.
 *
 * Ce qui reste au MONUMENT et n'a pas sa place ici : l'identification, la
 * protection, le propriétaire, l'état sanitaire (« en péril ? »), les
 * documents, l'équipe et le paywall.
 */
export interface Projet {
  id: ID;
  monumentId: ID;
  userId: ID;

  /**
   * Rôle EFFECTIF de l'utilisateur courant sur CE projet : le maximum de son
   * rôle sur l'équipe du monument et de son appartenance propre au chantier.
   *
   * C'est lui — et jamais `Monument.myRole` — qui gouverne ce que la page projet
   * autorise : un collaborateur invité sur le seul chantier n'a aucun rôle sur
   * le monument mais bien un rôle ici.
   */
  myRole?: import('./sharing.types').ProjectRole;

  /**
   * Posé sur un projet relu depuis le cache local (cf. stores/persistance),
   * jamais sur une réponse du serveur : son questionnaire peut dater, et rien
   * ne doit s'écrire par-dessus (cf. `repondreFait`). Disparaît dès que le
   * serveur répond, puisque sa ligne remplace celle du cache.
   */
  depuisLeCache?: true;

  /** Nullable en base : dérivable des raisons / travaux quand il manque. */
  titre?: string;

  /**
   * Tri-state assumé : `null` = la question n'a jamais été posée ; `[]` = « Pas
   * encore déterminé », une réponse à part entière (le hard_filter travaux du
   * moteur redevient fail-open) ; une liste = les types cochés.
   */
  travauxEnvisages: WorkType[] | null;

  /** Réponses au QCM ET clés réservées (`_raisons`), mêlées — cf. project.types. */
  questionnaire: ProjectQuestionnaireAnswers;

  /** null / absent = projet ouvert. */
  clotureAt?: string;

  createdAt: string;
  updatedAt: string;
}
