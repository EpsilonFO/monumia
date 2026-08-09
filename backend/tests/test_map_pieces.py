"""Fonctions pures de scripts/map_pieces.py (l'appel LLM n'est pas testé)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from map_pieces import inserer_piece_ids, normaliser


class NormalisationTests(unittest.TestCase):
    def test_casse_et_espaces(self) -> None:
        self.assertEqual(normaliser("  Relevé d'Identité Bancaire  "), "releve d'identite bancaire")

    def test_accents_supprimes(self) -> None:
        self.assertEqual(normaliser("Procès-verbal"), "proces-verbal")

    def test_espaces_internes_reduits(self) -> None:
        self.assertEqual(normaliser("RIB   (IBAN)"), "rib (iban)")

    def test_ponctuation_finale_retiree(self) -> None:
        self.assertEqual(normaliser("Titre de propriété."), "titre de propriete")


class InsertionTests(unittest.TestCase):
    YAML = (
        "nom: Aide test\n"
        "documents_requis:\n"
        "  - nom: Relevé d'identité bancaire\n"
        "  - nom: Copie de la convention\n"
        "    obligatoire: false\n"
        "    note: En cas de délégation.\n"
        "  - nom: Pièce sans correspondance\n"
        "\n"
        "tags: []\n"
    )

    def test_insere_apres_le_nom(self) -> None:
        texte, n = inserer_piece_ids(self.YAML, {"releve d'identite bancaire": "rib"})
        self.assertEqual(n, 1)
        self.assertIn("  - nom: Relevé d'identité bancaire\n    piece_id: rib\n", texte)

    def test_conserve_les_autres_cles(self) -> None:
        texte, _ = inserer_piece_ids(self.YAML, {"copie de la convention": "statuts_structure"})
        self.assertIn("    piece_id: statuts_structure\n    obligatoire: false\n", texte)

    def test_libelle_absent_du_mapping_ignore(self) -> None:
        texte, n = inserer_piece_ids(self.YAML, {})
        self.assertEqual(n, 0)
        self.assertEqual(texte, self.YAML)

    def test_idempotent(self) -> None:
        mapping = {"releve d'identite bancaire": "rib"}
        une_fois, _ = inserer_piece_ids(self.YAML, mapping)
        deux_fois, n = inserer_piece_ids(une_fois, mapping)
        self.assertEqual(n, 0)
        self.assertEqual(une_fois, deux_fois)

    def test_hors_bloc_documents_requis_ignore(self) -> None:
        yaml_texte = "conditions:\n  - nom: Relevé d'identité bancaire\n"
        texte, n = inserer_piece_ids(yaml_texte, {"releve d'identite bancaire": "rib"})
        self.assertEqual(n, 0)
        self.assertEqual(texte, yaml_texte)


if __name__ == "__main__":
    unittest.main()
