"""Le run hebdomadaire (incrément I3) : pré-vol, verrou, copie et recopie, étapes, banc d'étiquetage.

Aucun réseau ni modèle : le relevé de la clé est simulé, et le dépôt est un
petit dépôt fabriqué dans un dossier temporaire.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from catalogue import banc, calibrer, semaine
from catalogue.journal import Evenement, Journal
from catalogue.registre import Registre, charger


def _tout_a_l_ancienne() -> Registre:
    """Le registre livré, toutes les opérations laissées à l'ancienne chaîne."""
    reg = charger()
    return reg.model_copy(update={"proprietaires": dict.fromkeys(reg.proprietaires, "ancienne")})


# ------------------------------------------------------------------ pré-vol


def _cle(reste: float | None, expire: dt.datetime | None = None) -> Any:
    fin = expire or dt.datetime.now(dt.UTC) + dt.timedelta(days=30)
    return lambda: {"usage": 1.0, "limit_remaining": reste, "expires_at": fin.isoformat()}


def test_une_cle_sous_le_plafond_du_run_arrete_au_pre_vol() -> None:
    echecs, _ = semaine.cle_openrouter(18, 12, _cle(10.0))
    assert [e.code for e in echecs] == [4]


def test_une_cle_qui_expire_pendant_le_run_arrete_au_pre_vol() -> None:
    bientot = dt.datetime.now(dt.UTC) + dt.timedelta(hours=2)
    echecs, _ = semaine.cle_openrouter(18, 12, _cle(100.0, bientot))
    assert [e.code for e in echecs] == [4]


def test_un_releve_impossible_n_est_pas_un_feu_vert() -> None:
    def panne() -> dict[str, Any]:
        raise OSError("réseau")

    echecs, _ = semaine.cle_openrouter(18, 12, panne)
    assert [e.code for e in echecs] == [4]


def test_une_cle_sans_plafond_passe_avec_une_note() -> None:
    echecs, notes = semaine.cle_openrouter(18, 12, _cle(None))
    assert echecs == [] and any("pas de plafond" in n for n in notes)


# ------------------------------------------------------------------ copie et recopie


def _depot(tmp: Path) -> Path:
    racine = tmp / "depot"
    (racine / "backend" / "data" / "aides").mkdir(parents=True)
    (racine / "backend" / "data" / "reviews").mkdir(parents=True)
    (racine / "backend" / ".venv").mkdir()
    (racine / "backend" / "data" / "aides" / "a.yaml").write_text("slug: a\n", encoding="utf-8")
    (racine / "backend" / "data" / "veille-state.yaml").write_text("{}\n", encoding="utf-8")
    return racine


def test_le_verrou_ne_laisse_passer_qu_un_run(tmp_path: Path) -> None:
    racine = _depot(tmp_path)
    with semaine.verrou_run(racine) as premier, semaine.verrou_run(racine) as second:
        assert premier is True and second is False


def test_la_recopie_rend_les_fichiers_changes_dans_la_copie(tmp_path: Path) -> None:
    racine = _depot(tmp_path)
    depart = semaine.etat_fichiers(racine)
    copie = tmp_path / "copie"
    semaine.cloner(racine, copie)
    assert not (copie / "backend" / ".venv").exists()
    depart_copie = semaine.etat_fichiers(copie)
    (copie / "backend" / "data" / "aides" / "a.yaml").write_text(
        "slug: a\nnom: A\n", encoding="utf-8"
    )
    (copie / "backend" / "data" / "aides" / "b.yaml").write_text("slug: b\n", encoding="utf-8")
    recopies, conflits = semaine.recopier(copie, racine, depart, depart_copie)
    assert conflits == []
    assert recopies == ["backend/data/aides/a.yaml", "backend/data/aides/b.yaml"]
    assert "nom: A" in (racine / "backend" / "data" / "aides" / "a.yaml").read_text(
        encoding="utf-8"
    )


def test_un_original_modifie_pendant_le_run_bloque_toute_la_recopie(tmp_path: Path) -> None:
    racine = _depot(tmp_path)
    depart = semaine.etat_fichiers(racine)
    copie = tmp_path / "copie"
    semaine.cloner(racine, copie)
    depart_copie = semaine.etat_fichiers(copie)
    (copie / "backend" / "data" / "aides" / "a.yaml").write_text(
        "slug: a\nnom: A\n", encoding="utf-8"
    )
    (copie / "backend" / "data" / "veille-state.yaml").write_text("a: 1\n", encoding="utf-8")
    # Félix committe pendant le run : le fichier revient à une autre version.
    (racine / "backend" / "data" / "aides" / "a.yaml").write_text(
        "slug: a\n# commit\n", encoding="utf-8"
    )
    recopies, conflits = semaine.recopier(copie, racine, depart, depart_copie)
    assert recopies == [] and conflits == ["backend/data/aides/a.yaml"]
    assert (racine / "backend" / "data" / "veille-state.yaml").read_text(encoding="utf-8") == "{}\n"


# ------------------------------------------------------------------ run


def test_un_run_sans_etape_ecrit_son_rapport_et_sort_en_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    racine = _depot(tmp_path)
    monkeypatch.setattr(semaine, "prevol", lambda reg, **_: semaine.Prevol(notes=["clé : ok"]))
    monkeypatch.setattr(semaine, "SECOURS", tmp_path / "secours")
    monkeypatch.setattr(semaine, "notifier", lambda code, chemin: None)
    monkeypatch.setattr(semaine, "charger", _tout_a_l_ancienne)
    code = semaine.semaine(
        racine, journal=tmp_path / "journal", copies=tmp_path / "copies", jour=dt.date(2026, 10, 12)
    )
    assert code == 0
    rapport = (racine / "backend" / "data" / "reviews" / "2026-10-12-semaine.md").read_text(
        encoding="utf-8"
    )
    assert "Run fini" in rapport and "aucune" in rapport


