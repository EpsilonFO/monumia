"""Le type d'édifice de la fiche, et les faits qu'il répond d'avance.

Deux choses sont gardées ici :

- la LISTE des types, fermée en quatre endroits (`labels.TYPE_EDIFICE_LABELS`,
  le CHECK SQL de la migration, `TYPES_EDIFICE` et les regroupements du front),
  patron `test_familles.py` ;
- les DÉDUCTIONS (`eligibility_engine.DEDUCTIONS_TYPE_EDIFICE`), et la doctrine
  qui les borne : une valeur n'est déduite que si elle est certaine, une
  absence (type vide, « autre », type qui ne tranche pas) laisse la question
  posée, et la réponse de l'utilisateur prime toujours sur la fiche.
"""

import re
import unittest
from pathlib import Path

from pydantic import ValidationError

from aides_schema import FactDef, load_all_aides, load_facts, load_pending_facts
from eligibility_engine import (
    AUTO_SOURCE_DERIVERS,
    DEDUCTIONS_TYPE_EDIFICE,
    auto_sources_sans_derivation,
    build_context,
    evaluate_aide,
    run_deterministic_diagnostic,
)
from labels import (
    TYPE_EDIFICE_LABELS,
    TYPES_AVEC_AFFECTATION_CULTE,
    TYPES_AVEC_ARCHITECTURE_ROMANE,
)
from routers.aides import MonumentInvite
from routers.monuments import (
    CreateMonumentRequest,
    UpdateMonumentRequest,
    _champs_de_la_fiche,
    _precisions_coherentes,
)
from tests.test_eligibility_engine import _fixture_aide, _monument

RACINE = Path(__file__).resolve().parents[2]
MIGRATIONS = RACINE / "supabase" / "migrations"
FRONT_OPTIONS = RACINE / "frontend" / "src" / "constants" / "monument-options.ts"
FRONT_FICHE = RACINE / "frontend" / "src" / "lib" / "fiche-monument.ts"

FACTS = {**load_facts(), **load_pending_facts()}
SOURCE_TYPE = "monument.type_edifice"


class TableDesTypesTest(unittest.TestCase):
    #: Les codes, FIGÉS : les tables de déduction les citent, et une fiche en
    #: base porte l'un d'eux. En renommer un, c'est une migration de données.
    ATTENDUS = [
        "eglise",
        "chapelle",
        "abbaye_couvent",
        "temple",
        "synagogue",
        "croix_calvaire",
        "autre_religieux",
        "chateau",
        "manoir_demeure",
        "hotel_particulier",
        "maison",
        "edifice_public",
        "hopital",
        "halle",
        "patrimoine_industriel",
        "ferme",
        "moulin",
        "lavoir_fontaine",
        "pigeonnier",
        "petit_patrimoine",
        "fortification",
        "pont",
        "jardin",
        "site_archeologique",
        "monument_aux_morts",
        "monument_commemoratif",
        "autre",
    ]

    def test_les_codes(self) -> None:
        self.assertEqual(list(TYPE_EDIFICE_LABELS), self.ATTENDUS)

    def test_aucun_libelle_ne_porte_de_tiret_cadratin(self) -> None:
        for code, libelle in TYPE_EDIFICE_LABELS.items():
            self.assertNotIn("—", libelle, code)

    def test_les_precisions_portent_sur_des_types_connus(self) -> None:
        self.assertLessEqual(TYPES_AVEC_AFFECTATION_CULTE, set(TYPE_EDIFICE_LABELS))
        self.assertLessEqual(TYPES_AVEC_ARCHITECTURE_ROMANE, set(TYPE_EDIFICE_LABELS))

    def test_le_check_sql_dit_la_meme_chose(self) -> None:
        portantes = [
            p
            for p in sorted(MIGRATIONS.glob("*.sql"))
            if "monuments_type_edifice_check" in p.read_text(encoding="utf-8")
        ]
        self.assertTrue(portantes, "aucune migration ne pose le CHECK du type d'édifice")
        sql = portantes[-1].read_text(encoding="utf-8")
        bloc = re.search(r"type_edifice <@ array\[(.*?)\]::text\[\]", sql, re.S)
        assert bloc is not None, "CHECK `type_edifice <@ array[...]` absent de la migration"
        self.assertEqual(re.findall(r"'([a-z_]+)'", bloc.group(1)), self.ATTENDUS)

    def test_le_front_propose_exactement_les_memes_codes(self) -> None:
        bloc = re.search(
            r"export const TYPES_EDIFICE = \[(.*?)\] as const;",
            FRONT_OPTIONS.read_text(encoding="utf-8"),
            re.S,
        )
        assert bloc is not None, "TYPES_EDIFICE introuvable dans monument-options.ts"
        self.assertEqual(re.findall(r"value:\s*'([a-z_]+)'", bloc.group(1)), self.ATTENDUS)

    def test_le_front_propose_les_precisions_sur_les_memes_types(self) -> None:
        source = FRONT_FICHE.read_text(encoding="utf-8")
        for nom, attendu in (
            ("TYPES_AVEC_AFFECTATION_CULTE", TYPES_AVEC_AFFECTATION_CULTE),
            ("TYPES_AVEC_ARCHITECTURE_ROMANE", TYPES_AVEC_ARCHITECTURE_ROMANE),
        ):
            bloc = re.search(rf"export const {nom}[^=]*= new Set<[^>]*>\(\[(.*?)\]\)", source, re.S)
            assert bloc is not None, f"{nom} introuvable dans fiche-monument.ts"
            self.assertEqual(set(re.findall(r"'([a-z_]+)'", bloc.group(1))), attendu, nom)


