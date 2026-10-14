"""Plongements et cohérence du typage : cache, voisins, familles, impact."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import httpx
import numpy as np
import pytest

from aides_schema import Condition
from catalogue.coherence import Ligne, grouper, impact, signaler, voisinage
from catalogue.openrouter import Client
from catalogue.plongements import Plongeur, plus_proches


def _client(appels: list[list[str]]) -> Client:
    def repondre(requete: httpx.Request) -> httpx.Response:
        lot = json.loads(requete.content)["input"]
        appels.append(lot)
        return httpx.Response(
            200,
            json={
                "model": "Qwen/Qwen3-Embedding-8B",
                "data": [
                    {"index": i, "embedding": [float(len(t)), 1.0, 0.0]} for i, t in enumerate(lot)
                ],
                "usage": {"cost": 1e-07},
            },
        )

    return Client("cle-de-test", transport=httpx.MockTransport(repondre))


def test_un_texte_deja_plonge_ne_se_repaye_pas(tmp_path: Path) -> None:
    appels: list[list[str]] = []
    cache = tmp_path / "plongements.sqlite"
    p = Plongeur(_client(appels), cache=cache)
    premiers = p.vecteurs(["ab", "abcd", "ab"])
    p.fermer()
    assert appels == [["ab", "abcd"]]  # un texte en double ne part qu'une fois
    assert premiers.shape == (3, 3)
    assert np.allclose(np.linalg.norm(premiers, axis=1), 1.0)
    assert np.allclose(premiers[0], premiers[2])

    # Une seconde instance relit le cache sans client du tout : une mesure
    # rejouée tourne hors ligne.
    relu = Plongeur(cache=cache).vecteurs(["abcd", "ab"])
    assert np.allclose(relu, premiers[[1, 0]], atol=1e-3)


def test_plus_proches_trie_du_plus_proche_au_plus_lointain() -> None:
    corpus = np.array([[1.0, 0.0], [0.0, 1.0], [0.7071, 0.7071]])
    rangs, scores = plus_proches(np.array([[1.0, 0.0]]), corpus, 2)
    assert rangs.tolist() == [[0, 2]]
    assert scores[0, 0] == pytest.approx(1.0)


def _ligne(slug: str, **condition: object) -> Ligne:
    return Ligne(slug, slug, Condition.model_validate({"id": "c", "text": "t", **condition}))


GATE = {"kind": "user_fact", "fact": "etat_travaux", "predicate": {"eq": "non_commences"}}
INFO = {"kind": "info"}


def test_une_condition_isolee_dans_son_voisinage_est_signalee() -> None:
    lignes = [_ligne("a", **INFO)] + [_ligne(f"v{k}", **GATE) for k in range(3)]
    jugements = {(0, k): {"meme_critere": 0.95} for k in (1, 2, 3)}
    signalements = signaler(lignes, voisinage(4, jugements, 0.9))
    assert [s.indice for s in signalements] == [0]
    s = signalements[0]
    assert s.attendu == ("user_fact", "gate", "etat_travaux")
    assert (s.predicat, s.part_predicat) == ({"eq": "non_commences"}, 1.0)
    (groupe,) = grouper(lignes, signalements)
    assert (groupe.impact, len(groupe.signalements)) == ("elimination", 1)


def test_pas_de_signalement_sous_le_seuil_ou_sans_assez_de_voisins() -> None:
    lignes = [_ligne("a", **INFO)] + [_ligne(f"v{k}", **GATE) for k in range(3)]
    sous_le_seuil = {(0, k): {"meme_critere": 0.85} for k in (1, 2, 3)}
    assert signaler(lignes, voisinage(4, sous_le_seuil, 0.9)) == []
    deux_voisins = {(0, k): {"meme_critere": 0.95} for k in (1, 2)}
    assert signaler(lignes, voisinage(4, deux_voisins, 0.9)) == []


def test_pas_de_signalement_sans_typage_dominant() -> None:
    lignes = [_ligne("a", **INFO), _ligne("b", **GATE), _ligne("c", **GATE)]
    lignes += [
        _ligne("d", kind="manual_check", effect="info"),
        _ligne("e", kind="manual_check", effect="info"),
    ]
    jugements = {(0, k): {"meme_critere": 0.95} for k in (1, 2, 3, 4)}
    # 50 % gate, 50 % manual_check : aucun typage n'atteint 60 %.
    assert [s.indice for s in signaler(lignes, voisinage(5, jugements, 0.9))] == []


@pytest.mark.parametrize(
    ("typages", "attendu"),
    [
        # Une moitié écarte, l'autre n'écarte personne : le cas le plus grave.
        ([("user_fact", "gate", "etat_travaux"), ("info", "info", None)], "elimination"),
        ([("auto", "gate", "monument.protection"), ("manual_check", "info", None)], "elimination"),
        # Tout pèse, mais sur deux faits différents : un doublon de faits probable.
        (
            [("user_fact", "gate", "etat_travaux"), ("user_fact", "gate", "depenses_engagees")],
            "fait",
        ),
        ([("info", "info", None), ("discretionary", "info", None)], "affichage"),
        (
            [
                ("user_fact", "gate", "budget_travaux_estime"),
                ("user_fact", "modulateur", "budget_travaux_estime"),
            ],
            "modulation",
        ),
    ],
)
def test_impact_d_une_famille(typages: list[tuple[str, str, str | None]], attendu: str) -> None:
    assert impact(Counter(typages)) == attendu


def test_les_deux_sens_d_un_desaccord_forment_un_seul_groupe() -> None:
    # 0 (info) est entourée de gates, 4 (gate) est entourée d'infos : une seule
    # question, le typage canonique du critère.
    lignes = [_ligne("a", **INFO)] + [_ligne(f"g{k}", **GATE) for k in range(4)]
    lignes += [_ligne(f"i{k}", **INFO) for k in range(3)]
    jugements = {(0, k): {"meme_critere": 0.95} for k in (1, 2, 3)}
    jugements |= {(4, k): {"meme_critere": 0.95} for k in (5, 6, 7)}
    groupes = grouper(lignes, signaler(lignes, voisinage(8, jugements, 0.9)))
    assert len(groupes) == 1
    assert sorted(s.indice for s in groupes[0].signalements) == [0, 4]


def test_une_info_couverte_par_les_filtres_de_son_aide_n_est_pas_signalee() -> None:
    protege = {"kind": "auto", "field": "monument.protection", "predicate": {"in": ["classe"]}}
    info = Ligne("a", "a", Condition.model_validate({"id": "c", "text": "t", **INFO}))
    couverte = Ligne(
        "b",
        "b",
        Condition.model_validate({"id": "c", "text": "t", **INFO}),
        frozenset({"monument.protection"}),
    )
    voisines = [_ligne(f"v{k}", **protege) for k in range(3)]
    jugements = {(0, k): {"meme_critere": 0.95} for k in (1, 2, 3)}
    assert len(signaler([info, *voisines], voisinage(4, jugements, 0.9))) == 1
    assert signaler([couverte, *voisines], voisinage(4, jugements, 0.9)) == []
    # Dans l'autre sens : un gate auto entouré d'infos couvertes est cohérent.
    autour = [couverte, couverte, couverte]
    jugements = {(0, k): {"meme_critere": 0.95} for k in (1, 2, 3)}
    assert signaler([_ligne("g", **protege), *autour], voisinage(4, jugements, 0.9)) == []


def test_une_info_dont_l_aide_porte_deja_le_gate_ailleurs_n_est_pas_signalee() -> None:
    redite = Ligne(
        "a",
        "a",
        Condition.model_validate({"id": "c", "text": "t", **INFO}),
        ailleurs=frozenset({("user_fact", "gate", "etat_travaux")}),
    )
    voisines = [_ligne(f"v{k}", **GATE) for k in range(3)]
    jugements = {(0, k): {"meme_critere": 0.95} for k in (1, 2, 3)}
    assert signaler([redite, *voisines], voisinage(4, jugements, 0.9)) == []
