"""Tests de la reformulation de question d'un fait existant (décision `R1-reformulation`).

Trois étages : l'outil de l'agent et ses refus (`scripts/ingestion/reformulation.py`,
avec un juge P1 factice), la remontée en case et l'application au run suivant
(`catalogue/reformulations.py`), le registre et le lint. Rien ne touche au
réseau ni à `backend/data/`.

Run from backend/:  uv run pytest tests/test_reformulation_fait.py
"""

import dataclasses
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ingestion.atelier import Atelier  # noqa: E402
from ingestion.faits import citations_du_fait  # noqa: E402
from ingestion.outils import outils_pour  # noqa: E402

from aides_schema import Aide, charger_yaml, load_facts  # noqa: E402
from catalogue import reformulations as rf  # noqa: E402
from catalogue import registre as registre_mod  # noqa: E402
from catalogue.cases import Reponse  # noqa: E402
from catalogue.journal import Vue  # noqa: E402
from tests.test_ingestion_outils import BaseOutils, aide_yaml  # noqa: E402

QUESTION = "Le monument est-il ouvert au public ?"
BONNE = "Le monument ou son jardin est-il ouvert au public ?"
QUI_DERIVE = "Le monument est-il ouvert au public toute l'année ?"
QUI_INVERSE = "Le monument est-il ouvert au public ou fermé ?"
FAUSSE = "Le monument est-il parfois ouvert au public ?"

FACTS_YAML = f"""\
# En-tête : un commentaire qui doit survivre à la réécriture.
monument_ouvert_au_public:
  type: boolean
  scope: monument
  # Commentaire dans le bloc du fait.
  question: {QUESTION}
  help: >-
    Ouvert au public signifie accessible aux visiteurs, gratuitement ou non,
    au moins une partie de l'année.
surface_jardin_m2:
  type: integer
  scope: monument
  question: Quelle est la surface du jardin ?
  unit: m²
visites_guidees:
  type: boolean
  scope: monument
  question: Proposez-vous des visites guidées ?
  pertinent_si:
    fact: monument_ouvert_au_public
    predicate: {{eq: true}}
"""

SEUILS = {"citations_max": 40.0, "derive_max": 0.25, "similarite_min": 0.5}

# Ce que Jev répondrait, question par question : la probabilité qu'un demandeur
# qui répond oui / non remplisse « La programmation se déroule dans un jardin
# ouvert au public ». Le prédicat est `eq: true`.
JUGEMENTS = {
    QUESTION: {"oui": 0.95, "non": 0.05},
    BONNE: {"oui": 0.9, "non": 0.08},
    QUI_DERIVE: {"oui": 0.6, "non": 0.05},  # pas de désaccord, mais 0,35 de dérive
    QUI_INVERSE: {"oui": 0.92, "non": 0.85},  # « non » serait écarté à tort
}


class FauxJuge:
    """Le juge P1, sans réseau : une table par question, None pour une panne."""

    def __init__(self, table=None):
        self.table = JUGEMENTS if table is None else table
        self.appels = []

    def juger(self, g):
        self.appels.append(g.fait.question)
        probas = self.table.get(" ".join(g.fait.question.split()))
        if probas is None:
            return None
        return {r.id: probas[r.id] for r in g.reponses}


