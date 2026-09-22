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
  - un fichier annoté à la main n'est pas réécrit à la machine.

Run from backend/:  uv run pytest tests/test_retyper_faits.py
"""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

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
monument_ouvert_au_public:
  type: boolean
  scope: monument
  question: Le monument est-il ouvert au public ?
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

    def test_un_fichier_commente_est_refuse(self):
        """704 fichiers sur 1 079 sont stables ; les autres ont été annotés."""
        chemin = self.ecrire("ex-aide", [GATE_ENGAGEMENT])
        chemin.write_text(
            "# Fiche relue à la main le 2026-09-01.\n" + chemin.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        rapport = self.appliquer([Retypage("s_engage_charte_qualite")])
        self.assertFalse(rapport.ok)
        self.assertIn("réécriture YAML", rapport.erreurs[0])
        self.assertIn("adhesion-charte", rapport.erreurs[0])

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


if __name__ == "__main__":
    unittest.main()
