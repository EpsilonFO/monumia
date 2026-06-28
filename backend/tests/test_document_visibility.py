"""Tests des fonctions pures de visibilité des documents."""

import unittest

from services.project_access import (
    allowed_visibilities,
    can_edit_visibility,
    can_modify_document,
    can_view_document,
)


def _view(visibility, role, *, allowed=None, uploader="u2", viewer="u1"):
    return can_view_document(
        visibility=visibility,
        allowed_user_ids=allowed or [],
        uploader_id=uploader,
        viewer_id=viewer,
        viewer_role=role,
    )


class CanViewDocumentTests(unittest.TestCase):
    def test_author_always_views(self) -> None:
        self.assertTrue(_view("custom", None, uploader="u1", viewer="u1"))

    def test_owner_always_views(self) -> None:
        self.assertTrue(_view("custom", "owner"))

    def test_non_member_never_views(self) -> None:
        self.assertFalse(_view("team", None))

    def test_team_visible_to_any_member(self) -> None:
        self.assertTrue(_view("team", "member"))

    def test_responsables_hidden_from_member(self) -> None:
        self.assertFalse(_view("responsables", "member"))

    def test_responsables_visible_to_co_owner(self) -> None:
        self.assertTrue(_view("responsables", "co_owner"))

    def test_custom_visible_to_listed_member(self) -> None:
        self.assertTrue(_view("custom", "member", allowed=["u1"]))

    def test_custom_hidden_from_unlisted_co_owner(self) -> None:
        # un adjoint peut être exclu d'un document « personnes choisies »
        self.assertFalse(_view("custom", "co_owner", allowed=["u3"]))

    def test_custom_listed_but_non_member_denied(self) -> None:
        # défense : un id listé mais non membre (role None) ne voit pas
        self.assertFalse(_view("custom", None, allowed=["u1"]))


def _modify(visibility, role, *, allowed=None, uploader="u2", viewer="u1"):
    return can_modify_document(
        visibility=visibility,
        allowed_user_ids=allowed or [],
        uploader_id=uploader,
        viewer_id=viewer,
        viewer_role=role,
    )


class CanModifyDocumentTests(unittest.TestCase):
    """Modifier/supprimer un document exige de pouvoir le CONSULTER (bug : un
    adjoint sans accès pouvait quand même supprimer/remplacer une pièce)."""

    def test_co_owner_cannot_modify_hidden_custom(self) -> None:
        # adjoint exclu d'un doc « personnes choisies » → aucune action possible
        self.assertFalse(_modify("custom", "co_owner", allowed=["u3"]))

    def test_co_owner_can_modify_visible_docs(self) -> None:
        self.assertTrue(_modify("team", "co_owner"))
        self.assertTrue(_modify("responsables", "co_owner"))
        self.assertTrue(_modify("custom", "co_owner", allowed=["u1"]))

    def test_uploader_can_modify_even_when_custom(self) -> None:
        self.assertTrue(_modify("custom", "member", uploader="u1", viewer="u1"))

    def test_owner_modifies_even_hidden_custom(self) -> None:
        self.assertTrue(_modify("custom", "owner", allowed=["u3"]))

    def test_member_non_uploader_cannot_modify_team(self) -> None:
        # un simple membre ne peut agir que sur ses propres documents
        self.assertFalse(_modify("team", "member"))

    def test_non_member_cannot_modify(self) -> None:
        self.assertFalse(_modify("team", None))


class AllowedVisibilitiesTests(unittest.TestCase):
    def test_responsable_gets_all(self) -> None:
        self.assertEqual(allowed_visibilities("owner"), {"team", "responsables", "custom"})
        self.assertEqual(allowed_visibilities("co_owner"), {"team", "responsables", "custom"})

    def test_member_has_no_team(self) -> None:
        self.assertEqual(allowed_visibilities("member"), {"responsables", "custom"})
        self.assertEqual(allowed_visibilities(None), {"responsables", "custom"})


class CanEditVisibilityTests(unittest.TestCase):
    def test_uploader_can_edit_own(self) -> None:
        self.assertTrue(can_edit_visibility("member", is_uploader=True))

    def test_member_cannot_edit_others(self) -> None:
        self.assertFalse(can_edit_visibility("member", is_uploader=False))

    def test_responsable_edits_any(self) -> None:
        self.assertTrue(can_edit_visibility("co_owner", is_uploader=False))
        self.assertTrue(can_edit_visibility("owner", is_uploader=False))


if __name__ == "__main__":
    unittest.main()
