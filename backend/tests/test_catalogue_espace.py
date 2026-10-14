"""L'espace des conditions et des faits (catalogue/espace.py) : familles, contrôle, étape de la semaine.

Aucun appel réseau : un faux embedding range les textes par mots-clés, un faux
client de Jev rend des distributions fixées. Ce que ces tests fixent :

  - un jugement de Jev est gardé une fois pour toutes, et relu sans appel ;
  - une condition typée autrement que ses voisines confirmées ouvre UNE case,
    et seulement elle ;
  - un écart accepté ou déjà répondu ne revient pas en case ;
  - un fait proposé que Jev rattache à un fait existant n'est écrit qu'après
    lecture de ce fait, et le rattachement est noté pour Félix ;
  - les empreintes déclarées au registre sont celles du code.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from aides_schema import Condition, FactDef
from catalogue import coherence as co
from catalogue import espace as esp_mod
from catalogue.journal import empreinte
from catalogue.openrouter import Avis, Decision
from catalogue.registre import charger

MOTS = ("travaux", "commenc", "commune", "habitants", "dossier", "orgue", "devis")


class FauxPlongeur:
    """Un vecteur par présence de mots-clés : deux textes qui partagent leurs mots sont proches."""

    cout_usd = 0.0

    def vecteurs(self, textes: list[str]) -> np.ndarray:
        lignes = []
        for t in textes:
            v = np.array([1.0 if m in t.lower() else 0.0 for m in MOTS] + [0.01])
            lignes.append(v / np.linalg.norm(v))
        return np.stack(lignes)

    def fermer(self) -> None:
        pass


class FauxClient:
    """Jev : « même critère » à `p` pour toute paire, ou la distribution donnée."""

    def __init__(self, distribution: dict[str, float]) -> None:
        self.distribution = distribution
        self.appels = 0

    def decider(self, modele: str, etat: Any, questions: Any, **_: Any) -> Decision:
        self.appels += 1
        nom = next(iter(questions))
        return Decision({nom: Avis("choice", dict(self.distribution))}, modele, 0.00001, 10, 0.1)

    def fermer(self) -> None:
        pass


MEME = {co.MEME: 0.95, co.VOISIN: 0.04, co.AUTRE: 0.01}


def _ligne(slug: str, rang: int = 0, **condition: Any) -> co.Ligne:
    c = Condition.model_validate({"id": f"c{rang}", **condition})
    return co.Ligne(slug, slug, c, rang=rang)


GATE = {
    "text": "Les travaux ne doivent pas avoir commencé au dépôt du dossier.",
    "kind": "user_fact",
    "fact": "etat_travaux",
    "predicate": {"in": ["non_commences", "aucun"]},
}
INFO = {"text": "Le dossier doit être déposé avant le commencement des travaux.", "kind": "info"}


def _espace(tmp_path: Path, lignes: list[co.Ligne], client: FauxClient) -> esp_mod.Espace:
    juge = co.Juge(tmp_path / "jugements.jsonl", client=client)  # type: ignore[arg-type]
    return esp_mod.Espace(
        lignes,
        plongeur=FauxPlongeur(),
        juge=juge,
        reglages=esp_mod.Reglages(),  # type: ignore[arg-type]
    )


# ------------------------------------------------------------------ Jev gardé


def test_un_jugement_est_garde_et_relu_sans_appel(tmp_path: Path) -> None:
    client = FauxClient(MEME)
    juge = co.Juge(tmp_path / "j.jsonl", client=client)  # type: ignore[arg-type]
    etat = {"A": {"condition": "a"}, "B": {"condition": "b"}}
    assert juge.juger(etat) == MEME
    assert juge.juger(etat) == MEME
    assert client.appels == 1
    # Une autre instance (le run de la semaine suivante) relit le fichier.
    autre = FauxClient({co.MEME: 0.1, co.VOISIN: 0.1, co.AUTRE: 0.8})
    relu = co.Juge(tmp_path / "j.jsonl", client=autre)  # type: ignore[arg-type]
    assert relu.juger(etat) == MEME and autre.appels == 0
    ligne = json.loads((tmp_path / "j.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert set(ligne) == {"k", "p"}


def test_l_ordre_d_une_paire_ne_change_pas_sa_cle() -> None:
    a, b = _ligne("a-aide", 1, **GATE), _ligne("b-aide", 0, **INFO)
    assert co.paire(a, b) == co.paire(b, a) == (a, b)


# ------------------------------------------------------------------ famille et contrôle


def test_une_condition_qui_s_ecarte_de_sa_famille_ouvre_une_case(tmp_path: Path) -> None:
    catalogue = [_ligne(f"aide-{k}", 0, **GATE) for k in range(4)]
    espace = _espace(tmp_path, catalogue, FauxClient(MEME))
    texte = """\
