"""Tests du linter des données d'aides (scripts/lint_aides_data.py).

Le linter n'avait aucun test : il est pourtant le seul garde-fou automatique
entre une extraction et le catalogue, et le mode mono-slug en fait le contrat
que l'agent d'ingestion doit satisfaire avant de rendre la main. Ce qui est
vérifié ici est cette asymétrie assumée — la même citation introuvable est une
ERREUR sur une aide qu'on vient d'écrire et une INFORMATION sur le catalogue
entier, où elle est une dette héritée que personne ne vient de commettre.

Aucun test ne lit le vrai `data/` : tout se joue dans un tmpdir.

Run from backend/:  uv run pytest tests/test_lint_aides_data.py
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import lint_aides_data  # noqa: E402
import veille_collect  # noqa: E402
from lint_aides_data import lint, main  # noqa: E402

FACTS = """\
monument_ouvert_au_public:
  type: boolean
  scope: monument
  question: Le monument est-il ouvert au public ?
gratuite_acces:
  type: boolean
  scope: projet
  question: L'accès sera-t-il gratuit ?
surface_jardin_m2:
  type: integer
  scope: monument
  question: Quelle est la surface du jardin ?
  unit: m²
"""

SOURCE = """\
---
url: https://example.org/aide
fetched_at: 2026-01-01T09:00:00+00:00
sha256: 0000000000000000000000000000000000000000000000000000000000000000
---

# Jardins en scène

La programmation doit se dérouler dans un parc ou un jardin ouvert au public,
et l'accès du public aux représentations est gratuit pendant toute la durée de
la manifestation soutenue par la Région.
"""


def aide_yaml(slug: str, conditions: str = "") -> str:
    return f"""\
slug: {slug}
nom: Aide d'exemple
organisme: Région d'exemple
categorie: region
type: subvention
description: Une aide pour tester le linter.
conditions:
{conditions or "  []"}
"""


COND_OK = """\
  - id: ouvert-au-public
    text: La programmation se déroule dans un jardin ouvert au public.
    kind: user_fact
    effect: gate
    fact: monument_ouvert_au_public
    predicate: {eq: true}
    quote: doit se dérouler dans un parc ou un jardin ouvert au public
"""


class BaseLint(unittest.TestCase):
    """Monte un `data/` factice et y branche le linter."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.aides_dir = self.racine / "aides"
        self.sources_dir = self.racine / "sources"
        self.aides_dir.mkdir()
        self.sources_dir.mkdir()
        self.facts = self.racine / "facts.yaml"
        self.facts.write_text(FACTS, encoding="utf-8")
        self.pending = self.racine / "facts_pending.yaml"
        self.baseline = self.racine / "manual_check_baseline.json"
        self.baseline.write_text("{}\n", encoding="utf-8")
        # `load_baselines` lit SOURCES_DIR au moment de l'appel : le patch de
        # l'attribut de module suffit, il n'y a pas de copie à intercepter.
        patch = mock.patch.object(veille_collect, "SOURCES_DIR", self.sources_dir)
        patch.start()
        self.addCleanup(patch.stop)
        # `pdf_to_text` est mis en cache par chemin : deux tmpdir successifs
        # peuvent tomber sur le même chemin et se voler leur résultat.
        veille_collect.pdf_to_text.cache_clear()

    def ecrire_aide(self, slug: str, conditions: str = COND_OK) -> None:
        (self.aides_dir / f"{slug}.yaml").write_text(aide_yaml(slug, conditions), encoding="utf-8")

    def ecrire_snapshot(self, slug: str, contenu: str = SOURCE) -> None:
        dossier = self.sources_dir / slug
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "2026-01-01.md").write_text(contenu, encoding="utf-8")

    def lint(self, *slugs: str, **kw):
        return lint(
            slugs,
            aides_dir=self.aides_dir,
            facts_path=self.facts,
            pending_path=self.pending,
            baseline_path=self.baseline,
            **kw,
        )


