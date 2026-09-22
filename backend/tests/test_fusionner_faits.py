"""Tests du script de fusion de faits (scripts/fusionner_faits.py).

Un script de migration jetable, mais qui touche 29 lignes `fact:` dans 18
fichiers d'aides : ce qu'il faut fixer, c'est ce qu'il REFUSE. Le lint accepte
n'importe quelle clé qui existe — il ne dira jamais qu'une fusion a changé le
sens d'un critère d'éligibilité.

Quatre refus portent tout :
  - un type ou un scope qui change, parce que les prédicats des aides devraient
    changer avec, et qu'aucun script ne peut décider ça sans la source ;
  - une option sans équivalent, qui rendrait faux tout prédicat la citant ;
  - deux clés qui ne diffèrent que par « non » ou « sans » — la POLARITÉ
    opposée, seul cas qu'aucun contrôle de forme ne voit et dont l'erreur ne
    laisse aucune trace dans le diff ;
  - une suppression sèche dont la clé est encore référencée.

Et un invariant : une table refusée n'écrit RIEN, pas même la partie valide.

Run from backend/:  uv run pytest tests/test_fusionner_faits.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fusionner_faits import (  # noqa: E402
    Fusion,
    _polarite_opposee,
    appliquer,
    charger_table,
    main,
)

from aides_schema import load_facts, load_pending_facts  # noqa: E402

FACTS = """\
manifestation_but_non_lucratif:
  type: boolean
  scope: projet
  question: La manifestation est-elle à but non lucratif ?
"""

PENDING = """\
# --- aide-a ---
#
# Justification de la première proposition, que le retrait doit emporter avec
# le fait, et qu'un `safe_dump` effacerait pour tout le fichier.
porteur_secteur_industrie:
  type: boolean
  scope: proprietaire
  question: La structure relève-t-elle de l'industrie ?

# --- aide-b ---
#
# Justification de la seconde, qui doit SURVIVRE au retrait de la première.
entreprise_secteur_industrie:
  type: boolean
  scope: proprietaire
  question: L'entreprise relève-t-elle de l'industrie ?

# --- aide-c ---
#
# Un fait d'un autre type, pour le refus « enum absorbant un booléen ».
statut_industrie:
  type: enum
  scope: proprietaire
  question: Quel est le statut industriel de la structure ?
  options:
    - id: industrie
      label: Industrie
    - id: autre
      label: Autre

# --- aide-d ---
#
# Un couple de polarité opposée.
chauffage_fioul_apres_travaux:
  type: boolean
  scope: projet
  question: Après travaux, le fioul reste-t-il l'énergie principale ?
chauffage_sans_fioul_apres_travaux:
  type: boolean
  scope: projet
  question: Après travaux, le fioul cesse-t-il d'être l'énergie principale ?

# --- aide-e ---
#
# Un scope divergent.
projet_secteur_industrie:
  type: boolean
  scope: projet
  question: Le projet relève-t-il de l'industrie ?

# --- aide-f ---
#
# Un orphelin, que rien ne référence.
brouillon_abandonne:
  type: boolean
  scope: monument
  question: Question qu'on n'a jamais posée ?