class BaseReformulation(BaseOutils):
    def setUp(self):
        super().setUp()
        self.atelier.facts_path.write_text(FACTS_YAML, encoding="utf-8")
        load_facts.cache_clear()
        self.facts = load_facts(self.atelier.facts_path)
        # Le catalogue que lisent les citations : un dossier à nous, jamais le vrai.
        self.catalogue = self.racine / "catalogue"
        self.catalogue.mkdir()
        for slug in ("aide-a", "aide-b"):
            (self.catalogue / f"{slug}.yaml").write_text(
                aide_yaml("ouvert au public", slug=slug), encoding="utf-8"
            )
        patch = mock.patch.object(
            Atelier,
            "dossiers_catalogue",
            new_callable=mock.PropertyMock,
            return_value=(self.catalogue,),
        )
        patch.start()
        self.addCleanup(patch.stop)
        self.partage = self.racine / "reformulations-partagees.yaml"
        for cible, valeur in (
            ("catalogue.reformulations.REFORMULATIONS", self.partage),
            ("catalogue.registre.seuils_reformulation", lambda: dict(SEUILS)),
        ):
            p = mock.patch(cible, valeur)
            p.start()
            self.addCleanup(p.stop)
        self.juge = FauxJuge()
        self.construire()

    def construire(self, *, reformulation=True, juge=None):
        self.outils, self.etat = outils_pour(
            self.atelier,
            facts=dict(self.facts),
            pending=self.pending,
            fetcheur=self.fetcheur,
            reformulation=reformulation,
            juge_polarite=juge or self.juge,
        )
        self.table = {o.name: o for o in self.outils}

    def lire_et_inspecter(self, fact_id="monument_ouvert_au_public"):
        self.appeler("detail_fait", fact_id=fact_id)
        return self.appeler("conditions_du_fait", fact_id=fact_id)

    def proposer(self, question=BONNE, help="", fact_id="monument_ouvert_au_public"):
        return self.appeler(
            "proposer_reformulation",
            fact_id=fact_id,
            question=question,
            help=help,
            justification=(
                "La source finance un jardin ouvert au public autour d'un monument fermé : "
                "son propriétaire répondrait non à une question qui ne nomme que le monument."
            ),
        )


class TestCitations(unittest.TestCase):
    def test_les_quatre_lieux_de_citation(self):
        facts = {k: v for k, v in _facts().items()}
        aide = Aide.model_validate(
            charger_yaml(aide_yaml("q", slug="aide-x"))
            | {
                "applies_if": {"fact": "monument_ouvert_au_public", "predicate": {"eq": True}},
            }
        )
        brut = charger_yaml(aide_yaml("q", slug="aide-y"))
        brut["conditions"].append(
            {
                "id": "visites",
                "text": "Des visites sont proposées.",
                "kind": "user_fact",
                "effect": "gate",
                "fact": "visites_guidees",
                "predicate": {"eq": True},
                "applies_if": {"fact": "monument_ouvert_au_public", "predicate": {"eq": True}},
            }
        )
        aide_y = Aide.model_validate(brut)
        citations = citations_du_fait(
            {"aide-x": aide, "aide-y": aide_y}, facts, "monument_ouvert_au_public"
        )
        lieux = sorted((c.lieu, c.ref) for c in citations)
        self.assertEqual(
            lieux,
            [
                ("applies_if d'aide", "aide-x"),
                ("applies_if de condition", "aide-y#visites"),
                ("condition", "aide-x#ouvert-au-public"),
                ("condition", "aide-y#ouvert-au-public"),
                ("pertinent_si", "visites_guidees"),
            ],
        )
        gate = next(c for c in citations if c.ref == "aide-x#ouvert-au-public")
        self.assertIn('user_fact/gate {"eq": true}', gate.ligne())


def _facts():
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(FACTS_YAML)
    load_facts.cache_clear()
    try:
        return dict(load_facts(Path(f.name)))
    finally:
        Path(f.name).unlink()
        load_facts.cache_clear()


class TestOutils(BaseReformulation):
    def test_l_outil_n_est_expose_qu_a_la_demande(self):
        self.assertIn("proposer_reformulation", self.table)
        self.assertIn("conditions_du_fait", self.table)
        self.construire(reformulation=False)
        self.assertNotIn("proposer_reformulation", self.table)
        self.assertIn("conditions_du_fait", self.table)

    def test_conditions_du_fait_liste_et_trace(self):
        sortie = self.appeler("conditions_du_fait", fact_id="monument_ouvert_au_public")
        self.assertIn("cité 3 fois", sortie)
        self.assertIn("aide-a#ouvert-au-public", sortie)
        self.assertIn("[pertinent_si]", sortie)
        self.assertIn("monument_ouvert_au_public", self.etat.faits_inspectes)

    def test_l_aide_en_cours_est_lue_depuis_l_atelier(self):
        self.atelier.yaml_path.write_text(aide_yaml("ouvert au public"), encoding="utf-8")
        sortie = self.appeler("conditions_du_fait", fact_id="monument_ouvert_au_public")
        self.assertIn("ex-aide#ouvert-au-public", sortie)
        self.assertIn("cité 4 fois", sortie)


