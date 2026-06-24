"""Garde-fou : un suivi ne peut être créé/modifié que si un dossier existe
pour l'aide dans le projet. Test du router avec un faux client Supabase."""

import unittest

from fastapi import HTTPException

from routers.suivi import UpsertSuiviRequest, upsert_aide_suivi


class _Resp:
    def __init__(self, data: list) -> None:
        self.data = data


class _FakeTable:
    def __init__(self, name: str, store: dict) -> None:
        self._name = name
        self._store = store
        self._op = "select"
        self._row: dict | None = None

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

    def execute(self) -> _Resp:
        if self._op == "select":
            return _Resp(list(self._store.get(self._name, [])))
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


def _call(store: dict):
    return upsert_aide_suivi(
        monument_id="m1",
        aide_id="a1",
        body=UpsertSuiviRequest(statut="a_faire"),
        user_id="u1",
        supabase=_FakeClient(store),
    )


class DossierGuardTests(unittest.TestCase):
    def test_rejects_when_no_dossier(self) -> None:
        store = {"monuments": [{"id": "m1"}], "dossiers": [], "aide_suivis": []}
        with self.assertRaises(HTTPException) as ctx:
            _call(store)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_accepts_when_dossier_exists(self) -> None:
        store = {
            "monuments": [{"id": "m1"}],
            "dossiers": [{"id": "d1"}],
            "aide_suivis": [],
        }
        result = _call(store)
        self.assertEqual(result["aide_id"], "a1")
        self.assertEqual(result["monument_id"], "m1")


if __name__ == "__main__":
    unittest.main()
