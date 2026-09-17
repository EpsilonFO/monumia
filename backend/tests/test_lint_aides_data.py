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
from lint_aides_data import (  # noqa: E402
    compter_usage_faits,
    faits_entreprise_sans_marqueur,
    faits_references_dans,
    lint,
    main,
)

from aides_schema import load_facts, load_pending_facts  # noqa: E402

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


class TestOrphelins(BaseLint):
    """Un fait proposé que plus aucune aide ne cite : le lint doit le CONCLURE.

    Il calculait déjà qui référence quoi et n'en tirait rien. 48 des 526 faits
    en attente sont dans ce cas : des brouillons qu'un agent ne pouvait pas
    effacer avant `retirer_fait`, et que la relecture humaine doit arbitrer un
    par un pour rien.
    """

    PENDING_DEUX = (
        "jardin_remarquable:\n  type: boolean\n  scope: monument\n"
        "  question: Le jardin est-il labellisé remarquable ?\n"
        "orphelin_oublie:\n  type: boolean\n  scope: monument\n"
        "  question: Plus personne ne pose cette question ?\n"
    )
    COND_PENDING = """\
  - id: label-jardin
    text: Le jardin est labellisé « Jardin remarquable ».
    kind: user_fact
    effect: modulateur
    fact: jardin_remarquable
    predicate: {eq: true}
"""

    def test_orphelin_signale_en_avertissement(self):
        self.pending.write_text(self.PENDING_DEUX, encoding="utf-8")
        self.ecrire_aide("ex-aide", self.COND_PENDING)
        rapport = self.lint()
        self.assertTrue(rapport.ok, rapport.texte())
        self.assertIn("AUCUNE aide ne référence", rapport.texte())
        self.assertIn("orphelin_oublie", rapport.texte().split("AUCUNE aide ne référence")[1])

    def test_fait_reference_nest_pas_orphelin(self):
        self.pending.write_text(self.PENDING_DEUX, encoding="utf-8")
        self.ecrire_aide("ex-aide", self.COND_PENDING)
        ligne = next(
            li for li in self.lint().texte().splitlines() if "AUCUNE aide ne référence" in li
        )
        self.assertNotIn("jardin_remarquable", ligne)
        self.assertIn("1 proposé(s)", ligne)

    def test_orphelin_bloquant_en_strict(self):
        self.pending.write_text(self.PENDING_DEUX, encoding="utf-8")
        self.ecrire_aide("ex-aide", self.COND_PENDING)
        rapport = self.lint(strict=True)
        self.assertFalse(rapport.ok)
        self.assertIn("sans aucune référence", rapport.texte())

    def test_un_applies_if_suffit_a_referencer(self):
        """Un fait seulement ciblé par un `applies_if` pose bien une question."""
        self.pending.write_text(
            "profil_collectivite:\n  type: boolean\n  scope: proprietaire\n"
            "  question: Êtes-vous une collectivité ?\n",
            encoding="utf-8",
        )
        self.ecrire_aide(
            "ex-aide",
            """\
  - id: seulement-collectivites
    text: Pour les collectivités, une délibération est requise.
    kind: manual_check
    effect: info
    applies_if: {fact: profil_collectivite, predicate: {eq: true}}
""",
        )
        self.assertNotIn("AUCUNE aide ne référence", self.lint().texte())

    def test_mono_slug_ne_declare_pas_orphelin_le_fait_dune_autre_aide(self):
        """Le piège : sans balayage global, chaque lint d'agent accuserait le voisin.

        L'agent d'ingestion lance `lint <son slug>` plusieurs fois par aide. Si
        l'usage n'était compté que sur les aides lintées, il se verrait
        reprocher à chaque tour tous les faits proposés par les autres.
        """
        self.pending.write_text(self.PENDING_DEUX, encoding="utf-8")
        self.ecrire_aide("ex-aide", self.COND_PENDING)
        self.ecrire_aide("autre-aide", COND_OK)
        rapport = self.lint("autre-aide")
        self.assertIn("AUCUNE aide ne référence", rapport.texte())
        ligne = next(li for li in rapport.texte().splitlines() if "AUCUNE aide ne référence" in li)
        self.assertNotIn("jardin_remarquable", ligne)
        self.assertIn("orphelin_oublie", ligne)

    def test_le_balayage_textuel_est_fidele_au_parsing(self):
        """Les deux chemins de comptage doivent voir les mêmes références.

        Le mono-slug balaie `aides_dir` au motif textuel (0,08 s contre 2,7 s),
        le mode global réutilise les aides déjà chargées. Un écart ferait
        dépendre le verdict « orphelin » du mode d'appel.
        """
        self.ecrire_aide("ex-aide", COND_OK)
        self.ecrire_aide(
            "flux-aide",
            """\
  - id: en-flux
    text: Pour les jardins ouverts, la gratuité est requise.
    kind: user_fact
    effect: gate
    fact: gratuite_acces
    predicate: {eq: true}
    applies_if: {fact: monument_ouvert_au_public, predicate: {eq: true}}
""",
        )
        rapport = self.lint()
        self.assertEqual(
            faits_references_dans(self.aides_dir), set(compter_usage_faits(rapport.aides))
        )


