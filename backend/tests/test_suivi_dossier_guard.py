"""Gardes du suivi d'aide, au grain PROJET.

Deux invariants :
  - un suivi ne peut être créé/modifié que si un dossier existe pour l'aide
    DANS CE PROJET (409 sinon) — pas de suivi orphelin ;
  - la ligne écrite porte `projet_id` ET `monument_id` (dénormalisé pour les
    gardes et les requêtes batch du dashboard).

Test du router avec un faux client Supabase.
"""

import unittest

from fastapi import HTTPException

from routers.suivi import UpsertSuiviRequest, upsert_aide_suivi


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _FakeTable:
    def __init__(self, name: str, store: dict) -> None:
        self._name = name
        self._store = store
        self._op = "select"
        self._row: dict | None = None
        self._single = False

    def select(self, *_a, **_k) -> "_FakeTable":
        self._op = "select"
        return self

    def insert(self, row: dict) -> "_FakeTable":
        self._op = "insert"
        self._row = row
        return self

    def update(self, row: dict) -> "_FakeTable":
        self._op = "update"
        self._row = row
        return self

    def eq(self, *_a, **_k) -> "_FakeTable":
        return self

    def maybe_single(self) -> "_FakeTable":
        self._single = True
        return self

    def execute(self) -> _Resp:
        if self._op == "select":
            rows = list(self._store.get(self._name, []))
            if self._single:
                return _Resp(rows[0] if rows else None)
            return _Resp(rows)
        if self._op == "insert":
            return _Resp([dict(self._row or {})])
        if self._op == "update":
            base = (self._store.get(self._name) or [{}])[0]
            return _Resp([{**base, **(self._row or {})}])
        return _Resp([])


class _FakeClient:
    def __init__(self, store: dict) -> None:
        self._store = store

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(name, self._store)


def _store(dossiers: list[dict]) -> dict:
    """État minimal : un projet sur un monument dont u1 est chef de projet."""
    return {
        "projets": [{"id": "p1", "monument_id": "m1", "user_id": "u1"}],
        "project_members": [{"role": "owner"}],
        "monuments": [{"id": "m1", "user_id": "u1"}],
        "dossiers": dossiers,
        "aide_suivis": [],
    }


def _call(store: dict):
    return upsert_aide_suivi(
        projet_id="p1",
        aide_id="a1",
        body=UpsertSuiviRequest(statut="a_faire"),
        user_id="u1",
        supabase=_FakeClient(store),
    )


class DossierGuardTests(unittest.TestCase):
    def test_rejects_when_no_dossier(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _call(_store([]))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_accepts_when_dossier_exists(self) -> None:
        result = _call(_store([{"id": "d1", "projet_id": "p1", "aide_id": "a1"}]))
        self.assertEqual(result["aide_id"], "a1")
        self.assertEqual(result["projet_id"], "p1")
        # Dénormalisation : le monument du projet est recopié sur le suivi.
        self.assertEqual(result["monument_id"], "m1")

    def test_projet_introuvable(self) -> None:
        store = _store([{"id": "d1"}])
        store["projets"] = []
        with self.assertRaises(HTTPException) as ctx:
            _call(store)
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
