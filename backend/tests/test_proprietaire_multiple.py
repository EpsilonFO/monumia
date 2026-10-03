"""Plusieurs propriétaires cochés sur la fiche : « il suffit d'un seul ».

Le moteur évalue chaque aide une fois par propriétaire (une fiche où
`proprietaire` vaut ce seul code) et garde le meilleur verdict. Les questions
sont l'union de celles des profils encore vivants, et une réponse n'élimine
l'aide que si elle élimine tous ces profils. Un seul propriétaire : le
diagnostic d'avant, à l'identique.
"""

import time
import unittest

from pydantic import ValidationError

from aides_schema import load_all_aides, load_facts, load_pending_facts
from eligibility_engine import (
    RANG_STATUT,
    build_context,
    profils_par_proprietaire,
    proprietaire_unique,
    run_deterministic_diagnostic,
)
from routers.aides import MonumentInvite
from routers.monuments import CreateMonumentRequest, UpdateMonumentRequest
from tests.test_eligibility_engine import _fixture_aide, _monument

FACTS = {**load_facts(), **load_pending_facts()}
COMMUNE_ET_PRIVE = ["public_commune", "prive_personne_physique"]
FIGE = __import__("datetime").date(2026, 9, 30)


def _gate(id_: str, fact: str, predicate: dict, **extra) -> dict:
    return {
        "id": id_,
        "text": f"Condition {id_}.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": fact,
        "predicate": predicate,
        **extra,
    }


def _run(aides, proprietaire, answers=None):
    return run_deterministic_diagnostic(
        {a.slug: a for a in aides},
        FACTS,
        _monument(proprietaire=proprietaire),
        3000,
        answers or {},
        today=FIGE,
    )


def _slugs(res, seau: str) -> set[str]:
    return {m["aide"]["id"] for m in res[seau]}


class ProfilsTest(unittest.TestCase):
    def test_un_profil_par_proprietaire(self) -> None:
        profils = profils_par_proprietaire(_monument(proprietaire=COMMUNE_ET_PRIVE))
        self.assertEqual([p["proprietaire"] for p in profils], COMMUNE_ET_PRIVE)

    def test_une_chaine_seule_vaut_un_proprietaire(self) -> None:
        profils = profils_par_proprietaire(_monument(proprietaire="association"))
        self.assertEqual([p["proprietaire"] for p in profils], ["association"])

    def test_liste_vide_un_profil_sans_proprietaire(self) -> None:
        profils = profils_par_proprietaire(_monument(proprietaire=[]))
        self.assertEqual([p["proprietaire"] for p in profils], [None])

    def test_le_contexte_ne_retient_jamais_une_liste(self) -> None:
        """Appelé sans passer par les profils, le contexte ne compare pas une
        liste à `eq: public_commune` : il ne retient aucun propriétaire."""
        ctx = build_context(_monument(proprietaire=COMMUNE_ET_PRIVE), None, {})
        self.assertIsNone(ctx["monument.proprietaire"])
        ctx = build_context(_monument(proprietaire=["association"]), None, {})
        self.assertEqual(ctx["monument.proprietaire"], "association")
        self.assertIsNone(proprietaire_unique({"proprietaire": []}))

    def test_ordre_des_statuts(self) -> None:
        self.assertLess(RANG_STATUT["eligible"], RANG_STATUT["potentiel"])
        self.assertLess(RANG_STATUT["potentiel"], RANG_STATUT["atteignable"])
        self.assertLess(RANG_STATUT["atteignable"], RANG_STATUT["non_eligible"])