# `porteurs_concernes`, `hors_gate` et `pertinent_si` sont les trois marqueurs
# de l'ontologie qui CONTRAIGNENT les aides. Ils n'avaient pas de test : une
# règle qui ne se déclenche plus est indiscernable d'un catalogue propre.
FACTS_MARQUEURS = """\
statut_juridique_porteur:
  type: multi_enum
  scope: proprietaire
  question: Qui pourrait déposer la demande ?
  options:
    - id: societe
      label: Société
    - id: entreprise_individuelle
      label: Entreprise individuelle
    - id: public_commune
      label: Commune
effectif_salaries:
  type: integer
  scope: proprietaire
  question: Combien de salariés compte la structure porteuse ?
  porteurs_concernes: [societe, entreprise_individuelle]
autofinancement_pct:
  type: number
  scope: projet
  question: Quelle part du projet autofinancez-vous ?
  hors_gate: true
etat_travaux:
  type: enum
  scope: projet
  question: Où en sont les travaux ?
  options:
    - id: acheves
      label: Achevés
    - id: a_venir
      label: À venir
annees_depuis_achevement:
  type: integer
  scope: projet
  question: Depuis combien d'années les travaux sont-ils achevés ?
  pertinent_si: {fact: etat_travaux, predicate: {eq: acheves}}
"""

GATE_EFFECTIF = """\
  - id: effectif
    text: L'entreprise compte moins de 50 salariés.
    kind: user_fact
    effect: gate
    fact: effectif_salaries
    predicate: {lt: 50}
"""

GATE_PORTEUR = """\
  - id: beneficiaires-porteur
    text: "Bénéficiaires : TPE et PME."
    kind: user_fact
    effect: gate
    fact: statut_juridique_porteur
    predicate:
      in: [societe, entreprise_individuelle]
"""


class BaseMarqueurs(BaseLint):
    """Même tmpdir, mais une ontologie qui porte les trois marqueurs."""

    def setUp(self):
        super().setUp()
        self.facts.write_text(FACTS_MARQUEURS, encoding="utf-8")

    def erreurs_porteur(self):
        return [e for e in self.lint().erreurs if "statut_juridique_porteur" in e]


