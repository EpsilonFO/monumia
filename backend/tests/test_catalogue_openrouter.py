"""Le client OpenRouter du paquet `catalogue` : coût facturé, modèle servi, pannes classées."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from catalogue.openrouter import Client, Panne


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
