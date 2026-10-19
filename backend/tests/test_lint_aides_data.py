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
nom_court: Exemple
organisme: Région d'exemple
categorie: region
type: subvention
description: Une aide pour tester le linter.
# `check_portee_geographique` exige le ressort d'un financeur territorial : une
# aide régionale sans région se propose dans toute la France (vu en production
# le 2026-09-22 sur un monument des Vosges).
hard_filters:
  regions:
  - grand-est
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

    def avertissements_porteur(self):
        return [a for a in self.lint().avertissements if "gate porteur" in a]

    def charger_facts(self):
        load_facts.cache_clear()
        return load_facts(self.facts)


class TestPorteurEntreprise(BaseMarqueurs):
    """Le marqueur `porteurs_concernes` : d'une règle de lint à un gate exécuté.

    C'était une ERREUR jusqu'au 2026-09-21 — l'aide devait traduire sa puce
    « Bénéficiaires » en gate `in`, ou le lint sortait rouge. La règle a produit
    l'inverse de son but : quand la source ne nomme pas ses bénéficiaires, le
    modèle inventait le gate pour satisfaire le lint (580 aides sur 643 en
    gatent un, 13 conditions sont étiquetées « NON SOURCÉ »), le vérificateur le
    contestait, et le modèle le maintenait « parce que le lint l'exige ».

    Le marqueur est maintenant exécutable côté moteur, et le lint n'en fait plus
    qu'un relevé.
    """

    def test_gate_entreprise_sans_gate_porteur_nest_plus_une_erreur(self):
        """Ne pas nommer ses bénéficiaires quand la source se tait est LA bonne réponse."""
        self.ecrire_aide("pret-pme", GATE_EFFECTIF)
        self.assertEqual(self.erreurs_porteur(), [])

    def test_le_lint_releve_les_aides_sous_derivation(self):
        """Un relevé, pas un silence : l'agent doit savoir qu'il est couvert."""
        from lint_aides_data import aides_sous_derivation_porteur

        self.ecrire_aide("pret-pme", GATE_EFFECTIF)
        # Mono-slug : c'est le lint que l'agent d'ingestion lit, et c'est là que
        # le message doit l'ORIENTER. En global, `_statistiques` n'en donne que
        # le compte.
        rapport = self.lint("pret-pme")
        self.assertIn("le marqueur `porteurs_concernes` fait le travail", rapport.texte())
        self.assertIn("gate porteur dérivé du marqueur : 1 aide(s)", self.lint().texte())
        releve = aides_sous_derivation_porteur(rapport.aides[0], self.charger_facts())
        self.assertEqual(len(releve), 1, releve)
        self.assertIn("effectif", releve[0])
        self.assertIn("societe, entreprise_individuelle", releve[0])

    def test_le_message_oriente_contre_le_gate_invente(self):
        self.ecrire_aide("pret-pme", GATE_EFFECTIF)
        texte = self.lint("pret-pme").texte()
        self.assertIn("que si la source NOMME ses bénéficiaires", texte)

    def test_un_gate_porteur_explicite_desarme_le_releve(self):
        """La précédence : la source qui nomme ses bénéficiaires a raison."""
        self.ecrire_aide("pret-pme", GATE_EFFECTIF + GATE_PORTEUR)
        from lint_aides_data import aides_sous_derivation_porteur

        rapport = self.lint()
        self.assertEqual(aides_sous_derivation_porteur(rapport.aides[0], self.charger_facts()), [])

    def test_applies_if_d_aide_sur_le_porteur_compte_comme_un_gate(self):
        # Quatre aides du catalogue cadrent leur périmètre entier ainsi plutôt
        # que condition par condition : le moteur les traite pareil.
        from lint_aides_data import aides_sous_derivation_porteur

        (self.aides_dir / "pret-pme.yaml").write_text(
            aide_yaml("pret-pme", GATE_EFFECTIF)
            + "applies_if:\n  fact: statut_juridique_porteur\n  predicate:\n    in: [societe]\n",
            encoding="utf-8",
        )
        rapport = self.lint()
        self.assertEqual(aides_sous_derivation_porteur(rapport.aides[0], self.charger_facts()), [])

    def test_un_gate_plus_large_que_le_marqueur_est_un_avertissement(self):
        """138 aides du corpus, dont 31 admettant `public_commune`. La source a
        raison — mais la question du fait marqué leur sera posée, et ça se voit."""
        large = GATE_PORTEUR.replace(
            "[societe, entreprise_individuelle]", "[societe, public_commune]"
        )
        self.ecrire_aide("pret-pme", GATE_EFFECTIF + large)
        rapport = self.lint()
        self.assertTrue(rapport.ok, rapport.erreurs)
        avertissements = self.avertissements_porteur()
        self.assertEqual(len(avertissements), 1, avertissements)
        self.assertIn("public_commune", avertissements[0])

    def test_un_gate_aussi_etroit_que_le_marqueur_nalerte_pas(self):
        self.ecrire_aide("pret-pme", GATE_EFFECTIF + GATE_PORTEUR)
        self.assertEqual(self.avertissements_porteur(), [])

    def test_condition_non_gate_sur_un_fait_marque_ne_contraint_rien(self):
        # `effect: info` ne trie personne : elle n'ajoute pas de question
        # éliminante, donc pas de raison d'exiger un gate porteur.
        from lint_aides_data import aides_sous_derivation_porteur

        self.ecrire_aide("pret-pme", GATE_EFFECTIF.replace("effect: gate", "effect: info"))
        rapport = self.lint()
        self.assertEqual(aides_sous_derivation_porteur(rapport.aides[0], self.charger_facts()), [])

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


