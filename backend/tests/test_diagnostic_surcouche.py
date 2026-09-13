"""La surcouche d'administration vue du DIAGNOSTIC, sur le corpus réel.

Un seul funnel sert tous les diagnostics du produit : c'est ici qu'on vérifie
qu'y brancher la surcouche suffit — l'aide retirée disparaît des quatre seaux
et du compteur, la question reformulée arrive au QCM avec son nouveau texte, le
gate élargi fait changer l'aide de seau.

Les slugs et les clés de faits sont choisis À L'EXÉCUTION depuis le résultat nu :
le corpus bouge tous les jours, figer un slug rendrait ces tests faux à la
première ingestion.
"""

import unittest

from aides_schema import evaluate_predicate, load_all_aides, load_facts, load_pending_facts
from routers.aides import deterministic_diagnostic_for
from services import catalogue_admin as ca

SEAUX = (
    "aidesEligibles",
    "aidesPotentiellementEligibles",
    "aidesAtteignables",
    "aidesNonEligibles",
)

MONUMENT = {
    "id": "m1",
    "nom": "Château de Test",
    "protection": "classe",
    "proprietaire": "prive_personne_physique",
    "region": "ile-de-france",
    "departement_num": "78",
    "etat_conservation": "peril",
    "travaux_envisages": ["toiture", "facade"],
    "siecle_construction": "XVIIe siècle",
}


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _Query:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def select(self, *_a, **_k) -> "_Query":
        return self

    def execute(self) -> _Resp:
        return _Resp(list(self._rows))


class _FakeSupabase:
    def __init__(
        self,
        retirees: list | None = None,
        surcharges: list | None = None,
        predicats: list | None = None,
    ) -> None:
        self._tables = {
            ca.TABLE_RETIREES: retirees or [],
            ca.TABLE_SURCHARGES: surcharges or [],
            ca.TABLE_PREDICATS: predicats or [],
        }

    def table(self, name: str) -> _Query:
        return _Query(self._tables.get(name, []))


def _slugs(resultat: dict) -> set[str]:
    """`aide.id` EST le slug quand l'aide vient des YAML (cf. aide_display_dict)."""
    return {m["aide"]["id"] for seau in SEAUX for m in resultat.get(seau, [])}


def _question(resultat: dict, fact_key: str) -> dict | None:
    return next((q for q in resultat["qcmQuestions"] if q["id"] == fact_key), None)