class TestMonoSlug(BaseLint):
    def test_aide_valide_sort_verte(self):
        self.ecrire_aide("ex-aide")
        self.ecrire_snapshot("ex-aide")
        rapport = self.lint("ex-aide", quotes=True)
        self.assertTrue(rapport.ok, rapport.texte())
        self.assertEqual(rapport.quotes_absentes, [])
        self.assertEqual([a.slug for a in rapport.aides], ["ex-aide"])

    def test_aucune_statistique_globale(self):
        self.ecrire_aide("ex-aide")
        self.ecrire_snapshot("ex-aide")
        texte = self.lint("ex-aide").texte()
        self.assertNotIn("faits non référencés", texte)
        self.assertNotIn("dans l'ontologie", texte)

    def test_fichier_absent_est_une_erreur(self):
        rapport = self.lint("ex-inexistante")
        self.assertFalse(rapport.ok)
        self.assertIn("fichier absent", rapport.texte())

    def test_fait_inconnu_est_une_erreur(self):
        self.ecrire_aide(
            "ex-aide",
            """\
  - id: fait-fantome
    text: Une exigence quelconque.
    kind: user_fact
    effect: gate
    fact: fait_qui_nexiste_pas
    predicate: {eq: true}
""",
        )
        rapport = self.lint("ex-aide")
        self.assertFalse(rapport.ok)
        self.assertIn("fait inconnu", rapport.texte())

    def test_champ_hors_registre_est_une_erreur(self):
        self.ecrire_aide(
            "ex-aide",
            """\
  - id: champ-fantome
    text: Une exigence quelconque.
    kind: auto
    effect: gate
    field: monument.protecion
    predicate: {eq: classe}
""",
        )
        self.assertFalse(self.lint("ex-aide").ok)


class TestRatchet(BaseLint):
    GATE = """\
  - id: irreductible
    text: Le dossier est apprécié au regard des priorités régionales.
    kind: manual_check
    effect: gate
    notes: Rien dans la source ne permet de trancher.
"""

    def test_manual_check_gate_sur_aide_neuve_refuse(self):
        self.ecrire_aide("ex-aide", self.GATE)
        rapport = self.lint("ex-aide")
        self.assertFalse(rapport.ok)
        self.assertIn("manual_check gate (plafond 0)", rapport.texte())

    def test_gate_autorise_par_le_baseline(self):
        self.baseline.write_text(json.dumps({"ex-aide": {"gates": 1, "sans_notes": 0}}))
        self.ecrire_aide("ex-aide", self.GATE)
        self.assertTrue(self.lint("ex-aide").ok)

    def test_manual_check_sans_notes_refuse(self):
        self.ecrire_aide(
            "ex-aide",
            """\
  - id: irreductible
    text: Le dossier est apprécié au regard des priorités régionales.
    kind: manual_check
    effect: info
""",
        )
        rapport = self.lint("ex-aide")
        self.assertFalse(rapport.ok)
        self.assertIn("sans notes", rapport.texte())


class TestQuotes(BaseLint):
    INVENTEE = """\
  - id: quote-inventee
    text: Le taux est de 80 %.
    kind: manual_check
    effect: info
    notes: Chiffre annoncé par le financeur.
    quote: le taux d'intervention est porté à 80 % des dépenses éligibles
"""

    def test_quote_absente_est_une_erreur_en_mono_slug(self):
        self.ecrire_aide("ex-aide", self.INVENTEE)
        self.ecrire_snapshot("ex-aide")
        rapport = self.lint("ex-aide", quotes=True)
        self.assertFalse(rapport.ok)
        self.assertIn("quote introuvable", rapport.texte())
        self.assertEqual(len(rapport.quotes_absentes), 1)

    def test_quote_absente_reste_informative_en_global(self):
        self.ecrire_aide("ex-aide", self.INVENTEE)
        self.ecrire_snapshot("ex-aide")
        rapport = self.lint(quotes=True)
        self.assertTrue(rapport.ok, rapport.texte())
        self.assertEqual(len(rapport.quotes_absentes), 1)
        self.assertIn("1 introuvable(s)", rapport.texte())

    def test_sans_quotes_la_citation_nest_pas_verifiee(self):
        self.ecrire_aide("ex-aide", self.INVENTEE)
        self.ecrire_snapshot("ex-aide")
        self.assertTrue(self.lint("ex-aide").ok)

    def test_quote_elidee_est_degradee_non_bloquante(self):
        self.ecrire_aide(
            "ex-aide",
            """\
  - id: acces-gratuit
    text: L'accès du public est gratuit.
    kind: user_fact
    effect: gate
    fact: gratuite_acces
    predicate: {eq: true}
    quote: l'accès du public aux représentations est gratuit [...] soutenue par la Région
""",
        )
        self.ecrire_snapshot("ex-aide")
        rapport = self.lint("ex-aide", quotes=True)
        self.assertTrue(rapport.ok, rapport.texte())
        self.assertEqual(len(rapport.quotes_degradees), 1)

    def test_aide_citante_sans_snapshot_est_une_erreur(self):
        self.ecrire_aide("ex-aide")
        rapport = self.lint("ex-aide", quotes=True)
        self.assertFalse(rapport.ok)
        self.assertIn("aucun snapshot exploitable", rapport.texte())

    def test_aide_sans_citation_ni_snapshot_reste_verte(self):
        self.ecrire_aide(
            "ex-aide",
            """\
  - id: modalite
    text: Le dépôt se fait en ligne.
    kind: info
""",
        )
        self.assertTrue(self.lint("ex-aide", quotes=True).ok)


