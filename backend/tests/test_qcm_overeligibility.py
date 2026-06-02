"""Unit tests for the QCM over-eligibility fixes (see docs/fix-qcm-overeligibility.md).

Covers:
  FIX 1 + FIX 5 — only an explicit user answer clarifies an incertitude; LLM
                  skips and silent omissions leave the aide potentiellement
                  éligible (out of montantPotentielTotal).
  FIX 2        — nested-decreasing monotonicity repair on ordered-threshold
                  eliminationsParOption maps; categorical questions untouched.
  FIX 3        — source dedup keyed on `critere` alone, not (critere, detail).

Run from backend/:  .venv/bin/python -m unittest discover
"""

import logging
import unittest

import matching_engine as m


def _inc(
    categorie: str, critere: str = "crit", detail: str = "det", clarified: bool = False
) -> dict:
    """Build an incertitude evaluation dict shaped like _run_llm_phase emits."""
    return {
        "critere": critere,
        "verdict": "incertitude",
        "explication": detail,
        "categorie": categorie,
        "detail": detail,
        "clarified": clarified,
    }


def _make_result(aide_id: str, incertitudes: list[dict], montant_max: int = 1000) -> dict:
    """Build an eligible_result with the given incertitudes attached."""
    return {
        "aide": {"id": aide_id, "nom": aide_id, "montant_max": montant_max},
        "llmEvaluation": {
            "explication": "",
            "evaluations": list(incertitudes),
            "incertitudes": list(incertitudes),
        },
    }


def _question(categorie: str, options: list[dict], elim: dict | None = None) -> dict:
    q = {
        "id": "q1",
        "question": "Question ?",
        "categorie": categorie,
        "options": options,
    }
    if elim is not None:
        q["eliminationsParOption"] = elim
    return q


class ConservativeClarificationTests(unittest.TestCase):
    """FIX 1 + FIX 5: generation never clarifies; only explicit answers do."""

    def setUp(self) -> None:
        # Silence info/warning noise; assertLogs still works (it sets its own level).
        logging.getLogger("matching_engine").setLevel(logging.CRITICAL)

    def test_silently_missed_category_stays_potential(self) -> None:
        # Category present in input but neither asked nor explicitly skipped.
        inc = _inc("ouverture_public")
        result = _make_result("aide-R", [inc])
        parsed = {"questions": [], "categoriesSkippees": []}
        questions = m._process_qcm_response(parsed, {"ouverture_public": ["aide-R"]}, [result])

        self.assertEqual(questions, [])
        self.assertFalse(inc["clarified"], "a silently-missed incertitude must NOT be clarified")
        self.assertFalse(m._all_incertitudes_clarified(result))
        # Promotion gate (matching_engine.py) would keep the aide potential.
        promotable = [r for r in [result] if m._all_incertitudes_clarified(r)]
        self.assertEqual(promotable, [])

    def test_llm_skipped_category_stays_potential(self) -> None:
        # FIX 5: a category the LLM claims is "déjà connu du profil" still does
        # not promote — the reason is never trusted server-side.
        inc = _inc("ouverture_public")
        result = _make_result("aide-R", [inc])
        parsed = {
            "questions": [],
            "categoriesSkippees": [
                {"categorie": "ouverture_public", "raison": "deja connu du profil"}
            ],
        }
        m._process_qcm_response(parsed, {"ouverture_public": ["aide-R"]}, [result])

        self.assertFalse(inc["clarified"], "a skipped incertitude must NOT be clarified")
        self.assertFalse(m._all_incertitudes_clarified(result))

    def test_covered_category_not_clarified_at_generation(self) -> None:
        # Even when a question IS generated, generation never flips clarified —
        # that only happens later from the user's explicit answer.
        inc = _inc("ouverture_public")
        result = _make_result("aide-R", [inc])
        parsed = {
            "questions": [
                _question(
                    "ouverture_public",
                    [{"id": "a", "label": "A"}, {"id": "skip", "label": "Je ne sais pas"}],
                )
            ],
            "categoriesSkippees": [],
        }
        questions = m._process_qcm_response(parsed, {"ouverture_public": ["aide-R"]}, [result])

        self.assertEqual(len(questions), 1)
        self.assertFalse(inc["clarified"])
        self.assertFalse(m._all_incertitudes_clarified(result))


