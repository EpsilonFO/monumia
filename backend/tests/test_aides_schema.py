"""Tests du schéma de données d'aides et du moteur de prédicats.

Run from backend/:  .venv/bin/python -m unittest discover
"""

import unittest

from pydantic import ValidationError

from aides_schema import (
    ROLE_BY_TYPE,
    TYPES,
    Aide,
    Condition,
    Predicate,
    evaluate_predicate,
    load_all_aides,
    load_facts,
)


class TestEvaluatePredicate(unittest.TestCase):
    def test_comparisons(self):
        self.assertIs(evaluate_predicate({"gte": 40}, 60), True)
        self.assertIs(evaluate_predicate({"gte": 40}, 30), False)
        self.assertIs(evaluate_predicate({"eq": True}, False), False)
        self.assertIs(evaluate_predicate({"in": ["a", "b"]}, "b"), True)
        self.assertIs(evaluate_predicate({"not_in": ["a"]}, "b"), True)
        self.assertIs(evaluate_predicate({"contains": "ort"}, ["acv", "ort"]), True)
        self.assertIs(evaluate_predicate({"contains": "ort"}, []), False)

    def test_unknown_value_is_none_not_false(self):
        """Fail-closed : valeur inconnue → incertitude, jamais élimination."""
        self.assertIsNone(evaluate_predicate({"gte": 40}, None))
        self.assertIsNone(evaluate_predicate({"eq": True}, None))

    def test_combinators(self):
        any_of = {"any_of": [{"contains": "acv"}, {"contains": "ort"}]}
        self.assertIs(evaluate_predicate(any_of, ["ort"]), True)
        self.assertIs(evaluate_predicate(any_of, ["autre"]), False)
        all_of = {"all_of": [{"gte": 10}, {"lte": 20}]}
        self.assertIs(evaluate_predicate(all_of, 15), True)
        self.assertIs(evaluate_predicate(all_of, 25), False)

    def test_invalid_predicates_rejected(self):
        with self.assertRaises(ValidationError):
            Predicate.model_validate({"gte": 40, "lte": 60})  # deux opérateurs
        with self.assertRaises(ValidationError):
            Predicate.model_validate({"between": [1, 2]})  # opérateur inconnu


class TestConditionCoherence(unittest.TestCase):
    def test_user_fact_requires_fact_and_predicate(self):
        with self.assertRaises(ValidationError):
            Condition(id="x", text="t", kind="user_fact")

    def test_info_cannot_gate(self):
        with self.assertRaises(ValidationError):
            Condition(id="x", text="t", kind="info", effect="gate")

    def test_discretionary_has_no_predicate(self):
        with self.assertRaises(ValidationError):
            Condition.model_validate(
                {"id": "x", "text": "t", "kind": "discretionary", "predicate": {"eq": 1}}
            )

    def test_derogation_possible_requires_evaluable_gate(self):
        # OK sur un gate user_fact.
        Condition.model_validate(
            {
                "id": "x",
                "text": "t",
                "kind": "user_fact",
                "fact": "f",
                "predicate": {"eq": False},
                "derogation_possible": True,
            }
        )
        # Interdit sur un manual_check (rien à dégrader : déjà incertitude).
        with self.assertRaises(ValidationError):
            Condition.model_validate(
                {"id": "x", "text": "t", "kind": "manual_check", "derogation_possible": True}
            )


class TestFinancementPlan(unittest.TestCase):
    """Champs MVP du plan de financement (assiette, cumul) + rôle dérivé du type."""

    def _aide(self, **over):
        base = {
            "slug": "x",
            "nom": "X",
            "organisme": "Org",
            "categorie": "region",
            "type": "subvention",
            "description": "d",
        }
        base.update(over)
        return Aide.model_validate(base)

    def test_assiette_and_cumul_parse(self):
        a = self._aide(
            financement={"taux_max": 40, "assiette": "Travaux sur parties classées uniquement"},
            cumul={"plafond_public_pct": 80, "exclusions": ["detr"]},
        )
        self.assertEqual(a.financement.assiette, "Travaux sur parties classées uniquement")
        self.assertEqual(a.cumul.plafond_public_pct, 80)
        self.assertEqual(a.cumul.exclusions, ["detr"])

    def test_cumul_defaults_are_permissive(self):
        a = self._aide()
        self.assertTrue(a.cumul.cumulable)
        self.assertEqual(a.cumul.exclusions, [])
        self.assertIsNone(a.cumul.plafond_public_pct)
        self.assertIsNone(a.financement.assiette)

    def test_existing_aides_still_valid_without_new_fields(self):
        # Les 11 YAML actuels (sans assiette/cumul) doivent toujours charger.
        aides = load_all_aides()
        self.assertGreaterEqual(len(aides), 11)

    def test_every_type_has_a_financing_role(self):
        for t in TYPES:
            self.assertIn(t, ROLE_BY_TYPE, f"type « {t} » sans rôle dans ROLE_BY_TYPE")