class TablesDeDeductionTest(unittest.TestCase):
    """Chaque table parle d'un fait réel, avec des valeurs que ce fait admet."""

    def test_chaque_fait_de_la_table_lit_le_type_edifice(self) -> None:
        for key in DEDUCTIONS_TYPE_EDIFICE:
            fait = FACTS.get(key)
            assert fait is not None, key
            self.assertEqual(fait.scope, "monument", key)
            self.assertIn(SOURCE_TYPE, fait.auto_sources, key)

    def test_chaque_fait_qui_lit_le_type_a_sa_table(self) -> None:
        """Sinon le code brut (« eglise ») serait comparé à `eq: true`."""
        lecteurs = {k for k, f in FACTS.items() if SOURCE_TYPE in f.auto_sources}
        self.assertEqual(lecteurs, set(DEDUCTIONS_TYPE_EDIFICE))
        self.assertEqual(auto_sources_sans_derivation(FACTS), [])

    def test_les_types_et_les_valeurs_sont_valides(self) -> None:
        for key, table in DEDUCTIONS_TYPE_EDIFICE.items():
            fait = FACTS[key]
            self.assertLessEqual(set(table), set(TYPE_EDIFICE_LABELS), key)
            for type_edifice, valeur in table.items():
                if fait.type == "boolean":
                    self.assertIsInstance(valeur, bool, (key, type_edifice))
                else:
                    connues = {o.id for o in fait.options or [] if not o.unknown}
                    self.assertIn(valeur, connues, (key, type_edifice))

    def test_autre_ne_deduit_jamais_rien(self) -> None:
        for key, table in DEDUCTIONS_TYPE_EDIFICE.items():
            self.assertNotIn("autre", table, key)

    def test_quelques_deductions_de_reference(self) -> None:
        """Les cas qui ont motivé le champ, et deux abstentions voulues."""
        t = DEDUCTIONS_TYPE_EDIFICE
        self.assertIs(t["edifice_eglise_ou_chapelle"]["eglise"], True)
        self.assertIs(t["edifice_eglise_ou_chapelle"]["lavoir_fontaine"], False)
        self.assertIs(t["edifice_cultuel"]["synagogue"], True)
        self.assertIs(t["bien_representatif_histoire_culture_juives"]["synagogue"], True)
        self.assertIs(t["bien_representatif_histoire_culture_juives"]["eglise"], False)
        self.assertIs(t["edifice_monument_aux_morts"]["monument_aux_morts"], True)
        self.assertEqual(t["patrimoine_bati_rural_ou_cultuel"]["moulin"], "bati_rural")
        # Un château peut avoir un jardin, une abbaye peut abriter son église,
        # un bien civil peut témoigner de l'histoire juive : on s'abstient.
        self.assertNotIn("chateau", t["bien_parc_jardin_ou_arboretum"])
        self.assertNotIn("abbaye_couvent", t["edifice_eglise_ou_chapelle"])
        self.assertNotIn("maison", t["bien_representatif_histoire_culture_juives"])

    def test_derivations_existantes_conservees(self) -> None:
        self.assertIn(("annee_construction", "monument.siecle_construction"), AUTO_SOURCE_DERIVERS)
        self.assertIn(("edifice_eglise_ou_chapelle", "monument.nom"), AUTO_SOURCE_DERIVERS)


