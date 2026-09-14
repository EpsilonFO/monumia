"""Tests du schéma de données d'aides et du moteur de prédicats.

Run from backend/:  .venv/bin/python -m unittest discover
"""

import unittest

from pydantic import ValidationError

from aides_schema import (
    OPTIONS_BOOLEEN_IMPLICITES,
    ROLE_BY_TYPE,
    TYPES,
    Aide,
    Condition,
    FactDef,
    Predicate,
    _valider_faits,
    evaluate_predicate,
    load_all_aides,
    load_facts,
    load_pending_facts,
)


class TestLoadersAreCached(unittest.TestCase):
    """Les YAML ne changent qu'au déploiement : les loaders doivent être mis en
    cache, sinon chaque requête de diagnostic reparse ~130 fichiers (~0,7 s de
    CPU, sérialisé par le GIL quand le dashboard lance N diagnostics)."""

    def test_load_all_aides_returns_cached_result(self):
        self.assertIs(load_all_aides(), load_all_aides())

    def test_load_facts_returns_cached_result(self):
        self.assertIs(load_facts(), load_facts())

    def test_load_pending_facts_returns_cached_result(self):
        self.assertIs(load_pending_facts(), load_pending_facts())


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


class TestOptionsDeclareesSurUnBooleen(unittest.TestCase):
    """Les cinq règles de `_options_coherentes`.

    Un `boolean` peut offrir plus de deux réponses, chacune déclarant la valeur
    qu'elle envoie aux prédicats — lesquels restent `eq: true` / `eq: false`.
    """

    @staticmethod
    def _fait(**extra):
        base = {"type": "boolean", "scope": "projet", "question": "q ?"}
        return FactDef.model_validate({**base, **extra})

    OUI_NON = [
        {"id": "oui", "label": "Oui", "valeur": True},
        {"id": "non", "label": "Non", "valeur": False},
    ]

    def test_booleen_sans_options_reste_valide(self):
        """Le cas de 562 faits du corpus : rien à déclarer, rien ne change."""
        self.assertIsNone(self._fait().options)

    def test_booleen_avec_une_troisieme_reponse(self):
        fait = self._fait(
            options=[*self.OUI_NON, {"id": "les_deux", "label": "Les deux", "valeur": None}]
        )
        assert fait.options is not None
        self.assertEqual([o.id for o in fait.options], ["oui", "non", "les_deux"])
        self.assertIsNone(fait.options[2].valeur)

    # R1 — le couple implicite survit à la déclaration.
    def test_r1_oui_manquant_refuse(self):
        with self.assertRaises(ValidationError) as ctx:
            self._fait(options=[{"id": "non", "label": "Non", "valeur": False}])
        self.assertIn("oui", str(ctx.exception))

    def test_r1_non_manquant_refuse(self):
        with self.assertRaises(ValidationError):
            self._fait(options=[{"id": "oui", "label": "Oui", "valeur": True}])

    def test_r1_valeur_du_couple_non_detournee(self):
        """« oui » qui ne vaut plus True rendrait un gate `eq: true` impossible."""
        with self.assertRaises(ValidationError) as ctx:
            self._fait(
                options=[
                    {"id": "oui", "label": "Oui", "valeur": False},
                    {"id": "non", "label": "Non", "valeur": False},
                ]
            )
        self.assertIn("valeur attendue", str(ctx.exception))

    # R2 — sur un fait à choix, l'identifiant EST la valeur.
    def test_r2_valeur_interdite_sur_un_enum(self):
        with self.assertRaises(ValidationError) as ctx:
            FactDef.model_validate(
                {
                    "type": "enum",
                    "scope": "projet",
                    "question": "q ?",
                    "options": [{"id": "a", "label": "A", "valeur": True}],
                }
            )
        self.assertIn("réservé aux faits boolean", str(ctx.exception))

    def test_r2_valeur_interdite_sur_un_multi_enum(self):
        with self.assertRaises(ValidationError):
            FactDef.model_validate(
                {
                    "type": "multi_enum",
                    "scope": "projet",
                    "question": "q ?",
                    "options": [{"id": "a", "label": "A", "valeur": False}],
                }
            )

    # R3 — identifiants uniques.
    def test_r3_identifiants_en_double_refuses(self):
        with self.assertRaises(ValidationError) as ctx:
            self._fait(options=[*self.OUI_NON, {"id": "oui", "label": "Encore oui"}])
        self.assertIn("double", str(ctx.exception))

    # R4 — une réponse neutre ne tranche rien.
    def test_r4_unknown_exclut_valeur(self):
        with self.assertRaises(ValidationError) as ctx:
            self._fait(
                options=[
                    *self.OUI_NON,
                    {"id": "nsp", "label": "?", "unknown": True, "valeur": True},
                ]
            )
        self.assertIn("unknown", str(ctx.exception))

    def test_r4_unknown_seul_accepte(self):
        fait = self._fait(options=[*self.OUI_NON, {"id": "nsp", "label": "?", "unknown": True}])
        assert fait.options is not None
        self.assertTrue(fait.options[2].unknown)
        self.assertIsNone(fait.options[2].valeur)

    # R5 — les tranches d'un fait numérique viennent des seuils des aides.
    def test_r5_options_interdites_sur_un_integer(self):
        with self.assertRaises(ValidationError) as ctx:
            FactDef.model_validate(
                {
                    "type": "integer",
                    "scope": "projet",
                    "question": "q ?",
                    "options": [{"id": "a", "label": "A"}],
                }
            )
        self.assertIn("réservé aux faits", str(ctx.exception))

    def test_couple_implicite_expose_les_deux_valeurs(self):
        self.assertEqual(
            [(o.id, o.valeur) for o in OPTIONS_BOOLEEN_IMPLICITES],
            [("oui", True), ("non", False)],
        )


class TestErreurNommeLaCle(unittest.TestCase):
    """Sans la clé, l'erreur pydantic est illisible dans la sortie du lint, qui
    charge les 900 faits de l'ontologie d'un seul coup."""

    def test_le_message_porte_la_cle_du_fait(self):
        from pathlib import Path

        brut = {
            "fait_sain": {"type": "boolean", "scope": "projet", "question": "q ?"},
            "fait_casse": {
                "type": "boolean",
                "scope": "projet",
                "question": "q ?",
                "options": [{"id": "non", "label": "Non", "valeur": False}],
            },
        }
        with self.assertRaises(ValueError) as ctx:
            _valider_faits(brut, Path("facts.yaml"))
        message = str(ctx.exception)
        self.assertIn("fait_casse", message)
        self.assertIn("facts.yaml", message)

    def test_ontologie_saine_passe(self):
        from pathlib import Path

        faits = _valider_faits(
            {"f": {"type": "boolean", "scope": "projet", "question": "q ?"}}, Path("facts.yaml")
        )
        self.assertEqual(list(faits), ["f"])


if __name__ == "__main__":
    unittest.main()
