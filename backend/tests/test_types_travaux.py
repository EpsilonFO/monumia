"""Les types de travaux : une liste fermée en DEUX endroits.

`labels.TRAVAUX_LABELS`, qui cadre les aides (`hard_filters.travaux`), et
`WORK_TYPES` côté front, qui est la liste que l'utilisateur COCHE à l'étape
travaux du wizard. Aucune contrainte SQL ne les garde : `travaux_envisages` est
un `text[]` libre.

L'écart est à sens unique et SILENCIEUX : un code présent côté backend et absent
du front rend introuvables toutes les aides qui s'y cadrent — l'utilisateur ne
peut pas le cocher, l'intersection de `_evaluate_hard_filters` est donc toujours
vide, et rien ne le lui dit. C'est exactement le faux négatif que la doctrine du
champ interdit (cf. data/TYPING.md, § `hard_filters.travaux`).

Patron : `test_familles.py::TableDesFamillesTest`.
"""

import re
import unittest
from pathlib import Path

from labels import TRAVAUX_LABELS

RACINE = Path(__file__).resolve().parents[2]
FRONT_OPTIONS = RACINE / "frontend" / "src" / "constants" / "monument-options.ts"


class TableDesTypesTravauxTest(unittest.TestCase):
    #: Les vingt-quatre types et leur libellé, FIGÉS. Les quatre derniers
    #: décrivent le DOMAINE et non le bâti : sans eux, une aide qui ne finance
    #: qu'une plantation ou une desserte forestière n'a aucun moyen de dire
    #: qu'elle ne finance pas une toiture.
    ATTENDUS = {
        "toiture": "Toiture",
        "charpente": "Charpente",
        "couverture": "Couverture",
        "facade": "Façade",
        "maconnerie": "Maçonnerie",
        "vitraux": "Vitraux",
        "peintures_murales": "Peintures murales",
        "menuiserie": "Menuiserie",
        "electricite": "Électricité",
        "plomberie": "Plomberie",
        "chauffage": "Chauffage",
        "accessibilite": "Accessibilité",
        "mise_en_securite": "Mise en sécurité",
        "etude_prealable": "Étude préalable",
        "mobilier": "Mobilier",
        "archives": "Archives et documents (photographies, fonds papier, audiovisuel)",
        "orgues": "Orgues",
        "parcs_jardins": "Parcs et jardins",
        "protection_solaire": "Protection solaire",
        "ventilation": "Ventilation",
        "exploitation_agricole": "Exploitation agricole (plantations, vergers, haies)",
        "foret": "Forêt et desserte forestière",
        "eau_milieux_aquatiques": "Eau et milieux aquatiques (cours d'eau, étang, captage)",
        "equipement_professionnel": "Équipement professionnel (matériel, véhicule)",
        "equipement_numerique": "Équipement numérique (informatique, outils de médiation, affichage, réseau)",
    }

    def test_les_types_et_leurs_libelles(self) -> None:
        self.assertEqual(TRAVAUX_LABELS, self.ATTENDUS)

    def test_le_front_propose_exactement_les_memes_codes(self) -> None:
        """Les CODES, pas les libellés : le front écrit les apostrophes en ’
        typographique, et figer la ponctuation ferait échouer le test sur une
        correction de forme sans conséquence."""
        bloc = re.search(
            r"export const WORK_TYPES = \[(.*?)\] as const;",
            FRONT_OPTIONS.read_text(encoding="utf-8"),
            re.S,
        )
        assert bloc is not None, "WORK_TYPES introuvable dans monument-options.ts"
        codes = re.findall(r"value:\s*'([a-z_]+)'", bloc.group(1))
        self.assertEqual(codes, list(TRAVAUX_LABELS))


if __name__ == "__main__":
    unittest.main()
