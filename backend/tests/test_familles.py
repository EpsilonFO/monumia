"""Les familles thématiques : une liste fermée en TROIS endroits.

`labels.FAMILLES_LABELS` (d'où `aides_schema.FAMILLES` dérive), le CHECK SQL de
la migration `ajouter_familles_aides_v3`, et `FAMILLE_OPTIONS` côté front. Une
famille ajoutée à l'un et pas aux autres passerait la validation Pydantic et
échouerait à l'insertion (ou l'inverse : un code accepté en base qu'aucun
libellé ne sait rendre).

Le miroir front est `frontend/src/constants/__tests__/familles.test.ts`, qui
assène les mêmes valeurs — patron `test_billing_access.py::TableDesOffresTest`
↔ `offres.test.ts`.
"""

import re
import unittest
from pathlib import Path

from pydantic import ValidationError

from aides_schema import FAMILLES, Aide
from labels import FAMILLES_DESCRIPTION, FAMILLES_LABELS

RACINE = Path(__file__).resolve().parents[2]
MIGRATIONS = RACINE / "supabase" / "migrations"
FRONT_FAMILLES = RACINE / "frontend" / "src" / "constants" / "familles.ts"


class TableDesFamillesTest(unittest.TestCase):
    #: Les treize familles et leur libellé produit, FIGÉS. Toute modification
    #: ici doit se retrouver dans le front et dans le CHECK SQL.
    ATTENDUES = {
        "restauration_bati": "Restauration du bâti",
        "energie_climat": "Énergie et climat",
        "eau_nature_domaine": "Eau, nature et domaine",
        "securite_risques": "Sécurité et risques",
        "parcs_jardins_paysages": "Parcs, jardins et paysages",
        "tourisme_hebergement": "Tourisme et hébergement",
        "activite_economique_lieu": "Activité économique dans le lieu",
        "spectacles_manifestations": "Spectacles et manifestations",
        "vie_locale_associative": "Vie locale et associative",
        "mediation_numerique_expositions": "Médiation, expositions, musée, numérique",
        "accessibilite_publics": "Accessibilité et accueil des publics",
        "etudes_ingenierie": "Études et ingénierie",
        "labels_passerelles": "Labels et passerelles",
    }

    def test_les_treize_familles_et_leurs_libelles(self) -> None:
        self.assertEqual(FAMILLES_LABELS, self.ATTENDUES)
        self.assertEqual(FAMILLES, tuple(self.ATTENDUES))

    def test_chaque_famille_a_sa_description(self) -> None:
        """La description part dans les prompts d'ingestion et sert de règle au
        relecteur : « eau_nature_domaine » ne se devine pas."""
        self.assertEqual(list(FAMILLES_DESCRIPTION), list(FAMILLES_LABELS))
        for code, description in FAMILLES_DESCRIPTION.items():
            self.assertTrue(description.strip(), code)

    def test_le_check_sql_dit_la_meme_chose(self) -> None:
        """La migration est lue par glob sur son nom : son horodatage est celui
        du CLI et ne doit pas figer le test."""
        fichiers = sorted(MIGRATIONS.glob("*ajouter_familles_aides_v3.sql"))
        self.assertEqual(len(fichiers), 1, "migration des familles introuvable ou en double")
        sql = fichiers[0].read_text(encoding="utf-8")
        tableau = re.search(r"familles <@ array\[(.*?)\]::text\[\]", sql, re.S)
        self.assertIsNotNone(tableau, "CHECK `familles <@ array[...]` absent de la migration")
        assert tableau is not None  # pour pyright
        litteraux = re.findall(r"'([a-z_]+)'", tableau.group(1))
        self.assertEqual(litteraux, list(FAMILLES_LABELS))

    def test_le_front_dit_la_meme_chose(self) -> None:
        """Le type `Famille` et `FAMILLE_OPTIONS` sont testés côté front ; ici
        on vérifie seulement que les treize CODES y sont, pour qu'un ajout
        backend ne puisse pas rester invisible à l'écran."""
        source = FRONT_FAMILLES.read_text(encoding="utf-8")
        for code in FAMILLES_LABELS:
            self.assertIn(f"'{code}'", source, code)

    def test_une_aide_ne_peut_porter_quune_famille_du_referentiel(self) -> None:
        base = {
            "slug": "fx",
            "nom": "Fixture",
            "organisme": "Org",
            "categorie": "region",
            "type": "subvention",
            "description": "d",
        }
        self.assertEqual(Aide.model_validate(base).familles, [])
        self.assertEqual(
            Aide.model_validate({**base, "familles": ["spectacles_manifestations"]}).familles,
            ["spectacles_manifestations"],
        )
        with self.assertRaises(ValidationError):
            Aide.model_validate({**base, "familles": ["musee"]})
        # `adjacente` et `hors_perimetre` sont des décisions de TRI de la skill
        # de prospection, pas des familles : elles doivent être refusées.
        for tri in ("adjacente", "hors_perimetre"):
            with self.assertRaises(ValidationError, msg=tri):
                Aide.model_validate({**base, "familles": [tri]})


if __name__ == "__main__":
    unittest.main()
