"""Surcouche d'exploitation du catalogue : retraits, surcharges, impact, cache.

Tout est testé SANS base : les fonctions qui appliquent la surcouche sont pures,
et le cache se remplit depuis un faux client à deux tables.

Invariant qui court dans tout le fichier : les structures YAML sont partagées
entre requêtes (loaders `@cache`). Une surcouche qui les modifierait en place
contaminerait tous les diagnostics du process — d'où les assertions sur
`load_all_aides()` et `load_facts()` APRÈS coup.
"""

import unittest
from unittest.mock import patch

from aides_schema import Aide, FactDef, load_all_aides, load_facts
from eligibility_engine import conditions_porteur_derivees, engine_ready_aides
from services import catalogue_admin as ca
from services.catalogue_admin import OptionSurchargee, SurchargeFait


def _aide(slug: str, conditions: list[dict] | None = None, **over) -> Aide:
    champs = {
        "slug": slug,
        "nom": f"Aide {slug}",
        "organisme": "Org",
        "categorie": "region",
        "type": "subvention",
        "description": "d",
        "conditions": conditions or [],
    }
    champs.update(over)
    return Aide.model_validate(champs)


def _fact_enum(**over) -> FactDef:
    champs = {
        "type": "enum",
        "scope": "monument",
        "question": "Quel est l'usage du bien ?",
        "help": "Son usage principal aujourd'hui.",
        "options": [
            {"id": "culte", "label": "Lieu de culte"},
            {"id": "musee", "label": "Musée"},
            {"id": "inconnu", "label": "Je ne sais pas", "unknown": True},
        ],
    }
    champs.update(over)
    return FactDef.model_validate(champs)


def _fact_booleen(**over) -> FactDef:
    champs = {
        "type": "boolean",
        "scope": "projet",
        "question": "Les travaux portent-ils sur la partie protégée ?",
    }
    champs.update(over)
    return FactDef.model_validate(champs)


def _oui_non(*ids_neutres: str) -> list[OptionSurchargee]:
    """Le couple obligatoire, plus autant de réponses « ne tranche pas »."""
    return [
        OptionSurchargee(id="oui", label="Oui", valeur=True),
        OptionSurchargee(id="non", label="Non", valeur=False),
        *(OptionSurchargee(id=i, label=i, valeur=None) for i in ids_neutres),
    ]


def _gate(fact: str, predicate: dict, cid: str = "c1") -> dict:
    return {"id": cid, "text": "t", "kind": "user_fact", "fact": fact, "predicate": predicate}


class RetraitTests(unittest.TestCase):
    def test_retire_les_slugs_demandes(self) -> None:
        aides = {"a": _aide("a"), "b": _aide("b")}
        self.assertEqual(set(ca.retirer(aides, ["a"])), {"b"})

    def test_slug_inconnu_ignore(self) -> None:
        aides = {"a": _aide("a")}
        self.assertEqual(set(ca.retirer(aides, ["zzz"])), {"a"})

    def test_ne_touche_jamais_le_corpus_partage(self) -> None:
        """Le vrai corpus, celui que tous les diagnostics lisent."""
        corpus = load_all_aides()
        slug = next(iter(corpus))
        restant = ca.retirer(corpus, [slug])
        self.assertNotIn(slug, restant)
        self.assertIn(slug, load_all_aides())
        self.assertIs(corpus, load_all_aides())


