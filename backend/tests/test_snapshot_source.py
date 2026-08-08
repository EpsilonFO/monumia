"""Tests des briques de snapshot (scripts/snapshot_source.py).

L'enjeu principal est l'ANTI-ÉCRASEMENT : avant, deux snapshots pris le même
jour sous le même label s'écrasaient en silence, et le second effaçait la preuve
du premier — alors que c'est leur différence qui documente un changement de
règlement.

Run from backend/:  uv run pytest tests/test_snapshot_source.py
"""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import snapshot_source  # noqa: E402
import yaml  # noqa: E402
from snapshot_source import to_markdown, write_md_snapshot, write_pdf_snapshot  # noqa: E402


class SnapshotTestCase(unittest.TestCase):
    """Redirige data/sources vers un dossier jetable."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.sources = Path(self._tmp.name)
        patcher = patch.object(snapshot_source, "SOURCES_DIR", self.sources)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)


class TestToMarkdown(SnapshotTestCase):
    def test_conversion_sans_rewrap(self):
        # `body_width = 0` : une quote longue doit rester sur une ligne, sinon
        # elle devient incherchable dans le snapshot.
        longue = "Les travaux doivent concerner le gros œuvre, " * 6
        md = to_markdown(f"<html><body><p>{longue}</p></body></html>")
        self.assertIn(longue.strip(), md)

    def test_liens_conserves_images_ignorees(self):
        md = to_markdown('<p><a href="https://ex.fr/r.pdf">Règlement</a></p><img src="l.png">')
        self.assertIn("[Règlement](https://ex.fr/r.pdf)", md)
        self.assertNotIn("l.png", md)


class TestWriteMdSnapshot(SnapshotTestCase):
    HTML = "<html><body><p>Les édifices antérieurs à 1800.</p></body></html>"

    def test_en_tete_et_corps(self):
        path = write_md_snapshot("mon-aide", "https://ex.fr/aide", self.HTML, label="reglement")
        contenu = path.read_text(encoding="utf-8")
        self.assertTrue(path.name.endswith("-reglement.md"))
        self.assertIn("url: https://ex.fr/aide", contenu)
        self.assertIn("Les édifices antérieurs à 1800.", contenu)

    def test_sha_porte_sur_le_brut_pas_sur_le_markdown(self):
        # C'est ce qui permet à la veille de comparer une page fraîche à sa
        # baseline sans la reconvertir.
        path = write_md_snapshot("mon-aide", "https://ex.fr/aide", self.HTML)
        self.assertIn(f"sha256: {hashlib.sha256(self.HTML.encode()).hexdigest()}", path.read_text())

    def test_body_is_markdown_ne_convertit_pas(self):
        texte = "# Règlement\n\n  * point un\n  * point deux\n"
        path = write_md_snapshot("mon-aide", "file:///r.md", texte, body_is_markdown=True)
        self.assertTrue(path.read_text(encoding="utf-8").endswith(texte))

    def test_contenu_identique_le_meme_jour_reutilise_le_fichier(self):
        first = write_md_snapshot("mon-aide", "https://ex.fr/aide", self.HTML, label="page")
        avant = first.stat().st_mtime_ns
        second = write_md_snapshot("mon-aide", "https://ex.fr/aide", self.HTML, label="page")
        self.assertEqual(first, second)
        # Non réécrit : un `git diff` vide quand rien n'a bougé est la condition
        # pour que la revue humaine du diff reste lisible.
        self.assertEqual(avant, second.stat().st_mtime_ns)
        self.assertEqual(len(list(self.sources.glob("mon-aide/*.md"))), 1)

    def test_contenu_different_le_meme_jour_cree_une_variante(self):
        first = write_md_snapshot("mon-aide", "https://ex.fr/a", self.HTML, label="page")
        autre = "<html><body><p>Les édifices antérieurs à 1850.</p></body></html>"
        second = write_md_snapshot("mon-aide", "https://ex.fr/b", autre, label="page")
        self.assertNotEqual(first, second)
        self.assertTrue(second.stem.endswith("-page-b"))
        # La preuve du premier snapshot survit.
        self.assertIn("1800", first.read_text(encoding="utf-8"))
        self.assertIn("1850", second.read_text(encoding="utf-8"))

    def test_troisieme_variante(self):
        for n, annee in enumerate(("1800", "1850", "1900")):
            path = write_md_snapshot("mon-aide", "https://ex.fr/a", f"<p>{annee}</p>")
            if n == 2:
                self.assertTrue(path.stem.endswith("-c"))
        self.assertEqual(len(list(self.sources.glob("mon-aide/*.md"))), 3)

    def test_variante_deja_ecrite_est_reutilisee(self):
        a = write_md_snapshot("mon-aide", "https://ex.fr/a", "<p>1800</p>")
        b = write_md_snapshot("mon-aide", "https://ex.fr/a", "<p>1850</p>")
        # Re-snapshoter le contenu de la variante doit retrouver la variante,
        # pas en empiler une nouvelle.
        self.assertEqual(write_md_snapshot("mon-aide", "https://ex.fr/a", "<p>1850</p>"), b)
        self.assertEqual(write_md_snapshot("mon-aide", "https://ex.fr/a", "<p>1800</p>"), a)
        self.assertEqual(len(list(self.sources.glob("mon-aide/*.md"))), 2)


class TestWritePdfSnapshot(SnapshotTestCase):
    PDF = b"%PDF-1.4\nfaux contenu de reglement\n%%EOF"

    def test_octets_et_sidecar_de_provenance(self):
        path = write_pdf_snapshot(
            "mon-aide", self.PDF, url="https://ex.fr/r.pdf", label="reglement"
        )
        self.assertEqual(path.read_bytes(), self.PDF)
        sidecar = path.with_name(path.name + ".meta.yaml")
        meta = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
        self.assertEqual(meta["url"], "https://ex.fr/r.pdf")
        self.assertEqual(meta["sha256"], hashlib.sha256(self.PDF).hexdigest())
        self.assertIn("fetched_at", meta)

    def test_sidecar_sans_url_pour_un_fichier_local(self):
        path = write_pdf_snapshot("mon-aide", self.PDF)
        meta = yaml.safe_load(path.with_name(path.name + ".meta.yaml").read_text())
        self.assertNotIn("url", meta)
        self.assertEqual(meta["sha256"], hashlib.sha256(self.PDF).hexdigest())

    def test_sidecar_jamais_reecrit(self):
        # Il porte la date de la VRAIE première récupération.
        path = write_pdf_snapshot("mon-aide", self.PDF, url="https://ex.fr/r.pdf")
        sidecar = path.with_name(path.name + ".meta.yaml")
        origine = sidecar.read_text(encoding="utf-8")
        write_pdf_snapshot("mon-aide", self.PDF, url="https://ex.fr/autre.pdf")
        self.assertEqual(sidecar.read_text(encoding="utf-8"), origine)

    def test_pdf_identique_reutilise_le_fichier(self):
        first = write_pdf_snapshot("mon-aide", self.PDF, label="reglement")
        second = write_pdf_snapshot("mon-aide", self.PDF, label="reglement")
        self.assertEqual(first, second)
        self.assertEqual(len(list(self.sources.glob("mon-aide/*.pdf"))), 1)

    def test_pdf_different_cree_une_variante(self):
        first = write_pdf_snapshot("mon-aide", self.PDF, label="reglement")
        second = write_pdf_snapshot("mon-aide", self.PDF + b"v2", label="reglement")
        self.assertNotEqual(first, second)
        self.assertTrue(second.stem.endswith("-reglement-b"))
        self.assertEqual(first.read_bytes(), self.PDF)

    def test_sidecar_ignore_par_le_chargeur_de_baselines(self):
        # Le sidecar ne doit pas être pris pour un document à fouiller : son
        # suffixe est `.yaml`, et `load_baselines` ne lit que .md et .pdf.
        path = write_pdf_snapshot("mon-aide", self.PDF)
        self.assertEqual(path.with_name(path.name + ".meta.yaml").suffix, ".yaml")


class TestValidationDesNoms(SnapshotTestCase):
    def test_slug_invalide(self):
        for mauvais in ("../evasion", "Mon-Aide", "aide_underscore", ""):
            with self.assertRaises(SystemExit):
                write_md_snapshot(mauvais, "https://ex.fr", "<p>x</p>")

    def test_label_invalide(self):
        # Un label compose lui aussi le nom de fichier : sans validation,
        # « ../../secrets » ferait écrire hors du dossier des sources.
        with self.assertRaises(SystemExit):
            write_md_snapshot("mon-aide", "https://ex.fr", "<p>x</p>", label="../evasion")

    def test_validation_avant_le_telechargement(self):
        # Un slug fautif ne doit pas coûter un aller-retour réseau, ni sortir
        # sur une erreur httpx qui masque la cause. `snapshot()` valide donc
        # avant de toucher au réseau — vérifié en pointant sur un hôte qui
        # ferait échouer toute requête.
        with self.assertRaises(SystemExit) as ctx:
            snapshot_source.snapshot("MAUVAIS_SLUG", "https://hote.invalide./x")
        self.assertIn("slug invalide", str(ctx.exception))

    def test_labels_du_depot_acceptes(self):
        for bon in ("reglement", "page-2026", "reglement-objets-2016", "wayback-20240328"):
            self.assertTrue(write_md_snapshot("mon-aide", "https://ex.fr", "<p>x</p>", label=bon))


if __name__ == "__main__":
    unittest.main()
