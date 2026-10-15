"""Les aides fermées : sorties du catalogue alors qu'un utilisateur y travaillait.

Qui avait un dossier ou un suivi reçoit une explication (410, dossier annoté)
au lieu d'« Aide introuvable », puis ne voit plus le dossier une fois le
panneau lu. Une demande déjà déposée reste toujours visible. Les autres ne
voient rien : l'aide a simplement quitté le diagnostic.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from services import aides_fermees as af

SLUG = "tt-restauration"


class _Resp:
    def __init__(self, data: Any) -> None:
        self.data = data


class _Query:
    def __init__(self, base: _FakeSupabase, nom: str) -> None:
        self.base, self.nom = base, nom
        self.rows = list(base.tables.get(nom, []))
        self.single = False
        self.maj: dict | None = None

    def select(self, *_a: Any, **_k: Any) -> _Query:
        return self

    def eq(self, colonne: str, valeur: Any) -> _Query:
        self.rows = [r for r in self.rows if r.get(colonne) == valeur]
        return self

    def in_(self, colonne: str, valeurs: list) -> _Query:
        self.rows = [r for r in self.rows if r.get(colonne) in valeurs]
        return self

    def limit(self, n: int) -> _Query:
        self.rows = self.rows[:n]
        return self

    def maybe_single(self) -> _Query:
        self.single = True
        return self

    def update(self, valeurs: dict) -> _Query:
        self.maj = valeurs
        return self

    def execute(self) -> _Resp:
        self.base.lectures.append(self.nom)
        if self.maj is not None:
            for r in self.rows:
                r.update(self.maj)
            return _Resp(self.rows)
        if self.single:
            return _Resp(self.rows[0] if self.rows else None)
        return _Resp(self.rows)


class _FakeSupabase:
    def __init__(self, **tables: list[dict]) -> None:
        self.tables = tables
        self.lectures: list[str] = []

    def table(self, nom: str) -> _Query:
        return _Query(self, nom)


@pytest.fixture
def retirees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dossier = tmp_path / "retirees"
    dossier.mkdir()
    (dossier / f"{SLUG}.yaml").write_text(
        "# Retirée du catalogue le 2026-10-15 : absente du guide tt depuis 2 listings, page HTTP 404\n"
        f"slug: {SLUG}\nnom: Restauration du patrimoine rural non protégé\nnom_court: Patrimoine rural\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(af, "RETIREES", dossier)
    return dossier


def _dossier(statut: str = "en_cours", aide: str = SLUG, projet: str = "p1") -> dict:
    return {"id": f"d-{aide}-{projet}", "projet_id": projet, "aide_id": aide, "statut": statut}


def test_le_dossier_des_retirees_donne_nom_et_date(retirees: Path) -> None:
    (f,) = af.fermees().values()
    assert (f.slug, f.nom, f.fermee_le) == (SLUG, "Patrimoine rural", "2026-10-15")


def test_sans_aide_fermee_aucune_requete(retirees: Path) -> None:
    sb = _FakeSupabase()
    dossiers = [_dossier(aide="autre")]
    assert af.appliquer_aux_dossiers(sb, "u1", dossiers) is dossiers
    assert sb.lectures == []


def test_le_dossier_est_annote_tant_que_le_panneau_n_est_pas_lu(retirees: Path) -> None:
    sb = _FakeSupabase(users=[{"id": "u1", "aides_fermees_vues": {}}])
    (d,) = af.appliquer_aux_dossiers(sb, "u1", [_dossier()])
    assert d["aide_fermee"] == {
        "nom": "Patrimoine rural",
        "fermeeLe": "2026-10-15",
        "deposee": False,
    }


def test_une_fois_le_panneau_lu_le_dossier_disparait(retirees: Path) -> None:
    sb = _FakeSupabase(users=[{"id": "u1", "aides_fermees_vues": {}}])
    af.marquer_vue(sb, "u1", SLUG, af.datetime(2026, 10, 16))
    assert af.appliquer_aux_dossiers(sb, "u1", [_dossier(), _dossier(aide="autre")]) == [
        _dossier(aide="autre")
    ]
    # Pour un autre membre de l'équipe, qui n'a pas lu le panneau, il reste.
    sb.tables["users"].append({"id": "u2", "aides_fermees_vues": {}})
    assert len(af.appliquer_aux_dossiers(sb, "u2", [_dossier()])) == 1


@pytest.mark.parametrize(
    ("statut_dossier", "suivis"),
    [("soumis", []), ("en_cours", [{"projet_id": "p1", "aide_id": SLUG, "statut": "accorde"}])],
)
def test_une_demande_deposee_reste_visible(
    retirees: Path, statut_dossier: str, suivis: list[dict]
) -> None:
    sb = _FakeSupabase(users=[{"id": "u1", "aides_fermees_vues": {SLUG: "x"}}], aide_suivis=suivis)
    (d,) = af.appliquer_aux_dossiers(sb, "u1", [_dossier(statut_dossier)])
    assert d["aide_fermee"]["deposee"] is True


def test_les_suivis_suivent_le_meme_sort(retirees: Path) -> None:
    sb = _FakeSupabase(users=[{"id": "u1", "aides_fermees_vues": {SLUG: "x"}}])
    suivis = [
        {"projet_id": "p1", "aide_id": SLUG, "statut": "en_preparation"},
        {"projet_id": "p2", "aide_id": SLUG, "statut": "depose"},
        {"projet_id": "p1", "aide_id": "autre", "statut": "a_faire"},
    ]
    assert [s["projet_id"] + s["aide_id"] for s in af.filtrer_suivis(sb, "u1", suivis)] == [
        "p2" + SLUG,
        "p1autre",
    ]


def test_une_lecture_impossible_ne_masque_rien(retirees: Path) -> None:
    class Panne(_FakeSupabase):
        def table(self, nom: str) -> _Query:
            if nom == "users":
                raise RuntimeError("colonne absente")
            return super().table(nom)

    assert len(af.appliquer_aux_dossiers(Panne(), "u1", [_dossier()])) == 1


def test_get_aide_explique_la_fermeture_a_qui_y_travaillait(
    retirees: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from routers import aides as r

    monkeypatch.setattr(r, "load_all_aides", lambda: {})
    monkeypatch.setattr(
        r.catalogue_admin, "catalogue_effectif", lambda sb: SimpleNamespace(retirees=set())
    )
    sb = _FakeSupabase(
        dossiers=[{"id": "d1", "user_id": "u1", "aide_id": SLUG, "statut": "en_cours"}]
    )
    with pytest.raises(HTTPException) as engage:
        r.get_aide(SLUG, user_id="u1", supabase=sb)  # type: ignore[arg-type]
    assert engage.value.status_code == 410
    assert engage.value.detail["code"] == "aide_fermee"  # type: ignore[index]
    with pytest.raises(HTTPException) as inconnu:
        r.get_aide(SLUG, user_id="u2", supabase=sb)  # type: ignore[arg-type]
    assert inconnu.value.status_code == 404


def test_marquer_vue_refuse_une_aide_qui_n_est_pas_fermee(retirees: Path) -> None:
    from routers import aides as r

    sb = _FakeSupabase(users=[{"id": "u1", "aides_fermees_vues": {}}])
    r.marquer_aide_fermee_vue(SLUG, user_id="u1", supabase=sb)  # type: ignore[arg-type]
    assert SLUG in sb.tables["users"][0]["aides_fermees_vues"]
    with pytest.raises(HTTPException):
        r.marquer_aide_fermee_vue("inconnue", user_id="u1", supabase=sb)  # type: ignore[arg-type]
