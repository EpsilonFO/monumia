"""Confirmation d'email exigée à l'inscription (`enable_confirmations`).

Trois comportements que ce réglage fait apparaître, et qu'aucun code ne devinait
avant lui :

  * `sign_up` ne lève plus sur une adresse déjà inscrite, il rend un
    utilisateur SANS IDENTITÉ (anti-énumération de Supabase). Non reconnu, ce
    cas partait en insertion de profil dupliquée, donc en 500, là où le front
    attend le 409 auquel il accroche « Se connecter » ;
  * l'inscription rendue sans session n'est pas un échec : le compte existe, et
    c'est ce que le front lit pour renvoyer vers la boîte mail ;
  * la connexion d'une adresse non confirmée n'est pas un mot de passe faux.
    Le confondre menait l'utilisateur vers une réinitialisation inutile.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import BackgroundTasks, HTTPException, Response

from routers.auth import (
    DETAIL_DEJA_INSCRIT,
    DETAIL_NON_CONFIRME,
    LoginRequest,
    RegisterCollaboratorRequest,
    RegisterRequest,
    _url_retour_confirmation,
    login,
    register,
)
from routers.auth import register_collaborator as register_collab

BODY = RegisterRequest(
    email="marie@exemple.fr", password="motdepasse1", prenom="Marie", nom="Dupont"
)
BODY_COLLAB = RegisterCollaboratorRequest(
    email="marie@exemple.fr",
    password="motdepasse1",
    prenom="Marie",
    nom="Dupont",
    metier="architecte",
)

PROFIL = {
    "id": "user-1",
    "email": "marie@exemple.fr",
    "prenom": "Marie",
    "nom": "Dupont",
    "onboarding_complete": False,
    "notification_preferences": {},
}


class _Anon:
    """Client anon dont `sign_up` rend ce que rend Supabase, confirmation activée."""

    def __init__(self, *, identities=None, session=None):
        self.auth = MagicMock()
        self.auth.sign_up.return_value = SimpleNamespace(
            user=SimpleNamespace(id="user-1", identities=identities),
            session=session,
        )

    @property
    def options_du_sign_up(self) -> dict:
        return self.auth.sign_up.call_args[0][0]["options"]


def _supabase(profil_existe: bool = False):
    """Service-role factice, une réponse par requête attendue.

    Profil absent : `_profil_existe`, `insert`, `_get_profile`. Profil présent :
    l'insertion est sautée, il n'en reste que deux.
    """
    supabase = MagicMock()
    requete = supabase.table.return_value
    for methode in ("select", "eq", "limit", "insert", "single"):
        getattr(requete, methode).return_value = requete
    reponses = [SimpleNamespace(data=[{"id": "user-1"}] if profil_existe else [])]
    if not profil_existe:
        reponses.append(SimpleNamespace(data=None))
    reponses.append(SimpleNamespace(data=dict(PROFIL)))
    requete.execute.side_effect = reponses
    return supabase


class AdresseDejaPriseTest(unittest.TestCase):
    """`identities: []` = utilisateur factice, donc adresse déjà confirmée."""

    def test_409_sans_toucher_a_la_base(self) -> None:
        supabase = _supabase()
        with self.assertRaises(HTTPException) as ctx:
            register(
                body=BODY,
                response=Response(),
                background_tasks=BackgroundTasks(),
                anon=_Anon(identities=[]),
                supabase=supabase,
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, DETAIL_DEJA_INSCRIT)
        supabase.table.assert_not_called()

    def test_409_aussi_pour_le_collaborateur(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            register_collab(
                body=BODY_COLLAB,
                response=Response(),
                background_tasks=BackgroundTasks(),
                anon=_Anon(identities=[]),
                supabase=_supabase(),
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_identities_absent_n_est_pas_un_utilisateur_factice(self) -> None:
        """Se tromper de sens écraserait le profil d'un compte existant."""
        resultat = register(
            body=BODY,
            response=Response(),
            background_tasks=BackgroundTasks(),
            anon=_Anon(identities=None),
            supabase=_supabase(),
        )
        self.assertEqual(resultat["user"]["email"], "marie@exemple.fr")


