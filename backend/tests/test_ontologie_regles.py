"""Les règles de forme d'un fait (scripts/ontologie_regles.py).

Ce module est le seul endroit où trois chemins qui ne peuvent pas s'importer
l'un l'autre lisent la même règle : la porte d'entrée (`ingestion/faits.py`),
le lint et l'audit de fin de run. Ce qu'on teste ici, c'est donc la règle
elle-même — l'usage qu'en font les trois est testé chez eux.

La mesure qui cadre le détecteur de seuil : sur le corpus réel, la CLÉ désigne
25 faits proposés et 19 canoniques, tous de vrais seuils enfermés ; la QUESTION
en désigne une quinzaine de plus, dont la moitié sont du bruit (« moins de 250
employés » dans la définition européenne de la PME). D'où deux portes de
largeur différente, et non un seuil de confiance.

Run from backend/:  uv run pytest tests/test_ontologie_regles.py
"""

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ontologie_regles import (  # noqa: E402
    MAX_CAR_QUESTION,
    MAX_CAR_QUESTION_LINT,
    booleen_a_seuil,
    polarites_suspectes,
    question_trop_longue,
    seuil_chiffre,
    seuil_dans_la_cle,
)


@dataclass
class Fait:
    """Le strict minimum que lisent les règles de forme."""

    question: str
    type: str = "boolean"


class TestSeuilDansLaCle(unittest.TestCase):
    """Le signal propre : ce que le lint regarde et ce que le retypage vise."""

    def test_les_cas_nommes_du_lot(self):
        for cle in (
            "logement_plus_15_ans",
            "age_porteur_moins_62_ans",
            "batiment_plus_50_ans",
            "batiment_plus_15_ans_usage_habitation",
            "logement_vacant_2_ans",
            "s_engage_maintien_plantation_7_ans",
            "s_engage_occupation_logement_5_ans",
            "dirigeants_jeunes_moins_30_ans",
            "contrat_heures_hebdomadaires_30h",
            "baisse_ebe_ou_tresorerie_20pct",
            "atelier_min_5_inscriptions",
        ):
            with self.subTest(cle=cle):
                self.assertIsNotNone(seuil_dans_la_cle(cle), f"{cle} porte pourtant un seuil")

    def test_un_millesime_nest_pas_un_seuil(self):
        """« avant 1948 », « loi 1901 » : un nombre sans comparateur ne se retype pas."""
        for cle in (
            "batiment_construit_avant_1948",
            "association_loi_1901",
            "monument_classe_liste_1840",
            "porteur_immatricule_rne",
            "jardin_remarquable",
        ):
            with self.subTest(cle=cle):
                self.assertIsNone(seuil_dans_la_cle(cle))

    def test_un_integer_a_le_droit_de_porter_un_seuil(self):
        """Le seuil appartient au prédicat — mais un integer le NOMME légitimement."""
        fait = Fait("Depuis combien d'années le bâtiment est-il vacant ?", type="integer")
        self.assertIsNone(booleen_a_seuil("logement_vacance_ans", fait))

    def test_booleen_a_seuil_ne_lit_que_la_cle(self):
        """Sinon le lint crierait sur `est_pme_ue`, qui est canonique et légitime."""
        pme = Fait(
            "Votre structure est-elle une PME au sens de l'Union européenne "
            "(moins de 250 employés et chiffre d'affaires ≤ 50 M€) ?"
        )
        self.assertIsNone(booleen_a_seuil("est_pme_ue", pme))
        self.assertIsNotNone(booleen_a_seuil("logement_plus_15_ans", Fait("Le logement…")))


class TestSeuilChiffre(unittest.TestCase):
    """La porte d'entrée ratisse plus large : un refus qui oriente, pas un avertissement."""

    def test_la_question_suffit(self):
        for question in (
            "Le contrat prévu est-il d'au moins 30 heures par semaine ?",
            "La surface est-elle supérieure à 500 m2 ?",
            "Le taux d'autofinancement dépasse-t-il 20 % ?",
            "Le bâtiment est-il vacant depuis plus de 2 ans ?",
        ):
            with self.subTest(question=question):
                self.assertIsNotNone(seuil_chiffre("un_fait_quelconque", question))

    def test_une_question_sans_seuil_passe(self):
        for question in (
            "Le bâtiment est-il protégé au titre des monuments historiques ?",
            "Le jardin porte-t-il le label Jardin remarquable ?",
            "Le projet prévoit-il l'ouverture au public ?",
        ):
            with self.subTest(question=question):
                self.assertIsNone(seuil_chiffre("un_fait_quelconque", question))

    def test_le_fragment_trouve_est_rendu_pour_le_message(self):
        """L'agent doit savoir sur QUOI on bute, sinon il reformule au hasard."""
        trouve = seuil_chiffre("logement_plus_15_ans", "Le logement a-t-il plus de 15 ans ?")
        self.assertIn("15", trouve or "")


class TestLongueurDeQuestion(unittest.TestCase):
    def test_une_phrase_passe(self):
        self.assertIsNone(question_trop_longue(Fait("Le bâtiment est-il classé ?")))

    def test_une_liste_dexclusions_est_refusee(self):
        liste = "L'activité est-elle hors des catégories exclues : " + "intermédiation, " * 40
        self.assertEqual(question_trop_longue(Fait(liste)), len(" ".join(liste.split())))

    def test_le_repli_yaml_ne_compte_pas(self):
        """Un scalaire replié sur cinq lignes et la même phrase mesurent pareil."""
        plate = "a" * 60 + " " + "b" * 60
        repliee = "a" * 60 + "\n  " + "b" * 60
        self.assertEqual(
            question_trop_longue(Fait(plate), maximum=100),
            question_trop_longue(Fait(repliee), maximum=100),
        )

    def test_le_lint_est_plus_large_que_la_porte_dentree(self):
        """La marge laisse durcir l'entrée sans rendre le lint rouge sur le stock."""
        self.assertGreater(MAX_CAR_QUESTION_LINT, MAX_CAR_QUESTION)
        entre_deux = Fait("x" * ((MAX_CAR_QUESTION + MAX_CAR_QUESTION_LINT) // 2))
        self.assertIsNotNone(question_trop_longue(entre_deux))
        self.assertIsNone(question_trop_longue(entre_deux, maximum=MAX_CAR_QUESTION_LINT))


class TestPolaritesReexportees(unittest.TestCase):
    """Le détecteur a déménagé ici ; `ingestion.ontologie` le ré-exporte.

    Son comportement propre est couvert par
    `tests/test_ingestion_ontologie.py::TestPolarites`, resté inchangé — c'est
    justement ce qui prouve que le déménagement n'a rien changé.
    """

    def test_le_cas_nomme(self):
        suspects = polarites_suspectes(
            {
                "demande_eligible_france_agrimer": Fait(
                    "La demande est-elle non éligible aux aides France AgriMer ?"
                )
            }
        )
        self.assertEqual(suspects, ["demande_eligible_france_agrimer"])

    def test_ingestion_ontologie_reexporte_la_meme_fonction(self):
        from ingestion import ontologie

        self.assertIs(ontologie.polarites_suspectes, polarites_suspectes)


if __name__ == "__main__":
    unittest.main()