class TestDocuments(unittest.TestCase):
    """Pièces du dossier : coercion chaîne (legacy) et forme structurée."""

    def _aide(self, docs):
        return Aide.model_validate(
            {
                "slug": "x",
                "nom": "X",
                "organisme": "Org",
                "categorie": "region",
                "type": "subvention",
                "description": "d",
                "documents_requis": docs,
            }
        )

    def test_plain_string_is_coerced(self):
        a = self._aide(["Devis détaillés", "Preuve de propriété"])
        self.assertEqual(a.documents_requis[0].nom, "Devis détaillés")
        self.assertIsNone(a.documents_requis[0].url)
        self.assertTrue(a.documents_requis[0].obligatoire)

    def test_structured_document_with_link_and_note(self):
        a = self._aide(
            [
                {"nom": "Formulaire Cerfa", "url": "https://example.gouv.fr/cerfa.pdf"},
                {"nom": "Délibération du conseil", "obligatoire": False, "note": "si commune"},
            ]
        )
        self.assertEqual(a.documents_requis[0].url, "https://example.gouv.fr/cerfa.pdf")
        self.assertFalse(a.documents_requis[1].obligatoire)
        self.assertEqual(a.documents_requis[1].note, "si commune")

    def test_mixed_list(self):
        a = self._aide(["Photos", {"nom": "Plan de financement", "url": "https://x"}])
        self.assertEqual(len(a.documents_requis), 2)
        self.assertEqual(a.documents_requis[1].url, "https://x")


class TestCorpus(unittest.TestCase):
    """Le corpus data/ complet doit charger et se valider — c'est le contrat CI."""

    def test_facts_load(self):
        facts = load_facts()
        self.assertIn("jours_ouverture_public_par_an", facts)
        self.assertEqual(facts["maitrise_oeuvre"].type, "enum")

    def test_all_aides_load(self):
        aides = load_all_aides()
        self.assertGreaterEqual(len(aides), 96)
        self.assertTrue(all(isinstance(a, Aide) for a in aides.values()))

    def test_engine_ready_aides_have_no_untyped(self):
        """Invariant robuste (indépendant du contenu) : toute aide engine-ready
        est entièrement typée. Le contenu précis d'une aide est garanti par
        lint_aides_data.py, pas par des assertions golden fragiles."""
        from eligibility_engine import engine_ready_aides

        ready = engine_ready_aides(load_all_aides())
        self.assertGreater(len(ready), 0)
        for slug, aide in ready.items():
            self.assertFalse(
                any(c.kind == "untyped" for c in aide.conditions),
                f"{slug} est engine-ready mais contient des conditions untyped",
            )

    def test_condition_effects_synthetic(self):
        """effect : modulateur conservé, manual_check → gate (défaut), info → info."""
        aide = Aide.model_validate(
            {
                "slug": "t",
                "nom": "T",
                "organisme": "O",
                "categorie": "region",
                "type": "subvention",
                "description": "d",
                "conditions": [
                    {
                        "id": "mod",
                        "text": "bonus",
                        "kind": "user_fact",
                        "effect": "modulateur",
                        "fact": "f",
                        "predicate": {"gte": 40},
                    },
                    {"id": "mc", "text": "check", "kind": "manual_check"},
                    {"id": "nfo", "text": "info", "kind": "info"},
                ],
            }
        )
        by_id = {c.id: c for c in aide.conditions}
        self.assertEqual(by_id["mod"].effect, "modulateur")
        self.assertEqual(by_id["mc"].effect, "gate")
        self.assertEqual(by_id["nfo"].effect, "info")


if __name__ == "__main__":
    unittest.main()
