"""Le délai par hôte du téléchargeur vaut pour toute la machine (refonte, I1b)."""

from __future__ import annotations

import multiprocessing
import os
import sys
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline import web  # noqa: E402
from pipeline.web import Fetcheur, reinitialiser_delais  # noqa: E402


def _appels(dossier: str, hote: str, delai: float, n: int, file: multiprocessing.Queue) -> None:
    os.environ["MONUMIA_HOTES"] = dossier
    for _ in range(n):
        web._attendre_son_tour(hote, delai)
        file.put(time.time())


def test_deux_processus_respectent_le_delai_sur_le_meme_hote(tmp_path: Path) -> None:
    contexte = multiprocessing.get_context("spawn")
    file: multiprocessing.Queue = contexte.Queue()
    processus = [
        contexte.Process(target=_appels, args=(str(tmp_path), "guide.exemple.fr", 0.3, 3, file))
        for _ in range(2)
    ]
    for p in processus:
        p.start()
    for p in processus:
        p.join(timeout=60)
    instants = sorted(file.get(timeout=5) for _ in range(6))
    ecarts = [b - a for a, b in zip(instants, instants[1:], strict=False)]
    assert min(ecarts) >= 0.29


def test_deux_hotes_ne_s_attendent_pas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONUMIA_HOTES", str(tmp_path))
    reinitialiser_delais()
    debut = time.monotonic()
    web._attendre_son_tour("a.exemple.fr", 0.5)
    web._attendre_son_tour("b.exemple.fr", 0.5)
    assert time.monotonic() - debut < 0.4


def test_un_delai_nul_ne_touche_pas_au_disque(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MONUMIA_HOTES", str(tmp_path / "hotes"))
    web._attendre_son_tour("exemple.fr", 0.0)
    assert not (tmp_path / "hotes").exists()


def test_l_ancien_appelant_attend_toujours_entre_deux_requetes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le comportement d'avant, figé : un Fetcheur attend son délai entre deux pages du même hôte."""
    monkeypatch.setenv("MONUMIA_HOTES", str(tmp_path))
    reinitialiser_delais()
    instants: list[float] = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        instants.append(time.monotonic())
        return httpx.Response(
            200, text="<html><body>ok</body></html>", headers={"content-type": "text/html"}
        )

    with Fetcheur(transport=httpx.MockTransport(repondre), delai_s=0.2) as f:
        assert f.get("https://exemple.fr/a").ok
        assert f.get("https://exemple.fr/b").ok
    assert instants[1] - instants[0] >= 0.19
