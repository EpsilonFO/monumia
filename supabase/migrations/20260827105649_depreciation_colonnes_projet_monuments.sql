-- Suite de 20260827105636_creation_table_projets : le cadrage de chantier vit
-- désormais dans `projets`, ces trois colonnes de `monuments` n'ont plus de
-- lecteur.
--
-- Fichier séparé exprès (même pratique que 20260516174303) : le drop rend
-- bruyant — PGRST204 à l'écriture, colonne absente à la lecture — tout chemin
-- de code oublié. Il peut être différé d'une vague pour une fenêtre zéro-casse,
-- au prix de trois colonnes mortes en base.
--
-- `etat_conservation` RESTE sur le monument : la question « en péril ? » décrit
-- le bien, pas le chantier, et tous ses projets la partagent (fiche sanitaire).

alter table public.monuments
    drop column if exists questionnaire,
    drop column if exists travaux_envisages,
    drop column if exists cloture_at;
