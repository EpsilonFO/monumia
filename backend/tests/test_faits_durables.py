"""Les faits DURABLES d'un monument : ce qu'un nouveau projet ne redemande pas.

Le service est PUR (aucune base, aucun réseau) : on lui passe des lignes de
projets et l'ontologie. Trois choses à tenir, et chacune a coûté un bogue
ailleurs :

- la SUPERPOSITION de tous les projets, et non « le plus récent qui a des
  réponses » : un projet à dix faits suivi d'un projet à trois en perdrait sept ;
- le scope : seuls `monument` et `proprietaire` se reprennent. Un fait de scope
  `projet` décrit CE chantier, et le reprendre ferait mentir le suivant ;
- la provenance : sans elle, la reprise n'est pas explicable à l'écran.
"""

import unittest

from aides_schema import FactDef
from services.faits_durables import details_reprises, faits_durables, libelle_reponse


def _fait(scope: str, type_: str = "boolean") -> FactDef:
    return FactDef.model_validate({"type": type_, "scope": scope, "question": "q ?"})


def _fait_nomme(scope: str, question: str, type_: str = "boolean") -> FactDef:
    return FactDef.model_validate({"type": type_, "scope": scope, "question": question})


def _fait_avec_unite(scope: str, type_: str, unit: str) -> FactDef:
    return FactDef.model_validate({"type": type_, "scope": scope, "question": "q ?", "unit": unit})


FACTS = {
    "edifice_cultuel": _fait_nomme("monument", "L'édifice est-il cultuel ?"),
    "possede_orgue": _fait("monument"),
    "revenu_fiscal": _fait_nomme("proprietaire", "Quel est votre revenu fiscal ?", "number"),
    "etat_travaux": _fait("projet"),
    "budget_travaux": _fait("projet", "number"),
}


def _projet(pid: str, questionnaire: dict, updated_at: str, titre: str | None = None) -> dict:
    return {"id": pid, "titre": titre, "questionnaire": questionnaire, "updated_at": updated_at}


