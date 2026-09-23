"""Tests du moteur de diagnostic déterministe.

Run from backend/:  .venv/bin/python -m unittest discover
"""

import re
import unittest
from datetime import date

from aides_schema import (
    FAMILLES,
    Aide,
    AppliesIf,
    Calendrier,
    Condition,
    FactDef,
    Financement,
    MultiValue,
    RangeValue,
    evaluate_predicate,
    load_all_aides,
    load_facts,
    load_pending_facts,
)
from eligibility_engine import (
    FAITS_DEDUITS_DES_FAMILLES,
    FAITS_DEDUITS_VRAI_DES_FAMILLES,
    FAMILLES_PAR_RAISON,
    _match_result,
    _normalize_answer,
    _normalize_boundary,
    _numeric_gap,
    _numeric_tranches,
    _options_for_fact,
    _retournerait_contre,
    build_context,
    build_questions,
    deduire_faits_des_faits,
    disponibilite,
    engine_ready_aides,
    evaluate_aide,
    libelle_tranche,
    run_deterministic_diagnostic,
    split_reserved_answers,
)
from routers.aides import merge_projet_into_monument

AIDES = load_all_aides()
FACTS = {**load_facts(), **load_pending_facts()}
READY = engine_ready_aides(AIDES)


def _fixture_aide(conditions: list[dict], slug: str = "fixture-aide", **hard_filters) -> Aide:
    """Aide synthétique pour tester le COMPORTEMENT du moteur sans dépendre du
    contenu (mutable) du corpus — celui-ci est gardé par lint_aides_data.py."""
    raison = hard_filters.pop("raison", [])
    familles = hard_filters.pop("familles", [])
    applies_if = hard_filters.pop("applies_if", None)
    return Aide.model_validate(
        {
            "slug": slug,
            "nom": "Fixture",
            "organisme": "Org",
            "categorie": "region",
            "type": "subvention",
            "raison": raison,
            "familles": familles,
            "description": "d",
            "conditions": conditions,
            "hard_filters": hard_filters,
            **({"applies_if": applies_if} if applies_if else {}),
        }
    )


def _fait_gate(aide: Aide) -> str:
    """Le fait de `FAITS_DEDUITS_DES_FAMILLES` que cette aide gate en positif."""
    from aides_schema import evaluate_predicate as _ev

    return next(
        c.fact
        for c in aide.conditions
        if c.fact in FAITS_DEDUITS_DES_FAMILLES
        and c.effect == "gate"
        and c.predicate is not None
        and _ev(c.predicate.root, False) is False
        and c.fact
    )


def _monument(**over):
    base = {
        "id": "demo",
        "nom": "Château de Test",
        "protection": "classe",
        "proprietaire": "prive_personne_physique",
        "region": "ile-de-france",
        "departement_num": "78",
        "etat_conservation": "peril",
        "travaux_envisages": ["toiture", "facade"],
        "siecle_construction": "XVIIe siècle",
    }
    base.update(over)
    return base


class TestEngineReady(unittest.TestCase):
    def test_only_fully_typed_aides(self):
        for slug, aide in READY.items():
            self.assertFalse(
                any(c.kind == "untyped" for c in aide.conditions),
                f"{slug} a des conditions untyped mais est dans le set engine-ready",
            )

    def test_drac_classes_is_ready(self):
        self.assertIn("drac-mh-classes", READY)


class TestDisponibilite(unittest.TestCase):
    """Fenêtre de candidature : axe transverse au statut, jamais un filtre."""

    TODAY = date(2026, 6, 22)

    def _aide(self, slug: str = "fixture-aide", **calendrier) -> Aide:
        return _fixture_aide([], slug=slug).model_copy(
            update={"calendrier": Calendrier(**calendrier)}
        )

    def test_permanente_toujours_disponible(self):
        """`permanent: true` court-circuite les dates (6 YAML les cumulent)."""
        a = self._aide(permanent=True, date_limite=date(2026, 2, 13))
        self.assertEqual(disponibilite(a, self.TODAY), "maintenant")

    def test_sans_aucune_date_reputee_ouverte(self):
        self.assertEqual(disponibilite(self._aide(permanent=False), self.TODAY), "maintenant")

    def test_date_limite_passee_est_bientot(self):
        a = self._aide(permanent=False, date_limite=date(2026, 2, 13))
        self.assertEqual(disponibilite(a, self.TODAY), "bientot")

    def test_date_limite_du_jour_encore_ouverte(self):
        a = self._aide(permanent=False, date_limite=self.TODAY)
        self.assertEqual(disponibilite(a, self.TODAY), "maintenant")

    def test_date_limite_future_est_maintenant(self):
        a = self._aide(permanent=False, date_limite=date(2026, 8, 31))
        self.assertEqual(disponibilite(a, self.TODAY), "maintenant")

    def test_date_ouverture_future_est_bientot(self):
        a = self._aide(permanent=False, date_ouverture=date(2026, 9, 1))
        self.assertEqual(disponibilite(a, self.TODAY), "bientot")

    def test_fenetre_en_cours_est_maintenant(self):
        a = self._aide(
            permanent=False, date_ouverture=date(2026, 1, 15), date_limite=date(2026, 8, 31)
        )
        self.assertEqual(disponibilite(a, self.TODAY), "maintenant")

    def test_diagnostic_conserve_les_aides_closes(self):
        """Une aide close reste analysée, marquée « bientôt » — pas exclue."""
        a = self._aide(permanent=False, date_limite=date(2026, 2, 13))
        res = run_deterministic_diagnostic(
            {"fixture-aide": a}, FACTS, _monument(), 3000, today=self.TODAY
        )
        self.assertEqual(res["totalAidesAnalysees"], 1)
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fixture-aide"])
        self.assertEqual(res["aidesEligibles"][0]["disponibilite"], "bientot")

    def test_montant_potentiel_compte_les_bientot(self):
        """Le montant couvre aussi les aides « disponibles bientôt »."""
        ouverte = self._aide(slug="fx-ouverte", permanent=True).model_copy(
            update={"financement": Financement(montant_max=10_000)}
        )
        close = self._aide(
            slug="fx-close", permanent=False, date_limite=date(2026, 2, 13)
        ).model_copy(update={"financement": Financement(montant_max=90_000)})
        res = run_deterministic_diagnostic(
            {a.slug: a for a in (ouverte, close)}, FACTS, _monument(), 3000, today=self.TODAY
        )
        self.assertEqual(len(res["aidesEligibles"]), 2)
        self.assertEqual(res["montantPotentielTotal"], 100_000)

    def test_montant_potentiel_compte_les_a_confirmer(self):
        """Les aides « à confirmer » (statut potentiel) entrent dans le total."""
        certaine = self._aide(slug="fx-certaine", permanent=True).model_copy(
            update={"financement": Financement(montant_max=10_000)}
        )
        a_confirmer = _fixture_aide(
            [{"id": "mc", "text": "À vérifier auprès du financeur", "kind": "manual_check"}],
            slug="fx-a-confirmer",
        ).model_copy(update={"financement": Financement(montant_max=5_000)})
        res = run_deterministic_diagnostic(
            {a.slug: a for a in (certaine, a_confirmer)},
            FACTS,
            _monument(),
            3000,
            today=self.TODAY,
        )
        self.assertEqual(len(res["aidesPotentiellementEligibles"]), 1)
        self.assertEqual(res["montantPotentielTotal"], 15_000)


class TestTauxTravauxCumule(unittest.TestCase):
    """Part maximale du coût des travaux : « jusqu'à X € et / ou Y % des travaux ».

    N'agrège que les aides qui allègent la facture de chantier — un dispositif
    fiscal porte sur l'impôt, un prêt se rembourse, un label n'apporte rien.
    """

    LEVIER_FACT = "label_fondation_patrimoine_obtenu"

    def _aide(self, slug: str, taux: float | None, type_: str = "subvention") -> Aide:
        return _fixture_aide([], slug=slug).model_copy(
            update={"type": type_, "financement": Financement(taux_max=taux)}
        )

    def _run(self, *aides: Aide, answers: dict | None = None) -> dict:
        return run_deterministic_diagnostic(
            {a.slug: a for a in aides}, FACTS, _monument(), 3000, answers
        )

    def test_somme_des_taux(self):
        res = self._run(self._aide("fx-a", 30), self._aide("fx-b", 25))
        self.assertEqual(res["tauxTravauxMaxPct"], 55)

    def test_exclut_la_fiscalite(self):
        """Une déduction fiscale (Denormandie, Malraux) ne subventionne rien."""
        res = self._run(self._aide("fx-a", 30), self._aide("fx-fisc", 50, "deduction_fiscale"))
        self.assertEqual(res["tauxTravauxMaxPct"], 30)

    def test_exclut_prets_et_labels(self):
        res = self._run(
            self._aide("fx-a", 30),
            self._aide("fx-pret", 40, "pret"),
            self._aide("fx-label", 20, "label"),
        )
        self.assertEqual(res["tauxTravauxMaxPct"], 30)

    def test_ecrete_a_quatre_vingts_pour_cent(self):
        """Le maître d'ouvrage garde 20 % à sa charge : le cumul ne va pas plus loin."""
        res = self._run(self._aide("fx-a", 60), self._aide("fx-b", 70))
        self.assertEqual(res["tauxTravauxMaxPct"], 80)

    def test_aucune_aide_chiffree_en_taux(self):
        res = self._run(self._aide("fx-a", None))
        self.assertIsNone(res["tauxTravauxMaxPct"])

    def test_compte_les_a_debloquer_et_les_a_confirmer(self):
        """Les trois seaux affichés comptent, contrairement au montant potentiel."""
        gate_levier = {
            "id": "lev",
            "text": "Être labellisé Fondation du patrimoine",
            "kind": "user_fact",
            "fact": self.LEVIER_FACT,
            "predicate": {"eq": True},
        }
        a_debloquer = _fixture_aide([gate_levier], slug="fx-levier").model_copy(
            update={"financement": Financement(taux_max=25)}
        )
        a_confirmer = _fixture_aide(
            [{"id": "mc", "text": "À vérifier auprès du financeur", "kind": "manual_check"}],
            slug="fx-a-confirmer",
        ).model_copy(update={"financement": Financement(taux_max=15)})
        res = self._run(
            self._aide("fx-a", 30),
            a_debloquer,
            a_confirmer,
            answers={self.LEVIER_FACT: False},
        )
        self.assertEqual(len(res["aidesAtteignables"]), 1)
        self.assertEqual(len(res["aidesPotentiellementEligibles"]), 1)
        self.assertEqual(res["tauxTravauxMaxPct"], 70)


class TestRaisonPrefilter(unittest.TestCase):
    """Étape « Votre projet » : les intentions cochées (clé réservée `_raisons`)
    écartent les aides dont aucune finalité ne les recoupe."""

    TRAVAUX = _fixture_aide([], slug="fx-travaux", raison=["restauration_travaux"])
    EVENEMENT = _fixture_aide([], slug="fx-evenement", raison=["valorisation_rayonnement"])
    SANS_RAISON = _fixture_aide([], slug="fx-sans-raison")

    def _run(self, aides, answers=None):
        catalogue = {a.slug: a for a in aides}
        return run_deterministic_diagnostic(catalogue, FACTS, _monument(), 3000, answers)

    def _slugs(self, res) -> set[str]:
        return {
            m["aide"]["id"]
            for bucket in (
                "aidesEligibles",
                "aidesPotentiellementEligibles",
                "aidesNonEligibles",
            )
            for m in res[bucket]
        }

    def test_raisons_ecarte_les_aides_hors_projet(self):
        res = self._run([self.TRAVAUX, self.EVENEMENT], {"_raisons": ["restauration_travaux"]})
        self.assertEqual(self._slugs(res), {"fx-travaux"})
        self.assertEqual(res["totalAidesAnalysees"], 1)

    def test_aide_sans_raison_passe_toujours(self):
        """Fail-open : faute de donnée, on ne masque jamais une aide."""
        res = self._run(
            [self.TRAVAUX, self.SANS_RAISON], {"_raisons": ["valorisation_rayonnement"]}
        )
        self.assertEqual(self._slugs(res), {"fx-sans-raison"})

    def test_intersection_partielle_suffit(self):
        res = self._run([self.TRAVAUX], {"_raisons": ["fiscalite", "restauration_travaux"]})
        self.assertEqual(self._slugs(res), {"fx-travaux"})

    def test_sans_raisons_comportement_inchange(self):
        for answers in (None, {}, {"_raisons": []}):
            res = self._run([self.TRAVAUX, self.EVENEMENT], answers)
            self.assertEqual(self._slugs(res), {"fx-travaux", "fx-evenement"}, answers)

    def test_cles_reservees_ne_sont_pas_des_faits(self):
        """Une clé « _* » ne doit jamais atteindre le contexte d'évaluation."""
        facts_answers, reserved = split_reserved_answers(
            {"_raisons": ["fiscalite"], "etat_travaux": "non_commences"}
        )
        self.assertEqual(facts_answers, {"etat_travaux": "non_commences"})
        self.assertEqual(reserved, {"_raisons": ["fiscalite"]})
        ctx = build_context(_monument(), 3000, facts_answers)
        self.assertNotIn("_raisons", ctx["_answers"])

    def test_answers_du_caller_non_mutees(self):
        """Le dict d'entrée est partagé (store front, cache) : on ne le vide pas."""
        answers = {"_raisons": ["restauration_travaux"], "etat_travaux": "non_commences"}
        self._run([self.TRAVAUX], answers)
        self.assertIn("_raisons", answers)

    def test_aide_display_expose_la_raison(self):
        res = self._run([self.TRAVAUX], {"_raisons": ["restauration_travaux"]})
        match = res["aidesEligibles"][0]
        self.assertEqual(match["aide"]["raison"], ["restauration_travaux"])


class TestFaitsDeduitsDesRaisons(unittest.TestCase):
    """L'étape « Votre projet » répond d'avance certains faits : demander à un
    propriétaire qui refait sa toiture si son projet est un festival se lit
    comme une panne. Le filtrage `hors_projet` n'y suffit pas — une aide
    multi-raison (Fondation CA Pays de France) reste candidate pour un pur
    chantier et traîne ses faits événementiels avec elle."""

    FACT = "projet_evenementiel_ponctuel"
    GATE = {
        "id": "pas-evenementiel",
        "text": "L'aide ne concerne pas les opérations événementielles",
        "kind": "user_fact",
        "fact": FACT,
        "predicate": {"eq": False},
    }
    # Les deux finalités, comme la Fondation CA Pays de France : c'est le cas
    # que le préfiltre des raisons ne sait pas écarter.
    AIDE = _fixture_aide(
        [GATE],
        slug="fx-mixte",
        raison=["restauration_travaux", "valorisation_rayonnement"],
    )

    def _run(self, answers=None):
        return run_deterministic_diagnostic(
            {self.AIDE.slug: self.AIDE}, FACTS, _monument(), 3000, answers
        )

    def _questions(self, res) -> set[str]:
        return {q["id"] for q in res["qcmQuestions"]}

    def test_travaux_seuls_repondent_non_sans_poser_la_question(self):
        res = self._run({"_raisons": ["restauration_travaux"]})
        self.assertNotIn(self.FACT, self._questions(res))
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-mixte"])

    def test_faire_vivre_le_lieu_laisse_la_question_posee(self):
        """« Faire vivre » couvre autant des visites pérennes qu'une exposition
        d'un été : la déduction ne tranche pas, la question survit."""
        res = self._run({"_raisons": ["restauration_travaux", "valorisation_rayonnement"]})
        self.assertIn(self.FACT, self._questions(res))
        self.assertEqual(len(res["aidesPotentiellementEligibles"]), 1)

    def test_sans_raisons_comportement_inchange(self):
        for answers in (None, {}, {"_raisons": []}):
            res = self._run(answers)
            self.assertIn(self.FACT, self._questions(res), answers)

    def test_reponse_de_l_utilisateur_prime_sur_la_deduction(self):
        """Un projet d'événement déclaré tel quel reste écarté, même si
        l'intention « faire vivre le lieu » a été décochée depuis."""
        res = self._run({"_raisons": ["restauration_travaux"], self.FACT: "oui"})
        self.assertEqual([m["aide"]["id"] for m in res["aidesNonEligibles"]], ["fx-mixte"])

    def test_je_ne_sais_pas_ne_bloque_pas_la_deduction(self):
        res = self._run({"_raisons": ["restauration_travaux"], self.FACT: "skip"})
        self.assertNotIn(self.FACT, self._questions(res))
        self.assertEqual(len(res["aidesEligibles"]), 1)

    def test_answers_du_caller_non_mutees(self):
        """Le dict d'entrée est partagé (store front, cache) : la déduction en
        travaille une copie."""
        answers = {"_raisons": ["restauration_travaux"]}
        self._run(answers)
        self.assertEqual(answers, {"_raisons": ["restauration_travaux"]})


class TestHardFilters(unittest.TestCase):
    def test_inscrit_aide_refuses_classe_monument(self):
        """drac-mh-inscrits exige protection=inscrit → un classé est non éligible."""
        v = evaluate_aide(
            AIDES["drac-mh-inscrits"],
            _monument(protection="classe"),
            3000,
            build_context(_monument(protection="classe"), 3000),
            FACTS,
        )
        self.assertEqual(v.status, "non_eligible")
        self.assertIn("Protection", v.raison_ineligibilite)

    def test_commune_aide_refuses_private_owner(self):
        m = _monument(proprietaire="prive_personne_physique")
        v = evaluate_aide(AIDES["detr"], m, 3000, build_context(m, 3000), FACTS)
        self.assertEqual(v.status, "non_eligible")

    def test_population_threshold(self):
        """DETR : commune ≤ 20000 hab. Une grande ville (commune) est exclue."""
        m = _monument(proprietaire="public_commune", protection="non_protege")
        v_small = evaluate_aide(AIDES["detr"], m, 3000, build_context(m, 3000), FACTS)
        v_big = evaluate_aide(AIDES["detr"], m, 200000, build_context(m, 200000), FACTS)
        self.assertNotEqual(v_small.status, "non_eligible")
        self.assertEqual(v_big.status, "non_eligible")

    def test_travaux_ecarte_une_aide_dobjet(self):
        """L'aide IDF sur les fonds d'archives ne suit pas un chantier de toiture.

        Elle n'a que des conditions `effect: info` : sans hard_filter travaux,
        elle ressortait éligible pour tout monument d'Île-de-France.
        """
        m = _monument(travaux_envisages=["toiture"])
        v = evaluate_aide(AIDES["idf-restauration-oeuvre"], m, 3000, build_context(m, 3000), FACTS)
        self.assertEqual(v.status, "non_eligible")
        self.assertIn("Travaux éligibles", v.raison_ineligibilite)

    def test_travaux_vides_laissent_passer_laide_dobjet(self):
        """« Pas encore déterminé » (liste vide) : fail-open, on ne masque rien."""
        m = _monument(travaux_envisages=[])
        v = evaluate_aide(AIDES["idf-restauration-oeuvre"], m, 3000, build_context(m, 3000), FACTS)
        self.assertNotEqual(v.status, "non_eligible")


class TestEpciGating(unittest.TestCase):
    """Aides intercommunales : le gate `commune.epci` contre le SIREN de l'EPCI.

    Les hard_filters d'une aide de la CCMSL ne bornent que le département (77) :
    sans le rattachement intercommunal, toute la Seine-et-Marne restait en
    « potentiel ». Le SIREN vient de communes.epci_siren, posé sur le monument
    par routers.monuments._attach_epci.
    """

    CCMSL = "247700032"
    AIDE = "ccmsl-renovation-facades"

    def _monument_77(self, **over):
        return _monument(
            protection="non_protege",
            departement_num="77",
            proprietaire="prive_personne_physique",
            travaux_envisages=["facade"],
            **over,
        )

    def _status(self, monument):
        return evaluate_aide(
            AIDES[self.AIDE], monument, 3000, build_context(monument, 3000), FACTS
        ).status

    def test_epci_absent_reste_incertain(self):
        """Commune non enrichie : fail-closed, jamais un rejet."""
        m = self._monument_77()
        self.assertNotIn("commune.epci", build_context(m, 3000))
        self.assertNotEqual(self._status(m), "non_eligible")

    def test_autre_epci_du_departement_est_rejete(self):
        m = self._monument_77(**{"commune.epci": "200072346"})
        self.assertEqual(self._status(m), "non_eligible")

    def test_epci_porteur_ne_declenche_pas_le_rejet(self):
        m = self._monument_77(**{"commune.epci": self.CCMSL})
        self.assertNotEqual(self._status(m), "non_eligible")


