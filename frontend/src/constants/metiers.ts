/** Familles de métiers intervenant sur un projet de restauration de monument. */
export interface MetierGroup {
  label: string;
  options: string[];
}

export const METIER_GROUPS: MetierGroup[] = [
  {
    label: 'Propriétaire & porteur du projet',
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
    label: "Architectes & bureaux d'études",
    options: [
      'Architecte du patrimoine',
      'Architecte en chef des monuments historiques (ACMH)',
      "Bureau d'études / économiste de la construction",
      'Géomètre-expert',
      'Diagnostiqueur / expert du bâti',
    ],
  },
  {
    label: 'Artisans & restaurateurs',
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
    label: "Administration & contrôle de l'État",
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
    label: 'Financement & conseil juridique',
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
