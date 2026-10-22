import i18n from '@/i18n';

/**
 * Libellés d'affichage des énumérations d'aides.
 *
 * Les `value` doivent rester le miroir EXACT des tuples `CATEGORIES` et `TYPES`
 * de [aides_schema.py](backend/aides_schema.py) : elles viennent des YAML et
 * traversent le moteur sans transformation. Un `value` qui ne correspond à rien
 * ne casse pas l'affichage — il le dégrade en silence, en montrant le slug brut
 * à la place du libellé.
 */
export const AIDE_CATEGORIES = [
  { value: 'etat_drac', get label() { return i18n.t('constants:aideCategories.categories.etat_drac'); }, color: 'bg-info-muted text-info' },
  { value: 'region', get label() { return i18n.t('constants:aideCategories.categories.region'); }, color: 'bg-cat-violet-soft text-cat-violet' },
  { value: 'departement', get label() { return i18n.t('constants:aideCategories.categories.departement'); }, color: 'bg-cat-10-soft text-cat-10' },
  { value: 'fondation', get label() { return i18n.t('constants:aideCategories.categories.fondation'); }, color: 'bg-warning-muted text-warning' },
  { value: 'europe', get label() { return i18n.t('constants:aideCategories.categories.europe'); }, color: 'bg-cat-1-soft text-cat-1' },
  { value: 'mecenat', get label() { return i18n.t('constants:aideCategories.categories.mecenat'); }, color: 'bg-cat-2-soft text-cat-2' },
  { value: 'fiscalite', get label() { return i18n.t('constants:aideCategories.categories.fiscalite'); }, color: 'bg-success-muted text-success' },
  { value: 'autre', get label() { return i18n.t('constants:aideCategories.categories.autre'); }, color: 'bg-muted text-muted-foreground' },
] as const;

export const AIDE_TYPES = [
  { value: 'subvention', get label() { return i18n.t('constants:aideCategories.types.subvention'); } },
  { value: 'appel_a_projets', get label() { return i18n.t('constants:aideCategories.types.appel_a_projets'); } },
  { value: 'pret', get label() { return i18n.t('constants:aideCategories.types.pret'); } },
  { value: 'deduction_fiscale', get label() { return i18n.t('constants:aideCategories.types.deduction_fiscale'); } },
  { value: 'exoneration', get label() { return i18n.t('constants:aideCategories.types.exoneration'); } },
  { value: 'label', get label() { return i18n.t('constants:aideCategories.types.label'); } },
  { value: 'mecenat', get label() { return i18n.t('constants:aideCategories.types.mecenat'); } },
  { value: 'souscription', get label() { return i18n.t('constants:aideCategories.types.souscription'); } },
] as const;
