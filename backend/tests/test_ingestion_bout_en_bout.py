"""Une ingestion complète, de la commande au verdict — sans réseau ni modèle.

Le seul test qui exerce le CÂBLAGE : prompt système, prompt initial, treize
outils, boucle, vérificateur, post-contrôles, fiche de review et son en-tête.
Chaque pièce a ses propres tests ; celui-ci vérifie qu'elles se parlent.

Le modèle est rejoué (`fake_provider`), le réseau est simulé
(`httpx.MockTransport`), et tout s'écrit dans un tmpdir. Deux scénarios
suffisent à couvrir la décision : une ingestion propre qui aboutit, et une
ingestion qui pose un `manual_check` + `gate` sur une aide neuve — que le
ratchet refuse, et dont le YAML doit finir en `.yaml.echec`.

Run from backend/:  uv run pytest tests/test_ingestion_bout_en_bout.py
"""

import dataclasses
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import veille_collect  # noqa: E402
from ingestion.atelier import restaurer_sources  # noqa: E402
from ingestion.worker import ConfigIngestion, ContextePartage, ingerer_aide  # noqa: E402
from pipeline.etat import Tache  # noqa: E402
from pipeline.llm import Compteur  # noqa: E402
from pipeline.web import Fetcheur, reinitialiser_delais  # noqa: E402
from providall.testing import chat_reply, fake_provider, json_reply, tool_call  # noqa: E402

JOUR = date(2026, 9, 6)

PAGE = """\
<html><body>
<h1>Aide à la restauration du patrimoine rural</h1>
<p>La Région soutient la restauration des édifices non protégés présentant un
intérêt patrimonial. Le monument doit être ouvert au public au moins quarante
jours par an.</p>
<p>Le taux d'intervention est de 30 % des dépenses éligibles, dans la limite de
50 000 euros par opération.</p>
<p>Le dossier est déposé en ligne sur le portail régional avant le démarrage des
travaux. Les pièces demandées sont le devis détaillé, l'arrêté de protection le
cas échéant, et un plan de financement prévisionnel.</p>
</body></html>
"""

FACTS = """\
monument_ouvert_au_public:
  type: boolean
  scope: monument
  question: Le monument est-il ouvert au public ?
"""

REVIEW = "## Conditions\n\n" + ("Ligne de fiche de review destinée à l'humain. " * 30)

VERDICT_VERIFICATEUR = {
    "problemes": [],
    "axes_sans_probleme": ["condition_manquante", "quote_inexacte", "typage"],
    "qualite_source": "page_officielle",
    "commentaire": "Extraction fidèle à la page.",
}


def aide_yaml(conditions: str, snapshot: str) -> str:
    return f"""\
slug: ex-aide
nom: Aide à la restauration du patrimoine rural
nom_court: Restauration rurale (exemple)
organisme: Région d'exemple
categorie: region
type: subvention
# Le ressort du financeur : `check_portee_geographique` refuse une aide
# régionale qui ne le déclare pas, elle se proposerait dans toute la France.
hard_filters:
  regions:
  - grand-est
raison: [restauration_travaux]
familles: [restauration_bati]
description: Soutien à la restauration des édifices non protégés.
source:
  url_officielle: https://example.org/aide
  verified_at: '2026-09-06'
  snapshot: {snapshot}
financement:
  taux_max: 30
  montant_max: 50000
conditions:
{conditions}
"""


CONDITION_OK = """\
  - id: ouvert-au-public
    text: Le monument est ouvert au public au moins quarante jours par an.
    kind: user_fact
    effect: gate
    fact: monument_ouvert_au_public
    predicate: {eq: true}
    quote: ouvert au public au moins quarante jours par an
"""

CONDITION_GATE = """\
  - id: interet-patrimonial
    text: L'édifice présente un intérêt patrimonial.
    kind: manual_check
    effect: gate
    notes: La source ne définit pas ce qu'est un intérêt patrimonial.
    quote: présentant un intérêt patrimonial
"""

ENV = {
    "PROVIDALL_NO_DOTENV": "1",
    "LLM_MODEL_INGESTION": "ds-flash",
    "LLM_MODEL_VERIFICATION": "ds-pro",
    "DEEPSEEK_API_KEY": "faux",
}