class TestUserFactGating(unittest.TestCase):
    def test_unanswered_fact_is_potentiel_not_eligible(self):
        """Sans réponse, un gate user_fact laisse l'aide potentielle (fail-closed)."""
        m = _monument()
        v = evaluate_aide(AIDES["drac-mh-classes"], m, 3000, build_context(m, 3000), FACTS)
        self.assertEqual(v.status, "potentiel")
        self.assertIn("etat_travaux", v.missing_facts)

    def test_answer_can_make_ineligible(self):
        """Travaux déjà commencés → DRAC classés devient non éligible."""
        m = _monument()
        ctx = build_context(m, 3000, answers={"etat_travaux": "en_cours"})
        v = evaluate_aide(AIDES["drac-mh-classes"], m, 3000, ctx, FACTS)
        self.assertEqual(v.status, "non_eligible")

    def test_manual_check_gate_keeps_potentiel_even_when_user_facts_answered(self):
        """Un gate manual_check (invérifiable) maintient l'aide potentielle même
        quand tous les user_facts sont répondus favorablement — fail-closed."""
        aide = _fixture_aide(
            [
                {
                    "id": "tc",
                    "text": "Travaux non commencés",
                    "kind": "user_fact",
                    "fact": "etat_travaux",
                    "predicate": {"eq": "non_commences"},
                },
                {"id": "mc", "text": "À vérifier auprès du financeur", "kind": "manual_check"},
            ]
        )
        m = _monument()
        ctx = build_context(m, 3000, answers={"etat_travaux": "non_commences"})
        v = evaluate_aide(aide, m, 3000, ctx, FACTS)
        self.assertEqual(v.status, "potentiel")
        self.assertNotIn("etat_travaux", v.missing_facts)
        # Seul reste le manual_check : incertitude sans categorie (donc sans question).
        incertitudes = [e for e in v.evaluations if e["verdict"] == "incertitude"]
        self.assertEqual(len(incertitudes), 1)
        self.assertNotIn("categorie", incertitudes[0])

    def test_derogation_possible_soft_gate(self):
        """Gate souple : prédicat faux → incertitude (pas de refus). Vrai → satisfait.
        Inconnu → question posée."""
        soft = _fixture_aide(
            [
                {
                    "id": "tc",
                    "text": "Travaux non commencés (sauf dérogation)",
                    "kind": "user_fact",
                    "fact": "etat_travaux",
                    "predicate": {"eq": "non_commences"},
                    "derogation_possible": True,
                }
            ]
        )
        m = _monument()
        # Non commencés → satisfait → éligible.
        v_ok = evaluate_aide(
            soft, m, 3000, build_context(m, 3000, answers={"etat_travaux": "non_commences"}), FACTS
        )
        self.assertEqual(v_ok.status, "eligible")
        # Commencés → PAS refusé (dérogation possible) → potentiel, sans re-question.
        v_started = evaluate_aide(
            soft, m, 3000, build_context(m, 3000, answers={"etat_travaux": "en_cours"}), FACTS
        )
        self.assertEqual(v_started.status, "potentiel")
        self.assertNotIn("etat_travaux", v_started.missing_facts)
        # Inconnu → incertitude → question posée.
        v_unknown = evaluate_aide(soft, m, 3000, build_context(m, 3000), FACTS)
        self.assertEqual(v_unknown.status, "potentiel")
        self.assertIn("etat_travaux", v_unknown.missing_facts)

    def test_strict_gate_refuses_when_false(self):
        """Sans derogation_possible, le même prédicat faux refuse l'aide (contraste)."""
        strict = _fixture_aide(
            [
                {
                    "id": "tc",
                    "text": "Travaux non commencés",
                    "kind": "user_fact",
                    "fact": "etat_travaux",
                    "predicate": {"eq": "non_commences"},
                }
            ]
        )
        m = _monument()
        v = evaluate_aide(
            strict, m, 3000, build_context(m, 3000, answers={"etat_travaux": "en_cours"}), FACTS
        )
        self.assertEqual(v.status, "non_eligible")

    def test_aide_without_manual_check_becomes_eligible(self):
        """Une aide sans manual_check, dont les gates auto + user_fact sont tous
        satisfaits, devient éligible (Loto : protection + non-commencement +
        trésorerie insuffisante)."""
        m = _monument(protection="classe")
        answers = {"etat_travaux": "non_commences", "tresorerie_insuffisante_autofinancement": True}
        ctx = build_context(m, 3000, answers=answers)
        v = evaluate_aide(AIDES["loto-patrimoine"], m, 3000, ctx, FACTS)
        self.assertEqual(v.status, "eligible")


class TestAppliesIf(unittest.TestCase):
    def test_autofinancement_skipped_for_private(self):
        """L'autofinancement 20 % ne s'applique qu'aux collectivités → pas de
        question pour un propriétaire privé."""
        m = _monument(proprietaire="prive_personne_physique")
        v = evaluate_aide(AIDES["drac-mh-classes"], m, 3000, build_context(m, 3000), FACTS)
        self.assertNotIn("autofinancement_pct", v.missing_facts)


class TestQuestionGeneration(unittest.TestCase):
    def test_elimination_is_computed_correctly(self):
        m = _monument()
        res = run_deterministic_diagnostic(AIDES, FACTS, m, 3000)
        q_travaux = next(q for q in res["qcmQuestions"] if q["categorie"] == "etat_travaux")
        # « En cours » et « Achevés » éliminent DRAC classés ; « Pas encore
        # commencés » ne l'élimine pas (mais élimine les concours qui exigent
        # des travaux achevés — la question unifiée porte les deux familles).
        self.assertIn("drac-mh-classes", q_travaux["eliminationsParOption"].get("en_cours", []))
        self.assertIn("drac-mh-classes", q_travaux["eliminationsParOption"].get("acheves", []))
        self.assertNotIn(
            "drac-mh-classes", q_travaux["eliminationsParOption"].get("non_commences", [])
        )

    def test_fait_porteur_de_levier_n_elimine_jamais(self):
        """Un gate en échec sur un fait ACTIONNABLE rend l'aide « à débloquer »,
        pas refusée. L'annoncer comme éliminée ferait tomber du questionnaire
        les autres questions de l'aide (`isQuestionServingLiveAide` côté front),
        qui reviendrait ensuite avec des critères jamais posés."""
        aide = _fixture_aide(
            [
                self._gate("ouverture_public", {"not_in": ["aucune"]}),
                self._gate("porteur_est_proprietaire", {"eq": True}),
            ]
        )
        questions = {q["id"]: q for q in self._questions([aide])}
        self.assertEqual(questions["ouverture_public"]["eliminationsParOption"], {})

        # Le refus assumé : l'aide survit en « atteignable », et sa seconde
        # question garde donc tout son sens.
        res = run_deterministic_diagnostic(
            {aide.slug: aide}, FACTS, _monument(), 3000, {"ouverture_public": ["aucune"]}
        )
        self.assertEqual([m["aide"]["id"] for m in res["aidesAtteignables"]], [aide.slug])
        self.assertIn("porteur_est_proprietaire", [q["id"] for q in res["qcmQuestions"]])

    def test_gate_a_derogation_n_elimine_jamais(self):
        """`derogation_possible` dégrade l'échec en incertitude : l'aide reste
        potentielle. Même question, même option, seule la version ferme tombe."""
        souple = _fixture_aide(
            [self._gate("etat_travaux", {"eq": "non_commences"}, derogation_possible=True)],
            slug="fx-souple",
        )
        ferme = _fixture_aide(
            [self._gate("etat_travaux", {"eq": "non_commences"})],
            slug="fx-ferme",
        )
        q_travaux = {q["id"]: q for q in self._questions([souple, ferme])}["etat_travaux"]
        self.assertEqual(q_travaux["eliminationsParOption"]["en_cours"], ["fx-ferme"])

    def test_skip_never_eliminates(self):
        m = _monument()
        res = run_deterministic_diagnostic(AIDES, FACTS, m, 3000)
        for q in res["qcmQuestions"]:
            self.assertNotIn("skip", q["eliminationsParOption"])

    @staticmethod
    def _gate(
        fact: str,
        predicate: dict,
        applies_if: dict | None = None,
        derogation_possible: bool = False,
    ) -> dict:
        cond = {
            "id": f"c-{fact.replace('_', '-')}",
            "text": f"Condition sur {fact}",
            "kind": "user_fact",
            "fact": fact,
            "predicate": predicate,
        }
        if applies_if:
            cond["applies_if"] = applies_if
        if derogation_possible:
            cond["derogation_possible"] = True
        return cond

    def _questions(self, aides: list[Aide], answers=None) -> list[dict]:
        catalogue = {a.slug: a for a in aides}
        res = run_deterministic_diagnostic(catalogue, FACTS, _monument(), 3000, answers)
        return res["qcmQuestions"]

    def test_questions_sorted_by_aides_unblocked(self):
        """À égalité de nature (aucune passerelle), le fait qui débloque le plus
        d'aides passe en premier."""
        aides = [
            _fixture_aide(
                [self._gate("etat_travaux", {"eq": "non_commences"})]
                + ([self._gate("porteur_est_proprietaire", {"eq": True})] if i < 2 else [])
                + ([self._gate("visible_voie_publique", {"eq": True})] if i < 1 else []),
                slug=f"fx-{i}",
            )
            for i in range(3)
        ]
        counts = [len(q["aideIds"]) for q in self._questions(aides)]
        self.assertEqual(counts, [3, 2, 1])

    def test_fait_passerelle_pose_avant_ses_dependantes(self):
        """Un fait qui n'existe que dans un `applies_if` n'était jamais posé :
        sa condition restait bloquée en incertitude pour toujours."""
        aide = _fixture_aide(
            [
                self._gate(
                    "jours_ouverture_public_par_an",
                    {"gte": 20},
                    applies_if={
                        "fact": "label_fondation_patrimoine_obtenu",
                        "predicate": {"eq": True},
                    },
                )
            ]
        )
        ids = [q["id"] for q in self._questions([aide])]
        self.assertEqual(
            ids, ["label_fondation_patrimoine_obtenu", "jours_ouverture_public_par_an"]
        )

    def test_depends_on_emis_sur_le_fait_passerelle(self):
        aide = _fixture_aide(
            [
                self._gate(
                    "jours_ouverture_public_par_an",
                    {"gte": 20},
                    applies_if={
                        "fact": "label_fondation_patrimoine_obtenu",
                        "predicate": {"eq": True},
                    },
                )
            ]
        )
        questions = {q["id"]: q for q in self._questions([aide])}
        self.assertEqual(
            questions["jours_ouverture_public_par_an"]["dependsOn"],
            {"questionId": "label_fondation_patrimoine_obtenu", "showForOptionIds": ["oui"]},
        )
        # La passerelle elle-même ne dépend de rien et n'élimine personne.
        passerelle = questions["label_fondation_patrimoine_obtenu"]
        self.assertNotIn("dependsOn", passerelle)
        self.assertEqual(passerelle["eliminationsParOption"], {})

    def test_pas_de_depends_on_si_une_condition_est_inconditionnelle(self):
        """Fail-closed : une seule condition sans `applies_if` et la question se
        pose toujours."""
        conditionnelle = _fixture_aide(
            [
                self._gate(
                    "jours_ouverture_public_par_an",
                    {"gte": 20},
                    applies_if={
                        "fact": "label_fondation_patrimoine_obtenu",
                        "predicate": {"eq": True},
                    },
                )
            ],
            slug="fx-conditionnelle",
        )
        inconditionnelle = _fixture_aide(
            [self._gate("jours_ouverture_public_par_an", {"gte": 5})],
            slug="fx-inconditionnelle",
        )
        questions = {q["id"]: q for q in self._questions([conditionnelle, inconditionnelle])}
        self.assertNotIn("dependsOn", questions["jours_ouverture_public_par_an"])

    def test_passerelle_repondue_ne_repose_pas_la_question(self):
        """Le fait passerelle renseigné, la condition redevient tranchable : plus
        de question passerelle, et la dépendante n'a plus de branchement."""
        aide = _fixture_aide(
            [
                self._gate(
                    "jours_ouverture_public_par_an",
                    {"gte": 20},
                    applies_if={
                        "fact": "label_fondation_patrimoine_obtenu",
                        "predicate": {"eq": True},
                    },
                )
            ]
        )
        ids = [
            q["id"] for q in self._questions([aide], {"label_fondation_patrimoine_obtenu": True})
        ]
        self.assertEqual(ids, ["jours_ouverture_public_par_an"])

    def test_corpus_toute_dependance_est_posee_avant(self):
        res = run_deterministic_diagnostic(AIDES, FACTS, _monument(), 3000)
        seen: set[str] = set()
        for q in res["qcmQuestions"]:
            depends_on = q.get("dependsOn")
            if depends_on:
                self.assertIn(depends_on["questionId"], seen, f"{q['id']} précède sa passerelle")
            seen.add(q["id"])

    def test_help_du_fait_est_transmis(self):
        aide = _fixture_aide([self._gate("etat_travaux", {"eq": "non_commences"})])
        question = self._questions([aide])[0]
        self.assertTrue(question["help"])
        self.assertEqual(question["help"], FACTS["etat_travaux"].help)


class TestPerimetreAide(unittest.TestCase):
    """`Aide.applies_if` : l'aide relève d'un autre métier (festival, compagnie,
    école d'art) et ne doit pas polluer le questionnaire de tout le monde."""

    PERIMETRE = "projet_lieu_diffusion_culturelle"

    def _aide(self, conditions=None, slug="fx-festival") -> Aide:
        base = _fixture_aide(
            conditions
            or [
                {
                    "id": "duree",
                    "text": "Manifestation d'au moins 2 jours",
                    "kind": "user_fact",
                    "fact": "duree_manifestation_jours",
                    "predicate": {"gte": 2},
                }
            ],
            slug=slug,
        )
        return base.model_copy(
            update={
                "applies_if": AppliesIf.model_validate(
                    {"fact": self.PERIMETRE, "predicate": {"eq": True}}
                )
            }
        )

    def _run(self, aides, answers=None):
        return run_deterministic_diagnostic(
            {a.slug: a for a in aides}, FACTS, _monument(), 3000, answers
        )

    def test_perimetre_refuse_ecarte_laide_du_resultat(self):
        res = self._run([self._aide()], {self.PERIMETRE: False})
        self.assertEqual(res["totalAidesAnalysees"], 0)
        self.assertEqual(res["qcmQuestions"], [])

    def test_perimetre_inconnu_pose_la_question_en_premier(self):
        ids = [q["id"] for q in self._run([self._aide()])["qcmQuestions"]]
        self.assertEqual(ids[0], self.PERIMETRE)

    def test_les_questions_de_laide_se_branchent_sur_le_perimetre(self):
        questions = {q["id"]: q for q in self._run([self._aide()])["qcmQuestions"]}
        self.assertEqual(
            questions["duree_manifestation_jours"]["dependsOn"],
            {"questionId": self.PERIMETRE, "showForOptionIds": ["oui"]},
        )

    def test_perimetre_inconnu_empeche_leligibilite(self):
        """Toutes les conditions satisfaites ne suffisent pas : tant qu'on ignore
        si l'aide concerne l'utilisateur, elle reste incertaine (fail-closed)."""
        res = self._run([self._aide()], {"duree_manifestation_jours": 5})
        self.assertEqual(res["aidesEligibles"], [])
        self.assertEqual(len(res["aidesPotentiellementEligibles"]), 1)

    def test_perimetre_confirme_laisse_evaluer_normalement(self):
        res = self._run([self._aide()], {self.PERIMETRE: True, "duree_manifestation_jours": 5})
        self.assertEqual(len(res["aidesEligibles"]), 1)

    def test_condition_avec_sa_propre_clause_garde_la_sienne(self):
        """La clause de la condition est plus spécifique : elle l'emporte, et le
        branchement se désactive (fail-closed, la question reste posée)."""
        aide = self._aide(
            [
                {
                    "id": "duree",
                    "text": "Manifestation d'au moins 2 jours",
                    "kind": "user_fact",
                    "fact": "duree_manifestation_jours",
                    "predicate": {"gte": 2},
                    "applies_if": {"fact": "premiere_edition_realisee", "predicate": {"eq": True}},
                }
            ]
        )
        questions = {q["id"]: q for q in self._run([aide])["qcmQuestions"]}
        self.assertEqual(
            questions["duree_manifestation_jours"]["dependsOn"]["questionId"],
            "premiere_edition_realisee",
        )

    def test_gate_sur_le_fait_de_perimetre_nherite_pas_de_lui_meme(self):
        aide = self._aide(
            [
                {
                    "id": "diffusion",
                    "text": "Lieu de diffusion culturelle",
                    "kind": "user_fact",
                    "fact": self.PERIMETRE,
                    "predicate": {"eq": True},
                }
            ]
        )
        questions = {q["id"]: q for q in self._run([aide])["qcmQuestions"]}
        self.assertNotIn("dependsOn", questions[self.PERIMETRE])

    def test_perimetre_exige_un_fait(self):
        """Un champ structuré relève de hard_filters, pas du périmètre."""
        with self.assertRaises(ValueError):
            Aide.model_validate(
                {
                    "slug": "fx-champ",
                    "nom": "F",
                    "organisme": "O",
                    "categorie": "region",
                    "type": "subvention",
                    "description": "d",
                    "applies_if": {
                        "field": "monument.region",
                        "predicate": {"eq": "normandie"},
                    },
                }
            )

    def test_corpus_les_aides_hors_metier_portent_un_perimetre(self):
        """Garde-fou : les aides gatant sur un fait de programmation culturelle
        doivent déclarer leur périmètre, sinon leurs questions reviennent."""
        marqueurs = {
            "licence_entrepreneur_spectacles",
            "nombre_spectacles_programmes",
            "duree_manifestation_jours",
            "budget_precedente_edition",
            "salles_cinema_associees",
            "frequence_manifestation",
        }
        sans_perimetre = sorted(
            slug
            for slug, aide in AIDES.items()
            if aide.applies_if is None
            and any(c.fact in marqueurs and c.effect == "gate" for c in aide.conditions)
        )
        self.assertEqual(sans_perimetre, [])


class TestConditionsNonBloquantes(unittest.TestCase):
    """`manual_check` + `effect: info` : vraie condition d'éligibilité, mais dont
    la vérification n'a de sens qu'au montage du dossier. Affichée « à confirmer
    avec l'organisme », sans question et sans gater.

    Cas d'école : l'autofinancement minimum de 20 %. Quasi universel (article
    L.1111-10 du CGCT), donc sans pouvoir discriminant, et impossible à trancher
    avant d'avoir chiffré les travaux — le demander éliminait à tort.
    """

    def _run(self, conditions):
        aide = _fixture_aide(conditions)
        return run_deterministic_diagnostic({aide.slug: aide}, FACTS, _monument(), 3000)

    def test_ne_bloque_pas_et_ne_pose_pas_de_question(self):
        res = self._run(
            [
                {
                    "id": "autofinancement",
                    "text": "Autofinancement minimum de 20 % par la commune",
                    "kind": "manual_check",
                    "effect": "info",
                }
            ]
        )
        self.assertEqual(len(res["aidesEligibles"]), 1)
        self.assertEqual(res["qcmQuestions"], [])

    def test_reste_affichee_avec_la_bonne_nature(self):
        """Ni supprimée, ni fondue dans « Bon à savoir » : le front la range dans
        « À confirmer avec l'organisme », et le verdict `info` lui donne le petit
        « i » au lieu du point d'interrogation."""
        res = self._run(
            [
                {
                    "id": "autofinancement",
                    "text": "Autofinancement minimum de 20 % par la commune",
                    "kind": "manual_check",
                    "effect": "info",
                }
            ]
        )
        evaluation = res["aidesEligibles"][0]["llmEvaluation"]["evaluations"][0]
        self.assertEqual(evaluation["nature"], "manual_check")
        self.assertEqual(evaluation["verdict"], "info")
        self.assertIn("sans incidence", evaluation["explication"])

    def test_manual_check_gate_reste_bloquant(self):
        """Contraste : le manual_check par défaut (effect gate) maintient bien
        l'aide en incertitude. Seul `effect: info` la libère."""
        res = self._run(
            [{"id": "mc", "text": "À vérifier auprès du financeur", "kind": "manual_check"}]
        )
        self.assertEqual(len(res["aidesPotentiellementEligibles"]), 1)
        self.assertEqual(res["aidesEligibles"], [])

    def test_corpus_aucune_participation_minimale_ne_bloque(self):
        """La règle des 20 % doit être traitée de la même façon PARTOUT.

        Trois conditions l'exprimaient déjà en `manual_check` + gate (dont sur
        drac-mh-classes et drac-mh-inscrits) : retyper les seuls `user_fact`
        avait laissé deux poids deux mesures, ces aides restant bloquées en
        « potentiel » sur un critère devenu non bloquant ailleurs.
        """
        motif = re.compile(
            r"autofinancement|participation minimale du maître d.ouvrage"
            r"|participation minimum|contribution\s+\S+\s+minimale",
            re.I,
        )
        bloquantes = sorted(
            f"{slug} / {c.id}"
            for slug, aide in AIDES.items()
            for c in aide.conditions
            if c.effect == "gate" and motif.search(" ".join(c.text.split()))
        )
        self.assertEqual(bloquantes, [])

    def test_corpus_autofinancement_ne_gate_plus_nulle_part(self):
        """Garde-fou : une prochaine ingestion qui regaterait sur ce fait
        ferait réapparaître la question piège."""
        refs = sorted(
            f"{slug} / {c.id}"
            for slug, aide in AIDES.items()
            for c in aide.conditions
            if c.fact == "autofinancement_pct"
            or (c.applies_if and c.applies_if.fact == "autofinancement_pct")
        )
        self.assertEqual(refs, [])

    def test_corpus_les_conditions_dautofinancement_sont_conservees(self):
        """Retypées, pas supprimées : le critère et sa citation source restent
        affichables. Ancre nommée plutôt qu'un compte, moins fragile.

        L'ancre initiale (region-hauts-de-france) était un doublon du REPP,
        supprimé du catalogue — l'ancre porte désormais sur le fichier
        survivant, où l'article du CGCT est cité dans les notes.
        """
        cond = next(
            c
            for c in AIDES["hdf-restauration-patrimoine-protege"].conditions
            if c.id == "participation-minimale-mo-publics"
        )
        self.assertEqual((cond.kind, cond.effect), ("manual_check", "info"))
        self.assertIn("participation minimale", cond.quote or "")
        self.assertIn("L1111-10", cond.notes or "")
        # La clause d'applicabilité (maîtres d'ouvrage publics) est préservée.
        self.assertIsNotNone(cond.applies_if)