class TestRefus(BaseReformulation):
    def assertRefus(self, sortie, motif):
        self.assertTrue(sortie.startswith("ERREUR"), sortie)
        self.assertIn(motif, sortie)
        self.assertIn("Garde la question actuelle", sortie)
        self.assertFalse(self.atelier.reformulations_path.exists())

    def test_1_fait_absent_de_facts_yaml(self):
        self.assertRefus(self.proposer(fact_id="inconnu"), "n'est pas un fait de facts.yaml")

    def test_2_lecture_exigee(self):
        self.assertRefus(self.proposer(), "`detail_fait` et `conditions_du_fait`")
        self.appeler("detail_fait", fact_id="monument_ouvert_au_public")
        self.assertRefus(self.proposer(), "`conditions_du_fait`")

    def test_3_type_non_juge(self):
        self.lire_et_inspecter("surface_jardin_m2")
        self.assertRefus(
            self.proposer(question="Quelle est la surface du parc ?", fact_id="surface_jardin_m2"),
            "de type integer",
        )

    def test_4_fait_trop_cite(self):
        self.lire_et_inspecter()
        with mock.patch(
            "catalogue.registre.seuils_reformulation", lambda: {**SEUILS, "citations_max": 2}
        ):
            self.assertRefus(self.proposer(), "cité 3 fois (2 au plus)")

    def test_5_forme(self):
        self.lire_et_inspecter()
        self.assertRefus(
            self.proposer(question="Acceptez-vous d'ouvrir le monument au public ?"),
            "PROMESSE",
        )

    def test_6_tournure_trop_eloignee(self):
        self.lire_et_inspecter()
        self.assertRefus(
            self.proposer(question="Combien de visiteurs accueillez-vous chaque année ?"),
            "s'éloigne trop",
        )

    def test_7_une_autre_reformulation_attend(self):
        self.lire_et_inspecter()
        rf.deposer(
            {"fact": "monument_ouvert_au_public", "slug": "autre-aide", "question": "x"},
            self.partage,
            remplacer=False,
        )
        self.assertRefus(self.proposer(), "proposée par `autre-aide` attend")

    def test_8_un_desaccord_nouveau(self):
        self.lire_et_inspecter()
        self.assertRefus(self.proposer(question=QUI_INVERSE), "écarterait à tort « Non »")

    def test_8_une_derive_trop_forte(self):
        self.lire_et_inspecter()
        self.assertRefus(self.proposer(question=QUI_DERIVE), "dérive 0.35")

    def test_8_jev_en_panne(self):
        self.lire_et_inspecter()
        self.assertRefus(self.proposer(question=FAUSSE), "n'a pas pu rejuger")

    def test_8_jev_coupe(self):
        """`MONUMIA_ESPACE=0` (conftest) et aucun juge injecté : rien ne garantit le sens."""
        self.construire()
        self.juge = None
        self.outils, self.etat = outils_pour(
            self.atelier,
            facts=dict(self.facts),
            pending=self.pending,
            fetcheur=self.fetcheur,
            reformulation=True,
        )
        self.table = {o.name: o for o in self.outils}
        self.lire_et_inspecter()
        self.assertRefus(self.proposer(), "coupé")

    def test_les_refus_se_comptent(self):
        self.proposer()
        self.lire_et_inspecter()
        self.proposer()
        m = self.etat.mesures_espace(None)
        self.assertEqual((m["reformulations_refusees"], m["reformulations_proposees"]), (1, 1))


