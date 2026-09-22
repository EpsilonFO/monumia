"""Les familles thématiques : une liste fermée en TROIS endroits.

`labels.FAMILLES_LABELS` (d'où `aides_schema.FAMILLES` dérive), le CHECK SQL de
la dernière migration qui le repose, et `FAMILLE_OPTIONS` côté front. Une
famille ajoutée à l'un et pas aux autres passerait la validation Pydantic et
échouerait à l'insertion (ou l'inverse : un code accepté en base qu'aucun
libellé ne sait rendre).

Le miroir front est `frontend/src/constants/__tests__/familles.test.ts`, qui
assène les mêmes valeurs — patron `test_billing_access.py::TableDesOffresTest`
↔ `offres.test.ts`.
"""

import re
import unittest
from pathlib import Path

from pydantic import ValidationError

from aides_schema import AIDES_DIR, FAMILLES, Aide, load_aide
from labels import FAMILLES_DESCRIPTION, FAMILLES_HERITEES, FAMILLES_LABELS

RACINE = Path(__file__).resolve().parents[2]
MIGRATIONS = RACINE / "supabase" / "migrations"
FRONT_FAMILLES = RACINE / "frontend" / "src" / "constants" / "familles.ts"


class TableDesFamillesTest(unittest.TestCase):
    #: Les quatorze familles et leur libellé produit, FIGÉS. Toute modification
    #: ici doit se retrouver dans le front et dans le CHECK SQL.
    ATTENDUES = {
        "restauration_bati": "Restauration du bâti",
        "energie_climat": "Énergie et climat",
        "eau_nature_domaine": "Eau, nature et domaine",
        "securite_risques": "Sécurité et risques",
        "parcs_jardins_paysages": "Parcs, jardins et paysages",
        "hebergement_touristique": "Hébergement touristique",
        "tourisme_visite": "Site de visite et tourisme",
        "activite_economique_lieu": "Activité économique dans le lieu",
        "spectacles_manifestations": "Spectacles et manifestations",
        "vie_locale_associative": "Vie locale et associative",
        "mediation_numerique_expositions": "Médiation, expositions, musée, numérique",
        "accessibilite_publics": "Accessibilité et accueil des publics",
        "etudes_ingenierie": "Études et ingénierie",
        "labels_passerelles": "Labels et passerelles",
    }

    def test_les_quatorze_familles_et_leurs_libelles(self) -> None:
        self.assertEqual(FAMILLES_LABELS, self.ATTENDUES)
        self.assertEqual(FAMILLES, tuple(self.ATTENDUES))

    def test_chaque_famille_a_sa_description(self) -> None:
        """La description part dans les prompts d'ingestion et sert de règle au
        relecteur : « eau_nature_domaine » ne se devine pas."""
        self.assertEqual(list(FAMILLES_DESCRIPTION), list(FAMILLES_LABELS))
        for code, description in FAMILLES_DESCRIPTION.items():
            self.assertTrue(description.strip(), code)

    def test_le_check_sql_dit_la_meme_chose(self) -> None:
        """Le CHECK qui fait foi est celui de la migration la PLUS RÉCENTE qui
        le pose : une scission le repose (drop + add), et comparer le référentiel
        d'aujourd'hui au premier CHECK écrit ferait échouer le test pour de bon.
        Les migrations sont horodatées par le CLI, donc l'ordre du glob est
        chronologique."""
        portantes = [
            p
            for p in sorted(MIGRATIONS.glob("*.sql"))
            if "familles <@ array[" in p.read_text(encoding="utf-8")
        ]
        self.assertTrue(portantes, "aucune migration ne pose le CHECK des familles")
        sql = portantes[-1].read_text(encoding="utf-8")
        tableau = re.search(r"familles <@ array\[(.*?)\]::text\[\]", sql, re.S)
        self.assertIsNotNone(tableau, "CHECK `familles <@ array[...]` absent de la migration")
        assert tableau is not None  # pour pyright
        litteraux = re.findall(r"'([a-z_]+)'", tableau.group(1))
        self.assertEqual(litteraux, list(FAMILLES_LABELS))

    def test_le_front_dit_la_meme_chose(self) -> None:
        """Le type `Famille` et `FAMILLE_OPTIONS` sont testés côté front ; ici
        on vérifie seulement que les quatorze CODES y sont, pour qu'un ajout
        backend ne puisse pas rester invisible à l'écran."""
        source = FRONT_FAMILLES.read_text(encoding="utf-8")
        for code in FAMILLES_LABELS:
            self.assertIn(f"'{code}'", source, code)

    def test_une_aide_ne_peut_porter_quune_famille_du_referentiel(self) -> None:
        base = {
            "slug": "fx",
            "nom": "Fixture",
            "organisme": "Org",
            "categorie": "region",
            "type": "subvention",
            "description": "d",
        }
        self.assertEqual(Aide.model_validate(base).familles, [])
        self.assertEqual(
            Aide.model_validate({**base, "familles": ["spectacles_manifestations"]}).familles,
            ["spectacles_manifestations"],
        )
        with self.assertRaises(ValidationError):
            Aide.model_validate({**base, "familles": ["musee"]})
        # `adjacente` et `hors_perimetre` sont des décisions de TRI de la skill
        # de prospection, pas des familles : elles doivent être refusées.
        for tri in ("adjacente", "hors_perimetre"):
            with self.assertRaises(ValidationError, msg=tri):
                Aide.model_validate({**base, "familles": [tri]})


class FamillesHeriteesTest(unittest.TestCase):
    """Les codes RETIRÉS du référentiel, et ce qu'ils valent encore.

    Un projet enregistré porte ses familles telles qu'elles ont été cochées ;
    rien ne les réécrit. Un code retiré sans alias déclarerait donc une famille
    qu'aucune aide ne porte, et `hors_famille` (déclaré non vide, intersection
    vide) écarterait TOUTES les aides taguées.
    """

    def test_un_code_herite_est_sorti_du_referentiel(self) -> None:
        for ancien in FAMILLES_HERITEES:
            self.assertNotIn(ancien, FAMILLES_LABELS, ancien)

    def test_un_heritage_ne_pointe_que_vers_des_familles_vivantes(self) -> None:
        for ancien, successeurs in FAMILLES_HERITEES.items():
            self.assertTrue(successeurs, ancien)
            for code in successeurs:
                self.assertIn(code, FAMILLES_LABELS, f"{ancien} → {code}")

    def test_le_front_porte_le_meme_alias(self) -> None:
        source = FRONT_FAMILLES.read_text(encoding="utf-8")
        for ancien, successeurs in FAMILLES_HERITEES.items():
            self.assertIn(f"{ancien}: [", source, ancien)
            for code in successeurs:
                self.assertIn(f"'{code}'", source, code)

    def test_aucune_aide_ne_porte_encore_un_code_herite(self) -> None:
        """L'alias est un filet pour les QUESTIONNAIRES déjà enregistrés, pas
        une permission d'écrire l'ancien code : `Aide.familles` le refuse, et ce
        test le redit sur le catalogue réel."""
        for chemin in sorted(AIDES_DIR.glob("*.yaml")):
            familles = load_aide(chemin).familles
            for ancien in FAMILLES_HERITEES:
                self.assertNotIn(ancien, familles, chemin.stem)


if __name__ == "__main__":
    unittest.main()