class TestLeviers(unittest.TestCase):
    """Statut « atteignable » : un gate en échec sur un fait ACTIONNABLE ne
    refuse pas l'aide, il la met à débloquer avec son plan d'action."""

    LEVIER_FACT = "label_fondation_patrimoine_obtenu"

    @staticmethod
    def _gate(fact: str, predicate: dict, **extra) -> dict:
        return {
            "id": f"c-{fact.replace('_', '-')}",
            "text": f"Condition sur {fact}",
            "kind": "user_fact",
            "fact": fact,
            "predicate": predicate,
            **extra,
        }

    def _verdict(self, conditions, answers, **hard_filters):
        aide = _fixture_aide(conditions, **hard_filters)
        m = _monument()
        return evaluate_aide(aide, m, 3000, build_context(m, 3000, answers), FACTS)

    def test_fait_a_levier_rend_latteignable(self):
        v = self._verdict([self._gate(self.LEVIER_FACT, {"eq": True})], {self.LEVIER_FACT: False})
        self.assertEqual(v.status, "atteignable")
        self.assertEqual(len(v.leviers), 1)
        self.assertEqual(v.leviers[0]["factId"], self.LEVIER_FACT)
        self.assertTrue(v.leviers[0]["resume"])
        self.assertEqual(
            v.leviers[0]["organisme"], "Fondation du patrimoine (délégation régionale)"
        )

    def test_levier_ne_pollue_pas_les_criteres_rouges(self):
        """Un levier est une opportunité, pas un refus : il ne doit pas nourrir
        `criteresNonRemplis` ni `raisonIneligibilite` (affichés en rouge)."""
        v = self._verdict([self._gate(self.LEVIER_FACT, {"eq": True})], {self.LEVIER_FACT: False})
        self.assertEqual(v.criteres_non_remplis, [])
        self.assertIsNone(v.raison_ineligibilite)
        evaluation = next(e for e in v.evaluations if e["verdict"] == "non")
        self.assertTrue(evaluation["levier"])

    def test_fait_sans_levier_refuse_toujours(self):
        v = self._verdict(
            [self._gate("etat_travaux", {"eq": "non_commences"})], {"etat_travaux": "en_cours"}
        )
        self.assertEqual(v.status, "non_eligible")
        self.assertEqual(v.leviers, [])

    def test_un_seul_echec_ferme_suffit_a_refuser(self):
        """Précédence : le refus ferme l'emporte sur le levier."""
        v = self._verdict(
            [
                self._gate(self.LEVIER_FACT, {"eq": True}),
                self._gate("etat_travaux", {"eq": "non_commences"}),
            ],
            {self.LEVIER_FACT: False, "etat_travaux": "en_cours"},
        )
        self.assertEqual(v.status, "non_eligible")

    def test_levier_prime_sur_lincertitude(self):
        """Précédence : atteignable l'emporte sur potentiel — l'action concrète
        est plus utile à l'utilisateur qu'une incertitude résiduelle."""
        v = self._verdict(
            [
                self._gate(self.LEVIER_FACT, {"eq": True}),
                {"id": "mc", "text": "À vérifier", "kind": "manual_check"},
            ],
            {self.LEVIER_FACT: False},
        )
        self.assertEqual(v.status, "atteignable")

    def test_derogation_possible_prime_sur_le_levier(self):
        """Un gate souple dégrade en incertitude avant tout examen du levier."""
        v = self._verdict(
            [self._gate(self.LEVIER_FACT, {"eq": True}, derogation_possible=True)],
            {self.LEVIER_FACT: False},
        )
        self.assertEqual(v.status, "potentiel")
        self.assertEqual(v.leviers, [])

    def test_ecart_chiffre_sur_un_seuil_numerique(self):
        v = self._verdict(
            [self._gate("jours_ouverture_public_par_an", {"gte": 20})],
            {"jours_ouverture_public_par_an": 12},
        )
        self.assertEqual(v.status, "atteignable")
        self.assertEqual(v.leviers[0]["ecart"], "Il en manque 8 jours/an")

    def test_pas_decart_sur_un_booleen(self):
        v = self._verdict([self._gate(self.LEVIER_FACT, {"eq": True})], {self.LEVIER_FACT: False})
        self.assertNotIn("ecart", v.leviers[0])

    def test_numeric_gap_seuils_stricts_et_plafonds(self):
        entier = FACTS["jours_ouverture_public_par_an"]
        self.assertEqual(_numeric_gap({"gt": 0}, 0, entier), "Il en manque 1 jours/an")
        self.assertEqual(_numeric_gap({"lte": 5}, 8, entier), "Vous dépassez de 3 jours/an")
        self.assertEqual(_numeric_gap({"lt": 10}, 12, entier), "Vous dépassez de 3 jours/an")
        # Prédicat satisfait ou non chiffrable : aucun écart inventé.
        self.assertIsNone(_numeric_gap({"gte": 5}, 9, entier))
        self.assertIsNone(_numeric_gap({"eq": 5}, 9, entier))
        self.assertIsNone(_numeric_gap({"any_of": [{"gte": 5}]}, 1, entier))

    def test_atteignables_alimentent_le_qcm(self):
        """Une aide atteignable reste vivante : ses faits manquants continuent
        de générer des questions."""
        aide = _fixture_aide(
            [
                self._gate(self.LEVIER_FACT, {"eq": True}),
                self._gate("etat_travaux", {"eq": "non_commences"}),
            ]
        )
        res = run_deterministic_diagnostic(
            {aide.slug: aide}, FACTS, _monument(), 3000, {self.LEVIER_FACT: False}
        )
        self.assertEqual(len(res["aidesAtteignables"]), 1)
        self.assertIn("etat_travaux", [q["id"] for q in res["qcmQuestions"]])

    def test_bucket_trie_par_enjeu_et_total(self):
        def _aide(slug, montant):
            base = _fixture_aide([self._gate(self.LEVIER_FACT, {"eq": True})], slug=slug)
            return base.model_copy(update={"financement": Financement(montant_max=montant)})

        catalogue = {a.slug: a for a in (_aide("fx-petite", 1000), _aide("fx-grosse", 90000))}
        res = run_deterministic_diagnostic(
            catalogue, FACTS, _monument(), 3000, {self.LEVIER_FACT: False}
        )
        self.assertEqual(
            [m["aide"]["id"] for m in res["aidesAtteignables"]], ["fx-grosse", "fx-petite"]
        )
        self.assertEqual(res["montantAtteignableTotal"], 91000)
        self.assertIsNone(res["montantPotentielTotal"])

    def test_enjeu_max_par_question(self):
        aide = _fixture_aide([self._gate("etat_travaux", {"eq": "non_commences"})]).model_copy(
            update={"financement": Financement(montant_max=40000)}
        )
        res = run_deterministic_diagnostic({aide.slug: aide}, FACTS, _monument(), 3000)
        question = next(q for q in res["qcmQuestions"] if q["id"] == "etat_travaux")
        self.assertEqual(question["enjeuMax"], 40000)

    def test_statut_expose_dans_le_match_result(self):
        aide = _fixture_aide([self._gate(self.LEVIER_FACT, {"eq": True})])
        res = run_deterministic_diagnostic(
            {aide.slug: aide}, FACTS, _monument(), 3000, {self.LEVIER_FACT: False}
        )
        match = res["aidesAtteignables"][0]
        self.assertEqual(match["statut"], "atteignable")
        self.assertTrue(match["eligible"])
        self.assertEqual(len(match["leviers"]), 1)


class TestNumericTranches(unittest.TestCase):
    """Génération d'options pour les faits numériques — gestion des seuils
    stricts (régression du bug « Moins de 0 / 0 ou plus jours par an »)."""

    @staticmethod
    def _gate(fact: str, predicate: dict) -> Condition:
        return Condition.model_validate(
            {"id": "c", "text": "t", "kind": "user_fact", "fact": fact, "predicate": predicate}
        )

    @staticmethod
    def _fact(type_: str, unit: str | None = None) -> FactDef:
        return FactDef.model_validate(
            {"type": type_, "scope": "monument", "question": "q?", "unit": unit}
        )

    def test_normalize_boundary_strict_integer(self):
        # gt:n et lte:n se décalent de +1 sur un entier ; gte/lt/eq inchangés.
        self.assertEqual(_normalize_boundary("gt", 0, True), 1)
        self.assertEqual(_normalize_boundary("lte", 5, True), 6)
        self.assertEqual(_normalize_boundary("gte", 25, True), 25)
        self.assertEqual(_normalize_boundary("lt", 1800, True), 1800)
        # Sur un flottant, pas de décalage (pas d'epsilon).
        self.assertEqual(_normalize_boundary("gt", 0, False), 0)

    def test_gt_zero_produces_sane_options(self):
        # Le cas signalé : jours d'ouverture, gt:0 (≡ « au moins 1 jour »).
        fact = self._fact("integer", "jours/an")
        opts = _options_for_fact(fact, [self._gate("jours_ouverture_public_par_an", {"gt": 0})])
        labels = [o["label"] for o in opts]
        self.assertNotIn("Moins de 0 jours/an", labels)
        # Frontière utile = 1 : la bande basse (= 0 jour) et « 1 ou plus ».
        self.assertEqual([o["repr"] for o in opts], [0, 1])
        self.assertIn("1 jour/an ou plus", labels)

    def test_gt_zero_reachable_via_questionnaire(self):
        # Régression dure : avec gt:0 une option DOIT garder l'aide éligible.
        from aides_schema import evaluate_predicate

        opts = _options_for_fact(
            self._fact("integer", "jours/an"),
            [self._gate("jours_ouverture_public_par_an", {"gt": 0})],
        )
        satisfying = [o for o in opts if evaluate_predicate({"gt": 0}, o["repr"]) is True]
        self.assertTrue(satisfying, "au moins une tranche doit satisfaire gt:0")

    def test_gte_thresholds_unchanged(self):
        # Les seuils non stricts gardent leur comportement MECE d'origine.
        opts = _options_for_fact(
            self._fact("integer", "ans"),
            [
                self._gate("duree_location_envisagee_ans", {"gte": 6}),
                self._gate("duree_location_envisagee_ans", {"gte": 9}),
            ],
        )
        self.assertEqual([o["repr"] for o in opts], [5, 6, 9])

    def test_low_band_dropped_when_below_zero(self):
        # gte:0 → borne 0 → la bande « < 0 » est vide et omise.
        opts = _options_for_fact(
            self._fact("integer", "jours/an"),
            [self._gate("jours_ouverture_public_par_an", {"gte": 0})],
        )
        self.assertFalse(any(o["id"].startswith("lt") for o in opts))

    def test_unite_accordee_au_nombre(self):
        """« 1 jour », pas « 1 jours » : l'unité s'accorde sur le nombre qu'elle
        suit. `mois` est invariable, une unité composée n'accorde que sa tête."""
        for unit, attendu in (
            ("ans", ["Aucun (0)", "1 an ou plus"]),
            ("mois", ["Aucun (0)", "1 mois ou plus"]),
            ("compagnies", ["Aucun (0)", "1 compagnie ou plus"]),
            ("jours/an", ["Aucun (0)", "1 jour/an ou plus"]),
        ):
            opts = _options_for_fact(self._fact("integer", unit), [self._gate("f", {"gte": 1})])
            self.assertEqual([o["label"] for o in opts], attendu, unit)

    def test_tranche_basse_dun_compteur_a_seuil_un(self):
        """« Moins de 1 jour » se lit comme un arrondi alors que la bande ne
        contient que 0. On le dit : « Aucun (0) »."""
        opts = _options_for_fact(
            self._fact("integer", "jours/an"),
            [self._gate("jours_ouverture_public_par_an", {"gte": 1})],
        )
        basse = next(o for o in opts if o["id"].startswith("lt"))
        self.assertEqual(basse["label"], "Aucun (0)")
        self.assertEqual(basse["repr"], 0)
        # Un seuil plus haut garde le libellé ordinaire : la bande y contient
        # bien d'autres valeurs que zéro.
        opts = _options_for_fact(self._fact("integer", "ans"), [self._gate("f", {"gte": 3})])
        self.assertEqual(
            next(o for o in opts if o["id"].startswith("lt"))["label"], "Moins de 3 ans"
        )

    def test_euro_reste_colle_et_sans_unite_reste_nu(self):
        """Deux cas où l'accord ne s'applique pas : l'euro est un symbole collé
        au nombre, et un fait sans unité (une année de construction) n'en a
        pas."""
        opts = _options_for_fact(self._fact("number", "€"), [self._gate("f", {"gte": 1})])
        self.assertIn("1€ ou plus", [o["label"] for o in opts])
        opts = _options_for_fact(self._fact("integer"), [self._gate("f", {"lt": 1800})])
        self.assertEqual([o["label"] for o in opts], ["Moins de 1800", "1800 ou plus"])

    def test_une_tranche_se_relit_depuis_son_seul_identifiant(self):
        """L'invariant qui autorise `libelle_tranche` : l'identifiant d'une
        tranche porte ses bornes, donc son libellé se reconstruit à l'identique
        sans connaître les seuils des aides qui l'ont produit.

        C'est ce qui permet de rappeler à l'utilisateur ce qu'il a répondu (une
        réponse persistée vaut `ge5`, hors de tout diagnostic). Si les deux
        chemins dérivaient, on lui montrerait un libellé différent de celui
        qu'il a cliqué — pire que pas de libellé du tout.
        """
        jeux = [
            ([1], "jours/an"),
            ([1], "compagnies"),
            ([3, 5], "ans"),
            ([6, 9], "ans"),
            ([12], "mois"),
            ([1, 15, 25, 40, 90], "jours/an"),
            ([10000, 50000], "€"),
            ([1], "%"),
            ([2.5, 7.5], "%"),
            ([1800, 1926], None),
            ([3000], "litres"),
        ]
        for bornes, unit in jeux:
            for option in _numeric_tranches(bornes, unit):
                self.assertEqual(
                    libelle_tranche(option["id"], unit),
                    option["label"],
                    f"{option['id']} ({unit})",
                )

    def test_un_identifiant_dune_autre_forme_ne_se_relit_pas(self):
        """On n'invente pas : une réponse d'avant les tranches, ou écrite à la
        main, rend None plutôt qu'un libellé fabriqué."""
        for brut in ("oui", "40000", "ge", "lt", "de3a4", "", "ge5ans"):
            self.assertIsNone(libelle_tranche(brut, "ans"), brut)

    def test_les_consignes_de_saisie_zero_ont_disparu(self):
        """Corpus : un fait rendu en TRANCHES ne propose jamais de saisir 0. La
        consigne « (0 si …) » décrivait un champ de saisie qui n'existe pas."""
        fautifs = sorted(
            key
            for key, f in FACTS.items()
            if f.type in ("integer", "number") and "(0 si" in (f.question or "")
        )
        self.assertEqual(fautifs, [])


class TestMultiEnum(unittest.TestCase):
    """Faits à choix multiple : un prédicat est satisfait dès qu'UNE case cochée
    le satisfait, réfuté seulement si toutes le réfutent (cf. MultiValue)."""

    @staticmethod
    def _gate(fact: str, predicate: dict) -> dict:
        return {
            "id": "c-multi",
            "text": f"Condition sur {fact}",
            "kind": "user_fact",
            "fact": fact,
            "predicate": predicate,
        }

    def _status(self, fact: str, predicate: dict, answer) -> str:
        aide = _fixture_aide([self._gate(fact, predicate)])
        m = _monument()
        ctx = build_context(m, 3000, {fact: answer})
        return evaluate_aide(aide, m, 3000, ctx, FACTS).status

    def _questions(self, fact: str, predicate: dict) -> dict:
        aide = _fixture_aide([self._gate(fact, predicate)])
        res = run_deterministic_diagnostic({aide.slug: aide}, FACTS, _monument(), 3000)
        return {q["id"]: q for q in res["qcmQuestions"]}

    def test_les_deux_faits_cumulables_sont_bien_multi(self):
        for key in ("usage_batiment", "statut_juridique_porteur"):
            self.assertEqual(FACTS[key].type, "multi_enum", key)

    def test_une_valeur_cochee_suffit_a_satisfaire(self):
        self.assertIs(
            evaluate_predicate({"eq": "location"}, MultiValue(["habitation", "location"])), True
        )

    def test_refute_seulement_si_toutes_les_valeurs_refutent(self):
        self.assertIs(
            evaluate_predicate({"eq": "location"}, MultiValue(["habitation", "cultuel"])), False
        )

    def test_selection_vide_vaut_fait_inconnu(self):
        self.assertIsNone(evaluate_predicate({"eq": "location"}, MultiValue([])))

    def test_une_case_pertinente_rend_eligible(self):
        """Le cas d'usage : on dépose sous l'entité qui correspond au guichet."""
        status = self._status(
            "statut_juridique_porteur",
            {"in": ["association"]},
            ["prive_personne_physique", "association"],
        )
        self.assertEqual(status, "eligible")

    def test_aucune_case_pertinente_refuse(self):
        status = self._status(
            "statut_juridique_porteur",
            {"in": ["association"]},
            ["prive_personne_physique", "prive_sci"],
        )
        self.assertEqual(status, "non_eligible")

    def test_option_unknown_laisse_le_fait_inconnu(self):
        status = self._status(
            "statut_juridique_porteur", {"in": ["association"]}, ["pas_encore_decide"]
        )
        self.assertEqual(status, "potentiel")

    def test_reponse_unique_deja_persistee_reste_lisible(self):
        """Réponse d'avant le passage en choix multiple : une chaîne, pas une liste."""
        self.assertEqual(
            self._status("usage_batiment", {"eq": "activite_culturelle"}, "activite_culturelle"),
            "eligible",
        )

    def test_question_multiple_sans_pseudo_choix_passer(self):
        q = self._questions("usage_batiment", {"eq": "activite_culturelle"})["usage_batiment"]
        self.assertTrue(q["multiple"])
        self.assertNotIn("skip", [o["id"] for o in q["options"]])

    def test_question_simple_garde_le_pseudo_choix_passer(self):
        q = self._questions("etat_travaux", {"eq": "non_commences"})["etat_travaux"]
        self.assertFalse(q["multiple"])
        self.assertEqual(q["options"][-1], {"id": "skip", "label": "Passer cette question"})

    def test_option_unknown_remontee_au_front(self):
        q = self._questions("statut_juridique_porteur", {"in": ["association"]})[
            "statut_juridique_porteur"
        ]
        unknowns = [o["id"] for o in q["options"] if o.get("unknown")]
        self.assertEqual(unknowns, ["pas_encore_decide"])
        # Une option « pas encore décidé » n'élimine personne.
        self.assertNotIn("pas_encore_decide", q["eliminationsParOption"])


