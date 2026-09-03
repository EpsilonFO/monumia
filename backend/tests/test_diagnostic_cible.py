"""Cible du diagnostic déterministe : projet, ou monument en compatibilité.

Le moteur lui-même est couvert par test_eligibility_engine ; ici on garde la
frontière : la validation `projet_id` ou `monument_id`, la résolution du
monument parent, la reprise du questionnaire enregistré, et surtout le fait que
la redaction du paywall reste clé MONUMENT quelle que soit l'entrée.
"""

import unittest
from unittest.mock import patch

import pydantic
from fastapi import HTTPException

from routers.aides import DeterministicDiagnosticRequest, diagnostic_deterministe
from services.offres import VEILLE


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, rows: list, calls: list) -> None:
        self._rows = rows
        self._calls = calls
        self._single = False
        self._one = False

    def select(self, *_a, **_k) -> "_FakeQuery":
        return self

    def eq(self, key, value) -> "_FakeQuery":
        self._calls.append((key, value))
        return self

    def is_(self, *_a, **_k) -> "_FakeQuery":
        return self

    def order(self, *_a, **_k) -> "_FakeQuery":
        return self

    def limit(self, *_a, **_k) -> "_FakeQuery":
        return self

    def maybe_single(self) -> "_FakeQuery":
        self._single = True
        return self

    def single(self) -> "_FakeQuery":
        self._one = True
        return self

    def execute(self):
        if self._single or self._one:
            return _Resp(self._rows[0] if self._rows else None)
        return _Resp(list(self._rows))


class _FakeSupabase:
    def __init__(self, tables: dict) -> None:
        self._tables = tables
        self.calls: list = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self._tables.get(name, []), self.calls)


MONUMENT = {
    "id": "m1",
    "user_id": "u1",
    "nom": "Château",
    "protection": "classe",
    "proprietaire": "prive_personne_physique",
    "code_insee": None,
}
PROJET_OUVERT = {
    "id": "p1",
    "monument_id": "m1",
    "user_id": "u1",
    "travaux_envisages": ["toiture"],
    "questionnaire": {"_raisons": ["restauration_travaux"], "fait_x": "oui"},
    "cloture_at": None,
}


def _supabase(**over) -> _FakeSupabase:
    tables = {
        "projets": [PROJET_OUVERT],
        "monuments": [MONUMENT],
        "project_members": [{"role": "owner"}],
    }
    tables.update(over)
    return _FakeSupabase(tables)


class _Capture:
    """Remplace le moteur : on ne teste pas le diagnostic, mais ses entrées."""

    def __init__(self) -> None:
        self.monument: dict | None = None
        self.answers = None

    def __call__(self, monument, population, answers):
        self.monument = monument
        self.answers = answers
        return {"aidesEligibles": []}


def _run(body: DeterministicDiagnosticRequest, supabase, capture, *, offre=VEILLE):
    """Lance la route en remplaçant le moteur et la résolution d'offre.

    L'offre par défaut est Veille : ces tests parlent du CADRAGE passé au
    moteur, pas du caviardage — laisser le gratuit masquerait les aides à venir
    et brouillerait leurs assertions.
    """
    with (
        patch("routers.aides.deterministic_diagnostic_for", capture),
        patch("routers.aides.quotas.offre_du_monument", return_value=offre) as resolution,
    ):
        result = diagnostic_deterministe(body=body, user_id="u1", supabase=supabase)
    return result, resolution


class ValidationTests(unittest.TestCase):
    def test_refuse_une_requete_sans_cible(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            DeterministicDiagnosticRequest()

    def test_accepte_projet_id_seul(self) -> None:
        self.assertEqual(DeterministicDiagnosticRequest(projet_id="p1").projet_id, "p1")

    def test_accepte_monument_id_seul(self) -> None:
        self.assertEqual(DeterministicDiagnosticRequest(monument_id="m1").monument_id, "m1")


class CibleProjetTests(unittest.TestCase):
    def test_fusionne_les_travaux_du_projet(self) -> None:
        capture = _Capture()
        _run(DeterministicDiagnosticRequest(projet_id="p1"), _supabase(), capture)
        assert capture.monument is not None
        self.assertEqual(capture.monument["travaux_envisages"], ["toiture"])
        self.assertEqual(capture.monument["id"], "m1")

    def test_reprend_le_questionnaire_du_projet_si_answers_absent(self) -> None:
        capture = _Capture()
        _run(DeterministicDiagnosticRequest(projet_id="p1"), _supabase(), capture)
        self.assertEqual(capture.answers, PROJET_OUVERT["questionnaire"])

    def test_answers_remplace_entierement_le_questionnaire(self) -> None:
        """Remplacement, pas fusion profonde : le front envoie l'état complet."""
        capture = _Capture()
        _run(
            DeterministicDiagnosticRequest(projet_id="p1", answers={"fait_y": "non"}),
            _supabase(),
            capture,
        )
        self.assertEqual(capture.answers, {"fait_y": "non"})

    def test_answers_vide_est_respecte(self) -> None:
        """`{}` (questionnaire vierge du wizard) n'est pas `None`."""
        capture = _Capture()
        _run(DeterministicDiagnosticRequest(projet_id="p1", answers={}), _supabase(), capture)
        self.assertEqual(capture.answers, {})

    def test_offre_resolue_sur_le_monument_parent(self) -> None:
        """Le caviardage des aides à venir suit l'offre qui gouverne le BIEN,
        et le projet ne fait que désigner ce monument."""
        capture = _Capture()
        _, resolution = _run(DeterministicDiagnosticRequest(projet_id="p1"), _supabase(), capture)
        self.assertEqual(resolution.call_args.args[1], "m1")

    def test_projet_introuvable(self) -> None:
        capture = _Capture()
        with self.assertRaises(HTTPException) as ctx:
            _run(DeterministicDiagnosticRequest(projet_id="pX"), _supabase(projets=[]), capture)
        self.assertEqual(ctx.exception.status_code, 404)


class CompatMonumentTests(unittest.TestCase):
    def test_retombe_sur_le_projet_ouvert_le_plus_recent(self) -> None:
        capture = _Capture()
        _run(DeterministicDiagnosticRequest(monument_id="m1"), _supabase(), capture)
        assert capture.monument is not None
        self.assertEqual(capture.monument["travaux_envisages"], ["toiture"])
        self.assertEqual(capture.answers, PROJET_OUVERT["questionnaire"])

    def test_monument_sans_projet_diagnostique_quand_meme(self) -> None:
        """Fail-open : pas de projet = pas de cadrage, jamais une erreur."""
        capture = _Capture()
        _run(DeterministicDiagnosticRequest(monument_id="m1"), _supabase(projets=[]), capture)
        assert capture.monument is not None
        self.assertNotIn("travaux_envisages", capture.monument)
        self.assertEqual(capture.answers, {})


if __name__ == "__main__":
    unittest.main()
