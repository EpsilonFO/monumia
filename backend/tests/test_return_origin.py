"""Tests de l'origine de retour après paiement.

Stripe redirige le navigateur vers l'URL qu'on lui donne. La déduire de la
requête évite de configurer une variable par machine (et d'atterrir en
production depuis un poste de développement), mais l'en-tête vient du client :
la liste blanche est la seule chose qui empêche une redirection arbitraire.
"""

import unittest

from starlette.datastructures import Headers
from starlette.requests import Request

from config import resolve_app_origin
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


if __name__ == "__main__":
    unittest.main()
