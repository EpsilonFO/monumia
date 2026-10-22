import i18n from '@/i18n';

export const PROTECTION_LEVELS = [
  { value: 'classe', get label() { return i18n.t('constants:monumentOptions.protection.classe'); } },
  { value: 'inscrit', get label() { return i18n.t('constants:monumentOptions.protection.inscrit'); } },
  { value: 'abords', get label() { return i18n.t('constants:monumentOptions.protection.abords'); } },
  { value: 'spr', get label() { return i18n.t('constants:monumentOptions.protection.spr'); } },
  { value: 'non_protege', get label() { return i18n.t('constants:monumentOptions.protection.non_protege'); } },
] as const;

export const OWNERSHIP_TYPES = [
  { value: 'public_commune', get label() { return i18n.t('constants:monumentOptions.proprietaire.public_commune'); } },
  { value: 'public_epci', get label() { return i18n.t('constants:monumentOptions.proprietaire.public_epci'); } },
  { value: 'public_departement', get label() { return i18n.t('constants:monumentOptions.proprietaire.public_departement'); } },
  { value: 'public_region', get label() { return i18n.t('constants:monumentOptions.proprietaire.public_region'); } },
  { value: 'public_etat', get label() { return i18n.t('constants:monumentOptions.proprietaire.public_etat'); } },
  { value: 'syndicat_mixte', get label() { return i18n.t('constants:monumentOptions.proprietaire.syndicat_mixte'); } },
  { value: 'prive_personne_physique', get label() { return i18n.t('constants:monumentOptions.proprietaire.prive_personne_physique'); } },
  { value: 'prive_sci', get label() { return i18n.t('constants:monumentOptions.proprietaire.prive_sci'); } },
  { value: 'association', get label() { return i18n.t('constants:monumentOptions.proprietaire.association'); } },
  { value: 'mixte', get label() { return i18n.t('constants:monumentOptions.proprietaire.mixte'); } },
] as const;

export const ETATS_CONSERVATION = [
  { value: 'bon', get label() { return i18n.t('constants:monumentOptions.etatsConservation.bon'); } },
  { value: 'moyen', get label() { return i18n.t('constants:monumentOptions.etatsConservation.moyen'); } },
  { value: 'mauvais', get label() { return i18n.t('constants:monumentOptions.etatsConservation.mauvais'); } },
  { value: 'peril', get label() { return i18n.t('constants:monumentOptions.etatsConservation.peril'); } },
] as const;

export type EtatConservation = (typeof ETATS_CONSERVATION)[number]['value'];

/**
 * Natures du bien (`monuments.type_edifice`, choix multiple). Miroir de `TYPE_EDIFICE_LABELS`
 * ([backend/labels.py]), même ordre : `tests/test_type_edifice.py` compare les
 * codes, et le CHECK SQL refuse tout autre code. Le moteur en déduit les
 * réponses aux questions sur la nature de l'édifice (est-ce une église ? un
 * monument aux morts ?), qui ne sont alors plus posées. Les regroupements du
 * menu sont dans `lib/fiche-monument.ts`.
 */