class IlSuffitDUnSeulTest(unittest.TestCase):
    COMMUNALE = _fixture_aide([], slug="fx-communale", proprietaires=["public_commune"])
    PRIVEE = _fixture_aide([], slug="fx-privee", proprietaires=["prive_personne_physique"])
    ASSOCIATIVE = _fixture_aide([], slug="fx-asso", proprietaires=["association"])
    # « Si privé, le demandeur doit être imposable » : la clause privée ne doit
    # pas écarter l'aide pour la commune, qui peut la déposer.
    CLAUSE_PRIVEE = _fixture_aide(
        [
            _gate(
                "imposable",
                "edifice_cultuel",
                {"eq": True},
                applies_if={
                    "field": "monument.proprietaire",
                    "predicate": {"in": ["prive_personne_physique", "prive_sci"]},
                },
            )
        ],
        slug="fx-clause-privee",
    )

    def test_aide_communale_et_aide_privee_proposees(self) -> None:
        res = _run([self.COMMUNALE, self.PRIVEE, self.ASSOCIATIVE], COMMUNE_ET_PRIVE)
        self.assertEqual(_slugs(res, "aidesEligibles"), {"fx-communale", "fx-privee"})
        self.assertEqual(_slugs(res, "aidesNonEligibles"), {"fx-asso"})

    def test_clause_privee_necarte_pas_une_aide_que_la_commune_depose(self) -> None:
        # Le privé seul répondrait « non » (Château de Test, lu sur le nom ne
        # déduit rien : on force la réponse), la commune n'est pas concernée.
        answers = {"edifice_cultuel": "non"}
        seul = _run([self.CLAUSE_PRIVEE], ["prive_personne_physique"], answers)
        self.assertEqual(_slugs(seul, "aidesNonEligibles"), {"fx-clause-privee"})
        res = _run([self.CLAUSE_PRIVEE], COMMUNE_ET_PRIVE, answers)
        self.assertEqual(_slugs(res, "aidesEligibles"), {"fx-clause-privee"})

    def test_le_meilleur_verdict_lemporte_sur_une_question(self) -> None:
        """Commune éligible d'office, privé à confirmer : l'aide est éligible
        et ne pose aucune question."""
        res = _run([self.CLAUSE_PRIVEE], COMMUNE_ET_PRIVE)
        self.assertEqual(_slugs(res, "aidesEligibles"), {"fx-clause-privee"})
        self.assertEqual(res["qcmQuestions"], [])


class QuestionsDesProfilsVivantsTest(unittest.TestCase):
    """Commune à confirmer sur un fait, privé à confirmer sur un autre."""

    AIDE = _fixture_aide(
        [
            _gate(
                "commune-cultuel",
                "edifice_cultuel",
                {"eq": True},
                applies_if={
                    "field": "monument.proprietaire",
                    "predicate": {"eq": "public_commune"},
                },
            ),
            _gate(
                "prive-habitable",
                "batiment_habitable",
                {"eq": True},
                applies_if={
                    "field": "monument.proprietaire",
                    "predicate": {"eq": "prive_personne_physique"},
                },
            ),
        ],
        slug="fx-deux-branches",
    )

    def _questions(self, res) -> dict[str, dict]:
        return {q["id"]: q for q in res["qcmQuestions"]}

    def test_union_des_questions(self) -> None:
        res = _run([self.AIDE], COMMUNE_ET_PRIVE)
        self.assertEqual(_slugs(res, "aidesPotentiellementEligibles"), {"fx-deux-branches"})
        self.assertEqual(set(self._questions(res)), {"edifice_cultuel", "batiment_habitable"})

    def test_une_reponse_nelimine_que_si_tous_les_profils_tombent(self) -> None:
        """« Non » à la question de la commune n'écarte pas l'aide : le privé
        peut encore la déposer. Le front élague sur cette table."""
        questions = self._questions(_run([self.AIDE], COMMUNE_ET_PRIVE))
        for q in questions.values():
            self.assertEqual(q["eliminationsParOption"], {}, q["id"])

    def test_un_seul_proprietaire_elimine_comme_avant(self) -> None:
        questions = self._questions(_run([self.AIDE], ["public_commune"]))
        self.assertEqual(set(questions), {"edifice_cultuel"})
        self.assertEqual(
            questions["edifice_cultuel"]["eliminationsParOption"], {"non": ["fx-deux-branches"]}
        )

    def test_repondre_a_une_branche_suffit(self) -> None:
        res = _run([self.AIDE], COMMUNE_ET_PRIVE, {"batiment_habitable": "oui"})
        self.assertEqual(_slugs(res, "aidesEligibles"), {"fx-deux-branches"})

    def test_les_deux_branches_fermees_ecartent_laide(self) -> None:
        res = _run(
            [self.AIDE],
            COMMUNE_ET_PRIVE,
            {"batiment_habitable": "non", "edifice_cultuel": "non"},
        )
        self.assertEqual(_slugs(res, "aidesNonEligibles"), {"fx-deux-branches"})

    def test_elimination_commune_a_tous_les_profils(self) -> None:
        """Une question que les DEUX profils posent, et qu'une réponse ferme
        pour les deux : là, l'élimination est annoncée."""
        aide = _fixture_aide(
            [_gate("tous", "edifice_cultuel", {"eq": True})], slug="fx-commune-aux-deux"
        )
        q = self._questions(_run([aide], COMMUNE_ET_PRIVE))["edifice_cultuel"]
        self.assertEqual(q["eliminationsParOption"], {"non": ["fx-commune-aux-deux"]})


