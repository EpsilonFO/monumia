/**
 * Les visites guidées de l'application : une par écran, jouée à la première
 * arrivée sur cet écran (`useGuide`), jamais une visite qui navigue d'une page
 * à l'autre : elle casserait dès qu'un écran est flouté, vide ou différent sur
 * mobile.
 *
 * Règle d'écriture, vérifiée par `__tests__/guides.test.ts` (une bulle se lit
 * en trois secondes) :
 *   - titre : 4 mots au plus, qui nomment la chose ;
 *   - texte : une phrase de 120 caractères au plus, qui dit ce qu'on peut FAIRE
 *     ici, pas ce que c'est ;
 *   - 4 bulles au plus par écran, une notion par bulle, pas de jargon interne
 *     (ni « seau », ni « fait », ni « diagnostic déterministe »), pas de tiret
 *     cadratin.
 *
 * Chaque étape s'accroche à un élément existant par `data-guide="<ancre>"`.
 * Une étape dont l'ancre est absente, cachée ou derrière un paywall (`inert`)
 * est simplement sautée (`etapesJouables`).
 */

/** Miroir de `GuideId` (backend/routers/auth.py), vérifié par `test_guides_vus.py`. */
export const GUIDE_IDS = ['monuments', 'monument', 'questionnaire', 'projet', 'aide', 'dossier'] as const;
export type GuideId = (typeof GUIDE_IDS)[number];

export interface EtapeGuide {
  /** Valeur de l'attribut `data-guide` de l'élément visé. */
  ancre: string;
  titre: string;
  texte: string;
  /** Où poser la bulle par rapport à l'élément. */
  cote?: 'top' | 'right' | 'bottom' | 'left';
}

export const VISITES: Record<GuideId, readonly EtapeGuide[]> = {
  monuments: [
    {
      ancre: 'monuments.carte',
      titre: 'Votre monument',
      texte: 'Ouvrez votre monument pour voir sa fiche, ses projets et ses documents.',
    },
    {
      ancre: 'monuments.nouveau-monument',
      titre: 'Un autre monument',
      texte: 'Ajoutez un autre bien ici : chacun a sa fiche, ses projets et ses aides.',
    },
    {
      ancre: 'monuments.documents',
      titre: 'Vos documents',
      texte: 'Rangez ici arrêtés, plans et photos pour les retrouver au moment du dossier.',
      cote: 'right',
    },
  ],
  monument: [
    {
      ancre: 'monument.onglet-fiche',
      titre: 'La fiche du monument',
      texte: 'Complétez la fiche : la protection, le propriétaire et l’état décident des aides proposées.',
    },
    {
      ancre: 'monument.onglet-projets',
      titre: 'Les projets',
      texte: 'Ouvrez un projet pour voir ses aides, ou créez-en un pour un autre chantier.',
    },
    {
      ancre: 'monument.onglet-documents',
      titre: 'Les documents',
      texte: 'Déposez ici les pièces du monument : arrêté de protection, cadastre, photos.',
    },
    {
      ancre: 'monument.onglet-equipe',
      titre: 'L’équipe',
      texte: 'Invitez un architecte ou un collègue à travailler avec vous sur ce monument.',
    },
  ],
  questionnaire: [
    {
      ancre: 'questionnaire.aide',
      titre: 'Bon à savoir',
      texte: 'Lisez cet encadré en cas de doute : il explique les termes de la question.',
    },
    {
      ancre: 'questionnaire.passer',
      titre: 'Je ne sais pas',
      texte: 'Passez une question si vous hésitez : les aides restent proposées, vous répondrez plus tard.',
      cote: 'top',
    },
  ],
  projet: [
    {
      ancre: 'projet.aides',
      titre: 'Vos aides',
      texte: 'Cliquez sur une aide pour voir ses critères et préparer le dossier.',
    },
    {
      ancre: 'projet.echeancier',
      titre: 'L’échéancier',
      texte: 'Repérez ici les dates limites de dépôt de vos aides.',
    },
    {
      ancre: 'projet.dossiers',
      titre: 'Vos dossiers',
      texte: 'Suivez ici chaque dossier, de la préparation au dépôt.',
    },
    {
      ancre: 'projet.refaire',
      titre: 'Modifier vos réponses',
      texte: 'Modifiez vos réponses si votre projet change : la liste des aides se met à jour.',
    },
  ],
  aide: [
    {
      ancre: 'aide.criteres',
      titre: 'Les critères',
      texte: 'Vérifiez chaque critère et répondez ici aux questions encore ouvertes.',
    },
    {
      ancre: 'aide.montant',
      titre: 'Le montant',
      texte: 'Retrouvez ici ce que l’aide finance et jusqu’à quel montant.',
    },
    {
      ancre: 'aide.dossier',
      titre: 'Le dossier',
      texte: 'Créez le dossier pour obtenir la liste des pièces et les étapes du dépôt.',
    },
  ],
  dossier: [
    {
      ancre: 'dossier.pieces',
      titre: 'Les pièces',
      texte: 'Déposez chaque pièce demandée et voyez d’un coup d’œil combien sont prêtes.',
    },
    {
      ancre: 'dossier.telecharger',
      titre: 'Télécharger le dossier',
      texte: 'Téléchargez toutes les pièces en une fois, prêtes à envoyer à l’organisme.',
    },
    {
      ancre: 'dossier.aide',
      titre: 'L’aide visée',
      texte: 'Rouvrez la fiche de l’aide pour revoir ses conditions et la marche à suivre.',
    },
  ],
};

/** En dessous, la visite ne se lance pas : une bulle seule n'est pas une visite. */
export const ETAPES_MIN = 2;

/**
 * Les étapes qu'on peut jouer : celles dont l'ancre est visible (`estVisible`
 * le dit : présente, affichée, hors d'un contenu `inert`). Pure : le DOM est
 * interrogé par l'appelant.
 */
export function etapesJouables(
  etapes: readonly EtapeGuide[],
  estVisible: (ancre: string) => boolean,
): EtapeGuide[] {
  return etapes.filter((e) => estVisible(e.ancre));
}

/** Le sélecteur CSS d'une ancre. */
export function selecteurAncre(ancre: string): string {
  return `[data-guide="${ancre}"]`;
}
