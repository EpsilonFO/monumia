"""La conversion de l'état ancien vers le journal (refonte, I1b)."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path
from typing import Any

from catalogue import convertir as cv
from catalogue.journal import Evenement, Journal

BACKEND = Path(__file__).resolve().parents[1]


# ------------------------------------------------ les fichiers en service


def test_la_file_et_le_manifeste_en_service_se_reprojettent_a_l_octet(tmp_path: Path) -> None:
    """Le journal (JSON) garde tout ce qu'il faut pour refaire les deux fichiers par leurs écrivains."""
    journal = Journal(tmp_path)
    for decision, chemin in (("file", cv.FILE), ("veille", cv.MANIFESTE)):
        courant = cv.lire_yaml((BACKEND.parent / chemin).read_bytes())
        journal.ajouter_lot(
            Evenement(
                "import",
                f"a:{k}",
                decision=decision,
                run="r1",
                auteur="import",
                donnees={"etat": v},
            )
            for k, v in courant.items()
        )
    evenements = list(journal.lire())
    assert cv.reprojeter_file(evenements) == (BACKEND.parent / cv.FILE).read_bytes()
    assert cv.reprojeter_manifeste(evenements) == (BACKEND.parent / cv.MANIFESTE).read_bytes()


# --------------------------------------------------------- règles pures


def test_la_provenance_d_un_motif_se_lit_a_sa_forme() -> None:
    p = cv.provenance_motif
    assert p({"statut": "ignore", "motif_ignore": "doublon d'URL de x"}) == "doublon_regle"
    assert p({"statut": "ignore", "motif_ignore": "test du destinataire : aide_personne"}) == (
        "requalification_llm"
    )
    assert p({"statut": "ignore", "motif_ignore": "hors périmètre à l'ingestion : y"}) == (
        "requalification_llm"
    )
    assert p({"statut": "ignore", "motif_ignore": "hors périmètre : non_dispositif"}) == (
        "lecture_llm"
    )
    assert p({"statut": "ignore", "motif_ignore": "tri humain du 2026-09-30 : z"}) == "lot_approuve"
    assert p({"statut": "ignore"}) == "sans_trace"
    assert p({"statut": "a_valider"}) is None


def test_la_regle_de_base_rouvre_ce_que_le_passage_n_a_pas_applique() -> None:
    r = cv.regle_de_base
    passage = {"checked_at": "2026-10-04"}
    assert r({**passage, "status": "escalade_ingestion"}, "2026-09-01") == (True, "escalade")
    assert r({**passage, "status": "maj_llm"}, "2026-09-01") == (True, "inchange")
    assert r({**passage, "status": "maj_llm", "maj": {"date": "2026-10-04"}}, None) == (
        False,
        "retouche_appliquee",
    )
    # Une retouche d'un passage antérieur ne solde pas le changement de celui-ci.
    assert r({**passage, "status": "maj_llm", "maj": {"date": "2026-08-28"}}, None) == (
        True,
        "inchange",
    )
    assert r({**passage, "status": "maj_llm"}, "2026-10-05") == (False, "inchange_reverifiee")
    assert r({**passage, "status": "ok"}, None) == (False, "ok")


# ---------------------------------------------------- un dépôt synthétique


def _git(depot: Path, *args: str, date: str | None = None) -> None:
    env = {**os.environ}
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=depot,
        check=True,
        capture_output=True,
        env=env,
    )


def _depot(tmp_path: Path) -> Path:
    depot = tmp_path / "depot"
    for d in (cv.FILE.parent, cv.MANIFESTE.parent, cv.AIDES, cv.SOURCES):
        (depot / d).mkdir(parents=True, exist_ok=True)
    _git(depot, "init", "-q", "-b", "main")
    return depot


def _tache(statut: str, **champs: Any) -> cv.etat.Tache:
    return cv.etat.Tache(
        titre="t", url="https://exemple.fr/p", territoire="test", statut=statut,
        ajoute_le=dt.date(2026, 9, 1), **champs,
    )  # fmt: skip


