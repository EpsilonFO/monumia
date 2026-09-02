"""Tests du harnais de benchmark de l'audit (scripts/veille_benchmark_audit.py).

Le modèle n'est jamais appelé : on vérifie que les cas de référence se chargent,
que le retrait d'une condition produit une fiche valide amputée de la seule
condition visée, et que la notation reconnaît un retrait retrouvé.

Run from backend/:  uv run pytest tests/test_veille_benchmark_audit.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import yaml  # noqa: E402
from veille_audit import AuditLLMOutput, Corpus, CritereAudit, DocAudit  # noqa: E402
from veille_benchmark_audit import (  # noqa: E402
    Cas,
    Gold,
    Score,
    charger_golds,
    noter,
    preparer,
    recoupe,
)

from aides_schema import AIDES_DIR, Aide  # noqa: E402

SOURCE = (
    "Les édifices antérieurs à 1800 sont éligibles. Le propriétaire doit s'engager à "
    "ouvrir l'édifice au public quinze jours par an. Les travaux ne doivent pas avoir "
    "commencé à la date du dépôt du dossier."
)


def corpus() -> Corpus:
    return Corpus(docs=[DocAudit(nom="src", contenu=SOURCE, kind="text", provenance="baseline")])


class TestGolds(unittest.TestCase):
    def test_les_golds_du_depot_se_preparent_hors_ligne(self):
        golds = charger_golds()
        self.assertGreaterEqual(len(golds), 4)
        for gold in golds:
            cas = preparer(gold)
            self.assertFalse(cas.corpus.vide, gold.id)
            # La fiche soumise est valide et, en retrait, amputée de la SEULE
            # condition visée.
            Aide.model_validate(yaml.safe_load(cas.texte_fiche))
            originale = yaml.safe_load((AIDES_DIR / f"{gold.slug}.yaml").read_text("utf-8"))
            ids = {c["id"] for c in originale["conditions"]}
            restants = {c.id for c in cas.aide.conditions}
            if gold.retrait:
                self.assertEqual(ids - restants, {gold.condition}, gold.id)
                assert cas.retiree is not None
                self.assertEqual(cas.retiree["id"], gold.condition)
            else:
                self.assertEqual(ids, restants, gold.id)

    def test_un_type_inconnu_est_refuse(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump([{"id": "x", "slug": "y", "type": "bizarre"}], f)
        with self.assertRaises(SystemExit):
            charger_golds(Path(f.name))


class TestRecoupement(unittest.TestCase):
    def test_inclusion(self):
        self.assertTrue(
            recoupe(
                "ouvrir l'édifice au public quinze jours par an",
                "s'engager à ouvrir l'édifice au public quinze jours par an.",
                corpus(),
            )
        )

    def test_voisinage_dans_le_meme_document(self):
        self.assertTrue(
            recoupe("antérieurs à 1800 sont éligibles", "ouvrir l'édifice au public", corpus())
        )

    def test_passages_eloignes_ou_absents(self):
        loin = Corpus(
            docs=[
                DocAudit(
                    nom="src",
                    contenu="Alpha. " + "x " * 600 + "Omega.",
                    kind="text",
                    provenance="baseline",
                )
            ]
        )
        self.assertFalse(recoupe("Alpha.", "Omega.", loin))
        self.assertFalse(recoupe("Alpha.", "inexistant", loin))


class TestNotation(unittest.TestCase):
    def _cas(self, retiree: dict | None) -> Cas:
        aide = Aide.model_validate(
            {
                "slug": "aide-test",
                "nom": "Aide",
                "organisme": "Org",
                "categorie": "region",
                "type": "subvention",
                "description": "d",
                "source": {},
            }
        )
        return Cas(
            gold=Gold(id="g", slug="aide-test", type="retrait" if retiree else "intacte"),
            aide=aide,
            texte_fiche="",
            corpus=corpus(),
            retiree=retiree,
        )

    def test_retrait_retrouve_sans_faux(self):
        out = AuditLLMOutput(
            criteres=[
                CritereAudit(
                    quote="Les travaux ne doivent pas avoir commencé",
                    verdict="absent",
                    id="travaux",
                    text="t",
                )
            ]
        )
        score = Score(gold="g", modele="m", json_ok=True)
        noter(
            self._cas({"id": "c", "quote": "ne doivent pas avoir commencé à la date du dépôt"}),
            out,
            score,
        )
        self.assertTrue(score.retrouvee)
        self.assertEqual(score.faux, [])
        self.assertTrue(score.reussi)

    def test_intacte_compte_chaque_proposition_comme_faux(self):
        out = AuditLLMOutput(
            criteres=[
                CritereAudit(quote="Les édifices antérieurs", verdict="absent", id="a", text="t"),
                CritereAudit(
                    quote="quinze jours", verdict="divergent", cond_id="c", commentaire="x"
                ),
            ]
        )
        score = Score(gold="g", modele="m", json_ok=True)
        noter(self._cas(None), out, score)
        self.assertEqual(score.faux, ["+a", "~c"])
        self.assertIsNone(score.retrouvee)
        self.assertFalse(score.reussi)

    def test_fiche_incomplete_est_une_fausse_alerte(self):
        out = AuditLLMOutput(fiche_incomplete=True, raison_fiche_incomplete="?")
        score = Score(gold="g", modele="m", json_ok=True)
        noter(self._cas(None), out, score)
        self.assertEqual(score.faux, ["fiche_incomplete"])