class TestUrlsPartagees(BaseLint):
    """F2 — un dispositif, une fiche. À ACTIVER après le dédoublonnage du lot.

    130 groupes d'URL partagées au 2026-09-18, dont 51 ré-ingestions d'aides
    déjà au catalogue sous un slug suffixé `-2`. Rendue bloquante dès
    maintenant, la règle interdirait tout travail sur le catalogue avant de
    l'avoir corrigé : elle est donc exportée et appelée par le bilan, pas encore
    par `lint`.
    """

    def _aides(self, *urls: str):
        from aides_schema import Aide

        return [
            Aide.model_validate(
                {
                    "slug": f"aide-{i}",
                    "nom": "x",
                    "organisme": "Org",
                    "categorie": "region",
                    "type": "subvention",
                    "description": "d",
                    "source": {"url_officielle": u},
                }
            )
            for i, u in enumerate(urls)
        ]

    def test_deux_aides_sur_la_meme_page(self):
        from lint_aides_data import check_urls_partagees

        erreurs = check_urls_partagees(self._aides("https://x.fr/a", "https://x.fr/a"))
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("aide-0", erreurs[0])
        self.assertIn("aide-1", erreurs[0])

    def test_la_pagination_ne_sauve_pas_le_doublon(self):
        """22 paires du lot venaient de là : `-2` et `-3` d'une liste Typo3."""
        from lint_aides_data import check_urls_partagees

        erreurs = check_urls_partagees(
            self._aides(
                "https://x.fr/d?tx_news_pi1[news]=42",
                "https://x.fr/d?tx_news_pi1[news]=42&tx_news_pi1[currentPage]=2&cHash=a",
            )
        )
        self.assertEqual(len(erreurs), 1, erreurs)

    def test_deux_ancres_distinctes_sont_deux_dispositifs(self):
        """Une page qui porte deux dispositifs sous deux ancres est un vrai découpage."""
        from lint_aides_data import check_urls_partagees

        self.assertEqual(
            check_urls_partagees(self._aides("https://x.fr/a#toiture", "https://x.fr/a#facade")),
            [],
        )

    def test_des_urls_distinctes_ne_sont_pas_signalees(self):
        from lint_aides_data import check_urls_partagees

        self.assertEqual(check_urls_partagees(self._aides("https://x.fr/a", "https://x.fr/b")), [])


