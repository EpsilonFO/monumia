"""La fiche rédigée d'une aide : schéma, projection vers le front, lint, script.

Run from backend/:  uv run pytest tests/test_fiche_aide.py -q
"""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lint_aides_data import check_fiche  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from rediger_fiches import (  # noqa: E402
    ENTETE_FICHE,
    bloc_yaml,
    controler,
    ecrire_fiche,
    normaliser,
    retirer_fiche,
)

from aides_schema import Aide, Fiche, load_all_aides, load_facts, load_pending_facts  # noqa: E402
from eligibility_engine import (  # noqa: E402
    aide_display_dict,
    aide_fiche_dict,
    run_deterministic_diagnostic,
)
from routers.aides import _to_camel, retirer_les_modalites  # noqa: E402

FACTS = {**load_facts(), **load_pending_facts()}

CONDITIONS = [
    {
        "id": "travaux-non-commences",
        "text": "Les travaux ne doivent pas avoir commencé.",
        "kind": "manual_check",
        "effect": "gate",
        "quote": "Les travaux ne doivent pas avoir commencé.",
    },
    {
        "id": "taux-40",
        "text": "Le taux moyen est de 40 %.",
        "kind": "info",
        "quote": "40 % en moyenne",
    },
]

FICHE = {
    "redige_le": "2026-09-23",
    "titre": "Subvention pour un immeuble classé",
    "financeur": "DRAC · ministère de la Culture",
    "chapeau": "Une subvention de l'État pour les parties classées.",
    "montant": {"valeur": "40 % en moyenne", "detail": "Des travaux éligibles"},
    "essentiel": {"delai": {"valeur": "2 à 6 mois"}},
    "en_bref": {"puces": [{"ton": "couvert", "texte": "Les parties classées."}]},
    "conseils": [
        {"titre": "Attendez avant de démarrer.", "texte": "…", "condition": "travaux-non-commences"}
    ],
    "etapes": [{"titre": "Déposez en ligne"}],
    "points": {
        "travaux-non-commences": {"titre": "Ne pas commencer avant le dépôt"},
        "taux-40": {
            "titre": "40 % en moyenne",
            "resume": "Le taux moyen est de 40 %.",
            "theme": "montant",
        },
    },
}


def _aide(fiche: dict | None = FICHE, conditions: list[dict] = CONDITIONS, **over) -> Aide:
    return Aide.model_validate(
        {
            "slug": "fixture-fiche",
            "nom": "Fixture",
            "organisme": "DRAC",
            "categorie": "etat_drac",
            "type": "subvention",
            "description": "d",
            "conditions": conditions,
            "source": {"verified_at": "2026-09-01"},
            **({"fiche": fiche} if fiche is not None else {}),
            **over,
        }
    )


class TestSchema(unittest.TestCase):
    def test_une_fiche_valide_se_charge(self):
        aide = _aide()
        assert aide.fiche is not None
        self.assertEqual(aide.fiche.redige_le, date(2026, 9, 23))
        self.assertEqual(aide.fiche.points["taux-40"].theme, "montant")

    def test_une_fiche_en_retard_n_empeche_pas_l_aide_de_se_charger(self):
        """La veille retire des conditions sans toucher à la fiche : l'aide doit
        rester chargeable (le moteur la sert), la fiche passe « à relire »."""
        fiche = {
            **FICHE,
            "points": {"inexistante": {"titre": "t"}},
            "conseils": [{"titre": "t", "texte": "x", "condition": "ailleurs"}],
        }
        aide = _aide(fiche)
        avertissements = check_fiche(aide)
        self.assertTrue(any("inexistante" in a and "ailleurs" in a for a in avertissements))
        self.assertTrue(any("sans point" in a for a in avertissements))

    def test_rubrique_hors_liste_refusee(self):
        fiche = {**FICHE, "points": {"taux-40": {"titre": "t", "theme": "divers"}}}
        with self.assertRaises(ValidationError):
            _aide(fiche)

    def test_le_catalogue_se_charge_avec_ses_fiches(self):
        """Les dix fiches reprises de la maquette passent le schéma, chacune avec
        un point par condition."""
        avec = [a for a in load_all_aides().values() if a.fiche]
        self.assertGreaterEqual(len(avec), 10)
        for aide in avec:
            assert aide.fiche is not None
            self.assertEqual(set(aide.fiche.points), {c.id for c in aide.conditions}, aide.slug)