"""


def aide(slug: str, *facts: str) -> str:
    conditions = "".join(
        f"  - id: c{i}\n    text: Critère {i}.\n    kind: user_fact\n"
        f"    effect: gate\n    fact: {f}\n    predicate: {{eq: true}}\n"
        for i, f in enumerate(facts, 1)
    )
    return (
        f"slug: {slug}\nnom: Aide {slug}\norganisme: Région\ncategorie: region\n"
        f"type: subvention\ndescription: Une aide.\nconditions:\n{conditions}"
    )


class BaseFusion(unittest.TestCase):
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
        (self.aides_dir / "aide-a.yaml").write_text(
            aide("aide-a", "porteur_secteur_industrie"), encoding="utf-8"
        )
        (self.aides_dir / "aide-b.yaml").write_text(
            aide("aide-b", "entreprise_secteur_industrie", "chauffage_fioul_apres_travaux"),
            encoding="utf-8",
        )
        load_facts.cache_clear()
        load_pending_facts.cache_clear()

    def appliquer(self, *fusions: Fusion, ecrire: bool = True):
        return appliquer(
            list(fusions),
            aides_dir=self.aides_dir,
            pending_path=self.pending,
            facts_path=self.facts,
            ecrire=ecrire,
        )

    def cles_pending(self) -> set[str]:
        return set(yaml.safe_load(self.pending.read_text(encoding="utf-8")) or {})


class TestTable(unittest.TestCase):
    def test_table_bien_formee(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "t.yaml"
            chemin.write_text(
                "fusions:\n  - retirer: a\n    garder: b\n    motif: m\n  - retirer: c\n",
                encoding="utf-8",
            )
            fusions, erreurs = charger_table(chemin)
        self.assertEqual(erreurs, [])
        self.assertEqual(fusions[0], Fusion(retirer="a", garder="b", motif="m"))
        self.assertEqual(fusions[1].garder, "")

    def test_table_sans_liste_fusions_refusee(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "t.yaml"
            chemin.write_text("autre: chose\n", encoding="utf-8")
            _fusions, erreurs = charger_table(chemin)
        self.assertTrue(erreurs)

    def test_ligne_sans_retirer_refusee(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "t.yaml"
            chemin.write_text("fusions:\n  - garder: b\n", encoding="utf-8")
            _fusions, erreurs = charger_table(chemin)
        self.assertIn("`retirer` manquant", erreurs[0])


class TestPolarite(unittest.TestCase):
    """Le seul refus qu'aucun contrôle de type, de scope ou d'options ne donne."""

    def test_sans_detecte(self):
        self.assertEqual(
            _polarite_opposee(
                "chauffage_sans_fioul_apres_travaux", "chauffage_fioul_apres_travaux"
            ),
            "sans",
        )

    def test_non_detecte(self):
        self.assertEqual(
            _polarite_opposee("demande_eligible_agrimer", "demande_non_eligible_agrimer"), "non"
        )

    def test_un_suffixe_ordinaire_nest_pas_une_negation(self):
        self.assertIsNone(
            _polarite_opposee("structure_but_non_lucratif_seule", "structure_but_non_lucratif")
        )

    def test_deux_cles_sans_rapport(self):
        self.assertIsNone(_polarite_opposee("porteur_siege_grand_est", "jardin_remarquable"))

    def test_les_deux_nient_la_meme_chose(self):
        """Même négation des deux côtés : ce n'est pas une inversion."""
        self.assertIsNone(_polarite_opposee("a_sans_b_v2", "a_sans_b"))


