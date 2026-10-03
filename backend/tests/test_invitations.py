"""Tests des fonctions pures du cycle de vie d'une invitation."""

import unittest
from datetime import UTC, datetime, timedelta

from services.invitations import (
    INVITATION_TTL_DAYS,
    generate_invite_token,
    invitation_destinee_a,
    invitation_expiry_iso,
    is_invitation_acceptable,
)


class TokenTests(unittest.TestCase):
    def test_token_is_long_and_urlsafe(self) -> None:
        token = generate_invite_token()
        self.assertGreaterEqual(len(token), 32)
        self.assertTrue(all(c.isalnum() or c in "-_" for c in token))

    def test_tokens_are_unique(self) -> None:
        self.assertNotEqual(generate_invite_token(), generate_invite_token())


class ExpiryTests(unittest.TestCase):
    def test_expiry_is_ttl_days_after_now(self) -> None:
        now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
        expiry = invitation_expiry_iso(now)
        self.assertEqual(expiry, (now + timedelta(days=INVITATION_TTL_DAYS)).isoformat())


class AcceptableTests(unittest.TestCase):
    def _future(self) -> str:
        return (datetime.now(UTC) + timedelta(days=1)).isoformat()

    def _past(self) -> str:
        return (datetime.now(UTC) - timedelta(days=1)).isoformat()

    def test_pending_and_not_expired_is_acceptable(self) -> None:
        self.assertTrue(is_invitation_acceptable("pending", self._future()))

    def test_expired_timestamp_rejected(self) -> None:
        self.assertFalse(is_invitation_acceptable("pending", self._past()))

    def test_non_pending_status_rejected(self) -> None:
        self.assertFalse(is_invitation_acceptable("accepted", self._future()))
        self.assertFalse(is_invitation_acceptable("revoked", self._future()))


class DestinataireTests(unittest.TestCase):
    def test_meme_adresse_a_la_casse_pres(self) -> None:
        self.assertTrue(invitation_destinee_a("marie@exemple.fr", " Marie@Exemple.FR "))

    def test_autre_adresse_refusee(self) -> None:
        self.assertFalse(invitation_destinee_a("marie@exemple.fr", "paul@exemple.fr"))

    def test_adresse_absente_refusee(self) -> None:
        self.assertFalse(invitation_destinee_a("marie@exemple.fr", None))
        self.assertFalse(invitation_destinee_a("", ""))
        self.assertFalse(invitation_destinee_a(None, None))


if __name__ == "__main__":
    unittest.main()
