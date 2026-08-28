"""Schémas des projets de travaux : ce qui part en base et ce qui n'y va pas.

Reprend au grain PROJET ce que test_monument_questionnaire.py garantissait au
grain monument, plus les deux pièges propres à la nouvelle table :
  - `travaux_envisages = []` est une réponse valide (« Pas encore déterminé »),
    le hard_filter travaux du moteur étant fail-open sur liste vide ;
  - `user_id` ne doit JAMAIS sortir d'un PATCH (trigger `lock_owner`).
"""

import unittest

from routers.projets import CreateProjetRequest, UpdateProjetRequest, _row_from


class CreateProjetSchemaTests(unittest.TestCase):
    def test_accepte_une_liste_de_travaux_vide(self) -> None:
        body = CreateProjetRequest(travauxEnvisages=[])
        self.assertEqual(body.travauxEnvisages, [])
        self.assertEqual(_row_from(body)["travaux_envisages"], [])

    def test_travaux_par_defaut_vide(self) -> None:
        self.assertEqual(CreateProjetRequest().travauxEnvisages, [])

    def test_questionnaire_conserve_les_cles_reservees(self) -> None:
        """Les clés « _ » (métadonnées du diagnostic) voyagent telles quelles."""
        body = CreateProjetRequest(questionnaire={"_raisons": ["fiscalite"], "fait_x": "oui"})
        row = _row_from(body)
        self.assertEqual(row["questionnaire"], {"_raisons": ["fiscalite"], "fait_x": "oui"})

    def test_questionnaire_absent_par_defaut(self) -> None:
        self.assertNotIn("questionnaire", _row_from(CreateProjetRequest()))

    def test_ignore_les_cles_inconnues(self) -> None:
        """Un client qui enverrait encore `monumentId` ou `userId` ne doit pas
        les voir atteindre l'insert (PGRST204 / trigger lock_owner)."""
        body = CreateProjetRequest.model_validate(
            {"titre": "Toiture", "monumentId": "m1", "userId": "u1"}
        )
        self.assertEqual(_row_from(body), {"titre": "Toiture", "travaux_envisages": []})


class UpdateProjetSchemaTests(unittest.TestCase):
    def test_patch_vide_ne_touche_rien(self) -> None:
        self.assertEqual(_row_from(UpdateProjetRequest()), {})

    def test_patch_travaux_vide_est_transmis(self) -> None:
        """`[]` n'est pas `None` : « Pas encore déterminé » doit s'enregistrer."""
        row = _row_from(UpdateProjetRequest(travauxEnvisages=[]))
        self.assertEqual(row, {"travaux_envisages": []})

    def test_patch_ne_porte_jamais_user_id(self) -> None:
        body = UpdateProjetRequest.model_validate({"titre": "Nouveau", "userId": "autre"})
        self.assertNotIn("user_id", _row_from(body))
        self.assertNotIn("userId", _row_from(body))

    def test_patch_questionnaire_seul(self) -> None:
        row = _row_from(UpdateProjetRequest(questionnaire={"fait_y": ["a", "b"]}))
        self.assertEqual(row, {"questionnaire": {"fait_y": ["a", "b"]}})


if __name__ == "__main__":
    unittest.main()
