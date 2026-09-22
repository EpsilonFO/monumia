"""Retypage d'un fait en condition `info` / `manual_check` (scripts/retyper_faits.py).

Jumeau de `fusionner_faits.py`, et les deux se relisent ensemble : un mandat
étroit, une vérification sur la table ENTIÈRE avant toute écriture, et un
invariant sur `set(pending)` qui voit un découpage textuel ayant mordu sur le
voisin.

Ce que ces tests fixent, et qui n'est pas négociable :

  - `text` et `quote` ne bougent JAMAIS. Ce script ne lit aucune source, il n'a
    donc rien à dire de ce que la source dit ;
  - un `applies_if` est un PÉRIMÈTRE, pas une condition : le retyper changerait
    la portée de l'aide, et c'est hors mandat ;
  - un fichier annoté à la main garde ses commentaires : seul le bloc de la
    condition visée est réécrit, et l'invariant refuse le fichier entier plutôt
    que d'écrire un retypage approximatif ;
  - un fait APPROUVÉ ne se retire que si la table l'écrit (`source: facts.yaml`).

Run from backend/:  uv run pytest tests/test_retyper_faits.py
"""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import retyper_faits  # noqa: E402
from retyper_faits import (  # noqa: E402
    Retypage,
    appliquer,
    charger_table,
    orphelins,
    retirer_orphelins,
    table_des_engagements,
    verifier,
)

from aides_schema import load_facts, load_pending_facts  # noqa: E402

JOUR = date(2026, 9, 21)

FACTS = """\
# --- Le bien ---
monument_ouvert_au_public:
  type: boolean
  scope: monument
  question: Le monument est-il ouvert au public ?

# --- Le dépôt ---
demande_deposee_avant_demarrage:
  type: boolean
  scope: projet
  question: La demande sera-t-elle déposée avant le démarrage des travaux ?
"""

PENDING = """\
# --- ex-aide ---
#
# Proposé par ingerer.py ex-aide (2026-09-18).
s_engage_charte_qualite:
  type: boolean
  scope: projet
  question: Le porteur adhère-t-il à la charte qualité ?

# --- ex-aide ---
#
# Proposé par ingerer.py ex-aide (2026-09-18).
itineraire_eligible_pdipr:
  type: boolean
  scope: projet
  question: L'itinéraire est-il conforme aux critères du PDIPR ?
"""


def aide(slug: str, conditions: list[dict], **extra) -> dict:
    return {
        "slug": slug,
        "nom": "Aide d'exemple",
        "nom_court": "Exemple",
        "organisme": "Région d'exemple",
        "categorie": "region",
        "type": "subvention",
        "description": "Une aide pour tester le retypage.",
        "familles": ["restauration_bati"],
        "conditions": conditions,
        **extra,
    }


GATE_ENGAGEMENT = {
    "id": "adhesion-charte",
    "text": "Le porteur adhère à la charte qualité du territoire.",
    "kind": "user_fact",
    "effect": "gate",
    "fact": "s_engage_charte_qualite",
    "predicate": {"eq": True},
    "quote": "le porteur s'engage à adhérer à la charte qualité",
}

GATE_EXCLUSIONS = {
    "id": "itineraire-pdipr",
    "text": "L'itinéraire respecte les critères du PDIPR.",
    "kind": "user_fact",
    "effect": "gate",
    "fact": "itineraire_eligible_pdipr",
    "predicate": {"eq": True},
    "quote": "conforme aux critères d'éligibilité du PDIPR",
    "notes": "Liste longue, propre au règlement.",
}