class SurchargeFaitTests(unittest.TestCase):
    def test_reformule_sans_toucher_au_reste(self) -> None:
        original = FactDef.model_validate(
            {
                "type": "enum",
                "scope": "proprietaire",
                "question": "q?",
                "unit": None,
                "auto_source": "monument.nom",
                "hors_gate": True,
                "levier": {"resume": "Demander le label"},
                "options": [{"id": "oui", "label": "Oui"}],
            }
        )
        surcharge = SurchargeFait(fact_key="k", question="Nouvelle question ?")
        effectif = ca.surcharger_fait(original, surcharge)

        self.assertEqual(effectif.question, "Nouvelle question ?")
        self.assertEqual(effectif.type, original.type)
        self.assertEqual(effectif.scope, original.scope)
        self.assertEqual(effectif.auto_source, original.auto_source)
        self.assertEqual(effectif.hors_gate, original.hors_gate)
        self.assertEqual(effectif.levier, original.levier)
        self.assertEqual([o.id for o in effectif.options or []], ["oui"])
        # L'original reste intact : c'est lui que le YAML partage.
        self.assertEqual(original.question, "q?")

    def test_remplace_la_liste_entiere_des_options(self) -> None:
        effectif = ca.surcharger_fait(
            _fact_enum(),
            SurchargeFait(
                fact_key="k",
                options=[OptionSurchargee(id="culte", label="Église ou chapelle")],
            ),
        )
        self.assertEqual(
            [(o.id, o.label) for o in effectif.options or []], [("culte", "Église ou chapelle")]
        )

    def test_surcharge_doptions_garde_les_descriptions_du_yaml(self) -> None:
        """L'administration n'édite pas `description` : reformuler un libellé
        ne doit ni l'effacer ni faire échouer la surcharge. Une réponse
        nouvelle n'en a pas."""
        original = _fact_enum(
            options=[
                {"id": "culte", "label": "Lieu de culte", "description": "Église, temple."},
                {"id": "musee", "label": "Musée"},
            ]
        )
        effectif = ca.surcharger_fait(
            original,
            SurchargeFait(
                fact_key="k",
                options=[
                    OptionSurchargee(id="culte", label="Église ou chapelle"),
                    OptionSurchargee(id="musee", label="Musée"),
                    OptionSurchargee(id="autre", label="Autre usage"),
                ],
            ),
        )
        self.assertEqual(
            [(o.id, o.label, o.description) for o in effectif.options or []],
            [
                ("culte", "Église ou chapelle", "Église, temple."),
                ("musee", "Musée", None),
                ("autre", "Autre usage", None),
            ],
        )

    def test_surcharge_doptions_garde_les_groupes_du_yaml(self) -> None:
        """Même report pour `groupe` : une reformulation faite dans /admin ne
        doit pas défaire le rangement des cartes."""
        original = _fact_enum(
            options=[
                {"id": "culte", "label": "Lieu de culte", "groupe": "Usages"},
                {"id": "musee", "label": "Musée", "groupe": "Usages"},
            ]
        )
        effectif = ca.surcharger_fait(
            original,
            SurchargeFait(
                fact_key="k",
                options=[
                    OptionSurchargee(id="culte", label="Église ou chapelle"),
                    OptionSurchargee(id="autre", label="Autre usage"),
                ],
            ),
        )
        self.assertEqual(
            [(o.id, o.groupe) for o in effectif.options or []],
            [("culte", "Usages"), ("autre", None)],
        )

    def test_surcharge_invalide_conserve_le_fait_yaml(self) -> None:
        """Une liste vide sur un enum viole `_options_iff_enum` : la validation
        doit se relancer (d'où model_validate, et non model_copy)."""
        facts = {"usage": _fact_enum()}
        surcharge = SurchargeFait.model_construct(fact_key="usage", options=[])
        effectifs = ca.surcharger_faits(facts, {"usage": surcharge})
        self.assertEqual(effectifs["usage"], facts["usage"])

    def test_fait_absent_de_lontologie_ignore(self) -> None:
        effectifs = ca.surcharger_faits(
            {"usage": _fact_enum()}, {"zzz": SurchargeFait(fact_key="zzz", question="q?")}
        )
        self.assertEqual(set(effectifs), {"usage"})

    def test_ontologie_reelle_intacte_apres_surcharge(self) -> None:
        facts = load_facts()
        key = next(k for k, f in facts.items() if f.type == "enum")
        avant = facts[key].question
        ca.surcharger_faits(facts, {key: SurchargeFait(fact_key=key, question="Reformulée ?")})
        self.assertEqual(load_facts()[key].question, avant)


class ValidationTests(unittest.TestCase):
    def test_options_refusees_sur_un_fait_numerique(self) -> None:
        """Les tranches viennent des seuils des aides : une liste posée ici ne
        serait jamais lue."""
        numerique = FactDef.model_validate(
            {"type": "integer", "scope": "monument", "question": "q?"}
        )
        with self.assertRaises(ValueError) as ctx:
            ca.valider_surcharge(
                numerique,
                SurchargeFait(fact_key="k", options=[OptionSurchargee(id="a", label="A")]),
            )
        self.assertIn("calculées par le moteur", str(ctx.exception))

    def test_options_acceptees_sur_un_booleen(self) -> None:
        ca.valider_surcharge(
            _fact_booleen(),
            SurchargeFait(fact_key="k", options=_oui_non("les_deux")),
        )

    def test_booleen_sans_oui_refuse(self) -> None:
        """R1 : les réponses déjà enregistrées citent « oui » et « non »."""
        with self.assertRaises(ValueError) as ctx:
            ca.valider_surcharge(
                _fact_booleen(),
                SurchargeFait(
                    fact_key="k", options=[OptionSurchargee(id="non", label="Non", valeur=False)]
                ),
            )
        self.assertIn("ne peut pas être supprimée", str(ctx.exception))

    def test_booleen_dont_la_valeur_du_couple_est_detournee_refuse(self) -> None:
        options = _oui_non()
        options[0] = OptionSurchargee(id="oui", label="Oui", valeur=False)
        with self.assertRaises(ValueError) as ctx:
            ca.valider_surcharge(_fact_booleen(), SurchargeFait(fact_key="k", options=options))
        self.assertIn("doit garder la valeur", str(ctx.exception))

    def test_valeur_refusee_sur_un_enum(self) -> None:
        """R2 : sur un fait à choix, l'identifiant EST la valeur."""
        with self.assertRaises(ValueError) as ctx:
            ca.valider_surcharge(
                _fact_enum(),
                SurchargeFait(
                    fact_key="k", options=[OptionSurchargee(id="culte", label="C", valeur=True)]
                ),
            )
        self.assertIn("question Oui/Non", str(ctx.exception))

    def test_reponse_neutre_qui_tranche_refusee(self) -> None:
        """R4 : « je ne sais pas » n'envoie rien au moteur."""
        options = [*_oui_non(), OptionSurchargee(id="nsp", label="?", unknown=True, valeur=True)]
        with self.assertRaises(ValueError) as ctx:
            ca.valider_surcharge(_fact_booleen(), SurchargeFait(fact_key="k", options=options))
        self.assertIn("réponse neutre", str(ctx.exception))

    def test_liste_doptions_vide_refusee(self) -> None:
        with self.assertRaises(ValueError):
            ca.valider_surcharge(_fact_enum(), SurchargeFait(fact_key="k", options=[]))

    def test_ids_en_doublon_refuses(self) -> None:
        with self.assertRaises(ValueError):
            ca.valider_surcharge(
                _fact_enum(),
                SurchargeFait(
                    fact_key="k",
                    options=[
                        OptionSurchargee(id="culte", label="A"),
                        OptionSurchargee(id="culte", label="B"),
                    ],
                ),
            )

    def test_libelle_blanc_refuse(self) -> None:
        with self.assertRaises(ValueError):
            ca.valider_surcharge(
                _fact_enum(),
                SurchargeFait(fact_key="k", options=[OptionSurchargee(id="culte", label="   ")]),
            )

    def test_question_vide_refusee(self) -> None:
        with self.assertRaises(ValueError):
            ca.valider_surcharge(_fact_enum(), SurchargeFait(fact_key="k", question="  "))

    def test_help_vide_accepte(self) -> None:
        """Vider l'aide contextuelle est le seul moyen d'en retirer une fausse."""
        ca.valider_surcharge(_fact_enum(), SurchargeFait(fact_key="k", help=""))