export const TYPES_EDIFICE = [
  { value: 'eglise', get label() { return i18n.t('constants:monumentOptions.typesEdifice.eglise'); } },
  { value: 'chapelle', get label() { return i18n.t('constants:monumentOptions.typesEdifice.chapelle'); } },
  { value: 'abbaye_couvent', get label() { return i18n.t('constants:monumentOptions.typesEdifice.abbaye_couvent'); } },
  { value: 'temple', get label() { return i18n.t('constants:monumentOptions.typesEdifice.temple'); } },
  { value: 'synagogue', get label() { return i18n.t('constants:monumentOptions.typesEdifice.synagogue'); } },
  { value: 'croix_calvaire', get label() { return i18n.t('constants:monumentOptions.typesEdifice.croix_calvaire'); } },
  { value: 'autre_religieux', get label() { return i18n.t('constants:monumentOptions.typesEdifice.autre_religieux'); }, get hint() { return i18n.t('constants:monumentOptions.typesEdificeIndices.autre_religieux'); } },
  { value: 'chateau', get label() { return i18n.t('constants:monumentOptions.typesEdifice.chateau'); } },
  { value: 'manoir_demeure', get label() { return i18n.t('constants:monumentOptions.typesEdifice.manoir_demeure'); } },
  { value: 'hotel_particulier', get label() { return i18n.t('constants:monumentOptions.typesEdifice.hotel_particulier'); } },
  { value: 'maison', get label() { return i18n.t('constants:monumentOptions.typesEdifice.maison'); }, get hint() { return i18n.t('constants:monumentOptions.typesEdificeIndices.maison'); } },
  { value: 'edifice_public', get label() { return i18n.t('constants:monumentOptions.typesEdifice.edifice_public'); }, get hint() { return i18n.t('constants:monumentOptions.typesEdificeIndices.edifice_public'); } },
  { value: 'hopital', get label() { return i18n.t('constants:monumentOptions.typesEdifice.hopital'); } },
  { value: 'halle', get label() { return i18n.t('constants:monumentOptions.typesEdifice.halle'); } },
  { value: 'patrimoine_industriel', get label() { return i18n.t('constants:monumentOptions.typesEdifice.patrimoine_industriel'); }, get hint() { return i18n.t('constants:monumentOptions.typesEdificeIndices.patrimoine_industriel'); } },
  { value: 'ferme', get label() { return i18n.t('constants:monumentOptions.typesEdifice.ferme'); } },
  { value: 'moulin', get label() { return i18n.t('constants:monumentOptions.typesEdifice.moulin'); } },
  { value: 'lavoir_fontaine', get label() { return i18n.t('constants:monumentOptions.typesEdifice.lavoir_fontaine'); } },
  { value: 'pigeonnier', get label() { return i18n.t('constants:monumentOptions.typesEdifice.pigeonnier'); } },
  { value: 'petit_patrimoine', get label() { return i18n.t('constants:monumentOptions.typesEdifice.petit_patrimoine'); }, get hint() { return i18n.t('constants:monumentOptions.typesEdificeIndices.petit_patrimoine'); } },
  { value: 'fortification', get label() { return i18n.t('constants:monumentOptions.typesEdifice.fortification'); } },
  { value: 'pont', get label() { return i18n.t('constants:monumentOptions.typesEdifice.pont'); } },
  { value: 'jardin', get label() { return i18n.t('constants:monumentOptions.typesEdifice.jardin'); } },
  { value: 'site_archeologique', get label() { return i18n.t('constants:monumentOptions.typesEdifice.site_archeologique'); } },
  { value: 'monument_aux_morts', get label() { return i18n.t('constants:monumentOptions.typesEdifice.monument_aux_morts'); } },
  { value: 'monument_commemoratif', get label() { return i18n.t('constants:monumentOptions.typesEdifice.monument_commemoratif'); } },
  { value: 'autre', get label() { return i18n.t('constants:monumentOptions.typesEdifice.autre'); }, get hint() { return i18n.t('constants:monumentOptions.typesEdificeIndices.autre'); } },
] as const;

export type TypeEdifice = (typeof TYPES_EDIFICE)[number]['value'];


export const URGENCE_TRAVAUX = [
  { value: 'faible', get label() { return i18n.t('constants:monumentOptions.urgence.faible'); } },
  { value: 'moyenne', get label() { return i18n.t('constants:monumentOptions.urgence.moyenne'); } },
  { value: 'haute', get label() { return i18n.t('constants:monumentOptions.urgence.haute'); } },
  { value: 'critique', get label() { return i18n.t('constants:monumentOptions.urgence.critique'); } },
] as const;

