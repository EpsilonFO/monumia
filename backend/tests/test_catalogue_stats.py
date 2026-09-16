"""Statistiques du catalogue : la portée d'une aide, son rattachement
territorial, la liste qu'on déplie, et l'écart avec `aides_v3`.

Deux familles de tests, et la seconde est la plus importante :

- sur un CORPUS FABRIQUÉ, pour figer les règles de comptage : les quatre
  échelons sont disjoints et somment au corpus, une aide de Région limitée à
  quelques départements reste une aide de Région, une retirée sort de tout ;
- sur le CORPUS RÉEL, pour vérifier que rien ne se perd — la table
  `REGION_DEPARTEMENTS` couvre exactement les départements que le schéma des
  aides accepte, et chaque slug listé a bien sa fiche dans l'index. Un
  département oublié dans le rattachement ne casserait rien : il rendrait juste
  une région trop maigre, sans un mot.
"""

import unittest
from unittest.mock import patch

from aides_schema import Aide, load_all_aides
from labels import DEPARTEMENT_LABELS, DEPARTEMENT_REGION, REGION_DEPARTEMENTS, REGION_LABELS
from services import catalogue_admin as ca
from services import catalogue_stats as cs


def _aide(slug: str, **over) -> Aide:
    champs = {
        "slug": slug,
        "nom": f"Aide {slug}",
        "organisme": "Org",
        "categorie": "region",
        "type": "subvention",
        "description": "d",
    }
    champs.update(over)
    return Aide.model_validate(champs)


def _entree(aide: Aide, *, retiree=False) -> cs.Entree:
    return cs.Entree(aide=aide, retiree=retiree)


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _Query:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def select(self, *_a, **_k) -> "_Query":
        return self

    def execute(self) -> _Resp:
        return _Resp(list(self._rows))


class _FakeSupabase:
    def __init__(self, **tables) -> None:
        self._tables = tables

    def table(self, name: str) -> _Query:
        return _Query(self._tables.get(name, []))


class _SupabaseEnPanne:
    def table(self, _name: str):
        raise RuntimeError("relation « aides_v3 » inexistante")


class PorteeTests(unittest.TestCase):
    def test_sans_filtre_geographique_laide_est_nationale(self) -> None:
        self.assertEqual(_entree(_aide("a")).portee, "nationale")

    def test_une_region_rend_laide_regionale(self) -> None:
        entree = _entree(_aide("a", hard_filters={"regions": ["grand-est"]}))
        self.assertEqual(entree.portee, "region")

    def test_un_departement_rend_la_portee_departementale(self) -> None:
        entree = _entree(_aide("a", hard_filters={"departements": ["88"]}))
        self.assertEqual(entree.portee, "departement")

    def test_une_enumeration_plus_etroite_que_la_region_reste_departementale(self) -> None:
        """Deux départements du Grand Est sur dix : la liste restreint pour de
        bon, l'aide ne doit pas remonter sur les huit autres."""
        entree = _entree(
            _aide("a", hard_filters={"regions": ["grand-est"], "departements": ["88", "57"]})
        )
        self.assertEqual(entree.portee, "departement")

    def test_une_enumeration_couvrant_toute_la_region_reste_regionale(self) -> None:
        """Le cas le plus courant du corpus : un dispositif régional qui liste
        en plus tous les départements de sa région (colonne
        `aides_v3.departements`). La liste ne retire rien.

        Le lire comme départemental affichait « 0 régionale » sur
        Auvergne-Rhône-Alpes, et faisait passer dix appels à projets de la
        Région pour des aides de Conseil départemental.
        """
        entree = _entree(
            _aide(
                "a",
                hard_filters={
                    "regions": ["grand-est"],
                    "departements": REGION_DEPARTEMENTS["grand-est"],
                },
            )
        )
        self.assertEqual(entree.portee, "region")

    def test_une_enumeration_a_cheval_sur_deux_regions_reste_departementale(self) -> None:
        entree = _entree(
            _aide(
                "a",
                hard_filters={
                    "regions": ["grand-est", "bourgogne-franche-comte"],
                    "departements": REGION_DEPARTEMENTS["grand-est"],
                },
            )
        )
        self.assertEqual(entree.portee, "departement")

    def test_une_aide_departementale_appartient_a_sa_region(self) -> None:
        entree = _entree(_aide("a", hard_filters={"departements": ["88", "71"]}))
        self.assertEqual(entree.regions, {"grand-est", "bourgogne-franche-comte"})


