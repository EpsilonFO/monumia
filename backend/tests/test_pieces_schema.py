"""Validation du référentiel de pièces canoniques (data/pieces.yaml)."""

import unittest

import pydantic
import yaml

from pieces_schema import PIECES_FILE, Piece, load_pieces


class ReferentielTests(unittest.TestCase):
    def test_referentiel_charge(self) -> None:
        pieces = load_pieces()
        self.assertGreater(len(pieces), 20)

    def test_ids_en_snake_case(self) -> None:
        for key in load_pieces():
            self.assertRegex(key, r"^[a-z0-9_]+$", f"id invalide : {key}")

    def test_pas_de_doublon_de_nom(self) -> None:
        noms = [p.nom.lower() for p in load_pieces().values()]
        self.assertEqual(len(noms), len(set(noms)))

    def test_toutes_les_portees_sont_representees(self) -> None:
        portees = {p.portee for p in load_pieces().values()}
        self.assertEqual(portees, {"porteur", "monument", "operation"})

    def test_yaml_est_un_dictionnaire(self) -> None:
        raw = yaml.safe_load(PIECES_FILE.read_text(encoding="utf-8"))
        self.assertIsInstance(raw, dict)


class PieceValidationTests(unittest.TestCase):
    def _piece(self, **kw):
        base = {"nom": "Test", "portee": "porteur", "type_document": "autre"}
        return Piece.model_validate({**base, **kw})

    def test_perissable_sans_seuil_refuse(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            self._piece(perissable=True)

    def test_seuil_sans_perissable_refuse(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            self._piece(perissable=False, seuil_alerte_mois=12)

    def test_perissable_avec_seuil_accepte(self) -> None:
        piece = self._piece(perissable=True, seuil_alerte_mois=12)
        self.assertEqual(piece.seuil_alerte_mois, 12)

    def test_portee_inconnue_refusee(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            self._piece(portee="galaxie")

    def test_type_document_hors_enum_refuse(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            self._piece(type_document="hologramme")

    def test_champ_inconnu_refuse(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            self._piece(couleur="bleu")


class DocumentPieceIdTests(unittest.TestCase):
    """Le champ piece_id d'une pièce demandée est validé contre le référentiel."""

    def test_piece_id_connu_accepte(self) -> None:
        from aides_schema import Document

        doc = Document.model_validate({"nom": "RIB", "piece_id": "rib"})
        self.assertEqual(doc.piece_id, "rib")

    def test_piece_id_inconnu_refuse(self) -> None:
        from aides_schema import Document

        with self.assertRaises(pydantic.ValidationError):
            Document.model_validate({"nom": "RIB", "piece_id": "piece_qui_nexiste_pas"})

    def test_piece_id_absent_reste_none(self) -> None:
        from aides_schema import Document

        doc = Document.model_validate({"nom": "Pièce très spécifique"})
        self.assertIsNone(doc.piece_id)

    def test_corpus_ne_reference_que_des_pieces_connues(self) -> None:
        """Filet CI : la veille ajoute des aides en continu."""
        from aides_schema import load_all_aides

        connues = set(load_pieces())
        for slug, aide in load_all_aides().items():
            for doc in aide.documents_requis:
                if doc.piece_id is not None:
                    self.assertIn(doc.piece_id, connues, f"{slug} : pièce inconnue")


if __name__ == "__main__":
    unittest.main()