class SurchargeUtileTests(unittest.TestCase):
    def test_brouillon_identique_ne_vaut_pas_surcharge(self) -> None:
        original = _fact_enum()
        brouillon = SurchargeFait(
            fact_key="usage",
            question=original.question,
            help=original.help,
            options=[
                OptionSurchargee(id=o.id, label=o.label, unknown=o.unknown)
                for o in original.options or []
            ],
        )
        self.assertIsNone(ca.surcharge_utile(original, brouillon))

    def test_ne_garde_que_ce_qui_differe(self) -> None:
        original = _fact_enum()
        utile = ca.surcharge_utile(
            original,
            SurchargeFait(fact_key="usage", question="  Autre question ?  ", help=original.help),
        )
        assert utile is not None
        self.assertEqual(utile.question, "Autre question ?")
        self.assertIsNone(utile.help)
        self.assertIsNone(utile.options)

    def test_ordre_des_options_compte(self) -> None:
        original = _fact_enum()
        inversees = list(reversed(original.options or []))
        utile = ca.surcharge_utile(
            original,
            SurchargeFait(
                fact_key="usage",
                options=[
                    OptionSurchargee(id=o.id, label=o.label, unknown=o.unknown) for o in inversees
                ],
            ),
        )
        assert utile is not None
        self.assertIsNotNone(utile.options)


class ValeurSeuleTests(unittest.TestCase):
    """Le bug silencieux le plus coûteux du lot : sans `valeur` dans
    `_options_tuple`, un brouillon où seule une valeur change passerait pour
    identique à l'original, et la ligne serait SUPPRIMÉE au lieu d'être écrite."""

    def test_changer_une_valeur_seule_produit_bien_une_surcharge(self) -> None:
        original = _fact_booleen(
            options=[
                {"id": "oui", "label": "Oui", "valeur": True},
                {"id": "non", "label": "Non", "valeur": False},
                {"id": "les_deux", "label": "Les deux", "valeur": True},
            ]
        )
        # Même ids, mêmes libellés, même `unknown` : seule la valeur bouge.
        brouillon = SurchargeFait(fact_key="k", options=_oui_non("les_deux"))
        utile = ca.surcharge_utile(original, brouillon)
        self.assertIsNotNone(utile)
        assert utile is not None and utile.options is not None
        self.assertIsNone(utile.options[2].valeur)

    def test_brouillon_identique_valeurs_comprises_ne_vaut_pas_surcharge(self) -> None:
        original = _fact_booleen(
            options=[
                {"id": "oui", "label": "Oui", "valeur": True},
                {"id": "non", "label": "Non", "valeur": False},
                {"id": "les_deux", "label": "les_deux"},
            ]
        )
        brouillon = SurchargeFait(
            fact_key="k",
            question=original.question,
            help="",
            options=_oui_non("les_deux"),
        )
        self.assertIsNone(ca.surcharge_utile(original, brouillon))


class OptionsEditablesTests(unittest.TestCase):
    def test_booleen_nu_souvre_sur_le_couple_implicite(self) -> None:
        """Une liste vide ferait croire la question sans réponses, et
        l'administrateur repartirait de zéro en supprimant au passage les deux
        identifiants que les réponses persistées citent."""
        options = ca.options_editables(_fact_booleen())
        self.assertEqual([(o.id, o.valeur) for o in options], [("oui", True), ("non", False)])

    def test_enum_rend_ses_options_sans_valeur(self) -> None:
        options = ca.options_editables(_fact_enum())
        self.assertEqual([o.id for o in options], ["culte", "musee", "inconnu"])
        self.assertTrue(all(o.valeur is None for o in options))

    def test_fait_numerique_rend_une_liste_vide(self) -> None:
        numerique = FactDef.model_validate(
            {"type": "integer", "scope": "monument", "question": "q?"}
        )
        self.assertEqual(ca.options_editables(numerique), [])


