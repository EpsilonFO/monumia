"""La consultation respecte la visibilité : détail/URL signée masqués, liste filtrée."""

import unittest

from fastapi import HTTPException

from routers.documents import get_document, list_documents


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, response):
        self._response = response

    def __getattr__(self, _name):
        def _chain(*a, **k):
            return self

        return _chain

    def execute(self):
        return self._response


class _FakeSupabase:
    def __init__(self, responses):
        self._responses = responses

    def table(self, name):
        return _Query(self._responses.get(name, _Resp(None)))


def _supabase(*, doc=None, docs=None, caller_role=None):
    return _FakeSupabase(
        {
            "documents": _Resp(doc if doc is not None else docs),
            "project_members": _Resp({"role": caller_role} if caller_role else None),
            "monuments": _Resp(None),
        }
    )


RESTRICTED = {
    "id": "d1",
    "user_id": "u2",  # déposé par quelqu'un d'autre
    "monument_ids": ["m1"],
    "visibility": "responsables",
    "allowed_user_ids": [],
}


class GetDocumentViewTests(unittest.TestCase):
    def test_member_cannot_get_restricted(self):
        fake = _supabase(doc=RESTRICTED, caller_role="member")
        with self.assertRaises(HTTPException) as ctx:
            get_document("d1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_co_owner_can_get_restricted(self):
        fake = _supabase(doc=RESTRICTED, caller_role="co_owner")
        result = get_document("d1", user_id="u1", supabase=fake)
        self.assertEqual(result["id"], "d1")


class ListDocumentsFilterTests(unittest.TestCase):
    def test_member_listing_excludes_restricted(self):
        rows = [
            {
                "id": "d1",
                "user_id": "u2",
                "monument_ids": ["m1"],
                "visibility": "team",
                "allowed_user_ids": [],
            },
            {
                "id": "d2",
                "user_id": "u2",
                "monument_ids": ["m1"],
                "visibility": "responsables",
                "allowed_user_ids": [],
            },
        ]
        fake = _supabase(docs=rows, caller_role="member")
        result = list_documents(monument_id="m1", type=None, user_id="u1", supabase=fake)
        self.assertEqual([d["id"] for d in result], ["d1"])


if __name__ == "__main__":
    unittest.main()