class TestPorteurEntreprise(BaseMarqueurs):
    """Un gate sur un fait d'entreprise oblige à dire qui peut déposer."""

    def test_gate_entreprise_sans_gate_porteur_est_une_erreur(self):
        self.ecrire_aide("pret-pme", GATE_EFFECTIF)
        erreurs = self.erreurs_porteur()
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("pret-pme / effectif", erreurs[0])
        self.assertIn("societe, entreprise_individuelle", erreurs[0])

    def test_gate_porteur_pose_sur_l_aide_leve_l_erreur(self):
        self.ecrire_aide("pret-pme", GATE_EFFECTIF + GATE_PORTEUR)
        self.assertEqual(self.erreurs_porteur(), [])

    def test_applies_if_d_aide_sur_le_porteur_leve_l_erreur(self):
        # Quatre aides du catalogue cadrent leur périmètre entier ainsi plutôt
        # que condition par condition : le moteur les traite pareil.
        (self.aides_dir / "pret-pme.yaml").write_text(
            aide_yaml("pret-pme", GATE_EFFECTIF)
            + "applies_if:\n  fact: statut_juridique_porteur\n  predicate:\n    in: [societe]\n",
            encoding="utf-8",
        )
        self.assertEqual(self.erreurs_porteur(), [])

    def test_un_gate_porteur_meme_etroit_suffit(self):
        # Le lint exige que l'aide DISE qui dépose, il ne juge pas la liste :
        # la justesse du prédicat se relit au diff, contre la source.
        etroit = GATE_PORTEUR.replace("[societe, entreprise_individuelle]", "[public_commune]")
        self.ecrire_aide("pret-pme", GATE_EFFECTIF + etroit)
        self.assertEqual(self.erreurs_porteur(), [])

    def test_condition_non_gate_sur_un_fait_marque_ne_contraint_rien(self):
        # `effect: info` ne trie personne : elle n'ajoute pas de question
        # éliminante, donc pas de raison d'exiger un gate porteur.
        self.ecrire_aide("pret-pme", GATE_EFFECTIF.replace("effect: gate", "effect: info"))
        self.assertEqual(self.erreurs_porteur(), [])

    def test_marqueur_citant_une_option_inconnue_est_une_erreur(self):
        self.facts.write_text(
            FACTS_MARQUEURS.replace(
                "porteurs_concernes: [societe, entreprise_individuelle]",
                "porteurs_concernes: [societe, cooperative_lunaire]",
            ),
            encoding="utf-8",
        )
        self.ecrire_aide("pret-pme", GATE_EFFECTIF + GATE_PORTEUR)
        erreurs = [e for e in self.lint().erreurs if "porteurs_concernes" in e]
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("cooperative_lunaire", erreurs[0])

    def test_le_fait_porteur_ne_se_marque_pas_lui_meme(self):
        self.facts.write_text(
            FACTS_MARQUEURS.replace(
                "  question: Qui pourrait déposer la demande ?",
                "  question: Qui pourrait déposer la demande ?\n  porteurs_concernes: [societe]",
            ),
            encoding="utf-8",
        )
        erreurs = [e for e in self.lint().erreurs if "porteurs_concernes" in e]
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("ne se marque pas lui-même", erreurs[0])

    def test_marqueur_vide_est_refuse_a_la_validation(self):
        self.facts.write_text(
            FACTS_MARQUEURS.replace(
                "porteurs_concernes: [societe, entreprise_individuelle]",
                "porteurs_concernes: []",
            ),
            encoding="utf-8",
        )
        # Une liste vide dirait « aucun porteur », donc « question jamais
        # posée » : c'est une faute de frappe, refusée dès la validation.
        erreurs = self.lint().erreurs
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("porteurs_concernes", erreurs[0])


class TestHorsGate(BaseMarqueurs):
    """Miroir du test de corpus : l'agent d'ingestion voit le lint, pas pytest."""

    HORS_GATE = """\
  - id: autofinancement
    text: Le porteur autofinance au moins 20 % du projet.
    kind: user_fact
    effect: gate
    fact: autofinancement_pct
    predicate: {gte: 20}
"""

    def test_gate_sur_un_fait_hors_gate_est_une_erreur(self):
        self.ecrire_aide("aide-autofi", self.HORS_GATE)
        erreurs = [e for e in self.lint().erreurs if "hors_gate" in e]
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("manual_check", erreurs[0])

    def test_applies_if_de_condition_sur_un_fait_hors_gate_est_une_erreur(self):
        self.ecrire_aide(
            "aide-autofi",
            GATE_EFFECTIF
            + GATE_PORTEUR
            + "    applies_if: {fact: autofinancement_pct, predicate: {gte: 20}}\n",
        )
        erreurs = [e for e in self.lint().erreurs if "hors_gate" in e]
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("applies_if", erreurs[0])

    def test_info_sur_un_fait_hors_gate_reste_permis(self):
        self.ecrire_aide("aide-autofi", self.HORS_GATE.replace("effect: gate", "effect: info"))
        self.assertEqual([e for e in self.lint().erreurs if "hors_gate" in e], [])


class TestPertinentSi(BaseMarqueurs):
    """La dépendance intrinsèque d'un fait : cible, prédicat, et pas de chaîne."""

    def erreurs(self, remplacement: str):
        self.facts.write_text(
            FACTS_MARQUEURS.replace(
                "  pertinent_si: {fact: etat_travaux, predicate: {eq: acheves}}", remplacement
            ),
            encoding="utf-8",
        )
        return [e for e in self.lint().erreurs if "pertinent_si" in e]

    def test_ontologie_saine_ne_dit_rien(self):
        self.assertEqual(
            self.erreurs("  pertinent_si: {fact: etat_travaux, predicate: {eq: acheves}}"), []
        )

    def test_cible_inconnue(self):
        erreurs = self.erreurs("  pertinent_si: {fact: fait_fantome, predicate: {eq: oui}}")
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("fait cible inconnu", erreurs[0])

    def test_fait_qui_depend_de_lui_meme(self):
        erreurs = self.erreurs(
            "  pertinent_si: {fact: annees_depuis_achevement, predicate: {gte: 1}}"
        )
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("ne peut pas dépendre de lui-même", erreurs[0])

    def test_option_inexistante_dans_le_predicat(self):
        # Une clause jamais vraie tairait la question qu'elle gouverne : un
        # fait tu, pas une erreur visible à l'écran.
        erreurs = self.erreurs("  pertinent_si: {fact: etat_travaux, predicate: {eq: termines}}")
        self.assertEqual(len(erreurs), 1, erreurs)

    def test_chaine_de_deux_niveaux_refusee(self):
        self.facts.write_text(
            FACTS_MARQUEURS.replace(
                "  question: Où en sont les travaux ?",
                "  question: Où en sont les travaux ?\n"
                "  pertinent_si: {fact: effectif_salaries, predicate: {gte: 1}}",
            ),
            encoding="utf-8",
        )
        erreurs = [e for e in self.lint().erreurs if "chaîne limitée" in e]
        self.assertEqual(len(erreurs), 1, erreurs)