def _gate(fact: str, predicate: dict) -> dict:
    return {
        "id": "gate",
        "text": "Condition de test.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": fact,
        "predicate": predicate,
    }


class DeductionAuMoteurTest(unittest.TestCase):
    def _verdict(self, fact: str, predicate: dict, answers=None, **monument):
        aide = _fixture_aide([_gate(fact, predicate)])
        m = _monument(**monument)
        ctx = build_context(m, None, answers or {})
        return evaluate_aide(aide, m, None, ctx, FACTS)

    def test_le_type_repond_oui(self) -> None:
        v = self._verdict("edifice_eglise_ou_chapelle", {"eq": True}, type_edifice=["eglise"])
        self.assertEqual(v.status, "eligible")
        self.assertEqual(v.missing_facts, {})

    def test_le_type_repond_non_sans_question(self) -> None:
        v = self._verdict(
            "edifice_eglise_ou_chapelle", {"eq": True}, type_edifice=["lavoir_fontaine"]
        )
        self.assertEqual(v.status, "non_eligible")
        self.assertEqual(v.missing_facts, {})

    def test_un_enum_se_deduit_aussi(self) -> None:
        v = self._verdict(
            "patrimoine_bati_rural_ou_cultuel", {"eq": "bati_rural"}, type_edifice=["moulin"]
        )
        self.assertEqual(v.status, "eligible")

    def test_type_absent_laisse_la_question_posee(self) -> None:
        # « Château de Test » ne dit rien : le nom seul ne déduit jamais « non ».
        v = self._verdict("edifice_eglise_ou_chapelle", {"eq": True}, type_edifice=None)
        self.assertEqual(v.status, "potentiel")
        self.assertIn("edifice_eglise_ou_chapelle", v.missing_facts)

    def test_autre_laisse_la_question_posee(self) -> None:
        for fact in DEDUCTIONS_TYPE_EDIFICE:
            predicate = {"eq": True} if FACTS[fact].type == "boolean" else {"eq": "cultuel"}
            v = self._verdict(fact, predicate, type_edifice=["autre"], nom="Bien de test")
            self.assertIn(fact, v.missing_facts, fact)

    def test_type_qui_ne_tranche_pas_laisse_la_question_posee(self) -> None:
        v = self._verdict("bien_parc_jardin_ou_arboretum", {"eq": True}, type_edifice=["chateau"])
        self.assertIn("bien_parc_jardin_ou_arboretum", v.missing_facts)

    def test_la_reponse_de_lutilisateur_prime_sur_le_type(self) -> None:
        v = self._verdict(
            "edifice_eglise_ou_chapelle",
            {"eq": True},
            answers={"edifice_eglise_ou_chapelle": "oui"},
            type_edifice=["chateau"],
        )
        self.assertEqual(v.status, "eligible")
        v = self._verdict(
            "edifice_eglise_ou_chapelle",
            {"eq": True},
            answers={"edifice_eglise_ou_chapelle": "non"},
            type_edifice=["eglise"],
        )
        self.assertEqual(v.status, "non_eligible")

    def test_le_nom_reste_une_source_quand_le_type_manque(self) -> None:
        v = self._verdict(
            "edifice_eglise_ou_chapelle", {"eq": True}, type_edifice=None, nom="Église Saint-Martin"
        )
        self.assertEqual(v.status, "eligible")

    def test_le_nom_et_le_type_en_desaccord_reposent_la_question(self) -> None:
        """Un « Château » nommé « Chapelle du château » : sans doute la chapelle
        du domaine. Ni l'un ni l'autre ne l'emporte, on demande."""
        v = self._verdict(
            "edifice_eglise_ou_chapelle",
            {"eq": True},
            type_edifice=["chateau"],
            nom="Chapelle du château de Test",
        )
        self.assertIn("edifice_eglise_ou_chapelle", v.missing_facts)

    def test_le_nom_et_le_type_daccord(self) -> None:
        v = self._verdict(
            "edifice_cultuel", {"eq": True}, type_edifice=["chapelle"], nom="Chapelle Saint-Roch"
        )
        self.assertEqual(v.status, "eligible")