class UnSeulProprietaireIdentiqueTest(unittest.TestCase):
    """Sur le vrai catalogue : la chaîne, la liste d'un élément, même résultat."""

    AIDES = load_all_aides()

    def test_chaine_et_liste_dun_element(self) -> None:
        for proprietaire in ("public_commune", "prive_personne_physique", "association"):
            chaine = _run_corpus(self.AIDES, proprietaire)
            liste = _run_corpus(self.AIDES, [proprietaire])
            self.assertEqual(chaine, liste, proprietaire)

    def test_plusieurs_proprietaires_voient_au_moins_chacun(self) -> None:
        commune = _run_corpus(self.AIDES, "public_commune")
        prive = _run_corpus(self.AIDES, "prive_personne_physique")
        les_deux = _run_corpus(self.AIDES, COMMUNE_ET_PRIVE)
        self.assertLessEqual(proposees(commune) | proposees(prive), proposees(les_deux))
        self.assertLessEqual(_slugs(commune, "aidesEligibles"), _slugs(les_deux, "aidesEligibles"))

    def test_cout_raisonnable(self) -> None:
        debut = time.perf_counter()
        _run_corpus(self.AIDES, ["public_commune", "prive_personne_physique", "association"])
        self.assertLess(time.perf_counter() - debut, 3.0)


def proposees(res) -> set[str]:
    """Les aides proposées, à quelque titre que ce soit."""
    return (
        _slugs(res, "aidesEligibles")
        | _slugs(res, "aidesPotentiellementEligibles")
        | _slugs(res, "aidesAtteignables")
    )


def _run_corpus(aides, proprietaire):
    return run_deterministic_diagnostic(
        aides,
        FACTS,
        _monument(
            proprietaire=proprietaire,
            region="normandie",
            departement_num="27",
            protection="inscrit",
        ),
        3000,
        {},
        today=FIGE,
    )


class RoutesTest(unittest.TestCase):
    BASE = {"nom": "Église", "commune": "Évreux", "protection": "inscrit"}

    def test_liste_dedoublonnee(self) -> None:
        body = CreateMonumentRequest.model_validate(
            {**self.BASE, "proprietaire": ["public_commune", "association", "public_commune"]}
        )
        self.assertEqual(body.proprietaire, ["public_commune", "association"])

    def test_chaine_seule_acceptee(self) -> None:
        body = CreateMonumentRequest.model_validate({**self.BASE, "proprietaire": "prive_sci"})
        self.assertEqual(body.proprietaire, ["prive_sci"])
        invite = MonumentInvite.model_validate({**self.BASE, "proprietaire": "prive_sci"})
        self.assertEqual(invite.proprietaire, ["prive_sci"])

    def test_422_liste_vide_code_inconnu_absent(self) -> None:
        for mauvais in ([], ["inconnu"], ["public_commune", "inconnu"], [1]):
            with self.assertRaises(ValidationError, msg=repr(mauvais)):
                CreateMonumentRequest.model_validate({**self.BASE, "proprietaire": mauvais})
            with self.assertRaises(ValidationError, msg=repr(mauvais)):
                MonumentInvite.model_validate({**self.BASE, "proprietaire": mauvais})
        with self.assertRaises(ValidationError):
            CreateMonumentRequest.model_validate(self.BASE)
        with self.assertRaises(ValidationError):
            UpdateMonumentRequest.model_validate({"proprietaire": []})

    def test_patch_sans_proprietaire_ny_touche_pas(self) -> None:
        body = UpdateMonumentRequest.model_validate({"nom": "Autre"})
        self.assertNotIn("proprietaire", body.model_dump(exclude_none=True))


if __name__ == "__main__":
    unittest.main()
