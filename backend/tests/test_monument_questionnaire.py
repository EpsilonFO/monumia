"""Schema tests for the monument `questionnaire` JSONB persistence.

Proves the request models accept a free-form `questionnaire` dict and that
`_snake_row` keeps the `questionnaire` key intact (it is a single lowercase
word, so camel→snake conversion is a no-op and it is NOT in the popped list).
"""

import unittest

from routers.monuments import (
    CreateMonumentRequest,
    UpdateMonumentRequest,
    _snake_row,
)


class QuestionnaireSchemaTests(unittest.TestCase):
    def test_create_request_accepts_questionnaire(self) -> None:
        body = CreateMonumentRequest(
            nom="Château de Test",
            commune="Paris",
            protection="classe",
            proprietaire="prive",
            etatConservation="bon",
            questionnaire={"q1": "a", "q2": "b"},
        )
        self.assertEqual(body.questionnaire, {"q1": "a", "q2": "b"})

    def test_create_request_questionnaire_defaults_to_none(self) -> None:
        body = CreateMonumentRequest(
            nom="Château de Test",
            commune="Paris",
            protection="classe",
            proprietaire="prive",
            etatConservation="bon",
        )
        self.assertIsNone(body.questionnaire)

    def test_update_request_accepts_questionnaire(self) -> None:
        body = UpdateMonumentRequest(questionnaire={"q1": "a"})
        self.assertEqual(body.questionnaire, {"q1": "a"})

    def test_snake_row_keeps_questionnaire_key(self) -> None:
        body = CreateMonumentRequest(
            nom="Château de Test",
            commune="Paris",
            protection="classe",
            proprietaire="prive",
            etatConservation="bon",
            questionnaire={"q1": "a"},
        )
        row = _snake_row(body.model_dump(exclude_none=True))
        self.assertIn("questionnaire", row)
        self.assertEqual(row["questionnaire"], {"q1": "a"})

    def test_snake_row_omits_questionnaire_when_none(self) -> None:
        body = UpdateMonumentRequest(nom="Renamed")
        row = _snake_row(body.model_dump(exclude_none=True))
        self.assertNotIn("questionnaire", row)


if __name__ == "__main__":
    unittest.main()
