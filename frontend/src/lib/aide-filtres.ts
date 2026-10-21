import i18n from '@/i18n';
import type { AideCategory, AideMatchResult } from '@/types';

/**
 * Filtres de financeur sur la liste d'aides d'un projet.
 *
 * Ce ne sont PAS les catégories brutes du catalogue : « Prix et mécènes »
 * rassemble les fondations et le mécénat, deux catégories distinctes en base
 * mais une seule et même chose pour un propriétaire — de l'argent privé, qu'on
 * demande par candidature plutôt que par guichet. Les collectivités, elles,
 * restent séparées : c'est le premier tri que fait un porteur de projet.
 *
 * Le groupe est donc une notion de PRODUIT, indépendante du découpage
 * administratif du catalogue. D'où cette table, plutôt qu'un filtre direct sur
 * `aide.categorie`.
 */
export type AideFiltreKey =
  | 'toutes'
  | 'etat'
  | 'region'
  | 'departement'
  | 'prix_mecenat'
  | 'europe'
  | 'fiscalite'
  | 'autre';

export interface AideFiltre {
  key: AideFiltreKey;
  label: string;
  /** Catégories du catalogue rassemblées sous ce libellé. Vide = tout. */
  categories: AideCategory[];
}

/**
 * Ordre d'affichage : « Toutes » d'abord, puis du financeur le plus courant au
 * plus rare (région et département portent 120 des ~180 aides du catalogue).
 * L'ordre est fixe et ne suit PAS les comptes du diagnostic courant : une barre
 * dont les onglets se réordonnent d'un projet à l'autre est illisible.
 */
// Libellés en getters : lus au rendu, jamais figés à l'import.
export const AIDE_FILTRES: AideFiltre[] = [
  { key: 'toutes', get label() { return i18n.t('libAides:aideFiltres.toutes'); }, categories: [] },
  { key: 'prix_mecenat', get label() { return i18n.t('libAides:aideFiltres.prixMecenat'); }, categories: ['fondation', 'mecenat'] },
  { key: 'region', get label() { return i18n.t('libAides:aideFiltres.region'); }, categories: ['region'] },
  { key: 'departement', get label() { return i18n.t('libAides:aideFiltres.departement'); }, categories: ['departement'] },
  { key: 'etat', get label() { return i18n.t('libAides:aideFiltres.etat'); }, categories: ['etat_drac'] },
  { key: 'europe', get label() { return i18n.t('libAides:aideFiltres.europe'); }, categories: ['europe'] },
  { key: 'fiscalite', get label() { return i18n.t('libAides:aideFiltres.fiscalite'); }, categories: ['fiscalite'] },
  { key: 'autre', get label() { return i18n.t('libAides:aideFiltres.autre'); }, categories: ['autre'] },
];

/** Une aide entre-t-elle dans ce groupe ? « toutes » accepte tout. */
export function matchFiltre(match: AideMatchResult, filtre: AideFiltre): boolean {
  if (filtre.categories.length === 0) return true;
  return filtre.categories.includes(match.aide.categorie);
}

export function filtrerAides(aides: AideMatchResult[], filtre: AideFiltre): AideMatchResult[] {
  if (filtre.categories.length === 0) return aides;
  return aides.filter((m) => matchFiltre(m, filtre));
}

export interface AideFiltreOption extends AideFiltre {
  count: number;
}

/**
 * Les filtres à afficher, comptés sur l'ensemble des aides du projet.
 *
 * Un groupe vide n'est pas affiché : proposer « Europe (0) » à quelqu'un dont
 * aucune aide n'est européenne ajoute un choix qui ne mène nulle part. Le
 * groupe actuellement sélectionné est conservé même vide, sinon la barre
 * perdrait sous les doigts l'onglet qu'on vient de choisir.
 *
 * « Toutes les aides » ne sort que s'il y a au moins deux groupes à départager :
 * seul, il ne filtre rien.
 */
export function filtresDisponibles(
  aides: AideMatchResult[],
  selection: AideFiltreKey,
): AideFiltreOption[] {
  const options = AIDE_FILTRES.map((filtre) => ({
    ...filtre,
    count: filtre.categories.length === 0 ? aides.length : filtrerAides(aides, filtre).length,
  })).filter((o) => o.count > 0 || o.key === selection);

  const groupes = options.filter((o) => o.key !== 'toutes');
  return groupes.length > 1 ? options : [];
}
