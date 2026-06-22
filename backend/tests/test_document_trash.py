"""Helpers purs de la corbeille + élargissement de la vue « Mes documents »."""

import unittest

from routers.documents import (
    _best_role,
    _filter_visible,
    _should_auto_trash,
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
