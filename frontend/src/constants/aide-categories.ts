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
  { value: 'etat_drac', label: 'État (DRAC)', color: 'bg-info-muted text-info' },
  { value: 'region', label: 'Région', color: 'bg-cat-violet-soft text-cat-violet' },
  { value: 'departement', label: 'Département', color: 'bg-cat-10-soft text-cat-10' },
  { value: 'fondation', label: 'Fondation', color: 'bg-warning-muted text-warning' },
  { value: 'europe', label: 'Europe', color: 'bg-cat-1-soft text-cat-1' },
  { value: 'mecenat', label: 'Mécénat', color: 'bg-cat-2-soft text-cat-2' },
  { value: 'fiscalite', label: 'Fiscalité', color: 'bg-success-muted text-success' },
  { value: 'autre', label: 'Autre', color: 'bg-muted text-muted-foreground' },
] as const;

export const AIDE_TYPES = [
  { value: 'subvention', label: 'Subvention' },
  { value: 'appel_a_projets', label: 'Appel à projets' },
  { value: 'pret', label: 'Prêt' },
  { value: 'deduction_fiscale', label: 'Déduction fiscale' },
  { value: 'exoneration', label: 'Exonération' },
  { value: 'label', label: 'Label' },
  { value: 'mecenat', label: 'Mécénat' },
  { value: 'souscription', label: 'Souscription publique' },
] as const;
