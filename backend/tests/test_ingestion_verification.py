"""Tests de la vérification adversariale (scripts/ingestion/verification.py).

Trois propriétés à tenir :
  - la consigne vient du SKILL, pas d'une copie dans le code (sinon les deux
    divergent et la vérification par API cesse d'être celle du skill) ;
  - le vérificateur reçoit l'audit DÉTERMINISTE des citations comme un fait
    établi, et non l'instruction de le refaire lui-même ;
  - une panne du vérificateur ne bloque jamais : elle produit un problème
    MINEUR qui dit qu'il faudra relire à la main.

Run from backend/:  uv run pytest tests/test_ingestion_verification.py
"""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import providall  # noqa: E402
import veille_collect  # noqa: E402
from ingestion.atelier import atelier_redirige, restaurer_sources  # noqa: E402
from ingestion.contexte import SKILL_PATH  # noqa: E402
from ingestion.verification import (  # noqa: E402
    Probleme,
    RapportVerification,
    construire_prompt,
    prompt_verificateur,
    rendre,
    verifier,
)
from providall.testing import chat_reply, fake_provider, json_reply  # noqa: E402

from aides_schema import Aide  # noqa: E402

JOUR = date(2026, 9, 6)

SNAPSHOT = """\
---
url: https://example.org/aide
fetched_at: 2026-09-06T09:00:00+00:00
sha256: 0000000000000000000000000000000000000000000000000000000000000000
---

# Aide d'exemple

Le taux d'intervention est de 30 % des dépenses éligibles.
"""

AIDE = """\
slug: ex-aide
nom: Aide d'exemple
organisme: Région d'exemple
categorie: region
type: subvention
description: Une aide pour tester la vérification.
conditions:
  - id: taux
    text: Le taux d'intervention est de 30 %.
    kind: info
    quote: Le taux d'intervention est de 30 % des dépenses éligibles.
  - id: taux-faux
    text: Le taux est porté à 80 % pour les monuments classés.
    kind: info
    quote: le taux est porté à 80 % pour les monuments classés
"""

REPONSE = {
    "problemes": [
        {
            "axe": "condition_sans_fondement",
            "severite": "bloquant",
            "condition_id": "taux-faux",
            "citation_source": "Le taux d'intervention est de 30 % des dépenses éligibles.",
            "description": "La source ne mentionne aucun taux de 80 %.",
            "correction_proposee": "Supprimer la condition taux-faux.",
        }
    ],
    "axes_sans_probleme": ["quote_inexacte", "typage"],
    "qualite_source": "page_officielle",
    "commentaire": "Extraction globalement fidèle.",
}


def client() -> providall.Client:
    return providall.Client("ds-pro", api_key="faux", retry=providall.RetryPolicy(retries=0))


