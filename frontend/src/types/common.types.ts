export type UserSegment = 'commune' | 'prive' | 'btp';

export type ProtectionLevel = 'classe' | 'inscrit' | 'abords' | 'spr' | 'non_protege';

export type Region =
  | 'ile-de-france' | 'auvergne-rhone-alpes' | 'bourgogne-franche-comte'
  | 'bretagne' | 'centre-val-de-loire' | 'corse' | 'grand-est'
  | 'hauts-de-france' | 'normandie' | 'nouvelle-aquitaine'
  | 'occitanie' | 'pays-de-la-loire' | 'provence-alpes-cote-d-azur';

export type WorkType =
  | 'toiture' | 'charpente' | 'maconnerie' | 'vitraux'
  | 'peintures_murales' | 'menuiserie' | 'electricite'
  | 'plomberie' | 'chauffage' | 'accessibilite'
  | 'mise_en_securite' | 'etude_prealable'
  | 'facade' | 'couverture'
  | 'mobilier' | 'orgues' | 'parcs_jardins'
  | 'protection_solaire' | 'ventilation';

export type OwnershipType = 'public_commune' | 'public_epci' | 'public_departement'
  | 'public_region' | 'public_etat' | 'syndicat_mixte' | 'prive_personne_physique'
  | 'prive_sci' | 'association' | 'mixte';

export type ID = string;