class PrecisionsTest(unittest.TestCase):
    def _verdict(self, fact: str, predicate: dict, **monument):
        aide = _fixture_aide([_gate(fact, predicate)])
        m = _monument(**monument)
        return evaluate_aide(aide, m, None, build_context(m, None, {}), FACTS)

    def test_affecte_au_culte_repond(self) -> None:
        for valeur, statut in ((True, "eligible"), (False, "non_eligible")):
            v = self._verdict(
                "edifice_toujours_affecte_culte",
                {"eq": True},
                type_edifice=["eglise"],
                affecte_au_culte=valeur,
            )
            self.assertEqual(v.status, statut, valeur)

    def test_eglise_sans_precision_laisse_la_question(self) -> None:
        v = self._verdict("edifice_toujours_affecte_culte", {"eq": True}, type_edifice=["eglise"])
        self.assertIn("edifice_toujours_affecte_culte", v.missing_facts)

    def test_un_bien_civil_nest_pas_affecte_au_culte(self) -> None:
        v = self._verdict("edifice_toujours_affecte_culte", {"eq": False}, type_edifice=["maison"])
        self.assertEqual(v.status, "eligible")

    def test_une_precision_hors_de_son_type_nest_pas_lue(self) -> None:
        ctx = build_context(
            _monument(
                type_edifice=["lavoir_fontaine"], affecte_au_culte=True, architecture_romane=True
            ),
            None,
            {},
        )
        self.assertIsNone(ctx["monument.affecte_au_culte"])
        self.assertIsNone(ctx["monument.architecture_romane"])
        v = self._verdict(
            "edifice_architecture_romane",
            {"eq": True},
            type_edifice=["lavoir_fontaine"],
            architecture_romane=True,
        )
        self.assertIn("edifice_architecture_romane", v.missing_facts)

    def test_architecture_romane_repond(self) -> None:
        for valeur, statut in ((True, "eligible"), (False, "non_eligible")):
            v = self._verdict(
                "edifice_architecture_romane",
                {"eq": True},
                type_edifice=["eglise"],
                architecture_romane=valeur,
            )
            self.assertEqual(v.status, statut, valeur)

    def test_le_type_seul_ne_dit_rien_du_style(self) -> None:
        v = self._verdict("edifice_architecture_romane", {"eq": True}, type_edifice=["eglise"])
        self.assertIn("edifice_architecture_romane", v.missing_facts)