class BaseVerification(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # `atelier_redirige` détourne une globale de PROCESSUS : sans ce
        # nettoyage, les tests suivants liraient un tmpdir effacé.
        self.addCleanup(restaurer_sources)
        racine = Path(self._tmp.name)
        self.atelier = atelier_redirige("ex-aide", racine, jour=JOUR)
        veille_collect.pdf_to_text.cache_clear()
        (self.atelier.dossier_sources / "2026-09-06.md").write_text(SNAPSHOT, encoding="utf-8")
        self.atelier.yaml_path.write_text(AIDE, encoding="utf-8")
        self.aide = Aide.model_validate(__import__("yaml").safe_load(AIDE))


class TestConsigne(unittest.TestCase):
    def test_extraite_du_skill(self):
        consigne = prompt_verificateur(SKILL_PATH.read_text(encoding="utf-8"))
        self.assertIn("vérificateur adversarial", consigne)
        self.assertIn("RÉFUTER", consigne)
        # Les chevrons du bloc de citation ont bien été retirés.
        self.assertFalse(any(li.startswith(">") for li in consigne.splitlines()))

    def test_absence_de_bloc_leve(self):
        with self.assertRaises(KeyError):
            prompt_verificateur("## Étape 4 — Vérification\n\nPas de citation ici.\n")


class TestPrompt(BaseVerification):
    def setUp(self):
        super().setUp()
        self.prompt = construire_prompt(
            self.aide, self.atelier, skill_md=SKILL_PATH.read_text(encoding="utf-8")
        )

    def test_contient_le_yaml_et_la_source(self):
        self.assertIn("slug: ex-aide", self.prompt)
        self.assertIn("Le taux d'intervention est de 30 %", self.prompt)

    def test_audit_des_quotes_fourni_comme_fait_etabli(self):
        self.assertIn("AUDIT DES CITATIONS", self.prompt)
        self.assertIn("ne le recalcule pas", self.prompt)
        self.assertIn("INTROUVABLES : 1", self.prompt)
        self.assertIn("taux-faux", self.prompt)

    def test_contient_le_condense_de_schema(self):
        self.assertIn("Schéma exact", self.prompt)

    def test_dit_quil_ny_a_pas_doutil(self):
        self.assertIn("ni outil ni accès au système de fichiers", self.prompt)

    def test_troncature_des_documents(self):
        court = construire_prompt(
            self.aide,
            self.atelier,
            skill_md=SKILL_PATH.read_text(encoding="utf-8"),
            max_car_par_doc=40,
        )
        self.assertIn("document tronqué", court)


class TestVerifier(BaseVerification):
    def test_rapport_nominal(self):
        with fake_provider(json_reply(REPONSE)):
            rapport, rendu = verifier(self.atelier, client(), aide=self.aide)
        self.assertEqual(len(rapport.problemes), 1)
        self.assertEqual(len(rapport.bloquants), 1)
        self.assertIn("taux-faux", rendu)
        self.assertIn("BLOQUANT", rendu)
        self.assertIn("Supprimer la condition", rendu)

    def test_le_verificateur_ne_voit_pas_lhistorique(self):
        """Un seul message utilisateur : ni conversation, ni raisonnement transmis."""
        with fake_provider(json_reply(REPONSE)) as faux:
            verifier(self.atelier, client(), aide=self.aide)
        corps = faux.bodies[0]
        roles = [m["role"] for m in corps["messages"]]
        self.assertNotIn("assistant", roles)
        self.assertEqual(roles.count("user"), 1)

    def test_panne_donne_un_probleme_mineur_non_bloquant(self):
        with fake_provider(chat_reply("ceci n'est pas du JSON")):
            rapport, rendu = verifier(self.atelier, client(), aide=self.aide)
        self.assertEqual(rapport.bloquants, [])
        self.assertEqual(len(rapport.problemes), 1)
        self.assertEqual(rapport.problemes[0].severite, "mineur")
        self.assertIn("indisponible", rendu)

    def test_le_compteur_est_alimente(self):
        from pipeline.llm import Compteur

        compteur = Compteur()
        with fake_provider(json_reply(REPONSE)):
            verifier(self.atelier, client(), aide=self.aide, compteur=compteur)
        self.assertGreaterEqual(compteur.appels, 1)
        self.assertIn("verification", compteur.par_etiquette())


class TestRendu(unittest.TestCase):
    def test_aucun_probleme(self):
        self.assertIn("aucun problème", rendre(RapportVerification()))

    def test_axes_sans_probleme_listes(self):
        rapport = RapportVerification(axes_sans_probleme=["typage", "quote_inexacte"])
        self.assertIn("Axes contrôlés sans rien trouver : typage, quote_inexacte", rendre(rapport))

    def test_rappelle_que_le_verificateur_peut_avoir_tort(self):
        rapport = RapportVerification(
            problemes=[
                Probleme(
                    axe="typage",
                    severite="bloquant",
                    description="x",
                    correction_proposee="y",
                )
            ]
        )
        self.assertIn("désaccord", rendre(rapport))


if __name__ == "__main__":
    unittest.main()
