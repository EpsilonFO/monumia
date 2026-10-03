"""Tests du backfill des gates « Bénéficiaires » (scripts/proposer_gate_porteur.py).

Ce script écrit dans `data/aides/` sans relecture préalable quand une
proposition est NETTE : c'est exactement là qu'un test a de la valeur. Deux
propriétés le tiennent, et les deux sont vérifiées ici — la citation proposée se
retrouve dans le snapshot, et l'insertion textuelle laisse le fichier valide,
commentaires compris.

Aucun test ne lit le vrai `data/` : tout se joue dans un tmpdir.

Run from backend/:  uv run pytest tests/test_proposer_gate_porteur.py
"""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import proposer_gate_porteur as pgp  # noqa: E402
import veille_collect  # noqa: E402

from aides_schema import FactDef, load_aide  # noqa: E402

SNAPSHOT_ENTREPRISE = """\
---
url: https://example.org/pret
fetched_at: 2026-01-01T09:00:00+00:00
sha256: 0000000000000000000000000000000000000000000000000000000000000000
---

# Prêt de croissance

#### Pouvez-vous bénéficier de l'aide régionale ?

Vous pouvez bénéficier du prêt, si vous êtes :

  * Une TPE ou une PME dont les effectifs sont compris entre 3 et 50 salariés
  * Créée depuis plus de 3 ans

Et si votre projet concerne la création d'une entreprise nouvelle.

#### Comment demander l'aide régionale ?

Le dossier se dépose en ligne.
"""

SNAPSHOT_MIXTE = SNAPSHOT_ENTREPRISE.replace(
    "  * Une TPE ou une PME dont les effectifs sont compris entre 3 et 50 salariés",
    "  * Une TPE ou une PME, une commune ou un groupement de communes",
)

# Une fiche COMMENTÉE : 108 des 405 du catalogue le sont, et un `yaml.dump`
# effacerait ces commentaires sans que rien ne le signale.
AIDE_COMMENTEE = """\
slug: {slug}
nom: Prêt de croissance
organisme: Région d'exemple
categorie: region
type: pret
description: Une aide pour tester le backfill.
# Le périmètre a été arbitré le 2026-01-01 : voir data/reviews/.
conditions:
- id: effectif
  # Seuil lu dans le règlement, pas dans la page de présentation.
  text: L'entreprise compte entre 3 et 50 salariés.
  kind: user_fact
  effect: gate
  fact: effectif_salaries
  predicate:
    lte: 50
  quote: Une TPE ou une PME dont les effectifs sont compris entre 3 et 50 salariés
{conditions}tags:
- pret
"""

GATE_EXISTANT = """\
- id: beneficiaires-porteur
  text: Réservé aux entreprises.
  kind: user_fact
  effect: gate
  fact: statut_juridique_porteur
  predicate:
    in:
    - societe
"""


class BaseProposition(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name)
        self.aides_dir = racine / "aides"
        self.sources_dir = racine / "sources"
        self.aides_dir.mkdir()
        self.sources_dir.mkdir()
        for cible, attribut, valeur in (
            (veille_collect, "SOURCES_DIR", self.sources_dir),
            (pgp, "AIDES_DIR", self.aides_dir),
        ):
            patch = mock.patch.object(cible, attribut, valeur)
            patch.start()
            self.addCleanup(patch.stop)
        veille_collect.pdf_to_text.cache_clear()

    def ecrire(self, slug: str, snapshot: str, conditions: str = "") -> None:
        (self.aides_dir / f"{slug}.yaml").write_text(
            AIDE_COMMENTEE.format(slug=slug, conditions=conditions), encoding="utf-8"
        )
        dossier = self.sources_dir / slug
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "2026-01-01.md").write_text(snapshot, encoding="utf-8")

    def analyser(self, slug: str):
        documents, _illisibles, _provenance = veille_collect.load_baselines(slug)
        return pgp.analyser(load_aide(self.aides_dir / f"{slug}.yaml"), documents)

    def facts(self) -> dict[str, FactDef]:
        return {
            "statut_juridique_porteur": FactDef.model_validate(
                {
                    "type": "multi_enum",
                    "scope": "proprietaire",
                    "question": "Qui dépose ?",
                    "options": [
                        {"id": "societe", "label": "Société"},
                        {"id": "entreprise_individuelle", "label": "Entreprise individuelle"},
                        {"id": "public_commune", "label": "Commune"},
                    ],
                }
            ),
            "effectif_salaries": FactDef.model_validate(
                {
                    "type": "integer",
                    "scope": "proprietaire",
                    "question": "Combien de salariés ?",
                    "porteurs_concernes": ["societe", "entreprise_individuelle"],
                }
            ),
        }


