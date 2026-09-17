"""Tests du comparateur d'extractions (scripts/comparer_aides.py).

Le point délicat est l'APPARIEMENT : deux modèles nomment rarement une même
exigence de la même façon, et un comparateur qui s'en tiendrait aux
identifiants déclarerait « manquantes » des conditions parfaitement retrouvées.
Le banc d'essai en tirerait un classement faux, et le classement décide du
modèle qu'on met en production sur 1 400 aides.

Run from backend/:  uv run pytest tests/test_comparer_aides.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import yaml  # noqa: E402
from comparer_aides import (  # noqa: E402
    Journal,
    Ligne,
    apparier_conditions,
    comparer,
    lire_log,
    tableau,
)

from aides_schema import Aide  # noqa: E402

BASE = {
    "slug": "ex-aide",
    "nom": "Aide d'exemple",
    "organisme": "Région",
    "categorie": "region",
    "type": "subvention",
    "description": "Une aide.",
}


def aide(conditions: list[dict], **kw) -> Aide:
    return Aide.model_validate({**BASE, "conditions": conditions, **kw})


COND_REF = [
    {
        "id": "ouvert-au-public",
        "text": "Le monument est ouvert au public au moins quarante jours par an.",
        "kind": "manual_check",
        "effect": "gate",
        "notes": "x",
        "quote": "ouvert au public au moins quarante jours par an",
    },
    {
        "id": "travaux-non-commences",
        "text": "Les travaux ne doivent pas avoir commencé.",
        "kind": "manual_check",
        "effect": "gate",
        "notes": "x",
        "quote": "les travaux ne doivent pas avoir commencé",
    },
    {
        "id": "depot-en-ligne",
        "text": "Le dossier se dépose en ligne.",
        "kind": "info",
    },
]


class TestAppariement(unittest.TestCase):
    def test_par_identifiant(self):
        paires, manquantes, en_trop = apparier_conditions(
            aide(COND_REF).conditions, aide(COND_REF).conditions
        )
        self.assertEqual(len(paires), 3)
        self.assertEqual((manquantes, en_trop), ([], []))

    def test_par_citation_malgre_un_id_different(self):
        candidat = [{**COND_REF[0], "id": "ouverture-publique"}, COND_REF[1], COND_REF[2]]
        paires, manquantes, _ = apparier_conditions(
            aide(COND_REF).conditions, aide(candidat).conditions
        )
        self.assertEqual(len(paires), 3)
        self.assertEqual(manquantes, [])

    def test_par_texte_sans_id_ni_citation_communs(self):
        candidat = [
            {
                "id": "autre-nom",
                "text": "Le monument est ouvert au public au moins 40 jours par an.",
                "kind": "info",
            }
        ]
        paires, manquantes, _ = apparier_conditions(
            aide(COND_REF[:1]).conditions, aide(candidat).conditions
        )
        self.assertEqual(len(paires), 1)
        self.assertEqual(manquantes, [])

    def test_deux_textes_sans_rapport_ne_sapparient_pas(self):
        candidat = [{"id": "z", "text": "Le dossier comporte un devis détaillé.", "kind": "info"}]
        paires, manquantes, en_trop = apparier_conditions(
            aide(COND_REF[:1]).conditions, aide(candidat).conditions
        )
        self.assertEqual(paires, [])
        self.assertEqual(len(manquantes), 1)
        self.assertEqual(len(en_trop), 1)

    def test_une_condition_candidate_ne_sert_quune_fois(self):
        reference = [COND_REF[0], {**COND_REF[0], "id": "doublon"}]
        paires, manquantes, _ = apparier_conditions(
            aide(reference).conditions, aide(COND_REF[:1]).conditions
        )
        self.assertEqual(len(paires), 1)
        self.assertEqual(len(manquantes), 1)

    def test_deux_fenetres_sur_le_meme_passage_sapparient(self):
        """Deux modèles ne coupent pas leur citation aux mêmes bornes.

        Cas réel (or-glm sur hdf-jardins-en-scene, 2026-09-06) : la référence
        FINIT sur « EPCC communément appelé lieu intermédiaire », le candidat
        COMMENCE par là. Ni égalité, ni inclusion, et les `text` divergeaient
        trop — la même exigence DÉCISIVE était comptée manquée ET en trop.
        """
        reference = [
            {
                "id": "beneficiaires-eligibles",
                "text": "Associations, collectivités locales, EPCI et EPCC.",
                "kind": "info",
                "quote": (
                    "Associations, [...] Collectivités locales, [...] EPCI, "
                    "[...] EPCC communément appelé lieu intermédiaire"
                ),
            }
        ]
        candidat = [
            {
                "id": "beneficiaire-association-collectivite-epcc",
                "text": "Le porteur est une association, une collectivité, un EPCI ou un EPCC.",
                "kind": "info",
                "quote": (
                    "EPCC communément appelé lieu intermédiaire ou lieu de "
                    "programmation en territoire."
                ),
            }
        ]
        paires, manquantes, en_trop = apparier_conditions(
            aide(reference).conditions, aide(candidat).conditions
        )
        self.assertEqual(len(paires), 1)
        self.assertEqual((manquantes, en_trop), ([], []))

    def test_une_quote_incluse_dans_lautre_sapparie(self):
        """Le candidat cite le paragraphe entier là où la référence cite sa fin."""
        courte = "appréciées au regard des caractéristiques suivantes dans la limite des crédits"
        longue = f"Les propositions seront {courte} disponibles :"
        reference = [
            {
                "id": "a",
                "text": "Dans la limite des crédits.",
                "kind": "info",
                "quote": courte,
            }
        ]
        candidat = [
            {"id": "b", "text": "Critères d'appréciation.", "kind": "info", "quote": longue}
        ]
        paires, _, _ = apparier_conditions(aide(reference).conditions, aide(candidat).conditions)
        self.assertEqual(len(paires), 1)

    def test_un_bloc_commun_court_nappartie_pas(self):
        """Le garde-fou : sans lui, tout ce qui partage une tournure s'apparie.

        Le test est géométrique (fenêtres bord à bord), pas un seuil de
        similarité — mais il exige quand même un chevauchement substantiel.
        """
        reference = [
            {
                "id": "a",
                "text": "Le monument est classé.",
                "kind": "info",
                "quote": "le monument doit être classé au titre des monuments",
            }
        ]
        candidat = [
            {
                "id": "b",
                "text": "Le dossier est déposé en ligne.",
                "kind": "info",
                "quote": "au titre des monuments historiques, le dossier se dépose",
            }
        ]
        paires, manquantes, en_trop = apparier_conditions(
            aide(reference).conditions, aide(candidat).conditions
        )
        # « au titre des monuments » ne fait que 23 caractères : sous le seuil.
        self.assertEqual(paires, [])
        self.assertEqual((len(manquantes), len(en_trop)), (1, 1))


class TestComparaison(unittest.TestCase):
    def test_identique_donne_cent(self):
        comp = comparer(aide(COND_REF), aide(COND_REF))
        self.assertEqual(comp.score, 100.0)
        self.assertEqual(comp.rappel_gates, 1.0)

    def test_gate_manquee_fait_chuter_le_rappel(self):
        comp = comparer(aide(COND_REF), aide(COND_REF[1:]))
        self.assertEqual(comp.gates_reference, 2)
        self.assertEqual(comp.gates_retrouvees, 1)
        self.assertEqual(comp.rappel_gates, 0.5)
        self.assertIn("ouvert-au-public [manual_check/gate]", comp.manquantes)
        self.assertLess(comp.score, 80)

    def test_condition_inventee_fait_chuter_la_precision(self):
        candidat = [*COND_REF, {"id": "invente", "text": "Une exigence absente.", "kind": "info"}]
        comp = comparer(aide(COND_REF), aide(candidat))
        self.assertEqual(comp.en_trop, ["invente [info/info]"])
        self.assertAlmostEqual(comp.precision, 0.75)

    def test_typage_divergent_repere(self):
        candidat = [{**COND_REF[0], "kind": "discretionary", "effect": "info"}, *COND_REF[1:]]
        comp = comparer(aide(COND_REF), aide(candidat))
        champs = {d.champ for d in comp.divergences}
        self.assertEqual(champs, {"kind", "effect"})

    def test_champs_de_laide_compares(self):
        comp = comparer(
            aide(COND_REF, financement={"taux_max": 30}),
            aide(COND_REF, financement={"taux_max": 80}),
        )
        self.assertEqual(len(comp.champs_divergents), 1)
        self.assertEqual(comp.champs_divergents[0].champ, "financement.taux_max")

    def test_citations_verifiees_contre_les_snapshots(self):
        documents = [
            ("a.md", "Le monument est ouvert au public au moins quarante jours par an.", "text")
        ]
        comp = comparer(aide(COND_REF), aide(COND_REF), documents)
        self.assertEqual(comp.citations_candidat, 2)
        self.assertEqual(comp.citations_verifiees, 1)
        self.assertEqual(comp.quotes_ok, 0.5)

    def test_exigence_traitee_par_un_hard_filter_est_creditee(self):
        """La doctrine PRESCRIT le filtre structuré pour un champ structuré.

        La référence de hdf-jardins-en-scene porte les deux et le dit : sa
        condition `projet-territoire-regional` a pour notes « Redondant avec
        hard_filters.regions — conservé pour l'affichage ». Un candidat qui ne
        garde que le filtre applique la même restriction ; le compter manqué
        pénalisait le candidat pour avoir suivi la doctrine.
        """
        territoire = {
            "id": "projet-territoire-regional",
            "text": "Le projet doit se dérouler sur le territoire régional.",
            "kind": "auto",
            "effect": "gate",
            "field": "monument.region",
            "predicate": {"eq": "hauts-de-france"},
        }
        reference = aide([territoire], hard_filters={"regions": ["hauts-de-france"]})
        candidat = aide([], hard_filters={"regions": ["hauts-de-france"]})
        comp = comparer(reference, candidat)
        self.assertEqual(comp.couvertes_par_filtre, ["projet-territoire-regional"])
        self.assertEqual(comp.decisives_retrouvees, 1)
        self.assertEqual(comp.gates_retrouvees, 1)
        self.assertEqual(comp.manquantes, [])

    def test_un_hard_filter_sur_une_autre_valeur_ne_credite_rien(self):
        """Sinon le crédit masquerait une vraie erreur de périmètre."""
        territoire = {
            "id": "projet-territoire-regional",
            "text": "Le projet doit se dérouler sur le territoire régional.",
            "kind": "auto",
            "effect": "gate",
            "field": "monument.region",
            "predicate": {"eq": "hauts-de-france"},
        }
        comp = comparer(
            aide([territoire], hard_filters={"regions": ["hauts-de-france"]}),
            aide([], hard_filters={"regions": ["bretagne"]}),
        )
        self.assertEqual(comp.couvertes_par_filtre, [])
        self.assertEqual(comp.decisives_retrouvees, 0)

    def test_une_composite_est_signalee(self):
        """Une liste repliée en une condition rend le rappel minorant.

        Mesuré deux fois : les 11 critères de sélection de
        hdf-jardins-en-scene repliés en 2 conditions `discretionary/info`. Les
        exigences repliées sont réellement inertes pour le diagnostic, mais
        elles sont citées — le dire évite de conclure « le modèle ne les a pas
        vues ».
        """
        composite = {
            "id": "selection-criteres",
            "text": (
                "Les propositions sont appréciées au regard de la pertinence du projet, "
                "de la cohérence de l'espace, des actions culturelles, de la gratuité "
                "pour le public, de la compétence du porteur, de l'adéquation des "
                "ressources, de la nature des partenariats, de la dynamique "
                "participative, de la diversité des publics et des enjeux "
                "environnementaux."
            ),
            "kind": "discretionary",
            "effect": "info",
            "quote": "Les propositions seront appréciées au regard des caractéristiques suivantes",
        }
        comp = comparer(aide(COND_REF), aide([*COND_REF, composite]))
        self.assertEqual(comp.composites, ["selection-criteres"])
        self.assertTrue(any("MINORANT" in a for a in comp.avertissements()))

    def test_une_condition_courte_nest_pas_une_composite(self):
        comp = comparer(aide(COND_REF), aide(COND_REF))
        self.assertEqual(comp.composites, [])


LOG = """\
==============================================================================
ex-aide — run précédent
==============================================================================

