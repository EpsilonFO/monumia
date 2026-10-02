"""Reprise du loader sur une connexion HTTP/2 refermée par Supabase.

Vu au déploiement du 2026-10-02 : `RemoteProtocolError: Server disconnected`
à 50 puis à 350 aides sur la beta, et le sync entier tombait.
"""

import sys
from pathlib import Path
from unittest import mock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import load_aides_yaml as loader


def _coupures(n: int, puis: str = "ok"):
    """Une action qui échoue `n` fois en transport, puis rend `puis`."""
    appels = {"n": 0}

    def action() -> str:
        appels["n"] += 1
        if appels["n"] <= n:
            raise httpx.RemoteProtocolError("Server disconnected")
        return puis

    return action, appels


def test_rejoue_apres_une_coupure() -> None:
    action, appels = _coupures(2)
    with mock.patch.object(loader.time, "sleep") as dormir:
        assert loader._reprendre(action, "test") == "ok"
    assert appels["n"] == 3
    assert [c.args[0] for c in dormir.call_args_list] == [1, 2]


def test_abandonne_apres_le_dernier_essai() -> None:
    action, appels = _coupures(loader.ESSAIS)
    with mock.patch.object(loader.time, "sleep"), pytest.raises(httpx.RemoteProtocolError):
        loader._reprendre(action, "test")
    assert appels["n"] == loader.ESSAIS


def test_ne_rejoue_pas_une_erreur_applicative() -> None:
    """Une erreur de la base (contrainte, droits) n'est pas une coupure : on ne rejoue pas."""
    appels = {"n": 0}

    def action() -> None:
        appels["n"] += 1
        raise ValueError("violation de contrainte")

    with mock.patch.object(loader.time, "sleep"), pytest.raises(ValueError):
        loader._reprendre(action, "test")
    assert appels["n"] == 1
