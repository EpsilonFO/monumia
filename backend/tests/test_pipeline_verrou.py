"""Tests du verrou d'écriture partagée (scripts/pipeline/verrou.py).

Le test qui compte est celui de concurrence : c'est exactement l'incident du
2026-09-04 (deux ingestions parallèles, `facts_pending.yaml` écrasé, quatre
faits perdus) rejoué en 400 ajouts. S'il repasse au vert avec un `flock`
retiré, c'est que le test ne prouve rien.

Run from backend/:  uv run pytest tests/test_pipeline_verrou.py
"""

import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline.verrou import (  # noqa: E402
    VerrouIndisponible,
    ajouter_sous_verrou,
    ecrire_atomique,
    verrou_fichier,
)


class TestEcritureAtomique(unittest.TestCase):
    def test_cree_les_dossiers_manquants(self):
        with tempfile.TemporaryDirectory() as tmp:
            cible = Path(tmp) / "a" / "b" / "fichier.yaml"
            ecrire_atomique(cible, "contenu\n")
            self.assertEqual(cible.read_text(encoding="utf-8"), "contenu\n")

    def test_ne_laisse_aucun_temporaire(self):
        with tempfile.TemporaryDirectory() as tmp:
            cible = Path(tmp) / "fichier.yaml"
            ecrire_atomique(cible, "x")
            ecrire_atomique(cible, "y")
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["fichier.yaml"])


class TestAjoutConcurrent(unittest.TestCase):
    def test_deux_threads_deux_cents_ajouts_aucun_perdu(self):
        with tempfile.TemporaryDirectory() as tmp:
            cible = Path(tmp) / "pending.yaml"
            erreurs: list[BaseException] = []

            def travailler(prefixe: str) -> None:
                try:
                    for i in range(200):
                        ajouter_sous_verrou(cible, f"{prefixe}{i}\n", valider=lambda _t: None)
                except BaseException as exc:  # noqa: BLE001 — remonté par le test
                    erreurs.append(exc)

            fils = [threading.Thread(target=travailler, args=(p,)) for p in ("a", "b")]
            for f in fils:
                f.start()
            for f in fils:
                f.join()

            self.assertEqual(erreurs, [])
            lignes = cible.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lignes), 400)
            self.assertEqual(
                sorted(lignes),
                sorted([f"a{i}" for i in range(200)] + [f"b{i}" for i in range(200)]),
            )

    def test_validation_qui_leve_laisse_le_fichier_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            cible = Path(tmp) / "pending.yaml"
            cible.write_text("depart: 1\n", encoding="utf-8")

            def refuser(_texte: str) -> None:
                raise ValueError("collision de clé")

            with self.assertRaises(ValueError):
                ajouter_sous_verrou(cible, "ajout: 2\n", valider=refuser)
            self.assertEqual(cible.read_text(encoding="utf-8"), "depart: 1\n")

    def test_la_validation_voit_le_fichier_complet(self):
        with tempfile.TemporaryDirectory() as tmp:
            cible = Path(tmp) / "pending.yaml"
            cible.write_text("deja: la\n", encoding="utf-8")
            vus: list[str] = []
            ajouter_sous_verrou(cible, "neuf: ici\n", valider=vus.append)
            self.assertEqual(vus, ["deja: la\nneuf: ici\n"])

    def test_ajout_ajoute_le_saut_de_ligne_manquant(self):
        with tempfile.TemporaryDirectory() as tmp:
            cible = Path(tmp) / "pending.yaml"
            cible.write_text("sans-fin-de-ligne", encoding="utf-8")
            ajouter_sous_verrou(cible, "suite", valider=lambda _t: None)
            self.assertEqual(cible.read_text(encoding="utf-8"), "sans-fin-de-ligne\nsuite\n")


class TestVerrouTimeout(unittest.TestCase):
    def test_verrou_deja_pris_expire(self):
        with tempfile.TemporaryDirectory() as tmp:
            cible = Path(tmp) / "fichier.yaml"
            pris = threading.Event()
            liberer = threading.Event()

            def tenir() -> None:
                with verrou_fichier(cible):
                    pris.set()
                    liberer.wait(5)

            fil = threading.Thread(target=tenir)
            fil.start()
            try:
                self.assertTrue(pris.wait(5))
                with self.assertRaises(VerrouIndisponible), verrou_fichier(cible, timeout_s=0.1):
                    pass
            finally:
                liberer.set()
                fil.join()


if __name__ == "__main__":
    unittest.main()