class QuestionnaireSurLeCorpusTest(unittest.TestCase):
    """Sur le vrai catalogue : un type renseigné retire ses questions."""

    AIDES = load_all_aides()

    def _questions(self, **monument) -> set[str]:
        res = run_deterministic_diagnostic(self.AIDES, FACTS, _monument(**monument), 800, {})
        return {q["id"] for q in res["qcmQuestions"]}

    def test_les_faits_repondus_par_le_type_ne_sont_plus_poses(self) -> None:
        for type_edifice in ("eglise", "lavoir_fontaine", "chateau", "synagogue"):
            repondus = {
                fact for fact, table in DEDUCTIONS_TYPE_EDIFICE.items() if type_edifice in table
            }
            for region, dep in (("normandie", "27"), ("pays-de-la-loire", "49")):
                questions = self._questions(
                    type_edifice=[type_edifice],
                    nom="Bien de test",
                    region=region,
                    departement_num=dep,
                    protection="non_protege",
                    proprietaire="public_commune",
                )
                self.assertEqual(questions & repondus, set(), (type_edifice, region))

    def test_sans_type_ces_questions_existent_bien(self) -> None:
        """Garde-fou du test précédent : sans type, au moins une des questions
        visées est posée, sinon il ne prouverait rien."""
        questions = self._questions(
            type_edifice=None,
            nom="Bien de test",
            region="normandie",
            departement_num="27",
            protection="non_protege",
            proprietaire="public_commune",
        )
        self.assertTrue(questions & set(DEDUCTIONS_TYPE_EDIFICE))


class RoutesMonumentTest(unittest.TestCase):
    BASE = {
        "nom": "Lavoir du bourg",
        "commune": "Évreux",
        "protection": "non_protege",
        "proprietaire": "public_commune",
    }

    def test_un_type_inconnu_est_refuse(self) -> None:
        with self.assertRaises(ValidationError):
            CreateMonumentRequest.model_validate({**self.BASE, "typeEdifice": ["cathedrale"]})
        with self.assertRaises(ValidationError):
            CreateMonumentRequest.model_validate(
                {**self.BASE, "typeEdifice": ["chateau", "cathedrale"]}
            )
        with self.assertRaises(ValidationError):
            MonumentInvite.model_validate({**self.BASE, "typeEdifice": ["cathedrale"]})

    def test_creation_sans_type_necrit_aucune_colonne_du_type(self) -> None:
        """Une fiche sans type ne doit rien écrire de ces colonnes (et passe
        donc même avant que la migration soit appliquée)."""
        body = CreateMonumentRequest.model_validate({**self.BASE, "affecteAuCulte": True})
        data = _precisions_coherentes(_champs_de_la_fiche(body), creation=True)
        for colonne in ("type_edifice", "affecte_au_culte", "architecture_romane"):
            self.assertNotIn(colonne, data)

    def test_creation_avec_type_vide_les_precisions_sans_objet(self) -> None:
        body = CreateMonumentRequest.model_validate(
            {
                **self.BASE,
                "typeEdifice": ["chateau"],
                "affecteAuCulte": True,
                "architectureRomane": True,
            }
        )
        data = _precisions_coherentes(_champs_de_la_fiche(body), creation=True)
        self.assertEqual(data["type_edifice"], ["chateau"])
        self.assertIsNone(data["affecte_au_culte"])
        self.assertIs(data["architecture_romane"], True)

    def test_un_null_explicite_efface_le_type(self) -> None:
        body = UpdateMonumentRequest.model_validate({"typeEdifice": None})
        data = _precisions_coherentes(_champs_de_la_fiche(body))
        self.assertEqual(
            data, {"type_edifice": None, "affecte_au_culte": None, "architecture_romane": None}
        )

    def test_la_chaine_vide_efface_aussi(self) -> None:
        body = UpdateMonumentRequest.model_validate({"typeEdifice": ""})
        self.assertIsNone(_champs_de_la_fiche(body)["type_edifice"])

    def test_un_patch_sans_type_ne_touche_pas_au_type(self) -> None:
        body = UpdateMonumentRequest.model_validate({"nom": "Nouveau nom"})
        self.assertEqual(_precisions_coherentes(_champs_de_la_fiche(body)), {"nom": "Nouveau nom"})

    def test_le_diagnostic_invite_accepte_le_type(self) -> None:
        m = MonumentInvite.model_validate(
            {**self.BASE, "typeEdifice": ["eglise", "chateau"], "affecteAuCulte": False}
        )
        self.assertEqual(m.typeEdifice, ["eglise", "chateau"])