class BaseRetypage(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.aides_dir = self.racine / "aides"
        self.aides_dir.mkdir()
        self.facts = self.racine / "facts.yaml"
        self.facts.write_text(FACTS, encoding="utf-8")
        self.pending = self.racine / "facts_pending.yaml"
        self.pending.write_text(PENDING, encoding="utf-8")
        load_facts.cache_clear()
        load_pending_facts.cache_clear()

    def ecrire(self, slug: str, conditions: list[dict], **extra) -> Path:
        chemin = self.aides_dir / f"{slug}.yaml"
        chemin.write_text(
            yaml.safe_dump(
                aide(slug, conditions, **extra), allow_unicode=True, sort_keys=False, width=100
            ),
            encoding="utf-8",
        )
        return chemin

    def appliquer(self, retypages, *, ecrire=True):
        return appliquer(
            retypages,
            aides_dir=self.aides_dir,
            pending_path=self.pending,
            facts_path=self.facts,
            jour=JOUR,
            ecrire=ecrire,
        )

    def relire(self, slug: str) -> dict:
        return yaml.safe_load((self.aides_dir / f"{slug}.yaml").read_text(encoding="utf-8"))


class TestNominal(BaseRetypage):
    def test_un_engagement_devient_info_info(self):
        """59 gates sur des engagements : personne ne répond « non » à une charte."""
        self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        rapport = self.appliquer([Retypage("s_engage_charte_qualite", "Engagement du demandeur.")])
        self.assertTrue(rapport.ok, rapport.erreurs)
        cond = self.relire("ex-aide")["conditions"][0]
        self.assertEqual(cond["kind"], "info")
        self.assertEqual(cond["effect"], "info")
        self.assertNotIn("fact", cond)
        self.assertNotIn("predicate", cond)

    def test_un_autre_fait_devient_manual_check_info(self):
        self.ecrire("ex-aide", [GATE_EXCLUSIONS])
        rapport = self.appliquer([Retypage("itineraire_eligible_pdipr", "Propre au règlement.")])
        self.assertTrue(rapport.ok, rapport.erreurs)
        cond = self.relire("ex-aide")["conditions"][0]
        self.assertEqual(cond["kind"], "manual_check")
        self.assertEqual(cond["effect"], "info")

    def test_text_et_quote_ne_bougent_jamais(self):
        """Ce script ne lit aucune source : il n'a rien à dire de ce qu'elle dit."""
        self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        self.appliquer([Retypage("s_engage_charte_qualite")])
        cond = self.relire("ex-aide")["conditions"][0]
        self.assertEqual(cond["text"], GATE_ENGAGEMENT["text"])
        self.assertEqual(cond["quote"], GATE_ENGAGEMENT["quote"])

    def test_les_notes_gardent_la_provenance(self):
        self.ecrire("ex-aide", [GATE_EXCLUSIONS])
        self.appliquer([Retypage("itineraire_eligible_pdipr", "Propre au règlement.")])
        notes = self.relire("ex-aide")["conditions"][0]["notes"]
        self.assertIn("Liste longue, propre au règlement.", notes)
        self.assertIn("2026-09-21", notes)
        self.assertIn("itineraire_eligible_pdipr", notes)

    def test_le_fait_est_retire_du_pending(self):
        self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        self.appliquer([Retypage("s_engage_charte_qualite")])
        load_pending_facts.cache_clear()
        reste = load_pending_facts(self.pending)
        self.assertEqual(sorted(reste), ["itineraire_eligible_pdipr"])

    def test_plusieurs_aides_citant_le_meme_fait(self):
        self.ecrire("ex-a", [GATE_ENGAGEMENT])
        self.ecrire("ex-b", [GATE_ENGAGEMENT])
        rapport = self.appliquer([Retypage("s_engage_charte_qualite")])
        self.assertEqual(rapport.conditions, 2)
        self.assertEqual(sorted(rapport.fichiers_touches), ["ex-a", "ex-b"])

    def test_dry_run_necrit_rien(self):
        chemin = self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        avant_aide = chemin.read_text(encoding="utf-8")
        avant_pending = self.pending.read_text(encoding="utf-8")
        rapport = self.appliquer([Retypage("s_engage_charte_qualite")], ecrire=False)
        self.assertTrue(rapport.ok, rapport.erreurs)
        self.assertEqual(rapport.conditions, 1)
        self.assertEqual(chemin.read_text(encoding="utf-8"), avant_aide)
        self.assertEqual(self.pending.read_text(encoding="utf-8"), avant_pending)

    def test_une_autre_condition_de_la_meme_aide_est_intacte(self):
        autre = {
            "id": "ouvert",
            "text": "Le monument est ouvert au public.",
            "kind": "user_fact",
            "effect": "gate",
            "fact": "monument_ouvert_au_public",
            "predicate": {"eq": True},
        }
        self.ecrire("ex-aide", [GATE_ENGAGEMENT, autre])
        self.appliquer([Retypage("s_engage_charte_qualite")])
        self.assertEqual(self.relire("ex-aide")["conditions"][1], autre)


class TestRefus(BaseRetypage):
    def test_un_fait_approuve_est_refuse(self):
        self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        rapport = self.appliquer([Retypage("monument_ouvert_au_public")])
        self.assertFalse(rapport.ok)
        self.assertIn("APPROUVÉ", rapport.erreurs[0])

    def test_un_fait_absent_du_pending_est_refuse(self):
        rapport = self.appliquer([Retypage("jamais_vu")])
        self.assertFalse(rapport.ok)
        self.assertIn("déjà retypé", rapport.erreurs[0])

    def test_un_applies_if_daide_est_refuse(self):
        """C'est un PÉRIMÈTRE : le retyper changerait la portée de l'aide."""
        self.ecrire(
            "ex-aide",
            [GATE_EXCLUSIONS],
            applies_if={"fact": "s_engage_charte_qualite", "predicate": {"eq": True}},
        )
        rapport = self.appliquer([Retypage("s_engage_charte_qualite")])
        self.assertFalse(rapport.ok)
        self.assertIn("PÉRIMÈTRE", rapport.erreurs[0])

    def test_un_applies_if_de_condition_est_refuse(self):
        cond = {
            **GATE_EXCLUSIONS,
            "applies_if": {"fact": "s_engage_charte_qualite", "predicate": {"eq": True}},
        }
        self.ecrire("ex-aide", [cond])
        rapport = self.appliquer([Retypage("s_engage_charte_qualite")])
        self.assertFalse(rapport.ok)
        self.assertIn("hors mandat", rapport.erreurs[0])

    def test_un_fichier_commente_qui_ne_cite_pas_le_fait_ne_bloque_pas(self):
        """Sinon un seul fichier annoté figerait tout le catalogue."""
        self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        autre = self.ecrire("ex-autre", [GATE_EXCLUSIONS])
        autre.write_text("# annoté\n" + autre.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertTrue(self.appliquer([Retypage("s_engage_charte_qualite")]).ok)

    def test_un_doublon_dans_la_table_est_refuse(self):
        self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        rapport = self.appliquer(
            [Retypage("s_engage_charte_qualite"), Retypage("s_engage_charte_qualite")]
        )
        self.assertFalse(rapport.ok)
        self.assertIn("deux fois", rapport.erreurs[0])

    def test_un_refus_nécrit_rien_du_tout(self):
        """Une migration à moitié appliquée laisse des aides citant un fait supprimé."""
        chemin = self.ecrire("ex-aide", [GATE_ENGAGEMENT, GATE_EXCLUSIONS])
        avant = chemin.read_text(encoding="utf-8")
        rapport = self.appliquer(
            [Retypage("s_engage_charte_qualite"), Retypage("monument_ouvert_au_public")]
        )
        self.assertFalse(rapport.ok)
        self.assertEqual(chemin.read_text(encoding="utf-8"), avant)
        self.assertEqual(self.pending.read_text(encoding="utf-8"), PENDING)


#: Fiche ANNOTÉE, celle que `safe_dump` détruirait : un en-tête de relecture, un
#: commentaire dans la liste des conditions, une liste indentée de deux espaces
#: (et non zéro comme `safe_dump`), un commentaire en fin de ligne.
AIDE_ANNOTEE = """\
# Fiche relue à la main le 2026-09-01.
slug: ex-annotee
nom: Aide d'exemple
nom_court: Exemple
organisme: Région d'exemple
categorie: region
type: subvention
description: Une aide pour tester le retypage.
familles:
  - restauration_bati
conditions:
  # Puce 3 du règlement, scindée en deux.
  - id: adhesion-charte
    text: Le porteur adhère à la charte qualité du territoire.
    kind: user_fact
    effect: gate
    fact: s_engage_charte_qualite
    predicate:
      eq: true
    quote: le porteur s'engage à adhérer à la charte qualité
  - id: ouvert
    text: Le monument est ouvert au public.
    kind: user_fact
    effect: gate
    fact: monument_ouvert_au_public
    predicate:
      eq: true
    notes: Vérifié sur la fiche.
"""


class TestReecritureTextuelle(BaseRetypage):
    """58 des 109 fichiers du lot des engagements sont annotés à la main.

    `safe_dump` du fichier entier effacerait leurs commentaires, qui sont
    précisément ce que la relecture humaine a produit — d'où une réécriture du
    seul bloc visé, et un invariant qui refuse le fichier entier plutôt que de
    le réparer.
    """

    def ecrire_annotee(self, texte: str = AIDE_ANNOTEE) -> Path:
        chemin = self.aides_dir / "ex-annotee.yaml"
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def test_les_commentaires_survivent(self):
        chemin = self.ecrire_annotee()
        rapport = self.appliquer([Retypage("s_engage_charte_qualite", "Engagement du demandeur.")])
        self.assertTrue(rapport.ok, rapport.erreurs)
        texte = chemin.read_text(encoding="utf-8")
        self.assertIn("# Fiche relue à la main le 2026-09-01.", texte)
        self.assertIn("# Puce 3 du règlement, scindée en deux.", texte)

    def test_la_condition_visee_est_bien_retypee(self):
        self.ecrire_annotee()
        self.appliquer([Retypage("s_engage_charte_qualite", "Engagement du demandeur.")])
        cond = yaml.safe_load((self.aides_dir / "ex-annotee.yaml").read_text(encoding="utf-8"))[
            "conditions"
        ][0]
        self.assertEqual(cond["kind"], "info")
        self.assertEqual(cond["effect"], "info")
        self.assertNotIn("fact", cond)
        self.assertNotIn("predicate", cond)
        self.assertEqual(cond["text"], "Le porteur adhère à la charte qualité du territoire.")
        self.assertEqual(cond["quote"], "le porteur s'engage à adhérer à la charte qualité")
        self.assertIn("2026-09-21", cond["notes"])

    def test_les_autres_conditions_ne_bougent_pas_dun_caractere(self):
        chemin = self.ecrire_annotee()
        self.appliquer([Retypage("s_engage_charte_qualite")])
        texte = chemin.read_text(encoding="utf-8")
        intacte = AIDE_ANNOTEE[AIDE_ANNOTEE.index("  - id: ouvert") :]
        self.assertTrue(texte.endswith(intacte), texte)

    def test_une_forme_inattendue_est_refusee_et_nommee(self):
        """`id` n'ouvre pas l'item : le découpage renonce plutôt que d'improviser."""
        self.ecrire_annotee(
            AIDE_ANNOTEE.replace(
                "  - id: adhesion-charte\n"
                "    text: Le porteur adhère à la charte qualité du territoire.\n",
                "  - text: Le porteur adhère à la charte qualité du territoire.\n"
                "    id: adhesion-charte\n",
            )
        )
        rapport = self.appliquer([Retypage("s_engage_charte_qualite")])
        self.assertFalse(rapport.ok)
        self.assertIn("ex-annotee", rapport.erreurs[0])
        self.assertIn("adhesion-charte", rapport.erreurs[0])

    def test_un_invariant_viole_refuse_le_fichier_et_necrit_rien(self):
        """La garde qui autorise tout le reste : ce qui sort doit charger
        EXACTEMENT ce que `_retyper_condition` produit, sinon rien ne part."""
        chemin = self.ecrire_annotee()
        avant = chemin.read_text(encoding="utf-8")
        with mock.patch.object(retyper_faits, "_reecrire_textuellement", return_value=AIDE_ANNOTEE):
            rapport = self.appliquer([Retypage("s_engage_charte_qualite")])
        self.assertFalse(rapport.ok)
        self.assertIn("réécriture textuelle", rapport.erreurs[0])
        self.assertEqual(chemin.read_text(encoding="utf-8"), avant)
        self.assertEqual(self.pending.read_text(encoding="utf-8"), PENDING)


class TestFaitApprouve(BaseRetypage):
    """Un fait de `facts.yaml` se retire quand la TABLE porte la décision.

    Le script exigeait une décision humaine ; il exige désormais qu'elle soit
    ÉCRITE — relue, commitée, diffable — plutôt que prise en ligne de commande.
    """

    GATE = {
        "id": "depot-avant-demarrage",
        "text": "La demande est déposée avant tout commencement d'exécution.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": "demande_deposee_avant_demarrage",
        "predicate": {"eq": True},
    }
    LIGNE = Retypage(
        "demande_deposee_avant_demarrage",
        "Formalité de dépôt ; le critère réel est `etat_travaux`.",
        source="facts.yaml",
        kind_declare="info",
    )

    def test_sans_source_il_reste_refuse(self):
        self.ecrire("ex-aide", [self.GATE])
        rapport = self.appliquer([Retypage("demande_deposee_avant_demarrage")])
        self.assertFalse(rapport.ok)
        self.assertIn("APPROUVÉ", rapport.erreurs[0])
        self.assertIn("source: facts.yaml", rapport.erreurs[0])

    def test_avec_source_il_est_retire_de_facts_yaml(self):
        self.ecrire("ex-aide", [self.GATE])
        rapport = self.appliquer([self.LIGNE])
        self.assertTrue(rapport.ok, rapport.erreurs)
        self.assertEqual(rapport.retires, ["demande_deposee_avant_demarrage"])
        load_facts.cache_clear()
        self.assertEqual(sorted(load_facts(self.facts)), ["monument_ouvert_au_public"])

    def test_le_voisin_et_ses_commentaires_restent(self):
        """L'invariant de `fusionner_faits`, sur `facts.yaml` cette fois : le
        fichier porte exactement les faits d'avant, moins celui qu'on retire."""
        self.ecrire("ex-aide", [self.GATE])
        self.appliquer([self.LIGNE])
        texte = self.facts.read_text(encoding="utf-8")
        self.assertIn("# --- Le bien ---", texte)
        self.assertIn("monument_ouvert_au_public:", texte)
        self.assertNotIn("demande_deposee_avant_demarrage", texte)

    def test_le_pending_nest_pas_touche(self):
        self.ecrire("ex-aide", [self.GATE])
        self.appliquer([self.LIGNE])
        self.assertEqual(self.pending.read_text(encoding="utf-8"), PENDING)

    def test_le_kind_declare_prime_sur_le_prefixe(self):
        """`demande_deposee_avant_demarrage` est une promesse sans être un
        `s_engage_*` : sans la table, elle tomberait en `manual_check`."""
        self.ecrire("ex-aide", [self.GATE])
        self.appliquer([self.LIGNE])
        self.assertEqual(self.relire("ex-aide")["conditions"][0]["kind"], "info")
        self.assertEqual(
            Retypage("demande_deposee_avant_demarrage", source="facts.yaml").kind, "manual_check"
        )

    def test_une_source_qui_ne_porte_pas_le_fait_est_refusee(self):
        self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        rapport = self.appliquer([Retypage("s_engage_charte_qualite", source="facts.yaml")])
        self.assertFalse(rapport.ok)
        self.assertIn("n'y est pas", rapport.erreurs[0])

    def test_les_deux_ontologies_dans_la_meme_table(self):
        self.ecrire("ex-aide", [self.GATE, GATE_ENGAGEMENT])
        rapport = self.appliquer([self.LIGNE, Retypage("s_engage_charte_qualite")])
        self.assertTrue(rapport.ok, rapport.erreurs)
        load_facts.cache_clear()
        load_pending_facts.cache_clear()
        self.assertEqual(sorted(load_facts(self.facts)), ["monument_ouvert_au_public"])
        self.assertEqual(sorted(load_pending_facts(self.pending)), ["itineraire_eligible_pdipr"])


class TestTable(BaseRetypage):
    def test_charger_une_table_valide(self):
        chemin = self.racine / "table.yaml"
        chemin.write_text(
            "retypages:\n  - fait: s_engage_charte_qualite\n    motif: Engagement.\n",
            encoding="utf-8",
        )
        retypages, erreurs = charger_table(chemin)
        self.assertEqual(erreurs, [])
        self.assertEqual(retypages, [Retypage("s_engage_charte_qualite", "Engagement.")])

    def test_une_ligne_sans_fait_est_signalee(self):
        chemin = self.racine / "table.yaml"
        chemin.write_text("retypages:\n  - motif: rien\n", encoding="utf-8")
        _retypages, erreurs = charger_table(chemin)
        self.assertEqual(len(erreurs), 1, erreurs)

    def test_la_table_des_engagements_prend_tous_les_s_engage(self):
        load_pending_facts.cache_clear()
        table = table_des_engagements(load_pending_facts(self.pending))
        self.assertEqual([r.fait for r in table], ["s_engage_charte_qualite"])
        self.assertEqual(table[0].kind, "info")

    def test_le_kind_derive_du_prefixe(self):
        self.assertEqual(Retypage("s_engage_x").kind, "info")
        self.assertEqual(Retypage("itineraire_y").kind, "manual_check")

    def test_charger_source_et_kind(self):
        chemin = self.racine / "table.yaml"
        chemin.write_text(
            "retypages:\n"
            "  - fait: demande_deposee_avant_demarrage\n"
            "    motif: Formalité de dépôt.\n"
            "    source: facts.yaml\n"
            "    kind: info\n",
            encoding="utf-8",
        )
        retypages, erreurs = charger_table(chemin)
        self.assertEqual(erreurs, [])
        self.assertEqual(
            retypages,
            [
                Retypage(
                    "demande_deposee_avant_demarrage",
                    "Formalité de dépôt.",
                    source="facts.yaml",
                    kind_declare="info",
                )
            ],
        )

    def test_une_source_inconnue_est_signalee(self):
        chemin = self.racine / "table.yaml"
        chemin.write_text(
            "retypages:\n  - fait: s_engage_x\n    source: ontologie.yaml\n", encoding="utf-8"
        )
        _retypages, erreurs = charger_table(chemin)
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("source", erreurs[0])

    def test_un_kind_hors_mandat_est_signale(self):
        """Élargir la liste des `kind`, c'est élargir le mandat du script."""
        chemin = self.racine / "table.yaml"
        chemin.write_text(
            "retypages:\n  - fait: s_engage_x\n    kind: user_fact\n", encoding="utf-8"
        )
        _retypages, erreurs = charger_table(chemin)
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("hors du mandat", erreurs[0])


class TestOrphelins(BaseRetypage):
    def test_orphelin_detecte(self):
        self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        load_pending_facts.cache_clear()
        self.assertEqual(
            orphelins(load_pending_facts(self.pending), aides_dir=self.aides_dir),
            ["itineraire_eligible_pdipr"],
        )

    def test_retirer_orphelins_ne_touche_aucune_condition(self):
        chemin = self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        avant = chemin.read_text(encoding="utf-8")
        rapport = retirer_orphelins(
            aides_dir=self.aides_dir,
            pending_path=self.pending,
            facts_path=self.facts,
            jour=JOUR,
            ecrire=True,
        )
        self.assertTrue(rapport.ok, rapport.erreurs)
        self.assertEqual(rapport.retires, ["itineraire_eligible_pdipr"])
        self.assertEqual(rapport.conditions, 0)
        self.assertEqual(chemin.read_text(encoding="utf-8"), avant)

    def test_sans_orphelin_rien_a_faire(self):
        self.ecrire("ex-aide", [GATE_ENGAGEMENT, GATE_EXCLUSIONS])
        rapport = retirer_orphelins(
            aides_dir=self.aides_dir,
            pending_path=self.pending,
            facts_path=self.facts,
            ecrire=True,
        )
        self.assertTrue(rapport.ok)
        self.assertEqual(rapport.retires, [])


class TestInvariant(BaseRetypage):
    def test_le_pending_ne_perd_que_ce_quon_retire(self):
        """L'invariant qui tient toute la migration, comme dans fusionner_faits."""
        self.ecrire("ex-aide", [GATE_ENGAGEMENT, GATE_EXCLUSIONS])
        load_pending_facts.cache_clear()
        avant = set(load_pending_facts(self.pending))
        self.appliquer([Retypage("s_engage_charte_qualite")])
        load_pending_facts.cache_clear()
        self.assertEqual(set(load_pending_facts(self.pending)), avant - {"s_engage_charte_qualite"})

    def test_vider_le_pending_entier_laisse_un_fichier_vide(self):
        self.ecrire("ex-aide", [GATE_ENGAGEMENT, GATE_EXCLUSIONS])
        rapport = self.appliquer(
            [Retypage("s_engage_charte_qualite"), Retypage("itineraire_eligible_pdipr")]
        )
        self.assertTrue(rapport.ok, rapport.erreurs)
        self.assertEqual(self.pending.read_text(encoding="utf-8").strip(), "")

    def test_verifier_ne_rend_rien_sur_une_table_saine(self):
        self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        load_facts.cache_clear()
        load_pending_facts.cache_clear()
        self.assertEqual(
            verifier(
                [Retypage("s_engage_charte_qualite")],
                load_facts(self.facts),
                load_pending_facts(self.pending),
                aides_dir=self.aides_dir,
            ),
            [],
        )


class TestLotsReels(unittest.TestCase):
    """Miroir de `test_fusionner_faits.TestLotsReels` pour les tables de retypage.

    Un lot déjà appliqué est idempotent par refus : ses faits ne sont plus dans
    l'ontologie, donc le rejouer ne réécrit rien. Ce qui doit rester vrai, c'est
    que la table se charge et que chaque ligne porte son motif — c'est lui qui
    rend le diff relisible dans six mois.
    """

    LOTS = [
        chemin
        for chemin in sorted(
            (Path(__file__).resolve().parent.parent / "data" / "fusions").glob("*.yaml")
        )
        if "retypages" in (yaml.safe_load(chemin.read_text(encoding="utf-8")) or {})
    ]

    def test_toutes_les_tables_sont_bien_formees(self):
        self.assertTrue(self.LOTS, "aucune table de retypage versionnée")
        for chemin in self.LOTS:
            with self.subTest(table=chemin.name):
                retypages, erreurs = charger_table(chemin)
                self.assertEqual(erreurs, [])
                self.assertTrue(retypages)

    def test_chaque_ligne_porte_un_motif(self):
        for chemin in self.LOTS:
            retypages, _ = charger_table(chemin)
            for r in retypages:
                with self.subTest(table=chemin.name, fait=r.fait):
                    self.assertTrue(r.motif.strip())

    def test_le_lot_4_est_applique_et_ne_rejoue_rien(self):
        """Ses 43 faits ont quitté l'ontologie : le rejouer est refusé, ligne
        par ligne, et rien n'est écrit."""
        chemin = next(c for c in self.LOTS if "lot-4" in c.name)
        retypages, _ = charger_table(chemin)
        rapport = appliquer(retypages, ecrire=False)
        self.assertFalse(rapport.ok)
        refuses = {r.fait for r in retypages if any(r.fait in e for e in rapport.erreurs)}
        self.assertEqual(refuses, {r.fait for r in retypages})


if __name__ == "__main__":
    unittest.main()