--- tour 1 — entrée 100 (+0 cache) / sortie 10 — cumul $9.9999 — tool_calls
[appel] zorglub({})

==============================================================================
ex-aide — 2026-09-06T09:00:00+00:00 — ingestion glm-flash / vérification ds-pro
==============================================================================

--- tour 1 — entrée 23000 (+0 cache) / sortie 210 — cumul $0.0071 — tool_calls
[appel] snapshotter({"url": "https://example.org"})
[sortie] Archivé.

--- tour 2 — entrée 26000 (+0 cache) / sortie 4000 — cumul $0.0180 — tool_calls
[appel] ecrire_aide({"yaml_texte": "..."})
[sortie] Écrit.
[*] élagage : 12000 caractères retirés (120000 jetons)
[*] relance 1/2 : review manquante
[*] avertissement de budget ($1.6000 / $1.50)
[*] terminé en 2 tour(s), $0.0180 / $1.50, durée 87 s
"""


class TestLireLog(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.chemin = Path(self._tmp.name) / "ingest-ex-aide.log"
        self.chemin.write_text(LOG, encoding="utf-8")

    def test_lit_le_dernier_run_seulement(self):
        journal = lire_log(self.chemin)
        self.assertEqual(journal.tours, 2)
        self.assertEqual(journal.cout_usd, 0.018)
        self.assertNotIn("zorglub", journal.appels)

    def test_duree_outils_et_incidents(self):
        journal = lire_log(self.chemin)
        self.assertEqual(journal.duree_s, 87.0)
        self.assertEqual(journal.appels, {"snapshotter": 1, "ecrire_aide": 1})
        self.assertEqual(journal.elagages, 1)
        self.assertEqual(journal.relances, 1)
        self.assertTrue(journal.budget_epuise)


class TestTableau(unittest.TestCase):
    def test_synthese_classee_et_echecs_visibles(self):
        bon = Ligne(
            "glm-flash",
            "ex-aide",
            comparer(aide(COND_REF), aide(COND_REF)),
            Journal(tours=12, cout_usd=0.17, duree_s=90),
        )
        moins_bon = Ligne(
            "ds-flash",
            "ex-aide",
            comparer(aide(COND_REF), aide(COND_REF[1:])),
            Journal(tours=20, cout_usd=0.65, duree_s=200),
        )
        texte = tableau([moins_bon, bon], absents=[("gemini-flash", "ex-aide")])
        self.assertIn("| glm-flash | ex-aide |", texte)
        self.assertIn("$0.170", texte)
        self.assertIn("90 s", texte)
        self.assertIn("| gemini-flash | ex-aide | — |", texte)
        self.assertIn("**échec**", texte)
        # Le meilleur modèle passe en tête de la moyenne.
        self.assertLess(texte.index("**glm-flash**"), texte.index("**ds-flash**"))


class TestYamlDuDepot(unittest.TestCase):
    # Des aides VERSIONNÉES, et c'est le point : le catalogue de travail contient
    # aussi des extractions non encore committées (13 sur 215 au 2026-09-06).
    # Une de celles-là ferait passer le test en local et planter en CI.
    AIDES = ("idf-fonds-tourisme", "94-soutien-projets-histoire-archives-memoire")

    def test_des_aides_reelles_se_comparent_a_elles_memes(self):
        dossier = Path(__file__).resolve().parent.parent / "data" / "aides"
        for slug in self.AIDES:
            with self.subTest(slug=slug):
                chemin = dossier / f"{slug}.yaml"
                self.assertTrue(chemin.exists(), f"{slug}.yaml manque au dépôt")
                reelle = Aide.model_validate(yaml.safe_load(chemin.read_text(encoding="utf-8")))
                self.assertEqual(comparer(reelle, reelle).score, 100.0)


if __name__ == "__main__":
    unittest.main()