class FaitsDurablesTest(unittest.TestCase):
    def test_ne_reprend_que_le_bien_et_le_proprietaire(self) -> None:
        projets = [
            _projet(
                "p1",
                {
                    "edifice_cultuel": "oui",
                    "revenu_fiscal": "ge40000",
                    "etat_travaux": "acheves",
                    "budget_travaux": "ge10000",
                },
                "2026-01-01",
            )
        ]
        reponses, source = faits_durables(projets, FACTS)
        self.assertEqual(reponses, {"edifice_cultuel": "oui", "revenu_fiscal": "ge40000"})
        self.assertEqual(source, {"edifice_cultuel": "p1", "revenu_fiscal": "p1"})

    def test_superpose_tous_les_projets_cle_par_cle(self) -> None:
        """Le cas qui interdit « le dernier projet qui a des réponses » : le
        projet récent n'a qu'un fait, l'ancien en avait deux."""
        projets = [
            _projet("ancien", {"edifice_cultuel": "oui", "possede_orgue": "non"}, "2026-01-01"),
            _projet("recent", {"possede_orgue": "oui"}, "2026-06-01"),
        ]
        reponses, source = faits_durables(projets, FACTS)
        self.assertEqual(reponses, {"edifice_cultuel": "oui", "possede_orgue": "oui"})
        # Le plus récent l'emporte PAR CLÉ, et la provenance suit.
        self.assertEqual(source, {"edifice_cultuel": "ancien", "possede_orgue": "recent"})

    def test_une_question_passee_ne_se_reprend_pas(self) -> None:
        """`skip` ne dit rien : ni reprise (libellé vide à l'écran), ni
        écrasement de la vraie réponse d'un projet plus ancien."""
        projets = [
            _projet("ancien", {"edifice_cultuel": "oui"}, "2026-01-01"),
            _projet("recent", {"edifice_cultuel": "skip", "possede_orgue": "skip"}, "2026-06-01"),
        ]
        reponses, source = faits_durables(projets, FACTS)
        self.assertEqual(reponses, {"edifice_cultuel": "oui"})
        self.assertEqual(source, {"edifice_cultuel": "ancien"})

    def test_l_ordre_de_la_liste_ne_compte_pas(self) -> None:
        """Le tri se fait sur `updated_at`, pas sur l'ordre rendu par la base."""
        anciens = _projet("ancien", {"possede_orgue": "non"}, "2026-01-01")
        recents = _projet("recent", {"possede_orgue": "oui"}, "2026-06-01")
        for ordre in ([anciens, recents], [recents, anciens]):
            reponses, source = faits_durables(ordre, FACTS)
            self.assertEqual(reponses, {"possede_orgue": "oui"})
            self.assertEqual(source, {"possede_orgue": "recent"})

    def test_les_projets_clotures_comptent(self) -> None:
        """Un chantier terminé décrit toujours le même bien, et son
        questionnaire est souvent le plus complet."""
        projets = [
            _projet("clos", {"edifice_cultuel": "oui"}, "2026-01-01")
            | {"cloture_at": "2026-02-01"},
        ]
        reponses, _ = faits_durables(projets, FACTS)
        self.assertEqual(reponses, {"edifice_cultuel": "oui"})

    def test_les_cles_reservees_sont_ignorees(self) -> None:
        """`_raisons` et `_familles` portent le CADRAGE, qui est propre au
        chantier : les reprendre imposerait au nouveau projet l'intention de
        l'ancien."""
        projets = [
            _projet(
                "p1",
                {"_raisons": ["restauration_travaux"], "_familles": [], "edifice_cultuel": "oui"},
                "2026-01-01",
            )
        ]
        reponses, _ = faits_durables(projets, FACTS)
        self.assertEqual(reponses, {"edifice_cultuel": "oui"})

    def test_un_fait_retire_de_lontologie_est_ignore(self) -> None:
        """Fail-closed : une réponse dont le fait n'existe plus ne se reprend
        pas — elle serait un fait inconnu dans le contexte du moteur."""
        projets = [_projet("p1", {"fait_disparu": "oui", "possede_orgue": "non"}, "2026-01-01")]
        reponses, _ = faits_durables(projets, FACTS)
        self.assertEqual(reponses, {"possede_orgue": "non"})

    def test_aucun_projet_ou_questionnaire_vide(self) -> None:
        self.assertEqual(faits_durables([], FACTS), ({}, {}))
        self.assertEqual(faits_durables([_projet("p1", {}, "2026-01-01")], FACTS), ({}, {}))

    def test_questionnaire_absent_ou_mal_forme(self) -> None:
        """La colonne est un `jsonb` : elle peut porter autre chose qu'un objet
        sur une ligne héritée. On l'ignore plutôt que de casser la création du
        projet suivant."""
        projets = [
            {"id": "p1", "questionnaire": None, "updated_at": "2026-01-01"},
            {"id": "p2", "questionnaire": ["pas un objet"], "updated_at": "2026-02-01"},
            {"id": "p3", "updated_at": "2026-03-01"},
            _projet("p4", {"possede_orgue": "oui"}, "2026-04-01"),
        ]
        reponses, source = faits_durables(projets, FACTS)
        self.assertEqual(reponses, {"possede_orgue": "oui"})
        self.assertEqual(source, {"possede_orgue": "p4"})

    def test_updated_at_absent_passe_en_premier(self) -> None:
        """Une ligne sans date est traitée comme la plus ancienne : elle ne doit
        pas écraser une réponse datée."""
        projets = [
            {"id": "sans-date", "questionnaire": {"possede_orgue": "non"}},
            _projet("date", {"possede_orgue": "oui"}, "2026-01-01"),
        ]
        reponses, source = faits_durables(projets, FACTS)
        self.assertEqual(reponses, {"possede_orgue": "oui"})
        self.assertEqual(source, {"possede_orgue": "date"})


class FaitsDurablesSurLOntologieReelleTest(unittest.TestCase):
    """Sur l'ontologie du dépôt : le service doit reprendre quelque chose, sinon
    la phase entière ne sert à rien."""

    def test_le_scope_partage_les_faits_en_trois(self) -> None:
        from aides_schema import load_facts, load_pending_facts
        from services.faits_durables import SCOPES_DURABLES

        facts = {**load_facts(), **load_pending_facts()}
        durables = [k for k, f in facts.items() if f.scope in SCOPES_DURABLES]
        projet = [k for k, f in facts.items() if f.scope == "projet"]
        # Les ordres de grandeur du plan : ~100 faits durables, et une majorité
        # de faits de projet. Bornes larges — c'est un garde-fou, pas un
        # ratchet : l'ontologie bouge à chaque ingestion.
        self.assertGreater(len(durables), 50)
        self.assertGreater(len(projet), 50)

        questionnaire = {k: "oui" for k in facts}
        reponses, _ = faits_durables(
            [{"id": "p1", "questionnaire": questionnaire, "updated_at": "2026-01-01"}], facts
        )
        self.assertEqual(sorted(reponses), sorted(durables))


