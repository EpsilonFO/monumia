"""Tests du moteur de diagnostic déterministe.

Run from backend/:  .venv/bin/python -m unittest discover
"""

import unittest
from datetime import date

from aides_schema import Aide, Calendrier, load_all_aides, load_facts, load_pending_facts
from eligibility_engine import (
    build_context,
    candidature_close,
    engine_ready_aides,
    evaluate_aide,
    run_deterministic_diagnostic,
)

AIDES = load_all_aides()
FACTS = {**load_facts(), **load_pending_facts()}
READY = engine_ready_aides(AIDES)


def _fixture_aide(conditions: list[dict], **hard_filters) -> Aide:
    """Aide synthétique pour tester le COMPORTEMENT du moteur sans dépendre du
    contenu (mutable) du corpus — celui-ci est gardé par lint_aides_data.py."""
    return Aide.model_validate(
        {
            "slug": "fixture-aide",
            "nom": "Fixture",
            "organisme": "Org",
            "categorie": "region",
            "type": "subvention",
            "description": "d",
            "conditions": conditions,
            "hard_filters": hard_filters,
        }
    )


def _monument(**over):
    base = {
        "id": "demo",
        "nom": "Château de Test",
        "protection": "classe",
        "proprietaire": "prive_personne_physique",
        "region": "ile-de-france",
        "departement_num": "78",
        "etat_conservation": "peril",
        "travaux_envisages": ["toiture", "facade"],
        "siecle_construction": "XVIIe siècle",
    }
    base.update(over)
    return base


class TestEngineReady(unittest.TestCase):
    def test_only_fully_typed_aides(self):
        for slug, aide in READY.items():
            self.assertFalse(
                any(c.kind == "untyped" for c in aide.conditions),
                f"{slug} a des conditions untyped mais est dans le set engine-ready",
            )

    def test_drac_classes_is_ready(self):
        self.assertIn("drac-mh-classes", READY)


class TestCandidatureClose(unittest.TestCase):
    """Fenêtre de candidature : mêmes règles que prefiltrer_aides (SQL)."""

    TODAY = date(2026, 6, 22)

    def _aide(self, **calendrier) -> Aide:
        return _fixture_aide([]).model_copy(update={"calendrier": Calendrier(**calendrier)})

    def test_permanente_jamais_close(self):
        self.assertFalse(candidature_close(self._aide(permanent=True), self.TODAY))

    def test_sans_date_limite_jamais_close(self):
        self.assertFalse(candidature_close(self._aide(permanent=False), self.TODAY))

    def test_date_passee_est_close(self):
        a = self._aide(permanent=False, date_limite=date(2026, 2, 13))
        self.assertTrue(candidature_close(a, self.TODAY))

    def test_date_future_pas_close(self):
        a = self._aide(permanent=False, date_limite=date(2026, 8, 31))
        self.assertFalse(candidature_close(a, self.TODAY))

    def test_date_du_jour_pas_close(self):
        a = self._aide(permanent=False, date_limite=self.TODAY)
        self.assertFalse(candidature_close(a, self.TODAY))

    def test_diagnostic_exclut_les_aides_closes(self):
        """Une aide engine-ready mais close ne doit pas être analysée."""
        a = self._aide(permanent=False, date_limite=date(2026, 2, 13))
        res = run_deterministic_diagnostic({"fixture-aide": a}, FACTS, _monument(), 3000)
        self.assertEqual(res["totalAidesAnalysees"], 0)