class TestFaitsEnAttenteForme(BaseLint):
    """F3 — la forme des faits proposés. AVERTISSEMENTS, jamais erreurs.

    25 booléens à seuil et 97 questions longues sont déjà dans le fichier : les
    passer en erreur bloquerait tout travail sur le lot. La porte d'entrée, elle,
    les REFUSE (`ingestion/faits.py::proposer`), et c'est là qu'il faut être
    strict — le fait n'existe pas encore, l'agent peut corriger.
    """

    def _pending(self, contenu: str):
        self.pending.write_text(contenu, encoding="utf-8")
        self.ecrire_aide("ex-aide")
        self.ecrire_snapshot("ex-aide")
        return self.lint()

    def test_booleen_a_seuil_est_signale(self):
        rapport = self._pending(
            "logement_plus_15_ans:\n"
            "  type: boolean\n"
            "  scope: monument\n"
            "  question: Le logement a-t-il plus de 15 ans ?\n"
        )
        self.assertTrue(rapport.ok, rapport.erreurs)
        signales = [a for a in rapport.avertissements if "seuil chiffré" in a]
        self.assertEqual(len(signales), 1, rapport.avertissements)
        self.assertIn("logement_plus_15_ans", signales[0])

    def test_question_trop_longue_est_signalee(self):
        liste = "intermédiation financière, promotion immobilière, " * 10
        rapport = self._pending(
            "activite_hors_exclusions:\n"
            "  type: boolean\n"
            "  scope: proprietaire\n"
            f"  question: >-\n    L'activité est-elle hors des catégories exclues : {liste} ?\n"
        )
        self.assertTrue(rapport.ok, rapport.erreurs)
        self.assertTrue(any("caractères" in a for a in rapport.avertissements))

    def test_un_fait_bien_forme_nalerte_pas(self):
        rapport = self._pending(
            "age_batiment_ans:\n"
            "  type: integer\n"
            "  scope: monument\n"
            "  unit: ans\n"
            "  question: Quel âge a le bâtiment ?\n"
        )
        self.assertEqual(
            [a for a in rapport.avertissements if "seuil" in a or "caractères" in a], []
        )


class TestOrphelinsDuRun(BaseLint):
    """F4 — un brouillon que l'agent vient d'écrire n'est pas celui du voisin.

    37 orphelins dans `facts_pending.yaml` après le lot : l'agent change d'avis
    et laisse le premier fait derrière lui. Il peut le retirer — celui du
    voisin, non.
    """

    ORPHELIN = (
        "fait_abandonne:\n"
        "  type: boolean\n"
        "  scope: monument\n"
        "  question: Une question à laquelle plus rien ne se réfère ?\n"
    )

    def setUp(self):
        super().setUp()
        self.pending.write_text(self.ORPHELIN, encoding="utf-8")
        self.ecrire_aide("ex-aide")
        self.ecrire_snapshot("ex-aide")

    def test_orphelin_du_run_est_une_erreur_en_mono_slug(self):
        rapport = self.lint("ex-aide", faits_du_run=["fait_abandonne"])
        self.assertFalse(rapport.ok)
        self.assertIn("fait_abandonne", rapport.erreurs[0])
        self.assertIn("retirer_fait", rapport.erreurs[0])

    def test_mono_slug_ne_declare_pas_orphelin_le_fait_dune_autre_aide(self):
        """Sans `faits_du_run`, l'orphelin du voisin reste un avertissement."""
        rapport = self.lint("ex-aide")
        self.assertTrue(rapport.ok, rapport.erreurs)
        self.assertIn("brouillons à retirer", rapport.texte())

    def test_en_global_le_meme_orphelin_reste_informatif(self):
        """Le mode global relit un catalogue, il ne juge le geste de personne."""
        rapport = self.lint(faits_du_run=["fait_abandonne"])
        self.assertTrue(rapport.ok, rapport.erreurs)

    def test_un_fait_du_run_reference_ne_declenche_rien(self):
        self.pending.write_text(
            "fait_utilise:\n"
            "  type: boolean\n"
            "  scope: monument\n"
            "  question: Une question que l'aide cite ?\n",
            encoding="utf-8",
        )
        self.ecrire_aide(
            "ex-aide",
            """\
  - id: cite-le-fait
    text: Une exigence quelconque.
    kind: user_fact
    effect: gate
    fact: fait_utilise
    predicate: {eq: true}
""",
        )
        self.assertTrue(self.lint("ex-aide", faits_du_run=["fait_utilise"]).ok)