/**
 * Les types de travaux de l'étape « Sur quoi portent les travaux ? », rangés
 * sous six intertitres (`groupe`). L'ORDRE suit `TRAVAUX_LABELS`
 * ([backend/labels.py]), que `tests/test_types_travaux.py` compare code à code ;
 * l'écran regroupe dans l'ordre de première apparition de chaque groupe. Pas
 * de précision par case : le libellé seul doit suffire.
 */
export const WORK_TYPES = [
  { value: 'charpente', get label() { return i18n.t('constants:monumentOptions.travaux.charpente'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.closEtCouvert'); } },
  { value: 'couverture', get label() { return i18n.t('constants:monumentOptions.travaux.couverture'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.closEtCouvert'); } },
  { value: 'facade', get label() { return i18n.t('constants:monumentOptions.travaux.facade'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.closEtCouvert'); } },
  { value: 'maconnerie', get label() { return i18n.t('constants:monumentOptions.travaux.maconnerie'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.closEtCouvert'); } },
  { value: 'vitraux', get label() { return i18n.t('constants:monumentOptions.travaux.vitraux'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.decorsEtObjets'); } },
  { value: 'peintures_murales', get label() { return i18n.t('constants:monumentOptions.travaux.peintures_murales'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.decorsEtObjets'); } },
  { value: 'menuiserie', get label() { return i18n.t('constants:monumentOptions.travaux.menuiserie'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.closEtCouvert'); } },
  { value: 'electricite', get label() { return i18n.t('constants:monumentOptions.travaux.electricite'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.installationsTechniques'); } },
  { value: 'plomberie', get label() { return i18n.t('constants:monumentOptions.travaux.plomberie'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.installationsTechniques'); } },
  { value: 'chauffage', get label() { return i18n.t('constants:monumentOptions.travaux.chauffage'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.installationsTechniques'); } },
  { value: 'accessibilite', get label() { return i18n.t('constants:monumentOptions.travaux.accessibilite'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.installationsTechniques'); } },
  { value: 'mise_en_securite', get label() { return i18n.t('constants:monumentOptions.travaux.mise_en_securite'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.installationsTechniques'); } },
  { value: 'etude_prealable', get label() { return i18n.t('constants:monumentOptions.travaux.etude_prealable'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.etudes'); } },
  { value: 'mobilier', get label() { return i18n.t('constants:monumentOptions.travaux.mobilier'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.decorsEtObjets'); } },
  { value: 'archives', get label() { return i18n.t('constants:monumentOptions.travaux.archives'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.decorsEtObjets'); } },
  { value: 'orgues', get label() { return i18n.t('constants:monumentOptions.travaux.orgues'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.decorsEtObjets'); } },
  { value: 'parcs_jardins', get label() { return i18n.t('constants:monumentOptions.travaux.parcs_jardins'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.abordsEtDomaine'); } },
  { value: 'protection_solaire', get label() { return i18n.t('constants:monumentOptions.travaux.protection_solaire'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.closEtCouvert'); } },
  { value: 'ventilation', get label() { return i18n.t('constants:monumentOptions.travaux.ventilation'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.installationsTechniques'); } },
  // Le DOMAINE autour du bâti. Miroir de `TRAVAUX_LABELS` ([backend/labels.py]) :
  // un code présent d'un seul côté rend invisibles les aides qui s'y cadrent —
  // l'utilisateur ne pourrait jamais le cocher.
  { value: 'exploitation_agricole', get label() { return i18n.t('constants:monumentOptions.travaux.exploitation_agricole'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.abordsEtDomaine'); } },
  { value: 'foret', get label() { return i18n.t('constants:monumentOptions.travaux.foret'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.abordsEtDomaine'); } },
  { value: 'eau_milieux_aquatiques', get label() { return i18n.t('constants:monumentOptions.travaux.eau_milieux_aquatiques'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.abordsEtDomaine'); } },
  { value: 'equipement_numerique', get label() { return i18n.t('constants:monumentOptions.travaux.equipement_numerique'); }, get groupe() { return i18n.t('constants:monumentOptions.groupesTravaux.equipement'); } },
] as const;

export const MATERIAUX = [
  { value: 'pierre', get label() { return i18n.t('constants:monumentOptions.materiaux.pierre'); } },
  { value: 'brique', get label() { return i18n.t('constants:monumentOptions.materiaux.brique'); } },
  { value: 'bois', get label() { return i18n.t('constants:monumentOptions.materiaux.bois'); } },
  { value: 'ardoise', get label() { return i18n.t('constants:monumentOptions.materiaux.ardoise'); } },
  { value: 'tuile', get label() { return i18n.t('constants:monumentOptions.materiaux.tuile'); } },
  { value: 'lauze', get label() { return i18n.t('constants:monumentOptions.materiaux.lauze'); } },
  { value: 'chaume', get label() { return i18n.t('constants:monumentOptions.materiaux.chaume'); } },
  { value: 'zinc', get label() { return i18n.t('constants:monumentOptions.materiaux.zinc'); } },
  { value: 'plomb', get label() { return i18n.t('constants:monumentOptions.materiaux.plomb'); } },
  { value: 'verre', get label() { return i18n.t('constants:monumentOptions.materiaux.verre'); } },
  { value: 'metal', get label() { return i18n.t('constants:monumentOptions.materiaux.metal'); } },
  { value: 'torchis', get label() { return i18n.t('constants:monumentOptions.materiaux.torchis'); } },
  { value: 'enduit', get label() { return i18n.t('constants:monumentOptions.materiaux.enduit'); } },
  { value: 'autre', get label() { return i18n.t('constants:monumentOptions.materiaux.autre'); } },
] as const;

export const TYPES_COUVERTURE = [
  { value: 'toit à longs pans', get label() { return i18n.t('constants:monumentOptions.couvertures.toitALongsPans'); } },
  { value: 'toit à un pan', get label() { return i18n.t('constants:monumentOptions.couvertures.toitAUnPan'); } },
  { value: 'croupe', get label() { return i18n.t('constants:monumentOptions.couvertures.croupe'); } },
  { value: 'demi-croupe', get label() { return i18n.t('constants:monumentOptions.couvertures.demiCroupe'); } },
  { value: 'croupe ronde', get label() { return i18n.t('constants:monumentOptions.couvertures.croupeRonde'); } },
  { value: 'pavillon', get label() { return i18n.t('constants:monumentOptions.couvertures.pavillon'); } },
  { value: 'toit brisé', get label() { return i18n.t('constants:monumentOptions.couvertures.toitBrise'); } },
  { value: 'toit brisé à longs pans', get label() { return i18n.t('constants:monumentOptions.couvertures.toitBriseALongsPans'); } },
  { value: 'toit brisé en pavillon', get label() { return i18n.t('constants:monumentOptions.couvertures.toitBriseEnPavillon'); } },
  { value: 'flèche', get label() { return i18n.t('constants:monumentOptions.couvertures.fleche'); } },
  { value: 'flèche polygonale', get label() { return i18n.t('constants:monumentOptions.couvertures.flechePolygonale'); } },
  { value: 'flèche carrée', get label() { return i18n.t('constants:monumentOptions.couvertures.flecheCarree'); } },
  { value: 'dôme', get label() { return i18n.t('constants:monumentOptions.couvertures.dome'); } },
  { value: 'dôme à pans', get label() { return i18n.t('constants:monumentOptions.couvertures.domeAPans'); } },
  { value: 'coupole', get label() { return i18n.t('constants:monumentOptions.couvertures.coupole'); } },
  { value: 'bulbe', get label() { return i18n.t('constants:monumentOptions.couvertures.bulbe'); } },
  { value: 'toit en carène', get label() { return i18n.t('constants:monumentOptions.couvertures.toitEnCarene'); } },
  { value: 'terrasse', get label() { return i18n.t('constants:monumentOptions.couvertures.terrasse'); } },
  { value: 'comble à la mansart', get label() { return i18n.t('constants:monumentOptions.couvertures.combleALaMansart'); } },
  { value: 'pignon couvert', get label() { return i18n.t('constants:monumentOptions.couvertures.pignonCouvert'); } },
  { value: 'pignon découvert', get label() { return i18n.t('constants:monumentOptions.couvertures.pignonDecouvert'); } },
  { value: 'noue', get label() { return i18n.t('constants:monumentOptions.couvertures.noue'); } },
  { value: 'appentis', get label() { return i18n.t('constants:monumentOptions.couvertures.appentis'); } },
  { value: 'shed', get label() { return i18n.t('constants:monumentOptions.couvertures.shed'); } },
  { value: 'flèche de haut-clocher', get label() { return i18n.t('constants:monumentOptions.couvertures.flecheDeHautClocher'); } },
] as const;

export const AFFECTATAIRES = [
  { value: 'culte', get label() { return i18n.t('constants:monumentOptions.affectataires.culte'); } },
  { value: 'mairie', get label() { return i18n.t('constants:monumentOptions.affectataires.mairie'); } },
  { value: 'habitation', get label() { return i18n.t('constants:monumentOptions.affectataires.habitation'); } },
  { value: 'musee', get label() { return i18n.t('constants:monumentOptions.affectataires.musee'); } },
  { value: 'tourisme', get label() { return i18n.t('constants:monumentOptions.affectataires.tourisme'); } },
  { value: 'enseignement', get label() { return i18n.t('constants:monumentOptions.affectataires.enseignement'); } },
  { value: 'commercial', get label() { return i18n.t('constants:monumentOptions.affectataires.commercial'); } },
  { value: 'non_affecte', get label() { return i18n.t('constants:monumentOptions.affectataires.non_affecte'); } },
  { value: 'autre', get label() { return i18n.t('constants:monumentOptions.affectataires.autre'); } },
] as const;

// Lookup tables keyed by stored value. Long form for detail panels, short form
// for compact badges (e.g. the project summary bar).
export const PROTECTION_LABELS: Record<string, string> = {
  get classe() { return i18n.t('constants:monumentOptions.protectionLongue.classe'); },
  get inscrit() { return i18n.t('constants:monumentOptions.protectionLongue.inscrit'); },
  get abords() { return i18n.t('constants:monumentOptions.protectionLongue.abords'); },
  get spr() { return i18n.t('constants:monumentOptions.protectionLongue.spr'); },
  get non_protege() { return i18n.t('constants:monumentOptions.protectionLongue.non_protege'); },
};

export const PROTECTION_LABELS_SHORT: Record<string, string> = {
  get classe() { return i18n.t('constants:monumentOptions.protectionCourte.classe'); },
  get inscrit() { return i18n.t('constants:monumentOptions.protectionCourte.inscrit'); },
  get abords() { return i18n.t('constants:monumentOptions.protectionCourte.abords'); },
  get spr() { return i18n.t('constants:monumentOptions.protectionCourte.spr'); },
  get non_protege() { return i18n.t('constants:monumentOptions.protectionCourte.non_protege'); },
};

/**
 * Miroir de `ETAT_LABELS` côté backend (labels.py), qui borne les valeurs
 * admises en base et dans `hard_filters.etats_conservation`.
 */
export const ETAT_LABELS: Record<string, string> = {
  get bon() { return i18n.t('constants:monumentOptions.etatsConservation.bon'); },
  get moyen() { return i18n.t('constants:monumentOptions.etatsConservation.moyen'); },
  get mauvais() { return i18n.t('constants:monumentOptions.etatsConservation.mauvais'); },
  get peril() { return i18n.t('constants:monumentOptions.etatsConservation.peril'); },
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
  if (peril === null) return null;
  return peril
    ? i18n.t('constants:monumentOptions.peril.enPeril')
    : i18n.t('constants:monumentOptions.peril.pasEnPeril');
}
