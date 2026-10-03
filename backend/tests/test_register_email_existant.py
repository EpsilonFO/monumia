"""Adresse déjà inscrite : 409 en français, et non un 400 anglais.

Le message d'origine vient de la bibliothèque Supabase (« User already
registered ») et n'a jamais de raison d'atteindre un utilisateur. Le statut
compte autant que le texte : le front distingue le 409 (proposer la connexion,
en conservant le brouillon du parcours découverte) du 400 (une vraie erreur de
saisie).
"""

import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException, Response

from routers.auth import RegisterCollaboratorRequest, RegisterRequest, register
from routers.auth import register_collaborator as register_collab


class _AnonQuiRefuse:
    """Client anon dont `sign_up` lève, comme le fait la bibliothèque."""

    def __init__(self, message: str) -> None:
        self.auth = MagicMock()
        self.auth.sign_up.side_effect = Exception(message)


BODY = RegisterRequest(
    email="deja@example.com",
    password="motdepasse1",
    prenom="Marie",
    nom="Dupont",
)

BODY_COLLAB = RegisterCollaboratorRequest(
    email="deja@example.com",
    password="motdepasse1",
    prenom="Marie",
    nom="Dupont",
    metier="architecte",
)


class EmailDejaInscritTest(unittest.TestCase):
    def test_409_et_message_francais(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            register(
                body=BODY,
                response=Response(),
                anon=_AnonQuiRefuse("User already registered"),
                supabase=MagicMock(),
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, "Un compte existe déjà avec cette adresse.")

    def test_variante_de_message_reconnue(self) -> None:
        """Le libellé de la bibliothèque n'est pas un contrat : on cherche « already »."""
        with self.assertRaises(HTTPException) as ctx:
            register(
                body=BODY,
                response=Response(),
                anon=_AnonQuiRefuse("this email has already been registered"),
                supabase=MagicMock(),
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_inscription_collaborateur_aussi(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            register_collab(
                body=BODY_COLLAB,
                response=Response(),
                anon=_AnonQuiRefuse("User already registered"),
                supabase=MagicMock(),
            )
        self.assertEqual(ctx.exception.status_code, 409)


class AutresEchecsTest(unittest.TestCase):
    def test_reste_un_400_avec_son_message(self) -> None:
        """Tout ce qui n'est pas un doublon garde le comportement d'avant."""
        with self.assertRaises(HTTPException) as ctx:
            register(
                body=BODY,
                response=Response(),
                anon=_AnonQuiRefuse("Signups not allowed for this instance"),
                supabase=MagicMock(),
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Signups not allowed", str(ctx.exception.detail))

    def test_mot_de_passe_refuse_avant_tout_appel(self) -> None:
        """La politique de mot de passe passe toujours en premier."""
        anon = _AnonQuiRefuse("User already registered")
        faible = RegisterRequest(
            email="neuf@example.com", password="court", prenom="Marie", nom="Dupont"
        )
        with self.assertRaises(HTTPException) as ctx:
            register(body=faible, response=Response(), anon=anon, supabase=MagicMock())
        self.assertEqual(ctx.exception.status_code, 400)
        anon.auth.sign_up.assert_not_called()


if __name__ == "__main__":
    unittest.main()