class TestFaitsEnAttente(BaseLint):
    def test_pending_utilisable_mais_signale(self):
        self.pending.write_text(
            "jardin_remarquable:\n  type: boolean\n  scope: monument\n"
            "  question: Le jardin est-il labellisé remarquable ?\n",
            encoding="utf-8",
        )
        self.ecrire_aide(
            "ex-aide",
            """\
  - id: label-jardin
    text: Le jardin est labellisé « Jardin remarquable ».
    kind: user_fact
    effect: modulateur
    fact: jardin_remarquable
    predicate: {eq: true}
""",
        )
        rapport = self.lint("ex-aide")
        self.assertTrue(rapport.ok, rapport.texte())
        self.assertIn("faits en attente d'approbation", rapport.texte())
        self.assertFalse(self.lint("ex-aide", strict=True).ok)

    def test_collision_avec_facts_yaml_refusee(self):
        self.pending.write_text(
            "gratuite_acces:\n  type: boolean\n  scope: projet\n  question: Doublon ?\n",
            encoding="utf-8",
        )
        self.ecrire_aide("ex-aide")
        self.ecrire_snapshot("ex-aide")
        rapport = self.lint("ex-aide")
        self.assertFalse(rapport.ok)
        self.assertIn("déjà dans facts.yaml", rapport.texte())

    def test_cache_vide_a_chaque_appel(self):
        """Un fait proposé entre deux lints du même processus doit être vu.

        C'est le cas de l'agent d'ingestion : il appelle `proposer_fait` puis
        `lint()` dans la foulée, et un `@cache` non purgé lui ferait refuser sa
        propre proposition.
        """
        self.ecrire_aide(
            "ex-aide",
            """\
  - id: label-jardin
    text: Le jardin est labellisé « Jardin remarquable ».
    kind: user_fact
    effect: modulateur
    fact: jardin_remarquable
    predicate: {eq: true}
""",
        )
        self.assertFalse(self.lint("ex-aide").ok)
        self.pending.write_text(
            "jardin_remarquable:\n  type: boolean\n  scope: monument\n"
            "  question: Le jardin est-il labellisé remarquable ?\n",
            encoding="utf-8",
        )
        self.assertTrue(self.lint("ex-aide").ok)


class TestCLI(BaseLint):
    def test_update_baseline_avec_slug_refuse(self):
        self.assertEqual(main(["ex-aide", "--update-baseline"]), 2)

    def test_update_baseline_reecrit_le_fichier(self):
        self.ecrire_aide("ex-aide", TestRatchet.GATE)
        with (
            mock.patch.object(lint_aides_data, "AIDES_DIR", self.aides_dir),
            mock.patch.object(lint_aides_data, "FACTS_FILE", self.facts),
            mock.patch.object(lint_aides_data, "FACTS_PENDING_FILE", self.pending),
            mock.patch.object(lint_aides_data, "BASELINE_FILE", self.baseline),
        ):
            self.assertEqual(main(["--update-baseline"]), 0)
        self.assertEqual(
            json.loads(self.baseline.read_text()), {"ex-aide": {"gates": 1, "sans_notes": 0}}
        )

    def test_code_de_sortie_1_sur_erreur(self):
        self.ecrire_aide("ex-aide", TestRatchet.GATE)
        with (
            mock.patch.object(lint_aides_data, "AIDES_DIR", self.aides_dir),
            mock.patch.object(lint_aides_data, "FACTS_FILE", self.facts),
            mock.patch.object(lint_aides_data, "FACTS_PENDING_FILE", self.pending),
            mock.patch.object(lint_aides_data, "BASELINE_FILE", self.baseline),
        ):
            self.assertEqual(main(["ex-aide"]), 1)


if __name__ == "__main__":
    unittest.main()
