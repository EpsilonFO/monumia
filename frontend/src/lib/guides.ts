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

import i18n from '@/i18n';

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

/**
 * Une étape dont le titre et le texte sont lus au moment de l'affichage (getters),
 * jamais figés à l'import : la langue est fixée avant le premier rendu.
 */
function etape(
  ancre: string,
  titre: () => string,
  texte: () => string,
  cote?: EtapeGuide['cote'],
): EtapeGuide {
  const e: EtapeGuide = {
    ancre,
    get titre() {
      return titre();
    },
    get texte() {
      return texte();
    },
  };
  if (cote) e.cote = cote;
  return e;
}

export const VISITES: Record<GuideId, readonly EtapeGuide[]> = {
  monuments: [
    etape(
      'monuments.carte',
      () => i18n.t('libAides:guides.monuments.carte.titre'),
      () => i18n.t('libAides:guides.monuments.carte.texte'),
    ),
    etape(
      'monuments.nouveau-monument',
      () => i18n.t('libAides:guides.monuments.nouveauMonument.titre'),
      () => i18n.t('libAides:guides.monuments.nouveauMonument.texte'),
    ),
    etape(
      'monuments.documents',
      () => i18n.t('libAides:guides.monuments.documents.titre'),
      () => i18n.t('libAides:guides.monuments.documents.texte'),
      'right',
    ),
  ],
  monument: [
    etape(
      'monument.onglet-fiche',
      () => i18n.t('libAides:guides.monument.fiche.titre'),
      () => i18n.t('libAides:guides.monument.fiche.texte'),
    ),
    etape(
      'monument.onglet-projets',
      () => i18n.t('libAides:guides.monument.projets.titre'),
      () => i18n.t('libAides:guides.monument.projets.texte'),
    ),
    etape(
      'monument.onglet-documents',
      () => i18n.t('libAides:guides.monument.documents.titre'),
      () => i18n.t('libAides:guides.monument.documents.texte'),
    ),
    etape(
      'monument.onglet-equipe',
      () => i18n.t('libAides:guides.monument.equipe.titre'),
      () => i18n.t('libAides:guides.monument.equipe.texte'),
    ),
  ],
  questionnaire: [
    etape(
      'questionnaire.aide',
      () => i18n.t('libAides:guides.questionnaire.aide.titre'),
      () => i18n.t('libAides:guides.questionnaire.aide.texte'),
    ),
    etape(
      'questionnaire.passer',
      () => i18n.t('libAides:guides.questionnaire.passer.titre'),
      () => i18n.t('libAides:guides.questionnaire.passer.texte'),
      'top',
    ),
  ],
  projet: [
    etape(
      'projet.aides',
      () => i18n.t('libAides:guides.projet.aides.titre'),
      () => i18n.t('libAides:guides.projet.aides.texte'),
    ),
    etape(
      'projet.echeancier',
      () => i18n.t('libAides:guides.projet.echeancier.titre'),
      () => i18n.t('libAides:guides.projet.echeancier.texte'),
    ),
    etape(
      'projet.dossiers',
      () => i18n.t('libAides:guides.projet.dossiers.titre'),
      () => i18n.t('libAides:guides.projet.dossiers.texte'),
    ),
    etape(
      'projet.refaire',
      () => i18n.t('libAides:guides.projet.refaire.titre'),
      () => i18n.t('libAides:guides.projet.refaire.texte'),
    ),
  ],
  aide: [
    etape(
      'aide.criteres',
      () => i18n.t('libAides:guides.aide.criteres.titre'),
      () => i18n.t('libAides:guides.aide.criteres.texte'),
    ),
    etape(
      'aide.montant',
      () => i18n.t('libAides:guides.aide.montant.titre'),
      () => i18n.t('libAides:guides.aide.montant.texte'),
    ),
    etape(
      'aide.dossier',
      () => i18n.t('libAides:guides.aide.dossier.titre'),
      () => i18n.t('libAides:guides.aide.dossier.texte'),
    ),
  ],
  dossier: [
    etape(
      'dossier.pieces',
      () => i18n.t('libAides:guides.dossier.pieces.titre'),
      () => i18n.t('libAides:guides.dossier.pieces.texte'),
    ),
    etape(
      'dossier.telecharger',
      () => i18n.t('libAides:guides.dossier.telecharger.titre'),
      () => i18n.t('libAides:guides.dossier.telecharger.texte'),
    ),
    etape(
      'dossier.aide',
      () => i18n.t('libAides:guides.dossier.aide.titre'),
      () => i18n.t('libAides:guides.dossier.aide.texte'),
    ),
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
