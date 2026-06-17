"""Tests du rendu pur de l'email d'invitation."""

import unittest

from services.email_service import render_invitation_email


class RenderInvitationEmailTests(unittest.TestCase):
    def _html(self) -> str:
        return render_invitation_email(
            inviter_nom="Marie Dupont",
            monument_nom="Église Saint-Pierre",
            invite_url="https://app.monumia.fr/invitation/abc",
            expires_label="29 juin 2026",
        )

    def test_contains_inviter_and_project(self) -> None:
        html = self._html()
        self.assertIn("Marie Dupont", html)
        self.assertIn("Église Saint-Pierre", html)

    def test_contains_cta_link(self) -> None:
        self.assertIn("https://app.monumia.fr/invitation/abc", self._html())

    def test_contains_expiry(self) -> None:
        self.assertIn("29 juin 2026", self._html())

    def test_uses_brand_colors(self) -> None:
        html = self._html()
        self.assertIn("#0a369d", html)  # bleu institutionnel
        self.assertIn("#f17105", html)  # orange CTA


if __name__ == "__main__":
    unittest.main()