class ImpactBooleenTests(unittest.TestCase):
    """L'impact évalue à la VALEUR DÉCLARÉE, pas à l'identifiant.

    Sans ce correctif, l'écran annoncerait que « Oui » écarte les aides qui
    exigent `eq: true`, parce que `evaluate_predicate({"eq": True}, "oui")`
    vaut `False`. Le correctif part dans le même lot que l'ouverture du champ.
    """

    FACT = "travaux_partie_protegee"
    AIDES = {
        "exige-oui": _aide("exige-oui", [_gate(FACT, {"eq": True})]),
        "exige-non": _aide("exige-non", [_gate(FACT, {"eq": False})]),
    }

    def _impact(self, options: list[OptionSurchargee]) -> dict:
        return ca.impact_options(self.FACT, options, self.AIDES, _fact_booleen())

    def test_oui_ecarte_ce_qui_exige_non(self) -> None:
        impact = self._impact([OptionSurchargee(id="oui", label="Oui", valeur=True)])
        self.assertEqual([a["slug"] for a in impact["parOption"][0]["ecarte"]], ["exige-non"])

    def test_non_ecarte_ce_qui_exige_oui(self) -> None:
        impact = self._impact([OptionSurchargee(id="non", label="Non", valeur=False)])
        self.assertEqual([a["slug"] for a in impact["parOption"][0]["ecarte"]], ["exige-oui"])

    def test_reponse_qui_ne_tranche_pas_necarte_rien(self) -> None:
        impact = self._impact([OptionSurchargee(id="les_deux", label="Les deux", valeur=None)])
        self.assertEqual(impact["parOption"][0]["ecarte"], [])

    def test_la_valeur_est_remontee_au_front(self) -> None:
        impact = self._impact(_oui_non("les_deux"))
        self.assertEqual(
            [(ligne["id"], ligne["valeur"]) for ligne in impact["parOption"]],
            [("oui", True), ("non", False), ("les_deux", None)],
        )

    def test_sur_un_enum_lidentifiant_reste_la_valeur(self) -> None:
        """Non-régression : le détour ne vaut que pour les booléens."""
        aides = {"culte-only": _aide("culte-only", [_gate("usage", {"in": ["culte"]})])}
        impact = ca.impact_options(
            "usage", [OptionSurchargee(id="musee", label="Musée")], aides, _fact_enum()
        )
        self.assertEqual([a["slug"] for a in impact["parOption"][0]["ecarte"]], ["culte-only"])


class ImpactTests(unittest.TestCase):
    AIDES = {
        "culte-only": _aide("culte-only", [_gate("usage", {"in": ["culte"]})]),
        "hors-culte": _aide("hors-culte", [_gate("usage", {"neq": "culte"})]),
        "untyped": _aide(
            "untyped",
            [{"id": "c1", "text": "t", "kind": "untyped"}, _gate("usage", {"eq": "musee"}, "c2")],
        ),
    }

    def test_option_ecarte_les_aides_dont_le_gate_devient_faux(self) -> None:
        impact = ca.impact_options(
            "usage", [OptionSurchargee(id="musee", label="Musée")], self.AIDES, _fact_enum()
        )
        ecarte = {a["slug"] for a in impact["parOption"][0]["ecarte"]}
        self.assertEqual(ecarte, {"culte-only"})

    def test_aide_non_engine_ready_jamais_annoncee_ecartee(self) -> None:
        """`untyped` gate sur musee ≠ culte, mais le moteur ne la sert pas."""
        impact = ca.impact_options(
            "usage", [OptionSurchargee(id="culte", label="Culte")], self.AIDES, _fact_enum()
        )
        ecarte = {a["slug"] for a in impact["parOption"][0]["ecarte"]}
        self.assertNotIn("untyped", ecarte)
        self.assertEqual(ecarte, {"hors-culte"})

    def test_reponse_neutre_necarte_jamais(self) -> None:
        impact = ca.impact_options(
            "usage",
            [OptionSurchargee(id="inconnu", label="Je ne sais pas", unknown=True)],
            self.AIDES,
            _fact_enum(),
        )
        self.assertEqual(impact["parOption"][0]["ecarte"], [])

    def test_option_nouvelle_hors_in_est_ecartante(self) -> None:
        impact = ca.impact_options(
            "usage",
            [OptionSurchargee(id="ferme", label="Ferme")],
            self.AIDES,
            _fact_enum(),
        )
        self.assertEqual([a["slug"] for a in impact["parOption"][0]["ecarte"]], ["culte-only"])

    def test_option_supprimee_signale_les_aides_qui_la_citent(self) -> None:
        gardees = [
            OptionSurchargee(id="musee", label="Musée"),
            OptionSurchargee(id="inconnu", label="Je ne sais pas", unknown=True),
        ]
        impact = ca.impact_options("usage", gardees, self.AIDES, _fact_enum())
        supprimees = {
            s["id"]: {a["slug"] for a in s["referenceePar"]} for s in impact["supprimees"]
        }
        self.assertEqual(set(supprimees), {"culte"})
        self.assertEqual(supprimees["culte"], {"culte-only", "hors-culte"})

    def test_citation_dans_un_applies_if_compte(self) -> None:
        aides = {
            "perimetre": _aide(
                "perimetre",
                [],
                applies_if={"fact": "usage", "predicate": {"eq": "musee"}},
            )
        }
        impact = ca.impact_options(
            "usage", [OptionSurchargee(id="culte", label="Culte")], aides, _fact_enum()
        )
        supprimees = {
            s["id"]: [a["slug"] for a in s["referenceePar"]] for s in impact["supprimees"]
        }
        self.assertEqual(supprimees["musee"], ["perimetre"])

    def test_citation_dans_un_any_of_compte(self) -> None:
        aides = {
            "combinee": _aide(
                "combinee",
                [_gate("usage", {"any_of": [{"eq": "musee"}, {"eq": "culte"}]})],
            )
        }
        impact = ca.impact_options(
            "usage", [OptionSurchargee(id="inconnu", label="?", unknown=True)], aides, _fact_enum()
        )
        cites = {s["id"] for s in impact["supprimees"] if s["referenceePar"]}
        self.assertEqual(cites, {"culte", "musee"})

    def test_index_prcalcule_donne_le_meme_resultat(self) -> None:
        """L'index n'est qu'une accélération : lister l'ontologie entière le
        réutilise d'un fait à l'autre, il ne doit rien changer au verdict."""
        options = [
            OptionSurchargee(id="musee", label="Musée"),
            OptionSurchargee(id="ferme", label="Ferme"),
        ]
        direct = ca.impact_options("usage", options, self.AIDES, _fact_enum())
        indexe = ca.impact_options(
            "usage", options, self.AIDES, _fact_enum(), ca.construire_index(self.AIDES)
        )
        self.assertEqual(direct, indexe)

    def test_index_sur_le_corpus_reel(self) -> None:
        """L'index doit être EXHAUSTIF : une aide oubliée disparaîtrait de
        l'impact, et l'administrateur supprimerait une réponse en croyant que
        personne ne la cite."""
        corpus = load_all_aides()
        ready = engine_ready_aides(corpus)
        index = ca.construire_index(corpus)

        attendus_gates = {
            (key, slug)
            for slug, aide in ready.items()
            for key in {c.fact for c in aide.conditions if c.fact}
            if ca._gates_sur_fait(aide, key)
        }
        # Les gates porteur DÉRIVÉS d'un fait marqué `porteurs_concernes` : une
        # aide qui gate un tel fait sans gate porteur explicite est quand même
        # fermée aux autres porteurs (premier cas au corpus : le 2026-10-14,
        # region-grand-est-soutien-hotellerie sur
        # capital_groupe_financier_ou_culturel_majoritaire).
        ontologie = load_facts()
        attendus_gates |= {
            (ca.FAIT_PORTEUR, slug)
            for slug, aide in ready.items()
            if conditions_porteur_derivees(aide, ontologie)
        }
        obtenus_gates = {(key, slug) for key, par_slug in index.gates.items() for slug in par_slug}
        self.assertEqual(obtenus_gates, attendus_gates)

        # Les non-typées sont hors des gates (le moteur ne les sert pas) mais
        # restent comptées dans les citations.
        non_typees = set(corpus) - set(ready)
        self.assertFalse({slug for _k, slug in obtenus_gates} & non_typees)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Prédicats de conditions (chantier 3)