class TestPorteeGeographique(BaseLint):
    """Le défaut remonté par un test utilisateur le 2026-09-22.

    Un monument des Vosges (88) se voyait proposer des aides de
    Meurthe-et-Moselle et des Hauts-de-Seine, dont une fiche posée sur une page
    en HTTP 503 qui ne portait aucune donnée d'éligibilité et s'affichait
    « Bonne nouvelle, vous semblez éligible ».
    """

    def _aide(self, **kw):
        from aides_schema import Aide

        base = {
            "slug": "x-truc",
            "nom": "x",
            "organisme": "Département de la Meuse",
            "categorie": "departement",
            "type": "subvention",
            "description": "d",
            "source": {"url_officielle": "https://x.fr/a"},
        }
        return Aide.model_validate({**base, **kw})

    def test_une_aide_departementale_sans_departement_est_une_erreur(self):
        from lint_aides_data import check_portee_geographique

        erreurs = check_portee_geographique(self._aide())
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("hard_filters.departements", erreurs[0])

    def test_le_departement_pose_suffit(self):
        from lint_aides_data import check_portee_geographique

        self.assertEqual(
            check_portee_geographique(self._aide(hard_filters={"departements": ["55"]})), []
        )

    def test_une_region_doit_porter_sa_region(self):
        from lint_aides_data import check_portee_geographique

        aide = self._aide(categorie="region", organisme="Région Grand Est")
        self.assertEqual(len(check_portee_geographique(aide)), 1)
        ok = self._aide(
            categorie="region",
            organisme="Région Grand Est",
            hard_filters={"regions": ["grand-est"]},
        )
        self.assertEqual(check_portee_geographique(ok), [])

    def test_une_aide_nationale_na_pas_de_ressort_a_declarer(self):
        """DRAC, fondations, fiscalité : leur périmètre EST la France."""
        from lint_aides_data import check_portee_geographique

        for categorie in ("etat_drac", "fondation", "fiscalite", "europe", "mecenat", "autre"):
            with self.subTest(categorie=categorie):
                self.assertEqual(check_portee_geographique(self._aide(categorie=categorie)), [])


class TestFailOpen(BaseLint):
    """Une aide qui n'oppose RIEN passe pour éligible à tout le monde, partout."""

    def _aide(self, **kw):
        from aides_schema import Aide

        base = {
            "slug": "x-truc",
            "nom": "x",
            "organisme": "Fondation",
            "categorie": "fondation",
            "type": "subvention",
            "description": "d",
            "source": {"url_officielle": "https://x.fr/a"},
        }
        return Aide.model_validate({**base, **kw})

    def test_sans_rien_du_tout(self):
        from lint_aides_data import check_fail_open

        self.assertEqual(len(check_fail_open(self._aide())), 1)

    def test_un_hard_filter_suffit_a_opposer_quelque_chose(self):
        from lint_aides_data import check_fail_open

        self.assertEqual(check_fail_open(self._aide(hard_filters={"departements": ["55"]})), [])

    def test_applies_if_compte_comme_perimetre(self):
        """Le faux positif de la première version, sur du cœur de métier.

        `programme-patrimoine-emploi-fondation-patrimoine` ne porte QUE son
        `applies_if` (`projet_support_insertion_ou_formation`), et le moteur
        s'en sert pour la déclarer hors périmètre.
        """
        from lint_aides_data import check_fail_open

        aide = self._aide(
            applies_if={"fact": "etat_travaux", "predicate": {"eq": "acheves"}},
        )
        self.assertEqual(check_fail_open(aide), [])

    def test_le_defaut_nest_pas_bloquant(self):
        """Avertissement, pas erreur : `vmf-prix-restauration` est un prix dont
        la source ne publie AUCUN critère. Y poser un gate serait l'inventer."""
        from lint_aides_data import lint

        # Pas `ecrire_aide` : le gabarit partagé porte désormais un ressort
        # régional, donc il n'est plus fail-open.
        (self.aides_dir / "sans-rien.yaml").write_text(
            "slug: sans-rien\n"
            "nom: Prix d'exemple\n"
            "organisme: Association\n"
            "categorie: autre\n"
            "type: subvention\n"
            "description: Un prix dont la source ne publie aucun critère.\n"
            "conditions: []\n",
            encoding="utf-8",
        )
        rapport = lint(
            aides_dir=self.aides_dir,
            facts_path=self.facts,
            pending_path=self.pending,
            baseline_path=self.baseline,
            ratchet=False,
        )
        self.assertTrue(
            any("sans rien à vérifier" in a for a in rapport.avertissements),
            rapport.avertissements,
        )