class TestProjection(unittest.TestCase):
    def test_la_carte_part_avec_le_diagnostic(self):
        carte = aide_display_dict(_aide())["carte"]
        self.assertEqual(
            carte,
            {
                "titre": "Subvention pour un immeuble classé",
                "financeur": "DRAC · ministère de la Culture",
                "chapeau": "Une subvention de l'État pour les parties classées.",
                "montant": {"valeur": "40 % en moyenne", "detail": "Des travaux éligibles"},
            },
        )

    def test_sans_fiche_pas_de_carte(self):
        self.assertIsNone(aide_display_dict(_aide(fiche=None))["carte"])

    def test_le_reste_de_la_fiche_ne_part_pas_avec_le_diagnostic(self):
        d = aide_display_dict(_aide())
        self.assertNotIn("fiche", d)
        self.assertNotIn("reglement", d)

    def test_la_fiche_complete_passe_par_get_aide(self):
        d = _to_camel(aide_fiche_dict(_aide()))
        self.assertEqual(d["verifieLe"], "2026-09-01")
        self.assertEqual(d["fiche"]["redigeLe"], "2026-09-23")
        self.assertEqual(d["fiche"]["enBref"]["puces"][0]["ton"], "couvert")
        self.assertEqual(d["fiche"]["points"]["taux-40"]["theme"], "montant")
        self.assertEqual(
            d["reglement"][0],
            {
                "id": "travaux-non-commences",
                "text": "Les travaux ne doivent pas avoir commencé.",
                "quote": "Les travaux ne doivent pas avoir commencé.",
                "kind": "manual_check",
                "effect": "gate",
                "derogationPossible": False,
            },
        )

    def test_sans_fiche_le_reglement_reste_servi(self):
        d = aide_fiche_dict(_aide(fiche=None))
        self.assertIsNone(d["fiche"])
        self.assertEqual([c["id"] for c in d["reglement"]], ["travaux-non-commences", "taux-40"])

    def test_aide_a_venir_hors_offre_perd_le_financeur_de_sa_carte(self):
        """Le financeur court est l'organisme en quelques mots : il part avec lui."""
        d = _to_camel(aide_display_dict(_aide()))
        carte = d["carte"]
        retirer_les_modalites(d)
        self.assertIsNone(d["carte"]["financeur"])
        self.assertEqual(d["carte"]["titre"], "Subvention pour un immeuble classé")
        # Copie : la carte d'origine n'est pas touchée.
        self.assertEqual(carte["financeur"], "DRAC · ministère de la Culture")

    def test_chaque_verdict_porte_l_id_de_sa_condition(self):
        """La page relie un verdict à son point du règlement par l'id, jamais
        par le texte (qu'une veille peut retoucher)."""
        aide = _aide(fiche=None)
        res = run_deterministic_diagnostic(
            {aide.slug: aide},
            FACTS,
            {"id": "m", "nom": "M", "protection": "classe", "proprietaire": "public_commune"},
            3000,
        )
        match = next(
            m
            for bucket in ("aidesEligibles", "aidesPotentiellementEligibles", "aidesNonEligibles")
            for m in res[bucket]
        )
        ids = {e["conditionId"] for e in match["llmEvaluation"]["evaluations"]}
        self.assertEqual(ids, {"travaux-non-commences", "taux-40"})


