"""Validation de la visibilité au dépôt (POST) et à la mise à jour (PATCH)."""

import unittest

from fastapi import HTTPException

from routers.documents import (
    CreateDocumentRequest,
    UpdateDocumentRequest,
    create_document,
    update_document,
)


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, response, inserted, updated):
        self._response = response
        self._inserted = inserted
        self._updated = updated
        self._mode = None  # 'insert' | 'update' | None
        # Le vrai client rend un DICT après maybe_single()/single(), une LISTE
        # sinon : plusieurs gardes lisent la même table dans les deux modes.
        self._single = False

    def select(self, *a, **k):
        return self

    def insert(self, row, *a, **k):
        self._inserted.append(row)
        self._mode = "insert"
        return self

    def update(self, row, *a, **k):
        self._updated.append(row)
        self._mode = "update"
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._single = True
        return self

    def execute(self):
        # supabase renvoie une LISTE pour insert/update, l'objet configuré sinon.
        if self._mode == "insert":
            return _Resp([{**self._inserted[-1], "id": "d1"}])
        if self._mode == "update":
            return _Resp([{**self._updated[-1], "id": "d1"}])
        data = self._response.data
        if self._single:
            return _Resp(data)
        if data is None:
            return _Resp([])
        return _Resp(data if isinstance(data, list) else [data])


class _FakeSupabase:
    def __init__(self, responses):
        self._responses = responses
        self.inserted: list = []
        self.updated: list = []

    def table(self, name):
        return _Query(self._responses.get(name, _Resp(None)), self.inserted, self.updated)


def _supabase(*, caller_role, doc=None):
    return _FakeSupabase(
        {
            "project_members": _Resp(
                {"monument_id": "m1", "role": caller_role} if caller_role else None
            ),
            "monuments": _Resp(None),
            "documents": _Resp(doc) if doc is not None else _Resp(None),
        }
    )


class CreateVisibilityTests(unittest.TestCase):
    def _body(self, **over):
        base = dict(
            nom="Devis",
            nom_fichier="devis.pdf",
            type="devis",
            taille_fichier=10,
            mime_type="application/pdf",
            url="u1/devis.pdf",
            monument_ids=["m1"],
        )
        base.update(over)
        return CreateDocumentRequest(**base)

    def test_owner_default_is_responsables(self):
        # Défaut sûr : un document fraîchement déposé n'est PAS visible par toute
        # l'équipe. Même un chef de projet doit ouvrir explicitement à l'équipe.
        fake = _supabase(caller_role="owner")
        create_document(self._body(), user_id="u1", supabase=fake)
        self.assertEqual(fake.inserted[0]["visibility"], "responsables")

    def test_member_default_is_responsables(self):
        fake = _supabase(caller_role="member")
        create_document(self._body(), user_id="u1", supabase=fake)
        self.assertEqual(fake.inserted[0]["visibility"], "responsables")

    def test_member_cannot_set_team(self):
        fake = _supabase(caller_role="member")
        with self.assertRaises(HTTPException) as ctx:
            create_document(self._body(visibility="team"), user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_custom_keeps_allowed_ids(self):
        fake = _supabase(caller_role="owner")
        create_document(
            self._body(visibility="custom", allowed_user_ids=["u9"]),
            user_id="u1",
            supabase=fake,
        )
        self.assertEqual(fake.inserted[0]["visibility"], "custom")
        self.assertEqual(fake.inserted[0]["allowed_user_ids"], ["u9"])

    def test_non_custom_clears_allowed_ids(self):
        fake = _supabase(caller_role="owner")
        create_document(
            self._body(visibility="responsables", allowed_user_ids=["u9"]),
            user_id="u1",
            supabase=fake,
        )
        self.assertEqual(fake.inserted[0]["allowed_user_ids"], [])


class UpdateVisibilityTests(unittest.TestCase):
    DOC = {
        "id": "d1",
        "user_id": "u2",
        "monument_ids": ["m1"],
        "visibility": "team",
        "allowed_user_ids": [],
    }

    def test_member_cannot_set_team_on_own_doc(self):
        own = {**self.DOC, "user_id": "u1"}
        fake = _supabase(caller_role="member", doc=own)
        with self.assertRaises(HTTPException) as ctx:
            update_document(
                "d1", UpdateDocumentRequest(visibility="team"), user_id="u1", supabase=fake
            )
        self.assertEqual(ctx.exception.status_code, 422)

    def test_co_owner_sets_custom(self):
        fake = _supabase(caller_role="co_owner", doc=self.DOC)
        update_document(
            "d1",
            UpdateDocumentRequest(visibility="custom", allowed_user_ids=["u5"]),
            user_id="u1",
            supabase=fake,
        )
        self.assertEqual(fake.updated[0]["visibility"], "custom")
        self.assertEqual(fake.updated[0]["allowed_user_ids"], ["u5"])

    def test_member_cannot_edit_others_doc(self):
        fake = _supabase(caller_role="member", doc=self.DOC)  # auteur = u2
        with self.assertRaises(HTTPException) as ctx:
            update_document(
                "d1", UpdateDocumentRequest(visibility="responsables"), user_id="u1", supabase=fake
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_co_owner_cannot_edit_hidden_custom_doc(self):
        # adjoint exclu d'un doc « personnes choisies » → ne peut pas le modifier
        hidden = {
            "id": "d1",
            "user_id": "u2",
            "monument_ids": ["m1"],
            "visibility": "custom",
            "allowed_user_ids": ["u9"],
        }
        fake = _supabase(caller_role="co_owner", doc=hidden)
        with self.assertRaises(HTTPException) as ctx:
            update_document("d1", UpdateDocumentRequest(nom="Renommé"), user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
