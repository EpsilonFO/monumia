"""Statistiques du catalogue : la portée d'une aide, son rattachement
territorial, son chiffrage, et l'écart avec `aides_v3`.

Deux familles de tests, et la seconde est la plus importante :

- sur un CORPUS FABRIQUÉ, pour figer les règles de comptage (une aide
  départementale compte dans sa région, une retirée sort des taux, la
  couverture d'un département additionne les trois étages) ;
- sur le CORPUS RÉEL, pour vérifier que rien ne se perd — la somme des portées
  vaut le corpus, et la table `REGION_DEPARTEMENTS` couvre exactement les
  départements que le schéma des aides accepte. Un département oublié dans le
  rattachement ne casserait rien : il rendrait juste une région trop maigre,
  sans un mot.
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


def _entree(aide: Aide, *, retiree=False, typee=True, bientot=False) -> cs.Entree:
    return cs.Entree(aide=aide, retiree=retiree, typee=typee, bientot=bientot)


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

    def test_un_departement_rend_la_portee_locale(self) -> None:
        entree = _entree(_aide("a", hard_filters={"departements": ["88"]}))
        self.assertEqual(entree.portee, "locale")

    def test_une_enumeration_plus_etroite_que_la_region_reste_locale(self) -> None:
        """Deux départements du Grand Est sur dix : la liste restreint pour de
        bon, l'aide ne doit pas remonter sur les huit autres."""
        entree = _entree(
            _aide("a", hard_filters={"regions": ["grand-est"], "departements": ["88", "57"]})
        )
        self.assertEqual(entree.portee, "locale")

    def test_une_enumeration_couvrant_toute_la_region_reste_regionale(self) -> None:
        """Le cas le plus courant du corpus : un dispositif régional qui liste
        en plus tous les départements de sa région (colonne
        `aides_v3.departements`). La liste ne retire rien.

        Le lire comme local affichait « 0 régionale, 20 départementales » sur
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

    def test_une_enumeration_a_cheval_sur_deux_regions_reste_locale(self) -> None:
        entree = _entree(
            _aide(
                "a",
                hard_filters={
                    "regions": ["grand-est", "bourgogne-franche-comte"],
                    "departements": REGION_DEPARTEMENTS["grand-est"],
                },
            )
        )
        self.assertEqual(entree.portee, "locale")

    def test_une_aide_locale_appartient_a_sa_region(self) -> None:
        entree = _entree(_aide("a", hard_filters={"departements": ["88", "71"]}))
        self.assertEqual(entree.regions, {"grand-est", "bourgogne-franche-comte"})


class BlocTests(unittest.TestCase):
    def test_une_retiree_est_comptee_a_part_et_sort_des_taux(self) -> None:
        bloc = cs._bloc(
            [
                _entree(_aide("a", financement={"taux_max": 20})),
                _entree(_aide("b", financement={"taux_max": 80}), retiree=True),
            ]
        )
        self.assertEqual(bloc["nb"], 1)
        self.assertEqual(bloc["retirees"], 1)
        self.assertEqual(bloc["tauxMax"], 20)

    def test_le_taux_retenu_est_le_maximum_sinon_le_minimum(self) -> None:
        bloc = cs._bloc(
            [
                _entree(_aide("a", financement={"taux_min": 15, "taux_max": 40})),
                _entree(_aide("b", financement={"taux_min": 30})),
            ]
        )
        self.assertEqual(bloc["tauxMin"], 15)
        self.assertEqual(bloc["tauxMax"], 40)
        self.assertEqual(bloc["tauxMedian"], 35)
        self.assertEqual(bloc["nbAvecTaux"], 2)

    def test_un_groupe_sans_chiffrage_rend_des_nuls_et_non_des_zeros(self) -> None:
        """Zéro dirait « taux nul » ; nul dit « la source ne chiffre pas »."""
        bloc = cs._bloc([_entree(_aide("a"))])
        self.assertIsNone(bloc["tauxMax"])
        self.assertIsNone(bloc["montantMedian"])
        self.assertEqual(bloc["nbAvecMontant"], 0)

    def test_groupe_vide(self) -> None:
        bloc = cs._bloc([])
        self.assertEqual(bloc["nb"], 0)
        self.assertIsNone(bloc["tauxMedian"])

    def test_typees_et_bientot_ne_comptent_que_les_servies(self) -> None:
        bloc = cs._bloc(
            [
                _entree(_aide("a"), typee=True, bientot=True),
                _entree(_aide("b"), typee=True, bientot=True, retiree=True),
            ]
        )
        self.assertEqual(bloc["typees"], 1)
        self.assertEqual(bloc["bientot"], 1)


class _CorpusFabrique(unittest.TestCase):
    """Le corpus est remplacé par quatre aides : les règles de comptage se
    lisent alors à l'œil nu. Pas de test ici — deux classes en héritent, et des
    tests hérités s'exécuteraient deux fois."""

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
    def test_le_corpus_se_repartit_sans_perte(self) -> None:
        corpus = self._stats()["corpus"]
        self.assertEqual(corpus["total"], 5)
        self.assertEqual(
            corpus["nationales"] + corpus["regionales"] + corpus["locales"],
            corpus["nb"],
        )

    def test_une_region_agrege_ses_departements(self) -> None:
        grand_est = self._region(self._stats(), "grand-est")
        # Deux aides à périmètre régional : celle qui déclare sa région, et
        # celle qui énumère en plus ses dix départements.
        self.assertEqual(grand_est["regionales"], 2)
        self.assertEqual(grand_est["locales"], 2)
        self.assertEqual(grand_est["nb"], 4)
        # Maximum, pas acquis : les deux aides locales ne valent pas partout.
        self.assertEqual(grand_est["couvertureMax"], 5)

    def test_une_region_distingue_le_perimetre_du_financeur(self) -> None:
        """La question que le périmètre ne répond pas : quelle collectivité
        finance ? Les deux aides locales du Grand Est viennent de Conseils
        départementaux, les deux régionales non."""
        grand_est = self._region(self._stats(), "grand-est")
        self.assertEqual(grand_est["conseilsDepartementaux"], 2)
        self.assertEqual(grand_est["conseilRegional"], 2)

    def test_une_region_sans_aide_reste_dans_le_tableau(self) -> None:
        """Un zéro est une information de prospection, pas une ligne à cacher."""
        bretagne = self._region(self._stats(), "bretagne")
        self.assertEqual(bretagne["nb"], 0)
        self.assertEqual(bretagne["couvertureMax"], 1)

    def test_la_couverture_dun_departement_additionne_les_trois_etages(self) -> None:
        vosges = self._departement(self._stats(), "88")
        self.assertEqual((vosges["locales"], vosges["regionales"], vosges["nationales"]), (1, 2, 1))
        self.assertEqual(vosges["couverture"], 4)
        self.assertEqual(vosges["regionLabel"], "Grand Est")

    def test_une_regionale_enumeree_nest_pas_comptee_deux_fois(self) -> None:
        """Elle nomme le 88 dans ses `departements` ET couvre toute la région :
        la compter en local puis en régional gonflerait la couverture d'un
        étage fantôme."""
        vosges = self._departement(self._stats(), "88")
        self.assertEqual(
            vosges["couverture"],
            vosges["locales"] + vosges["regionales"] + vosges["nationales"],
        )
        self.assertEqual(vosges["locales"], 1)

    def test_un_departement_voisin_voit_les_memes_regionales(self) -> None:
        moselle = self._departement(self._stats(), "57")
        self.assertEqual(moselle["locales"], 1)
        self.assertEqual(moselle["couverture"], 4)

    def test_un_departement_distingue_ses_aides_du_conseil_departemental(self) -> None:
        """Le chiffre que le périmètre ne donne pas : onze aides applicables et
        zéro ici veut dire qu'un financeur entier reste à prospecter."""
        vosges = self._departement(self._stats(), "88")
        self.assertEqual(vosges["conseilDepartemental"], 1)
        bas_rhin = self._departement(self._stats(), "67")
        self.assertEqual((bas_rhin["locales"], bas_rhin["conseilDepartemental"]), (0, 0))

    def test_tous_les_departements_sont_listes(self) -> None:
        self.assertEqual(len(self._stats()["departements"]), len(DEPARTEMENT_LABELS))

    def test_une_aide_retiree_sort_des_comptes_et_de_sa_region(self) -> None:
        stats = self._stats(**{ca.TABLE_RETIREES: [{"slug": "vosges"}]})
        self.assertEqual(stats["corpus"]["nb"], 4)
        self.assertEqual(stats["corpus"]["retirees"], 1)
        grand_est = self._region(stats, "grand-est")
        self.assertEqual(grand_est["locales"], 1)
        self.assertEqual(grand_est["retirees"], 1)
        self.assertEqual(self._departement(stats, "88")["couverture"], 3)

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
        sync = self._stats(
            aides_v3=[{"slug": "nationale"}, {"slug": "regionale"}, {"slug": "regionale-enumeree"}]
        )["synchronisation"]
        self.assertTrue(sync["lisible"])
        self.assertEqual(sync["enBase"], 3)
        self.assertEqual(sync["manquantes"], ["moselle", "vosges"])

    def test_une_aide_retiree_nest_pas_reclamee_en_base(self) -> None:
        """Elle répond 404 partout de toute façon : la réclamer enverrait
        chercher une panne inexistante."""
        sync = self._stats(
            aides_v3=[
                {"slug": "nationale"},
                {"slug": "regionale"},
                {"slug": "regionale-enumeree"},
                {"slug": "moselle"},
            ],
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
        entrees = [
            cs.Entree(aide=aide, retiree=False, typee=False, bientot=False)
            for aide in load_all_aides().values()
        ]
        portees = {e.portee for e in entrees}
        self.assertTrue(portees <= {"nationale", "region", "locale"})

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
