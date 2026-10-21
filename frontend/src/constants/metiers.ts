import i18n from '@/i18n';

/** Familles de métiers intervenant sur un projet de restauration de monument. */
export interface MetierGroup {
  label: string;
  options: string[];
}

// Les `options` restent en français : ce sont des VALEURS (texte libre stocké
// tel quel dans `metier`), pas seulement des libellés.
export const METIER_GROUPS: MetierGroup[] = [
  {
    get label() { return i18n.t('constants:metiers.groupes.proprietaire'); },
    options: [
      'Propriétaire du monument',
      'Maire ou élu',
      "Responsable d'association",
      'Secrétaire de mairie / agent administratif',
      'Bénévole',
      "Assistant à maîtrise d'ouvrage (AMO) / chargé de mission patrimoine",
    ],
  },
  {
    get label() { return i18n.t('constants:metiers.groupes.architectes'); },
    options: [
      'Architecte du patrimoine',
      'Architecte en chef des monuments historiques (ACMH)',
      "Bureau d'études / économiste de la construction",
      'Géomètre-expert',
      'Diagnostiqueur / expert du bâti',
    ],
  },
  {
    get label() { return i18n.t('constants:metiers.groupes.artisans'); },
    options: [
      'Tailleur de pierre / maçon du patrimoine',
      'Charpentier',
      'Couvreur / ardoisier / zingueur',
      'Menuisier / ébéniste',
      'Vitrailliste / maître verrier',
      'Peintre en décor / fresquiste / doreur',
      'Sculpteur / ornemaniste / staffeur',
      "Ferronnier d'art",
      'Mosaïste / marbrier / céramiste',
      "Campaniste / horloger d'édifice",
      "Restaurateur d'œuvres d'art",
      'Entreprise spécialisée (Qualibat MH, EPV, GMH)',
    ],
  },
  {
    get label() { return i18n.t('constants:metiers.groupes.administration'); },
    options: [
      'Architecte des Bâtiments de France (ABF)',
      'DRAC / CRMH',
      'Conservateur (CAOA)',
      'Vérificateur des monuments historiques (VMH)',
      'Bureau de contrôle technique',
      'Coordonnateur sécurité (SPS)',
    ],
  },
  {
    get label() { return i18n.t('constants:metiers.groupes.financement'); },
    options: [
      'Fondation du patrimoine',
      "Mécène / fondation d'entreprise",
      'Conseil régional ou départemental',
      'Expert-comptable',
      'Notaire',
      'Avocat',
      'Assureur',
    ],
  },
];

export const METIER_AUTRE = 'Autre';

/**
 * Liste courte présentée à l'inscription (collaborateur / invitation).
 * Six familles lisibles, sans jargon, pour un public peu à l'aise avec l'informatique.
 * La valeur stockée côté backend (`metier`, texte libre) est l'un de ces libellés.
 */
export const METIER_FAMILLES: string[] = [
  'Propriétaire ou porteur du projet',
  "Architecte ou bureau d'études",
  'Artisan ou restaurateur',
  "Administration ou contrôle de l'État",
  'Financement ou conseil',
  METIER_AUTRE,
];

/**
 * Libellé affiché d'un métier. `METIER_FAMILLES` reste en français parce que la
 * famille choisie est la VALEUR enregistrée (`metier`, texte libre) : une
 * inscription en anglais ne doit pas écrire « Other » là où une autre écrit
 * « Autre ». Le libellé se traduit à l'affichage ; un texte qui n'est pas une
 * famille connue (saisie libre, métier détaillé d'avant) s'affiche tel quel.
 */
const LIBELLES_METIER = new Map<string, () => string>([
  ['Propriétaire ou porteur du projet', () => i18n.t('constants:metiers.familles.proprietaire')],
  ["Architecte ou bureau d'études", () => i18n.t('constants:metiers.familles.architecte')],
  ['Artisan ou restaurateur', () => i18n.t('constants:metiers.familles.artisan')],
  ["Administration ou contrôle de l'État", () => i18n.t('constants:metiers.familles.administration')],
  ['Financement ou conseil', () => i18n.t('constants:metiers.familles.financement')],
  [METIER_AUTRE, () => i18n.t('constants:metiers.familles.autre')],
]);

export function libelleMetier(metier: string): string {
  return LIBELLES_METIER.get(metier)?.() ?? metier;
}