class ChoixMultipleTest(unittest.TestCase):
    """Plusieurs types cochés : un fait ne se déduit qu'à l'unanimité."""

    def _verdict(self, fact: str, predicate: dict, answers=None, **monument):
        aide = _fixture_aide([_gate(fact, predicate)])
        m = _monument(**{"nom": "Bien de test", **monument})
        return evaluate_aide(aide, m, None, build_context(m, None, answers or {}), FACTS)

    def test_unanimite_des_types(self) -> None:
        # Église + chapelle : l'une et l'autre sont des « églises ou chapelles ».
        v = self._verdict(
            "edifice_eglise_ou_chapelle", {"eq": True}, type_edifice=["eglise", "chapelle"]
        )
        self.assertEqual(v.status, "eligible")
        # Lavoir + pigeonnier : ni l'un ni l'autre, sans question.
        v = self._verdict(
            "edifice_eglise_ou_chapelle",
            {"eq": True},
            type_edifice=["lavoir_fontaine", "pigeonnier"],
        )
        self.assertEqual(v.status, "non_eligible")
        self.assertEqual(v.missing_facts, {})

    def test_desaccord_des_types_laisse_la_question_posee(self) -> None:
        """Château + chapelle : le projet peut porter sur l'un ou l'autre."""
        for fact in ("edifice_eglise_ou_chapelle", "edifice_cultuel"):
            v = self._verdict(fact, {"eq": True}, type_edifice=["chateau", "chapelle"])
            self.assertIn(fact, v.missing_facts, fact)

    def test_un_type_qui_ne_tranche_pas_suffit(self) -> None:
        for types in (["lavoir_fontaine", "autre"], ["lavoir_fontaine", "abbaye_couvent"]):
            v = self._verdict("edifice_eglise_ou_chapelle", {"eq": True}, type_edifice=types)
            self.assertIn("edifice_eglise_ou_chapelle", v.missing_facts, types)

    def test_liste_vide_comme_absence(self) -> None:
        ctx = build_context(_monument(type_edifice=[]), None, {})
        self.assertIsNone(ctx["monument.type_edifice"])
        v = self._verdict("edifice_cultuel", {"eq": True}, type_edifice=[])
        self.assertIn("edifice_cultuel", v.missing_facts)

    def test_une_chaine_seule_vaut_un_type(self) -> None:
        """Colonne `text` d'avant la migration, brouillon invité d'avant."""
        v = self._verdict("edifice_cultuel", {"eq": True}, type_edifice="chapelle")
        self.assertEqual(v.status, "eligible")

    def test_la_reponse_prime_sur_des_types_unanimes(self) -> None:
        v = self._verdict(
            "edifice_eglise_ou_chapelle",
            {"eq": True},
            answers={"edifice_eglise_ou_chapelle": "oui"},
            type_edifice=["lavoir_fontaine", "pigeonnier"],
        )
        self.assertEqual(v.status, "eligible")

    def test_le_nom_par_dessus_les_types(self) -> None:
        # Types unanimes « non », nom « Chapelle… » : désaccord, on demande.
        v = self._verdict(
            "edifice_eglise_ou_chapelle",
            {"eq": True},
            type_edifice=["chateau", "pigeonnier"],
            nom="Chapelle du domaine",
        )
        self.assertIn("edifice_eglise_ou_chapelle", v.missing_facts)
        # Types en désaccord (aucune valeur), le nom seul parle.
        v = self._verdict(
            "edifice_eglise_ou_chapelle",
            {"eq": True},
            type_edifice=["chateau", "chapelle"],
            nom="Chapelle Saint-Roch",
        )
        self.assertEqual(v.status, "eligible")

    def test_architecture_romane_vaut_pour_lensemble(self) -> None:
        """Château + lavoir, romane : le lavoir ne l'admet pas, le château si ;
        la précision est gardée et répond au fait roman."""
        v = self._verdict(
            "edifice_architecture_romane",
            {"eq": True},
            type_edifice=["chateau", "lavoir_fontaine"],
            architecture_romane=True,
        )
        self.assertEqual(v.status, "eligible")

    def test_affecte_au_culte_nalimente_que_son_fait(self) -> None:
        """Château + chapelle, affectée au culte : le fait d'affectation vaut oui,
        mais « édifice cultuel » reste à l'unanimité des types, donc demandé."""
        monument = {"type_edifice": ["chateau", "chapelle"], "affecte_au_culte": True}
        v = self._verdict("edifice_toujours_affecte_culte", {"eq": True}, **monument)
        self.assertEqual(v.status, "eligible")
        v = self._verdict("edifice_cultuel", {"eq": True}, **monument)
        self.assertIn("edifice_cultuel", v.missing_facts)

    def test_precision_ignoree_si_aucun_type_ne_ladmet(self) -> None:
        ctx = build_context(
            _monument(type_edifice=["chateau", "lavoir_fontaine"], affecte_au_culte=True),
            None,
            {},
        )
        self.assertIsNone(ctx["monument.affecte_au_culte"])