class TestRefus(BaseFusion):
    def test_type_different_refuse(self):
        rapport = self.appliquer(
            Fusion(retirer="porteur_secteur_industrie", garder="statut_industrie")
        )
        self.assertFalse(rapport.ok)
        self.assertIn("types différents", rapport.erreurs[0])

    def test_scope_different_refuse(self):
        rapport = self.appliquer(
            Fusion(retirer="projet_secteur_industrie", garder="porteur_secteur_industrie")
        )
        self.assertFalse(rapport.ok)
        self.assertIn("scope", rapport.erreurs[0])

    def test_polarite_opposee_refusee(self):
        rapport = self.appliquer(
            Fusion(
                retirer="chauffage_sans_fioul_apres_travaux", garder="chauffage_fioul_apres_travaux"
            )
        )
        self.assertFalse(rapport.ok)
        self.assertIn("polarité opposée", rapport.erreurs[0])

    def test_retirer_un_fait_approuve_refuse(self):
        rapport = self.appliquer(
            Fusion(retirer="manifestation_but_non_lucratif", garder="porteur_secteur_industrie")
        )
        self.assertFalse(rapport.ok)
        self.assertIn("APPROUVÉ", rapport.erreurs[0])

    def test_fait_inconnu_refuse(self):
        rapport = self.appliquer(Fusion(retirer="zorglub", garder="porteur_secteur_industrie"))
        self.assertFalse(rapport.ok)
        self.assertIn("déjà fusionné", rapport.erreurs[0])

    def test_cible_inconnue_refusee(self):
        rapport = self.appliquer(Fusion(retirer="brouillon_abandonne", garder="zorglub"))
        self.assertFalse(rapport.ok)
        self.assertIn("n'existe ni dans", rapport.erreurs[0])

    def test_chaine_refusee(self):
        """A→B et B→C : l'ordre d'application déciderait du résultat."""
        rapport = self.appliquer(
            Fusion(retirer="porteur_secteur_industrie", garder="entreprise_secteur_industrie"),
            Fusion(retirer="entreprise_secteur_industrie", garder="chauffage_fioul_apres_travaux"),
        )
        self.assertFalse(rapport.ok)
        self.assertTrue(any("à la fois gardé et retiré" in e for e in rapport.erreurs))

    def test_suppression_seche_dun_fait_reference_refusee(self):
        rapport = self.appliquer(Fusion(retirer="porteur_secteur_industrie"))
        self.assertFalse(rapport.ok)
        self.assertTrue(any("suppression sèche" in e for e in rapport.erreurs))

    def test_un_refus_nesuit_rien_du_tout(self):
        """Pas même la partie valide : une migration à moitié faite est pire que rien."""
        avant_pending = self.pending.read_text(encoding="utf-8")
        avant_aide = (self.aides_dir / "aide-a.yaml").read_text(encoding="utf-8")
        rapport = self.appliquer(
            Fusion(retirer="brouillon_abandonne"),
            Fusion(retirer="porteur_secteur_industrie", garder="statut_industrie"),
        )
        self.assertFalse(rapport.ok)
        self.assertEqual(self.pending.read_text(encoding="utf-8"), avant_pending)
        self.assertEqual((self.aides_dir / "aide-a.yaml").read_text(encoding="utf-8"), avant_aide)


class TestApplication(BaseFusion):
    def test_fusion_nominale(self):
        rapport = self.appliquer(
            Fusion(retirer="porteur_secteur_industrie", garder="entreprise_secteur_industrie")
        )
        self.assertTrue(rapport.ok, rapport.erreurs)
        self.assertIn(
            "fact: entreprise_secteur_industrie",
            (self.aides_dir / "aide-a.yaml").read_text(encoding="utf-8"),
        )
        self.assertNotIn("porteur_secteur_industrie", self.cles_pending())

    def test_la_justification_du_voisin_survit(self):
        """Découpage textuel : un `safe_dump` effacerait les 500 justifications du fichier."""
        self.appliquer(
            Fusion(retirer="porteur_secteur_industrie", garder="entreprise_secteur_industrie")
        )
        texte = self.pending.read_text(encoding="utf-8")
        self.assertIn("qui doit SURVIVRE au retrait de la première", texte)
        self.assertNotIn("que le retrait doit emporter", texte)

    def test_dry_run_necrit_rien(self):
        avant = self.pending.read_text(encoding="utf-8")
        rapport = self.appliquer(
            Fusion(retirer="porteur_secteur_industrie", garder="entreprise_secteur_industrie"),
            ecrire=False,
        )
        self.assertTrue(rapport.ok)
        self.assertEqual(rapport.occurrences, 1)
        self.assertEqual(self.pending.read_text(encoding="utf-8"), avant)

    def test_suppression_seche_ne_touche_aucune_aide(self):
        avant = (self.aides_dir / "aide-a.yaml").read_text(encoding="utf-8")
        rapport = self.appliquer(Fusion(retirer="brouillon_abandonne"))
        self.assertTrue(rapport.ok, rapport.erreurs)
        self.assertEqual(rapport.occurrences, 0)
        self.assertEqual(rapport.retires, ["brouillon_abandonne"])
        self.assertEqual((self.aides_dir / "aide-a.yaml").read_text(encoding="utf-8"), avant)

    def test_plusieurs_clés_vers_une_seule(self):
        rapport = self.appliquer(
            Fusion(retirer="porteur_secteur_industrie", garder="entreprise_secteur_industrie"),
            Fusion(retirer="projet_secteur_industrie", garder="entreprise_secteur_industrie"),
        )
        # Le scope de `projet_secteur_industrie` diffère : la table entière est refusée.
        self.assertFalse(rapport.ok)

    def test_seules_les_lignes_fact_sont_touchees(self):
        """Un `fact:` dans une autre position, ou la clé citée ailleurs, ne bouge pas."""
        (self.aides_dir / "aide-c.yaml").write_text(
            aide("aide-c", "porteur_secteur_industrie").replace(
                "description: Une aide.",
                "description: Aide citant porteur_secteur_industrie dans son texte.",
            ),
            encoding="utf-8",
        )
        self.appliquer(
            Fusion(retirer="porteur_secteur_industrie", garder="entreprise_secteur_industrie")
        )
        texte = (self.aides_dir / "aide-c.yaml").read_text(encoding="utf-8")
        self.assertIn("citant porteur_secteur_industrie dans son texte", texte)
        self.assertIn("fact: entreprise_secteur_industrie", texte)
        self.assertNotIn("fact: porteur_secteur_industrie", texte)

    def test_le_fichier_reste_lisible(self):
        self.appliquer(
            Fusion(retirer="porteur_secteur_industrie", garder="entreprise_secteur_industrie")
        )
        load_pending_facts.cache_clear()
        restants = load_pending_facts(self.pending)
        self.assertIn("entreprise_secteur_industrie", restants)
        self.assertNotIn("porteur_secteur_industrie", restants)


