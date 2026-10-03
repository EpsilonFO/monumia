"""Progression d'un dossier : la part des pièces fournies sur toutes ses pièces.

C'est le chiffre de l'anneau sur la carte du dossier ; il doit dire la même
chose que la page du dossier (« 4 / 12 »).
"""

import unittest

from routers.dossiers import _recalculate_progression


def _piece(statut: str, obligatoire: bool = True) -> dict:
    return {"statut": statut, "obligatoire": obligatoire}


class ProgressionTests(unittest.TestCase):
    def test_compte_aussi_les_pieces_facultatives(self) -> None:
        # Les trois obligatoires sont là, mais huit pièces sur douze manquent :
        # ne compter que les obligatoires annonçait 100 %.
        checklist = [
            _piece("fourni"),
            _piece("fourni"),
            _piece("fourni"),
            _piece("fourni", obligatoire=False),
            *[_piece("manquant", obligatoire=False) for _ in range(8)],
        ]
        self.assertEqual(_recalculate_progression({"checklist": checklist}), 33)

    def test_une_piece_reprise_ne_compte_pas_avant_confirmation(self) -> None:
        checklist = [_piece("fourni"), _piece("repris")]
        self.assertEqual(_recalculate_progression({"checklist": checklist}), 50)

    def test_checklist_vide(self) -> None:
        self.assertEqual(_recalculate_progression({"checklist": []}), 0)


if __name__ == "__main__":
    unittest.main()
