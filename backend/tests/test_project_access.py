"""Tests des fonctions pures de contrôle d'accès projet."""

import unittest

from services.project_access import can_delete_document, get_project_role, role_at_least


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Mime le chaînage fluent de supabase-py ; renvoie une réponse fixe."""

    def __init__(self, response):
        self._response = response

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return self._response


class _FakeSupabase:
    def __init__(self, responses_by_table):
        self._responses = responses_by_table

    def table(self, name):
        return _FakeQuery(self._responses.get(name, _FakeResponse(None)))


class RoleAtLeastTests(unittest.TestCase):
    def test_owner_satisfies_every_level(self) -> None:
        self.assertTrue(role_at_least("owner", "member"))
        self.assertTrue(role_at_least("owner", "co_owner"))
        self.assertTrue(role_at_least("owner", "owner"))

    def test_co_owner_is_not_owner(self) -> None:
        self.assertTrue(role_at_least("co_owner", "member"))
        self.assertTrue(role_at_least("co_owner", "co_owner"))
        self.assertFalse(role_at_least("co_owner", "owner"))

    def test_member_is_lowest(self) -> None:
        self.assertTrue(role_at_least("member", "member"))
        self.assertFalse(role_at_least("member", "co_owner"))

    def test_none_role_satisfies_nothing(self) -> None:
        self.assertFalse(role_at_least(None, "member"))


class CanDeleteDocumentTests(unittest.TestCase):
    def test_uploader_can_always_delete_own(self) -> None:
        self.assertTrue(can_delete_document("member", is_uploader=True))

    def test_member_cannot_delete_others(self) -> None:
        self.assertFalse(can_delete_document("member", is_uploader=False))

    def test_co_owner_and_owner_delete_any(self) -> None:
        self.assertTrue(can_delete_document("co_owner", is_uploader=False))
        self.assertTrue(can_delete_document("owner", is_uploader=False))

    def test_non_member_cannot_delete(self) -> None:
        self.assertFalse(can_delete_document(None, is_uploader=False))

    def test_uploader_without_project_role_can_delete(self) -> None:
        # Document personnel non rattaché à un projet : l'auteur peut le supprimer.
        self.assertTrue(can_delete_document(None, is_uploader=True))


class GetProjectRoleTests(unittest.TestCase):
    def test_returns_membership_role_when_present(self) -> None:
        supabase = _FakeSupabase({"project_members": _FakeResponse({"role": "co_owner"})})
        self.assertEqual(get_project_role(supabase, "mon-1", "user-1"), "co_owner")

    def test_falls_back_to_owner_when_user_owns_monument(self) -> None:
        # Pas de ligne d'appartenance, mais l'utilisateur est le user_id (propriétaire
        # authoritatif, immuable) du monument : il doit rester 'owner' de son projet.
        supabase = _FakeSupabase(
            {
                "project_members": _FakeResponse(None),
                "monuments": _FakeResponse({"id": "mon-1"}),
            }
        )
        self.assertEqual(get_project_role(supabase, "mon-1", "user-1"), "owner")

    def test_returns_none_when_neither_member_nor_owner(self) -> None:
        supabase = _FakeSupabase(
            {
                "project_members": _FakeResponse(None),
                "monuments": _FakeResponse(None),
            }
        )
        self.assertIsNone(get_project_role(supabase, "mon-1", "user-1"))


if __name__ == "__main__":
    unittest.main()