class MonotonicityRepairTests(unittest.TestCase):
    """FIX 2: ordered-threshold eliminationsParOption must nest; repair, never drop."""

    THRESHOLD_OPTIONS = [
        {"id": "lt40", "label": "Moins de 40 jours par an"},
        {"id": "40_59", "label": "Entre 40 et 59 jours par an"},
        {"id": "60_79", "label": "Entre 60 et 79 jours par an"},
        {"id": "ge80", "label": "80 jours ou plus par an"},
        {"id": "skip", "label": "Je ne sais pas"},
    ]

    def test_non_monotone_map_is_repaired_with_warning(self) -> None:
        # "X" is eliminated at 60_79 (higher) but missing from 40_59 (lower) — a
        # logical impossibility. Repair must reintegrate it into every lower tranche.
        clean_elim = {"lt40": ["X"], "60_79": ["X"]}
        with self.assertLogs("matching_engine", level="WARNING") as cm:
            repaired = m._repair_monotonic_eliminations(
                clean_elim, self.THRESHOLD_OPTIONS, "ouverture_public"
            )

        self.assertEqual(repaired["lt40"], ["X"])
        self.assertEqual(repaired["40_59"], ["X"], "X must be reintegrated into the lower tranche")
        self.assertEqual(repaired["60_79"], ["X"])
        self.assertNotIn("ge80", repaired, "the satisfied tranche stays empty")
        # Nesting holds: elim(lt40) ⊇ elim(40_59) ⊇ elim(60_79) ⊇ elim(ge80).
        for low, high in (("lt40", "40_59"), ("40_59", "60_79")):
            self.assertTrue(set(repaired.get(high, [])) <= set(repaired[low]))
        self.assertTrue(any("Monotonie" in line for line in cm.output))

    def test_already_monotone_map_is_unchanged(self) -> None:
        clean_elim = {"lt40": ["A", "B", "C"], "40_59": ["B", "C"], "60_79": ["C"]}
        repaired = m._repair_monotonic_eliminations(
            clean_elim, self.THRESHOLD_OPTIONS, "ouverture_public"
        )
        self.assertEqual(repaired["lt40"], ["A", "B", "C"])
        self.assertEqual(repaired["40_59"], ["B", "C"])
        self.assertEqual(repaired["60_79"], ["C"])

    def test_categorical_question_left_untouched(self) -> None:
        options = [
            {"id": "abf_oui", "label": "Oui, accord obtenu"},
            {"id": "abf_non", "label": "Non, pas d'accord"},
            {"id": "skip", "label": "Je ne sais pas"},
        ]
        clean_elim = {"abf_non": ["Y", "Z"]}
        repaired = m._repair_monotonic_eliminations(clean_elim, options, "accord_abf_prealable")
        self.assertEqual(repaired, {"abf_non": ["Y", "Z"]})

    def test_ambiguous_duplicate_keys_left_untouched(self) -> None:
        # Both options key to (40,) → no strict order → conservatively skip.
        options = [
            {"id": "moins40", "label": "Moins de 40"},
            {"id": "plus40", "label": "40 ou plus"},
            {"id": "skip", "label": "Je ne sais pas"},
        ]
        clean_elim = {"moins40": ["A"]}
        repaired = m._repair_monotonic_eliminations(clean_elim, options, "x")
        self.assertEqual(repaired, {"moins40": ["A"]})

    def test_repair_wired_into_process_qcm_response(self) -> None:
        result = _make_result("X", [_inc("ouverture_public")])
        parsed = {
            "questions": [
                _question(
                    "ouverture_public",
                    self.THRESHOLD_OPTIONS,
                    elim={"lt40": ["X"], "60_79": ["X"]},
                )
            ],
            "categoriesSkippees": [],
        }
        logging.getLogger("matching_engine").setLevel(logging.CRITICAL)
        questions = m._process_qcm_response(parsed, {"ouverture_public": ["X"]}, [result])

        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["eliminationsParOption"]["40_59"], ["X"])


class AggregateDedupTests(unittest.TestCase):
    """FIX 3: dedup sources on `critere` alone, merging aide ids/noms."""

    def test_same_critere_different_detail_collapses_to_one_source(self) -> None:
        crit = "ouverture au public >= 40 jours/an"
        r1 = _make_result("A1", [_inc("ouverture_public", critere=crit, detail="paraphrase une")])
        r2 = _make_result("A2", [_inc("ouverture_public", critere=crit, detail="paraphrase deux")])

        aggregated = m._aggregate_incertitudes([r1, r2])

        self.assertEqual(len(aggregated), 1)
        cat = aggregated[0]
        self.assertEqual(cat["categorie"], "ouverture_public")
        self.assertEqual(len(cat["sources"]), 1, "differing detail must NOT split the source")
        src = cat["sources"][0]
        self.assertEqual(src["aideIds"], ["A1", "A2"], "aide ids merged across the shared critere")
        self.assertEqual(src["critere"], crit)
        self.assertIn(src["detail"], {"paraphrase une", "paraphrase deux"})

    def test_distinct_criteres_stay_separate(self) -> None:
        r1 = _make_result("A1", [_inc("ouverture_public", critere="ouverture >= 40 j/an")])
        r2 = _make_result("A2", [_inc("ouverture_public", critere="ouverture >= 60 j/an")])

        aggregated = m._aggregate_incertitudes([r1, r2])

        self.assertEqual(len(aggregated), 1)
        self.assertEqual(len(aggregated[0]["sources"]), 2)

    def test_representative_detail_is_most_frequent(self) -> None:
        crit = "ouverture >= 40 j/an"
        results = [
            _make_result("A1", [_inc("ouverture_public", critere=crit, detail="commun")]),
            _make_result("A2", [_inc("ouverture_public", critere=crit, detail="commun")]),
            _make_result("A3", [_inc("ouverture_public", critere=crit, detail="rare")]),
        ]

        aggregated = m._aggregate_incertitudes(results)

        self.assertEqual(aggregated[0]["sources"][0]["detail"], "commun")


if __name__ == "__main__":
    unittest.main()
