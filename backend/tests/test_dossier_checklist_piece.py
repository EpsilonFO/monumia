"""La checklist générée porte le rattachement au référentiel de pièces."""

import unittest

from services.dossier_service import create_dossier_from_aide

_MONUMENT = {"id": "m1", "nom": "Chapelle", "commune": "Rennes", "protection": "classe"}
_USER = {"id": "u1", "nom": "Dupont", "segment": "prive"}


def _dossier(documents_requis):
    return create_dossier_from_aide(
        aide={"id": "a1", "nom": "Aide test", "documents_requis": documents_requis},
        monument=_MONUMENT,
        user=_USER,
        travaux_prevus=[],
    )


class ChecklistPieceIdTests(unittest.TestCase):
    def test_piece_id_recopie_dans_l_item(self) -> None:
        dossier = _dossier([{"nom": "RIB", "piece_id": "rib"}])
        self.assertEqual(dossier["checklist"][0]["pieceId"], "rib")

    def test_absence_de_piece_id_donne_none(self) -> None:
        dossier = _dossier([{"nom": "Pièce très spécifique"}])
        self.assertIsNone(dossier["checklist"][0]["pieceId"])

    def test_libelle_chaine_simple_donne_none(self) -> None:
        """Ancien format YAML : une chaîne au lieu d'un objet."""
        dossier = _dossier(["Titre de propriété"])
        self.assertIsNone(dossier["checklist"][0]["pieceId"])

    def test_items_issus_des_templates_en_dur_portent_la_cle(self) -> None:
        """Le fallback CHECKLIST_TEMPLATES doit produire la même forme d'item."""
        dossier = create_dossier_from_aide(
            aide={"id": "a1", "nom": "DRAC", "categorie": "etat_drac", "documents_requis": []},
            monument=_MONUMENT,
            user=_USER,
            travaux_prevus=[],
        )
        for item in dossier["checklist"]:
            self.assertIn("pieceId", item)

    def test_statut_initial_inchange(self) -> None:
        dossier = _dossier([{"nom": "RIB", "piece_id": "rib"}])
        self.assertEqual(dossier["checklist"][0]["statut"], "manquant")


if __name__ == "__main__":
    unittest.main()