class TestDiagnosticShape(unittest.TestCase):
    def test_output_contract(self):
        res = run_deterministic_diagnostic(AIDES, FACTS, _monument(), 3000)
        for key in (
            "aidesEligibles",
            "aidesPotentiellementEligibles",
            "aidesAtteignables",
            "aidesNonEligibles",
            "montantPotentielTotal",
            "montantAtteignableTotal",
            "qcmQuestions",
            "totalAidesAnalysees",
        ):
            self.assertIn(key, res)
        match = (res["aidesEligibles"] + res["aidesPotentiellementEligibles"])[0]
        for key in (
            "aide",
            "statut",
            "eligible",
            "criteresRemplis",
            "criteresNonRemplis",
            "leviers",
            "llmEvaluation",
        ):
            self.assertIn(key, match)
        self.assertIn("id", match["aide"])  # = slug
        self.assertIn("raison", match["aide"])
        self.assertIn("familles", match["aide"])
        for question in res["qcmQuestions"]:
            for key in ("id", "question", "help", "options", "aideIds", "enjeuMax"):
                self.assertIn(key, question)

    def test_les_quatre_buckets_partitionnent_les_aides(self):
        res = run_deterministic_diagnostic(AIDES, FACTS, _monument(), 3000)
        slugs = [
            m["aide"]["id"]
            for bucket in (
                "aidesEligibles",
                "aidesPotentiellementEligibles",
                "aidesAtteignables",
                "aidesNonEligibles",
            )
            for m in res[bucket]
        ]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertEqual(len(slugs), res["totalAidesAnalysees"])


class TestElimineParReponse(unittest.TestCase):
    """`elimineParReponse` sépare les refus issus d'une RÉPONSE de ceux déduits
    de la fiche du monument. Le front n'affiche que les premiers : se voir
    refuser une aide sur un critère qu'on n'a jamais eu à trancher n'apprend
    rien."""

    def _flag(self, aide: Aide, monument: dict, answers: dict | None = None) -> bool:
        ctx = build_context(monument, 3000, answers=answers)
        verdict = evaluate_aide(aide, monument, 3000, ctx, FACTS)
        return _match_result(verdict)["elimineParReponse"]

    def test_gate_user_fact_en_echec_est_impute_a_la_reponse(self):
        """Travaux déjà commencés : c'est l'utilisateur qui a écarté l'aide."""
        m = _monument()
        self.assertTrue(self._flag(AIDES["drac-mh-classes"], m, {"etat_travaux": "en_cours"}))

    def test_hard_filter_nest_pas_impute_a_la_reponse(self):
        """Refus déduit de la fiche (mauvaise région) : aucune réponse en cause."""
        aide = _fixture_aide([], regions=["bretagne"])
        m = _monument(region="ile-de-france")
        verdict = evaluate_aide(aide, m, 3000, build_context(m, 3000), FACTS)
        self.assertEqual(verdict.status, "non_eligible")
        self.assertFalse(self._flag(aide, m))

    def test_gate_auto_nest_pas_impute_a_la_reponse(self):
        """Un gate `auto` lit la fiche du monument, pas les réponses."""
        aide = _fixture_aide(
            [
                {
                    "id": "prot",
                    "text": "Monument non protégé",
                    "kind": "auto",
                    "effect": "gate",
                    "field": "monument.protection",
                    "predicate": {"not_in": ["classe"]},
                }
            ]
        )
        m = _monument(protection="classe")
        verdict = evaluate_aide(aide, m, 3000, build_context(m, 3000), FACTS)
        self.assertEqual(verdict.status, "non_eligible")
        self.assertFalse(self._flag(aide, m))

    def test_refus_automatique_lemporte_sur_la_reponse(self):
        """Hors région ET travaux commencés : l'aide n'a jamais été candidate,
        c'est la région que `raisonIneligibilite` affiche. Ne pas l'imputer à
        l'utilisateur, sinon la liste se remplit d'aides d'autres régions."""
        aide = _fixture_aide(
            [
                {
                    "id": "tc",
                    "text": "Travaux non commencés",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": "etat_travaux",
                    "predicate": {"eq": "non_commences"},
                }
            ],
            regions=["bretagne"],
        )
        m = _monument(region="ile-de-france")
        self.assertFalse(self._flag(aide, m, {"etat_travaux": "en_cours"}))
        # Sans le hard_filter, la même réponse est bien imputée à l'utilisateur.
        sans_hf = _fixture_aide(aide.conditions and [c.model_dump() for c in aide.conditions])
        self.assertTrue(self._flag(sans_hf, m, {"etat_travaux": "en_cours"}))

    def test_faux_hors_non_eligible(self):
        """Le champ est toujours présent et faux sur les autres statuts."""
        m = _monument()
        verdict = evaluate_aide(AIDES["drac-mh-classes"], m, 3000, build_context(m, 3000), FACTS)
        self.assertNotEqual(verdict.status, "non_eligible")
        self.assertFalse(_match_result(verdict)["elimineParReponse"])


class TestFusionMonumentProjet(unittest.TestCase):
    """Contrat de non-régression de l'inversion de hiérarchie.

    Le moteur n'a PAS changé : `FIELD_REGISTRY` et `build_context` lisent
    toujours `travaux_envisages` sur le monument. Depuis que le cadrage vit sur
    le projet, c'est `merge_projet_into_monument` qui recompose ce monument à la
    frontière (routers). Ces tests prouvent que le contexte obtenu est identique
    à celui d'avant l'inversion — un chantier décrit sur un projet doit produire
    exactement le même diagnostic qu'un monument qui portait ces travaux.
    """

    def test_contexte_identique_a_l_avant_inversion(self):
        avant = _monument(travaux_envisages=["toiture", "facade"])
        # Après : la fiche ne porte plus les travaux, le projet les porte.
        fiche = _monument()
        fiche.pop("travaux_envisages")
        projet = {"id": "p1", "travaux_envisages": ["toiture", "facade"]}
        apres = merge_projet_into_monument(fiche, projet)

        self.assertEqual(build_context(avant, 3000), build_context(apres, 3000))

    def test_le_projet_ecrase_les_travaux_de_la_fiche(self):
        """Deux projets d'un même monument doivent pouvoir diverger."""
        fiche = _monument(travaux_envisages=["toiture"])
        fusion = merge_projet_into_monument(fiche, {"travaux_envisages": ["orgues"]})
        self.assertEqual(fusion["travaux_envisages"], ["orgues"])
        # Sans mutation de la fiche : le même monument sert les autres projets.
        self.assertEqual(fiche["travaux_envisages"], ["toiture"])

    def test_projet_sans_travaux_donne_une_liste_vide(self):
        """« Pas encore déterminé » : le hard_filter travaux redevient fail-open."""
        fusion = merge_projet_into_monument(_monument(), {"travaux_envisages": []})
        self.assertEqual(fusion["travaux_envisages"], [])
        aide = _fixture_aide([], travaux=["orgues"])
        verdict = evaluate_aide(aide, fusion, 3000, build_context(fusion, 3000), FACTS)
        self.assertNotEqual(verdict.status, "non_eligible")

    def test_monument_sans_projet_reste_inchange(self):
        fiche = _monument()
        self.assertIs(merge_projet_into_monument(fiche, None), fiche)


class TestFaitDeduitDUneAutreReponse(unittest.TestCase):
    """« Fermé au public, sans projet d'ouverture » répond d'avance « ouvert
    0 jour par an » : la question des jours se pose APRÈS celle de l'ouverture,
    s'y branche, et n'est plus posée dès que cette case est cochée — le serveur
    déduit la valeur. Celui qui répond quand même garde sa réponse.

    La source est un fait à choix MULTIPLE : la déduction ne vaut que si la case
    déduisante est la seule cochée."""

    SOURCE = "ouverture_public"
    DEDUIT = "jours_ouverture_public_par_an"
    FERME = ["aucune"]
    OUVERT = ["jep_evenements"]
    GATE_VISITE = {
        "id": "visite",
        "text": "Édifice accessible à la visite du public",
        "kind": "user_fact",
        "fact": SOURCE,
        "predicate": {"not_in": ["aucune"]},
    }
    GATE_JOURS = {
        "id": "jours",
        "text": "Ouvert au public au moins 40 jours par an",
        "kind": "user_fact",
        "fact": DEDUIT,
        "predicate": {"gte": 40},
    }

    def _run(self, answers=None, aides=None):
        if aides is None:
            aides = [
                _fixture_aide([self.GATE_VISITE], slug="fx-visite"),
                _fixture_aide([self.GATE_JOURS], slug="fx-jours"),
            ]
        return run_deterministic_diagnostic(
            {a.slug: a for a in aides}, FACTS, _monument(), 3000, answers
        )

    def _ids(self, res) -> list[str]:
        return [q["id"] for q in res["qcmQuestions"]]

    def test_la_source_se_pose_avant_et_la_question_deduite_s_y_branche(self):
        questions = {q["id"]: q for q in self._run()["qcmQuestions"]}
        self.assertEqual(list(questions), [self.SOURCE, self.DEDUIT])
        # Seule « fermé au public » retire la question : elle déduit 0 jour.
        # Toutes les autres cases la gardent, « je ne sais pas » comprise
        # (fail-closed), et « passer » aussi (le front traite `skip` comme non
        # répondu).
        options = [o["id"] for o in questions[self.SOURCE]["options"]]
        self.assertEqual(
            questions[self.DEDUIT]["dependsOn"],
            {
                "questionId": self.SOURCE,
                "showForOptionIds": [o for o in options if o != "aucune"],
            },
        )

    def test_la_source_passe_devant_meme_avec_moins_d_aides(self):
        # Deux aides sur les jours contre une sur la visite : sans promotion de
        # la source, le nombre d'aides mettrait les jours en premier.
        aides = [
            _fixture_aide([self.GATE_VISITE], slug="fx-visite"),
            _fixture_aide([self.GATE_JOURS], slug="fx-jours"),
            _fixture_aide([self.GATE_JOURS], slug="fx-jours-bis"),
        ]
        self.assertEqual(self._ids(self._run(aides=aides))[0], self.SOURCE)

    def test_ferme_au_public_deduit_zero_jour_sans_poser_la_question(self):
        res = self._run({self.SOURCE: self.FERME})
        self.assertEqual(self._ids(res), [])
        # Les DEUX aides tombent « atteignables » plutôt que « non éligibles »,
        # et c'est la décision de la fusion : `ouverture_public` porte un levier
        # (ouvrir au public, même quelques jours), donc aucun de ses gates n'est
        # dirimant. Ouvrir est un geste que le propriétaire peut faire ; le lui
        # présenter en rouge le priverait de la démarche.
        self.assertEqual(
            [m["aide"]["id"] for m in res["aidesAtteignables"]], ["fx-visite", "fx-jours"]
        )
        self.assertEqual(res["aidesPotentiellementEligibles"], [])

    def test_ouvert_au_public_laisse_la_question_des_jours(self):
        self.assertEqual(self._ids(self._run({self.SOURCE: self.OUVERT})), [self.DEDUIT])

    def test_source_passee_ne_deduit_rien(self):
        self.assertEqual(self._ids(self._run({self.SOURCE: "skip"})), [self.SOURCE, self.DEDUIT])

    def test_la_reponse_de_l_utilisateur_prime_sur_la_deduction(self):
        res = self._run({self.SOURCE: self.FERME, self.DEDUIT: "ge40"})
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-jours"])

    def test_deduction_directe(self):
        self.assertEqual(
            deduire_faits_des_faits({self.SOURCE: self.FERME}, FACTS),
            {self.SOURCE: self.FERME, self.DEDUIT: 0},
        )
        # Une source inconnue ou positive ne déduit rien.
        self.assertEqual(deduire_faits_des_faits({}, FACTS), {})
        self.assertEqual(
            deduire_faits_des_faits({self.SOURCE: self.OUVERT}, FACTS),
            {self.SOURCE: self.OUVERT},
        )

    def test_selection_contradictoire_ne_deduit_rien(self):
        """Sur une source à choix multiple, la déduction exige que la case
        déduisante soit la SEULE cochée : « fermé au public » coché AVEC
        « ouvert lors des Journées du patrimoine » est une sélection qui se
        contredit, et la sémantique existentielle du MultiValue veut qu'on n'en
        conclue rien (fail-closed). La question des jours survit."""
        melange = {self.SOURCE: self.FERME + self.OUVERT}
        self.assertEqual(deduire_faits_des_faits(melange, FACTS), melange)
        self.assertEqual(self._ids(self._run(melange)), [self.DEDUIT])


class TestBooleenAReponsesDeclarees(unittest.TestCase):
    """Un `boolean` qui déclare ses réponses : le QCM en offre plus de deux, les
    prédicats des aides restent `eq: true` / `eq: false`.

    Le fait est SYNTHÉTIQUE : le comportement testé est celui du moteur, pas le
    contenu (mutable) de l'ontologie.
    """

    FACT_KEY = "fixture_booleen_declare"

    def _fact(self) -> FactDef:
        return FactDef.model_validate(
            {
                "type": "boolean",
                "scope": "projet",
                "question": "Les travaux portent-ils sur la partie protégée ?",
                "options": [
                    {"id": "oui", "label": "Oui", "valeur": True},
                    {"id": "non", "label": "Non", "valeur": False},
                    {"id": "les_deux", "label": "Les deux"},
                ],
            }
        )

    def _facts(self) -> dict[str, FactDef]:
        return {**FACTS, self.FACT_KEY: self._fact()}

    def _aide(self) -> Aide:
        return _fixture_aide(
            [
                {
                    "id": "gate-protege",
                    "text": "Les travaux portent sur la partie protégée.",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": self.FACT_KEY,
                    "predicate": {"eq": True},
                }
            ]
        )

    def _questions(self, answers: dict | None = None) -> list[dict]:
        res = run_deterministic_diagnostic(
            {"fixture-aide": self._aide()},
            self._facts(),
            _monument(),
            3000,
            answers=answers,
            today=date(2026, 2, 14),
        )
        return res["qcmQuestions"]

    def _diagnostic(self, answers: dict) -> dict:
        return run_deterministic_diagnostic(
            {"fixture-aide": self._aide()},
            self._facts(),
            _monument(),
            3000,
            answers=answers,
            today=date(2026, 2, 14),
        )

    def test_options_du_moteur_portent_les_valeurs_declarees(self):
        opts = _options_for_fact(self._fact(), [])
        self.assertEqual(
            [(o["id"], o["value"]) for o in opts],
            [("oui", True), ("non", False), ("les_deux", None)],
        )

    def test_trois_reponses_plus_passer(self):
        question = next(q for q in self._questions() if q["id"] == self.FACT_KEY)
        self.assertEqual([o["id"] for o in question["options"]], ["oui", "non", "les_deux", "skip"])

    def test_unknown_emis_explicitement_quand_le_fait_declare(self):
        """Le front n'a plus à deviner au libellé : `false` part sur le fil."""
        question = next(q for q in self._questions() if q["id"] == self.FACT_KEY)
        declarees = [o for o in question["options"] if o["id"] != "skip"]
        self.assertTrue(all("unknown" in o for o in declarees))
        self.assertEqual([o["unknown"] for o in declarees], [False, False, False])

    def test_seule_la_reponse_contraire_elimine(self):
        question = next(q for q in self._questions() if q["id"] == self.FACT_KEY)
        self.assertEqual(question["eliminationsParOption"], {"non": ["fixture-aide"]})

    def test_la_reponse_neutre_nest_pas_dans_les_eliminations(self):
        question = next(q for q in self._questions() if q["id"] == self.FACT_KEY)
        self.assertNotIn("les_deux", question["eliminationsParOption"])

    def test_la_reponse_neutre_laisse_laide_en_potentiel(self):
        """Fail-closed : valeur nulle → fait inconnu → incertitude, jamais un
        refus. L'aide reste « à confirmer » et la question revient."""
        res = self._diagnostic({self.FACT_KEY: "les_deux"})
        self.assertEqual(
            [m["aide"]["id"] for m in res["aidesPotentiellementEligibles"]], ["fixture-aide"]
        )
        self.assertEqual(res["aidesNonEligibles"], [])

    def test_la_reponse_contraire_ecarte(self):
        res = self._diagnostic({self.FACT_KEY: "non"})
        self.assertEqual([m["aide"]["id"] for m in res["aidesNonEligibles"]], ["fixture-aide"])

    def test_la_reponse_favorable_rend_eligible(self):
        res = self._diagnostic({self.FACT_KEY: "oui"})
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fixture-aide"])

    def test_showforoptionids_inclut_la_reponse_neutre(self):
        """Une question branchée sur ce fait doit rester posée quand la réponse
        ne tranche pas : la condition peut encore s'appliquer (fail-closed)."""
        aide = _fixture_aide(
            [
                {
                    "id": "passerelle",
                    "text": "Gate passerelle.",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": self.FACT_KEY,
                    "predicate": {"eq": True},
                },
                {
                    "id": "dependante",
                    "text": "Ne s'applique qu'aux chantiers sur partie protégée.",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": "diagnostic_prealable_realise",
                    "predicate": {"eq": True},
                    "applies_if": {"fact": self.FACT_KEY, "predicate": {"eq": True}},
                },
            ]
        )
        res = run_deterministic_diagnostic(
            {"fixture-aide": aide},
            self._facts(),
            _monument(),
            3000,
            today=date(2026, 2, 14),
        )
        dependante = next(
            q for q in res["qcmQuestions"] if q["id"] == "diagnostic_prealable_realise"
        )
        self.assertEqual(dependante["dependsOn"]["questionId"], self.FACT_KEY)
        self.assertIn("les_deux", dependante["dependsOn"]["showForOptionIds"])
        self.assertNotIn("non", dependante["dependsOn"]["showForOptionIds"])


class TestBooleenSansOptions(unittest.TestCase):
    """Le cas de 562 faits : rien ne change, le couple implicite fait foi."""

    def test_options_implicites(self):
        fact = FactDef.model_validate({"type": "boolean", "scope": "projet", "question": "q ?"})
        self.assertEqual(
            [(o["id"], o["value"], o["unknown"]) for o in _options_for_fact(fact, [])],
            [("oui", True, False), ("non", False, False)],
        )

    def test_unknown_reste_tu_quand_le_fait_ne_declare_rien(self):
        """Contrat d'origine : le drapeau n'est émis que s'il vaut `true`. Le
        repli par libellé du front (`unknownAnswer.ts`) continue de s'appliquer
        aux options FABRIQUÉES par le moteur."""
        aide = _fixture_aide(
            [
                {
                    "id": "gate",
                    "text": "Le diagnostic préalable est réalisé.",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": "diagnostic_prealable_realise",
                    "predicate": {"eq": True},
                }
            ]
        )
        res = run_deterministic_diagnostic(
            {"fixture-aide": aide}, FACTS, _monument(), 3000, today=date(2026, 2, 14)
        )
        question = next(q for q in res["qcmQuestions"] if q["id"] == "diagnostic_prealable_realise")
        self.assertEqual([o["id"] for o in question["options"]], ["oui", "non", "skip"])
        self.assertTrue(all("unknown" not in o for o in question["options"]))


if __name__ == "__main__":
    unittest.main()


