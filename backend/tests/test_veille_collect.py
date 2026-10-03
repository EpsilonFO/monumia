"""Tests de l'étage A hors réseau (scripts/veille_collect.py).

Ce qui est vérifié : le rapprochement d'une URL et de sa baseline, l'héritage
de baseline après redirection, et le texte des PDF frais. Aucun test ne
télécharge quoi que ce soit.

Run from backend/:  uv run pytest tests/test_veille_collect.py
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import veille_collect  # noqa: E402
from veille_collect import (  # noqa: E402
    AideCollect,
    FetchResult,
    MonitoredUrl,
    cle_url,
    monitored_urls,
    pdf_bytes_to_text,
    relier_redirections,
)

from aides_schema import Aide  # noqa: E402


def make_aide(**source) -> Aide:
    return Aide.model_validate(
        {
            "slug": "aide-test",
            "nom": "Aide test",
            "organisme": "Organisme test",
            "categorie": "region",
            "type": "subvention",
            "description": "Une aide de test.",
            "source": source,
        }
    )


class TestCleUrl(unittest.TestCase):
    def test_variantes_d_ecriture_convergent(self):
        for variante in (
            "https://www.ex.fr/aide/",
            "http://ex.fr/aide",
            "https://EX.fr/aide#conditions",
            "https://ex.fr/aide/?utm_source=lettre&utm_campaign=x",
        ):
            self.assertEqual(cle_url(variante), "ex.fr/aide", variante)

    def test_parametres_de_ressource_conserves(self):
        # `?id=12` désigne une autre page : ce n'est pas du suivi.
        self.assertEqual(cle_url("https://ex.fr/aide?id=12&b=1"), "ex.fr/aide?b=1&id=12")
        self.assertNotEqual(
            cle_url("https://ex.fr/aide?id=12"), cle_url("https://ex.fr/aide?id=13")
        )

    def test_racine(self):
        self.assertEqual(cle_url("https://ex.fr/"), "ex.fr/")


class TestMonitoredUrls(unittest.TestCase):
    """La page officielle retrouve sa baseline malgré `www.`, le slash final et le protocole."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        racine = Path(tmp.name)
        (racine / "aide-test").mkdir()
        (racine / "aide-test" / "2026-07-01.md").write_text(
            "---\nurl: https://www.ex.fr/aide/\nfetched_at: x\nsha256: abc\n---\n\ncorps\n",
            encoding="utf-8",
        )
        patcher = mock.patch.object(veille_collect, "SOURCES_DIR", racine)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_officielle_herite_de_la_baseline_a_cle_egale(self):
        urls = monitored_urls(make_aide(url_officielle="http://ex.fr/aide"))
        self.assertEqual([u.role for u in urls], ["officielle"])
        self.assertEqual(urls[0].baseline_sha, "abc")
        self.assertEqual(urls[0].baseline_body, "\ncorps\n")

    def test_formulaire_identique_a_une_page_surveillee_non_doublonne(self):
        aide = make_aide(
            url_officielle="http://ex.fr/aide", formulaire_url="https://www.ex.fr/aide"
        )
        self.assertEqual([u.role for u in monitored_urls(aide)], ["officielle"])

    def test_url_reellement_differente_reste_surveillee_a_part(self):
        urls = monitored_urls(make_aide(url_officielle="https://ex.fr/autre-page"))
        self.assertEqual([u.role for u in urls], ["officielle", "snapshot"])
        self.assertFalse(urls[0].has_baseline)


class TestRedirections(unittest.TestCase):
    OFF = "https://ancien.fr/aide"
    CIBLE = "https://nouveau.fr/fiche-aide"

    def _col(self, url_finale: str | None) -> AideCollect:
        off = MonitoredUrl(url=self.OFF, role="officielle")
        cible = MonitoredUrl(
            url=self.CIBLE,
            role="snapshot",
            label="fiche",
            baseline_path=Path("2026-07-01-fiche.md"),
            baseline_sha="sha",
            baseline_body="corps",
        )
        return AideCollect(
            slug="aide-test",
            urls=[off, cible],
            fetched={
                self.OFF: FetchResult(url=self.OFF, status=200, url_finale=url_finale, body_md="x"),
                self.CIBLE: FetchResult(url=self.CIBLE, status=200, url_finale=self.CIBLE),
            },
        )

    def test_officielle_redirigee_herite_de_la_baseline_et_la_cible_disparait(self):
        col = self._col(url_finale=self.CIBLE + "/")
        relier_redirections(col)
        self.assertEqual([u.url for u in col.urls], [self.OFF])
        off = col.page_principale
        assert off is not None
        self.assertEqual(off.baseline_sha, "sha")
        self.assertEqual(off.label, "fiche")

    def test_sans_redirection_rien_ne_bouge(self):
        col = self._col(url_finale=self.OFF)
        relier_redirections(col)
        self.assertEqual([u.url for u in col.urls], [self.OFF, self.CIBLE])

    def test_redirection_vers_une_page_inconnue_ne_fait_rien(self):
        col = self._col(url_finale="https://ailleurs.fr/")
        relier_redirections(col)
        self.assertEqual([u.url for u in col.urls], [self.OFF, self.CIBLE])


class TestTextePdf(unittest.TestCase):
    def test_cache_disque_evite_la_seconde_extraction(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        appels: list[bytes] = []

        def faux_pdftotext(content: bytes) -> str | None:
            appels.append(content)
            return "texte extrait"

        with (
            mock.patch.object(veille_collect, "PDFTEXT_CACHE_DIR", Path(tmp.name)),
            mock.patch.object(veille_collect, "_pdftotext", faux_pdftotext),
        ):
            self.assertEqual(pdf_bytes_to_text(b"%PDF-1"), "texte extrait")
            self.assertEqual(pdf_bytes_to_text(b"%PDF-1"), "texte extrait")
            self.assertEqual(len(appels), 1)
            self.assertEqual(len(list(Path(tmp.name).glob("*.txt"))), 1)

    def test_un_echec_n_est_jamais_mis_en_cache(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with (
            mock.patch.object(veille_collect, "PDFTEXT_CACHE_DIR", Path(tmp.name)),
            mock.patch.object(veille_collect, "_pdftotext", lambda c: None),
        ):
            self.assertIsNone(pdf_bytes_to_text(b"%PDF-1"))
            self.assertEqual(list(Path(tmp.name).glob("*.txt")), [])

    def test_texte_d_un_fetch_result(self):
        court = FetchResult(url="u", status=200, is_binary=True, texte_pdf="trop court")
        self.assertIsNone(court.texte)
        long = FetchResult(url="u", status=200, is_binary=True, texte_pdf="x" * 2000)
        self.assertEqual(long.kind, "pdf")
        self.assertEqual(long.texte, "x" * 2000)
        page = FetchResult(url="u", status=200, body_md="page")
        self.assertEqual((page.kind, page.texte), ("text", "page"))