class TestAnalyse(BaseProposition):
    def test_passage_entreprise_donne_une_proposition_nette(self):
        self.ecrire("pret-croissance", SNAPSHOT_ENTREPRISE)
        proposition = self.analyser("pret-croissance")
        self.assertTrue(proposition.net, proposition)
        self.assertEqual(proposition.options, ["societe", "entreprise_individuelle"])
        self.assertIn("TPE ou une PME", proposition.quote)

    def test_la_citation_se_retrouve_dans_le_snapshot(self):
        # La garantie qui porte tout le reste : `--appliquer` écrit sans
        # relecture, une citation inventée passerait au catalogue.
        self.ecrire("pret-croissance", SNAPSHOT_ENTREPRISE)
        proposition = self.analyser("pret-croissance")
        self.assertIn(proposition.quote, SNAPSHOT_ENTREPRISE)

    def test_un_porteur_public_dans_le_passage_rend_la_proposition_non_nette(self):
        self.ecrire("pret-croissance", SNAPSHOT_MIXTE)
        proposition = self.analyser("pret-croissance")
        self.assertFalse(proposition.net, proposition)
        self.assertEqual(proposition.autres, ["public_commune"])

    def test_la_citation_ne_sort_pas_de_l_enumeration_des_beneficiaires(self):
        # « Et si votre projet concerne la création d'une entreprise » est un
        # critère de PROJET : la citer désignerait un bénéficiaire que la source
        # ne nomme pas.
        self.ecrire("pret-croissance", SNAPSHOT_ENTREPRISE)
        proposition = self.analyser("pret-croissance")
        self.assertNotIn("votre projet concerne", proposition.quote)

    def test_sans_section_beneficiaires_rien_n_est_propose(self):
        self.ecrire(
            "pret-croissance", SNAPSHOT_ENTREPRISE.replace("Pouvez-vous bénéficier", "Objet")
        )
        proposition = self.analyser("pret-croissance")
        self.assertFalse(proposition.net)
        self.assertEqual(proposition.passage, "")


class TestApplication(BaseProposition):
    def appliquer(self, slug: str) -> bool:
        return pgp.appliquer(self.analyser(slug), jour=date(2026, 1, 1))

    def test_insertion_laisse_le_fichier_valide_et_commente(self):
        self.ecrire("pret-croissance", SNAPSHOT_ENTREPRISE)
        self.assertTrue(self.appliquer("pret-croissance"))
        texte = (self.aides_dir / "pret-croissance.yaml").read_text(encoding="utf-8")
        self.assertIn("# Le périmètre a été arbitré le 2026-01-01", texte)
        self.assertIn("# Seuil lu dans le règlement", texte)
        aide = load_aide(self.aides_dir / "pret-croissance.yaml")
        gate = next(c for c in aide.conditions if c.id == pgp.ID_CONDITION)
        self.assertEqual(gate.fact, "statut_juridique_porteur")
        self.assertEqual(gate.effect, "gate")
        self.assertEqual(gate.predicate.root, {"in": ["societe", "entreprise_individuelle"]})
        self.assertIn("proposer_gate_porteur.py", gate.notes or "")

    def test_la_condition_entre_dans_le_bloc_conditions(self):
        # Une insertion après `tags:` serait syntaxiquement valide et
        # sémantiquement fausse : le gate ne serait jamais évalué.
        self.ecrire("pret-croissance", SNAPSHOT_ENTREPRISE)
        self.appliquer("pret-croissance")
        texte = (self.aides_dir / "pret-croissance.yaml").read_text(encoding="utf-8")
        self.assertLess(texte.index(pgp.ID_CONDITION), texte.index("tags:"))

    def test_un_gate_porteur_deja_pose_n_est_pas_double(self):
        self.ecrire("pret-croissance", SNAPSHOT_ENTREPRISE, conditions=GATE_EXISTANT)
        aide = load_aide(self.aides_dir / "pret-croissance.yaml")
        self.assertTrue(pgp.gate_porteur(aide))
        # Le corpus l'exclut d'office : la règle du lint ne le sort pas en erreur.
        self.assertEqual(
            pgp.corpus({"pret-croissance": aide}, self.facts())[0],
            [],
        )


class TestCorpus(BaseProposition):
    def test_une_aide_muette_entre_dans_le_corpus(self):
        self.ecrire("pret-croissance", SNAPSHOT_ENTREPRISE)
        aide = load_aide(self.aides_dir / "pret-croissance.yaml")
        en_erreur, permissifs = pgp.corpus({"pret-croissance": aide}, self.facts())
        self.assertEqual(en_erreur, ["pret-croissance"])
        self.assertEqual(permissifs, [])

    def test_un_gate_porteur_qui_admet_une_commune_est_signale(self):
        permissif = GATE_EXISTANT.replace(
            "    - societe\n", "    - societe\n    - public_commune\n"
        )
        self.ecrire("pret-croissance", SNAPSHOT_ENTREPRISE, conditions=permissif)
        aide = load_aide(self.aides_dir / "pret-croissance.yaml")
        en_erreur, permissifs = pgp.corpus({"pret-croissance": aide}, self.facts())
        self.assertEqual(en_erreur, [])
        self.assertEqual(len(permissifs), 1, permissifs)
        self.assertEqual(permissifs[0].faits, ["effectif_salaries"])


if __name__ == "__main__":
    unittest.main()