class InscriptionSansSessionTest(unittest.TestCase):
    def test_le_compte_est_cree_et_le_jeton_est_nul(self) -> None:
        resultat = register(
            body=BODY,
            response=Response(),
            background_tasks=BackgroundTasks(),
            anon=_Anon(identities=[{"provider": "email"}], session=None),
            supabase=_supabase(),
        )
        self.assertIsNone(resultat["access_token"])
        self.assertEqual(resultat["user"]["prenom"], "Marie")

    def test_aucun_cookie_de_refresh_sans_session(self) -> None:
        response = Response()
        register(
            body=BODY,
            response=response,
            background_tasks=BackgroundTasks(),
            anon=_Anon(identities=[{"provider": "email"}], session=None),
            supabase=_supabase(),
        )
        self.assertNotIn("monumia_refresh", response.headers.get("set-cookie", ""))


class ReinscriptionNonConfirmeeTest(unittest.TestCase):
    """Adresse inscrite mais jamais confirmée : Supabase relance l'email."""

    def test_le_profil_existant_n_est_pas_reinsere(self) -> None:
        supabase = _supabase(profil_existe=True)
        resultat = register(
            body=BODY,
            response=Response(),
            background_tasks=BackgroundTasks(),
            anon=_Anon(identities=[{"provider": "email"}], session=None),
            supabase=supabase,
        )
        self.assertIsNone(resultat["access_token"])
        supabase.table.return_value.insert.assert_not_called()


class ConnexionNonConfirmeeTest(unittest.TestCase):
    def test_403_et_message_dedie(self) -> None:
        anon = MagicMock()
        anon.auth.sign_in_with_password.side_effect = Exception("Email not confirmed")
        with self.assertRaises(HTTPException) as ctx:
            login(
                body=LoginRequest(email="marie@exemple.fr", password="motdepasse1"),
                response=Response(),
                anon=anon,
                supabase=MagicMock(),
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, DETAIL_NON_CONFIRME)

    def test_un_mauvais_mot_de_passe_reste_un_401(self) -> None:
        anon = MagicMock()
        anon.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")
        with self.assertRaises(HTTPException) as ctx:
            login(
                body=LoginRequest(email="marie@exemple.fr", password="faux"),
                response=Response(),
                anon=anon,
                supabase=MagicMock(),
            )
        self.assertEqual(ctx.exception.status_code, 401)


class UrlDeRetourTest(unittest.TestCase):
    """Le client ne choisit jamais l'URL, seulement l'intention."""

    def test_defaut(self) -> None:
        self.assertTrue(_url_retour_confirmation().endswith("/auth/callback"))

    def test_reprise_du_brouillon(self) -> None:
        self.assertTrue(
            _url_retour_confirmation(reprise=True).endswith("/auth/callback?reprise=brouillon")
        )

    def test_invitation_encodee(self) -> None:
        url = _url_retour_confirmation(invitation="a/b?c=1")
        self.assertTrue(url.endswith("/auth/callback?invitation=a%2Fb%3Fc%3D1"))

    def test_l_invitation_prime_sur_la_reprise(self) -> None:
        url = _url_retour_confirmation(reprise=True, invitation="jeton")
        self.assertTrue(url.endswith("/auth/callback?invitation=jeton"))

    def test_transmise_au_sign_up(self) -> None:
        anon = _Anon(identities=[{"provider": "email"}], session=None)
        register(
            body=BODY.model_copy(update={"reprise": True}),
            response=Response(),
            background_tasks=BackgroundTasks(),
            anon=anon,
            supabase=_supabase(),
        )
        self.assertIn("reprise=brouillon", anon.options_du_sign_up["email_redirect_to"])

    def test_transmise_au_sign_up_du_collaborateur(self) -> None:
        anon = _Anon(identities=[{"provider": "email"}], session=None)
        register_collab(
            body=BODY_COLLAB.model_copy(update={"invitation": "jeton-42"}),
            response=Response(),
            background_tasks=BackgroundTasks(),
            anon=anon,
            supabase=_supabase(),
        )
        self.assertIn("invitation=jeton-42", anon.options_du_sign_up["email_redirect_to"])


if __name__ == "__main__":
    unittest.main()