if __name__ == "__main__":
    unittest.main()


class LibelleDesReprisesTest(unittest.TestCase):
    """Nommer les réponses reprises. Sans ça, le bandeau du questionnaire
    annonce un nombre que rien ne permet de vérifier — et il ne peut pas
    renvoyer à la fiche de l'aide, puisqu'une réponse reprise n'est plus une
    incertitude et que le moteur ne rend plus sa question.
    """

    def test_un_booleen_sans_options_declarees(self) -> None:
        """Le couple implicite Oui/Non suffit à rendre la réponse."""
        fait = _fait("monument")
        self.assertEqual(libelle_reponse(fait, "oui"), "Oui")
        self.assertEqual(libelle_reponse(fait, "non"), "Non")

    def test_un_enum_rend_le_libelle_de_son_option(self) -> None:
        fait = FactDef.model_validate(
            {
                "type": "enum",
                "scope": "monument",
                "question": "Quel usage ?",
                "options": [
                    {"id": "cultuel", "label": "Lieu de culte"},
                    {"id": "habitation", "label": "Habitation"},
                ],
            }
        )
        self.assertEqual(libelle_reponse(fait, "cultuel"), "Lieu de culte")

    def test_un_multi_enum_joint_les_cases_cochees(self) -> None:
        fait = FactDef.model_validate(
            {
                "type": "multi_enum",
                "scope": "proprietaire",
                "question": "Qui peut déposer ?",
                "options": [
                    {"id": "association", "label": "Une association"},
                    {"id": "commune", "label": "La commune"},
                ],
            }
        )
        self.assertEqual(
            libelle_reponse(fait, ["association", "commune"]), "Une association, La commune"
        )

    def test_une_tranche_numerique_se_relit_depuis_son_identifiant(self) -> None:
        """Les tranches sont fabriquées par le moteur depuis les seuils des
        aides candidates, qu'on n'a pas ici — mais l'identifiant porte ses
        bornes, donc le libellé se reconstruit à l'identique (`libelle_tranche`,
        testée en aller-retour dans test_eligibility_engine)."""
        self.assertEqual(
            libelle_reponse(_fait_avec_unite("proprietaire", "number", "€"), "ge40000"),
            "40000€ ou plus",
        )
        self.assertEqual(
            libelle_reponse(_fait_avec_unite("projet", "integer", "ans"), "lt5"),
            "Moins de 5 ans",
        )
        # L'accord du singulier suit, comme à l'écran.
        self.assertEqual(
            libelle_reponse(_fait_avec_unite("projet", "integer", "ans"), "ge1"),
            "1 an ou plus",
        )

    def test_une_valeur_numerique_hors_tranche_ne_se_nomme_pas(self) -> None:
        """Une réponse d'avant les tranches, ou écrite à la main : on n'invente
        pas de libellé."""
        fait = _fait_avec_unite("proprietaire", "number", "€")
        self.assertIsNone(libelle_reponse(fait, "40000"))
        self.assertIsNone(libelle_reponse(fait, 40000))

    def test_une_option_disparue_ne_se_nomme_pas(self) -> None:
        """Fail-closed : une réponse persistée sur une option retirée depuis
        n'a plus de libellé, et on n'en invente pas."""
        self.assertIsNone(libelle_reponse(_fait("monument"), "peut_etre"))

    def test_details_nomme_question_reponse_et_provenance(self) -> None:
        reponses = {"edifice_cultuel": "oui", "revenu_fiscal": "ge40000"}
        source = {"edifice_cultuel": "p1", "revenu_fiscal": "p2"}
        details = details_reprises(reponses, source, FACTS, {"p1": "Toiture 2024", "p2": None})
        self.assertEqual([d["fact"] for d in details], ["edifice_cultuel", "revenu_fiscal"])
        self.assertEqual(details[0]["reponse"], "Oui")
        self.assertEqual(details[0]["projetTitre"], "Toiture 2024")
        self.assertEqual([d["scope"] for d in details], ["monument", "proprietaire"])
        # La tranche numérique est relue depuis son identifiant : les bornes y
        # sont. Le fixture n'a pas d'unité, d'où le libellé nu.
        self.assertEqual(details[1]["reponse"], "40000 ou plus")
        self.assertIsNone(details[1]["projetTitre"])

    def test_details_ignore_un_fait_retire_de_lontologie(self) -> None:
        details = details_reprises({"disparu": "oui"}, {"disparu": "p1"}, FACTS, {})
        self.assertEqual(details, [])