class EchelonTests(unittest.TestCase):
    """Qui finance, et à quel étage. C'est `categorie` qui tranche, pas le
    périmètre : « les aides du département de l'Isère » veut dire celles du
    Conseil départemental, pas celles qui s'appliquent en Isère."""

    def test_une_aide_de_region_limitee_a_trois_departements_reste_regionale(self) -> None:
        """Le cas qui a motivé la reprise : ce dispositif remontait dans la
        liste de l'Isère comme s'il venait du Conseil départemental."""
        entree = _entree(
            _aide("montagne", categorie="region", hard_filters={"departements": ["38", "73", "74"]})
        )
        self.assertEqual(entree.echelon, "region")
        self.assertEqual(entree.regions, {"auvergne-rhone-alpes"})

    def test_une_fondation_a_perimetre_local_nest_ni_region_ni_departement(self) -> None:
        """Une délégation de fondation couvre huit départements sans qu'un euro
        vienne d'un Département : la compter là serait faux, et la cacher
        ferait disparaître vingt et une aides de la page."""
        entree = _entree(
            _aide("prix-public", categorie="fondation", hard_filters={"departements": ["38", "69"]})
        )
        self.assertEqual(entree.echelon, "autre")

    def test_une_aide_de_conseil_departemental(self) -> None:
        entree = _entree(
            _aide("cd", categorie="departement", hard_filters={"departements": ["88"]})
        )
        self.assertEqual(entree.echelon, "departement")

    def test_une_fondation_sans_filtre_geographique_est_nationale(self) -> None:
        self.assertEqual(_entree(_aide("loto", categorie="fondation")).echelon, "national")

    def test_une_collectivite_sans_territoire_retombe_sur_son_perimetre(self) -> None:
        """Garde-fou : sans ligne où l'accrocher, elle disparaîtrait de la page.
        Le corpus n'en contient aucune — c'est justement pour que ça reste vrai
        sans surveillance qu'on ne la laisse pas tomber dans le vide."""
        self.assertEqual(_entree(_aide("orpheline", categorie="departement")).echelon, "national")


class GroupeTests(unittest.TestCase):
    def test_une_retiree_sort_du_compte_de_la_liste_et_des_taux(self) -> None:
        groupe = cs._groupe(
            [
                _entree(_aide("a", financement={"taux_max": 20})),
                _entree(_aide("b", financement={"taux_max": 80}), retiree=True),
            ]
        )
        self.assertEqual(groupe["nb"], 1)
        self.assertEqual(groupe["slugs"], ["a"])
        self.assertEqual(groupe["tauxMax"], 20)

    def test_les_slugs_sortent_dans_lordre_des_noms(self) -> None:
        """C'est l'ordre du dépliant : le front n'a pas à retrier une liste que
        le serveur connaît déjà."""
        groupe = cs._groupe(
            [
                _entree(_aide("z", nom="Aide alpha")),
                _entree(_aide("a", nom="Zèbre")),
            ]
        )
        self.assertEqual(groupe["slugs"], ["z", "a"])

    def test_le_taux_retenu_est_le_maximum_sinon_le_minimum(self) -> None:
        groupe = cs._groupe(
            [
                _entree(_aide("a", financement={"taux_min": 15, "taux_max": 40})),
                _entree(_aide("b", financement={"taux_min": 30})),
            ]
        )
        self.assertEqual(groupe["tauxMin"], 15)
        self.assertEqual(groupe["tauxMax"], 40)
        self.assertEqual(groupe["tauxMedian"], 35)
        self.assertEqual(groupe["nbAvecTaux"], 2)

    def test_un_groupe_sans_chiffrage_rend_des_nuls_et_non_des_zeros(self) -> None:
        """Zéro dirait « taux nul » ; nul dit « la source ne chiffre pas »."""
        groupe = cs._groupe([_entree(_aide("a"))])
        self.assertIsNone(groupe["tauxMax"])
        self.assertIsNone(groupe["montantMedian"])
        self.assertEqual(groupe["nbAvecMontant"], 0)

    def test_groupe_vide(self) -> None:
        groupe = cs._groupe([])
        self.assertEqual((groupe["nb"], groupe["slugs"]), (0, []))
        self.assertIsNone(groupe["tauxMedian"])