# ---------------------------------------------------------------------------


def _gate_modifiable(fact: str = "usage", predicate: dict | None = None, cid: str = "g1") -> dict:
    return {
        "id": cid,
        "text": "Le bien doit être un lieu de culte.",
        "kind": "user_fact",
        "effect": "gate",
        "fact": fact,
        "predicate": predicate or {"eq": "culte"},
    }


def _ligne(
    slug: str = "a",
    cid: str = "g1",
    predicate: dict | None = None,
    **over,
) -> ca.SurchargePredicat:
    champs = {
        "aide_slug": slug,
        "condition_id": cid,
        "predicate": predicate or {"in": ["culte", "musee"]},
        "condition_text": "Le bien doit être un lieu de culte.",
        "fact_key": "usage",
        "predicate_origine": {"eq": "culte"},
    }
    champs.update(over)
    return ca.SurchargePredicat.model_validate(champs)


FACTS = {"usage": _fact_enum()}


class CanonisationTests(unittest.TestCase):
    def test_in_a_une_valeur_devient_eq(self) -> None:
        """28 des 412 gates du corpus. Sans ça, recomposer le prédicat d'origine
        depuis le menu écrirait une ligne qui ne change rien."""
        self.assertEqual(ca.canoniser_predicat({"in": ["culte"]}), {"eq": "culte"})

    def test_not_in_a_une_valeur_devient_neq(self) -> None:
        self.assertEqual(ca.canoniser_predicat({"not_in": ["culte"]}), {"neq": "culte"})

    def test_eq_a_plusieurs_valeurs_devient_in(self) -> None:
        self.assertEqual(ca.predicat_depuis("eq", ["musee", "culte"]), {"in": ["culte", "musee"]})

    def test_none_in_garde_sa_liste_meme_a_une_valeur(self) -> None:
        """L'exclusion stricte n'a pas de forme scalaire : la ramener à `neq`
        la rendrait existentielle, c.-à-d. changerait son sens."""
        self.assertEqual(ca.canoniser_predicat({"none_in": ["culte"]}), {"none_in": ["culte"]})

    def test_valeurs_triees_et_dedoublonnees(self) -> None:
        self.assertEqual(
            ca.predicat_depuis("in", ["musee", "culte", "musee"]), {"in": ["culte", "musee"]}
        )

    def test_aller_retour_est_lidentite(self) -> None:
        for predicate in ({"eq": "culte"}, {"in": ["culte", "musee"]}, {"neq": "musee"}):
            with self.subTest(predicate=predicate):
                operateur, valeurs = ca.operateur_et_valeurs(predicate)
                self.assertEqual(ca.predicat_depuis(operateur, valeurs), predicate)

    def test_predicat_utile_rend_none_sur_une_egalite_canonique(self) -> None:
        self.assertIsNone(ca.predicat_utile({"in": ["culte"]}, {"eq": "culte"}))
        self.assertIsNone(ca.predicat_utile({"in": ["a", "b"]}, {"in": ["b", "a"]}))

    def test_predicat_utile_rend_le_neuf_quand_il_differe(self) -> None:
        self.assertEqual(
            ca.predicat_utile({"eq": "culte"}, {"in": ["culte", "musee"]}),
            {"in": ["culte", "musee"]},
        )


