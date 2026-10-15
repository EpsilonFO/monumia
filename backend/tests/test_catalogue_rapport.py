"""Le rapport de la semaine : ce qui attend une réponse d'abord, le reste replié et jamais répété."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from catalogue import cases
from catalogue.cases import Case
from catalogue.rapport import Rapport

JOUR = dt.date(2026, 10, 15)
OPTIONS = {"garder": "garder la version en service", "voir": "vu"}


def _case(sorte: str, objet: str = "a:x", etat: str = "e1", titre: str | None = None) -> Case:
    return Case(sorte, objet, titre or sorte, etat, OPTIONS, ("contexte",))


def test_une_sorte_inconnue_est_a_trancher() -> None:
    assert _case("reextraction-valeur").a_trancher
    assert _case("sorte-neuve").a_trancher
    assert not _case("reextraction-typage").a_trancher
    assert not _case("veille-echeance").a_trancher


def test_le_rapport_separe_a_trancher_et_pour_information(tmp_path: Path) -> None:
    r = Rapport(JOUR, "run")
    r.cases = [_case("veille-echeance", titre="échéance"), _case("reextraction-valeur")]
    texte = r.ecrire(tmp_path).read_text(encoding="utf-8")
    assert texte.index("## À trancher (1)") < texte.index("## Pour information (1)")
    a_trancher = texte.split("## À trancher (1)")[1].split("## Pour information")[0]
    assert "reextraction-valeur" in a_trancher and "veille-echeance" not in a_trancher
    assert "<summary>1 nouvelle(s) : échéance 1</summary>" in texte


def test_une_case_pour_information_deja_posee_n_est_pas_repetee(tmp_path: Path) -> None:
    premier = Rapport(JOUR, "r1")
    premier.cases = [_case("veille-echeance"), _case("reextraction-valeur")]
    premier.ecrire(tmp_path)
    second = Rapport(JOUR + dt.timedelta(days=7), "r2")
    second.cases = [
        _case("veille-echeance"),
        _case("veille-echeance", objet="a:y"),
        _case("reextraction-valeur"),
    ]
    texte = second.ecrire(tmp_path).read_text(encoding="utf-8")
    # La case à trancher revient ; l'échéance déjà posée ne revient pas, la neuve oui.
    assert texte.count("<!-- case ") == 2
    assert "a:y" in texte and "1 autre(s), déjà posée(s)" in texte
    # Une réponse donnée dans le premier rapport est toujours lue.
    chemin = tmp_path / "2026-10-15-semaine.md"
    chemin.write_text(
        chemin.read_text(encoding="utf-8").replace("- [ ] `garder`", "- [x] `garder`", 1),
        encoding="utf-8",
    )
    reponses, _ = cases.lire(chemin.read_text(encoding="utf-8"))
    assert [r.sorte for r in reponses] == ["reextraction-valeur"]
