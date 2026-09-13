"""Une réponse persistée sur une option qui n'existe plus vaut fait INCONNU.

Les réponses vivent dans `projets.questionnaire` et survivent aux options :
corriger `facts.yaml`, ou reformuler une question depuis /admin, peut supprimer
l'id qu'un projet a déjà enregistré. Rendre cet id brut aux prédicats
éliminerait des aides pour toujours, sans que personne puisse le corriger — le
moteur doit retomber sur son principe fail-closed : inconnu, donc incertitude.
"""

import unittest

from aides_schema import FactDef, MultiValue
from eligibility_engine import _normalize_answer


def _fact(type_: str) -> FactDef:
    return FactDef.model_validate(
        {
            "type": type_,
            "scope": "monument",
            "question": "q?",
            "options": [
                {"id": "culte", "label": "Culte"},
                {"id": "musee", "label": "Musée"},
                {"id": "inconnu", "label": "Je ne sais pas", "unknown": True},
            ],
        }
    )


class EnumTests(unittest.TestCase):
    def test_option_connue_rendue_telle_quelle(self) -> None:
        self.assertEqual(_normalize_answer(_fact("enum"), "culte"), "culte")

    def test_option_neutre_vaut_inconnu(self) -> None:
        self.assertIsNone(_normalize_answer(_fact("enum"), "inconnu"))

    def test_option_supprimee_vaut_inconnu(self) -> None:
        self.assertIsNone(_normalize_answer(_fact("enum"), "ferme"))

    def test_skip_vaut_inconnu(self) -> None:
        self.assertIsNone(_normalize_answer(_fact("enum"), "skip"))


class MultiEnumTests(unittest.TestCase):
    def test_ne_garde_que_les_options_connues(self) -> None:
        valeur = _normalize_answer(_fact("multi_enum"), ["culte", "ferme", "musee"])
        self.assertEqual(valeur, MultiValue(["culte", "musee"]))

    def test_selection_entierement_perimee_vaut_inconnu(self) -> None:
        self.assertIsNone(_normalize_answer(_fact("multi_enum"), ["ferme", "grange"]))

    def test_option_neutre_toujours_ecartee(self) -> None:
        self.assertEqual(
            _normalize_answer(_fact("multi_enum"), ["inconnu", "culte"]), MultiValue(["culte"])
        )


class BooleenTests(unittest.TestCase):
    """Un booléen sans options garde le couple implicite ; un booléen qui en
    déclare lit la `valeur` de la réponse choisie."""

    @staticmethod
    def _nu() -> FactDef:
        return FactDef.model_validate({"type": "boolean", "scope": "projet", "question": "q ?"})

    @staticmethod
    def _declare() -> FactDef:
        return FactDef.model_validate(
            {
                "type": "boolean",
                "scope": "projet",
                "question": "q ?",
                "options": [
                    {"id": "oui", "label": "Oui", "valeur": True},
                    {"id": "non", "label": "Non", "valeur": False},
                    {"id": "les_deux", "label": "Les deux"},
                    {"id": "nsp", "label": "Je ne sais pas", "unknown": True},
                ],
            }
        )

    def test_couple_implicite(self) -> None:
        self.assertIs(_normalize_answer(self._nu(), "oui"), True)
        self.assertIs(_normalize_answer(self._nu(), "non"), False)

    def test_bool_deja_typé_traverse(self) -> None:
        self.assertIs(_normalize_answer(self._nu(), True), True)
        self.assertIs(_normalize_answer(self._nu(), False), False)

    def test_id_inconnu_vaut_inconnu(self) -> None:
        self.assertIsNone(_normalize_answer(self._nu(), "peut_etre"))

    def test_reponse_deja_enregistree_survit_a_lajout_doptions(self) -> None:
        """La preuve que la migration est INERTE : R1 impose que « oui » et
        « non » survivent, donc un questionnaire déjà rempli ne bouge pas d'un
        pouce quand un fait se met à déclarer ses réponses."""
        for identifiant, attendu in (("oui", True), ("non", False)):
            with self.subTest(identifiant):
                self.assertIs(_normalize_answer(self._nu(), identifiant), attendu)
                self.assertIs(_normalize_answer(self._declare(), identifiant), attendu)

    def test_valeur_nulle_vaut_inconnu(self) -> None:
        """« Ne tranche pas » : le fait reste inconnu, l'aide n'est pas écartée."""
        self.assertIsNone(_normalize_answer(self._declare(), "les_deux"))

    def test_reponse_neutre_vaut_inconnu(self) -> None:
        self.assertIsNone(_normalize_answer(self._declare(), "nsp"))

    def test_option_supprimee_vaut_inconnu(self) -> None:
        self.assertIsNone(_normalize_answer(self._declare(), "parti"))


class SansOntologieTests(unittest.TestCase):
    def test_fait_absent_laisse_la_valeur_brute(self) -> None:
        """Le garde-fou porte sur les OPTIONS d'un fait connu : sans fait, il
        n'y a pas d'options auxquelles comparer."""
        self.assertEqual(_normalize_answer(None, "valeur"), "valeur")


if __name__ == "__main__":
    unittest.main()