class TestHardFilters(unittest.TestCase):
    def test_inscrit_aide_refuses_classe_monument(self):
        """drac-mh-inscrits exige protection=inscrit → un classé est non éligible."""
        v = evaluate_aide(
            AIDES["drac-mh-inscrits"],
            _monument(protection="classe"),
            3000,
            build_context(_monument(protection="classe"), 3000),
            FACTS,
        )
        self.assertEqual(v.status, "non_eligible")
        self.assertIn("Protection", v.raison_ineligibilite)

    def test_commune_aide_refuses_private_owner(self):
        m = _monument(proprietaire="prive_personne_physique")
        v = evaluate_aide(AIDES["detr"], m, 3000, build_context(m, 3000), FACTS)
        self.assertEqual(v.status, "non_eligible")

    def test_population_threshold(self):
        """DETR : commune ≤ 20000 hab. Une grande ville (commune) est exclue."""
        m = _monument(proprietaire="public_commune", protection="non_protege")
        v_small = evaluate_aide(AIDES["detr"], m, 3000, build_context(m, 3000), FACTS)
        v_big = evaluate_aide(AIDES["detr"], m, 200000, build_context(m, 200000), FACTS)
        self.assertNotEqual(v_small.status, "non_eligible")
        self.assertEqual(v_big.status, "non_eligible")


class TestUserFactGating(unittest.TestCase):
    def test_unanswered_fact_is_potentiel_not_eligible(self):
        """Sans réponse, un gate user_fact laisse l'aide potentielle (fail-closed)."""
        m = _monument()
        v = evaluate_aide(AIDES["drac-mh-classes"], m, 3000, build_context(m, 3000), FACTS)
        self.assertEqual(v.status, "potentiel")
        self.assertIn("travaux_commences", v.missing_facts)

    def test_answer_can_make_ineligible(self):
        """Travaux déjà commencés → DRAC classés devient non éligible."""
        m = _monument()
        ctx = build_context(m, 3000, answers={"travaux_commences": True})
        v = evaluate_aide(AIDES["drac-mh-classes"], m, 3000, ctx, FACTS)
        self.assertEqual(v.status, "non_eligible")

    def test_manual_check_gate_keeps_potentiel_even_when_user_facts_answered(self):
        """Un gate manual_check (invérifiable) maintient l'aide potentielle même
        quand tous les user_facts sont répondus favorablement — fail-closed."""
        aide = _fixture_aide(
            [
                {
                    "id": "tc",
                    "text": "Travaux non commencés",
                    "kind": "user_fact",
                    "fact": "travaux_commences",
                    "predicate": {"eq": False},
                },
                {"id": "mc", "text": "À vérifier auprès du financeur", "kind": "manual_check"},
            ]
        )
        m = _monument()
        ctx = build_context(m, 3000, answers={"travaux_commences": False})
        v = evaluate_aide(aide, m, 3000, ctx, FACTS)
        self.assertEqual(v.status, "potentiel")
        self.assertNotIn("travaux_commences", v.missing_facts)
        # Seul reste le manual_check : incertitude sans categorie (donc sans question).
        incertitudes = [e for e in v.evaluations if e["verdict"] == "incertitude"]
        self.assertEqual(len(incertitudes), 1)
        self.assertNotIn("categorie", incertitudes[0])

    def test_derogation_possible_soft_gate(self):
        """Gate souple : prédicat faux → incertitude (pas de refus). Vrai → satisfait.
        Inconnu → question posée."""
        soft = _fixture_aide(
            [
                {
                    "id": "tc",
                    "text": "Travaux non commencés (sauf dérogation)",
                    "kind": "user_fact",
                    "fact": "travaux_commences",
                    "predicate": {"eq": False},
                    "derogation_possible": True,
                }
            ]
        )
        m = _monument()
        # Non commencés → satisfait → éligible.
        v_ok = evaluate_aide(
            soft, m, 3000, build_context(m, 3000, answers={"travaux_commences": False}), FACTS
        )
        self.assertEqual(v_ok.status, "eligible")
        # Commencés → PAS refusé (dérogation possible) → potentiel, sans re-question.
        v_started = evaluate_aide(
            soft, m, 3000, build_context(m, 3000, answers={"travaux_commences": True}), FACTS
        )
        self.assertEqual(v_started.status, "potentiel")
        self.assertNotIn("travaux_commences", v_started.missing_facts)
        # Inconnu → incertitude → question posée.
        v_unknown = evaluate_aide(soft, m, 3000, build_context(m, 3000), FACTS)
        self.assertEqual(v_unknown.status, "potentiel")
        self.assertIn("travaux_commences", v_unknown.missing_facts)

    def test_strict_gate_refuses_when_false(self):
        """Sans derogation_possible, le même prédicat faux refuse l'aide (contraste)."""
        strict = _fixture_aide(
            [
                {
                    "id": "tc",
                    "text": "Travaux non commencés",
                    "kind": "user_fact",
                    "fact": "travaux_commences",
                    "predicate": {"eq": False},
                }
            ]
        )
        m = _monument()
        v = evaluate_aide(
            strict, m, 3000, build_context(m, 3000, answers={"travaux_commences": True}), FACTS
        )
        self.assertEqual(v.status, "non_eligible")

    def test_aide_without_manual_check_becomes_eligible(self):
        """Une aide sans manual_check, dont les gates auto + user_fact sont tous
        satisfaits, devient éligible (Loto : protection + non-commencement +
        trésorerie insuffisante)."""
        m = _monument(protection="classe")
        answers = {"travaux_commences": False, "tresorerie_insuffisante_autofinancement": True}
        ctx = build_context(m, 3000, answers=answers)
        v = evaluate_aide(AIDES["loto-patrimoine"], m, 3000, ctx, FACTS)
        self.assertEqual(v.status, "eligible")


