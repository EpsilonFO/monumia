"""La rédaction des fiches : seconde chance après un refus des contrôles."""

import shutil
import sys
import tempfile
import unittest
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import rediger_fiches  # noqa: E402

from aides_schema import AIDES_DIR, load_aide  # noqa: E402

# Une fiche réelle et rédigée : sa propre fiche passe les contrôles.
ETALON = rediger_fiches.EXEMPLE


@dataclass
class _Reponse:
    error: str | None = None


@dataclass
class _Essai:
    data: object
    response: _Reponse


class FauxClient:
    """Rend les fiches données dans l'ordre et garde les prompts reçus."""

    def __init__(self, *fiches):
        self.fiches = list(fiches)
        self.prompts: list[str] = []

    def try_complete_json(self, _modele, prompt, system=""):
        self.prompts.append(prompt)
        return _Essai(self.fiches.pop(0), _Reponse())


class FauxCompteur:
    def ajouter(self, *_args):
        pass


class TestSecondeChance(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.chemin = Path(tmp.name) / f"{ETALON}.yaml"
        shutil.copy(AIDES_DIR / f"{ETALON}.yaml", self.chemin)
        self.bonne = load_aide(self.chemin).fiche
        assert self.bonne is not None
        # Le défaut le plus fréquent mesuré : un point de règlement omis.
        premier = next(iter(self.bonne.points))
        self.incomplete = self.bonne.model_copy(
            update={"points": {k: v for k, v in self.bonne.points.items() if k != premier}}
        )
        self.premier = premier

    def _rediger(self, client):
        return rediger_fiches.rediger(
            self.chemin, client, "système", FauxCompteur(), date(2026, 10, 4)
        )

    def test_refus_puis_correction_ecrit_la_fiche(self):
        client = FauxClient(self.incomplete, self.bonne.model_copy())
        res = self._rediger(client)
        self.assertEqual(res.erreurs, [])
        self.assertEqual(len(client.prompts), 2)
        # Le second prompt renvoie le motif exact du refus.
        self.assertIn("REFUSÉE", client.prompts[1])
        self.assertIn(self.premier, client.prompts[1].split("Motifs du refus")[1])
        self.assertEqual(load_aide(self.chemin).fiche.redige_le, date(2026, 10, 4))

    def test_refus_repetes_n_ecrivent_rien(self):
        avant = self.chemin.read_text(encoding="utf-8")
        client = FauxClient(*[self.incomplete.model_copy() for _ in range(3)])
        res = self._rediger(client)
        self.assertTrue(any("conditions sans point" in e for e in res.erreurs))
        self.assertEqual(len(client.prompts), 1 + rediger_fiches.MAX_CORRECTIONS)
        self.assertEqual(self.chemin.read_text(encoding="utf-8"), avant)

    def test_le_prompt_liste_les_points_attendus(self):
        prompt = rediger_fiches.prompt_pour(self.chemin)
        for cond in load_aide(self.chemin).conditions:
            self.assertIn(cond.id, prompt.split("exactement une entrée par condition")[1])


if __name__ == "__main__":
    unittest.main()