class TestDetteMarqueurPorteur(BaseMarqueurs):
    """Le garde-fou du garde-fou : rien ne fait NAÎTRE un fait marqué.

    `porteurs_concernes` bloque une aide qui gate un fait marqué — mais un fait
    neuf naît toujours nu. Ce détecteur signale ceux dont le vocabulaire sent
    l'entreprise, et il ne doit JAMAIS bloquer : la liste est une invitation à
    relire. `creation_offre_visite_entreprise` parle d'entreprise et concerne
    pourtant un monument qui ouvre son atelier ; le refuser obligerait à marquer
    un fait à tort, ce qui est bien pire qu'un fait non marqué.
    """

    def facts_avec(self, bloc_fait: str) -> list[str]:
        self.facts.write_text(FACTS_MARQUEURS + bloc_fait, encoding="utf-8")
        self.ecrire_aide("pret-pme", GATE_EFFECTIF + GATE_PORTEUR)
        return faits_entreprise_sans_marqueur(
            {**load_facts(self.facts), **load_pending_facts(self.pending)}
        )

    def test_un_fait_d_entreprise_nu_est_signale(self):
        self.assertIn(
            "chiffre_affaires_viticole",
            self.facts_avec(
                "chiffre_affaires_viticole:\n"
                "  type: number\n"
                "  scope: proprietaire\n"
                "  question: Quel est le chiffre d'affaires de votre entreprise ?\n"
            ),
        )

    def test_un_fait_deja_marque_ne_l_est_pas(self):
        self.assertNotIn(
            "chiffre_affaires_viticole",
            self.facts_avec(
                "chiffre_affaires_viticole:\n"
                "  type: number\n"
                "  scope: proprietaire\n"
                "  porteurs_concernes: [societe]\n"
                "  question: Quel est le chiffre d'affaires de votre entreprise ?\n"
            ),
        )

    def test_l_entreprise_qui_execute_les_travaux_ne_compte_pas(self):
        # La famille de faux positifs la plus nombreuse, et la seule
        # systématique : l'entreprise y est complément d'agent, jamais sujet.
        self.assertNotIn(
            "travaux_par_entreprises_batiment",
            self.facts_avec(
                "travaux_par_entreprises_batiment:\n"
                "  type: boolean\n"
                "  scope: projet\n"
                "  question: Les travaux ont-ils été réalisés par des entreprises du bâtiment ?\n"
            ),
        )

    def test_un_fait_hors_gate_ne_compte_pas(self):
        # Aucune aide ne peut le gater : le marqueur, qui n'agit qu'à travers un
        # gate, n'y changerait rien.
        self.assertNotIn(
            "fonds_propres_entreprise_pct",
            self.facts_avec(
                "fonds_propres_entreprise_pct:\n"
                "  type: number\n"
                "  scope: projet\n"
                "  hors_gate: true\n"
                "  question: Quelle part votre entreprise autofinance-t-elle ?\n"
            ),
        )

    def test_la_dette_ne_bloque_jamais_le_lint(self):
        self.facts.write_text(
            FACTS_MARQUEURS + "chiffre_affaires_viticole:\n"
            "  type: number\n"
            "  scope: proprietaire\n"
            "  question: Quel est le chiffre d'affaires de votre entreprise ?\n",
            encoding="utf-8",
        )
        self.ecrire_aide("pret-pme", GATE_EFFECTIF + GATE_PORTEUR)
        self.ecrire_snapshot("pret-pme")
        rapport = self.lint()
        self.assertTrue(rapport.ok, rapport.texte())
        self.assertIn("porteurs_concernes", rapport.texte())


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
