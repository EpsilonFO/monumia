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

from aides_schema import load_all_aides
from labels import TRAVAUX_LABELS, TRAVAUX_RETIRES, normaliser_travaux

RACINE = Path(__file__).resolve().parents[2]
FRONT_OPTIONS = RACINE / "frontend" / "src" / "constants" / "monument-options.ts"


class TableDesTypesTravauxTest(unittest.TestCase):
    #: Les vingt-trois types et leur libellé, FIGÉS. Trois d'entre eux décrivent
    #: le DOMAINE et non le bâti : sans eux, une aide qui ne finance qu'une
    #: plantation ou une desserte forestière n'a aucun moyen de dire qu'elle ne
    #: finance pas une charpente. « toiture » et « equipement_professionnel »
    #: sont retirés depuis le 2026-10-07 (cf. labels.TRAVAUX_RETIRES).
    ATTENDUS = {
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

    def test_chaque_type_ouvre_au_moins_une_aide(self) -> None:
        """Une case que l'utilisateur coche doit servir : un code qu'aucune aide
        ne cite écarte, coché seul, toutes les aides cadrées sur des travaux sans
        en ouvrir une seule. C'était `equipement_professionnel`."""
        cites = {code for aide in load_all_aides().values() for code in aide.hard_filters.travaux}
        self.assertEqual(sorted(set(TRAVAUX_LABELS) - cites), [])

    def test_les_codes_retires_ne_sont_plus_proposes(self) -> None:
        self.assertEqual(set(TRAVAUX_RETIRES) & set(TRAVAUX_LABELS), set())
        for remplacants in TRAVAUX_RETIRES.values():
            self.assertLessEqual(set(remplacants), set(TRAVAUX_LABELS))


class NormaliserTravauxTest(unittest.TestCase):
    """Les projets enregistrés avant le retrait d'un code gardent leur résultat."""

    def test_toiture_devient_charpente_et_couverture(self) -> None:
        self.assertEqual(
            normaliser_travaux(["toiture", "facade"]), ["charpente", "couverture", "facade"]
        )

    def test_sans_doublon_et_dans_l_ordre(self) -> None:
        self.assertEqual(
            normaliser_travaux(["facade", "toiture", "charpente"]),
            ["facade", "charpente", "couverture"],
        )

    def test_un_code_sans_remplacant_disparait(self) -> None:
        self.assertEqual(normaliser_travaux(["equipement_professionnel"]), [])
        self.assertEqual(normaliser_travaux(None), [])


if __name__ == "__main__":
    unittest.main()
