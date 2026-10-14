"""Le sens des prédicats (catalogue/polarite.py) : ce que le prédicat admet, contre ce que Jev lit.

Aucun appel réseau : un faux client de Jev rend des probabilités fixées.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aides_schema import Condition, FactDef
from catalogue import polarite as pol
from catalogue.openrouter import Avis, Decision

FAITS = {
    "etat_travaux": FactDef.model_validate(
        {
            "type": "enum",
            "scope": "projet",
            "question": "Où en sont les travaux ?",
            "options": [
                {"id": "non_commences", "label": "Pas commencés"},
                {"id": "commences", "label": "Commencés"},
                {"id": "aucun", "label": "Aucun : ce projet ne comporte pas de travaux"},
                {"id": "ne_sait_pas", "label": "Je ne sais pas", "unknown": True},
            ],
        }
    ),
    "orgue_present": FactDef.model_validate(
        {"type": "boolean", "scope": "monument", "question": "Le monument abrite-t-il un orgue ?"}
    ),
    "budget": FactDef.model_validate(
        {"type": "integer", "scope": "projet", "question": "Quel budget ?"}
    ),
}


def _gate(**c: Any) -> Condition:
    return Condition.model_validate({"id": "c", "text": "Texte.", "effect": "gate", **c})


class FauxClient:
    def __init__(self, p: dict[str, float]) -> None:
        self.p, self.appels = p, 0

    def decider(self, modele: str, etat: Any, questions: dict[str, Any], **_: Any) -> Decision:
        self.appels += 1
        avis = {
            q: Avis("noul", {"true": self.p.get(q, 0.5), "false": 1 - self.p.get(q, 0.5)})
            for q in questions
        }
        return Decision(avis, modele, 0.00001, 10, 0.1)

    def fermer(self) -> None:
        pass


def test_le_predicat_est_lu_comme_le_moteur_le_lit() -> None:
    c = _gate(kind="user_fact", fact="etat_travaux", predicate={"eq": "non_commences"})
    g = pol.gate_de("a", "Aide", c, FAITS)
    assert g is not None
    # « Je ne sais pas » ne tranche pas : le moteur n'en écarte personne, il n'est pas jugé.
    assert [(r.id, r.admise) for r in g.reponses] == [
        ("non_commences", True),
        ("commences", False),
        ("aucun", False),
    ]
    booleen = pol.gate_de(
        "a", "Aide", _gate(kind="user_fact", fact="orgue_present", predicate={"eq": True}), FAITS
    )
    assert booleen is not None and [(r.id, r.admise) for r in booleen.reponses] == [
        ("oui", True),
        ("non", False),
    ]


def test_seules_les_gates_sur_un_fait_a_reponses_sont_jugees() -> None:
    assert pol.gate_de("a", "A", _gate(kind="info", effect="info"), FAITS) is None
    numerique = _gate(kind="user_fact", fact="budget", predicate={"gte": 10000})
    assert pol.gate_de("a", "A", numerique, FAITS) is None
    modulateur = _gate(
        kind="user_fact", fact="orgue_present", predicate={"eq": True}, effect="modulateur"
    )
    assert pol.gate_de("a", "A", modulateur, FAITS) is None


def test_un_desaccord_a_un_sens_et_un_jugement_n_est_paye_qu_une_fois(tmp_path: Path) -> None:
    c = _gate(kind="user_fact", fact="etat_travaux", predicate={"eq": "non_commences"})
    g = pol.gate_de("a", "Aide", c, FAITS)
    assert g is not None
    # r0 = non_commences, r1 = commences, r2 = aucun.
    client = FauxClient({"r0": 0.95, "r1": 0.05, "r2": 0.9})
    juge = pol.Juge(tmp_path / "p.jsonl", client=client)
    probas = juge.juger(g)
    assert probas == {"non_commences": 0.95, "commences": 0.05, "aucun": 0.9}
    d = pol.desaccords(g, probas, haut=0.8, bas=0.2)
    assert [(x.reponse.id, x.sens) for x in d] == [("aucun", "ecarte_a_tort")]
    # Rejugé depuis le fichier, sans appel.
    relu = pol.Juge(tmp_path / "p.jsonl", client=FauxClient({}))
    assert relu.juger(g) == probas and client.appels == 1


AIDE = """\
slug: neuve
nom: Aide neuve
organisme: Région
description: Une aide.
categorie: region
type: subvention
conditions:
- id: depot
  text: Les travaux ne doivent pas avoir commencé au dépôt.
  kind: user_fact
  effect: gate
  fact: etat_travaux
  predicate: {eq: non_commences}
"""


def test_le_lint_bloque_un_predicat_qui_ecarte_une_reponse_admise(tmp_path: Path) -> None:
    juge = pol.Juge(tmp_path / "p.jsonl", client=FauxClient({"r0": 0.95, "r1": 0.1, "r2": 0.9}))
    bloquants, indications, panne = pol.verifier("neuve", AIDE, FAITS, juge=juge, seuils=(0.8, 0.2))
    assert panne is None and indications == []
    assert len(bloquants) == 1 and "depot" in bloquants[0] and "`aucun`" in bloquants[0]


def test_un_predicat_trop_large_n_est_qu_une_indication(tmp_path: Path) -> None:
    juge = pol.Juge(tmp_path / "p.jsonl", client=FauxClient({"r0": 0.1, "r1": 0.1, "r2": 0.1}))
    bloquants, indications, _ = pol.verifier("neuve", AIDE, FAITS, juge=juge, seuils=(0.8, 0.2))
    assert bloquants == [] and len(indications) == 1 and "non_commences" in indications[0]


def test_le_controle_se_tait_quand_l_espace_est_coupe(monkeypatch: Any) -> None:
    monkeypatch.setenv("MONUMIA_ESPACE", "0")
    assert pol.verifier("neuve", AIDE, FAITS) == ([], [], None)


def test_l_empreinte_du_registre_est_celle_du_code() -> None:
    from catalogue.registre import charger

    assert charger().decisions[pol.DECISION].empreintes["questions"] == pol.EMPREINTE_QUESTIONS
