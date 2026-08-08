-- Faits à choix MULTIPLE (`multi_enum`) — miroir de backend/data/facts.yaml.
--
-- Deux questions du QCM admettent plusieurs réponses simultanées : les usages
-- du bâtiment (habité ET ouvert à la visite) et les entités susceptibles de
-- déposer une demande (on dépose sous l'association pour une aide réservée aux
-- associations, en nom propre pour une autre). Le type existe côté YAML
-- (aides_schema.FactDef) ; la table `facts`, alimentée par
-- backend/scripts/load_aides_yaml.py, refusait la valeur.

alter table public.facts drop constraint if exists facts_type_check;

alter table public.facts
    add constraint facts_type_check
    check (type in ('boolean', 'integer', 'number', 'enum', 'multi_enum'));
