"""Unit tests for `_should_generate_qcm` — the pure guard that decides whether
the QCM-generation phase runs.

QCM is generated only when there is at least one aide carrying an incertitude
AND the caller did not explicitly opt out via `skip_qcm`.
"""

import unittest

import matching_engine as m


class ShouldGenerateQcmTests(unittest.TestCase):
    def test_nonempty_and_not_skipped_generates(self) -> None:
        self.assertTrue(m._should_generate_qcm(["aide-A"], skip_qcm=False))

    def test_nonempty_but_skipped_does_not_generate(self) -> None:
        self.assertFalse(m._should_generate_qcm(["aide-A"], skip_qcm=True))

    def test_empty_never_generates(self) -> None:
        self.assertFalse(m._should_generate_qcm([], skip_qcm=False))
        self.assertFalse(m._should_generate_qcm([], skip_qcm=True))

    def test_returns_plain_bool(self) -> None:
        # Must be a real bool, not a truthy list, so callers/JSON stay clean.
        self.assertIs(m._should_generate_qcm(["aide-A"], skip_qcm=False), True)
        self.assertIs(m._should_generate_qcm([], skip_qcm=False), False)


if __name__ == "__main__":
    unittest.main()