def test_un_pre_vol_rate_n_appelle_rien_et_le_dit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    racine = _depot(tmp_path)
    monkeypatch.setattr(
        semaine, "prevol", lambda reg, **_: semaine.Prevol([semaine.Echec(6, "pdftotext absent")])
    )
    monkeypatch.setattr(semaine, "notifier", lambda code, chemin: None)
    monkeypatch.setattr(
        semaine, "cloner", lambda *a: pytest.fail("aucune copie après un pré-vol raté")
    )
    code = semaine.semaine(
        racine, journal=tmp_path / "j", copies=tmp_path / "c", jour=dt.date(2026, 10, 12)
    )
    assert code == 6
    rapport = (racine / "backend" / "data" / "reviews" / "2026-10-12-semaine.md").read_text(
        encoding="utf-8"
    )
    assert "pdftotext absent" in rapport


def test_les_etapes_suivent_le_registre(tmp_path: Path) -> None:
    reg = _tout_a_l_ancienne()
    assert semaine.etapes(reg, tmp_path, tmp_path) == []
    reprise = reg.model_copy(update={"proprietaires": {**reg.proprietaires, "veille": "nouvelle"}})
    (veille,) = semaine.etapes(reprise, tmp_path / "j", tmp_path)
    assert veille.arguments[:3] == ["veille", "--journal", str(tmp_path / "j")]


def test_deux_semaines_de_suite_balayent_tous_les_territoires_une_fois(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import datetime as dt

    from prospection.territoires import charger_territoires

    reg = _tout_a_l_ancienne()
    reg = reg.model_copy(
        update={
            "proprietaires": {**reg.proprietaires, "prospection": "nouvelle"},
            "reglages": reg.reglages.model_copy(update={"rotation_territoires": 2}),
        }
    )

    def balayes(jour: dt.date) -> list[str]:
        class Jour(dt.date):
            @classmethod
            def today(cls) -> dt.date:  # type: ignore[override]
                return jour

        monkeypatch.setattr(semaine.dt, "date", Jour)
        return [e.nom.removeprefix("entree-") for e in semaine.etapes(reg, tmp_path, tmp_path)]

    lundi = dt.date(2026, 10, 19)
    une, deux = balayes(lundi), balayes(lundi + dt.timedelta(days=7))
    assert sorted(une + deux) == sorted(charger_territoires())
    assert balayes(lundi + dt.timedelta(days=14)) == une


# ------------------------------------------------------------------ banc d'étiquetage


def test_le_banc_exporte_la_zone_prudente_a_l_aveugle_et_relit_les_etiquettes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    (blobs / "e1").write_text(json.dumps({"diff": "+ une ligne"}), encoding="utf-8")
    j = Journal(tmp_path / "journal")
    j.ajouter_lot(
        [
            Evenement(
                "decision",
                "a:x",
                decision="V1-garde",
                t="2026-10-12T03:00:00+00:00",
                modele="typesafe/jev-1.13-20260917",
                issue="prudente",
                cle="k1",
                donnees={"p": 0.2, "etat_jev": "e1"},
            ),
            Evenement(
                "decision",
                "a:y",
                decision="V1-garde",
                t="2026-10-12T03:00:00+00:00",
                modele="typesafe/jev-1.13-20260917",
                issue="prudente",
                cle="k2",
                donnees={"p": 0.3, "etat_jev": "e1"},
            ),
            # La référence de y a avancé depuis : plus rien à juger.
            Evenement(
                "decision",
                "a:y",
                decision="base",
                t="2026-10-13T03:00:00+00:00",
                donnees={"cle_url": "u", "fichier": "f.md"},
            ),
        ]
    )
    assert banc.preparer(j, tmp_path / "lot", blobs) == 1
    cas = json.loads((tmp_path / "lot" / "cas.json").read_text(encoding="utf-8"))
    assert [c["cas"] for c in cas] == ["k1"] and "p" not in json.dumps(cas[0]["etat"])
    monkeypatch.setattr(calibrer, "ETALONS", tmp_path / "etalons")
    etiquettes = tmp_path / "etiquettes.json"
    etiquettes.write_text(json.dumps([{"cas": "k1", "etiquette": "touche"}]), encoding="utf-8")
    assert banc.lire(j, etiquettes, blobs) == 1
    assert banc.lire(j, etiquettes, blobs) == 0
    (e,) = calibrer.lire("V1-garde")
    assert (
        e.etiquette == 1
        and e.provenance == "claude-aveugle"
        and e.p == {"typesafe/jev-1.13-20260917": 0.2}
    )
    (sortie,) = [e for e in j.lire() if e.decision == "V1-etiquette"]
    assert sortie.objet == "a:x" and sortie.issue == "touche" and sortie.donnees["garde"] == "k1"


def test_le_registre_refuse_une_prospection_et_une_ingestion_separees() -> None:
    from catalogue.registre import Registre

    brut = _tout_a_l_ancienne().model_dump()
    brut["proprietaires"] = {**brut["proprietaires"], "prospection": "nouvelle"}
    with pytest.raises(ValueError, match="même chaîne"):
        Registre.model_validate(brut)