class SurcoucheDiagnosticTests(unittest.TestCase):
    """Le diagnostic nu sert de témoin : la surcouche ne doit changer QUE ce
    qu'on lui demande."""

    @classmethod
    def setUpClass(cls) -> None:
        ca.invalider()
        cls.nu = deterministic_diagnostic_for(MONUMENT, 12000, {})

    def setUp(self) -> None:
        ca.invalider()

    def tearDown(self) -> None:
        ca.invalider()

    # ── Aides retirées ──────────────────────────────────────────────────────

    def test_aide_retiree_disparait_des_seaux_et_du_compteur(self) -> None:
        slug = sorted(_slugs(self.nu))[0]
        resultat = deterministic_diagnostic_for(
            MONUMENT, 12000, {}, supabase=_FakeSupabase(retirees=[{"slug": slug}])
        )
        self.assertNotIn(slug, _slugs(resultat))
        self.assertEqual(resultat["totalAidesAnalysees"], self.nu["totalAidesAnalysees"] - 1)

    def test_sans_client_le_moteur_reste_nu(self) -> None:
        resultat = deterministic_diagnostic_for(MONUMENT, 12000, {})
        self.assertEqual(_slugs(resultat), _slugs(self.nu))

    def test_surcouche_vide_ne_change_rien(self) -> None:
        resultat = deterministic_diagnostic_for(MONUMENT, 12000, {}, supabase=_FakeSupabase())
        self.assertEqual(_slugs(resultat), _slugs(self.nu))
        self.assertEqual(resultat["totalAidesAnalysees"], self.nu["totalAidesAnalysees"])

    # ── Questions reformulées ───────────────────────────────────────────────

    def _fait_enum_pose(self) -> tuple[str, dict]:
        """Une question du QCM portée par un fait à options, et sa question."""
        facts = {**load_facts(), **load_pending_facts()}
        for question in self.nu["qcmQuestions"]:
            fact = facts.get(question["id"])
            if fact is not None and fact.type == "enum" and len(fact.options or []) >= 2:
                return question["id"], question
        self.skipTest("aucune question enum posée par ce monument")
        raise AssertionError  # inatteignable, pour le typeur

    def test_question_et_aide_contextuelle_reformulees(self) -> None:
        key, _ = self._fait_enum_pose()
        resultat = deterministic_diagnostic_for(
            MONUMENT,
            12000,
            {},
            supabase=_FakeSupabase(
                surcharges=[{"fact_key": key, "question": "Reformulée ?", "help": "Nouvelle aide."}]
            ),
        )
        question = _question(resultat, key)
        assert question is not None
        self.assertEqual(question["question"], "Reformulée ?")
        self.assertEqual(question["help"], "Nouvelle aide.")

    def test_libelle_de_reponse_reformule_sans_toucher_aux_eliminations(self) -> None:
        key, originale = self._fait_enum_pose()
        facts = {**load_facts(), **load_pending_facts()}
        options = [
            {"id": o.id, "label": f"{o.label} (reformulé)", "unknown": o.unknown}
            for o in facts[key].options or []
        ]
        resultat = deterministic_diagnostic_for(
            MONUMENT,
            12000,
            {},
            supabase=_FakeSupabase(surcharges=[{"fact_key": key, "options": options}]),
        )
        question = _question(resultat, key)
        assert question is not None
        self.assertTrue(
            all(
                o["label"].endswith("(reformulé)") for o in question["options"] if o["id"] != "skip"
            )
        )
        self.assertEqual(question["eliminationsParOption"], originale["eliminationsParOption"])

    def test_reponse_ajoutee_apparait_avec_ses_eliminations(self) -> None:
        key, originale = self._fait_enum_pose()
        facts = {**load_facts(), **load_pending_facts()}
        options = [
            {"id": o.id, "label": o.label, "unknown": o.unknown} for o in facts[key].options or []
        ]
        options.append({"id": "reponse_neuve", "label": "Réponse ajoutée", "unknown": False})
        resultat = deterministic_diagnostic_for(
            MONUMENT,
            12000,
            {},
            supabase=_FakeSupabase(surcharges=[{"fact_key": key, "options": options}]),
        )
        question = _question(resultat, key)
        assert question is not None
        self.assertIn("reponse_neuve", [o["id"] for o in question["options"]])
        # Une réponse hors de tout prédicat écarte au moins autant d'aides que
        # les autres : les gates `in [...]` deviennent faux pour elle.
        elim = question["eliminationsParOption"]
        if any(elim.values()):
            self.assertIn("reponse_neuve", elim)
        # Les réponses d'origine gardent exactement leurs éliminations.
        for option_id, slugs in originale["eliminationsParOption"].items():
            self.assertEqual(elim.get(option_id), slugs)

    def test_ontologie_yaml_intacte_apres_diagnostic_surcharge(self) -> None:
        key, _ = self._fait_enum_pose()
        avant = load_facts().get(key) or load_pending_facts()[key]
        question_avant = avant.question
        deterministic_diagnostic_for(
            MONUMENT,
            12000,
            {},
            supabase=_FakeSupabase(surcharges=[{"fact_key": key, "question": "Reformulée ?"}]),
        )
        apres = load_facts().get(key) or load_pending_facts()[key]
        self.assertEqual(apres.question, question_avant)


if __name__ == "__main__":
    unittest.main()


