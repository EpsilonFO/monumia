-- Rattachement intercommunal des communes (EPCI à fiscalité propre).
--
-- Les aides intercommunales bornent leur territoire par le SIREN de l'EPCI
-- porteur (ex. CC Moret Seine et Loing = 247700032) : la condition typée
-- `field: commune.epci` du moteur déterministe n'avait jusqu'ici aucune source
-- de données, donc restait en incertitude fail-closed pour toutes les communes.
--
-- `epci_siren` est le SIREN à 9 chiffres du référentiel BANATIC, celui-là même
-- que les règlements d'aide et le champ commune.epci du FIELD_REGISTRY
-- utilisent. `epci_nom` n'a qu'un rôle d'affichage / debug.
--
-- Nullable : ~98 communes n'appartiennent à aucun EPCI à fiscalité propre
-- (îles mono-communales, Paris hors MGP historique). Un NULL doit rester
-- distinguable d'un 0 — l'absence de rattachement est une donnée, pas un trou.

alter table public.communes
  add column if not exists epci_siren text,
  add column if not exists epci_nom text;

-- Le prédicat `eq` du moteur compare une commune à un SIREN : lookup par
-- code_insee (déjà la PK). L'index sert le sens inverse — lister les communes
-- d'un EPCI, utile aux scripts de contrôle et aux futurs filtres territoriaux.
create index if not exists idx_communes_epci_siren
  on public.communes (epci_siren);
