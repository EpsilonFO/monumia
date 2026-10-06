"""Cliquet de la forme des questions (règle du 2026-10-06, en-tête de facts.yaml).

Le lint AVERTIT sur chaque question trop longue et chaque libellé trop long ;
ce test empêche la dette de REMONTER. Les plafonds ci-dessous sont l'état du
catalogue au moment où la règle a été posée : on les baisse quand on résorbe,
on ne les monte jamais. Un fait neuf qui dépasse se réécrit (question courte,
détail dans `help`, énumération dans les `description` des options), il ne
relève pas le plafond.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ontologie_regles import (  # noqa: E402
    MAX_CAR_LIBELLE_OPTION,
    libelles_trop_longs,
    options_a_grouper,
    question_trop_longue,
)

from aides_schema import load_facts, load_pending_facts  # noqa: E402

#: Questions de plus de 200 caractères. La dernière,
#: `projet_hors_exclusions_artificialisation_cours_eau`, attend une décision :
#: sa question dit l'inverse de son prédicat.
PLAFOND_QUESTIONS_LONGUES = 1
#: Libellés d'option de plus de `MAX_CAR_LIBELLE_OPTION` caractères.
PLAFOND_LIBELLES_LONGS = 0
#: Faits à plus de huit options sans aucun `groupe`.
PLAFOND_FAITS_A_GROUPER = 0

FAITS = {**load_facts(), **load_pending_facts()}


class FormeDesFaitsTest(unittest.TestCase):
    def test_questions_longues(self) -> None:
        longues = sorted(k for k, f in FAITS.items() if question_trop_longue(f, maximum=200))
        self.assertLessEqual(len(longues), PLAFOND_QUESTIONS_LONGUES, longues)

    def test_libelles_longs(self) -> None:
        longs = sorted(
            f"{k}.{oid}" for k, f in FAITS.items() for oid in libelles_trop_longs(f.options)
        )
        self.assertLessEqual(len(longs), PLAFOND_LIBELLES_LONGS, (MAX_CAR_LIBELLE_OPTION, longs))

    def test_faits_a_grouper(self) -> None:
        a_grouper = sorted(k for k, f in FAITS.items() if options_a_grouper(f.options))
        self.assertLessEqual(len(a_grouper), PLAFOND_FAITS_A_GROUPER, a_grouper)

    def test_aucun_tiret_cadratin_dans_ce_qui_saffiche_aux_options(self) -> None:
        for k, f in FAITS.items():
            for o in f.options or []:
                for texte in (o.label, o.description or "", o.groupe or ""):
                    self.assertNotIn("—", texte, f"{k}.{o.id}")


if __name__ == "__main__":
    unittest.main()