class MandatTests(unittest.TestCase):
    """`condition_modifiable` est LE mandat, énoncé une seule fois."""

    def _condition(self, **over):
        champs = _gate_modifiable()
        champs.update(over)
        return _aide("a", [champs]).conditions[0]

    def test_gate_user_fact_sur_un_enum_est_modifiable(self) -> None:
        self.assertTrue(ca.condition_modifiable(self._condition(), FACTS))

    def test_effet_info_hors_mandat(self) -> None:
        self.assertFalse(ca.condition_modifiable(self._condition(effect="info"), FACTS))

    def test_manual_check_hors_mandat(self) -> None:
        condition = _aide("a", [{"id": "g1", "text": "t", "kind": "manual_check"}]).conditions[0]
        self.assertFalse(ca.condition_modifiable(condition, FACTS))

    def test_fait_numerique_hors_mandat(self) -> None:
        """Déplacer un seuil est un autre geste que choisir des réponses."""
        numerique = {
            "nb": FactDef.model_validate({"type": "integer", "scope": "monument", "question": "q?"})
        }
        self.assertFalse(
            ca.condition_modifiable(self._condition(fact="nb", predicate={"gte": 40}), numerique)
        )

    def test_fait_booleen_hors_mandat(self) -> None:
        booleen = {"b": _fact_booleen()}
        self.assertFalse(
            ca.condition_modifiable(self._condition(fact="b", predicate={"eq": True}), booleen)
        )

    def test_combinateur_hors_mandat(self) -> None:
        """L'interface ne sait pas rendre un any_of : un éditeur qui ne peut pas
        AFFICHER ce qu'il modifie est une machine à casser des prédicats."""
        condition = self._condition(predicate={"any_of": [{"eq": "culte"}, {"eq": "musee"}]})
        self.assertFalse(ca.condition_modifiable(condition, FACTS))

    def test_fait_inconnu_hors_mandat(self) -> None:
        self.assertFalse(ca.condition_modifiable(self._condition(fact="absent"), FACTS))