class TestSucces(BaseReformulation):
    def test_la_proposition_s_ecrit_dans_l_atelier(self):
        self.lire_et_inspecter()
        sortie = self.proposer(help="Un jardin ouvert compte, même si le bâtiment est fermé.")
        self.assertIn("proposée", sortie)
        entree = rf.lire(self.atelier.reformulations_path)["monument_ouvert_au_public"]
        self.assertEqual(entree["question_origine"], QUESTION)
        self.assertEqual(entree["question"], BONNE)
        self.assertEqual(entree["slug"], "ex-aide")
        self.assertEqual(entree["citations"], 3)
        self.assertEqual(entree["p1"], {"gates": 2, "derive": 0.05})
        self.assertIn("Un jardin ouvert compte", entree["help"])
        # Les deux gates ont été jugées avec l'ancienne puis la nouvelle question.
        self.assertEqual(sorted(set(self.juge.appels)), sorted({QUESTION, BONNE}))
        self.assertEqual(list(self.etat.reformulations), ["monument_ouvert_au_public"])

    def test_sans_help_l_aide_actuelle_reste(self):
        self.lire_et_inspecter()
        self.proposer()
        entree = rf.lire(self.atelier.reformulations_path)["monument_ouvert_au_public"]
        self.assertEqual(entree["help"], entree["help_origine"])

    def test_le_second_appel_remplace(self):
        self.lire_et_inspecter()
        self.proposer()
        table = {
            **JUGEMENTS,
            "Le monument ou ses jardins sont-ils ouverts au public ?": JUGEMENTS[BONNE],
        }
        self.juge.table = table
        sortie = self.proposer(question="Le monument ou ses jardins sont-ils ouverts au public ?")
        self.assertIn("remplace", sortie)
        entrees = rf.lire(self.atelier.reformulations_path)
        self.assertEqual(len(entrees), 1)
        self.assertIn("ses jardins", entrees["monument_ouvert_au_public"]["question"])

    def test_une_seule_par_aide(self):
        self.lire_et_inspecter()
        self.proposer()
        self.lire_et_inspecter("visites_guidees")
        sortie = self.proposer(
            question="Proposez-vous des visites guidées du monument ?", fact_id="visites_guidees"
        )
        self.assertTrue(sortie.startswith("ERREUR"))
        self.assertIn("une seule reformulation par aide", sortie)


# ---------------------------------------------------------------------------
# Remontée et application
# ---------------------------------------------------------------------------


def _entree(**surcharge):
    return {
        "fact": "monument_ouvert_au_public",
        "slug": "ex-aide",
        "jour": "2026-10-15",
        "question_origine": QUESTION,
        "help_origine": (
            "Ouvert au public signifie accessible aux visiteurs, gratuitement ou non, au moins "
            "une partie de l'année."
        ),
        "question": BONNE,
        "help": "Un jardin ouvert compte, même si le bâtiment reste fermé.",
        "justification": "Le propriétaire d'un jardin ouvert autour d'un monument fermé.",
        "citations": 3,
        "extrait_citations": ["aide-a#ouvert-au-public  [condition] user_fact/gate"],
        "p1": {"gates": 2, "derive": 0.05},
        **surcharge,
    }