class BaseBoutEnBout(unittest.TestCase):
    def setUp(self):
        reinitialiser_delais()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # `atelier_redirige` détourne une globale de PROCESSUS : sans ce
        # nettoyage, les tests suivants liraient un tmpdir effacé.
        self.addCleanup(restaurer_sources)
        self.racine = Path(self._tmp.name)
        self.facts = self.racine / "facts.yaml"
        self.facts.write_text(FACTS, encoding="utf-8")
        veille_collect.pdf_to_text.cache_clear()

        env = mock.patch.dict(os.environ, ENV, clear=False)
        env.start()
        self.addCleanup(env.stop)

        self.config = ConfigIngestion(
            sortie=self.racine / "sortie",
            jour=JOUR,
            journaliser=False,
            fetcheur=lambda: Fetcheur(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(200, text=PAGE, headers={"content-type": "text/html"})
                ),
                delai_s=0.0,
            ),
        )
        self.atelier = dataclasses.replace(
            self.config.atelier("ex-aide"),
            facts_path=self.facts,
            pending_path=self.racine / "pending.yaml",
        )
        (self.racine / "pending.yaml").write_text("", encoding="utf-8")
        # `ingerer_aide` reconstruit son atelier depuis la config : on lui fait
        # rendre le nôtre, ontologie de test comprise.
        atelier_patch = mock.patch.object(
            ConfigIngestion, "atelier", lambda _self, _slug: self.atelier
        )
        atelier_patch.start()
        self.addCleanup(atelier_patch.stop)

        self.contexte = ContextePartage.construire(self.atelier)
        self.tache = Tache(
            titre="Aide à la restauration du patrimoine rural",
            url="https://example.org/aide",
            territoire="hauts-de-france",
            statut="valide",
            ajoute_le=JOUR,
        )

    def scenario(self, conditions: str) -> list:
        """Les six tours d'une ingestion type, rejoués dans l'ordre."""
        snapshot = "data/sources/ex-aide/2026-09-06.md"
        return [
            chat_reply(
                tool_calls=[tool_call("snapshotter", {"url": "https://example.org/aide"}, id="c1")]
            ),
            chat_reply(
                tool_calls=[tool_call("lire_snapshot", {"chemin": "2026-09-06.md"}, id="c2")]
            ),
            chat_reply(
                tool_calls=[
                    tool_call(
                        "ecrire_aide", {"yaml_texte": aide_yaml(conditions, snapshot)}, id="c3"
                    )
                ]
            ),
            chat_reply(tool_calls=[tool_call("lint", {}, id="c4")]),
            chat_reply(tool_calls=[tool_call("verification_adversariale", {}, id="c5")]),
            chat_reply(tool_calls=[tool_call("ecrire_review", {"markdown": REVIEW}, id="c6")]),
            chat_reply("Ingestion terminée : 1 condition typée, citation vérifiée."),
        ]

    def ingerer(self, conditions: str, compteur: Compteur | None = None):
        # La réponse JSON du vérificateur est insérée là où il l'appelle : le
        # faux adaptateur rejoue les réponses dans l'ordre, tous rôles confondus.
        reponses = self.scenario(conditions)
        reponses.insert(5, json_reply(VERDICT_VERIFICATEUR))
        with fake_provider(*reponses):
            return ingerer_aide(
                "ex-aide",
                self.tache,
                self.config,
                contexte=self.contexte,
                compteur=compteur,
            )


class TestIngestionReussie(BaseBoutEnBout):
    def setUp(self):
        super().setUp()
        self.compteur = Compteur()
        self.resultat = self.ingerer(CONDITION_OK, self.compteur)

    def test_verdict_ok(self):
        self.assertTrue(self.resultat.ok, self.resultat.motif_echec)
        self.assertEqual(self.resultat.arret, "termine")
        self.assertIsNone(self.resultat.motif_echec)

    def test_les_quatre_livrables_existent(self):
        self.assertTrue(self.atelier.yaml_path.exists())
        self.assertTrue(self.atelier.review_path.exists())
        self.assertTrue(self.atelier.snapshots())
        self.assertFalse(self.atelier.yaml_echec_path.exists())

    def test_le_yaml_est_chargeable_et_lintable(self):
        from lint_aides_data import lint

        from aides_schema import load_aide

        aide = load_aide(self.atelier.yaml_path)
        self.assertEqual(aide.slug, "ex-aide")
        rapport = lint(
            ["ex-aide"],
            quotes=True,
            aides_dir=self.atelier.aides_dir,
            facts_path=self.facts,
            pending_path=self.atelier.pending_path,
        )
        self.assertTrue(rapport.ok, rapport.texte())

    def test_lentete_de_review_dit_ce_quil_faut_relire(self):
        contenu = self.atelier.review_path.read_text(encoding="utf-8")
        self.assertIn("<!--", contenu)
        self.assertIn("2026-09-06", contenu)
        self.assertIn("À RELIRE", contenu)
        self.assertIn("2026-09-06.md", contenu)
        self.assertIn("## Conditions", contenu)

    def test_la_verification_a_bien_tourne(self):
        self.assertEqual(self.resultat.bloquants, 0)

    def test_le_compteur_global_a_recu_le_cumul(self):
        self.assertGreater(self.compteur.appels, 0)
        self.assertIn("aide:ex-aide", self.compteur.par_etiquette())


class TestIngestionRefusee(BaseBoutEnBout):
    def test_manual_check_gate_sur_aide_neuve_refuse(self):
        resultat = self.ingerer(CONDITION_GATE)
        self.assertFalse(resultat.ok)
        assert resultat.motif_echec is not None
        self.assertIn("lint rouge", resultat.motif_echec)
        self.assertIn("manual_check gate", resultat.motif_echec)

    def test_le_yaml_refuse_sort_du_catalogue_mais_reste_lisible(self):
        self.ingerer(CONDITION_GATE)
        self.assertFalse(self.atelier.yaml_path.exists())
        self.assertEqual(list(self.atelier.aides_dir.glob("*.yaml")), [])
        echec = self.atelier.yaml_echec_path
        self.assertTrue(echec.exists())
        self.assertIn("interet-patrimonial", echec.read_text(encoding="utf-8"))

    def test_les_preuves_restent(self):
        self.ingerer(CONDITION_GATE)
        self.assertTrue(self.atelier.snapshots())
        self.assertTrue(self.atelier.review_path.exists())


if __name__ == "__main__":
    unittest.main()
