"""Tests de l'email d'invitation : rendu, expéditeur et voie de sortie."""

import os
import unittest
from unittest.mock import MagicMock, patch

from services.email_service import (
    expediteur_invitation,
    render_invitation_email,
    render_invitation_text,
    send_invitation_email,
)


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

    def test_invitation_projet_ne_promet_pas_les_aides(self) -> None:
        # Un invité entre en `member`, qui n'a pas l'onglet Aides du projet.
        html = render_invitation_email(
            inviter_nom="Marie Dupont",
            monument_nom="Église Saint-Pierre",
            invite_url="https://app.monumia.fr/invitation/abc",
            expires_label="29 juin 2026",
            projet_titre="Reprise de la couverture",
        )
        self.assertIn("Reprise de la couverture", html)
        self.assertIn("ses dossiers et ses documents", html)
        self.assertNotIn("aides", html)

    def test_uses_brand_colors(self) -> None:
        html = self._html()
        self.assertIn("#0a369d", html)  # bleu institutionnel
        self.assertIn("#f17105", html)  # orange CTA

    def test_les_valeurs_saisies_sont_echappees(self) -> None:
        # Nom et titre viennent d'utilisateurs : pas de HTML injecté dans l'email.
        html = render_invitation_email(
            inviter_nom="<b>Marie</b>",
            monument_nom="Église <script>",
            invite_url="https://app.monumia.fr/invitation/abc",
            expires_label="29 juin 2026",
        )
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;b&gt;Marie&lt;/b&gt;", html)

    def test_version_texte_porte_le_lien(self) -> None:
        texte = render_invitation_text(
            inviter_nom="Marie Dupont",
            monument_nom="Église Saint-Pierre",
            invite_url="https://app.monumia.fr/invitation/abc",
            expires_label="29 juin 2026",
            projet_titre="Reprise de la couverture",
        )
        self.assertIn("https://app.monumia.fr/invitation/abc", texte)
        self.assertIn("« Reprise de la couverture »", texte)
        self.assertNotIn("<", texte)


class ExpediteurInvitationTests(unittest.TestCase):
    def test_nom_de_celui_qui_invite_sur_l_adresse_du_domaine(self) -> None:
        with patch.dict(os.environ, {"RESEND_FROM": "Monumia <invitations@monumia.fr>"}):
            self.assertEqual(
                expediteur_invitation("Marie Dupont"),
                '"Marie Dupont via Monumia" <invitations@monumia.fr>',
            )

    def test_nom_inconnu_garde_l_expediteur_de_marque(self) -> None:
        with patch.dict(os.environ, {"RESEND_FROM": "Monumia <invitations@monumia.fr>"}):
            self.assertEqual(expediteur_invitation("Un membre"), "Monumia <invitations@monumia.fr>")

    def test_caracteres_d_en_tete_retires(self) -> None:
        with patch.dict(os.environ, {"RESEND_FROM": ""}):
            self.assertEqual(
                expediteur_invitation('Marie "<x>" Dupont'),
                '"Marie x Dupont via Monumia" <invitations@monumia.fr>',
            )


class SendInvitationTests(unittest.TestCase):
    ARGS = {
        "to_email": "invite@exemple.fr",
        "inviter_nom": "Marie Dupont",
        "monument_nom": "Église Saint-Pierre",
        "invite_url": "https://app.monumia.fr/invitation/abc",
        "expires_label": "29 juin 2026",
        "inviter_email": "marie@exemple.fr",
    }

    def test_resend_recoit_texte_html_et_reponse_a_l_invitant(self) -> None:
        with (
            patch.dict(os.environ, {"RESEND_API_KEY": "re_x", "RESEND_FROM": ""}),
            patch("resend.Emails.send") as envoi,
        ):
            send_invitation_email(**self.ARGS)
        (message,) = envoi.call_args.args
        self.assertEqual(message["from"], '"Marie Dupont via Monumia" <invitations@monumia.fr>')
        self.assertEqual(message["reply_to"], "marie@exemple.fr")
        self.assertIn("https://app.monumia.fr/invitation/abc", message["text"])
        self.assertIn("https://app.monumia.fr/invitation/abc", message["html"])

    def test_sans_resend_part_au_mailpit_local(self) -> None:
        smtp = MagicMock()
        with (
            patch.dict(os.environ, {"RESEND_API_KEY": "", "SMTP_DEV": "localhost:54325"}),
            patch("smtplib.SMTP", return_value=smtp) as connexion,
        ):
            send_invitation_email(**self.ARGS)
        connexion.assert_called_once_with("localhost", 54325, timeout=5)
        (message,) = smtp.__enter__.return_value.send_message.call_args.args
        self.assertEqual(message["To"], "invite@exemple.fr")
        self.assertEqual(message["Reply-To"], "marie@exemple.fr")
        self.assertTrue(message.is_multipart())

    def test_mailpit_injoignable_repli_console(self) -> None:
        with (
            patch.dict(os.environ, {"RESEND_API_KEY": "", "SMTP_DEV": "localhost:1"}),
            patch("smtplib.SMTP", side_effect=ConnectionRefusedError),
            self.assertLogs("services.email_service", level="WARNING") as journal,
        ):
            send_invitation_email(**self.ARGS)
        self.assertTrue(any("invitation/abc" in ligne for ligne in journal.output))


if __name__ == "__main__":
    unittest.main()
