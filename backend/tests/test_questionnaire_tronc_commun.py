"""Ratchet du TRONC COMMUN : le questionnaire général ne doit pas regrossir.

Ce que ce test garde n'est pas le nombre total de questions — il croît avec le
catalogue, et c'est normal : chaque aide apporte ses critères. Il garde le
nombre de questions PARTAGÉES par au moins deux aides, les seules que le
questionnaire général pose (les autres se posent sur la carte de leur aide).
C'est la seule grandeur qui doit rester petite pendant qu'on ingère.

Deux bornes, et la seconde est la vraie alarme :

- la TOLÉRANCE laisse une ingestion légitime réutiliser un fait jusqu'ici
  orphelin. Un fait qui passe de 1 à 2 aides entre au tronc, et c'est
  exactement ce qu'on demande aux ingestions : sans cette marge, le test
  casserait à chaque bonne nouvelle ;
- le PLAFOND, lui, ne bouge pas avec la baseline. Un tronc de quarante
  questions est un tunnel, quelle qu'en soit l'histoire.

Baseline périmée : `uv run python scripts/mesure_questionnaire.py --update-baseline`,
puis on relit le diff comme le reste du lot.
"""

import json
import unittest
from pathlib import Path

from aides_schema import load_all_aides, load_facts, load_pending_facts
from profils_questionnaire import PROFILS, mesurer

AIDES = load_all_aides()
FACTS = {**load_facts(), **load_pending_facts()}

BASELINE_FILE = Path(__file__).resolve().parent.parent / "data" / "questionnaire_baseline.json"

#: Marge laissée à une ingestion qui réutilise un fait jusqu'ici orphelin.
TOLERANCE = 2

#: Au-delà, le tronc commun redevient un tunnel — indépendamment de la baseline.
PLAFOND_TRONC = 35

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
                contexte = (
                    f"\n  profil : {nom}"
                    f"\n  tronc : {len(mesure.tronc)} (baseline {attendu['tronc']}, "
                    f"tolérance {TOLERANCE}, plafond {PLAFOND_TRONC})"
                    f"\n  questions entrées dans le tronc :\n{detail or '      (aucune)'}"
                    f"\n  si la hausse est légitime : {COMMANDE}"
                )
                self.assertLessEqual(len(mesure.tronc), attendu["tronc"] + TOLERANCE, contexte)
                self.assertLessEqual(len(mesure.tronc), PLAFOND_TRONC, contexte)


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