def _ecrire_file(depot: Path, taches: dict[str, cv.etat.Tache]) -> None:
    cv.etat.ecrire(depot / cv.FILE, taches)


def _ecrire_manifeste(depot: Path, entrees: dict[str, Any]) -> None:
    cv.veille_aides.write_manifest(entrees, depot / cv.MANIFESTE)


def _aide(depot: Path, slug: str, verifiee: str = "2026-09-01", suffixe: str = ".yaml") -> None:
    (depot / cv.AIDES / f"{slug}{suffixe}").write_text(
        f"slug: {slug}\nsource:\n  verified_at: {verifiee}\n", encoding="utf-8"
    )


def _instantane(depot: Path, slug: str, nom: str, url: str) -> None:
    dossier = depot / cv.SOURCES / slug
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / nom).write_text(
        f"---\nurl: {url}\nfetched_at: 2026-09-01T00:00:00+00:00\nsha256: {nom}\n---\n\ncorps\n",
        encoding="utf-8",
    )


def _commit(depot: Path, message: str, date: str) -> None:
    _git(depot, "add", "-A")
    _git(depot, "commit", "-q", "-m", message, date=date)


def test_chaque_etat_est_date_par_le_commit_qui_l_a_introduit(tmp_path: Path) -> None:
    depot = _depot(tmp_path)
    _ecrire_file(depot, {"a": _tache("a_valider"), "b": _tache("a_valider")})
    _ecrire_manifeste(depot, {})
    _commit(depot, "c1", "2026-09-01T10:00:00+00:00")
    _git(depot, "checkout", "-q", "-b", "x")
    _ecrire_file(depot, {"a": _tache("valide"), "b": _tache("a_valider")})
    _commit(depot, "c2 sur x", "2026-09-02T10:00:00+00:00")
    _git(depot, "checkout", "-q", "main")
    _ecrire_file(
        depot,
        {"a": _tache("a_valider"), "b": _tache("ignore", motif_ignore="doublon d'URL de a")},
    )
    _commit(depot, "c3 sur main", "2026-09-03T10:00:00+00:00")
    # La fusion reprend a de x et b de main : elle n'introduit rien.
    _git(depot, "merge", "-q", "-s", "ours", "--no-commit", "x")
    _ecrire_file(
        depot, {"a": _tache("valide"), "b": _tache("ignore", motif_ignore="doublon d'URL de a")}
    )
    _commit(depot, "fusion", "2026-09-04T10:00:00+00:00")

    journal = Journal(tmp_path / "journal")
    ajoutes = cv.convertir(depot, journal, run="r1")
    file = {e.objet: e for e in ajoutes if e.decision == "file"}
    assert file["a:a"].t == "2026-09-02T10:00:00+00:00"
    assert file["a:b"].t == "2026-09-03T10:00:00+00:00"
    assert file["a:b"].donnees["provenance_motif"] == "doublon_regle"
    assert [h[2] for h in file["a:a"].donnees["historique"]] == ["a_valider", "valide"]
    assert cv.verifier(depot, journal) == []

    # Relancé sans changement : rien.
    assert cv.convertir(depot, journal, run="r2") == []

    # Un état laissé non committé se date par le fichier, une tâche retirée se consigne.
    _ecrire_file(depot, {"a": _tache("ingere")})
    ajoutes = cv.convertir(depot, journal, run="r3")
    assert {(e.objet, e.decision, e.issue) for e in ajoutes} == {
        ("a:a", "file", "ingere"),
        ("a:b", "file", "retiree"),
        ("a:a", "catalogue", "ecartee_apres_ingestion"),  # ingérée, et pas de YAML
    }
    mtime = dt.datetime.fromtimestamp((depot / cv.FILE).stat().st_mtime, dt.UTC)
    a = next(e for e in ajoutes if e.objet == "a:a" and e.decision == "file")
    assert a.t == mtime.isoformat(timespec="seconds")
    assert cv.verifier(depot, journal) == []


