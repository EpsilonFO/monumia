"""Tests de la file d'attente (scripts/pipeline/etat.py).

Ce qui est vérifié ici, c'est qu'aucune décision humaine ne peut être effacée
par une machine : une prospection rejouée ne remet pas en `a_valider` une aide
déjà ingérée, et deux orchestrateurs ne peuvent pas prendre le même slug.

Run from backend/:  uv run pytest tests/test_pipeline_etat.py
"""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline.etat import (  # noqa: E402
    Ingestion,
    Tache,
    charger,
    ecrire,
    fusionner,
    mettre_a_jour,
    selectionner,
    transition,
)


def tache(**kw) -> Tache:
    base = {
        "titre": "Aide d'exemple",
        "url": "https://example.org/aide",
        "territoire": "hauts-de-france",
        "ajoute_le": date(2026, 9, 6),
    }
    return Tache.model_validate({**base, **kw})


class TestRoundTrip(unittest.TestCase):
    def test_ecriture_relecture_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            depart = {
                "hdf-b": tache(famille="restauration_bati"),
                "hdf-a": tache(
                    urls_pdf=["https://example.org/reglement.pdf"],
                    statut="ingere",
                    ingestion=Ingestion(tours=54, cout_usd=0.31, tentatives=1),
                ),
            }
            ecrire(chemin, depart)
            relu = charger(chemin)
            self.assertEqual(relu, depart)
            premier = chemin.read_text(encoding="utf-8")
            ecrire(chemin, relu)
            self.assertEqual(chemin.read_text(encoding="utf-8"), premier)

    def test_slugs_tries_et_champs_vides_omis(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"zz": tache(), "aa": tache()})
            texte = chemin.read_text(encoding="utf-8")
            self.assertLess(texte.index("aa:"), texte.index("zz:"))
            self.assertNotIn("famille:", texte)
            self.assertNotIn("ingestion:", texte)

    def test_motif_echec_nul_reste_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"aa": tache(ingestion=Ingestion(tours=3))})
            self.assertIn("motif_echec: null", chemin.read_text(encoding="utf-8"))


class TestFusion(unittest.TestCase):
    def test_ajoute_les_inconnus_et_les_renvoie(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            self.assertEqual(fusionner(chemin, {"hdf-a": tache()}), ["hdf-a"])
            self.assertEqual(fusionner(chemin, {"hdf-a": tache(), "hdf-b": tache()}), ["hdf-b"])

    def test_preserve_un_slug_deja_ingere(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(
                chemin,
                {"hdf-a": tache(statut="ingere", ingestion=Ingestion(tours=54, tentatives=1))},
            )
            self.assertEqual(fusionner(chemin, {"hdf-a": tache(statut="a_valider")}), [])
            relu = charger(chemin)["hdf-a"]
            self.assertEqual(relu.statut, "ingere")
            assert relu.ingestion is not None
            self.assertEqual(relu.ingestion.tours, 54)

    def test_preserve_un_slug_ignore_a_la_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"hdf-a": tache(statut="ignore")})
            fusionner(chemin, {"hdf-a": tache()})
            self.assertEqual(charger(chemin)["hdf-a"].statut, "ignore")

    def test_complete_les_pdf_sans_doublon(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"hdf-a": tache(statut="valide", urls_pdf=["https://e.org/1.pdf"])})
            fusionner(
                chemin,
                {"hdf-a": tache(urls_pdf=["https://e.org/1.pdf", "https://e.org/2.pdf"])},
            )
            relu = charger(chemin)["hdf-a"]
            self.assertEqual(relu.urls_pdf, ["https://e.org/1.pdf", "https://e.org/2.pdf"])
            self.assertEqual(relu.statut, "valide")


class TestTransition(unittest.TestCase):
    def test_prise_de_jeton_puis_refus(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"hdf-a": tache(statut="valide")})
            self.assertTrue(transition(chemin, "hdf-a", "en_cours", depuis=("valide",)))
            # Le second orchestrateur trouve le slug déjà pris.
            self.assertFalse(transition(chemin, "hdf-a", "en_cours", depuis=("valide",)))

    def test_refuse_de_reprendre_une_aide_ingeree(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"hdf-a": tache(statut="ingere")})
            self.assertFalse(transition(chemin, "hdf-a", "en_cours", depuis=("valide",)))
            self.assertEqual(charger(chemin)["hdf-a"].statut, "ingere")

    def test_slug_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {})
            self.assertFalse(transition(chemin, "inconnu", "en_cours", depuis=("valide",)))


class TestMiseAJour(unittest.TestCase):
    def test_fusionne_le_bloc_ingestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {"hdf-a": tache(ingestion=Ingestion(tentatives=1, modele="glm-flash"))})
            mettre_a_jour(chemin, "hdf-a", statut="echec", ingestion={"motif_echec": "lint rouge"})
            relu = charger(chemin)["hdf-a"]
            assert relu.ingestion is not None
            self.assertEqual(relu.statut, "echec")
            self.assertEqual(relu.ingestion.motif_echec, "lint rouge")
            # Ce que la tentative précédente avait consigné survit.
            self.assertEqual(relu.ingestion.tentatives, 1)
            self.assertEqual(relu.ingestion.modele, "glm-flash")

    def test_slug_absent_leve(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "file-attente.yaml"
            ecrire(chemin, {})
            with self.assertRaises(KeyError):
                mettre_a_jour(chemin, "inconnu", statut="echec")


class TestSelection(unittest.TestCase):
    def test_filtre_et_trie_par_priorite(self):
        etat = {
            "b-normale": tache(statut="valide"),
            "a-basse": tache(statut="valide", priorite="basse"),
            "c-haute": tache(statut="valide", priorite="haute"),
            "d-attente": tache(statut="a_valider", priorite="haute"),
            "e-ailleurs": tache(statut="valide", territoire="normandie"),
        }
        self.assertEqual(
            selectionner(etat, territoires=["hauts-de-france"]),
            ["c-haute", "b-normale", "a-basse"],
        )
        self.assertEqual(selectionner(etat, statuts=("a_valider",)), ["d-attente"])
        self.assertEqual(selectionner(etat, slugs=["a-basse", "d-attente"]), ["a-basse"])


class TestChargementAbsent(unittest.TestCase):
    def test_fichier_absent_donne_file_vide(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(charger(Path(tmp) / "rien.yaml"), {})


if __name__ == "__main__":
    unittest.main()
