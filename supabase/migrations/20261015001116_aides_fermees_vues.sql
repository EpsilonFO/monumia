-- Aides fermées déjà expliquées, par compte (2026-10-15).
--
-- Une aide que son guide ne liste plus et dont la page est morte sort du
-- catalogue sans case (`backend/catalogue/sorties.py`). Qui y travaillait
-- (un dossier, un suivi) voit au premier clic un panneau qui explique la
-- fermeture ; ensuite ses dossiers en préparation sur cette aide ne
-- s'affichent plus pour lui (`backend/services/aides_fermees.py`). Une demande
-- déjà déposée reste toujours visible.
--
-- La clé est le slug de l'aide, la valeur la date où le panneau a été lu.
-- Écrite par `POST /aides/{slug}/fermee-vue`. Patron de `guides_vus`.

alter table public.users
  add column if not exists aides_fermees_vues jsonb not null default '{}'::jsonb;