class ValidationPredicatTests(unittest.TestCase):
    def _condition(self):
        return _aide("a", [_gate_modifiable()]).conditions[0]

    def test_predicat_valide_passe(self) -> None:
        ca.valider_predicat(self._condition(), {"in": ["culte", "musee"]}, FACTS)

    def test_combinateur_refuse(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            ca.valider_predicat(self._condition(), {"any_of": [{"eq": "culte"}]}, FACTS)
        self.assertIn("prédicat composé", str(ctx.exception))

    def test_liste_vide_refusee(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            ca.valider_predicat(self._condition(), {"in": []}, FACTS)
        self.assertIn("au moins une réponse", str(ctx.exception))

    def test_valeur_hors_options_refusee_avec_le_message_du_lint(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            ca.valider_predicat(self._condition(), {"eq": "ferme"}, FACTS)
        self.assertIn("hors options du fait", str(ctx.exception))

    def test_operateur_hors_des_admis_refuse(self) -> None:
        with self.assertRaises(ValueError):
            ca.valider_predicat(self._condition(), {"gte": 3}, FACTS)

    def test_none_in_refuse_sur_un_choix_simple(self) -> None:
        """Même validation que le lint : `none_in` n'existe que sur un multi_enum."""
        with self.assertRaises(ValueError):
            ca.valider_predicat(self._condition(), {"none_in": ["culte"]}, FACTS)

    def test_validation_contre_lontologie_effective(self) -> None:
        """Un prédicat peut légitimement citer une réponse qui n'existe que dans
        `faits_surcharges` : les deux forment alors un bloc indissociable."""
        surchargee = ca.surcharger_fait(
            _fact_enum(),
            SurchargeFait(
                fact_key="usage",
                options=[
                    OptionSurchargee(id="culte", label="Culte"),
                    OptionSurchargee(id="grange", label="Grange"),
                ],
            ),
        )
        ca.valider_predicat(self._condition(), {"eq": "grange"}, {"usage": surchargee})
        with self.assertRaises(ValueError):
            ca.valider_predicat(self._condition(), {"eq": "grange"}, FACTS)


class VerdictPredicatTests(unittest.TestCase):
    """La cascade d'états, un par un — et l'asymétrie `a_revoir`."""

    AIDES = {"a": _aide("a", [_gate_modifiable()])}

    def _verdict(self, ligne: ca.SurchargePredicat, aides=None):
        return ca.verdict_predicat(ligne, aides if aides is not None else self.AIDES, FACTS)

    def test_active(self) -> None:
        self.assertEqual(self._verdict(_ligne()).etat, "active")

    def test_aide_absente(self) -> None:
        self.assertEqual(self._verdict(_ligne(slug="partie")).etat, "aide_absente")

    def test_condition_absente(self) -> None:
        self.assertEqual(self._verdict(_ligne(cid="autre")).etat, "condition_absente")

    def test_hors_mandat(self) -> None:
        aides = {"a": _aide("a", [{**_gate_modifiable(), "effect": "info"}])}
        self.assertEqual(self._verdict(_ligne(), aides).etat, "hors_mandat")

    def test_perimee_fait(self) -> None:
        """Un retypage vers un autre fait rendrait le prédicat absurde sans rien
        changer au texte."""
        facts = {**FACTS, "autre": _fact_enum()}
        aides = {"a": _aide("a", [_gate_modifiable(fact="autre")])}
        verdict = ca.verdict_predicat(_ligne(), aides, facts)
        self.assertEqual(verdict.etat, "perimee_fait")
        self.assertFalse(verdict.appliquee)

    def test_perimee_texte(self) -> None:
        aides = {"a": _aide("a", [{**_gate_modifiable(), "text": "Un tout autre critère."}])}
        verdict = self._verdict(_ligne(), aides)
        self.assertEqual(verdict.etat, "perimee_texte")
        self.assertFalse(verdict.appliquee)
        # Le panneau doit pouvoir afficher l'ancien à côté du nouveau.
        self.assertEqual(verdict.condition_text_actuel, "Un tout autre critère.")
        self.assertEqual(verdict.ligne.condition_text, "Le bien doit être un lieu de culte.")

    def test_un_simple_re_repli_du_texte_ne_perime_pas(self) -> None:
        """Le même texte coupé à une autre colonne périmerait toutes les
        surcharges de la fiche — un faux positif de masse."""
        replie = "Le bien doit être\n    un lieu   de culte."
        aides = {"a": _aide("a", [{**_gate_modifiable(), "text": replie}])}
        self.assertEqual(self._verdict(_ligne(), aides).etat, "active")

    def test_invalide_quand_une_reponse_citee_disparait(self) -> None:
        restreint = {"usage": _fact_enum(options=[{"id": "culte", "label": "Culte"}])}
        verdict = ca.verdict_predicat(_ligne(), self.AIDES, restreint)
        self.assertEqual(verdict.etat, "invalide")
        self.assertFalse(verdict.appliquee)

    def test_a_revoir_quand_le_yaml_a_rattrape(self) -> None:
        """Le YAML a bougé mais le texte n'a pas changé : on garde le correctif
        et on demande un arbitrage."""
        aides = {"a": _aide("a", [_gate_modifiable(predicate={"eq": "musee"})])}
        verdict = self._verdict(_ligne(), aides)
        self.assertEqual(verdict.etat, "a_revoir")

    def test_asymetrie_a_revoir_appliquee_perimee_non(self) -> None:
        """LA décision de conception : ignorer une surcharge « à revoir »
        re-casserait en silence ce que l'administrateur avait réparé."""
        rattrape = {"a": _aide("a", [_gate_modifiable(predicate={"eq": "musee"})])}
        perime = {"a": _aide("a", [{**_gate_modifiable(), "text": "Autre chose."}])}
        self.assertTrue(self._verdict(_ligne(), rattrape).appliquee)
        self.assertFalse(self._verdict(_ligne(), perime).appliquee)


class AppliquerPredicatsTests(unittest.TestCase):
    AIDES = {"a": _aide("a", [_gate_modifiable()]), "b": _aide("b", [_gate_modifiable()])}

    def _verdicts(self, **over):
        ligne = _ligne(**over)
        return {
            (ligne.aide_slug, ligne.condition_id): ca.verdict_predicat(ligne, self.AIDES, FACTS)
        }

    def test_substitue_le_predicat(self) -> None:
        effectives = ca.appliquer_predicats(self.AIDES, self._verdicts(), FACTS)
        self.assertEqual(effectives["a"].conditions[0].predicate.root, {"in": ["culte", "musee"]})

    def test_ne_touche_que_les_aides_concernees(self) -> None:
        effectives = ca.appliquer_predicats(self.AIDES, self._verdicts(), FACTS)
        self.assertIs(effectives["b"], self.AIDES["b"])

    def test_sans_ligne_rien_nest_reconstruit(self) -> None:
        effectives = ca.appliquer_predicats(self.AIDES, {}, FACTS)
        self.assertIs(effectives["a"], self.AIDES["a"])

    def test_une_surcharge_perimee_ne_sapplique_pas(self) -> None:
        aides = {"a": _aide("a", [{**_gate_modifiable(), "text": "Autre chose."}])}
        ligne = _ligne()
        verdicts = {("a", "g1"): ca.verdict_predicat(ligne, aides, FACTS)}
        effectives = ca.appliquer_predicats(aides, verdicts, FACTS)
        self.assertIs(effectives["a"], aides["a"])

    def test_le_corpus_yaml_reste_intact(self) -> None:
        """L'invariant qui court dans tout le fichier : les structures des
        loaders `@cache` sont PARTAGÉES entre requêtes."""
        avant = load_all_aides()
        ca.appliquer_predicats(avant, {}, FACTS)
        self.assertIs(load_all_aides(), avant)

    def test_un_predicat_invalide_conserve_laide_yaml(self) -> None:
        """Ce test interdit un futur `model_copy(update=)` : en Pydantic v2 il
        NE RELANCE PAS les validateurs, et le prédicat malformé passerait
        jusque dans le moteur."""
        ligne = _ligne(predicate={"in": ["culte"], "eq": "musee"})
        verdict = ca.VerdictPredicat(ligne, "active")
        effectives = ca.appliquer_predicats(self.AIDES, {("a", "g1"): verdict}, FACTS)
        self.assertIs(effectives["a"], self.AIDES["a"])


class ImpactPredicatTests(unittest.TestCase):
    def _aide_et_condition(self, **over):
        champs = _gate_modifiable()
        champs.update(over)
        aide = _aide("a", [champs])
        return aide, aide.conditions[0]

    def test_verdict_avant_apres_par_reponse(self) -> None:
        aide, condition = self._aide_et_condition()
        impact = ca.impact_predicat(aide, condition, {"in": ["culte", "musee"]}, FACTS)
        par_id = {r["id"]: r for r in impact["parReponse"]}
        # « musee » était écarté par `eq: culte`, il ne l'est plus.
        self.assertTrue(par_id["musee"]["avantEcarte"])
        self.assertFalse(par_id["musee"]["apresEcarte"])
        self.assertTrue(par_id["musee"]["changement"])
        # « culte » ne bouge pas.
        self.assertFalse(par_id["culte"]["changement"])

    def test_reponse_neutre_necarte_jamais(self) -> None:
        aide, condition = self._aide_et_condition()
        impact = ca.impact_predicat(aide, condition, {"eq": "musee"}, FACTS)
        neutre = next(r for r in impact["parReponse"] if r["id"] == "inconnu")
        self.assertFalse(neutre["avantEcarte"])
        self.assertFalse(neutre["apresEcarte"])

    def test_le_avant_est_le_predicat_servi(self) -> None:
        """« Ce que ça change à partir de maintenant », pas par rapport à un
        état que plus personne ne voit."""
        aide, condition = self._aide_et_condition(predicate={"eq": "musee"})
        impact = ca.impact_predicat(aide, condition, {"eq": "musee"}, FACTS)
        self.assertEqual(impact["avant"], {"eq": "musee"})
        self.assertFalse(any(r["changement"] for r in impact["parReponse"]))

    def test_avertissement_derogation(self) -> None:
        aide, condition = self._aide_et_condition(derogation_possible=True)
        impact = ca.impact_predicat(aide, condition, {"eq": "musee"}, FACTS)
        self.assertTrue(any("Dérogation" in a for a in impact["avertissements"]))

    def test_avertissement_applies_if(self) -> None:
        aide, condition = self._aide_et_condition(
            applies_if={"fact": "usage", "predicate": {"eq": "culte"}}
        )
        impact = ca.impact_predicat(aide, condition, {"eq": "musee"}, FACTS)
        self.assertTrue(any("certains profils" in a for a in impact["avertissements"]))

    def test_avertissement_autre_gate_sur_le_meme_fait(self) -> None:
        aide = _aide("a", [_gate_modifiable(), _gate_modifiable(cid="g2")])
        impact = ca.impact_predicat(aide, aide.conditions[0], {"eq": "musee"}, FACTS)
        self.assertTrue(any("autre gate" in a for a in impact["avertissements"]))

    def test_avertissement_aide_non_engine_ready(self) -> None:
        aide, condition = self._aide_et_condition()
        impact = ca.impact_predicat(aide, condition, {"eq": "musee"}, FACTS, engine_ready=False)
        self.assertTrue(any("aucun effet" in a for a in impact["avertissements"]))

    def test_avertissement_aide_retiree(self) -> None:
        aide, condition = self._aide_et_condition()
        impact = ca.impact_predicat(aide, condition, {"eq": "musee"}, FACTS, retiree=True)
        self.assertTrue(any("retirée" in a for a in impact["avertissements"]))


class _Resp:
    def __init__(self, data) -> None:
        self.data = data


class _Query:
    def __init__(self, rows: list, compteur: dict, table: str) -> None:
        self._rows = rows
        self._compteur = compteur
        self._table = table

    def select(self, *_a, **_k) -> "_Query":
        self._compteur[self._table] = self._compteur.get(self._table, 0) + 1
        return self

    def execute(self) -> _Resp:
        return _Resp(list(self._rows))


class _FakeSupabase:
    def __init__(self, **tables) -> None:
        self._tables = tables
        self.lectures: dict[str, int] = {}

    def table(self, name: str) -> _Query:
        return _Query(self._tables.get(name, []), self.lectures, name)


class _SupabaseEnPanne:
    def table(self, _name: str):
        raise RuntimeError("relation « aides_retirees » inexistante")


class CacheTests(unittest.TestCase):
    def setUp(self) -> None:
        ca.invalider()

    def tearDown(self) -> None:
        # Sinon l'état fuit vers les autres fichiers de tests du même process.
        ca.invalider()

    def test_deux_appels_une_seule_lecture(self) -> None:
        supabase = _FakeSupabase()
        ca.catalogue_effectif(supabase)
        ca.catalogue_effectif(supabase)
        self.assertEqual(supabase.lectures.get(ca.TABLE_RETIREES), 1)
        self.assertEqual(supabase.lectures.get(ca.TABLE_SURCHARGES), 1)

    def test_invalider_force_la_relecture(self) -> None:
        supabase = _FakeSupabase()
        ca.catalogue_effectif(supabase)
        ca.invalider()
        ca.catalogue_effectif(supabase)
        self.assertEqual(supabase.lectures.get(ca.TABLE_RETIREES), 2)

    def test_ttl_expire(self) -> None:
        supabase = _FakeSupabase()
        with patch.object(ca.time, "monotonic", return_value=1000.0):
            ca.catalogue_effectif(supabase)
        with patch.object(ca.time, "monotonic", return_value=1000.0 + ca.TTL_SECONDES + 1):
            ca.catalogue_effectif(supabase)
        self.assertEqual(supabase.lectures.get(ca.TABLE_RETIREES), 2)

    def test_applique_les_deux_tables(self) -> None:
        corpus = load_all_aides()
        slug = next(iter(corpus))
        key = next(k for k, f in load_facts().items() if f.type == "enum")
        supabase = _FakeSupabase(
            aides_retirees=[{"slug": slug, "motif": "obsolète"}],
            faits_surcharges=[{"fact_key": key, "question": "Reformulée ?"}],
        )
        catalogue = ca.catalogue_effectif(supabase)
        self.assertNotIn(slug, catalogue.aides)
        self.assertEqual(catalogue.retirees[slug]["motif"], "obsolète")
        self.assertEqual(catalogue.facts[key].question, "Reformulée ?")

    def test_ligne_malformee_ignoree(self) -> None:
        supabase = _FakeSupabase(
            aides_retirees=[{"slug": None}, {"motif": "sans slug"}],
            faits_surcharges=[
                {"question": "sans clé"},
                {"fact_key": "k", "options": "pas une liste"},
            ],
        )
        catalogue = ca.catalogue_effectif(supabase)
        self.assertEqual(catalogue.retirees, {})
        self.assertEqual(catalogue.surcharges, {})

    def test_base_injoignable_sert_les_yaml(self) -> None:
        """La migration pas encore appliquée ne doit pas couper le diagnostic."""
        catalogue = ca.catalogue_effectif(_SupabaseEnPanne())
        self.assertEqual(catalogue.retirees, {})
        self.assertEqual(set(catalogue.aides), set(load_all_aides()))


if __name__ == "__main__":
    unittest.main()