class _CorpusFabrique(unittest.TestCase):
    """Le corpus est remplacé par cinq aides : les règles de comptage se lisent
    alors à l'œil nu. Pas de test ici — deux classes en héritent, et des tests
    hérités s'exécuteraient deux fois."""

    CORPUS = {
        "nationale": _aide("nationale", categorie="etat_drac"),
        "regionale": _aide("regionale", hard_filters={"regions": ["grand-est"]}),
        "vosges": _aide("vosges", categorie="departement", hard_filters={"departements": ["88"]}),
        "moselle": _aide("moselle", categorie="departement", hard_filters={"departements": ["57"]}),
        # Le piège : une aide RÉGIONALE qui liste en plus ses dix départements.
        "regionale-enumeree": _aide(
            "regionale-enumeree",
            hard_filters={
                "regions": ["grand-est"],
                "departements": REGION_DEPARTEMENTS["grand-est"],
            },
        ),
        # L'autre piège : une aide de la Région limitée à deux départements.
        "regionale-restreinte": _aide(
            "regionale-restreinte", hard_filters={"departements": ["88", "57"]}
        ),
        # Et le quatrième seau : un financeur sans échelon territorial.
        "fondation-locale": _aide(
            "fondation-locale", categorie="fondation", hard_filters={"departements": ["88"]}
        ),
    }

    def setUp(self) -> None:
        ca.invalider()
        self.patches = [
            patch.object(cs, "load_all_aides", lambda: self.CORPUS),
            patch.object(ca, "load_all_aides", lambda: self.CORPUS),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        ca.invalider()

    def _stats(self, **tables) -> dict:
        return cs.statistiques_catalogue(_FakeSupabase(**tables))

    def _region(self, stats: dict, code: str) -> dict:
        return next(r for r in stats["regions"] if r["code"] == code)

    def _departement(self, stats: dict, code: str) -> dict:
        return next(d for d in stats["departements"] if d["code"] == code)


class StatistiquesTests(_CorpusFabrique):
    def test_les_quatre_echelons_sont_disjoints_et_somment_au_corpus(self) -> None:
        """C'est ce qui rend les quatre chiffres de tête additionnables : une
        aide tombe dans exactement un seau."""
        corpus = self._stats()["corpus"]
        self.assertEqual(corpus["total"], 7)
        self.assertEqual(
            corpus["nationales"]
            + corpus["regionales"]
            + corpus["departementales"]
            + corpus["autres"],
            corpus["nb"],
        )
        self.assertEqual(
            (corpus["nationales"], corpus["regionales"], corpus["departementales"]), (1, 3, 2)
        )
        self.assertEqual(corpus["autres"], 1)

    def test_une_region_compte_les_aides_du_conseil_regional(self) -> None:
        """Les trois, quelle que soit l'écriture de leur périmètre : la région
        déclarée, l'énumération complète, et la restriction à deux
        départements. Cette dernière est le cas qui a motivé la reprise."""
        grand_est = self._region(self._stats(), "grand-est")
        self.assertEqual(grand_est["nb"], 3)
        self.assertIn("regionale-restreinte", grand_est["slugs"])

    def test_une_region_sans_aide_reste_dans_le_tableau(self) -> None:
        """Un zéro est une information de prospection, pas une ligne à cacher."""
        bretagne = self._region(self._stats(), "bretagne")
        self.assertEqual((bretagne["nb"], bretagne["slugs"]), (0, []))

    def test_un_departement_ne_compte_que_les_aides_de_son_conseil(self) -> None:
        """Les Vosges ont trois aides à leur périmètre — celle du Département,
        une de la Région, une de fondation — et une seule est « du
        département »."""
        stats = self._stats()
        self.assertEqual(self._departement(stats, "88")["slugs"], ["vosges"])
        self.assertEqual(self._departement(stats, "57")["slugs"], ["moselle"])
        self.assertEqual(self._departement(stats, "67")["nb"], 0)

    def test_un_financeur_sans_echelon_va_dans_le_quatrieme_seau(self) -> None:
        stats = self._stats()
        self.assertEqual(stats["autres"]["slugs"], ["fondation-locale"])
        self.assertNotIn("fondation-locale", self._departement(stats, "88")["slugs"])

    def test_une_aide_de_region_ne_tombe_jamais_dans_ses_departements(self) -> None:
        """Ni celle qui énumère toute la région, ni celle qui se restreint à
        deux départements : les deux sont sur la ligne de la Région."""
        vosges = self._departement(self._stats(), "88")
        self.assertNotIn("regionale-enumeree", vosges["slugs"])
        self.assertNotIn("regionale-restreinte", vosges["slugs"])
        self.assertEqual(vosges["regionLabel"], "Grand Est")

    def test_tous_les_departements_sont_listes(self) -> None:
        self.assertEqual(len(self._stats()["departements"]), len(DEPARTEMENT_LABELS))

    def test_une_aide_retiree_sort_des_comptes_et_des_listes(self) -> None:
        stats = self._stats(**{ca.TABLE_RETIREES: [{"slug": "vosges"}]})
        self.assertEqual(stats["corpus"]["nb"], 6)
        self.assertEqual(stats["corpus"]["retirees"], 1)
        self.assertEqual(self._departement(stats, "88")["slugs"], [])
        self.assertNotIn("vosges", stats["aides"])

    def test_chaque_slug_liste_a_son_nom_dans_lindex(self) -> None:
        """L'index est envoyé une fois, les groupes ne portent que des slugs :
        un slug sans nom afficherait une ligne vide dans le dépliant."""
        stats = self._stats()
        groupes = [stats["national"], stats["autres"], *stats["regions"], *stats["departements"]]
        for groupe in groupes:
            for slug in groupe["slugs"]:
                self.assertIn(slug, stats["aides"])

    def test_lindex_ne_porte_que_le_nom(self) -> None:
        """Le dépliant n'affiche rien d'autre : tout champ en plus serait du
        poids envoyé à chaque rafraîchissement pour rien."""
        self.assertEqual(self._stats()["aides"]["nationale"], "Aide nationale")

    def test_les_categories_couvrent_le_corpus(self) -> None:
        stats = self._stats()
        self.assertEqual(sum(c["nb"] for c in stats["categories"]), stats["corpus"]["nb"])
        drac = next(c for c in stats["categories"] if c["code"] == "etat_drac")
        self.assertEqual((drac["nb"], drac["label"]), (1, "État (DRAC)"))

    def test_les_types_couvrent_le_corpus(self) -> None:
        stats = self._stats()
        self.assertEqual(sum(t["nb"] for t in stats["types"]), stats["corpus"]["nb"])


class SynchronisationTests(_CorpusFabrique):
    def test_les_slugs_absents_daides_v3_sont_signales(self) -> None:
        """Le symptôme en production : le diagnostic propose l'aide, la
        création de dossier répond « Aide introuvable »."""
        presentes = ["nationale", "regionale", "regionale-enumeree", "regionale-restreinte"]
        sync = self._stats(aides_v3=[{"slug": s} for s in presentes])["synchronisation"]
        self.assertTrue(sync["lisible"])
        self.assertEqual(sync["enBase"], 4)
        self.assertEqual(sync["manquantes"], ["fondation-locale", "moselle", "vosges"])

    def test_une_aide_retiree_nest_pas_reclamee_en_base(self) -> None:
        """Elle répond 404 partout de toute façon : la réclamer enverrait
        chercher une panne inexistante."""
        presentes = [
            "nationale",
            "regionale",
            "regionale-enumeree",
            "regionale-restreinte",
            "fondation-locale",
            "moselle",
        ]
        sync = self._stats(
            aides_v3=[{"slug": s} for s in presentes],
            **{ca.TABLE_RETIREES: [{"slug": "vosges"}]},
        )["synchronisation"]
        self.assertEqual(sync["nbManquantes"], 0)

    def test_une_base_illisible_retire_le_bloc_au_lieu_de_tout_reclamer(self) -> None:
        sync = cs._synchronisation(_SupabaseEnPanne(), ["a", "b"])
        self.assertFalse(sync["lisible"])
        self.assertEqual(sync["nbManquantes"], 0)

    def test_la_liste_des_manquantes_est_bornee(self) -> None:
        sync = cs._synchronisation(_FakeSupabase(), [f"aide-{i}" for i in range(100)])
        self.assertEqual(sync["nbManquantes"], 100)
        self.assertEqual(len(sync["manquantes"]), cs.MANQUANTES_MAX)


class CorpusReelTests(unittest.TestCase):
    """Le rattachement territorial doit couvrir EXACTEMENT ce que le schéma des
    aides accepte, sinon des aides disparaissent des statistiques en silence."""

    def test_le_rattachement_partitionne_les_departements(self) -> None:
        rattaches = [code for codes in REGION_DEPARTEMENTS.values() for code in codes]
        self.assertEqual(sorted(rattaches), sorted(DEPARTEMENT_LABELS))
        self.assertEqual(len(rattaches), len(set(rattaches)), "un département dans deux régions")

    def test_le_rattachement_couvre_toutes_les_regions(self) -> None:
        self.assertEqual(sorted(REGION_DEPARTEMENTS), sorted(REGION_LABELS))

    def test_toutes_les_aides_du_corpus_ont_une_portee(self) -> None:
        entrees = [cs.Entree(aide=aide, retiree=False) for aide in load_all_aides().values()]
        portees = {e.portee for e in entrees}
        self.assertTrue(portees <= {"nationale", "region", "departement"})

    def test_aucune_aide_du_corpus_ne_cite_un_departement_hors_table(self) -> None:
        inconnus = {
            code
            for aide in load_all_aides().values()
            for code in aide.hard_filters.departements
            if code not in DEPARTEMENT_REGION
        }
        self.assertEqual(inconnus, set())


if __name__ == "__main__":
    unittest.main()