class RoutesChoixMultipleTest(unittest.TestCase):
    BASE = RoutesMonumentTest.BASE

    def test_dedoublonne_dans_lordre(self) -> None:
        body = CreateMonumentRequest.model_validate(
            {**self.BASE, "typeEdifice": ["chateau", "chapelle", "chateau"]}
        )
        self.assertEqual(body.typeEdifice, ["chateau", "chapelle"])

    def test_liste_vide_vaut_null(self) -> None:
        body = UpdateMonumentRequest.model_validate({"typeEdifice": []})
        self.assertIsNone(body.typeEdifice)
        data = _precisions_coherentes(_champs_de_la_fiche(body))
        self.assertEqual(
            data, {"type_edifice": None, "affecte_au_culte": None, "architecture_romane": None}
        )
        creation = CreateMonumentRequest.model_validate({**self.BASE, "typeEdifice": []})
        self.assertNotIn(
            "type_edifice", _precisions_coherentes(_champs_de_la_fiche(creation), creation=True)
        )

    def test_une_chaine_seule_est_acceptee(self) -> None:
        body = CreateMonumentRequest.model_validate({**self.BASE, "typeEdifice": "chapelle"})
        self.assertEqual(body.typeEdifice, ["chapelle"])

    def test_refuse_ce_qui_nest_pas_une_liste_de_codes(self) -> None:
        for mauvais in ([1], {"a": 1}, ["inconnu"]):
            with self.assertRaises(ValidationError, msg=repr(mauvais)):
                UpdateMonumentRequest.model_validate({"typeEdifice": mauvais})

    def test_precisions_gardees_si_un_type_les_admet(self) -> None:
        body = UpdateMonumentRequest.model_validate(
            {
                "typeEdifice": ["chateau", "chapelle"],
                "affecteAuCulte": True,
                "architectureRomane": False,
            }
        )
        data = _precisions_coherentes(_champs_de_la_fiche(body))
        self.assertIs(data["affecte_au_culte"], True)
        self.assertIs(data["architecture_romane"], False)

    def test_precisions_videes_si_plus_aucun_type_ne_les_admet(self) -> None:
        body = UpdateMonumentRequest.model_validate(
            {"typeEdifice": ["maison", "lavoir_fontaine"], "affecteAuCulte": True}
        )
        data = _precisions_coherentes(_champs_de_la_fiche(body))
        self.assertIsNone(data["affecte_au_culte"])
        self.assertIsNone(data["architecture_romane"])


class FactDefAutoSourceTest(unittest.TestCase):
    def test_une_source_ou_plusieurs(self) -> None:
        base = {"type": "boolean", "scope": "monument", "question": "q ?"}
        self.assertEqual(FactDef.model_validate(base).auto_sources, [])
        self.assertEqual(
            FactDef.model_validate({**base, "auto_source": "monument.nom"}).auto_sources,
            ["monument.nom"],
        )
        self.assertEqual(
            FactDef.model_validate(
                {**base, "auto_source": ["monument.type_edifice", "monument.nom"]}
            ).auto_sources,
            ["monument.type_edifice", "monument.nom"],
        )


if __name__ == "__main__":
    unittest.main()
