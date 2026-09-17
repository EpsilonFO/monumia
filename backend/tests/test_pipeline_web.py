"""Tests du fetcheur (scripts/pipeline/web.py).

Aucun test ne touche au réseau : tout passe par `httpx.MockTransport`. Les deux
comportements qui méritent un filet sont ceux qui ont coûté des heures en
production — le 403 d'un WAF qui ne cède qu'à une identité de navigateur, et le
défi JavaScript qui rend 200 sur une page vide.

Run from backend/:  uv run pytest tests/test_pipeline_web.py
"""

import io
import sys
import unittest
import zipfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline.web import Fetcheur, reinitialiser_delais  # noqa: E402

HTML = "<html><body><h1>Aide</h1><p>Taux de 30 %</p></body></html>"


def _docx_minimal(*paragraphes: str) -> bytes:
    """Un .docx authentique : un ZIP portant `word/document.xml`."""
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    corps = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphes)
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "word/document.xml", f"<w:document {ns}><w:body>{corps}</w:body></w:document>"
        )
    return tampon.getvalue()


# Une page de défi telle que la rend le shield AURA : 200, moins d'un kilo,
# et un cookie à calculer.
SHIELD = (
    "<html><script>var challenge = Date.now();"
    "var reponse = (challenge * 3) % 7;"
    'setCookie("sh_token", challenge + ":" + reponse);'
    "location.reload();</script></html>"
)


class TestFetcheur(unittest.TestCase):
    def setUp(self):
        reinitialiser_delais()

    def fetcheur(self, handler, **kw) -> Fetcheur:
        return Fetcheur(transport=httpx.MockTransport(handler), delai_s=0.0, **kw)

    def test_page_html_et_markdown(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})

        with self.fetcheur(handler) as f:
            page = f.get("https://example.org/aide")
            self.assertTrue(page.ok)
            self.assertTrue(page.est_html)
            self.assertFalse(page.est_pdf)
            self.assertIn("Taux de 30 %", page.markdown())

    def test_docx_converti_et_pas_rendu_en_zip_brut(self):
        """Un règlement d'intervention en .docx doit devenir citable.

        Avant, `markdown()` rendait le ZIP décodé en force
        (« PK...[Content_Types].xml ») : mesuré sur hdf-jardins-en-scene le
        2026-09-06, deux annexes .docx illisibles ont mis 8 conditions de la
        référence hors de portée du modèle.
        """
        octets = _docx_minimal("Le taux est de 40 % des dépenses éligibles.")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=octets,
                headers={
                    "content-type": (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                },
            )

        with self.fetcheur(handler) as f:
            page = f.get("https://example.org/reglement.docx")
        self.assertTrue(page.est_docx)
        self.assertFalse(page.est_pdf)
        self.assertIn("Le taux est de 40 % des dépenses éligibles.", page.markdown())
        self.assertNotIn("Content_Types", page.markdown())

    def test_docx_reconnu_sans_content_type(self):
        """Certains serveurs rendent un .docx en application/octet-stream."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=_docx_minimal("Critère de sélection : gratuité."),
                headers={"content-type": "application/octet-stream"},
            )

        with self.fetcheur(handler) as f:
            page = f.get("https://example.org/r")
        self.assertTrue(page.est_docx)
        self.assertIn("gratuité", page.markdown())

    def test_403_bascule_sur_les_entetes_navigateur(self):
        vus: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            ua = request.headers.get("user-agent", "")
            vus.append(ua)
            if "MonumiaIngest" in ua:
                return httpx.Response(403, text="interdit")
            return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})

        with self.fetcheur(handler) as f:
            page = f.get("https://www.normandie.fr/aide")
        self.assertTrue(page.ok)
        self.assertEqual(len(vus), 2)
        self.assertIn("MonumiaIngest", vus[0])
        self.assertIn("Chrome", vus[1])

    def test_403_persistant_reste_une_page_en_erreur(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, text="interdit")

        with self.fetcheur(handler) as f:
            page = f.get("https://example.org/mur")
        self.assertFalse(page.ok)
        self.assertEqual(page.status, 403)

    def test_shield_javascript_rejoue_avec_le_cookie(self):
        appels: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            appels.append(request)
            if request.headers.get("cookie"):
                return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})
            return httpx.Response(200, text=SHIELD, headers={"content-type": "text/html"})

        with self.fetcheur(handler) as f:
            page = f.get("https://www.auvergnerhonealpes.fr/aides/x")
        self.assertIn("Taux de 30 %", page.markdown())
        self.assertEqual(len(appels), 2)
        self.assertIn("sh_token=", appels[1].headers.get("cookie", ""))

    def test_pdf_non_decode_en_texte(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=b"%PDF-1.4 \xff\xfe binaire",
                headers={"content-type": "application/pdf"},
            )

        with self.fetcheur(handler) as f:
            page = f.get("https://example.org/reglement.pdf")
        self.assertTrue(page.est_pdf)
        self.assertEqual(page.texte, "")
        self.assertEqual(page.markdown(), "")
        self.assertTrue(page.contenu.startswith(b"%PDF-"))

    def test_panne_reseau_donne_une_page_en_erreur(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("DNS", request=request)

        with self.fetcheur(handler) as f:
            page = f.get("https://inexistant.example/aide")
        self.assertFalse(page.ok)
        assert page.erreur is not None
        self.assertIn("ConnectError", page.erreur)

    def test_cache_evite_le_second_aller_retour(self):
        appels = []

        def handler(request: httpx.Request) -> httpx.Response:
            appels.append(request.url)
            return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})

        with self.fetcheur(handler) as f:
            f.get("https://example.org/a")
            f.get("https://example.org/a")
        self.assertEqual(len(appels), 1)

    def test_cache_borne_a_sa_taille(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})

        with self.fetcheur(handler, taille_cache=2) as f:
            for i in range(5):
                f.get(f"https://example.org/{i}")
            self.assertEqual(len(f._cache), 2)

    def test_erreur_reseau_non_mise_en_cache(self):
        appels = []

        def handler(request: httpx.Request) -> httpx.Response:
            appels.append(request.url)
            raise httpx.ConnectError("DNS", request=request)

        with self.fetcheur(handler) as f:
            f.get("https://inexistant.example/a")
            f.get("https://inexistant.example/a")
        self.assertEqual(len(appels), 2)

    def test_entetes_inconnus_refuses(self):
        with self.assertRaises(ValueError):
            Fetcheur(entetes="furtif")


if __name__ == "__main__":
    unittest.main()