class TestAnneeConstructionDeduiteDuSiecle(unittest.TestCase):
    """Le siècle de la fiche répond à la place de l'utilisateur.

    `annee_construction` porte un `auto_source` sur `monument.siecle_construction` :
    inutile de demander l'année d'un monument dont la notice donne déjà le
    siècle. Un siècle n'étant pas une année, la déduction est un INTERVALLE :
    elle ne tranche que les seuils qu'elle tranche vraiment, et laisse la
    question posée sinon (fail-closed).
    """

    def _aide(self, predicate: dict):
        return _fixture_aide(
            [
                {
                    "id": "anciennete",
                    "text": "L'édifice doit être ancien.",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": "annee_construction",
                    "predicate": predicate,
                }
            ]
        )

    def _run(self, predicate: dict, siecle: str | None, answers: dict | None = None):
        monument = _monument(siecle_construction=siecle)
        ctx = build_context(monument, None, answers or {})
        return evaluate_aide(self._aide(predicate), monument, None, ctx, FACTS)

    def test_siecle_connu_tranche_le_gate_sans_question(self):
        verdict = self._run({"lt": 1800}, "XVIIe siècle")
        self.assertEqual(verdict.status, "eligible")
        self.assertEqual(verdict.missing_facts, {})

    def test_siecle_connu_elimine_quand_le_seuil_est_franchi(self):
        verdict = self._run({"lt": 1800}, "20e siècle")
        self.assertEqual(verdict.status, "non_eligible")
        self.assertEqual(verdict.missing_facts, {})

    def test_seuil_a_cheval_sur_le_siecle_pose_la_question(self):
        # Le 18e siècle court de 1701 à 1800 : « antérieur à 1800 » est vrai au
        # début, faux à la fin. On ne tranche pas, on demande.
        verdict = self._run({"lt": 1800}, "18e siècle")
        self.assertEqual(verdict.status, "potentiel")
        self.assertIn("annee_construction", verdict.missing_facts)

    def test_siecle_illisible_pose_la_question(self):
        verdict = self._run({"lt": 1800}, "Moyen Age")
        self.assertIn("annee_construction", verdict.missing_facts)

    def test_siecle_absent_pose_la_question(self):
        verdict = self._run({"lt": 1800}, None)
        self.assertIn("annee_construction", verdict.missing_facts)

    def test_la_reponse_prime_sur_le_siecle(self):
        # L'utilisateur répond 1850 : plus précis que « 17e siècle » de la fiche.
        verdict = self._run({"lt": 1800}, "XVIIe siècle", {"annee_construction": 1850})
        self.assertEqual(verdict.status, "non_eligible")

    def test_fourchette_de_siecles_lue_en_entier(self):
        # « 14e - 18e siècle » : les deux bornes partagent le mot « siècle ».
        # Ne lire que la dernière donnerait le 18e — le bâtiment est construit
        # au 14e et remanié jusqu'au 18e, c'est la PREMIÈRE campagne qui date
        # sa construction.
        from eligibility_engine import _annee_depuis_siecle

        self.assertEqual(tuple(_annee_depuis_siecle("14e - 18e siècle")), (1301, 1400))
        self.assertEqual(tuple(_annee_depuis_siecle("14e, 15e et 16e siècles")), (1301, 1400))
        self.assertEqual(tuple(_annee_depuis_siecle("12e au 14e siècle")), (1101, 1200))
        self.assertEqual(tuple(_annee_depuis_siecle("12e s.;13e s.")), (1101, 1200))
        self.assertEqual(tuple(_annee_depuis_siecle("xviie-xviiie siècles")), (1601, 1700))
        # Les quantièmes (« 2e moitié », « 4e quart ») ne sont pas des siècles.
        self.assertEqual(tuple(_annee_depuis_siecle("2e moitié 19e siècle")), (1801, 1900))
        self.assertEqual(tuple(_annee_depuis_siecle("4e quart 18e siècle")), (1701, 1800))
        self.assertIsNone(_annee_depuis_siecle("Moyen Age"))
        self.assertIsNone(_annee_depuis_siecle("Vieux siècle"))

    def test_edifice_remanie_reste_date_de_sa_construction(self):
        # Cas réel (château de Paley, « 14e - 18e siècle ») : « antérieur à
        # 1800 » est acquis, la question ne doit plus être posée.
        verdict = self._run({"lt": 1800}, "14e - 18e siècle")
        self.assertEqual(verdict.status, "eligible")
        self.assertEqual(verdict.missing_facts, {})

    def test_fourchette_encadrante_satisfaite(self):
        verdict = self._run({"all_of": [{"gte": 401}, {"lte": 1996}]}, "12e s.;13e s.")
        self.assertEqual(verdict.status, "eligible")

    def test_refus_deduit_de_la_fiche_nest_pas_impute_a_lutilisateur(self):
        verdict = self._run({"lt": 1800}, "20e siècle")
        self.assertFalse(_match_result(verdict)["elimineParReponse"])

    def test_refus_sur_reponse_reste_impute_a_lutilisateur(self):
        verdict = self._run({"lt": 1800}, None, {"annee_construction": 1850})
        self.assertTrue(_match_result(verdict)["elimineParReponse"])

    def test_fait_tranche_par_la_fiche_nest_pas_redemande_sous_un_applies_if(self):
        # Applicabilité inconnue : l'aide reste en incertitude (fail-closed),
        # mais l'inconnue est le fait PASSERELLE, pas l'année — que la fiche
        # donne déjà. Seule la passerelle est posée.
        aide = _fixture_aide(
            [
                {
                    "id": "anciennete",
                    "text": "L'édifice doit être ancien.",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": "annee_construction",
                    "predicate": {"lt": 1800},
                    "applies_if": {"fact": "porteur_est_proprietaire", "predicate": {"eq": True}},
                }
            ]
        )
        monument = _monument(siecle_construction="XVIIe siècle")
        ctx = build_context(monument, None, {})
        verdict = evaluate_aide(aide, monument, None, ctx, FACTS)
        self.assertEqual(verdict.status, "potentiel")
        self.assertNotIn("annee_construction", verdict.missing_facts)
        self.assertIn("porteur_est_proprietaire", verdict.gateway_facts)


class TestEgliseDeduiteDuNom(unittest.TestCase):
    """« Église Saint-Martin » répond d'avance à « est-ce une église ? ».

    Déduction POSITIVE seulement : un nom sans le mot ne prouve pas le
    contraire (« Notre-Dame de X », « Collégiale »), la question reste posée.
    """

    def _aide(self, fact: str = "edifice_eglise_ou_chapelle"):
        return _fixture_aide(
            [
                {
                    "id": "cultuel",
                    "text": "L'édifice doit être une église ou une chapelle.",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": fact,
                    "predicate": {"eq": True},
                }
            ]
        )

    def _run(self, nom: str, fact: str = "edifice_eglise_ou_chapelle", answers=None):
        monument = _monument(nom=nom)
        ctx = build_context(monument, None, answers or {})
        return evaluate_aide(self._aide(fact), monument, None, ctx, FACTS)

    def test_nom_qui_commence_par_eglise_repond_oui(self):
        verdict = self._run("Église Saint-Martin")
        self.assertEqual(verdict.status, "eligible")
        self.assertEqual(verdict.missing_facts, {})

    def test_accents_et_majuscules_indifferents(self):
        for nom in ("EGLISE SAINT-PIERRE", "église saint-pierre", "L'Église Notre-Dame"):
            self.assertEqual(self._run(nom).status, "eligible")

    def test_chapelle_et_qualificatifs(self):
        for nom in ("Chapelle des Pénitents", "Ancienne chapelle Saint-Roch"):
            self.assertEqual(self._run(nom).status, "eligible")

    def test_le_meme_nom_vaut_pour_ledifice_cultuel(self):
        verdict = self._run("Chapelle des Pénitents", fact="edifice_cultuel")
        self.assertEqual(verdict.status, "eligible")

    def test_toponyme_nest_pas_une_chapelle(self):
        # Le mot doit être la TÊTE du nom, sinon « Château de la Chapelle-… »
        # deviendrait une chapelle.
        for nom in ("Château de la Chapelle-Rainsouin", "Manoir de l'Église"):
            verdict = self._run(nom)
            self.assertIn("edifice_eglise_ou_chapelle", verdict.missing_facts)

    def test_nom_muet_laisse_la_question_posee(self):
        for nom in ("Notre-Dame de Paris", "Château de Paley", "Basilique Saint-Denis"):
            verdict = self._run(nom)
            self.assertIn("edifice_eglise_ou_chapelle", verdict.missing_facts)

    def test_la_reponse_negative_prime_sur_le_nom(self):
        # Un propriétaire qui a nommé « Chapelle » une grange peut le dire.
        verdict = self._run("Chapelle des Pénitents", answers={"edifice_eglise_ou_chapelle": "non"})
        self.assertEqual(verdict.status, "non_eligible")


class TestRangeValue(unittest.TestCase):
    """Sémantique universelle d'un intervalle : les deux bornes doivent
    s'accorder, et seuls les opérateurs de seuil concluent aux bornes."""

    def test_bornes_accordees_concluent(self):
        self.assertIs(evaluate_predicate({"lt": 1800}, RangeValue((1401, 1500))), True)
        self.assertIs(evaluate_predicate({"gte": 1800}, RangeValue((1401, 1500))), False)

    def test_bornes_en_desaccord_restent_indeterminees(self):
        self.assertIsNone(evaluate_predicate({"lt": 1800}, RangeValue((1701, 1800))))

    def test_operateur_non_monotone_reste_indetermine(self):
        # 1450 est dans l'intervalle : conclure « non » éliminerait à tort.
        self.assertIsNone(evaluate_predicate({"eq": 1450}, RangeValue((1401, 1500))))

    def test_intervalle_degenere_vaut_une_valeur(self):
        self.assertIs(evaluate_predicate({"eq": 1500}, RangeValue((1500, 1500))), True)


class TestOrdreDesQuestions(unittest.TestCase):
    """À nombre d'aides égal, les questions suivent l'ordre du règlement, pas
    l'alphabet : « possède un orgue » avant « âge de l'orgue », et les
    questions d'une même aide se suivent au lieu de se disperser."""

    ORGUE = {
        "id": "objet-orgue",
        "text": "Orgue à tuyaux existant",
        "kind": "user_fact",
        "fact": "possede_orgue_a_tuyaux",
        "predicate": {"eq": True},
    }
    AGE = {
        "id": "age",
        "text": "Instrument de plus de 50 ans",
        "kind": "user_fact",
        "fact": "age_orgue_ans",
        "predicate": {"gte": 50},
    }
    MANIFESTATIONS = {
        "id": "manifestations",
        "text": "Manifestations culturelles publiques",
        "kind": "user_fact",
        "fact": "manifestations_culturelles_publiques_orgue",
        "predicate": {"eq": True},
    }

    def _ids(self, aides: dict) -> list[str]:
        res = run_deterministic_diagnostic(aides, FACTS, _monument(), 3000, None)
        return [q["id"] for q in res["qcmQuestions"]]

    def test_ordre_de_la_source_plutot_que_l_alphabet(self):
        aide = _fixture_aide([self.ORGUE, self.AGE], slug="fx-orgue")
        self.assertEqual(self._ids({aide.slug: aide}), ["possede_orgue_a_tuyaux", "age_orgue_ans"])

    def test_les_questions_d_une_meme_aide_se_suivent(self):
        # Alphabet : age (fx-a), manifestations (fx-b), possede (fx-a) — fx-a
        # dispersée autour de fx-b. Attendu : fx-a entière, puis fx-b.
        a = _fixture_aide([self.ORGUE, self.AGE], slug="fx-a")
        b = _fixture_aide([self.MANIFESTATIONS], slug="fx-b")
        self.assertEqual(
            self._ids({a.slug: a, b.slug: b}),
            [
                "possede_orgue_a_tuyaux",
                "age_orgue_ans",
                "manifestations_culturelles_publiques_orgue",
            ],
        )

    def test_le_nombre_d_aides_prime_toujours(self):
        # `age_orgue_ans` sert deux aides : il passe avant le reste, quel que
        # soit l'ordre dans lequel fx-a l'énonce.
        a = _fixture_aide([self.ORGUE, self.AGE], slug="fx-a")
        b = _fixture_aide([self.AGE], slug="fx-b")
        self.assertEqual(self._ids({a.slug: a, b.slug: b})[0], "age_orgue_ans")

    def test_build_questions_sur_verdicts_vides(self):
        self.assertEqual(build_questions([], FACTS), [])


class TestFaitArtistiqueDeduitDesRaisons(unittest.TestCase):
    """Même déduction que pour l'événementiel : un pur chantier ne voit jamais
    « votre projet est-il artistique ou culturel ? » — l'étape « Votre projet »
    a déjà répondu non, comme le dit le `help` du fait."""

    FACT = "projet_artistique_ou_culturel"
    GATE = {
        "id": "objet-artistique",
        "text": "Réalisation d'un projet artistique ou culturel",
        "kind": "user_fact",
        "fact": FACT,
        "predicate": {"eq": True},
    }
    AIDE = _fixture_aide(
        [GATE],
        slug="fx-academie",
        raison=["restauration_travaux", "valorisation_rayonnement"],
    )

    def _run(self, answers=None):
        return run_deterministic_diagnostic(
            {self.AIDE.slug: self.AIDE}, FACTS, _monument(), 3000, answers
        )

    def _questions(self, res) -> set[str]:
        return {q["id"] for q in res["qcmQuestions"]}

    def test_travaux_seuls_repondent_non_sans_poser_la_question(self):
        res = self._run({"_raisons": ["restauration_travaux"]})
        self.assertNotIn(self.FACT, self._questions(res))
        self.assertEqual([m["aide"]["id"] for m in res["aidesNonEligibles"]], ["fx-academie"])

    def test_faire_vivre_le_lieu_laisse_la_question_posee(self):
        res = self._run({"_raisons": ["valorisation_rayonnement"]})
        self.assertIn(self.FACT, self._questions(res))
        self.assertEqual(len(res["aidesPotentiellementEligibles"]), 1)

    def test_reponse_de_l_utilisateur_prime_sur_la_deduction(self):
        res = self._run({"_raisons": ["restauration_travaux"], self.FACT: "oui"})
        self.assertNotIn(self.FACT, self._questions(res))
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-academie"])


class TestProjetSansTravaux(unittest.TestCase):
    """L'option « aucun » d'`etat_travaux` : la réponse de cadrage d'un projet
    « faire vivre le lieu ».

    Elle réfute par construction les deux familles de gates sur l'état des
    travaux — les programmes qui financent un chantier (`eq: non_commences`) et
    les prix qui en récompensent un (`eq: acheves`) — et déduit un budget de
    travaux nul, ce qui retire du QCM la question du budget.
    """

    FACT = "etat_travaux"
    BUDGET = "budget_travaux_estime"

    GATE_PROGRAMME = {
        "id": "travaux-non-commences",
        "text": "Les travaux ne doivent pas avoir commencé au dépôt du dossier.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": FACT,
        "predicate": {"eq": "non_commences"},
    }
    GATE_PRIX = {
        "id": "travaux-acheves",
        "text": "Le prix récompense un chantier achevé.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": FACT,
        "predicate": {"eq": "acheves"},
    }
    GATE_BUDGET = {
        "id": "budget-minimum",
        "text": "Le budget des travaux doit atteindre 10 000 € HT.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": BUDGET,
        "predicate": {"gte": 10000},
    }

    def _run(self, conditions: list[dict], answers=None, slug="fx-travaux"):
        aide = _fixture_aide(conditions, slug=slug)
        return run_deterministic_diagnostic({slug: aide}, FACTS, _monument(), 3000, answers)

    def _questions(self, res) -> list[str]:
        return [q["id"] for q in res["qcmQuestions"]]

    def test_aucun_refuse_un_programme_de_chantier(self):
        res = self._run([self.GATE_PROGRAMME], {self.FACT: "aucun"})
        self.assertEqual([m["aide"]["id"] for m in res["aidesNonEligibles"]], ["fx-travaux"])

    def test_aucun_refuse_un_prix_de_chantier(self):
        res = self._run([self.GATE_PRIX], {self.FACT: "aucun"})
        self.assertEqual([m["aide"]["id"] for m in res["aidesNonEligibles"]], ["fx-travaux"])

    def test_les_trois_autres_reponses_sont_inchangees(self):
        for reponse, attendu in (
            ("non_commences", "aidesEligibles"),
            ("en_cours", "aidesNonEligibles"),
            ("acheves", "aidesNonEligibles"),
        ):
            res = self._run([self.GATE_PROGRAMME], {self.FACT: reponse})
            self.assertEqual([m["aide"]["id"] for m in res[attendu]], ["fx-travaux"], reponse)

    def test_aucun_deduit_un_budget_de_travaux_nul(self):
        self.assertEqual(
            deduire_faits_des_faits({self.FACT: "aucun"}, FACTS),
            {self.FACT: "aucun", self.BUDGET: 0},
        )
        # Les autres réponses ne déduisent rien : le budget reste à demander.
        for reponse in ("non_commences", "en_cours", "acheves", "skip"):
            self.assertEqual(
                deduire_faits_des_faits({self.FACT: reponse}, FACTS),
                {self.FACT: reponse},
                reponse,
            )

    def test_la_question_du_budget_disparait_et_le_seuil_echoue(self):
        res = self._run([self.GATE_BUDGET], {self.FACT: "aucun"})
        self.assertNotIn(self.BUDGET, self._questions(res))
        self.assertEqual([m["aide"]["id"] for m in res["aidesNonEligibles"]], ["fx-travaux"])

    def test_la_reponse_de_l_utilisateur_prime_sur_la_deduction(self):
        res = self._run([self.GATE_BUDGET], {self.FACT: "aucun", self.BUDGET: "ge10000"})
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-travaux"])

    def test_la_question_du_budget_se_branche_sur_l_etat_des_travaux(self):
        """`dependsOn` : le front ne montre plus le budget dès qu'« aucun » est
        coché, et la source se pose AVANT lui."""
        res = self._run([self.GATE_PROGRAMME, self.GATE_BUDGET])
        ids = self._questions(res)
        self.assertEqual(ids[0], self.FACT)
        budget = next(q for q in res["qcmQuestions"] if q["id"] == self.BUDGET)
        self.assertEqual(budget["dependsOn"]["questionId"], self.FACT)
        self.assertNotIn("aucun", budget["dependsOn"]["showForOptionIds"])
        self.assertEqual(
            sorted(budget["dependsOn"]["showForOptionIds"]),
            ["acheves", "en_cours", "non_commences"],
        )

    def test_aucun_est_la_derniere_reponse_proposee(self):
        """« Aucun » ferme la liste : les trois réponses habituelles d'un projet
        de restauration restent en tête, dans leur ordre."""
        res = self._run([self.GATE_PROGRAMME])
        question = next(q for q in res["qcmQuestions"] if q["id"] == self.FACT)
        self.assertEqual(
            [o["id"] for o in question["options"]],
            ["non_commences", "en_cours", "acheves", "aucun", "skip"],
        )

    def test_le_fioul_apres_travaux_ne_se_pose_pas_sans_travaux(self):
        """« Après les travaux, la principale source d'énergie sera-t-elle encore
        le fioul ? » n'a pas de réponse quand il n'y a pas de travaux — un
        testeur l'a signalé le 2026-09-22. La porte est déclarée sur le FAIT
        (`pertinent_si: etat_travaux`), pas sur les aides : `_depends_on`
        renonçait, les cinq aides qui citent le fait ayant deux passerelles
        différentes.

        Deux effets d'un seul coup, et le second est le moins visible : la
        question disparaît, ET la condition qui l'exige cesse d'écarter l'aide
        (`_pertinence`, consultée par `evaluate_aide`).
        """
        exclusion = {
            "id": "pas-de-fioul-apres-travaux",
            "text": "La principale source d'énergie ne doit pas demeurer le fioul après travaux.",
            "kind": "user_fact",
            "effect": "gate",
            "fact": "chauffage_fioul_apres_travaux",
            "predicate": {"eq": False},
        }
        res = self._run([exclusion], {self.FACT: "aucun"})
        self.assertNotIn("chauffage_fioul_apres_travaux", self._questions(res))
        self.assertEqual(res["aidesNonEligibles"], [])
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-travaux"])

    def test_le_fioul_reste_pose_des_quil_y_a_un_chantier(self):
        for reponse in ("non_commences", "en_cours", "acheves"):
            with self.subTest(etat=reponse):
                exclusion = {
                    "id": "pas-de-fioul-apres-travaux",
                    "text": "La principale source d'énergie ne doit pas demeurer le fioul.",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": "chauffage_fioul_apres_travaux",
                    "predicate": {"eq": False},
                }
                res = self._run([exclusion], {self.FACT: reponse})
                self.assertIn("chauffage_fioul_apres_travaux", self._questions(res))

    def test_corpus_le_fioul_ne_survit_pas_a_aucun_travaux(self):
        """Sur le catalogue réel, et sur l'aide qui faisait passer la question :
        `region-grand-est-hotellerie-plein-air` accepte `etat_travaux: aucun`
        sans gate de budget, donc rien d'autre ne l'écartait."""
        res = run_deterministic_diagnostic(
            AIDES,
            FACTS,
            _monument(region="grand-est", departement_num="88", travaux_envisages=[]),
            1200,
            {
                "_raisons": ["valorisation_rayonnement"],
                "_familles": ["hebergement_touristique"],
                self.FACT: "aucun",
                "statut_juridique_porteur": ["association"],
            },
        )
        self.assertNotIn("chauffage_fioul_apres_travaux", self._questions(res))
        ecartees = {
            m["aide"]["id"]
            for m in res["aidesNonEligibles"]
            if any(
                e.get("conditionId") == "pas-de-fioul-apres-travaux"
                for e in (m["llmEvaluation"]["evaluations"] or [])
            )
        }
        self.assertEqual(ecartees, set())

    #: Aides `valorisation_rayonnement` qu'un projet SANS TRAVAUX ne peut
    #: toujours pas obtenir, et pourquoi. Dette de TYPAGE, pas de `raison` : le
    #: fait choisi à l'ingestion ne convient pas, et le corriger demande de
    #: rouvrir la source (`/ingest-aide`), pas de retoucher un prédicat.
    DETTE_DE_TYPAGE = {
        "56-valorisation-restauration-patrimoine": "plancher de 2 500 € posé sur "
        "`budget_travaux_estime` alors qu'il porte sur le coût du projet, "
        "« équipements de valorisation » compris",
        "71-label-ens": "planchers posés sur `budget_travaux_estime` alors que le label "
        "et le plan de gestion ne sont pas des travaux",
        "europa-nostra-heritage-awards": "`etat_travaux eq acheves` appliqué aux cinq "
        "catégories, alors que Recherche, Éducation et Engagement citoyen n'ont pas de "
        "chantier",
        "fondation-ca-paysdefrance": "plancher de 50 000 € sur `budget_travaux_estime` "
        "alors que la fondation finance aussi le patrimoine artistique et muséal",
        "naq-tourisme-sites-visites": "plancher de 50 000 € sur `budget_travaux_estime` "
        "alors que la modernisation d'un site de visite n'est pas que du bâti",
        "pdl-handicap-tourisme": "plancher de 1 500 € sur `budget_travaux_estime` alors "
        "que l'aide finance l'ACQUISITION d'équipements",
        "pdl-tourisme-culturel-innovation": "plancher de 5 000 € sur "
        "`budget_travaux_estime` alors que la première branche est un produit touristique",
        "prix-patrimoine-institut-de-france": "`etat_travaux eq acheves` alors que le "
        "prix récompense une ACTION de médiation déjà mise en place, pas un chantier",
        "prix-regional-biodiversite-paca-fondation-patrimoine": "`etat_travaux` appliqué "
        "aux deux branches, alors que la préservation de la biodiversité n'est pas un "
        "chantier",
        # Lot venu du pipeline de prospection (branche `feat/pipeline-prospection-
        # ingestion`), ingéré avant que cet invariant existe. Les `etat_travaux`
        # « dépôt avant démarrage » y ont été élargis à « aucun » comme ailleurs ; ne
        # restent que des PLANCHERS DE DÉPENSES posés sur `budget_travaux_estime`, qui
        # demandent de rouvrir la source pour savoir sur quelle assiette ils portent.
        "normandie-reconversion-espaces-activites-industriels-friche": "plancher de "
        "200 000 € sur `budget_travaux_estime` alors que la reconversion d'une friche "
        "porte aussi sur des études et de l'animation de site",
        "region-grand-est-chantiers-benevoles": "plancher de 2 000 € sur "
        "`budget_travaux_estime` alors qu'un chantier de bénévoles est d'abord une "
        "action de transmission",
        "region-grand-est-soutien-amenagement-musees-equipements": "plancher de "
        "150 000 € sur `budget_travaux_estime` alors que l'aide finance aussi des "
        "équipements muséographiques",
        "region-grand-est-soutien-developpement-tourisme-fluvial": "plancher de "
        "40 000 € sur `budget_travaux_estime`, et `etat_travaux` appliqué aux deux "
        "branches dont l'animation de l'escale",
        "region-grand-est-soutien-hebergements-collectifs": "plancher de 125 000 € sur "
        "`budget_travaux_estime` alors que l'assiette couvre aussi l'équipement",
        "region-grand-est-soutien-hostels": "plancher de 125 000 € sur "
        "`budget_travaux_estime` alors que l'assiette couvre aussi l'équipement",
        "region-grand-est-soutien-hotellerie": "plancher de 125 000 € sur "
        "`budget_travaux_estime` alors que l'assiette couvre aussi l'équipement",
        # Lot du 2026-09-18 (Charente, Landes), même motif : un plancher de
        # dépenses de l'OPÉRATION typé comme un budget de travaux.
        "16-restauration-patrimoine-protege-prive": "plancher de 3 000 € sur "
        "`budget_travaux_estime` alors qu'il porte sur les études ET les travaux, et que "
        "l'aide finance aussi la valorisation des restaurations (visite, exposition)",
        "40-appui-attractivite-touristique": "plancher de 50 000 € sur "
        "`budget_travaux_estime` alors que la source l'applique aux dépenses éligibles, "
        "études, aménagements et équipements inclus",
        "40-meubles-tourisme-chambres-hotes-hebergements-innovants": "plancher de "
        "10 000 € sur `budget_travaux_estime` alors qu'il porte sur la dépense "
        "subventionnable, qui couvre aussi l'équipement de l'hébergement",
    }

    def test_corpus_une_aide_de_valorisation_est_obtenable_sans_travaux(self):
        """L'invariant qui tient la cohérence entre `raison` et « aucun travaux ».

        Une aide ne porte `valorisation_rayonnement` que si elle finance une
        action SANS chantier (data/TYPING.md, § `raison`). Le moteur sait le
        vérifier : si un de ses gates est RÉFUTÉ par « ce projet ne comporte pas
        de travaux », elle ne le fait pas.

        C'est le filtre strict, posé sur la DONNÉE plutôt qu'au runtime : un tag
        faux se voit ici au lieu de se payer en aides hors sujet et en questions
        de chantier dans un projet d'animation. Le second passage de l'audit du
        2026-09-16 a corrigé 29 `raison` fautives et élargi 14 prédicats à
        l'état « aucun » ; les neuf restantes sont une dette de TYPAGE, nommée
        ci-dessus et à reprendre par l'ingestion.

        La réciproque n'est PAS un invariant : une aide de restauration a tout
        lieu de refuser « aucun », c'est même ce qui rend la réponse utile.
        """
        reponses = deduire_faits_des_faits({self.FACT: "aucun"}, FACTS)
        fautives = {}
        for slug, aide in AIDES.items():
            if "valorisation_rayonnement" not in aide.raison:
                continue
            refutes = [
                f"{c.id} ({c.fact})"
                for c in aide.conditions
                if c.kind == "user_fact"
                and c.effect == "gate"
                and c.fact in reponses
                and c.predicate is not None
                and evaluate_predicate(
                    c.predicate.root, _normalize_answer(FACTS.get(c.fact), reponses[c.fact])
                )
                is False
            ]
            if refutes:
                fautives[slug] = refutes
        self.assertEqual(
            sorted(fautives),
            sorted(self.DETTE_DE_TYPAGE),
            "une aide `valorisation_rayonnement` qu'un projet sans travaux ne peut pas "
            "obtenir : soit son `raison` est faux (retirer la valorisation), soit sa "
            "condition est trop large (énumérer « aucun » parmi les états admis), soit "
            "elle rejoint la dette de typage nommée dans DETTE_DE_TYPAGE",
        )


