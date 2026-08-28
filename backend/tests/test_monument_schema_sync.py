"""Regression tests guarding the monument request models against schema drift.

Migration 20260516174303_remove_unused_columns_monuments_table.sql dropped ten
columns from `monuments`. La dépréciation qui suit la création de `projets` en
a retiré trois de plus (`questionnaire`, `travaux_envisages`, `cloture_at`) :
le cadrage d'un chantier vit désormais sur le projet. Les modèles de requête ne
doivent émettre aucune de ces colonnes — PostgREST rejette un insert/update qui
référence une colonne absente de son cache de schéma (PGRST204), ce qui cassait
l'étape « Terminer » du wizard.

`etat_conservation`, lui, RESTE une colonne de `monuments` : la question « en
péril ? » décrit le bien et tous ses projets la partagent.
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
    "questionnaire",
    "travaux_envisages",
    "cloture_at",
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
            travauxEnvisages=["toiture"],
            questionnaire={"q1": "a"},
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
            travauxEnvisages=["toiture"],
            questionnaire={"q1": "a"},
        )
        row = _snake_row(body.model_dump(exclude_none=True))
        for col in REMOVED_COLUMNS:
            self.assertNotIn(col, row, f"{col} must not reach the monuments update")

    def test_etat_conservation_reste_une_colonne_du_monument(self) -> None:
        """Garde-fou inverse : l'état sanitaire ne doit PAS partir avec le reste."""
        row = _snake_row(
            UpdateMonumentRequest(etatConservation="peril").model_dump(exclude_none=True)
        )
        self.assertEqual(row["etat_conservation"], "peril")


if __name__ == "__main__":
    unittest.main()
