"""Le résumé des non éligibles dans la réponse du diagnostic.

Neuf dixièmes du poids d'un diagnostic tenaient dans des aides non éligibles
que le front n'affiche jamais. Ce qui est vérifié ici : celles écartées par une
réponse gardent tout, les autres gardent de quoi être retrouvées par leur id,
et rien de ce qui se calcule sur le résultat ne bouge.
"""

import json
import unittest

from routers.aides import deterministic_diagnostic_for, resumer_non_eligibles

MONUMENT = {
    "id": "m1",
    "nom": "Château de Test",
    "protection": "classe",
    "proprietaire": "prive_personne_physique",
    "region": "ile-de-france",
    "departement_num": "78",
    "etat_conservation": "peril",
    "travaux_envisages": ["toiture", "facade"],
    "siecle_construction": "XVIIe siècle",
}


def _match(slug: str, *, elimine: bool) -> dict:
    return {
        "aide": {
            "id": slug,
            "nom": f"Aide {slug}",
            "nomCourt": slug,
            "descriptionLongue": "x" * 500,
            "documentsRequis": [{"nom": "Devis"}],
            "conditionsEligibiliteDetail": "- une condition",
            "montantMax": 1000,
        },
        "statut": "non_eligible",
        "eligible": False,
        "elimineParReponse": elimine,
        "criteresRemplis": [],
        "criteresNonRemplis": ["c1"],
        "raisonIneligibilite": "hors région",
        "leviers": [],
        "llmEvaluation": {"explication": "…", "evaluations": [{"id": "c1"}], "incertitudes": []},
    }


class ResumerNonEligiblesTests(unittest.TestCase):
    def test_une_aide_ecartee_par_une_reponse_garde_tout(self) -> None:
        entree = _match("a", elimine=True)
        attendu = json.loads(json.dumps(entree))
        out = resumer_non_eligibles({"aidesNonEligibles": [entree]})
        self.assertEqual(out["aidesNonEligibles"], [attendu])
        self.assertNotIn("resume", out["aidesNonEligibles"][0])

    def test_les_autres_sont_resumees_et_le_disent(self) -> None:
        out = resumer_non_eligibles({"aidesNonEligibles": [_match("b", elimine=False)]})
        (resume,) = out["aidesNonEligibles"]
        self.assertTrue(resume["resume"])
        for absent in ("llmEvaluation", "raisonIneligibilite", "leviers"):
            self.assertNotIn(absent, resume)
        for absent in ("descriptionLongue", "documentsRequis", "conditionsEligibiliteDetail"):
            self.assertNotIn(absent, resume["aide"])
        self.assertEqual(resume["aide"]["id"], "b")
        self.assertEqual(resume["aide"]["montantMax"], 1000)
        self.assertEqual(resume["criteresNonRemplis"], ["c1"])

    def test_les_autres_seaux_ne_bougent_pas(self) -> None:
        eligible = {**_match("c", elimine=False), "statut": "eligible", "eligible": True}
        out = resumer_non_eligibles({"aidesEligibles": [eligible], "aidesNonEligibles": []})
        self.assertIn("llmEvaluation", out["aidesEligibles"][0])


class ResumeSurLeCorpusTests(unittest.TestCase):
    """Sur le corpus réel, par le funnel : les invariants du plan de charge."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.resultat = deterministic_diagnostic_for(MONUMENT, 12000, {})

    def test_toutes_les_entrees_gardent_leur_id(self) -> None:
        # Les tests de la surcouche et la fiche d'aide cherchent une aide par
        # son id dans ce seau : le résumé ne doit jamais le perdre.
        for m in self.resultat["aidesNonEligibles"]:
            self.assertTrue(m["aide"]["id"])

    def test_seules_les_ecartees_par_reponse_gardent_leur_analyse(self) -> None:
        for m in self.resultat["aidesNonEligibles"]:
            with self.subTest(aide=m["aide"]["id"]):
                self.assertEqual("llmEvaluation" in m, bool(m["elimineParReponse"]))
                self.assertEqual(m.get("resume", False), not m["elimineParReponse"])

    def test_le_total_ne_depend_pas_des_seaux(self) -> None:
        total = sum(
            len(self.resultat[s])
            for s in (
                "aidesEligibles",
                "aidesPotentiellementEligibles",
                "aidesAtteignables",
                "aidesNonEligibles",
            )
        )
        self.assertEqual(self.resultat["totalAidesAnalysees"], total)


if __name__ == "__main__":
    unittest.main()