class TestProgrammeValorisationDeduitDesRaisons(unittest.TestCase):
    """Cocher « Faire vivre et ouvrir le lieu » EST un programme de
    valorisation : demander « prévoyez-vous des actions de valorisation après
    les travaux ? » juste après se lit comme une panne, et la question n'a de
    surcroît aucun sens pour un projet sans chantier.

    Déduction POSITIVE, la seule de la table : elle n'est tenable que parce
    qu'aucun gate du corpus ne porte `eq: false` sur ce fait (cf. le test de
    corpus ci-dessous), donc elle ne peut écarter personne.
    """

    FACT = "prevoit_programme_valorisation"
    GATE = {
        "id": "programme-de-valorisation",
        "text": "Le porteur doit prévoir un programme de valorisation du bien restauré.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": FACT,
        "predicate": {"eq": True},
    }
    AIDE = _fixture_aide(
        [GATE],
        slug="fx-valorisation",
        raison=["restauration_travaux", "valorisation_rayonnement"],
    )

    def _run(self, answers=None):
        return run_deterministic_diagnostic(
            {self.AIDE.slug: self.AIDE}, FACTS, _monument(), 3000, answers
        )

    def _questions(self, res) -> set[str]:
        return {q["id"] for q in res["qcmQuestions"]}

    def test_faire_vivre_repond_oui_sans_poser_la_question(self):
        res = self._run({"_raisons": ["valorisation_rayonnement"]})
        self.assertNotIn(self.FACT, self._questions(res))
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-valorisation"])

    def test_un_pur_chantier_garde_la_question(self):
        """L'inverse ne se déduit pas : un projet de restauration peut très bien
        prévoir un programme de valorisation, que plusieurs aides exigent."""
        res = self._run({"_raisons": ["restauration_travaux"]})
        self.assertIn(self.FACT, self._questions(res))
        self.assertEqual(len(res["aidesPotentiellementEligibles"]), 1)

    def test_sans_raisons_comportement_inchange(self):
        for answers in (None, {}, {"_raisons": []}):
            self.assertIn(self.FACT, self._questions(self._run(answers)), answers)

    def test_reponse_de_l_utilisateur_prime_sur_la_deduction(self):
        """Un « non » explicite survit à la déduction. L'aide tombe
        « atteignable » et non « non éligible » : le fait porte un levier
        (prévoir des actions de valorisation est un choix de conduite de
        projet), donc aucun de ses gates n'est dirimant."""
        res = self._run({"_raisons": ["valorisation_rayonnement"], self.FACT: "non"})
        self.assertEqual([m["aide"]["id"] for m in res["aidesAtteignables"]], ["fx-valorisation"])

    def test_corpus_aucun_gate_negatif_sur_le_fait_deduit(self):
        """Ce qui autorise la déduction positive. Un `eq: false` futur ferait
        « écartée par vos réponses » sans que l'utilisateur ait répondu."""
        fautifs = sorted(
            f"{slug} / {c.id}"
            for slug, aide in AIDES.items()
            for c in aide.conditions
            if c.fact == self.FACT
            and c.effect == "gate"
            and c.predicate is not None
            and evaluate_predicate(c.predicate.root, True) is False
        )
        self.assertEqual(fautifs, [])


class TestEntretienCourantEtRenovationFondamentale(unittest.TestCase):
    """Deux questions qui se contredisaient en se suivant (retour de test).

    « Vos travaux relèvent-ils de l'entretien courant ? » puis « Votre programme
    relève-t-il d'une création, d'une extension ou d'une rénovation en
    profondeur ? » : la seconde excluait l'entretien courant dans son énoncé
    même, et se posait pourtant à quelqu'un qui venait de répondre. Pire, elle
    se posait souvent EN PREMIER — le classement par nombre d'aides dépend des
    aides encore vivantes, et sur un profil vosgien la question d'hôtellerie
    passait devant.

    Ce n'est PAS un cas de `pertinent_si` : le fait a bel et bien une valeur
    pour ce profil (`false`), et les cinq aides qui l'exigent doivent voir leur
    critère REFUSÉ — avec le levier qui va avec —, pas ignoré. C'est une
    déduction : le serveur connaît déjà la réponse.

    Le sens de la déduction n'est pas neutre : la source se pose avant sa cible,
    donc c'est la question la plus partagée qui passe devant (13 aides contre
    5). La réciproque serait aussi vraie, mais poserait une question
    d'hôtellerie à tout le monde — et deux entrées croisées feraient un cycle.
    """

    ENTRETIEN = "travaux_entretien_courant"
    RENOVATION = "projet_renovation_fondamentale"

    GATE_ENTRETIEN = {
        "id": "exclusion-entretien",
        "text": "Les travaux d'entretien courant ne sont pas éligibles.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": ENTRETIEN,
        "predicate": {"eq": False},
    }
    GATE_RENOVATION = {
        "id": "renovation-fondamentale",
        "text": "Le programme relève d'une création, d'une extension ou d'une rénovation.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": RENOVATION,
        "predicate": {"eq": True},
    }

    def _run(self, conditions: list[dict], answers=None):
        aide = _fixture_aide(conditions, slug="fx-renov")
        return run_deterministic_diagnostic({"fx-renov": aide}, FACTS, _monument(), 3000, answers)

    def _questions(self, res) -> list[str]:
        return [q["id"] for q in res["qcmQuestions"]]

    def test_entretien_courant_repond_non_a_la_renovation(self):
        self.assertEqual(
            deduire_faits_des_faits({self.ENTRETIEN: "oui"}, FACTS),
            {self.ENTRETIEN: "oui", self.RENOVATION: False},
        )

    def test_linverse_ne_se_deduit_pas(self):
        """Ne pas être de l'entretien courant ne fait pas une rénovation
        fondamentale : une mise aux normes seule et un simple rafraîchissement
        répondent « non » aux deux questions. C'est aussi ce qui interdit de
        fusionner les deux faits."""
        for reponse in ("non", "skip"):
            self.assertEqual(
                deduire_faits_des_faits({self.ENTRETIEN: reponse}, FACTS),
                {self.ENTRETIEN: reponse},
                reponse,
            )

    def test_la_question_disparait_et_le_critere_est_refuse(self):
        """Refusé, pas ignoré : le fait porte un levier, l'aide part donc « à
        débloquer » avec la démarche qui la rouvrirait."""
        res = self._run([self.GATE_RENOVATION], {self.ENTRETIEN: "oui"})
        self.assertNotIn(self.RENOVATION, self._questions(res))
        self.assertEqual([m["aide"]["id"] for m in res["aidesAtteignables"]], ["fx-renov"])

    def test_la_source_se_pose_avant_sa_cible_et_la_branche(self):
        res = self._run([self.GATE_ENTRETIEN, self.GATE_RENOVATION])
        ids = self._questions(res)
        self.assertLess(ids.index(self.ENTRETIEN), ids.index(self.RENOVATION))
        question = next(q for q in res["qcmQuestions"] if q["id"] == self.RENOVATION)
        self.assertEqual(
            question["dependsOn"],
            {"questionId": self.ENTRETIEN, "showForOptionIds": ["non"]},
        )

    def test_la_reponse_de_l_utilisateur_prime_sur_la_deduction(self):
        res = self._run([self.GATE_RENOVATION], {self.ENTRETIEN: "oui", self.RENOVATION: "oui"})
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-renov"])

    def test_corpus_aucune_aide_ne_gate_les_deux_faits(self):
        """L'invariant qui rend la déduction sûre : si une aide exigeait les
        deux, elle poserait deux fois la même question à un candidat, et la
        déduction trancherait l'une sans qu'il l'ait vue."""
        fautives = sorted(
            slug
            for slug, aide in AIDES.items()
            if {c.fact for c in aide.conditions} >= {self.ENTRETIEN, self.RENOVATION}
        )
        self.assertEqual(fautives, [])

    def test_corpus_la_renovation_nest_jamais_exigee_a_l_envers(self):
        """Tous les gates du fait déduit sont `eq: true` : la valeur déduite
        (`false`) ne peut donc que refuser, jamais rendre une aide éligible sur
        un critère que l'utilisateur n'a pas renseigné."""
        fautifs = sorted(
            f"{slug} / {c.id}"
            for slug, aide in AIDES.items()
            for c in aide.conditions
            if c.fact == self.RENOVATION
            and c.effect == "gate"
            and c.predicate is not None
            and evaluate_predicate(c.predicate.root, False) is not False
        )
        self.assertEqual(fautifs, [])


class TestReponseQuiNeTranchePas(unittest.TestCase):
    """Un `boolean` qui déclare ses réponses, dont une troisième qui ne tranche pas.

    Le cas venait de `s_engage_mesure_impact_environnemental` : l'engagement
    portait sur des indicateurs que chaque financeur définit à sa façon, « oui »
    ou « non » dans l'abstrait n'était répondable par personne, et un « non » par
    prudence écartait des aides. « Selon l'aide en jeu » laissait le fait
    INCONNU — la condition reste une incertitude, l'aide reste « à confirmer »,
    et aucun prédicat d'aide n'a eu à bouger.

    Le fait réel est parti avec le lot des engagements (2026-09-22), qui a retypé
    toute la famille en `info` : la question ne se pose plus du tout, ce qui est
    une meilleure réponse encore. La SÉMANTIQUE testée ici, elle, ne dépendait
    pas de ce fait-là et reste celle du moteur — d'où une fixture, sur le patron
    de `TestPertinentSi._facts`.
    """

    FACT = "fixture_selon_aide"
    GATE = {
        "id": "mesure-impact",
        "text": "Le porteur chiffre l'impact environnemental visé par les travaux.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": FACT,
        "predicate": {"eq": True},
    }

    def _facts(self) -> dict[str, FactDef]:
        return {
            **FACTS,
            self.FACT: FactDef.model_validate(
                {
                    "type": "boolean",
                    "scope": "projet",
                    "question": "Acceptez-vous de chiffrer l'impact environnemental visé ?",
                    # R1 du schéma : un booléen qui déclare ses options DOIT
                    # garder « oui » et « non », les réponses déjà enregistrées
                    # en dépendent. La troisième ne porte pas de valeur.
                    "options": [
                        {"id": "oui", "label": "Oui", "valeur": True},
                        {"id": "non", "label": "Non", "valeur": False},
                        {"id": "selon_aide", "label": "Selon l'aide en jeu", "unknown": True},
                    ],
                    # Le fait réel portait un levier (une contrepartie à
                    # accepter, pas un droit à obtenir) : c'est lui qui rend
                    # `non` « atteignable » plutôt que refusé, et qui vide la
                    # table des éliminations.
                    "levier": {
                        "resume": "Rien à obtenir de personne : une contrepartie à accepter.",
                    },
                }
            ),
        }

    def _run(self, answers=None):
        aide = _fixture_aide([self.GATE], slug="fx-impact")
        return run_deterministic_diagnostic(
            {"fx-impact": aide}, self._facts(), _monument(), 3000, answers
        )

    def test_les_trois_reponses_sont_proposees_dans_lordre(self):
        question = next(q for q in self._run()["qcmQuestions"] if q["id"] == self.FACT)
        self.assertEqual(
            [o["id"] for o in question["options"]], ["oui", "non", "selon_aide", "skip"]
        )

    def test_oui_et_non_gardent_leur_sens(self):
        """R1 du schéma : les réponses déjà enregistrées ne changent pas de sens.
        `non` laisse l'aide « atteignable » plutôt que refusée, le fait portant
        un levier (c'est une contrepartie à accepter, pas un droit à obtenir)."""
        self.assertEqual(
            [m["aide"]["id"] for m in self._run({self.FACT: "oui"})["aidesEligibles"]],
            ["fx-impact"],
        )
        self.assertEqual(
            [m["aide"]["id"] for m in self._run({self.FACT: "non"})["aidesAtteignables"]],
            ["fx-impact"],
        )

    def test_selon_laide_n_ecarte_jamais(self):
        res = self._run({self.FACT: "selon_aide"})
        self.assertEqual(res["aidesNonEligibles"], [])
        self.assertEqual(
            [m["aide"]["id"] for m in res["aidesPotentiellementEligibles"]], ["fx-impact"]
        )

    def test_selon_laide_ne_porte_aucune_elimination(self):
        """Le front recalcule les éliminations sans appeler le serveur
        (`computeEliminatedAideIds`) : la table ne doit rien porter sur cette
        réponse. Elle est ici vide pour TOUTES les réponses, le fait ayant un
        levier — la mécanique générale (`non` écarte, la réponse qui ne tranche
        pas non) est couverte par TestBooleenAReponsesDeclarees."""
        question = next(q for q in self._run()["qcmQuestions"] if q["id"] == self.FACT)
        self.assertEqual(question["eliminationsParOption"].get("selon_aide", []), [])


