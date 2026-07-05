-- Restrict aides_v3.categorie and aides_v3.type to a fixed set of allowed values.
--
-- Garde d'existence : ce fichier est horodaté AVANT la création d'aides_v3
-- (20260515125542), qui déclare déjà ces mêmes contraintes. Sur une base
-- vierge il doit donc être un no-op ; il ne s'applique qu'aux bases où la
-- table préexistait aux migrations.

do $$
begin
  if to_regclass('public.aides_v3') is null then
    return;
  end if;

  alter table public.aides_v3
    drop constraint if exists aides_v3_categorie_check;

  alter table public.aides_v3
    add constraint aides_v3_categorie_check
    check (categorie in (
      'etat_drac',
      'departement',
      'fiscalite',
      'europe',
      'mecenat',
      'fondation',
      'region',
      'autre'
    ));

  alter table public.aides_v3
    drop constraint if exists aides_v3_type_check;

  alter table public.aides_v3
    add constraint aides_v3_type_check
    check (type in (
      'label',
      'appel_a_projets',
      'exoneration',
      'mecenat',
      'souscription',
      'pret',
      'deduction_fiscale',
      'subvention'
    ));
end $$;
