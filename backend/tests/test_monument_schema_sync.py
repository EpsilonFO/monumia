"""Regression tests guarding the monument request models against schema drift.

Migration 20260516174303_remove_unused_columns_monuments_table.sql dropped ten
columns from `monuments` (the questionnaire answers now live in the single
`questionnaire` JSONB column added by 20260613090000). The request models must
not emit those columns: PostgREST rejects an insert/update that references a
column missing from its schema cache (PGRST204), which crashed the "Terminer"
step of the Projet wizard.
"""

import unittest

from routers.monuments import (
    CreateMonumentRequest,
    UpdateMonumentRequest,
    _snake_row,
)

# snake_case names of every column dropped from `monuments`, plus `adresse`
# which was never a column on the table.
REMOVED_COLUMNS = (
    "affectataire",
    "periode_construction",
    "superficie",
    "materiaux",
    "type_couverture",
    "nombre_niveaux",
    "urgence_travaux",
    "diagnostic_realise",
    "derniers_travaux",
    "description_etat",
    "adresse",
)


class RemovedColumnsSchemaTests(unittest.TestCase):
    def test_create_row_excludes_removed_columns(self) -> None:
        body = CreateMonumentRequest(
            nom="Château de Test",
            commune="Paris",
            protection="classe",
            proprietaire="prive",
            etatConservation="bon",
            affectataire="Commune de Test",
            periodeConstruction=["XIXe"],
            superficie=120.0,
            materiaux=["pierre"],
            typeCouverture="ardoise",
            nombreNiveaux=3,
            urgenceTravaux="haute",
            diagnosticRealise=True,
            derniersTravaux="2020-01-01",
            descriptionEtat="bon état général",
        )
        row = _snake_row(body.model_dump(exclude_none=True))
        for col in REMOVED_COLUMNS:
            self.assertNotIn(col, row, f"{col} must not reach the monuments insert")

    def test_update_row_excludes_removed_columns(self) -> None:
        body = UpdateMonumentRequest(
            nom="Renamed",
            adresse="1 rue de Test",
            affectataire="Commune de Test",
            superficie=120.0,
            urgenceTravaux="haute",
            diagnosticRealise=True,
            descriptionEtat="bon état",
        )
        row = _snake_row(body.model_dump(exclude_none=True))
        for col in REMOVED_COLUMNS:
            self.assertNotIn(col, row, f"{col} must not reach the monuments update")


if __name__ == "__main__":
    unittest.main()