class TestLint(unittest.TestCase):
    def test_fiche_anterieure_a_la_source_signalee(self):
        aide = _aide(source={"verified_at": "2026-10-01"})
        self.assertTrue(any("à relire" in a for a in check_fiche(aide)))

    def test_tiret_long_signale(self):
        aide = _aide({**FICHE, "chapeau": "Une aide — pour tous."})
        self.assertTrue(any("tiret long" in a for a in check_fiche(aide)))

    def test_fiche_propre_sans_avertissement(self):
        self.assertEqual(check_fiche(_aide()), [])

    def test_aide_sans_fiche_sans_avertissement(self):
        self.assertEqual(check_fiche(_aide(fiche=None)), [])


class TestScriptRedaction(unittest.TestCase):
    YAML = "slug: x\nnom: X\ntags:\n  - a\n"

    def _fiche(self) -> Fiche:
        aide = _aide()
        assert aide.fiche is not None
        return aide.fiche

    def test_ecrire_puis_reecrire_ne_duplique_pas(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "x.yaml"
            chemin.write_text(self.YAML, encoding="utf-8")
            ecrire_fiche(chemin, self._fiche())
            premier = chemin.read_text(encoding="utf-8")
            ecrire_fiche(chemin, self._fiche())
            self.assertEqual(chemin.read_text(encoding="utf-8"), premier)
            self.assertEqual(premier.count("\nfiche:"), 1)
            self.assertTrue(premier.startswith(self.YAML))
            self.assertIn(ENTETE_FICHE, premier)

    def test_retirer_une_fiche_absente_ne_change_rien(self):
        self.assertEqual(retirer_fiche(self.YAML), self.YAML)

    def test_refuse_une_fiche_qui_n_est_pas_le_dernier_bloc(self):
        texte = self.YAML + "fiche:\n  titre: t\ndemarche: d\n"
        with self.assertRaisesRegex(ValueError, "dernier"):
            retirer_fiche(texte)

    def test_normaliser_retire_ce_que_le_modele_n_a_pas_a_decider(self):
        aide = _aide()
        fiche = Fiche.model_validate(
            {
                **FICHE,
                "redige_le": None,
                "essentiel": {"calendrier": {"valeur": "Ouvert toute l'année", "detail": "d"}},
                "points": {
                    "travaux-non-commences": {"titre": "t", "theme": "projet"},
                    "taux-40": {"titre": "t", "theme": "montant"},
                },
            }
        )
        fiche = normaliser(aide, fiche, date(2026, 9, 24))
        self.assertEqual(fiche.redige_le, date(2026, 9, 24))
        assert fiche.essentiel.calendrier is not None
        self.assertIsNone(fiche.essentiel.calendrier.valeur)
        self.assertEqual(fiche.essentiel.calendrier.detail, "d")
        self.assertIsNone(fiche.points["travaux-non-commences"].theme)
        self.assertEqual(fiche.points["taux-40"].theme, "montant")

    def test_controler_refuse_un_point_manquant_et_un_tiret(self):
        aide = _aide()
        fiche = Fiche.model_validate(
            {**FICHE, "chapeau": "Une aide — pour tous.", "points": {"taux-40": {"titre": "t"}}}
        )
        erreurs = controler(aide, fiche)
        self.assertTrue(any("sans point" in e for e in erreurs), erreurs)
        self.assertTrue(any("sans rubrique" in e for e in erreurs), erreurs)
        self.assertTrue(any("tiret" in e for e in erreurs), erreurs)

    def test_controler_accepte_la_fiche_de_reference(self):
        self.assertEqual(controler(_aide(), self._fiche()), [])

    def test_bloc_yaml_relu_donne_la_meme_fiche(self):
        import yaml

        relu = yaml.safe_load(bloc_yaml(self._fiche()))["fiche"]
        self.assertEqual(Fiche.model_validate(relu), self._fiche())


if __name__ == "__main__":
    unittest.main()