class TestAppliesIf(unittest.TestCase):
    def test_autofinancement_skipped_for_private(self):
        """L'autofinancement 20 % ne s'applique qu'aux collectivités → pas de
        question pour un propriétaire privé."""
        m = _monument(proprietaire="prive_personne_physique")
        v = evaluate_aide(AIDES["drac-mh-classes"], m, 3000, build_context(m, 3000), FACTS)
        self.assertNotIn("autofinancement_pct", v.missing_facts)


class TestQuestionGeneration(unittest.TestCase):
    def test_elimination_is_computed_correctly(self):
        m = _monument()
        res = run_deterministic_diagnostic(AIDES, FACTS, m, 3000)
        q_travaux = next(q for q in res["qcmQuestions"] if q["categorie"] == "travaux_commences")
        # « Oui » élimine DRAC classés ; « Non » n'élimine personne.
        self.assertIn("drac-mh-classes", q_travaux["eliminationsParOption"].get("oui", []))
        self.assertNotIn("non", q_travaux["eliminationsParOption"])

    def test_skip_never_eliminates(self):
        m = _monument()
        res = run_deterministic_diagnostic(AIDES, FACTS, m, 3000)
        for q in res["qcmQuestions"]:
            self.assertNotIn("skip", q["eliminationsParOption"])

    def test_questions_sorted_by_aides_unblocked(self):
        m = _monument()
        res = run_deterministic_diagnostic(AIDES, FACTS, m, 3000)
        counts = [len(q["aideIds"]) for q in res["qcmQuestions"]]
        self.assertEqual(counts, sorted(counts, reverse=True))


class TestDiagnosticShape(unittest.TestCase):
    def test_output_contract(self):
        res = run_deterministic_diagnostic(AIDES, FACTS, _monument(), 3000)
        for key in (
            "aidesEligibles",
            "aidesPotentiellementEligibles",
            "aidesNonEligibles",
            "qcmQuestions",
            "totalAidesAnalysees",
        ):
            self.assertIn(key, res)
        match = (res["aidesEligibles"] + res["aidesPotentiellementEligibles"])[0]
        for key in ("aide", "eligible", "criteresRemplis", "criteresNonRemplis", "llmEvaluation"):
            self.assertIn(key, match)
        self.assertIn("id", match["aide"])  # = slug


if __name__ == "__main__":
    unittest.main()
