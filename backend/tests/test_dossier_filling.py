"""Contrôle d'accès du remplissage d'un dossier (projets partagés).

Un collaborateur (member) doit pouvoir DÉPOSER une pièce dans un dossier (remplir
une case vide avec son propre document). En revanche, remplacer ou retirer une
pièce déjà fournie suit la règle des documents : seul l'auteur de la pièce
existante, ou un chef de projet / adjoint (co_owner/owner), peut le faire.
"""

import unittest

from fastapi import HTTPException

from routers.dossiers import UpdateChecklistItemRequest, update_checklist_item


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, response):
        self._response = response

    # chaînage fluent — toutes les méthodes renvoient self
    def select(self, *a, **k):
        return self

    def update(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return self._response


class _FakeSupabase:
    def __init__(self, responses_by_table):
        self._responses = responses_by_table

    def table(self, name):
        return _Query(self._responses.get(name, _Resp(None)))


def _make(*, caller_role, item):
    """Fabrique un faux supabase pour un dossier à une seule pièce `item`."""
    dossier = {
        "id": "dos-1",
        "projet_id": "pro-1",
        "monument_id": "mon-1",
        "checklist": [item],
    }
    return _FakeSupabase(
        {
            "dossiers": _Resp(dossier),
            "projets": _Resp({"id": "pro-1", "monument_id": "mon-1", "user_id": "owner"}),
            "projet_members": _Resp(None),
            "project_members": _Resp(
                {"monument_id": "mon-1", "role": caller_role} if caller_role else None
            ),
            "monuments": _Resp(None),
        }
    )


def _make_with_uploader(*, caller_role, current_doc_id, uploader_id):
    dossier = {
        "id": "dos-1",
        "projet_id": "pro-1",
        "monument_id": "mon-1",
        "checklist": [{"id": "it-1", "statut": "fourni", "documentId": current_doc_id}],
    }
    return _FakeSupabase(
        {
            "dossiers": _Resp(dossier),
            "projets": _Resp({"id": "pro-1", "monument_id": "mon-1", "user_id": "owner"}),
            "projet_members": _Resp(None),
            "project_members": _Resp(
                {"monument_id": "mon-1", "role": caller_role} if caller_role else None
            ),
            "monuments": _Resp(None),
            "documents": _Resp({"user_id": uploader_id}),
        }
    )


FILL = UpdateChecklistItemRequest(statut="fourni", document_id="doc-new")
REMOVE = UpdateChecklistItemRequest(statut="manquant")


class FillEmptyItemTests(unittest.TestCase):
    def test_member_can_fill_empty_item(self):
        fake = _make(caller_role="member", item={"id": "it-1", "statut": "manquant"})
        out = update_checklist_item("dos-1", "it-1", FILL, user_id="u1", supabase=fake)
        # Renvoie le dossier (pas d'exception).
        self.assertEqual(out["id"], "dos-1")


class ReplaceOrRemoveTests(unittest.TestCase):
    def test_member_cannot_replace_others_piece(self):
        fake = _make_with_uploader(caller_role="member", current_doc_id="doc-x", uploader_id="u2")
        with self.assertRaises(HTTPException) as ctx:
            update_checklist_item("dos-1", "it-1", FILL, user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_member_can_replace_own_piece(self):
        fake = _make_with_uploader(
            caller_role="member", current_doc_id="doc-mine", uploader_id="u1"
        )
        out = update_checklist_item("dos-1", "it-1", FILL, user_id="u1", supabase=fake)
        self.assertEqual(out["id"], "dos-1")

    def test_member_cannot_remove_others_piece(self):
        fake = _make_with_uploader(caller_role="member", current_doc_id="doc-x", uploader_id="u2")
        with self.assertRaises(HTTPException) as ctx:
            update_checklist_item("dos-1", "it-1", REMOVE, user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_co_owner_can_replace_others_piece(self):
        fake = _make_with_uploader(caller_role="co_owner", current_doc_id="doc-x", uploader_id="u2")
        out = update_checklist_item("dos-1", "it-1", FILL, user_id="u1", supabase=fake)
        self.assertEqual(out["id"], "dos-1")

    def test_non_member_is_rejected(self):
        # Pas membre du projet → _get_dossier_or_404 lève (404/403).
        fake = _make(caller_role=None, item={"id": "it-1", "statut": "manquant"})
        with self.assertRaises(HTTPException):
            update_checklist_item("dos-1", "it-1", FILL, user_id="u9", supabase=fake)


if __name__ == "__main__":
    unittest.main()