def test_un_changement_de_veille_non_applique_reste_du(tmp_path: Path) -> None:
    depot = _depot(tmp_path)
    url = "https://exemple.fr/aide"
    passage = {"checked_at": "2026-10-04", "urls": [{"label": "page", "sha256": "x", "url": url}]}
    entrees = {
        "escalade": {**passage, "status": "escalade_ingestion"},
        "inchangee": {**passage, "status": "maj_llm"},
        "retouchee": {**passage, "status": "maj_llm", "maj": {"date": "2026-10-04"}},
        "reingeree": {**passage, "status": "maj_llm"},
        "ecartee": {**passage, "status": "ok"},
    }
    for slug in entrees:
        _instantane(depot, slug, "2026-09-01-page.md", url)
    for slug in ("inchangee", "retouchee", "reingeree"):
        _instantane(depot, slug, "2026-10-04-page.md", url)
    for slug in ("escalade", "inchangee", "retouchee"):
        _aide(depot, slug)
    _aide(depot, "reingeree", verifiee="2026-10-05")
    _aide(depot, "ecartee", suffixe=".yaml.echec")
    _ecrire_file(depot, {})
    _ecrire_manifeste(depot, entrees)
    _commit(depot, "passage", "2026-10-07T10:00:00+00:00")

    ajoutes = cv.convertir(depot, Journal(tmp_path / "journal"), run="r1")
    bases = {e.objet: e.donnees for e in ajoutes if e.decision == "base"}
    assert (bases["a:escalade"]["fichier"], bases["a:escalade"]["du"]) == (
        "2026-09-01-page.md",
        True,
    )
    assert (bases["a:inchangee"]["fichier"], bases["a:inchangee"]["du"]) == (
        "2026-09-01-page.md",
        True,
    )
    assert (bases["a:retouchee"]["fichier"], bases["a:retouchee"]["du"]) == (
        "2026-10-04-page.md",
        False,
    )
    assert (bases["a:reingeree"]["fichier"], bases["a:reingeree"]["du"]) == (
        "2026-10-04-page.md",
        False,
    )
    assert "a:ecartee" not in bases
    contradictions = {(e.objet, e.decision) for e in ajoutes if e.type == "contradiction"}
    assert contradictions == {("a:ecartee", "veille_hors_catalogue")}
    veille = {e.objet: e for e in ajoutes if e.decision == "veille"}
    assert veille["a:escalade"].t == "2026-10-04T00:00:00+00:00"  # le passage, pas le commit


def test_ecarts_et_contradictions_ne_se_consignent_qu_une_fois(tmp_path: Path) -> None:
    depot = _depot(tmp_path)
    _aide(depot, "double")
    _aide(depot, "double", suffixe=".yaml.echec")
    _aide(depot, "rouverte")
    _aide(depot, "sortie")
    _ecrire_manifeste(depot, {})
    _ecrire_file(
        depot,
        {
            "double": _tache("ingere"),
            "rouverte": _tache("ingere", motif_ignore="tri humain du 2026-09-30 : hors cible"),
            "sortie": _tache("ingere"),
        },
    )
    _commit(depot, "c1", "2026-09-01T10:00:00+00:00")
    (depot / cv.AIDES / "sortie.yaml").rename(depot / cv.AIDES / "sortie.yaml.echec")
    _commit(depot, "écartée après ingestion", "2026-09-05T10:00:00+00:00")

    journal = Journal(tmp_path / "journal")
    ajoutes = cv.convertir(depot, journal, run="r1")
    assert {(e.objet, e.decision) for e in ajoutes if e.type == "contradiction"} == {
        ("a:double", "yaml_et_echec"),
        ("a:rouverte", "ingeree_malgre_ecart"),
    }
    ecart = next(e for e in ajoutes if e.decision == "catalogue")
    assert (ecart.objet, ecart.issue, ecart.t) == (
        "a:sortie",
        "ecartee_apres_ingestion",
        "2026-09-05T10:00:00+00:00",
    )
    assert cv.convertir(depot, journal, run="r2") == []
