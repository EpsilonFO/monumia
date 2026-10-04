"""Tests de POST /auth/refresh : seul un refus de Supabase rend 401 (le front
déconnecte alors) ; une panne rend 503, que le front réessaie sans toucher à la
session. Vu le 2026-10-04 : chaque déploiement déconnectait les comptes actifs."""

from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException, Response
from postgrest.exceptions import APIError
from supabase import AuthApiError
from supabase_auth.errors import AuthRetryableError

import routers.auth as auth
from routers.auth import REFRESH_COOKIE, refresh


class _Anon:
    def __init__(self, comportement):
        self._comportement = comportement
        self.auth = self

    def refresh_session(self, token):
        if isinstance(self._comportement, Exception):
            raise self._comportement
        return self._comportement


def _requete(token="rt-ancien"):
    return SimpleNamespace(cookies={REFRESH_COOKIE: token})


def _session_ok():
    session = SimpleNamespace(
        access_token="at-neuf",
        refresh_token="rt-neuf",
        user=SimpleNamespace(id="user-1"),
    )
    return SimpleNamespace(session=session, user=session.user)


def _appeler(anon):
    return refresh(_requete(), Response(), None, anon, supabase=None)  # type: ignore[arg-type]


@pytest.mark.parametrize("status", [400, 401, 403])
def test_jeton_refuse_par_supabase_rend_401(status):
    erreur = AuthApiError("Invalid Refresh Token", status, "refresh_token_not_found")
    with pytest.raises(HTTPException) as exc:
        _appeler(_Anon(erreur))
    assert exc.value.status_code == 401


@pytest.mark.parametrize(
    "erreur",
    [
        AuthRetryableError("Bad Gateway", 502),
        AuthApiError("Internal error", 500, None),
        AuthApiError("Too many requests", 429, "over_request_rate_limit"),
        httpx.ConnectError("Connection refused"),
        RuntimeError("boom"),
    ],
)
def test_panne_de_supabase_rend_503(erreur):
    with pytest.raises(HTTPException) as exc:
        _appeler(_Anon(erreur))
    assert exc.value.status_code == 503


def test_profil_illisible_ne_perd_pas_le_jeton_tourne(monkeypatch):
    def _profil_en_panne(*_):
        raise RuntimeError("base injoignable")

    monkeypatch.setattr(auth, "_get_profile", _profil_en_panne)
    response = Response()
    corps = refresh(_requete(), response, None, _Anon(_session_ok()), supabase=None)  # type: ignore[arg-type]

    assert corps["access_token"] == "at-neuf"
    assert corps["user"] is None
    assert "rt-neuf" in response.headers["set-cookie"]


def test_profil_absent_reste_un_refus(monkeypatch):
    """Pas de session applicative sans ligne `users` : `.single()` sans ligne
    lève PGRST116, que la route ne doit pas absorber comme une panne."""

    def _sans_ligne(*_):
        raise APIError({"code": "PGRST116", "message": "0 rows"})

    monkeypatch.setattr(auth, "_get_profile", _sans_ligne)
    with pytest.raises(HTTPException) as exc:
        refresh(_requete(), Response(), None, _Anon(_session_ok()), supabase=None)  # type: ignore[arg-type]
    assert exc.value.status_code == 404


def test_succes_pose_le_nouveau_cookie(monkeypatch):
    monkeypatch.setattr(auth, "_get_profile", lambda *_: {"id": "user-1"})
    response = Response()
    corps = refresh(_requete(), response, None, _Anon(_session_ok()), supabase=None)  # type: ignore[arg-type]

    assert corps["user"] == {"id": "user-1"}
    assert "rt-neuf" in response.headers["set-cookie"]