class PredicatsSurchargesTests(unittest.TestCase):
    """Le prédicat surchargé, vu du diagnostic : un gate élargi fait remonter
    l'aide d'un seau à l'autre, un gate resserré se voit dans le QCM."""

    def setUp(self) -> None:
        ca.invalider()
        self.facts = {**load_facts(), **load_pending_facts()}

    def tearDown(self) -> None:
        ca.invalider()

    def _cible(self) -> tuple[str, str, str, list[str], str]:
        """(slug, condition_id, fact_key, réponses, réponse écartante).

        Cherchée DANS le QCM du diagnostic nu plutôt que dans le corpus : une
        aide citée par `eliminationsParOption` est forcément servie, posée en
        question, et écartée par CE gate-là pour cette réponse — trois
        propriétés qu'un balayage du corpus ne garantit pas, et sans lesquelles
        élargir le gate ne prouverait rien.

        Le corpus bouge tous les jours : rien n'est figé ici.
        """
        nu = deterministic_diagnostic_for(MONUMENT, 12000, {})
        aides = load_all_aides()
        for question in nu["qcmQuestions"]:
            fact_key = question["id"]
            fait = self.facts.get(fact_key)
            if fait is None or fait.type != "enum":
                continue
            options = [o.id for o in fait.options or [] if not o.unknown]
            if len(options) < 2:
                continue
            for ecartante, slugs in sorted(question["eliminationsParOption"].items()):
                if ecartante not in options:
                    continue
                for slug in slugs:
                    aide = aides.get(slug)
                    if aide is None:
                        continue
                    # Un SEUL gate sur ce fait : sinon élargir celui-ci
                    # laisserait l'autre écarter l'aide, et le test mentirait.
                    tous = [c for c in aide.conditions if c.fact == fact_key and c.effect == "gate"]
                    if len(tous) != 1:
                        continue
                    gate = tous[0]
                    if not ca.condition_modifiable(gate, self.facts):
                        continue
                    if (
                        gate.predicate
                        and evaluate_predicate(gate.predicate.root, ecartante) is False
                    ):
                        return slug, gate.id, fact_key, options, ecartante
        self.skipTest("aucun gate modifiable écartant une aide posée au QCM")
        raise AssertionError  # inatteignable, pour le typeur

    def _ligne(self, slug: str, cid: str, predicate: dict, **over) -> dict:
        condition = next(c for c in load_all_aides()[slug].conditions if c.id == cid)
        ligne = {
            "aide_slug": slug,
            "condition_id": cid,
            "predicate": predicate,
            "condition_text": condition.text,
            "fact_key": condition.fact,
            "predicate_origine": dict(condition.predicate.root) if condition.predicate else {},
        }
        ligne.update(over)
        return ligne

    def test_surcouche_vide_ne_change_rien(self) -> None:
        nu = deterministic_diagnostic_for(MONUMENT, 12000, {})
        ca.invalider()
        avec = deterministic_diagnostic_for(MONUMENT, 12000, {}, supabase=_FakeSupabase())
        self.assertEqual(_slugs(avec), _slugs(nu))

    def test_gate_elargi_fait_changer_laide_de_seau(self) -> None:
        slug, cid, fact_key, options, ecartante = self._cible()
        # On répond justement ce qui écarte l'aide.
        answers = {fact_key: ecartante}

        ca.invalider()
        avant = deterministic_diagnostic_for(MONUMENT, 12000, answers, supabase=_FakeSupabase())
        self.assertIn(slug, {m["aide"]["id"] for m in avant["aidesNonEligibles"]})

        ca.invalider()
        apres = deterministic_diagnostic_for(
            MONUMENT,
            12000,
            answers,
            supabase=_FakeSupabase(
                predicats=[self._ligne(slug, cid, ca.predicat_depuis("in", options))]
            ),
        )
        self.assertNotIn(slug, {m["aide"]["id"] for m in apres["aidesNonEligibles"]})

    def test_gate_resserre_se_voit_dans_les_eliminations(self) -> None:
        slug, cid, fact_key, options, ecartante = self._cible()
        # Resserrer SUR la réponse qui écartait : elle n'écarte plus, et toutes
        # les autres écartent désormais.
        ca.invalider()
        resultat = deterministic_diagnostic_for(
            MONUMENT,
            12000,
            {},
            supabase=_FakeSupabase(
                predicats=[self._ligne(slug, cid, ca.predicat_depuis("eq", [ecartante]))]
            ),
        )
        question = _question(resultat, fact_key)
        assert question is not None
        self.assertNotIn(slug, question["eliminationsParOption"].get(ecartante, []))
        for autre in [o for o in options if o != ecartante]:
            with self.subTest(reponse=autre):
                self.assertIn(slug, question["eliminationsParOption"].get(autre, []))

    def test_surcharge_perimee_ne_change_rien(self) -> None:
        slug, cid, _fact_key, options, _ecartante = self._cible()
        ca.invalider()
        temoin = deterministic_diagnostic_for(MONUMENT, 12000, {}, supabase=_FakeSupabase())
        ca.invalider()
        resultat = deterministic_diagnostic_for(
            MONUMENT,
            12000,
            {},
            supabase=_FakeSupabase(
                predicats=[
                    self._ligne(
                        slug,
                        cid,
                        ca.predicat_depuis("in", options),
                        condition_text="un texte qui n’est plus celui de la condition",
                    )
                ]
            ),
        )
        self.assertEqual(_slugs(resultat), _slugs(temoin))

    def test_le_corpus_yaml_reste_intact(self) -> None:
        avant = load_all_aides()
        slug, cid, _fact_key, options, _ecartante = self._cible()
        predicats_avant = [
            dict(c.predicate.root) if c.predicate else None for c in avant[slug].conditions
        ]
        ca.invalider()
        deterministic_diagnostic_for(
            MONUMENT,
            12000,
            {},
            supabase=_FakeSupabase(
                predicats=[self._ligne(slug, cid, ca.predicat_depuis("in", options))]
            ),
        )
        self.assertIs(load_all_aides(), avant)
        self.assertEqual(
            [dict(c.predicate.root) if c.predicate else None for c in avant[slug].conditions],
            predicats_avant,
        )
