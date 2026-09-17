export const PROTECTION_LEVELS = [
  { value: 'classe', label: 'Classé Monument Historique' },
  { value: 'inscrit', label: 'Inscrit Monument Historique' },
  { value: 'abords', label: 'En périmètre d\'un MH (abords)' },
  { value: 'spr', label: 'Site Patrimonial Remarquable (SPR)' },
  { value: 'non_protege', label: 'Non protégé' },
] as const;

export const OWNERSHIP_TYPES = [
  { value: 'public_commune', label: 'Commune' },
  { value: 'public_epci', label: 'Intercommunalité (EPCI)' },
  { value: 'public_departement', label: 'Département' },
  { value: 'public_region', label: 'Région' },
  { value: 'public_etat', label: 'État' },
  { value: 'syndicat_mixte', label: 'Syndicat mixte / Parc naturel régional' },
  { value: 'prive_personne_physique', label: 'Propriétaire privé (personne physique)' },
  { value: 'prive_sci', label: 'SCI' },
  { value: 'association', label: 'Association' },
  { value: 'mixte', label: 'Propriété mixte' },
] as const;

export const ETATS_CONSERVATION = [
  { value: 'bon', label: 'Bon état' },
  { value: 'moyen', label: 'État moyen' },
  { value: 'mauvais', label: 'Mauvais état' },
  { value: 'peril', label: 'En péril' },
] as const;

export type EtatConservation = (typeof ETATS_CONSERVATION)[number]['value'];

export const URGENCE_TRAVAUX = [
  { value: 'faible', label: 'Faible' },
  { value: 'moyenne', label: 'Moyenne' },
  { value: 'haute', label: 'Haute' },
  { value: 'critique', label: 'Critique' },
] as const;

export const WORK_TYPES = [
  { value: 'toiture', label: 'Toiture' },
  { value: 'charpente', label: 'Charpente' },
  { value: 'couverture', label: 'Couverture' },
  { value: 'facade', label: 'Façade' },
  { value: 'maconnerie', label: 'Maçonnerie' },
  { value: 'vitraux', label: 'Vitraux' },
  { value: 'peintures_murales', label: 'Peintures murales' },
  { value: 'menuiserie', label: 'Menuiserie' },
  { value: 'electricite', label: 'Électricité' },
  { value: 'plomberie', label: 'Plomberie' },
  { value: 'chauffage', label: 'Chauffage' },
  { value: 'accessibilite', label: 'Accessibilité' },
  { value: 'mise_en_securite', label: 'Mise en sécurité' },
  { value: 'etude_prealable', label: 'Étude préalable' },
  { value: 'mobilier', label: 'Mobilier' },
  { value: 'archives', label: 'Archives et documents (photographies, fonds papier, audiovisuel)' },
  { value: 'orgues', label: 'Orgues' },
  { value: 'parcs_jardins', label: 'Parcs et jardins' },
  { value: 'protection_solaire', label: 'Protection solaire' },
  { value: 'ventilation', label: 'Ventilation' },
  // Le DOMAINE autour du bâti. Miroir de `TRAVAUX_LABELS` ([backend/labels.py]) :
  // un code présent d'un seul côté rend invisibles les aides qui s'y cadrent —
  // l'utilisateur ne pourrait jamais le cocher.
  { value: 'exploitation_agricole', label: 'Exploitation agricole (plantations, vergers, haies)' },
  { value: 'foret', label: 'Forêt et desserte forestière' },
  {
    value: 'eau_milieux_aquatiques',
    label: 'Eau et milieux aquatiques (cours d’eau, étang, captage)',
  },
  { value: 'equipement_professionnel', label: 'Équipement professionnel (matériel, véhicule)' },
] as const;

export const MATERIAUX = [
  { value: 'pierre', label: 'Pierre' },
  { value: 'brique', label: 'Brique' },
  { value: 'bois', label: 'Bois' },
  { value: 'ardoise', label: 'Ardoise' },
  { value: 'tuile', label: 'Tuile' },
  { value: 'lauze', label: 'Lauze' },
  { value: 'chaume', label: 'Chaume' },
  { value: 'zinc', label: 'Zinc' },
  { value: 'plomb', label: 'Plomb' },
  { value: 'verre', label: 'Verre' },
  { value: 'metal', label: 'Métal' },
  { value: 'torchis', label: 'Torchis' },
  { value: 'enduit', label: 'Enduit' },
  { value: 'autre', label: 'Autre' },
] as const;

