-- L'état de conservation n'est plus demandé à la création de la fiche monument :
-- il est renseigné à l'étape « Votre projet » du wizard, après la création, par
-- la question « le monument est-il en péril ? ». La colonne doit donc tolérer
-- l'absence de valeur entre les deux.
--
-- Le moteur déterministe traite déjà `null` comme une incertitude fail-closed
-- (aide « potentiellement éligible » + question), jamais comme une élimination.

alter table public.monuments alter column etat_conservation drop not null;