class TestLevierDeDemarche(BaseLint):
    """Critère ou démarche (TYPING, 2026-09-23) : une démarche faisable avant le
    dépôt s'annonce par un `manual_check` qui cite le levier d'un fait, elle ne
    se demande pas ; un gate posé sur un fait à levier est signalé."""

    FACTS_LEVIER = (
        FACTS
        + """\
audit_realise:
  type: boolean
  scope: monument
  question: Un audit énergétique a-t-il été réalisé ?
  levier:
    resume: Faire réaliser un audit énergétique.
"""
    )

    DEMARCHE = """\
  - id: audit
    text: Le porteur réalise un audit énergétique.
    kind: manual_check
    effect: info
    levier: {fait}
    notes: Démarche faisable avant le dépôt.
"""

    def setUp(self):
        super().setUp()
        self.facts.write_text(self.FACTS_LEVIER, encoding="utf-8")

    def test_levier_cite_un_fait_qui_en_porte_un(self):
        self.ecrire_aide("aide-audit", self.DEMARCHE.format(fait="audit_realise"))
        rapport = self.lint()
        self.assertEqual(rapport.erreurs, [])
        self.assertEqual([a for a in rapport.avertissements if "levier" in a], [])

    def test_levier_sur_un_fait_sans_levier_est_une_erreur(self):
        self.ecrire_aide("aide-audit", self.DEMARCHE.format(fait="monument_ouvert_au_public"))
        erreurs = [e for e in self.lint().erreurs if "levier" in e]
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("monument_ouvert_au_public", erreurs[0])

    def test_levier_sur_un_fait_inconnu_est_une_erreur(self):
        self.ecrire_aide("aide-audit", self.DEMARCHE.format(fait="fait_inexistant"))
        erreurs = [e for e in self.lint().erreurs if "fait_inexistant" in e]
        self.assertEqual(len(erreurs), 1, erreurs)

    def test_gate_sur_un_fait_a_levier_est_une_erreur(self):
        self.ecrire_aide(
            "aide-audit",
            """\
  - id: audit
    text: Le porteur réalise un audit énergétique.
    kind: user_fact
    effect: gate
    fact: audit_realise
    predicate: {eq: true}
""",
        )
        rapport = self.lint()
        erreurs = [e for e in rapport.erreurs if "fait à levier" in e]
        self.assertEqual(len(erreurs), 1, rapport.erreurs)
        self.assertIn("aide-audit / audit", erreurs[0])

    def test_une_question_maintenue_nest_pas_signalee(self):
        self.facts.write_text(
            self.FACTS_LEVIER + "    question_maintenue: true\n", encoding="utf-8"
        )
        self.ecrire_aide(
            "aide-audit",
            """\
  - id: audit
    text: Le porteur réalise un audit énergétique.
    kind: user_fact
    effect: gate
    fact: audit_realise
    predicate: {eq: true}
""",
        )
        self.assertEqual([e for e in self.lint().erreurs if "fait à levier" in e], [])

    def test_un_fait_cite_par_levier_compte_comme_reference(self):
        """Sans quoi un fait proposé qui ne sert plus qu'à porter le plan
        d'action serait annoncé orphelin, et retiré."""
        self.ecrire_aide("aide-audit", self.DEMARCHE.format(fait="audit_realise"))
        self.assertIn("audit_realise", faits_references_dans(self.aides_dir))


class TestPourquoi(unittest.TestCase):
    """`pourquoi` : chaque clé nomme une réponse du fait, ou vaut « * ».

    Contrôle de LINT et non de modèle : une réponse retirée depuis /admin ne
    doit pas invalider la surcharge du fait entière.
    """

    @staticmethod
    def _fait(**champs):
        from aides_schema import FactDef

        return FactDef.model_validate({"scope": "projet", "question": "Q ?", **champs})

    def test_booleen_implicite_admet_oui_non_et_repli(self):
        fait = self._fait(type="boolean", pourquoi={"non": "Parce que.", "*": "Repli."})
        self.assertEqual(lint_aides_data.check_pourquoi({"f": fait}), [])

    def test_cle_inconnue_signalee(self):
        fait = self._fait(
            type="enum",
            options=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            pourquoi={"c": "Réponse disparue."},
        )
        erreurs = lint_aides_data.check_pourquoi({"f": fait})
        self.assertEqual(len(erreurs), 1)
        self.assertIn("pourquoi.c", erreurs[0])

    def test_lien_d_auteur_signale(self):
        fait = self._fait(type="boolean", pourquoi={"non": "Voir [[autre_fait]]."})
        self.assertIn("lien d'auteur", lint_aides_data.check_pourquoi({"f": fait})[0])

    def test_modele_refuse_une_cle_d_option_sur_un_fait_numerique(self):
        with self.assertRaises(ValueError):
            self._fait(type="integer", pourquoi={"lt10": "Tranche recalculée."})
        self._fait(type="integer", pourquoi={"*": "Seuil minimal."})

    def test_modele_refuse_un_texte_vide(self):
        with self.assertRaises(ValueError):
            self._fait(type="boolean", pourquoi={"non": "  "})


