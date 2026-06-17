"""Unit tests for the add-document-to-projects pure helper.

Adding a document to a project must *associate* the existing document with the
target project (append to monument_ids) rather than create an independent copy.
These tests prove the merge stays deduplicated and order-preserving.
"""

import unittest

from routers.documents import AddToProjectsRequest, _merge_monument_ids


class MergeMonumentIdsTests(unittest.TestCase):
    def test_appends_new_projects(self) -> None:
        self.assertEqual(_merge_monument_ids(["mon-A"], ["mon-B"]), ["mon-A", "mon-B"])

    def test_preserves_existing_order_and_appends(self) -> None:
        self.assertEqual(
            _merge_monument_ids(["mon-A", "mon-B"], ["mon-C", "mon-D"]),
            ["mon-A", "mon-B", "mon-C", "mon-D"],
        )

    def test_skips_duplicates(self) -> None:
        self.assertEqual(_merge_monument_ids(["mon-A"], ["mon-A", "mon-B"]), ["mon-A", "mon-B"])

    def test_dedupes_within_new_list(self) -> None:
        self.assertEqual(_merge_monument_ids([], ["mon-A", "mon-A"]), ["mon-A"])

    def test_empty_existing(self) -> None:
        self.assertEqual(_merge_monument_ids([], ["mon-A", "mon-B"]), ["mon-A", "mon-B"])

    def test_does_not_mutate_inputs(self) -> None:
        existing = ["mon-A"]
        new = ["mon-B"]
        _merge_monument_ids(existing, new)
        self.assertEqual(existing, ["mon-A"])
        self.assertEqual(new, ["mon-B"])


class AddToProjectsRequestTests(unittest.TestCase):
    def test_accepts_monument_ids_list(self) -> None:
        body = AddToProjectsRequest(monument_ids=["a", "b"])
        self.assertEqual(body.monument_ids, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
