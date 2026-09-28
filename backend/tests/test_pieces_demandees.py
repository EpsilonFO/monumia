"""Les pièces que demandent les aides d'un projet (« À déposer pour vos aides »).

Deux chemins : la fonction pure qui lit un diagnostic, et l'étiquette `piece_id`
que la route de dépôt pose sur le document créé depuis cette liste.
"""

import unittest

import pydantic
from fastapi import HTTPException

from pieces_schema import TYPE_DOCUMENTS, load_pieces
from routers.dashboard import build_digest
from routers.documents import CreateDocumentRequest, UpdateDocumentRequest, create_document
from services.pieces_demandees import PIECES_PROPRES_AU_FINANCEUR, pieces_demandees
from tests.test_document_visibility_endpoints import _supabase


def _match(aide_id: str, pieces: list[str | None], disponibilite: str = "maintenant") -> dict:
    return {
        "aide": {
            "id": aide_id,
            "nom": aide_id,
            "categorie": "etat",
            "documentsRequis": [{"nom": f"pièce {p}", "piece_id": p} for p in pieces],
        },
        "disponibilite": disponibilite,
    }


class PiecesDemandeesTests(unittest.TestCase):
    def test_compte_les_aides_des_trois_seaux_a_portee(self) -> None:
        result = {
            "aidesEligibles": [_match("a1", ["rib", "plan_financement"])],
            "aidesPotentiellementEligibles": [_match("a2", ["rib"])],
            "aidesAtteignables": [_match("a3", ["rib"])],
            "aidesNonEligibles": [_match("a4", ["rib", "titre_propriete"])],
        }
        pieces = pieces_demandees(result)
        self.assertEqual([p["pieceId"] for p in pieces], ["rib", "plan_financement"])
        self.assertEqual(pieces[0]["aideIds"], ["a1", "a2", "a3"])
        # Le référentiel donne le nom, la description et le type.
        rib = load_pieces()["rib"]
        self.assertEqual(pieces[0]["nom"], rib.nom)
        self.assertEqual(pieces[0]["description"], rib.description)
        self.assertEqual(pieces[0]["typeDocument"], "rib")
        self.assertEqual(pieces[0]["portee"], "porteur")

    def test_une_aide_qui_cite_deux_fois_la_meme_piece_compte_une_fois(self) -> None:
        result = {"aidesEligibles": [_match("a1", ["rib", "rib"])]}
        self.assertEqual(pieces_demandees(result)[0]["aideIds"], ["a1"])

    def test_pieces_propres_au_financeur_exclues(self) -> None:
        result = {"aidesEligibles": [_match("a1", [*PIECES_PROPRES_AU_FINANCEUR, "rib"])]}
        self.assertEqual([p["pieceId"] for p in pieces_demandees(result)], ["rib"])

    def test_pieces_sans_id_ou_hors_referentiel_ignorees(self) -> None:
        result = {"aidesEligibles": [_match("a1", [None, "piece_fantome"])]}
        self.assertEqual(pieces_demandees(result), [])

    def test_aides_a_venir_hors_offre_ne_comptent_pas(self) -> None:
        # Hors offre, une aide au guichet fermé perd ses documentsRequis
        # (retirer_les_modalites) : le compteur ne doit pas les rendre.
        result = {"aidesEligibles": [_match("a1", ["rib"]), _match("a2", ["rib"], "bientot")]}
        self.assertEqual(pieces_demandees(result, masquer_bientot=True)[0]["aideIds"], ["a1"])
        self.assertEqual(pieces_demandees(result)[0]["aideIds"], ["a1", "a2"])

    def test_tri_par_nombre_d_aides_puis_par_id(self) -> None:
        result = {
            "aidesEligibles": [
                _match("a1", ["statuts_structure", "rib"]),
                _match("a2", ["rib", "devis_travaux"]),
            ]
        }
        self.assertEqual(
            [p["pieceId"] for p in pieces_demandees(result)],
            ["rib", "devis_travaux", "statuts_structure"],
        )

    def test_le_digest_porte_les_pieces(self) -> None:
        result = {"aidesEligibles": [_match("a1", ["rib"])]}
        digest = build_digest(result, "m1", "p1")
        self.assertEqual(digest["piecesDemandees"][0]["pieceId"], "rib")


class ReferentielTypesTests(unittest.TestCase):
    def test_chaque_piece_a_un_type_connu(self) -> None:
        for piece in load_pieces().values():
            self.assertIn(piece.type_document, TYPE_DOCUMENTS)

    def test_les_six_nouveaux_types_servent(self) -> None:
        types = {p.type_document for p in load_pieces().values()}
        for t in (
            "autorisation_urbanisme",
            "rib",
            "titre_propriete",
            "deliberation",
            "statuts",
            "plan_financement",
        ):
            self.assertIn(t, types)


class DepotAvecPieceTests(unittest.TestCase):
    def _body(self, **over):
        base = dict(
            nom="RIB",
            nom_fichier="rib.pdf",
            type="rib",
            taille_fichier=10,
            mime_type="application/pdf",
            url="u1/rib.pdf",
            monument_ids=["m1"],
        )
        base.update(over)
        return CreateDocumentRequest(**base)

    def test_piece_id_estampille_le_document(self) -> None:
        fake = _supabase(caller_role="owner")
        create_document(self._body(piece_id="rib"), user_id="u1", supabase=fake)
        self.assertEqual(fake.inserted[0]["piece_id"], "rib")

    def test_sans_piece_id_rien_n_est_pose(self) -> None:
        fake = _supabase(caller_role="owner")
        create_document(self._body(), user_id="u1", supabase=fake)
        self.assertNotIn("piece_id", fake.inserted[0])

    def test_piece_id_inconnu_refuse(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            self._body(piece_id="piece_fantome")

    def test_type_inconnu_refuse(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            self._body(type="hologramme")
        with self.assertRaises(pydantic.ValidationError):
            UpdateDocumentRequest(type="hologramme")

    def test_nouveau_type_accepte(self) -> None:
        self.assertEqual(UpdateDocumentRequest(type="plan_financement").type, "plan_financement")

    def test_le_droit_de_deposer_reste_exige(self) -> None:
        fake = _supabase(caller_role=None)
        with self.assertRaises(HTTPException):
            create_document(self._body(piece_id="rib"), user_id="u1", supabase=fake)


if __name__ == "__main__":
    unittest.main()
