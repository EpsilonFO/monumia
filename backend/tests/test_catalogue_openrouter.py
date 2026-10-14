"""Le client OpenRouter du paquet `catalogue` : coût facturé, modèle servi, pannes classées."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from catalogue.openrouter import Client, Panne, choix, noul


def _reponse(contenu: str = '{"ok": true}', **usage: object) -> dict[str, object]:
    return {
        "model": "z-ai/glm-5.3-flash",
        "provider": "Crusoe",
        "choices": [{"message": {"content": contenu}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 8,
            "cost": 0.0000222,
            "completion_tokens_details": {"reasoning_tokens": 3},
            **usage,
        },
    }


def _client(gestionnaire, tmp_path: Path | None = None, tentatives: int = 2) -> Client:
    return Client(
        "cle-de-test",
        transport=httpx.MockTransport(gestionnaire),
        tentatives=tentatives,
        journal=tmp_path / "appels.jsonl" if tmp_path else None,
    )


def test_le_cout_et_le_modele_viennent_de_la_reponse(tmp_path: Path) -> None:
    corps_envoyes = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        corps_envoyes.append(json.loads(requete.content))
        return httpx.Response(200, json=_reponse())

    client = _client(repondre, tmp_path)
    r = client.completer(
        "z-ai/glm-5.3-flash", [{"role": "user", "content": "x"}], schema={"type": "object"}
    )
    assert r.donnees == {"ok": True}
    assert r.cout_usd == pytest.approx(0.0000222)
    assert (r.modele_servi, r.fournisseur) == ("z-ai/glm-5.3-flash", "Crusoe")
    assert (r.jetons_entree, r.jetons_sortie, r.jetons_raisonnement) == (120, 8, 3)
    envoye = corps_envoyes[0]
    assert envoye["usage"] == {"include": True}
    assert envoye["response_format"]["json_schema"]["strict"] is True
    assert envoye["provider"] == {"require_parameters": True}
    trace = [json.loads(x) for x in (tmp_path / "appels.jsonl").read_text().splitlines()]
    assert trace[0]["cout_usd"] == pytest.approx(0.0000222)
    assert "panne" not in trace[0]


def test_credits_epuises_sans_relance() -> None:
    appels = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        appels.append(1)
        return httpx.Response(402, json={"error": "insufficient credits"})

    with pytest.raises(Panne) as exc:
        _client(repondre, tentatives=3).completer("m", [{"role": "user", "content": "x"}])
    assert exc.value.classe == "credits"
    assert len(appels) == 1


def test_une_erreur_transitoire_est_relancee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("catalogue.openrouter.time.sleep", lambda _s: None)
    etats = iter([503, 200])

    def repondre(requete: httpx.Request) -> httpx.Response:
        statut = next(etats)
        return httpx.Response(statut, json=_reponse() if statut == 200 else {"error": "down"})

    r = _client(repondre).completer("m", [{"role": "user", "content": "x"}])
    assert r.texte == '{"ok": true}'


def test_une_reponse_vide_est_une_panne_pas_un_non(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("catalogue.openrouter.time.sleep", lambda _s: None)

    def repondre(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_reponse(contenu=""))

    with pytest.raises(Panne) as exc:
        _client(repondre, tmp_path).completer("m", [{"role": "user", "content": "x"}])
    assert exc.value.classe == "reponse_vide"
    # Une réponse vide est facturée : le coût reste tracé avec la panne.
    trace = [json.loads(x) for x in (tmp_path / "appels.jsonl").read_text().splitlines()]
    assert all(t["panne"] == "reponse_vide" and t["cout_usd"] for t in trace)


def test_un_json_invalide_est_une_panne(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("catalogue.openrouter.time.sleep", lambda _s: None)

    def repondre(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_reponse(contenu="{pas du json"))

    with pytest.raises(Panne) as exc:
        _client(repondre).completer(
            "m", [{"role": "user", "content": "x"}], schema={"type": "object"}
        )
    assert exc.value.classe == "json_invalide"


def test_une_requete_refusee_ne_se_relance_pas() -> None:
    appels = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        appels.append(1)
        return httpx.Response(400, json={"error": "bad schema"})

    with pytest.raises(Panne) as exc:
        _client(repondre, tentatives=3).completer("m", [{"role": "user", "content": "x"}])
    assert exc.value.classe == "requete"
    assert len(appels) == 1


def test_sans_cle_le_client_refuse_de_demarrer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(Panne) as exc:
        Client(None)
    assert exc.value.classe == "cle"


# ----------------------------------------------------------------- décisions


def _decision(**reponses: object) -> dict[str, object]:
    return {
        "model": "typesafe/jev-1.13-20260917",
        "answers": reponses,
        "usage": {"input_tokens": 300, "cost": 0.0000126},
    }


def test_une_decision_rend_des_distributions_et_le_cout() -> None:
    def repondre(requete: httpx.Request) -> httpx.Response:
        assert requete.url.path == "/api/alpha/decisions"
        return httpx.Response(
            200,
            json=_decision(
                deposable={"type": "noul", "noul": 0.81},
                destinataire={
                    "type": "choice",
                    "choice": "proprietaire_gestionnaire",
                    "probabilities": {"proprietaire_gestionnaire": 0.7, "activite_tiers": 0.3},
                },
            ),
        )

    questions = {
        "deposable": noul("Déposable ?", "oui", "non"),
        "destinataire": choix("Qui ?", {"proprietaire_gestionnaire": "p", "activite_tiers": "t"}),
    }
    d = _client(repondre).decider("typesafe/jev-1.13", {"page": "x"}, questions)
    assert d.avis["deposable"].proba("true") == pytest.approx(0.81)
    assert d.avis["deposable"].proba("false") == pytest.approx(0.19)
    assert d.avis["destinataire"].choix == "proprietaire_gestionnaire"
    assert d.cout_usd == pytest.approx(0.0000126)
    assert d.modele_servi == "typesafe/jev-1.13-20260917"


@pytest.mark.parametrize(
    "reponse",
    [
        {"type": "noul"},
        {"type": "noul", "noul": None},
        {"type": "noul", "noul": 1.4},
        {"type": "choice", "choice": "a"},
        {"type": "choice", "probabilities": {}},
    ],
)
def test_une_reponse_de_jev_sans_probabilite_est_une_panne(
    reponse: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("catalogue.openrouter.time.sleep", lambda _s: None)

    def repondre(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_decision(q=reponse))

    with pytest.raises(Panne) as exc:
        _client(repondre).decider("m", "état", {"q": noul("?", "oui", "non")})
    assert exc.value.classe == "reponse_invalide"


def test_une_question_sans_reponse_est_une_panne(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("catalogue.openrouter.time.sleep", lambda _s: None)

    def repondre(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_decision(autre={"type": "noul", "noul": 0.5}))

    with pytest.raises(Panne) as exc:
        _client(repondre).decider("m", "état", {"q": noul("?", "oui", "non")})
    assert exc.value.classe == "reponse_invalide"


def test_un_modele_servi_hors_liste_est_refuse_sans_relance() -> None:
    appels = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        appels.append(1)
        return httpx.Response(200, json=_reponse())

    with pytest.raises(Panne) as exc:
        _client(repondre, tentatives=3).completer(
            "z-ai/glm-5.3-flash", [{"role": "user", "content": "x"}], acceptes={"autre/modele"}
        )
    assert exc.value.classe == "modele_substitue"
    assert len(appels) == 1


def test_un_delai_depasse_est_une_panne(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("catalogue.openrouter.time.sleep", lambda _s: None)

    def repondre(requete: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("trop long", request=requete)

    with pytest.raises(Panne) as exc:
        _client(repondre).decider("m", "état", {"q": noul("?", "oui", "non")}, delai_s=0.1)
    assert exc.value.classe == "delai"


def _plongements(*vecteurs: list[float], ordre: list[int] | None = None) -> dict[str, object]:
    rangs = ordre if ordre is not None else list(range(len(vecteurs)))
    return {
        "model": "Qwen/Qwen3-Embedding-8B",
        "data": [{"index": r, "embedding": vecteurs[r]} for r in rangs],
        "usage": {"prompt_tokens": 18, "cost": 1.8e-07},
    }


def test_des_plongements_rendent_un_vecteur_par_texte_dans_l_ordre_des_index() -> None:
    def repondre(requete: httpx.Request) -> httpx.Response:
        assert requete.url.path == "/api/v1/embeddings"
        assert json.loads(requete.content)["input"] == ["a", "b"]
        return httpx.Response(200, json=_plongements([1.0, 0.0], [0.0, 1.0], ordre=[1, 0]))

    p = _client(repondre).plonger(
        "qwen/qwen3-embedding-8b", ["a", "b"], acceptes=["Qwen/Qwen3-Embedding-8B"]
    )
    assert p.vecteurs == [[1.0, 0.0], [0.0, 1.0]]
    assert p.cout_usd == pytest.approx(1.8e-07)
    assert p.modele_servi == "Qwen/Qwen3-Embedding-8B"


@pytest.mark.parametrize(
    "reponse",
    [
        {"model": "Qwen/Qwen3-Embedding-8B", "data": [{"index": 0, "embedding": [1.0]}]},
        {"model": "Qwen/Qwen3-Embedding-8B", "data": [{"index": 0, "embedding": [1.0]}] * 2},
        _plongements([1.0], []),
    ],
    ids=["vecteur_manquant", "rang_en_double", "vecteur_vide"],
)
def test_un_plongement_incomplet_est_une_panne(
    monkeypatch: pytest.MonkeyPatch, reponse: dict[str, object]
) -> None:
    monkeypatch.setattr("catalogue.openrouter.time.sleep", lambda _s: None)
    client = _client(lambda _r: httpx.Response(200, json=reponse))
    with pytest.raises(Panne) as exc:
        client.plonger("qwen/qwen3-embedding-8b", ["a", "b"])
    assert exc.value.classe == "reponse_invalide"