slug: neuve
nom: Aide neuve
organisme: Région
description: Une aide.
categorie: region
type: subvention
conditions:
- id: depot
  text: Le dossier doit être déposé avant le commencement des travaux.
  kind: info
  effect: info
- id: orgue
  text: L'orgue doit être classé.
  kind: info
  effect: info
"""
    cases, panne = esp_mod.controler_aide("neuve", texte, esp=espace)
    assert panne is None
    assert [c.sorte for c in cases] == ["coherence:depot"]
    assert "user_fact/gate/etat_travaux" in cases[0].titre
    # Ré-extraction : seules les conditions neuves sont contrôlées.
    cases, _ = esp_mod.controler_aide("neuve", texte, seulement={"orgue"}, esp=espace)
    assert cases == []


AIDE_INFO_ET_GATE = """\
slug: neuve
nom: Aide neuve
organisme: Région
description: Une aide.
categorie: region
type: subvention
conditions:
- id: depot
  text: Le dossier doit être déposé avant le commencement des travaux.
  kind: info
  effect: info
- id: commune
  text: La commune doit compter moins de 2 000 habitants.
  kind: user_fact
  fact: commune_moins_2000
  predicate: {eq: true}
"""


def _catalogue_mixte() -> list[co.Ligne]:
    """Quatre aides où « travaux non commencés » est un gate, quatre où « commune » est info."""
    commune = {"text": "La commune doit compter moins de 5 000 habitants.", "kind": "info"}
    return [_ligne(f"aide-{k}", 0, **GATE) for k in range(4)] + [
        _ligne(f"autre-{k}", 0, **commune) for k in range(4)
    ]


def test_le_lint_impose_la_famille_quand_elle_ajoute_un_gate(tmp_path: Path) -> None:
    espace = _espace(tmp_path, _catalogue_mixte(), FauxClient(MEME))
    erreurs, panne = esp_mod.alignements("neuve", AIDE_INFO_ET_GATE, esp=espace)
    assert panne is None
    # `depot` est en info quand sa famille pose le gate : bloquant. `commune`
    # pose un gate que sa famille laisse en info : il le garde.
    assert len(erreurs) == 1
    assert "depot" in erreurs[0] and "user_fact/gate/etat_travaux" in erreurs[0]


def test_un_gate_que_la_famille_n_a_pas_ne_fait_pas_de_case(tmp_path: Path) -> None:
    espace = _espace(tmp_path, _catalogue_mixte(), FauxClient(MEME))
    cases, _ = esp_mod.controler_aide("neuve", AIDE_INFO_ET_GATE, esp=espace)
    assert [c.sorte for c in cases] == ["coherence:depot"]


def test_en_mode_case_le_lint_n_impose_rien(tmp_path: Path) -> None:
    espace = _espace(tmp_path, _catalogue_mixte(), FauxClient(MEME))
    espace.reglages = dataclasses.replace(espace.reglages, typage_famille="case")
    assert esp_mod.alignements("neuve", AIDE_INFO_ET_GATE, esp=espace) == ([], None)
    cases, _ = esp_mod.controler_aide("neuve", AIDE_INFO_ET_GATE, esp=espace)
    assert sorted(c.sorte for c in cases) == ["coherence:commune", "coherence:depot"]


def test_le_lint_n_impose_rien_quand_l_espace_est_coupe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONUMIA_ESPACE", "0")
    assert esp_mod.alignements("neuve", AIDE_INFO_ET_GATE) == ([], None)


def test_une_condition_conforme_a_sa_famille_ne_dit_rien(tmp_path: Path) -> None:
    catalogue = [_ligne(f"aide-{k}", 0, **GATE) for k in range(4)]
    espace = _espace(tmp_path, catalogue, FauxClient(MEME))
    f = espace.famille(_ligne("neuve", 0, **GATE))
    assert f.dominante is not None and not esp_mod.ecart(_ligne("neuve", 0, **GATE), f)


def test_sans_confirmation_de_jev_pas_de_famille(tmp_path: Path) -> None:
    catalogue = [_ligne(f"aide-{k}", 0, **GATE) for k in range(4)]
    theme = {co.MEME: 0.3, co.VOISIN: 0.6, co.AUTRE: 0.1}
    espace = _espace(tmp_path, catalogue, FauxClient(theme))
    f = espace.famille(_ligne("neuve", 0, **INFO))
    assert f.voisines and f.dominante is None


def test_l_outil_de_l_agent_nomme_la_famille(tmp_path: Path) -> None:
    catalogue = [_ligne(f"aide-{k}", 0, **GATE) for k in range(4)]
    espace = _espace(tmp_path, catalogue, FauxClient(MEME))
    sortie = esp_mod.voisines_pour(INFO["text"], "neuve", "Aide neuve", espace)
    assert sortie.startswith("FAMILLE : `user_fact/gate/etat_travaux`")
    assert "aide-0#c0" in sortie


def test_l_outil_se_tait_quand_l_espace_est_coupe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONUMIA_ESPACE", "0")
    assert "désactivé" in esp_mod.voisines_pour("x", "s", "n")
    assert esp_mod.controler_aide("s", "slug: s") == ([], None)


# ------------------------------------------------------------------ étape de la semaine


def test_un_ecart_accepte_ou_repondu_ne_revient_pas(tmp_path: Path) -> None:
    catalogue = [_ligne(f"aide-{k}", 0, **GATE) for k in range(4)] + [_ligne("zz-info", 0, **INFO)]
    espace = _espace(tmp_path, catalogue, FauxClient(MEME))
    b = esp_mod.stock(espace, set(), lambda *_: False)
    assert [c.objet for c in b.cases] == ["a:zz-info"]
    case = b.cases[0]

    accepte = esp_mod.Accepte("zz-info#c0", "info/info", "user_fact/gate/etat_travaux")
    assert esp_mod.stock(espace, {accepte}, lambda *_: False).cases == []
    repondu = esp_mod.stock(
        espace, set(), lambda s, o, e: (s, o, e) == (case.sorte, case.objet, case.etat)
    )
    assert repondu.cases == []


def test_au_stock_un_gate_que_la_famille_n_a_pas_ne_fait_pas_de_case(tmp_path: Path) -> None:
    catalogue = [_ligne(f"aide-{k}", 0, **INFO) for k in range(4)] + [_ligne("zz-gate", 0, **GATE)]
    espace = _espace(tmp_path, catalogue, FauxClient(MEME))
    assert esp_mod.stock(espace, set(), lambda *_: False).cases == []
    espace.reglages = dataclasses.replace(espace.reglages, typage_famille="case")
    assert [c.objet for c in esp_mod.stock(espace, set(), lambda *_: False).cases] == ["a:zz-gate"]


# ------------------------------------------------------------------ famille d'un fait


ONTOLOGIE = {
    "etat_travaux": FactDef.model_validate(
        {
            "type": "enum",
            "scope": "projet",
            "question": "Votre projet comporte-t-il des travaux, et où en êtes-vous ?",
            "options": [{"id": "non_commences", "label": "Pas commencés"}],
        }
    ),
    "orgue_present": FactDef.model_validate(
        {"type": "boolean", "scope": "monument", "question": "Le monument abrite-t-il un orgue ?"}
    ),
}
DEVIS = FactDef.model_validate(
    {"type": "boolean", "scope": "projet", "question": "Avez-vous signé un devis de travaux ?"}
)


def test_un_fait_propose_rejoint_le_fait_que_jev_choisit(tmp_path: Path) -> None:
    client = FauxClient({"c1": 0.9, "c2": 0.05, esp_mod.AUCUN: 0.05})
    juge = co.Juge(tmp_path / "j.jsonl", client=client)  # type: ignore[arg-type]
    f = esp_mod.famille_du_fait(
        "devis_signes",
        DEVIS,
        {**ONTOLOGIE, "devis_signes": DEVIS},
        plongeur=FauxPlongeur(),  # type: ignore[arg-type]
        juge=juge,
        reglages=esp_mod.Reglages(),
    )
    assert f is not None and f.cle == f.candidats[0] and f.proba == 0.9


def test_aucun_ne_rattache_rien(tmp_path: Path) -> None:
    client = FauxClient({"c1": 0.2, esp_mod.AUCUN: 0.8})
    juge = co.Juge(tmp_path / "j.jsonl", client=client)  # type: ignore[arg-type]
    f = esp_mod.famille_du_fait(
        "devis_signes",
        DEVIS,
        ONTOLOGIE,
        plongeur=FauxPlongeur(),  # type: ignore[arg-type]
        juge=juge,
        reglages=esp_mod.Reglages(),
    )
    assert f is None


@pytest.mark.parametrize("en_case", [True, False])
def test_les_faits_en_attente_rattaches_ne_vont_en_case_qu_en_mode_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, en_case: bool
) -> None:
    monkeypatch.setattr("catalogue.registre.faits_neufs_en_case", lambda: en_case)
    client = FauxClient({"c1": 0.9, "c2": 0.05, esp_mod.AUCUN: 0.05})
    espace = _espace(tmp_path, [], client)
    b = esp_mod.faits_en_attente({"devis_signes": DEVIS}, ONTOLOGIE, lambda *_: False, espace)
    assert len(b.cases) == (1 if en_case else 0)
    assert b.lignes == ["1 fait(s) en attente, 1 rattaché(s) à un fait existant."]


def test_proposer_un_fait_de_la_famille_exige_de_lire_ce_fait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ingestion import faits
    from ingestion.atelier import atelier_redirige, restaurer_sources

    pending = tmp_path / "facts_pending.yaml"
    pending.write_text("", encoding="utf-8")
    atelier = dataclasses.replace(atelier_redirige("ex-aide", tmp_path), pending_path=pending)
    famille = esp_mod.FamilleFait("etat_travaux", 0.97, ["etat_travaux", "orgue_present"])
    monkeypatch.setattr(faits, "_famille", lambda *_: (famille, False))
    definition = "type: boolean\nscope: projet\nquestion: Avez-vous signé un devis de travaux ?\n"
    justification = "x" * 90
    try:
        refus = faits.proposer(atelier, ONTOLOGIE, "devis_signes", definition, justification)
        assert refus.startswith("ERREUR") and "`etat_travaux`" in refus
        assert pending.read_text(encoding="utf-8") == ""
        ok = faits.proposer(
            atelier,
            ONTOLOGIE,
            "devis_signes",
            definition,
            justification,
            detailles=("etat_travaux",),
        )
        assert not ok.startswith("ERREUR")
        assert "Famille selon Jev : etat_travaux (0.97)" in pending.read_text(encoding="utf-8")
    finally:
        restaurer_sources()


# ------------------------------------------------------------------ registre


def test_les_empreintes_du_registre_sont_celles_du_code() -> None:
    r = charger()
    assert r.decisions["C1-coherence"].empreintes["questions"] == co.EMPREINTE_QUESTIONS
    assert (
        r.decisions["F3-famille-fait"].empreintes["questions"] == esp_mod.EMPREINTE_QUESTIONS_FAIT
    )
    assert (
        empreinte(json.dumps(co.QUESTIONS, ensure_ascii=False, sort_keys=True))
        == co.EMPREINTE_QUESTIONS
    )
    reglages = esp_mod.Reglages.depuis(r)
    assert (reglages.meme, reglages.cosinus) == (0.8, 0.75)