class TestModeEcriture(BaseLint):
    """Ce que l'ingestion corrigeait à la main après coup, refusé pendant la boucle."""

    def test_untyped_bloque_en_ecriture_seulement(self):
        cond = COND_OK + "  - id: a-typer\n    text: Une exigence.\n    kind: untyped\n"
        self.ecrire_aide("ex-aide", cond)
        self.assertTrue(self.lint("ex-aide").ok)
        rapport = self.lint("ex-aide", ecriture=True)
        self.assertFalse(rapport.ok)
        self.assertTrue(any("untyped" in e for e in rapport.erreurs))

    def test_calendrier_permanent_avec_date_limite(self):
        from lint_aides_data import check_ecriture

        from aides_schema import Aide

        aide = Aide.model_validate(
            {
                "slug": "x-truc",
                "nom": "x",
                "organisme": "Fondation",
                "categorie": "fondation",
                "type": "subvention",
                "description": "d",
                "calendrier": {"permanent": True, "date_limite": "2027-01-31"},
            }
        )
        erreurs = check_ecriture(aide, {})
        self.assertEqual(len(erreurs), 1)
        self.assertIn("permanent: false", erreurs[0])

    def test_page_sans_rien_a_trancher_avertit(self):
        self.ecrire_aide("ex-page", "  []")
        rapport = self.lint("ex-page", ecriture=True)
        self.assertTrue(any("non_dispositif" in a for a in rapport.avertissements))


class TestPredicatNumerique(unittest.TestCase):
    """`gte: true` sur un entier passait le lint : le moteur comparait un nombre à un booléen."""

    def test_valeur_non_numerique_refusee(self):
        from aides_schema import FactDef, Predicate, check_fact_predicate

        facts = {
            "age_batiment_ans": FactDef.model_validate(
                {"type": "integer", "scope": "monument", "question": "Quel âge a le bâtiment ?"}
            )
        }
        for valeur in (True, "abc", [1, "deux"]):
            with self.subTest(valeur=valeur):
                pred = Predicate.model_validate(
                    {"in" if isinstance(valeur, list) else "gte": valeur}
                )
                self.assertTrue(check_fact_predicate("c", "age_batiment_ans", pred, facts))
        self.assertEqual(
            check_fact_predicate(
                "c", "age_batiment_ans", Predicate.model_validate({"gte": 15}), facts
            ),
            [],
        )


class TestPlancher(unittest.TestCase):
    """`plancher` est un seuil de DÉPENSES : le minimum de l'aide va dans `montant_min`.

    Relecture du 2026-10-19 : 28 des 111 planchers du catalogue portaient le
    minimum de la subvention. Le contrôle lit la source autour de la valeur.
    """

    def _aide(self, plancher: float):
        from aides_schema import Aide

        return Aide.model_validate(
            {
                "slug": "x-truc",
                "nom": "x",
                "organisme": "Région",
                "categorie": "region",
                "type": "subvention",
                "description": "d",
                "source": {"url_officielle": "https://x.fr/a"},
                "financement": {"plancher": plancher},
            }
        )

    def _avertit(self, plancher: float, texte: str) -> bool:
        from lint_aides_data import check_plancher

        return bool(check_plancher(self._aide(plancher), [("page.md", texte, "md")]))

    def test_minimum_de_subvention_signale(self):
        self.assertTrue(
            self._avertit(
                2000, "Dans tous les cas, la subvention ne pourra être inférieure à 2 000 €."
            )
        )
        self.assertTrue(self._avertit(1500, "Plancher de subvention : 1500 €"))
        self.assertTrue(self._avertit(50000, "Plancher minimal de subvention FEDER : 50 000 €"))

    def test_seuil_de_depenses_accepte(self):
        self.assertFalse(self._avertit(3000, "Dépense subventionnable plancher : 3 000 €.H.T."))
        self.assertFalse(self._avertit(50000, "Seuil minimum de dépenses éligibles : 50 000 € HT"))
        self.assertFalse(self._avertit(1000, "Plancher des projets aidés : 1 000 € HT."))

    def test_conversion_en_depenses_lue_apres_la_valeur(self):
        # Le minimum d'aide est cité juste avant, mais la valeur est la dépense.
        self.assertFalse(
            self._avertit(
                40000,
                "Le seuil d'intervention est de 8 000 € minimum de subvention "
                "(soit 40 000 € de dépenses éligibles).",
            )
        )

    def test_sans_source_ni_plancher_rien(self):
        from lint_aides_data import check_plancher

        self.assertEqual(check_plancher(self._aide(2000), []), [])
        self.assertFalse(self._avertit(2000, "Aucune mention de ce montant."))
