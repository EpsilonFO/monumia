export const DENOMINATIONS = [
  { value: 'eglise', label: 'Église' },
  { value: 'chapelle', label: 'Chapelle' },
  { value: 'cathedrale', label: 'Cathédrale' },
  { value: 'abbaye', label: 'Abbaye' },
  { value: 'chateau', label: 'Château' },
  { value: 'manoir', label: 'Manoir' },
  { value: 'hotel_particulier', label: 'Hôtel particulier' },
  { value: 'maison', label: 'Maison' },
  { value: 'tour', label: 'Tour' },
  { value: 'rempart', label: 'Rempart / Fortification' },
  { value: 'pont', label: 'Pont' },
  { value: 'halle', label: 'Halle' },
  { value: 'lavoir', label: 'Lavoir' },
  { value: 'fontaine', label: 'Fontaine' },
  { value: 'theatre', label: 'Théâtre' },
  { value: 'moulin', label: 'Moulin' },
  { value: 'ferme', label: 'Ferme' },
  { value: 'grange', label: 'Grange' },
  { value: 'autre', label: 'Autre' },
] as const;

export const PROTECTION_LEVELS = [
  { value: 'classe', label: 'Classé Monument Historique' },
  { value: 'inscrit', label: 'Inscrit Monument Historique' },
  { value: 'abords', label: 'En périmètre d\'un MH (abords)' },
  { value: 'spr', label: 'Site Patrimonial Remarquable (SPR)' },
  { value: 'non_protege', label: 'Non protégé' },
] as const;

export const OWNERSHIP_TYPES = [
  { value: 'public_commune', label: 'Commune' },
  { value: 'public_departement', label: 'Département' },
  { value: 'public_region', label: 'Région' },
  { value: 'public_etat', label: 'État' },
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
  { value: 'restauration_generale', label: 'Restauration générale' },
  { value: 'etude_prealable', label: 'Étude préalable' },
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
