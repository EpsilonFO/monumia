"""Le miroir Python de l'élimination du QCM, et la mesure de coût en questions.

`profils_questionnaire` rejoue côté serveur ce que le front fait à l'écran :
chaque réponse écarte des aides, donc des questions. C'est ce parcours-là que
le ratchet mesure — un miroir qui dérive ferait mentir le ratchet sans que rien
ne le signale. D'où la fixture PARTAGÉE `fixtures/qcm_elimination.json`, rejouée
ici et par `frontend/src/lib/__tests__/qcm.test.ts`.

Run from backend/:  uv run pytest tests/test_profils_questionnaire.py
"""

import json
import unittest
from pathlib import Path

from aides_schema import Aide, FactDef
from profils_questionnaire import (
    PROFILS,
    aides_eliminees,
    delta_tronc,
    est_visible,
    parcours_simule,
)

FIXTURE = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "qcm_elimination.json").read_text(
        encoding="utf-8"
    )
)


class TestMiroirElimination(unittest.TestCase):
    """La fixture partagée, rejouée côté Python."""

    def test_eliminations(self):
        for cas in FIXTURE["cas_elimination"]:
            with self.subTest(cas=cas["nom"]):
                self.assertEqual(
                    aides_eliminees(cas["answers"], FIXTURE["questions"]),
                    set(cas["eliminees"]),
                )

    def test_visibilite(self):
        par_id = {q["id"]: q for q in FIXTURE["questions"]}
        for cas in FIXTURE["cas_visibilite"]:
            with self.subTest(cas=cas["nom"]):
                self.assertEqual(
                    est_visible(par_id[cas["question"]], cas["answers"]), cas["visible"]
                )


def _aide(slug: str, conditions: list[dict]) -> Aide:
    return Aide.model_validate(
        {
            "slug": slug,
            "nom": slug,
            "organisme": "Organisme d'exemple",
            "categorie": "region",
            "type": "subvention",
            "description": "Aide de test.",
            "conditions": conditions,
        }
    )


def _gate(id_: str, fait: str, predicat: dict) -> dict:
    return {
        "id": id_,
        "text": f"Condition {id_}.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": fait,
        "predicate": predicat,
    }


FACTS = {
    "monument_ouvert_au_public": FactDef.model_validate(
        {"type": "boolean", "scope": "monument", "question": "Ouvert au public ?"}
    ),
    "gratuite_acces": FactDef.model_validate(
        {"type": "boolean", "scope": "projet", "question": "Accès gratuit ?"}
    ),
}


class TestDeltaTronc(unittest.TestCase):
    """Ce qu'une aide coûte au questionnaire de TOUS les propriétaires.

    Invisible depuis la fiche de l'aide : une question n'entre au tronc commun
    que si une AUTRE aide la partage déjà.
    """

    def test_une_aide_qui_partage_une_question_la_fait_entrer_au_tronc(self):
        avant = {"a": _aide("a", [_gate("ouvert", "monument_ouvert_au_public", {"eq": True})])}
        apres = {
            **avant,
            "b": _aide("b", [_gate("ouvert", "monument_ouvert_au_public", {"eq": True})]),
        }
        delta = delta_tronc(avant, apres, FACTS)
        for nom, (tronc_avant, tronc_apres, entrantes) in delta.items():
            with self.subTest(profil=nom):
                self.assertEqual(tronc_avant, 0)
                self.assertEqual(tronc_apres, 1)
                self.assertEqual(entrantes, ["monument_ouvert_au_public"])

    def test_une_aide_dont_la_question_reste_orpheline_ne_coute_rien_au_tronc(self):
        avant = {"a": _aide("a", [_gate("ouvert", "monument_ouvert_au_public", {"eq": True})])}
        apres = {**avant, "b": _aide("b", [_gate("gratuit", "gratuite_acces", {"eq": True})])}
        delta = delta_tronc(avant, apres, FACTS)
        for nom, (tronc_avant, tronc_apres, entrantes) in delta.items():
            with self.subTest(profil=nom):
                self.assertEqual((tronc_avant, tronc_apres, entrantes), (0, 0, []))


class TestParcours(unittest.TestCase):
    """Le parcours sur le catalogue réel : propriétés, pas valeurs."""

    def setUp(self) -> None:
        from aides_schema import load_all_aides, load_facts, load_pending_facts

        self.aides = load_all_aides()
        self.facts = {**load_facts(), **load_pending_facts()}

    def test_le_parcours_est_un_sous_ensemble_ordonne_du_tronc(self):
        from profils_questionnaire import mesurer

        for nom, profil in PROFILS.items():
            with self.subTest(profil=nom):
                parcours = parcours_simule(self.aides, self.facts, profil)
                tronc = [q["id"] for q in mesurer(self.aides, self.facts, profil).tronc]
                self.assertEqual(len(parcours), len(set(parcours)), "question posée deux fois")
                self.assertLessEqual(set(parcours), set(tronc))
                # L'ordre du tronc est celui du moteur : le parcours le suit,
                # il ne fait que sauter les questions devenues inutiles.
                self.assertEqual(parcours, [q for q in tronc if q in set(parcours)])

    def test_le_parcours_est_deterministe(self):
        # Un ratchet qui mesure du bruit ne garde rien : la règle de choix
        # départage à gain égal par l'identifiant, justement pour ça.
        profil = PROFILS["commune, classé, Grand Est (88), restauration"]
        self.assertEqual(
            parcours_simule(self.aides, self.facts, profil),
            parcours_simule(self.aides, self.facts, profil),
        )


if __name__ == "__main__":
    unittest.main()
