-- Domaine Mérimée du bien, recopié sur le monument (2026-10-06).
--
-- La précision « architecture romane » de la fiche n'est proposée qu'aux biens
-- dont le domaine Mérimée contient « architecture religieuse » (valeur seule ou
-- combinée : « architecture religieuse;architecture militaire »). Le formulaire,
-- le router et le moteur doivent tous le connaître : le garder sur la ligne
-- évite une jointure à chaque diagnostic.
--
-- Rempli par le serveur seul, depuis `merimee_buildings`, à la création et
-- quand `reference_merimee` change (cf. routers/monuments.py). Jamais par le
-- client. NULL pour un bien saisi à la main ou une notice sans domaine.

alter table public.monuments
  add column if not exists merimee_domaine text;

update public.monuments m
   set merimee_domaine = mb.domaine
  from public.merimee_buildings mb
 where mb.reference = m.reference_merimee
   and m.merimee_domaine is distinct from mb.domaine;