class TestCLI(BaseFusion):
    def test_table_illisible_rend_2(self):
        chemin = self.racine / "absente.yaml"
        self.assertEqual(main([str(chemin)]), 2)


class TestLotsReels(unittest.TestCase):
    """Les tables versionnées doivent rester cohérentes avec l'ontologie du dépôt.

    Un lot déjà appliqué est idempotent par refus : ses clés ne sont plus dans
    `facts_pending.yaml`, donc le rejouer est refusé et n'écrit rien. C'est
    exactement ce qu'on veut d'un script de migration relancé par erreur.

    `data/fusions/` héberge aussi les tables de RETYPAGE (clé `retypages`), qui
    ont leur propre script et leur propre miroir dans `test_retyper_faits.py` :
    on ne retient ici que les tables de fusion.
    """

    LOTS = [
        chemin
        for chemin in sorted(
            (Path(__file__).resolve().parent.parent / "data" / "fusions").glob("*.yaml")
        )
        if "fusions" in (yaml.safe_load(chemin.read_text(encoding="utf-8")) or {})
    ]

    def test_toutes_les_tables_sont_bien_formees(self):
        self.assertTrue(self.LOTS, "aucune table de fusion versionnée")
        for chemin in self.LOTS:
            with self.subTest(table=chemin.name):
                fusions, erreurs = charger_table(chemin)
                self.assertEqual(erreurs, [])
                self.assertTrue(fusions)

    def test_chaque_ligne_porte_un_motif(self):
        """Le motif est ce qui rend le diff relisible : sans lui, on perd le pourquoi."""
        for chemin in self.LOTS:
            fusions, _ = charger_table(chemin)
            for f in fusions:
                with self.subTest(table=chemin.name, retirer=f.retirer):
                    self.assertTrue(f.motif.strip())

    def test_le_lot_3_est_integralement_refuse(self):
        """Il documente des décisions humaines : aucune de ses lignes ne doit passer."""
        chemin = next(c for c in self.LOTS if "lot-3" in c.name)
        fusions, _ = charger_table(chemin)
        rapport = appliquer(fusions, ecrire=False)
        self.assertFalse(rapport.ok)
        refusees = {f.retirer for f in fusions if any(f.retirer in e for e in rapport.erreurs)}
        self.assertEqual(refusees, {f.retirer for f in fusions})


if __name__ == "__main__":
    unittest.main()
