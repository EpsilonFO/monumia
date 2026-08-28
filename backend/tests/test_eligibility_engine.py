"""Tests du moteur de diagnostic déterministe.

Run from backend/:  .venv/bin/python -m unittest discover
"""

import re
import unittest
from datetime import date

from aides_schema import (
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
    _match_result,
    _normalize_boundary,
    _numeric_gap,
    _options_for_fact,
    build_context,
    disponibilite,
    engine_ready_aides,
    evaluate_aide,
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
    return Aide.model_validate(
        {
            "slug": slug,
            "nom": "Fixture",
            "organisme": "Org",
            "categorie": "region",
            "type": "subvention",
            "raison": raison,
            "description": "d",
            "conditions": conditions,
            "hard_filters": hard_filters,
        }
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

    def test_skip_never_eliminates(self):
        m = _monument()
        res = run_deterministic_diagnostic(AIDES, FACTS, m, 3000)
        for q in res["qcmQuestions"]:
            self.assertNotIn("skip", q["eliminationsParOption"])

    @staticmethod
    def _gate(fact: str, predicate: dict, applies_if: dict | None = None) -> dict:
        cond = {
            "id": f"c-{fact.replace('_', '-')}",
            "text": f"Condition sur {fact}",
            "kind": "user_fact",
            "fact": fact,
            "predicate": predicate,
        }
        if applies_if:
            cond["applies_if"] = applies_if
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
                + ([self._gate("erp", {"eq": True})] if i < 2 else [])
                + ([self._gate("residence_principale", {"eq": True})] if i < 1 else []),
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
        # Frontière utile = 1 : « Moins de 1 » (= 0 jour) et « 1 ou plus ».
        self.assertEqual([o["repr"] for o in opts], [0, 1])
        self.assertIn("1 jours/an ou plus", labels)

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
                    "applies_if": {"fact": "erp", "predicate": {"eq": True}},
                }
            ]
        )
        monument = _monument(siecle_construction="XVIIe siècle")
        ctx = build_context(monument, None, {})
        verdict = evaluate_aide(aide, monument, None, ctx, FACTS)
        self.assertEqual(verdict.status, "potentiel")
        self.assertNotIn("annee_construction", verdict.missing_facts)
        self.assertIn("erp", verdict.gateway_facts)


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
