"""Endpoint de reprise des pièces et détachement d'un document."""

import unittest
from unittest.mock import patch

from routers.dossiers import UpdateChecklistItemRequest


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, store, table):
        self._store = store
        self._table = table
        self._update = None

    def select(self, *a, **k):
        return self

    def update(self, values, *a, **k):
        self._update = values
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def or_(self, *a, **k):
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self._update is not None:
            self._store.updates.setdefault(self._table, []).append(self._update)
            return _Resp([self._store.rows.get(self._table)])
        return _Resp(self._store.rows.get(self._table))


class _FakeSupabase:
    def __init__(self, rows):
        self.rows = rows
        self.updates: dict[str, list] = {}

    def table(self, name):
        return _Query(self, name)


_DOSSIER = {
    "id": "d1",
    "monument_id": "p1",
    "user_id": "u1",
    "checklist": [
        {
            "id": "i1",
            "label": "RIB",
            "description": "",
            "obligatoire": True,
            "categorie": "document",
            "ordre": 1,
            "statut": "manquant",
            "pieceId": "rib",
        }
    ],
}


class ReprendrePiecesTests(unittest.TestCase):
    def test_endpoint_applique_la_reprise(self) -> None:
        from routers.dossiers import reprendre_pieces

        supabase = _FakeSupabase({"dossiers": _DOSSIER})

        reprise = [{**_DOSSIER["checklist"][0], "statut": "repris", "documentId": "doc1"}]
        with (
            patch("routers.dossiers.require_project_access", return_value=None),
            patch("routers.dossiers.apply_reuse", return_value=(reprise, 1)) as faux,
        ):
            reprendre_pieces("d1", user_id="u1", supabase=supabase)

        faux.assert_called_once()
        ecrit = supabase.updates["dossiers"][0]
        self.assertEqual(ecrit["checklist"][0]["statut"], "repris")
        # Un item « repris » ne compte pas dans la progression.
        self.assertEqual(ecrit["progression_pourcentage"], 0)


class DetachementTests(unittest.TestCase):
    def test_detacher_vide_le_document(self) -> None:
        body = UpdateChecklistItemRequest(statut="manquant", detacher=True)
        self.assertTrue(body.detacher)
        self.assertIsNone(body.document_id)

    def test_detacher_absent_par_defaut(self) -> None:
        body = UpdateChecklistItemRequest(statut="fourni", document_id="doc1")
        self.assertFalse(body.detacher)


if __name__ == "__main__":
    unittest.main()