export const TYPES_COUVERTURE = [
  { value: 'toit à longs pans', label: 'Toit à longs pans' },
  { value: 'toit à un pan', label: 'Toit à un pan' },
  { value: 'croupe', label: 'Croupe' },
  { value: 'demi-croupe', label: 'Demi-croupe' },
  { value: 'croupe ronde', label: 'Croupe ronde' },
  { value: 'pavillon', label: 'Pavillon' },
  { value: 'toit brisé', label: 'Toit brisé' },
  { value: 'toit brisé à longs pans', label: 'Toit brisé à longs pans' },
  { value: 'toit brisé en pavillon', label: 'Toit brisé en pavillon' },
  { value: 'flèche', label: 'Flèche' },
  { value: 'flèche polygonale', label: 'Flèche polygonale' },
  { value: 'flèche carrée', label: 'Flèche carrée' },
  { value: 'dôme', label: 'Dôme' },
  { value: 'dôme à pans', label: 'Dôme à pans' },
  { value: 'coupole', label: 'Coupole' },
  { value: 'bulbe', label: 'Bulbe' },
  { value: 'toit en carène', label: 'Toit en carène' },
  { value: 'terrasse', label: 'Terrasse' },
  { value: 'comble à la mansart', label: 'Comble à la mansart' },
  { value: 'pignon couvert', label: 'Pignon couvert' },
  { value: 'pignon découvert', label: 'Pignon découvert' },
  { value: 'noue', label: 'Noue' },
  { value: 'appentis', label: 'Appentis' },
  { value: 'shed', label: 'Shed' },
  { value: 'flèche de haut-clocher', label: 'Flèche de haut-clocher' },
] as const;

export const AFFECTATAIRES = [
  { value: 'culte', label: 'Culte' },
  { value: 'mairie', label: 'Mairie / Services municipaux' },
  { value: 'habitation', label: 'Habitation' },
  { value: 'musee', label: 'Musée' },
  { value: 'tourisme', label: 'Tourisme / Visite' },
  { value: 'enseignement', label: 'Enseignement' },
  { value: 'commercial', label: 'Activité commerciale' },
  { value: 'non_affecte', label: 'Non affecté / Vacant' },
  { value: 'autre', label: 'Autre' },
] as const;

// Lookup tables keyed by stored value. Long form for detail panels, short form
// for compact badges (e.g. the project summary bar).
export const PROTECTION_LABELS: Record<string, string> = {
  classe: 'Classé Monument Historique',
  inscrit: 'Inscrit Monument Historique',
  abords: "En périmètre d'un MH",
  spr: 'Site Patrimonial Remarquable',
  non_protege: 'Non protégé',
};

export const PROTECTION_LABELS_SHORT: Record<string, string> = {
  classe: 'Classé MH',
  inscrit: 'Inscrit MH',
  abords: 'Périmètre MH',
  spr: 'Site Patrimonial Remarquable',
  non_protege: 'Non protégé',
};

/**
 * Miroir de `ETAT_LABELS` côté backend (labels.py), qui borne les valeurs
 * admises en base et dans `hard_filters.etats_conservation`.
 */
export const ETAT_LABELS: Record<string, string> = {
  bon: 'Bon état',
  moyen: 'État moyen',
  mauvais: 'Mauvais état',
  peril: 'En péril',
};

/**
 * Les vignettes et fiches ne montrent qu'un signal binaire dérivé des quatre
 * niveaux : `mauvais` et `peril` sont regroupés côté péril, exactement comme
 * les gates des aides concernées (`{in: [mauvais, peril]}`). Le wizard, lui,
 * pose bien la question sur les quatre niveaux (cf. `PerilStep`).
 *
 * Renvoie `null` tant que la question n'a pas été posée — la colonne est
 * nullable depuis la migration 20260827094119.
 */
export function isEnPeril(etat: string | null | undefined): boolean | null {
  if (!etat) return null;
  return etat === 'peril' || etat === 'mauvais';
}

/** Libellé du signal péril pour les vignettes et fiches (null si non renseigné). */
export function perilLabel(etat: string | null | undefined): string | null {
  const peril = isEnPeril(etat);
  return peril === null ? null : peril ? 'En péril' : 'Pas en péril';
}