class TestFamillesPrefilter(unittest.TestCase):
    """Étape « Les activités » : les familles cochées (clé réservée `_familles`)
    écartent les aides d'un autre thème.

    Miroir de `TestRaisonPrefilter` un cran plus fin : `raison` met dans le même
    sac un festival, un gîte et un outil de médiation, la famille les sépare.
    """

    SPECTACLE = _fixture_aide([], slug="fx-spectacle", familles=["spectacles_manifestations"])
    HEBERGEMENT = _fixture_aide([], slug="fx-hebergement", familles=["hebergement_touristique"])
    SANS_FAMILLE = _fixture_aide([], slug="fx-sans-famille")
    MIXTE = _fixture_aide(
        [],
        slug="fx-mixte",
        familles=["spectacles_manifestations", "hebergement_touristique"],
    )
    # Une aide de restauration taguée bâti, pour le cas des projets anciens.
    BATI = _fixture_aide(
        [], slug="fx-bati", raison=["restauration_travaux"], familles=["restauration_bati"]
    )

    def _run(self, aides, answers=None):
        catalogue = {a.slug: a for a in aides}
        return run_deterministic_diagnostic(catalogue, FACTS, _monument(), 3000, answers)

    def _slugs(self, res) -> set[str]:
        return {
            m["aide"]["id"]
            for bucket in (
                "aidesEligibles",
                "aidesPotentiellementEligibles",
                "aidesAtteignables",
                "aidesNonEligibles",
            )
            for m in res[bucket]
        }

    def test_familles_ecartent_les_aides_hors_theme(self):
        res = self._run(
            [self.SPECTACLE, self.HEBERGEMENT], {"_familles": ["spectacles_manifestations"]}
        )
        self.assertEqual(self._slugs(res), {"fx-spectacle"})
        self.assertEqual(res["totalAidesAnalysees"], 1)

    def test_aide_sans_famille_passe_toujours(self):
        """Fail-open, comme pour `raison` : faute de tag, on ne masque jamais."""
        res = self._run(
            [self.HEBERGEMENT, self.SANS_FAMILLE], {"_familles": ["spectacles_manifestations"]}
        )
        self.assertEqual(self._slugs(res), {"fx-sans-famille"})

    def test_intersection_partielle_suffit(self):
        res = self._run([self.MIXTE], {"_familles": ["spectacles_manifestations"]})
        self.assertEqual(self._slugs(res), {"fx-mixte"})

    def test_montrez_moi_tout_ne_filtre_rien(self):
        """`[]` est une RÉPONSE (« je ne sais pas encore »), pas une absence :
        elle ne filtre rien, comme la clé absente."""
        for answers in (None, {}, {"_familles": []}):
            res = self._run([self.SPECTACLE, self.HEBERGEMENT], answers)
            self.assertEqual(self._slugs(res), {"fx-spectacle", "fx-hebergement"}, answers)

    def test_un_projet_ancien_multi_intentions_garde_ses_aides_de_travaux(self):
        """`FAMILLES_PAR_RAISON` : l'intention « restaurer » implique les cinq
        familles de chantier. Sans ça, un projet d'avant le choix exclusif qui
        repasse le wizard et coche « spectacles » perdrait toutes ses aides de
        restauration — elles ne sont pas hors sujet, elles sont l'autre moitié
        de son projet."""
        res = self._run(
            [self.SPECTACLE, self.HEBERGEMENT, self.BATI],
            {
                "_raisons": ["restauration_travaux", "valorisation_rayonnement"],
                "_familles": ["spectacles_manifestations"],
            },
        )
        self.assertEqual(self._slugs(res), {"fx-spectacle", "fx-bati"})

    def test_les_familles_implicites_ne_declenchent_pas_le_filtre(self):
        """Un projet de restauration ne voit PAS l'étape des activités : ses
        familles implicites ne doivent donc rien filtrer, sinon il perdrait
        toute aide taguée hors des cinq familles de chantier."""
        res = self._run([self.SPECTACLE, self.BATI], {"_raisons": ["restauration_travaux"]})
        self.assertEqual(self._slugs(res), {"fx-spectacle", "fx-bati"})

    #: Les deux successeurs de `tourisme_hebergement`, scindé le 2026-09-22.
    VISITE = _fixture_aide([], slug="fx-visite", familles=["tourisme_visite"])

    def test_un_code_de_famille_retire_vaut_ses_successeurs(self):
        """`FAMILLES_HERITEES` : un projet cadré AVANT la scission porte encore
        `tourisme_hebergement` dans son questionnaire, et rien ne le réécrit.
        Sans l'alias, il déclarerait une famille qu'aucune aide ne porte —
        déclaré non vide, intersection vide — et perdrait TOUTES les aides
        taguées, l'inverse exact de ce qu'il a demandé."""
        res = self._run(
            [self.HEBERGEMENT, self.VISITE, self.SPECTACLE],
            {"_familles": ["tourisme_hebergement"]},
        )
        self.assertEqual(self._slugs(res), {"fx-hebergement", "fx-visite"})

    def test_un_code_de_famille_inconnu_ne_ferme_que_lui_meme(self):
        """Fail-open : un code venu de la base qui n'est ni vivant ni hérité est
        gardé tel quel. Il ne rencontre aucune aide, mais il n'en ouvre pas
        d'autres par la bande — et les codes cochés à côté continuent de valoir."""
        res = self._run(
            [self.HEBERGEMENT, self.SPECTACLE],
            {"_familles": ["famille_future", "spectacles_manifestations"]},
        )
        self.assertEqual(self._slugs(res), {"fx-spectacle"})

    def test_cle_reservee_ne_devient_pas_un_fait(self):
        facts_answers, reserved = split_reserved_answers(
            {"_familles": ["spectacles_manifestations"], "etat_travaux": "aucun"}
        )
        self.assertEqual(facts_answers, {"etat_travaux": "aucun"})
        self.assertEqual(reserved, {"_familles": ["spectacles_manifestations"]})

    def test_valeur_mal_formee_ne_filtre_rien(self):
        """Le dict vient de `projets.questionnaire`, donc d'un enregistrement
        qui peut précéder la clé ou l'avoir mal écrite : fail-open."""
        for brut in ("spectacles_manifestations", 42, None, [None, 7]):
            res = self._run([self.SPECTACLE, self.HEBERGEMENT], {"_familles": brut})
            self.assertEqual(self._slugs(res), {"fx-spectacle", "fx-hebergement"}, repr(brut))

    def test_aide_display_expose_les_familles(self):
        res = self._run([self.SPECTACLE], {"_familles": ["spectacles_manifestations"]})
        match = (res["aidesEligibles"] + res["aidesPotentiellementEligibles"])[0]
        self.assertEqual(match["aide"]["familles"], ["spectacles_manifestations"])


class TestFaitsDeduitsDesFamilles(unittest.TestCase):
    """Les familles cochées répondent d'avance aux faits de PÉRIMÈTRE d'un autre
    thème : avoir coché « spectacles » dit déjà que le projet n'est pas un
    hébergement touristique.

    La garde est le cœur du dispositif. `hors_famille` promet un fail-open PAR
    AIDE, alors que la déduction agit PAR FAIT : répondre « non » à un fait de
    périmètre écarte, via `hors_perimetre`, les aides non taguées qui s'appuient
    dessus. On ne déduit donc que si toutes les porteuses du fait sont taguées
    dans les familles que la table associe à CE fait.
    """

    FACT = "projet_hebergement_touristique"
    PERIMETRE = {"fact": FACT, "predicate": {"eq": True}}

    def _aide(self, slug, familles, perimetre=True):
        return _fixture_aide(
            [],
            slug=slug,
            familles=familles,
            **({"applies_if": self.PERIMETRE} if perimetre else {}),
        )

    def _run(self, aides, answers):
        catalogue = {a.slug: a for a in aides}
        return run_deterministic_diagnostic(catalogue, FACTS, _monument(), 3000, answers)

    def _questions(self, res) -> set[str]:
        return {q["id"] for q in res["qcmQuestions"]}

    EXCLUSION = {
        "id": "pas-un-hebergement",
        "text": "Le dispositif ne finance pas les hébergements touristiques.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": FACT,
        "predicate": {"eq": False},
    }

    def test_une_famille_dun_autre_theme_repond_non_davance(self):
        """Ce que la déduction supprime, c'est la QUESTION — ici celle qu'une
        aide de spectacles pose en EXCLUSION (« pas un hébergement »). Avoir
        coché « spectacles » y répond déjà, et l'aide devient éligible sans
        qu'on ait eu à demander."""
        aide = _fixture_aide(
            [self.EXCLUSION], slug="fx-spectacle", familles=["spectacles_manifestations"]
        )
        res = self._run([aide], {"_familles": ["spectacles_manifestations"]})
        self.assertNotIn(self.FACT, self._questions(res))
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-spectacle"])

    def test_un_gate_positif_mal_tague_bloque_la_deduction(self):
        """Le cas le plus dangereux, et il existe dans le corpus : treize aides
        gatent `eq: true` sur un fait de la table SANS en faire leur périmètre.
        Déduire « non » les ferait tomber « écartées par vos réponses » sans que
        l'utilisateur ait rien répondu. La garde regarde donc les conditions
        autant que les périmètres."""
        positif = {**self.EXCLUSION, "id": "est-un-lieu", "predicate": {"eq": True}}
        aide = _fixture_aide([positif], slug="fx-non-taguee")
        exclusion = _fixture_aide(
            [self.EXCLUSION], slug="fx-spectacle", familles=["spectacles_manifestations"]
        )
        res = self._run([aide, exclusion], {"_familles": ["spectacles_manifestations"]})
        self.assertIn(self.FACT, self._questions(res))
        self.assertEqual(res["aidesNonEligibles"], [])

    def test_la_tuile_hebergement_repond_oui_davance(self):
        """Le miroir POSITIF, entré le 2026-09-22 avec la scission de
        `tourisme_hebergement`. Cocher « Hébergement touristique » DIT que le
        projet en est un : reposer la question juste après se lit comme une
        panne, et c'est le symptôme qu'un testeur a rapporté."""
        aide = self._aide("fx-hebergement", ["hebergement_touristique"])
        res = self._run([aide], {"_familles": ["hebergement_touristique"]})
        self.assertNotIn(self.FACT, self._questions(res))
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-hebergement"])

    def test_les_deux_tuiles_de_tourisme_laissent_la_question_posee(self):
        """Qui coche l'hébergement ET les sites de visite n'a rien déclaré de
        tranché : la question reste, et c'est elle qui départage. C'est tout
        l'intérêt d'avoir scindé la famille — une seule tuile ne pouvait rien
        dire, deux peuvent."""
        aide = self._aide("fx-hebergement", ["hebergement_touristique"])
        visite = _fixture_aide([self.EXCLUSION], slug="fx-visite", familles=["tourisme_visite"])
        res = self._run(
            [aide, visite], {"_familles": ["hebergement_touristique", "tourisme_visite"]}
        )
        self.assertIn(self.FACT, self._questions(res))
        self.assertEqual(res["aidesNonEligibles"], [])

    def test_une_aide_qui_exclut_lhebergement_bloque_la_deduction(self):
        """La garde vaut dans les DEUX sens. Une aide encore candidate qui gate
        `eq: false` sur le fait tomberait « écartée par vos réponses » sur une
        question jamais posée : tant qu'elle est là, on demande. Après le re-tag
        du 2026-09-22, les trois du corpus sortent par `hors_famille` avant la
        déduction — mais la garde ne fait pas confiance aux tags."""
        aide = self._aide("fx-hebergement", ["hebergement_touristique"])
        exclut = _fixture_aide(
            [self.EXCLUSION], slug="fx-exclut", familles=["hebergement_touristique"]
        )
        res = self._run([aide, exclut], {"_familles": ["hebergement_touristique"]})
        self.assertIn(self.FACT, self._questions(res))
        self.assertEqual(res["aidesNonEligibles"], [])

    def test_corpus_la_garde_protege_les_gates_negatifs(self):
        """Pendant de `test_corpus_la_garde_protege_tous_les_gates_positifs`,
        pour la déduction POSITIVE : les aides du corpus qu'un « oui » réfute
        doivent toutes être vues par la garde."""
        exposees = sorted(
            slug
            for slug, aide in AIDES.items()
            for c in aide.conditions
            if c.fact in FAITS_DEDUITS_VRAI_DES_FAMILLES
            and c.effect == "gate"
            and c.predicate is not None
            and evaluate_predicate(c.predicate.root, True) is False
        )
        self.assertTrue(exposees, "le corpus n'expose plus le cas : test à revoir")
        for slug in exposees:
            self.assertTrue(
                any(
                    _retournerait_contre(AIDES[slug], fait, True)
                    for fait in FAITS_DEDUITS_VRAI_DES_FAMILLES
                ),
                f"{slug} n'est pas vue par la garde",
            )

    def test_corpus_chaque_region_pose_au_plus_une_question_de_tourisme(self):
        """Le profil du testeur, région par région : « hébergement » seul, sans
        travaux. Aucune région ne doit reposer `projet_hebergement_touristique`
        — la tuile y répond — et le tronc doit rester court. `type_hebergement_
        touristique` reste légitime : il DEMANDE lequel, ce que la tuile ne dit
        pas."""
        for region, departement in (
            ("grand-est", "88"),
            ("normandie", "14"),
            ("nouvelle-aquitaine", "33"),
            ("centre-val-de-loire", "37"),
            ("auvergne-rhone-alpes", "69"),
            ("pays-de-la-loire", "44"),
        ):
            with self.subTest(region=region):
                monument = _monument(
                    region=region, departement_num=departement, travaux_envisages=[]
                )
                res = run_deterministic_diagnostic(
                    AIDES,
                    FACTS,
                    monument,
                    1200,
                    {
                        "_raisons": ["valorisation_rayonnement"],
                        "_familles": ["hebergement_touristique"],
                        "etat_travaux": "aucun",
                        "statut_juridique_porteur": ["association"],
                    },
                )
                self.assertNotIn(self.FACT, self._questions(res), region)

    def test_une_porteuse_non_taguee_bloque_la_deduction(self):
        """Le cas qui justifie la garde : sans elle, une aide non taguée à
        périmètre tourisme serait écartée par la bande, alors que
        `hors_famille` vient de la laisser passer."""
        mixte = self._aide("fx-mixte", ["hebergement_touristique", "spectacles_manifestations"])
        nue = self._aide("fx-non-taguee", [])
        res = self._run([mixte, nue], {"_familles": ["spectacles_manifestations"]})
        self.assertIn(self.FACT, self._questions(res))
        self.assertIn(
            "fx-non-taguee", {m["aide"]["id"] for m in res["aidesPotentiellementEligibles"]}
        )

    def test_une_porteuse_taguee_hors_table_bloque_la_deduction(self):
        """Même raison : une aide « festival touristique » taguée spectacles est
        gardée par `hors_famille`, la déduction la tuerait."""
        festival = self._aide("fx-festival", ["spectacles_manifestations"])
        res = self._run([festival], {"_familles": ["spectacles_manifestations"]})
        self.assertIn(self.FACT, self._questions(res))

    def test_sans_familles_declarees_aucune_deduction(self):
        aide = self._aide("fx-hebergement", ["hebergement_touristique"])
        for answers in (None, {}, {"_familles": []}):
            res = self._run([aide], answers)
            self.assertIn(self.FACT, self._questions(res), answers)

    def test_la_reponse_de_l_utilisateur_prime(self):
        mixte = self._aide("fx-mixte", ["hebergement_touristique", "spectacles_manifestations"])
        res = self._run([mixte], {"_familles": ["spectacles_manifestations"], self.FACT: "oui"})
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-mixte"])

    def test_answers_du_caller_non_mutees(self):
        mixte = self._aide("fx-mixte", ["hebergement_touristique", "spectacles_manifestations"])
        answers = {"_familles": ["spectacles_manifestations"]}
        self._run([mixte], answers)
        self.assertEqual(answers, {"_familles": ["spectacles_manifestations"]})

    def test_corpus_aucun_fait_du_monument_dans_la_table(self):
        """Un fait de scope `monument` n'a rien à faire dans la table : il décrit
        le BIEN, et un jardin ne cesse pas d'exister parce qu'on monte un
        festival. Les faits de porteur (`porteur_compagnie_artistique`…), eux,
        y sont légitimes : ils décrivent qui dépose, ce que le thème du projet
        renseigne bel et bien."""
        fautifs = sorted(
            f"{k} (scope {FACTS[k].scope})"
            for k in FAITS_DEDUITS_DES_FAMILLES
            if k in FACTS and FACTS[k].scope == "monument"
        )
        self.assertEqual(fautifs, [])

    def test_corpus_les_faits_deduits_existent_et_sont_des_booleens(self):
        """La déduction écrit `False` : sur un `multi_enum`, elle n'aurait aucun
        sens (`_normalize_answer` en attend une liste d'options)."""
        fautifs = sorted(
            k for k in FAITS_DEDUITS_DES_FAMILLES if k not in FACTS or FACTS[k].type != "boolean"
        )
        self.assertEqual(fautifs, [])

    def test_corpus_les_familles_citees_existent(self):
        inconnues = sorted(
            {f for familles in FAITS_DEDUITS_DES_FAMILLES.values() for f in familles}
            - set(FAMILLES)
        ) + sorted(
            {f for familles in FAMILLES_PAR_RAISON.values() for f in familles} - set(FAMILLES)
        )
        self.assertEqual(inconnues, [])

    def test_corpus_la_garde_protege_tous_les_gates_positifs(self):
        """Le corpus compte treize aides qui gatent `eq: true` sur un fait de la
        table SANS en faire leur périmètre (les lieux de diffusion de
        Seine-et-Marne, les compagnies, les écoles de musique…). Chacune doit
        être vue par la garde : déduire « non » les ferait tomber « écartées par
        vos réponses » sur une question jamais posée.

        C'est l'invariant que la garde tient par construction ; ce test vérifie
        qu'elle les voit bien, et il échouerait si la garde revenait à ne
        regarder que les périmètres.

        À ne pas confondre avec la table des RAISONS, qui n'a PAS de garde (elle
        déduit de la seule intention déclarée) : là, une élimination sans
        question posée existe et est assumée — l'aide à projet de l'Académie des
        beaux-arts est bien écartée d'un projet purement de travaux, et
        l'utilisateur l'a dit en cochant son intention.
        """
        exposees = sorted(
            slug
            for slug, aide in AIDES.items()
            for c in aide.conditions
            if c.fact in FAITS_DEDUITS_DES_FAMILLES
            and c.effect == "gate"
            and c.predicate is not None
            and evaluate_predicate(c.predicate.root, False) is False
        )
        self.assertTrue(exposees, "le corpus n'expose plus le cas : test à revoir")
        for slug in exposees:
            self.assertTrue(
                _retournerait_contre(AIDES[slug], _fait_gate(AIDES[slug])),
                f"{slug} n'est pas vue par la garde",
            )

    def test_corpus_une_aide_taguee_a_perimetre_deduit_reste_dans_la_table(self):
        """L'invariant qui protège la garde : une aide qui porte des familles ET
        dont le périmètre est un fait de la table doit les porter DANS les
        familles de ce fait. Sinon `hors_famille` la garde et la déduction la
        tue — le seul cas où les deux mécaniques se contredisent.

        Une aide SANS famille est hors sujet ici : la garde la voit et renonce
        à déduire (fail-closed), ce que testent les cas synthétiques ci-dessus.
        """
        fautives = sorted(
            f"{slug} ({aide.applies_if.fact} ← {aide.familles})"
            for slug, aide in AIDES.items()
            if aide.applies_if
            and aide.applies_if.fact in FAITS_DEDUITS_DES_FAMILLES
            and aide.familles
            and not set(aide.familles) <= FAITS_DEDUITS_DES_FAMILLES[aide.applies_if.fact]
        )
        self.assertEqual(fautives, [])


