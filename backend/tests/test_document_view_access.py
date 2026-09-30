"""La consultation respecte la visibilité : détail/URL signée masqués, liste filtrée."""

import unittest

from fastapi import HTTPException

from routers.documents import (
    AddToProjectsRequest,
    add_document_to_projects,
    get_document,
    list_documents,
)


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    """Chaînage fluent bouchonné.

    Le vrai client renvoie un DICT (ou None) après `maybe_single()` / `single()`,
    et une LISTE sinon. Le faux doit faire la même différence : plusieurs gardes
    lisent la même table dans les deux modes (rôle unitaire vs périmètre complet
    de l'utilisateur), et un faux qui rendrait toujours un dict les casserait.
    """

    @staticmethod
    def _coerce(data, single: bool):
        if single:
            return data
        if data is None:
            return []
        return data if isinstance(data, list) else [data]

    def __init__(self, response):
        self._response = response
        self._single = False

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._single = True
        return self

    def __getattr__(self, _name):
        def _chain(*a, **k):
            return self

        return _chain

    def execute(self):
        return _Resp(self._coerce(self._response.data, self._single))


class _FakeSupabase:
    def __init__(self, responses):
        self._responses = responses

    def table(self, name):
        return _Query(self._responses.get(name, _Resp(None)))


def _supabase(*, doc=None, docs=None, caller_role=None):
    return _FakeSupabase(
        {
            "documents": _Resp(doc if doc is not None else docs),
            "project_members": _Resp(
                {"monument_id": "m1", "role": caller_role} if caller_role else None
            ),
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


class ReshareEscalationTests(unittest.TestCase):
    def test_member_cannot_reshare_restricted(self):
        """Un membre ne pouvant pas consulter un document restreint ne peut pas le repartager."""
        fake = _supabase(doc=RESTRICTED, caller_role="member")
        with self.assertRaises(HTTPException) as ctx:
            add_document_to_projects(
                "d1",
                AddToProjectsRequest(monument_ids=["m2"]),
                user_id="u1",
                supabase=fake,
            )
        self.assertEqual(ctx.exception.status_code, 404)


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
        result = list_documents(
            monument_id="m1", projet_id=None, type=None, user_id="u1", supabase=fake
        )
        self.assertEqual([d["id"] for d in result], ["d1"])


class _OrQuery(_Query):
    """Comme `_Query`, en gardant les clauses `or_` posées sur la table."""

    def __init__(self, response, journal):
        super().__init__(response)
        self._journal = journal

    def or_(self, clauses):
        self._journal.append(clauses)
        return self


class _OrFakeSupabase(_FakeSupabase):
    def __init__(self, responses):
        super().__init__(responses)
        self.or_clauses: list[str] = []

    def table(self, name):
        return _OrQuery(self._responses.get(name, _Resp(None)), self.or_clauses)


def _chantier_doc(doc_id, visibility):
    """Un document déposé sur le seul chantier p1, pas sur le monument."""
    return {
        "id": doc_id,
        "user_id": "u2",
        "monument_ids": [],
        "projet_ids": ["p1"],
        "visibility": visibility,
        "allowed_user_ids": [],
    }


class ListMonumentDocumentsIncludesProjetsTests(unittest.TestCase):
    """L'onglet Documents d'un monument montre aussi les pièces de ses chantiers."""

    def _fake(self, *, caller_role, propres):
        return _OrFakeSupabase(
            {
                "documents": _Resp(
                    [_chantier_doc("d-team", "team"), _chantier_doc("d-resp", "responsables")]
                ),
                "project_members": _Resp({"monument_id": "m1", "role": caller_role}),
                "monuments": _Resp(None),
                "projets": _Resp([{"id": "p1", "user_id": "u9"}]),
                "projet_members": _Resp(propres),
            }
        )

    def test_query_covers_monument_and_its_projets(self):
        fake = self._fake(caller_role="member", propres=[])
        list_documents(monument_id="m1", projet_id=None, type=None, user_id="u1", supabase=fake)
        self.assertEqual(fake.or_clauses, ["monument_ids.cs.{m1},projet_ids.ov.{p1}"])

    def test_member_sees_team_projet_doc_not_responsables(self):
        fake = self._fake(caller_role="member", propres=[])
        result = list_documents(
            monument_id="m1", projet_id=None, type=None, user_id="u1", supabase=fake
        )
        self.assertEqual([d["id"] for d in result], ["d-team"])

    def test_co_owner_of_the_projet_sees_responsables_doc(self):
        """Le rôle effectif sur le chantier est le max des deux appartenances."""
        fake = self._fake(caller_role="member", propres=[{"projet_id": "p1", "role": "co_owner"}])
        result = list_documents(
            monument_id="m1", projet_id=None, type=None, user_id="u1", supabase=fake
        )
        self.assertEqual([d["id"] for d in result], ["d-team", "d-resp"])


if __name__ == "__main__":
    unittest.main()
