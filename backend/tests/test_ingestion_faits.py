"""Tests de la proposition de faits (scripts/ingestion/faits.py).

Le fichier `facts_pending.yaml` a déjà été détruit une fois par deux ingestions
parallèles (2026-09-04, quatre faits perdus). Les tests ci-dessous fixent les
trois propriétés qui l'empêchent de se reproduire : une collision est refusée,
une écriture refusée laisse le fichier strictement intact, et le fait ajouté
est immédiatement visible du lint lancé dans le même processus.

Run from backend/:  uv run pytest tests/test_ingestion_faits.py
"""

import dataclasses
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ingestion import faits  # noqa: E402
from ingestion.atelier import atelier_redirige, restaurer_sources  # noqa: E402

from aides_schema import FactDef, load_pending_facts  # noqa: E402

JOUR = date(2026, 9, 6)

FACTS = {
    "monument_ouvert_au_public": FactDef(
        type="boolean", scope="monument", question="Le monument est-il ouvert au public ?"
    ),
    "accord_abf": FactDef(
        type="enum",
        scope="projet",
        question="Avez-vous l'accord de l'Architecte des Bâtiments de France (ABF) ?",
        options=[
            {"id": "obtenu", "label": "Obtenu"},  # type: ignore[list-item]
            {"id": "en_cours", "label": "En cours"},  # type: ignore[list-item]
        ],
    ),
}

DEFINITION = """\
type: boolean
scope: monument
question: Le jardin est-il labellisé « Jardin remarquable » ?
help: Label délivré par le ministère de la Culture pour cinq ans.
"""

JUSTIFICATION = (
    "Aucun fait existant ne porte le label « Jardin remarquable » : "
    "`monument_ouvert_au_public` ne dit rien du label, et `accord_abf` relève de "
    "l'autorisation de travaux, pas d'une distinction. Le règlement en fait un "
    "critère de bonification explicite."
)


class BaseFaits(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # `atelier_redirige` détourne une globale de PROCESSUS : sans ce
        # nettoyage, les tests suivants liraient un tmpdir effacé.
        self.addCleanup(restaurer_sources)
        self.racine = Path(self._tmp.name)
        self.pending_path = self.racine / "facts_pending.yaml"
        self.pending_path.write_text("", encoding="utf-8")
        self.atelier = dataclasses.replace(
            atelier_redirige("ex-aide", self.racine, jour=JOUR),
            pending_path=self.pending_path,
        )
        load_pending_facts.cache_clear()

    def proposer(self, fact_id="jardin_remarquable", definition=DEFINITION, justif=JUSTIFICATION):
        return faits.proposer(self.atelier, FACTS, fact_id, definition, justif)


class TestRecherche(unittest.TestCase):
    def test_mord_sur_lid_la_question_et_les_options(self):
        self.assertIn("accord_abf", faits.rechercher(FACTS, {}, "architecte bâtiments"))
        self.assertIn("accord_abf", faits.rechercher(FACTS, {}, "en_cours"))
        self.assertIn("monument_ouvert_au_public", faits.rechercher(FACTS, {}, "ouvert public"))

    def test_classe_par_nombre_de_mots_retrouves(self):
        sortie = faits.rechercher(FACTS, {}, "public monument ouvert")
        self.assertLess(
            sortie.index("monument_ouvert_au_public"),
            sortie.index("accord_abf") if "accord_abf" in sortie else len(sortie),
        )

    def test_scope_filtre(self):
        self.assertIn("Aucun fait", faits.rechercher(FACTS, {}, "architecte", scope="monument"))

    def test_faits_en_attente_marques(self):
        pending = {
            "jardin_remarquable": FactDef(
                type="boolean", scope="monument", question="Jardin remarquable ?"
            )
        }
        self.assertIn("⏳", faits.rechercher(FACTS, pending, "jardin remarquable"))

    def test_sans_resultat_oriente_vers_la_proposition(self):
        self.assertIn("proposer_fait", faits.rechercher(FACTS, {}, "zorglub"))


class TestDetail(unittest.TestCase):
    def test_rend_le_yaml_du_fait(self):
        sortie = faits.detail(FACTS, {}, "accord_abf")
        self.assertIn("enum", sortie)
        self.assertIn("obtenu", sortie)

    def test_fait_inconnu(self):
        self.assertIn("Fait inconnu", faits.detail(FACTS, {}, "zorglub"))


class TestProposition(BaseFaits):
    def test_ajout_nominal(self):
        sortie = self.proposer()
        self.assertNotIn("ERREUR", sortie)
        contenu = self.pending_path.read_text(encoding="utf-8")
        self.assertIn("# --- ex-aide ---", contenu)
        self.assertIn("Proposé par ingerer.py ex-aide (2026-09-06)", contenu)
        self.assertIn("Jardin remarquable", contenu)
        brut = yaml.safe_load(contenu)
        self.assertEqual(set(brut), {"jardin_remarquable"})

    def test_le_fait_est_visible_immediatement(self):
        """Le lint tourne dans le MÊME processus : le cache doit avoir été purgé."""
        self.proposer()
        self.assertIn("jardin_remarquable", load_pending_facts(self.pending_path))

    def test_collision_avec_facts_yaml_refusee(self):
        sortie = self.proposer(fact_id="monument_ouvert_au_public")
        self.assertIn("ERREUR", sortie)
        self.assertIn("existe déjà", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), "")

    def test_collision_avec_un_fait_deja_propose_refusee(self):
        self.proposer()
        avant = self.pending_path.read_text(encoding="utf-8")
        sortie = self.proposer()
        self.assertIn("ERREUR", sortie)
        self.assertIn("déjà proposé", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), avant)

    def test_identifiant_invalide_refuse(self):
        for mauvais in ("JardinRemarquable", "jardin-remarquable", "jardin remarquable", ""):
            self.assertIn("ERREUR", self.proposer(fact_id=mauvais), mauvais)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), "")

    def test_justification_trop_courte_refusee(self):
        sortie = self.proposer(justif="parce que")
        self.assertIn("ERREUR", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), "")

    def test_definition_invalide_refusee(self):
        sortie = self.proposer(definition="type: couleur\nscope: monument\nquestion: x ?\n")
        self.assertIn("ERREUR", sortie)
        self.assertEqual(self.pending_path.read_text(encoding="utf-8"), "")

    def test_enum_sans_options_refuse(self):
        sortie = self.proposer(definition="type: enum\nscope: monument\nquestion: Laquelle ?\n")
        self.assertIn("ERREUR", sortie)

    def test_definition_enveloppee_dans_son_id_acceptee(self):
        """Les modèles envoient tantôt la définition nue, tantôt `{id: …}`."""
        enveloppee = "jardin_remarquable:\n" + "\n".join(
            f"  {li}" for li in DEFINITION.strip().splitlines()
        )
        self.assertNotIn("ERREUR", self.proposer(definition=enveloppee))
        self.assertIn("jardin_remarquable", load_pending_facts(self.pending_path))

    def test_deux_faits_saccumulent(self):
        self.proposer()
        self.proposer(
            fact_id="jardin_labellise_ens",
            definition="type: boolean\nscope: monument\nquestion: Espace naturel sensible ?\n",
        )
        self.assertEqual(
            set(load_pending_facts(self.pending_path)),
            {"jardin_remarquable", "jardin_labellise_ens"},
        )


if __name__ == "__main__":
    unittest.main()