class TestPertinentSi(unittest.TestCase):
    """`pertinent_si` : la dépendance déclarée UNE FOIS sur le fait.

    « Depuis combien d'années les travaux sont-ils achevés ? » n'a de sens que
    si `etat_travaux = acheves`. C'est une propriété du FAIT, pas de telle aide,
    et elle était recopiée en `applies_if` sur chacune des quatre conditions qui
    le citaient. Le moteur la reporte désormais comme il reporte le périmètre
    d'une aide, et le reste suit tout seul : `dependsOn`, `gateway_facts`, ordre
    des questions.
    """

    FACT = "fixture_anciennete"
    SOURCE = "etat_travaux"

    def _facts(self, **surcharge) -> dict[str, FactDef]:
        return {
            **FACTS,
            self.FACT: FactDef.model_validate(
                {
                    "type": "integer",
                    "scope": "projet",
                    "unit": "ans",
                    "question": "Depuis combien d'années les travaux sont-ils achevés ?",
                    "pertinent_si": {"fact": self.SOURCE, "predicate": {"eq": "acheves"}},
                    **surcharge,
                }
            ),
        }

    GATE = {
        "id": "acheve-recemment",
        "text": "Le chantier doit être achevé depuis moins de 3 ans.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": FACT,
        "predicate": {"lte": 3},
    }

    def _run(self, answers=None, aide=None, facts=None):
        aide = aide or _fixture_aide([self.GATE], slug="fx-prix")
        return run_deterministic_diagnostic(
            {aide.slug: aide}, facts or self._facts(), _monument(), 3000, answers
        )

    def _questions(self, res) -> dict[str, dict]:
        return {q["id"]: q for q in res["qcmQuestions"]}

    def _aide_a_clause_propre(self) -> Aide:
        """Cas Normandie : la condition porte SA clause, qui n'est pas la porte.

        `_scoped_conditions` garde la clause propre et perd la porte — sans la
        règle, l'aide gardait un critère d'ancienneté opposable à un chantier
        qui n'a pas commencé.
        """
        gate = {
            **self.GATE,
            "applies_if": {
                "fact": "travaux_perimetre_protection",
                "predicate": {"eq": "protegees_seulement"},
            },
        }
        return _fixture_aide([gate], slug="fx-prix")

    def _aide_a_perimetre(self) -> Aide:
        """Cas Grand Est : le fait porté est le PÉRIMÈTRE de l'aide.

        Le gate synthétique de `_perimetre_condition` n'a pas d'`applies_if` et
        `_scoped_conditions` ne le voit jamais : la porte n'avait aucun moyen
        d'arriver jusqu'à lui.
        """
        return _fixture_aide(
            [], slug="fx-prix", applies_if={"fact": self.FACT, "predicate": {"lte": 3}}
        )

    def test_la_question_se_branche_sur_le_fait_porteur(self):
        """Effet visible : un `dependsOn` que le front sait rendre, alors
        qu'aucune condition ne déclare plus la clause."""
        qs = self._questions(self._run())
        self.assertEqual(
            qs[self.FACT]["dependsOn"],
            {"questionId": self.SOURCE, "showForOptionIds": ["acheves"]},
        )
        # La porteuse est posée AVANT sa dépendante : sans quoi le branchement
        # ne servirait à rien.
        ids = [q["id"] for q in self._run()["qcmQuestions"]]
        self.assertLess(ids.index(self.SOURCE), ids.index(self.FACT))

    def test_la_question_disparait_quand_la_clause_est_fausse(self):
        for reponse in ("non_commences", "en_cours", "aucun"):
            self.assertNotIn(self.FACT, self._questions(self._run({self.SOURCE: reponse})), reponse)

    def test_la_question_reste_quand_la_clause_est_vraie(self):
        self.assertIn(self.FACT, self._questions(self._run({self.SOURCE: "acheves"})))

    def test_clause_inconnue_laisse_la_question_posee(self):
        """Fail-closed : sans réponse à la porteuse, on pose les deux."""
        qs = self._questions(self._run({self.SOURCE: "skip"}))
        self.assertIn(self.FACT, qs)
        self.assertIn(self.SOURCE, qs)

    def test_la_condition_n_est_pas_evaluee_hors_de_sa_clause(self):
        """Le point qui compte : un chantier à venir ne doit pas être REFUSÉ par
        un critère d'ancienneté, il doit l'ignorer."""
        res = self._run({self.SOURCE: "non_commences", self.FACT: "ge6"})
        self.assertEqual(res["aidesNonEligibles"], [])
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-prix"])

    def test_la_clause_propre_dune_condition_reste_prioritaire(self):
        """Plus spécifique : elle gagne l'ÉVALUATION de la condition.

        Elle ne gagne plus le BRANCHEMENT : la question se branche sur la porte
        du fait, qui vaut de toutes les aides à la fois, tandis que la clause
        propre ne vaut que de cette condition-ci. Les deux sont posées, et la
        clause propre continue de décider si la condition s'applique.
        """
        qs = self._questions(self._run(aide=self._aide_a_clause_propre()))
        self.assertEqual(qs[self.FACT]["dependsOn"]["questionId"], self.SOURCE)
        self.assertIn("travaux_perimetre_protection", qs)
        # La clause propre gouverne toujours : hors de son périmètre, la
        # condition ne s'applique pas et l'aide passe sans elle.
        res = self._run(
            {self.SOURCE: "acheves", "travaux_perimetre_protection": "non_protegees_seulement"},
            aide=self._aide_a_clause_propre(),
        )
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-prix"])

    def test_la_porte_du_fait_passe_avant_le_perimetre_de_laide(self):
        """Une condition ne porte qu'UNE clause, et `_scoped_conditions` reporte
        le périmètre plutôt que la porte. Le branchement, lui, ne passe plus par
        ce report : une question dépourvue de SENS est pire qu'une question
        prématurée, et la porte est la seule des deux à dire que la question n'en
        a pas. Perdre le périmètre ici ne coûte rien — quand il est faux, l'aide
        est écartée avec toutes ses questions."""
        aide = _fixture_aide(
            [self.GATE],
            slug="fx-prix",
            applies_if={"fact": "projet_hebergement_touristique", "predicate": {"eq": True}},
        )
        qs = self._questions(self._run(aide=aide))
        self.assertEqual(qs[self.FACT]["dependsOn"]["questionId"], self.SOURCE)
        self.assertIn("projet_hebergement_touristique", qs)

    def test_un_gate_sur_le_fait_porteur_nherite_pas_de_lui_meme(self):
        """Sinon la question serait sa propre condition d'applicabilité, et ne
        se poserait jamais."""
        facts = self._facts(pertinent_si={"fact": self.SOURCE, "predicate": {"eq": "acheves"}})
        gate = {**self.GATE, "fact": self.SOURCE, "predicate": {"eq": "acheves"}}
        qs = self._questions(self._run(aide=_fixture_aide([gate], slug="fx-prix"), facts=facts))
        self.assertIsNone(qs[self.SOURCE].get("dependsOn"))

    def test_une_aide_dont_le_perimetre_est_porte_sort_quand_la_porte_est_fermee(self):
        """Le second défaut, indépendant du masquage : ces aides restaient
        « potentielles » pour toujours — périmètre en incertitude sur un fait
        qu'on ne leur demanderait jamais."""
        res = self._run({self.SOURCE: "non_commences"}, aide=self._aide_a_perimetre())
        self.assertEqual(res["aidesPotentiellementEligibles"], [])
        self.assertEqual(res["aidesEligibles"], [])
        self.assertEqual(res["totalAidesAnalysees"], 0)
        self.assertNotIn(self.FACT, self._questions(res))

    def test_une_aide_dont_le_perimetre_est_porte_pose_la_porte(self):
        """Tout inconnu : l'aide reste candidate et la porte est posée. Sans
        elle, la question de périmètre se brancherait sur une question absente
        du questionnaire — donc ne se brancherait pas du tout."""
        res = self._run(aide=self._aide_a_perimetre())
        qs = self._questions(res)
        self.assertEqual(
            [m["aide"]["id"] for m in res["aidesPotentiellementEligibles"]], ["fx-prix"]
        )
        self.assertIn(self.SOURCE, qs)
        self.assertEqual(qs[self.FACT]["dependsOn"]["questionId"], self.SOURCE)

    def test_une_condition_a_clause_propre_est_ignoree_quand_la_porte_est_fermee(self):
        """Le cas Normandie : une exclusion « ni gîte ni chambre d'hôtes » ne
        doit pas bloquer quelqu'un qui n'a aucun projet d'hébergement. La clause
        propre porte sur autre chose, elle ne peut pas le dire."""
        res = self._run(
            {self.SOURCE: "non_commences", "travaux_perimetre_protection": "protegees_seulement"},
            aide=self._aide_a_clause_propre(),
        )
        self.assertEqual(res["aidesNonEligibles"], [])
        self.assertEqual([m["aide"]["id"] for m in res["aidesEligibles"]], ["fx-prix"])
        self.assertNotIn(self.FACT, self._questions(res))

    def test_une_condition_a_clause_propre_pose_la_porte(self):
        """Les deux clauses sont posées, et la question du fait se branche sur
        la porte : c'est elle qui dit que la question n'a pas de sens."""
        qs = self._questions(self._run(aide=self._aide_a_clause_propre()))
        self.assertIn(self.SOURCE, qs)
        self.assertIn("travaux_perimetre_protection", qs)
        self.assertEqual(
            qs[self.FACT]["dependsOn"],
            {"questionId": self.SOURCE, "showForOptionIds": ["acheves"]},
        )

    def test_corpus_le_type_d_hebergement_ne_se_pose_plus_sans_projet_d_hebergement(self):
        """Le retour de test qui a ouvert le lot, sur le CORPUS réel.

        Treize aides citent `type_hebergement_touristique`, et cinq cassaient
        l'inférence de `_depends_on` : trois l'utilisent comme périmètre d'aide,
        deux ont une clause propre. La question était donc posée à tout le monde
        — y compris après un « non » à la porte.
        """
        porte = "projet_hebergement_touristique"
        fait = FACTS["type_hebergement_touristique"]
        self.assertIsNotNone(fait.pertinent_si)
        assert fait.pertinent_si is not None  # pour pyright
        self.assertEqual(fait.pertinent_si.fact, porte)

        res = run_deterministic_diagnostic(AIDES, FACTS, _monument(), 3000, {porte: "non"})
        self.assertNotIn("type_hebergement_touristique", {q["id"] for q in res["qcmQuestions"]})
        # Et plus aucune aide ne reste « à confirmer » sur ce seul fait : le
        # périmètre est tranché, l'exclusion ne s'applique pas.
        restantes = sorted(
            m["aide"]["id"]
            for m in res["aidesPotentiellementEligibles"]
            for ev in m["llmEvaluation"]["evaluations"]
            if ev.get("categorie") == "type_hebergement_touristique"
        )
        self.assertEqual(restantes, [])

    def test_corpus_la_clause_du_fait_a_remplace_les_quatre_recopies(self):
        """Ce que le lot a fait : la règle vit une fois sur le fait, et aucune
        condition ne la répète. Une recopie future serait du bruit (le lint la
        signale) ; ce test fige l'état atteint sur le fait réel."""
        fait = FACTS["anciennete_achevement_travaux_ans"]
        self.assertIsNotNone(fait.pertinent_si)
        assert fait.pertinent_si is not None  # pour pyright
        self.assertEqual(fait.pertinent_si.fact, "etat_travaux")
        self.assertEqual(fait.pertinent_si.predicate.root, {"eq": "acheves"})
        recopies = sorted(
            f"{slug} / {c.id}"
            for slug, aide in AIDES.items()
            for c in aide.conditions
            if c.fact == "anciennete_achevement_travaux_ans" and c.applies_if is not None
        )
        self.assertEqual(recopies, [])


class TestPorteursConcernesDerive(unittest.TestCase):
    """Le marqueur `porteurs_concernes` rendu EXÉCUTABLE (2026-09-21).

    Un fait marqué `[societe, entreprise_individuelle]` dit que la question n'a
    de sens que pour ces porteurs-là. C'était une contrainte de LINT : l'aide
    devait poser en plus un gate `statut_juridique_porteur`, faute de quoi le
    lint sortait rouge. La règle a produit l'inverse de son but — quand la
    source ne nomme pas ses bénéficiaires, le modèle inventait le gate, le
    vérificateur le contestait, et le modèle le maintenait « parce que le lint
    l'exige » : 580 aides sur 643 en portaient un, 13 conditions étiquetées
    « NON SOURCÉ ».

    Le moteur applique désormais le marqueur lui-même. Deux propriétés
    gouvernent tout ce qui suit :

      - un gate porteur EXPLICITE a précédence sur la dérivation. Mesuré : 138
        aides du corpus ont un gate plus large que le marqueur d'un fait
        qu'elles gatent, dont 31 qui admettent `public_commune`. Les cumuler
        refuserait une commune que la source admet noir sur blanc ;
      - fail-closed : un porteur INCONNU ne refuse jamais. Il pose sa question,
        et la condition reste une incertitude.
    """

    PORTEUR = "statut_juridique_porteur"
    FAIT = "fixture_effectif_salarie"

    def _facts(self, marqueur=("societe", "entreprise_individuelle")) -> dict[str, FactDef]:
        return {
            **FACTS,
            self.FAIT: FactDef.model_validate(
                {
                    "type": "integer",
                    "scope": "proprietaire",
                    "unit": "salariés",
                    "question": "Combien de salariés compte la structure ?",
                    **({"porteurs_concernes": list(marqueur)} if marqueur else {}),
                }
            ),
        }

    GATE_MARQUE = {
        "id": "effectif",
        "text": "La structure compte moins de 250 salariés.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": FAIT,
        "predicate": {"lte": 250},
    }
    GATE_PORTEUR = {
        "id": "porteur-eligible",
        "text": "Sont éligibles les sociétés et les communes.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": PORTEUR,
        "predicate": {"in": ["societe", "public_commune"]},
    }

    def _run(self, answers=None, conditions=None, facts=None, slug="fx-pme"):
        aide = _fixture_aide(conditions or [self.GATE_MARQUE], slug=slug)
        return run_deterministic_diagnostic(
            {aide.slug: aide}, facts or self._facts(), _monument(), 3000, answers
        )

    SEAUX = {
        "eligibles": "aidesEligibles",
        "potentielles": "aidesPotentiellementEligibles",
        "atteignables": "aidesAtteignables",
        "non_eligibles": "aidesNonEligibles",
    }

    def _verdict(self, res, slug="fx-pme") -> dict:
        for seau, cle in self.SEAUX.items():
            for m in res.get(cle, []):
                if m["aide"]["id"] == slug:
                    return {**m, "_seau": seau}
        raise AssertionError(f"{slug} absente des quatre seaux")

    def _questions(self, res) -> list[str]:
        return [q["id"] for q in res["qcmQuestions"]]

    # --- le refus -----------------------------------------------------------

    def test_une_commune_est_ecartee_sans_que_la_question_soit_posee(self):
        """Le cœur de la mesure : 10 questions d'entreprise posées à une commune."""
        res = self._run({self.PORTEUR: "public_commune"})
        verdict = self._verdict(res)
        self.assertEqual(verdict["_seau"], "non_eligibles")
        self.assertNotIn(self.FAIT, self._questions(res))

    def test_le_refus_nomme_les_porteurs_concernes(self):
        res = self._run({self.PORTEUR: "public_commune"})
        evaluations = self._verdict(res)["llmEvaluation"]["evaluations"]
        refus = [e for e in evaluations if e["verdict"] == "non"]
        self.assertEqual(len(refus), 1, refus)
        self.assertIn("Réservé aux porteurs", refus[0]["explication"])
        self.assertIn("societe", refus[0]["explication"])

    def test_une_societe_se_voit_poser_la_question(self):
        res = self._run({self.PORTEUR: "societe"})
        self.assertIn(self.FAIT, self._questions(res))
        self.assertEqual(self._verdict(res)["_seau"], "potentielles")

    # --- le porteur inconnu -------------------------------------------------

    def test_porteur_inconnu_pose_la_question_du_porteur_avant_le_fait(self):
        res = self._run()
        questions = self._questions(res)
        self.assertIn(self.PORTEUR, questions)
        self.assertLess(questions.index(self.PORTEUR), questions.index(self.FAIT))

    def test_la_question_du_porteur_elimine_exactement(self):
        """`eliminationsParOption` doit refléter le moteur, sinon le front élague
        un questionnaire dont l'aide revient avec des critères jamais posés."""
        res = self._run()
        question = next(q for q in res["qcmQuestions"] if q["id"] == self.PORTEUR)
        elim = question["eliminationsParOption"]
        self.assertIn("fx-pme", elim.get("public_commune", []))
        self.assertNotIn("fx-pme", elim.get("societe", []))

    def test_le_fait_repondu_mais_le_porteur_inconnu_reste_une_incertitude(self):
        """Sans quoi une aide d'entreprise serait « éligible » avant qu'on sache
        si elle s'adresse à ce porteur."""
        res = self._run({self.FAIT: 12})
        verdict = self._verdict(res)
        self.assertEqual(verdict["_seau"], "potentielles")
        # Le fait est tranché : on ne le repose pas.
        self.assertNotIn(self.FAIT, self._questions(res))
        self.assertIn(self.PORTEUR, self._questions(res))

    # --- la précédence du gate explicite ------------------------------------

    def test_un_gate_explicite_plus_large_laisse_passer_la_commune(self):
        """138 aides du corpus, dont 31 admettant `public_commune`. La source a
        raison contre le marqueur — un cumul strict refuserait ce qu'elle admet."""
        res = self._run(
            {self.PORTEUR: "public_commune"},
            conditions=[self.GATE_MARQUE, self.GATE_PORTEUR],
        )
        self.assertEqual(self._verdict(res)["_seau"], "potentielles")
        self.assertIn(self.FAIT, self._questions(res))

    def test_un_gate_explicite_refuse_ce_quil_exclut(self):
        res = self._run(
            {self.PORTEUR: "association"},
            conditions=[self.GATE_MARQUE, self.GATE_PORTEUR],
        )
        self.assertEqual(self._verdict(res)["_seau"], "non_eligibles")

    def test_un_applies_if_daide_sur_le_porteur_desarme_aussi_la_derivation(self):
        aide = Aide.model_validate(
            {
                "slug": "fx-pme",
                "nom": "Fixture",
                "organisme": "Org",
                "categorie": "region",
                "type": "subvention",
                "description": "d",
                "conditions": [self.GATE_MARQUE],
                "applies_if": {
                    "fact": self.PORTEUR,
                    "predicate": {"in": ["societe", "public_commune"]},
                },
            }
        )
        res = run_deterministic_diagnostic(
            {aide.slug: aide},
            self._facts(),
            _monument(),
            3000,
            {self.PORTEUR: "public_commune"},
        )
        self.assertEqual(self._verdict(res)["_seau"], "potentielles")

    # --- ce que la dérivation ne fait PAS ------------------------------------

    def test_un_fait_sans_marqueur_est_inchange(self):
        res = self._run({self.PORTEUR: "public_commune"}, facts=self._facts(marqueur=()))
        self.assertEqual(self._verdict(res)["_seau"], "potentielles")
        self.assertIn(self.FAIT, self._questions(res))

    def test_une_condition_info_sur_un_fait_marque_nelimine_rien(self):
        """`effect: info` ne trie personne : elle ne doit pas fermer l'aide."""
        info = {**self.GATE_MARQUE, "effect": "info"}
        res = self._run({self.PORTEUR: "public_commune"}, conditions=[info])
        self.assertNotEqual(self._verdict(res)["_seau"], "non_eligibles")

    def test_un_refus_de_porteur_nest_pas_atteignable_meme_avec_un_levier(self):
        """Un levier dit « faites cette démarche » ; changer de forme juridique
        pour toucher une aide n'en est pas une."""
        facts = self._facts()
        facts[self.FAIT] = FactDef.model_validate(
            {
                **facts[self.FAIT].model_dump(exclude_none=True),
                "levier": {
                    "resume": "Créer une société d'exploitation",
                    "demarche": "Voir un notaire",
                },
            }
        )
        res = self._run({self.PORTEUR: "public_commune"}, facts=facts)
        self.assertEqual(self._verdict(res)["_seau"], "non_eligibles")

    def test_deux_faits_marques_ne_font_quune_question(self):
        facts = self._facts()
        facts["fixture_ca_annuel"] = FactDef.model_validate(
            {
                "type": "integer",
                "scope": "proprietaire",
                "unit": "€",
                "question": "Quel est le chiffre d'affaires annuel ?",
                "porteurs_concernes": ["societe"],
            }
        )
        second = {
            "id": "ca",
            "text": "Le chiffre d'affaires est inférieur à 50 M€.",
            "kind": "user_fact",
            "effect": "gate",
            "fact": "fixture_ca_annuel",
            "predicate": {"lte": 50_000_000},
        }
        res = self._run(conditions=[self.GATE_MARQUE, second], facts=facts)
        self.assertEqual(self._questions(res).count(self.PORTEUR), 1)
        question = next(q for q in res["qcmQuestions"] if q["id"] == self.PORTEUR)
        # Élimination = UNION des deux marqueurs : `entreprise_individuelle`
        # échoue sur le second, `public_commune` sur les deux.
        self.assertIn("fx-pme", question["eliminationsParOption"].get("public_commune", []))
        self.assertIn(
            "fx-pme", question["eliminationsParOption"].get("entreprise_individuelle", [])
        )
        self.assertNotIn("fx-pme", question["eliminationsParOption"].get("societe", []))

    # --- le corpus ----------------------------------------------------------

    def test_corpus_aucune_option_de_marqueur_nest_inconnue(self):
        """Devenu CRITIQUE avec la dérivation : `{in: [<option inconnue>]}` est
        faux pour tout le monde, et l'aide devient inaccessible à tous."""
        porteur = FACTS.get(self.PORTEUR)
        assert porteur is not None
        connues = {o.id for o in porteur.options or []}
        for cle, fait in FACTS.items():
            if not fait.porteurs_concernes:
                continue
            with self.subTest(fait=cle):
                self.assertEqual(set(fait.porteurs_concernes) - connues, set())
