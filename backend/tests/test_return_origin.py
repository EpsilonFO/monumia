"""Tests des URLs que le backend fabrique à destination d'un navigateur :
retours de paiement Stripe et liens d'invitation envoyés par email.

Les déduire de la requête évite de configurer une variable par machine (et
d'envoyer en production un utilisateur parti de la beta), mais l'en-tête vient
du client : la liste blanche est la seule chose qui empêche une redirection
arbitraire.
"""

import unittest

from starlette.datastructures import Headers
from starlette.requests import Request

from config import default_app_url, request_app_origin, resolve_app_origin
from services import stripe_billing as billing

FALLBACK = "https://app.monumia.fr"


def _request(headers: dict) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/billing/checkout",
        "headers": Headers(headers).raw,
    }
    return Request(scope)


class ResolveAppOriginTest(unittest.TestCase):
    def test_origine_connue_acceptee(self):
        for origin in (
            "http://localhost:3000",
            "http://localhost:3001",
            "https://app.monumia.fr",
            "https://beta.monumia.fr",
            "https://monumia.fr",
        ):
            self.assertEqual(resolve_app_origin(origin, FALLBACK), origin)

    def test_slash_final_tolere(self):
        self.assertEqual(
            resolve_app_origin("http://localhost:3000/", FALLBACK), "http://localhost:3000"
        )

    def test_origine_absente_retombe_sur_la_configuration(self):
        self.assertEqual(resolve_app_origin(None, FALLBACK), FALLBACK)
        self.assertEqual(resolve_app_origin("", FALLBACK), FALLBACK)

    def test_origine_inconnue_refusee(self):
        """Le cœur du test : aucune redirection hors liste blanche."""
        for hostile in (
            "https://monumia.fr.attaquant.example",
            "http://attaquant.example",
            "https://app.monumia.fr.evil.co",
            "javascript:alert(1)",
            "//attaquant.example",
            "http://localhost:9999",
        ):
            self.assertEqual(resolve_app_origin(hostile, FALLBACK), FALLBACK, hostile)


class ReturnOriginTest(unittest.TestCase):
    def test_entete_origin_utilise(self):
        request = _request({"origin": "http://localhost:3000"})
        self.assertEqual(billing.return_origin(request), "http://localhost:3000")

    def test_repli_sur_le_referer(self):
        """Certains navigateurs n'envoient pas Origin sur une requête same-site."""
        request = _request({"referer": "http://localhost:3000/tarifs?projet=abc"})
        self.assertEqual(billing.return_origin(request), "http://localhost:3000")

    def test_origin_prime_sur_referer(self):
        request = _request(
            {"origin": "http://localhost:3000", "referer": "https://beta.monumia.fr/tarifs"}
        )
        self.assertEqual(billing.return_origin(request), "http://localhost:3000")

    def test_sans_entete_retombe_sur_app_url(self):
        request = _request({})
        self.assertEqual(billing.return_origin(request), billing.app_url())

    def test_referer_hostile_ignore(self):
        request = _request({"referer": "https://attaquant.example/tarifs"})
        self.assertEqual(billing.return_origin(request), billing.app_url())


class InvitationOriginTest(unittest.TestCase):
    """Le lien d'invitation doit suivre l'environnement de l'invitant.

    Régression vécue : l'URL était codée en dur sur `app.monumia.fr`, donc une
    invitation créée depuis la beta envoyait le destinataire en production, où
    le jeton n'existe pas — « Invitation introuvable ».
    """

    def _invite_url(self, headers: dict) -> str:
        request = _request(headers)
        return f"{request_app_origin(request)}/invitation/tok123"

    def test_invitation_depuis_la_beta_reste_sur_la_beta(self):
        self.assertEqual(
            self._invite_url({"origin": "https://beta.monumia.fr"}),
            "https://beta.monumia.fr/invitation/tok123",
        )

    def test_invitation_depuis_la_prod_reste_en_prod(self):
        self.assertEqual(
            self._invite_url({"origin": "https://app.monumia.fr"}),
            "https://app.monumia.fr/invitation/tok123",
        )

    def test_invitation_depuis_localhost(self):
        self.assertEqual(
            self._invite_url({"origin": "http://localhost:3000"}),
            "http://localhost:3000/invitation/tok123",
        )

    def test_origine_hostile_retombe_sur_la_configuration(self):
        self.assertEqual(
            self._invite_url({"origin": "https://attaquant.example"}),
            f"{default_app_url()}/invitation/tok123",
        )

    def test_sans_entete_retombe_sur_la_configuration(self):
        self.assertEqual(self._invite_url({}), f"{default_app_url()}/invitation/tok123")


if __name__ == "__main__":
    unittest.main()
