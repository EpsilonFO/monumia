"""Ratchet du questionnaire : le tunnel ne doit pas rallonger.

Ce que ce test garde n'est pas le nombre total de questions — il croît avec le
catalogue, et c'est normal : chaque aide apporte ses critères. Il garde deux
grandeurs, et la seconde est celle que vit l'utilisateur :

- le TRONC COMMUN : les questions partagées par au moins deux aides, les seules
  que le questionnaire général pose (les autres se posent sur la carte de leur
  aide). C'est ce que le questionnaire POURRAIT poser, réponses vides.
- le PARCOURS SIMULÉ : ce qu'il pose RÉELLEMENT, en rejouant l'élimination du
  front question après question (`parcours_simule`, miroir de
  `frontend/src/lib/qcm.ts`). L'écart n'est pas anecdotique — sur le profil
  Grand Est, 42 questions calculées contre 20 réellement posées, et le
  correctif des gates bénéficiaires du 2026-09-17 se voyait sur les DEUX (68 →
  42, 27 → 20) alors qu'un ratchet purement statique l'aurait manqué avant que
  le porteur n'entre dans les profils.

Deux bornes, et la seconde est la vraie alarme :

- la TOLÉRANCE laisse une ingestion légitime réutiliser un fait jusqu'ici
  orphelin. Un fait qui passe de 1 à 2 aides entre au tronc, et c'est
  exactement ce qu'on demande aux ingestions : sans cette marge, le test
  casserait à chaque bonne nouvelle ;
- le PLAFOND, lui, ne bouge pas avec la baseline. Il porte désormais sur le
  PARCOURS : c'est le nombre de questions qu'un propriétaire doit traverser, et
  aucune histoire de catalogue ne rend vingt-cinq questions supportables.

Baseline périmée : `uv run python scripts/mesure_questionnaire.py --update-baseline`,
puis on relit le diff comme le reste du lot.
"""

import json
import unittest
from pathlib import Path

from aides_schema import load_all_aides, load_facts, load_pending_facts
from profils_questionnaire import PROFILS, mesurer, parcours_simule

AIDES = load_all_aides()
FACTS = {**load_facts(), **load_pending_facts()}

BASELINE_FILE = Path(__file__).resolve().parent.parent / "data" / "questionnaire_baseline.json"

#: Marge laissée à une ingestion qui réutilise un fait jusqu'ici orphelin.
TOLERANCE = 2

#: Au-delà, le questionnaire redevient un tunnel — indépendamment de la
#: baseline. Posé le 2026-09-17, après les gates bénéficiaires : le pire profil
#: (Grand Est) descend alors à 20 questions posées, la marge tient la place
#: d'un lot d'ingestion sans laisser le tunnel se réinstaller.
PLAFOND_PARCOURS = 25

COMMANDE = "uv run python scripts/mesure_questionnaire.py --update-baseline"


class TroncCommunTest(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))

    def test_baseline_couvre_tous_les_profils(self):
        """Un profil ajouté sans baseline doit le dire, pas passer en silence."""
        self.assertEqual(
            sorted(self.baseline),
            sorted(PROFILS),
            f"baseline désynchronisée des profils — lancer : {COMMANDE}",
        )

    def test_tronc_commun_ne_regrossit_pas(self):
        for nom, profil in PROFILS.items():
            with self.subTest(profil=nom):
                attendu = self.baseline.get(nom)
                self.assertIsNotNone(attendu, f"profil absent de la baseline — lancer : {COMMANDE}")
                mesure = mesurer(AIDES, FACTS, profil)
                entrees = sorted({q["id"] for q in mesure.tronc} - set(attendu["tronc_ids"]))
                detail = "\n".join(
                    f"      + {q['id']} ({len(q.get('aideIds') or [])} aides : "
                    f"{', '.join(q.get('aideIds') or [])})"
                    for q in mesure.tronc
                    if q["id"] in entrees
                )
                parcours = parcours_simule(AIDES, FACTS, profil)
                nouvelles = [q for q in parcours if q not in attendu["parcours_ids"]]
                contexte = (
                    f"\n  profil : {nom}"
                    f"\n  tronc : {len(mesure.tronc)} (baseline {attendu['tronc']}, "
                    f"tolérance {TOLERANCE})"
                    f"\n  parcours : {len(parcours)} (baseline {attendu['parcours']}, "
                    f"tolérance {TOLERANCE}, plafond {PLAFOND_PARCOURS})"
                    f"\n  questions entrées dans le tronc :\n{detail or '      (aucune)'}"
                    f"\n  questions entrées dans le parcours : "
                    f"{', '.join(nouvelles) or '(aucune)'}"
                    f"\n  si la hausse est légitime : {COMMANDE}"
                )
                self.assertLessEqual(len(mesure.tronc), attendu["tronc"] + TOLERANCE, contexte)
                self.assertLessEqual(len(parcours), attendu["parcours"] + TOLERANCE, contexte)
                self.assertLessEqual(len(parcours), PLAFOND_PARCOURS, contexte)


class PartitionTest(unittest.TestCase):
    """La partition elle-même, sur le corpus réel."""

    def test_partition_est_une_bipartition(self):
        for nom, profil in PROFILS.items():
            with self.subTest(profil=nom):
                m = mesurer(AIDES, FACTS, profil)
                self.assertEqual(len(m.tronc) + len(m.propres), len(m.questions))
                ids = {q["id"] for q in m.tronc} & {q["id"] for q in m.propres}
                self.assertEqual(ids, set())

    def test_la_porteuse_suit_sa_dependante_dans_le_tronc(self):
        """Une question branchée n'est jamais posée sans sa porteuse."""
        for nom, profil in PROFILS.items():
            with self.subTest(profil=nom):
                m = mesurer(AIDES, FACTS, profil)
                tronc_ids = {q["id"] for q in m.tronc}
                posees = {q["id"] for q in m.questions}
                for q in m.tronc:
                    dep = q.get("dependsOn")
                    if dep and dep["questionId"] in posees:
                        self.assertIn(
                            dep["questionId"],
                            tronc_ids,
                            f"{q['id']} est dans le tronc sans sa porteuse {dep['questionId']}",
                        )


if __name__ == "__main__":
    unittest.main()