class TestRemonteeEtApplication(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.partage = self.racine / "reformulations.yaml"
        self.facts = self.racine / "facts.yaml"
        self.facts.write_text(FACTS_YAML, encoding="utf-8")

    def vue(self, option, entree=None):
        entree = entree or _entree()
        r = Reponse("case", rf.SORTE, rf.objet(entree["fact"]), rf.etat(entree), option).evenement()
        return Vue([r])

    def test_remonter_ouvre_une_case_et_garde_le_premier_arrive(self):
        texte = aide_yaml("ouvert au public")
        cases, notes = rf.remonter("ex-aide", [_entree()], texte, ecrire=True, chemin=self.partage)
        self.assertEqual(notes, [])
        (case,) = cases
        self.assertEqual(
            (case.sorte, case.objet), ("R-reformulation", "f:monument_ouvert_au_public")
        )
        self.assertEqual(set(case.options), {"appliquer", "refuser"})
        rendu = "\n".join(case.rendre())
        self.assertIn(f"question proposée : « {BONNE} »", rendu)
        self.assertIn("faits_surcharges", rendu)
        autre = _entree(slug="autre-aide", question="Autre tournure ?")
        cases, notes = rf.remonter(
            "autre-aide",
            [autre],
            aide_yaml("q", slug="autre-aide"),
            ecrire=True,
            chemin=self.partage,
        )
        self.assertEqual(cases, [])
        self.assertIn("attend Félix", notes[0])
        self.assertEqual(rf.lire(self.partage)["monument_ouvert_au_public"]["slug"], "ex-aide")

    def test_remonter_ignore_une_aide_qui_ne_cite_plus_le_fait(self):
        texte = aide_yaml("q").replace("fact: monument_ouvert_au_public", "fact: autre_fait")
        cases, notes = rf.remonter("ex-aide", [_entree()], texte, ecrire=True, chemin=self.partage)
        self.assertEqual(cases, [])
        self.assertIn("ne cite plus le fait", notes[0])
        self.assertFalse(self.partage.exists())

    def test_remonter_suit_le_reglage(self):
        with mock.patch("catalogue.registre.reformulation_fait_active", lambda: False):
            cases, _ = rf.remonter(
                "ex-aide", [_entree()], aide_yaml("q"), ecrire=True, chemin=self.partage
            )
        self.assertEqual(cases, [])

    def test_appliquer_ne_change_que_question_et_help(self):
        rf.deposer(_entree(), self.partage, remplacer=False)
        avant = charger_yaml(self.facts.read_text(encoding="utf-8"))
        notes = rf.appliquer(self.vue("appliquer"), chemin=self.partage, facts_path=self.facts)
        self.assertIn("réécrite", notes[0])
        texte = self.facts.read_text(encoding="utf-8")
        self.assertIn("# En-tête : un commentaire qui doit survivre", texte)
        self.assertIn("  # Commentaire dans le bloc du fait.", texte)
        apres = charger_yaml(texte)
        self.assertEqual(apres["monument_ouvert_au_public"]["question"], BONNE)
        self.assertEqual(
            apres["monument_ouvert_au_public"]["help"],
            "Un jardin ouvert compte, même si le bâtiment reste fermé.",
        )
        for cle in ("surface_jardin_m2", "visites_guidees"):
            self.assertEqual(apres[cle], avant[cle])
        self.assertEqual(
            {
                k: v
                for k, v in apres["monument_ouvert_au_public"].items()
                if k not in ("question", "help")
            },
            {
                k: v
                for k, v in avant["monument_ouvert_au_public"].items()
                if k not in ("question", "help")
            },
        )
        self.assertEqual(rf.lire(self.partage), {})

    def test_une_longue_question_se_replie(self):
        longue = (
            "Le monument ou son jardin est-il ouvert au public pendant au moins une partie "
            "de l'année, même partiellement ?"
        )
        entree = _entree(question=longue)
        rf.deposer(entree, self.partage, remplacer=False)
        rf.appliquer(self.vue("appliquer", entree), chemin=self.partage, facts_path=self.facts)
        texte = self.facts.read_text(encoding="utf-8")
        self.assertIn("question: >-", texte)
        self.assertEqual(charger_yaml(texte)["monument_ouvert_au_public"]["question"], longue)

    def test_un_temoin_perime_n_ecrit_rien(self):
        entree = _entree(question_origine="Une question qui n'est plus celle en place ?")
        rf.deposer(entree, self.partage, remplacer=False)
        avant = self.facts.read_text(encoding="utf-8")
        notes = rf.appliquer(
            self.vue("appliquer", entree), chemin=self.partage, facts_path=self.facts
        )
        self.assertIn("périmée", notes[0])
        self.assertEqual(self.facts.read_text(encoding="utf-8"), avant)
        self.assertEqual(rf.lire(self.partage), {})

    def test_refuser_retire_sans_ecrire(self):
        rf.deposer(_entree(), self.partage, remplacer=False)
        avant = self.facts.read_text(encoding="utf-8")
        notes = rf.appliquer(self.vue("refuser"), chemin=self.partage, facts_path=self.facts)
        self.assertIn("refusée", notes[0])
        self.assertEqual(self.facts.read_text(encoding="utf-8"), avant)
        self.assertEqual(rf.lire(self.partage), {})

    def test_a_blanc_rien_n_est_ecrit(self):
        rf.deposer(_entree(), self.partage, remplacer=False)
        avant = self.facts.read_text(encoding="utf-8")
        notes = rf.appliquer(
            self.vue("appliquer"), a_blanc=True, chemin=self.partage, facts_path=self.facts
        )
        self.assertIn("réécrite", notes[0])
        self.assertEqual(self.facts.read_text(encoding="utf-8"), avant)
        self.assertIn("monument_ouvert_au_public", rf.lire(self.partage))

    def test_une_reponse_a_un_autre_etat_ne_vaut_pas(self):
        rf.deposer(_entree(), self.partage, remplacer=False)
        vue = self.vue("appliquer", _entree(question="Une autre tournure, vue par Félix ?"))
        self.assertEqual(rf.appliquer(vue, chemin=self.partage, facts_path=self.facts), [])
        self.assertIn("monument_ouvert_au_public", rf.lire(self.partage))

    def test_la_case_cochee_dans_le_rapport_s_applique(self):
        from catalogue import cases as cases_mod

        cases, _ = rf.remonter(
            "ex-aide", [_entree()], aide_yaml("q"), ecrire=True, chemin=self.partage
        )
        rapport = "\n".join(cases[0].rendre()).replace("- [ ] `appliquer`", "- [x] `appliquer`")
        (reponse,), ambigues = cases_mod.lire(rapport)
        self.assertEqual(ambigues, [])
        notes = rf.appliquer(Vue([reponse.evenement()]), chemin=self.partage, facts_path=self.facts)
        self.assertIn("réécrite", notes[0])
        self.assertEqual(
            charger_yaml(self.facts.read_text(encoding="utf-8"))["monument_ouvert_au_public"][
                "question"
            ],
            BONNE,
        )

    def test_le_lint_signale_une_entree_perimee(self):
        rf.deposer(_entree(), self.partage, remplacer=False)
        rf.deposer(_entree(fact="disparu"), self.partage, remplacer=False)
        rf.deposer(
            _entree(fact="visites_guidees", question_origine="Ancienne ?"),
            self.partage,
            remplacer=False,
        )
        load_facts.cache_clear()
        messages = rf.avertissements(load_facts(self.facts), self.partage)
        load_facts.cache_clear()
        self.assertEqual(len(messages), 2)
        self.assertTrue(any("`disparu` n'existe plus" in m for m in messages))
        self.assertTrue(any("`visites_guidees` a changé" in m for m in messages))


class TestRegistre(unittest.TestCase):
    def test_r1_est_valide_et_porte_ses_seuils(self):
        reg = registre_mod.charger()
        d = reg.decisions["R1-reformulation"]
        self.assertEqual((d.statut, d.decideur), ("en_service", "felix"))
        self.assertEqual(set(d.seuils), {"citations_max", "derive_max", "similarite_min"})
        self.assertEqual(reg.reglages.reformulation_fait, "case")
        self.assertTrue(registre_mod.reformulation_fait_active())

    def test_off_retire_l_outil(self):
        import tempfile

        brut = yaml.safe_load(registre_mod.REGISTRE.read_text(encoding="utf-8"))
        brut["reglages"]["reformulation_fait"] = "off"
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "registre.yaml"
            chemin.write_text(yaml.safe_dump(brut, allow_unicode=True), encoding="utf-8")
            self.assertFalse(registre_mod.reformulation_fait_active(chemin))

    def test_la_nouvelle_chaine_suit_le_reglage(self):
        """`catalogue.agent` passe le réglage à la configuration de l'agent."""
        import inspect

        from catalogue import agent

        self.assertIn(
            'reformulation=reg.reglages.reformulation_fait == "case"', inspect.getsource(agent.main)
        )

    def test_la_recopie_du_run_emporte_le_fichier_d_attente(self):
        from catalogue import semaine

        self.assertIn("backend/data/catalogue/reformulations.yaml", semaine.FICHIERS_ECRITS)


def test_dataclass_atelier_reformulations_dans_la_sortie(tmp_path):
    from ingestion.atelier import atelier_redirige, restaurer_sources

    try:
        atelier = atelier_redirige("x", tmp_path)
        assert atelier.reformulations_path == tmp_path.resolve() / "reformulations.yaml"
        standard = dataclasses.replace(
            atelier, pending_path=registre_mod.BACKEND / "data" / "facts_pending.yaml"
        )
        assert standard.reformulations_path == rf.REFORMULATIONS
    finally:
        restaurer_sources()
