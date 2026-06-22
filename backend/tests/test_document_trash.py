"""Helpers purs de la corbeille + élargissement de la vue « Mes documents »."""

import unittest

from fastapi import HTTPException

from routers.documents import (
    _best_role,
    _filter_visible,
    _should_auto_trash,
    remove_document_from_project,
    restore_document,
    trash_document,
    unlink_from_dossier,
)


class ShouldAutoTrashTests(unittest.TestCase):
    def test_both_empty_trashes(self):
        self.assertTrue(_should_auto_trash([], []))
        self.assertTrue(_should_auto_trash(None, None))

    def test_any_link_keeps(self):
        self.assertFalse(_should_auto_trash(["m1"], []))
        self.assertFalse(_should_auto_trash([], ["d1"]))
        self.assertFalse(_should_auto_trash(["m1"], ["d1"]))


class BestRoleTests(unittest.TestCase):
    ROLES = {"m1": "member", "m2": "owner", "m3": "co_owner"}

    def test_picks_highest_among_linked(self):
        self.assertEqual(_best_role(["m1", "m3"], self.ROLES), "co_owner")
        self.assertEqual(_best_role(["m1", "m2"], self.ROLES), "owner")

    def test_none_when_no_membership(self):
        self.assertIsNone(_best_role(["mX"], self.ROLES))
        self.assertIsNone(_best_role([], self.ROLES))


class FilterVisibleTests(unittest.TestCase):
    def _row(self, **over):
        base = dict(
            id="d1", user_id="u2", monument_ids=["m1"],
            visibility="team", allowed_user_ids=[],
        )
        base.update(over)
        return base

    def test_uploader_sees_own_even_without_role(self):
        rows = [self._row(user_id="u1", monument_ids=[])]
        self.assertEqual(len(_filter_visible(rows, "u1", {})), 1)

    def test_member_sees_team_not_responsables(self):
        roles = {"m1": "member"}
        team = self._row(visibility="team")
        resp = self._row(visibility="responsables")
        out = _filter_visible([team, resp], "u1", roles)
        self.assertEqual([r["visibility"] for r in out], ["team"])

    def test_non_member_excluded(self):
        rows = [self._row(visibility="team", monument_ids=["mX"])]
        self.assertEqual(_filter_visible(rows, "u1", {}), [])


# ---------------------------------------------------------------------------
# Fake Supabase pour les tests d'endpoints (Task 4)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, response, updated):
        self._response = response
        self._updated = updated
        self._mode = None

    def select(self, *a, **k):
        return self

    def update(self, row, *a, **k):
        self._updated.append(row)
        self._mode = "update"
        return self

    def eq(self, *a, **k):
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self._mode == "update":
            return _Resp([{**self._updated[-1], "id": "d1"}])
        return self._response


class _FakeSupabase:
    def __init__(self, responses):
        self._responses = responses
        self.updated: list = []

    def table(self, name):
        return _Query(self._responses.get(name, _Resp(None)), self.updated)


def _fake(*, doc, caller_role="owner", dossier=None):
    return _FakeSupabase(
        {
            "documents": _Resp(doc),
            "project_members": _Resp({"role": caller_role} if caller_role else None),
            "monuments": _Resp(None),
            "dossiers": _Resp(dossier),
        }
    )


class TrashEndpointTests(unittest.TestCase):
    DOC = {"id": "d1", "user_id": "u1", "monument_ids": ["m1"], "dossiers_utilises": ["x"]}

    def test_trash_detaches_all_and_sets_flag(self):
        fake = _fake(doc=self.DOC, caller_role="member")  # uploader u1
        trash_document("d1", user_id="u1", supabase=fake)
        patch = fake.updated[0]
        self.assertEqual(patch["monument_ids"], [])
        self.assertEqual(patch["dossiers_utilises"], [])
        self.assertIsNotNone(patch["trashed_at"])

    def test_trash_forbidden_for_plain_member_non_uploader(self):
        doc = {**self.DOC, "user_id": "u2"}
        fake = _fake(doc=doc, caller_role="member")  # caller u1 != auteur
        with self.assertRaises(HTTPException) as ctx:
            trash_document("d1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_restore_clears_flag_for_uploader(self):
        doc = {**self.DOC, "trashed_at": "2026-01-01T00:00:00Z"}
        fake = _fake(doc=doc, caller_role="member")
        restore_document("d1", user_id="u1", supabase=fake)
        self.assertIsNone(fake.updated[0]["trashed_at"])

    def test_restore_forbidden_for_non_uploader(self):
        doc = {**self.DOC, "user_id": "u2", "trashed_at": "2026-01-01T00:00:00Z"}
        fake = _fake(doc=doc, caller_role="owner")
        with self.assertRaises(HTTPException) as ctx:
            restore_document("d1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)


class UnlinkAutoTrashTests(unittest.TestCase):
    def test_unlink_last_dossier_no_project_trashes(self):
        doc = {"id": "d1", "user_id": "u1", "monument_ids": [], "dossiers_utilises": ["dz"]}
        fake = _fake(doc=doc, caller_role="member", dossier={"id": "dz", "monument_id": "m1"})
        unlink_from_dossier("d1", "dz", user_id="u1", supabase=fake)
        patch = fake.updated[0]
        self.assertEqual(patch["dossiers_utilises"], [])
        self.assertIsNotNone(patch["trashed_at"])

    def test_unlink_with_remaining_project_keeps(self):
        doc = {"id": "d1", "user_id": "u1", "monument_ids": ["m1"], "dossiers_utilises": ["dz"]}
        fake = _fake(doc=doc, caller_role="member", dossier={"id": "dz", "monument_id": "m1"})
        unlink_from_dossier("d1", "dz", user_id="u1", supabase=fake)
        self.assertNotIn("trashed_at", fake.updated[0])


class RemoveFromProjectTests(unittest.TestCase):
    def test_remove_one_of_two_keeps(self):
        doc = {"id": "d1", "user_id": "u1", "monument_ids": ["m1", "m2"], "dossiers_utilises": []}
        fake = _fake(doc=doc, caller_role="owner")
        remove_document_from_project("d1", "m1", user_id="u1", supabase=fake)
        patch = fake.updated[0]
        self.assertEqual(patch["monument_ids"], ["m2"])
        self.assertNotIn("trashed_at", patch)

    def test_remove_last_project_trashes(self):
        doc = {"id": "d1", "user_id": "u1", "monument_ids": ["m1"], "dossiers_utilises": []}
        fake = _fake(doc=doc, caller_role="owner")
        remove_document_from_project("d1", "m1", user_id="u1", supabase=fake)
        patch = fake.updated[0]
        self.assertEqual(patch["monument_ids"], [])
        self.assertIsNotNone(patch["trashed_at"])

    def test_remove_forbidden_for_plain_member_non_uploader(self):
        doc = {"id": "d1", "user_id": "u2", "monument_ids": ["m1"], "dossiers_utilises": []}
        fake = _fake(doc=doc, caller_role="member")
        with self.assertRaises(HTTPException) as ctx:
            remove_document_from_project("d1", "m1", user_id="u1", supabase=fake)
        self.assertEqual(ctx.exception.status_code, 403)
