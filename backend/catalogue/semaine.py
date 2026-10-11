"""Le run hebdomadaire planifiable (incrément I3, section 9 d'`architecture.md`).

    cd <worktree de service>/backend && uv run --no-sync python -m catalogue semaine

Dans l'ordre :

1. Un seul run par checkout (`.run.lock`, `flock`), et aucun ancien script du
   pipeline en cours sur la machine.
2. Pré-vol : clé OpenRouter (reste sur son plafond, date d'expiration),
   dépendances (`providall`, `curl_cffi`, `truststore`), `pdftotext` et sa
   version épinglée, venv synchronisé sur `uv.lock` (`uv sync --check`, hors
   ligne), registre et fichiers de faits valides. Un pré-vol raté n'appelle
   aucun modèle et écrit quand même le rapport.
3. Copie jetable du dépôt (clone APFS, hors du worktree) : les YAML, les faits,
   les instantanés et le manifeste ne s'écrivent que dans la copie. Le journal,
   lui, s'écrit directement dans le worktree, en ajout seul : un run tué ne perd
   ni ses décisions ni sa dépense.
4. Les étapes dont le registre donne l'opération à la nouvelle chaîne tournent
   dans la copie, chacune en sous-processus, sous le délai du run.
5. Recopie : chaque fichier changé dans la copie revient dans le worktree,
   seulement si l'original n'a pas bougé depuis le départ (un commit de Félix
   pendant le run, par exemple) ; sinon rien ne revient, le run s'arrête en
   code 8 et garde sa copie. Le piège du 2026-09-13 (un commit qui ramène à HEAD
   des fichiers qu'un run écrit) ne peut plus se produire.
6. Copie datée du journal hors du worktree ; notification si le code n'est pas 0.

Aucune opération git : le diff reste dans le worktree, et le rapport donne les
commandes (décision 4, réglage `git: diff`).

Codes de sortie : 0 fini ; 1 fini, non livrable ; 2 budget épuisé ; 3 réseau
général ; 4 clé, crédits ou modèle ; 5 fichier partagé invalide ; 6 dépendance
absente ou venv périmé ; 7 plus de cinq objets en bug ; 8 conflit (run déjà en
cours, ancien script en cours, original modifié pendant le run) ; 9 délai du
run atteint.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from catalogue.journal import DOSSIER as JOURNAL
from catalogue.rapport import Rapport, ajouter_parties
from catalogue.registre import BACKEND, Registre, charger

RACINE = BACKEND.parent
COPIES = Path.home() / ".cache" / "monumia" / "runs"
SECOURS = Path.home() / ".local" / "share" / "monumia" / "journal"
REVIEWS = BACKEND / "data" / "reviews"
# Les 11 255 verdicts de citations de référence ont été calculés avec cette
# version : une autre extrairait autrement le texte des PDF (54 % des verdicts).
PDFTOTEXT = "26.07.0"
ANCIENS_SCRIPTS = (
    "prospecter.py",
    "ingerer.py",
    "balayage.py",
    "veille_aides.py",
    "rediger_fiches.py",
)
# Ce que le run peut écrire dans la copie et recopier dans le worktree.
ECRITS = (
    "backend/data/aides",
    "backend/data/sources",
    "backend/data/reviews",
    "backend/data/catalogue/brouillons",
    "backend/data/catalogue/rebuts",
)
FICHIERS_ECRITS = (
    "backend/data/veille-state.yaml",
    "backend/data/facts_pending.yaml",
    "backend/data/facts.yaml",
    "backend/data/prospection/file-attente.yaml",
)
# Ce que la copie emporte : le code et les données, sans venv ni caches.
EXCLUS = {".venv", ".cache", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}

CODES = {
    0: "fini",
    1: "fini, non livrable",
    2: "budget épuisé",
    3: "réseau général",
    4: "clé, crédits ou modèle",
    5: "fichier partagé invalide",
    6: "dépendance absente ou venv périmé",
    7: "plus de cinq objets en bug",
    8: "conflit",
    9: "délai du run atteint",
}


@dataclass
class Echec:
    code: int
    message: str


@dataclass
class Prevol:
    echecs: list[Echec] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def code(self) -> int:
        return min((e.code for e in self.echecs), default=0)


# ------------------------------------------------------------------ pré-vol


def cle_openrouter(
    plafond: float, delai_h: float, lire: Callable[[], dict[str, Any]] | None = None
) -> tuple[list[Echec], list[str]]:
    """Le reste sur le plafond de la clé et son expiration (`GET /api/v1/key`, gratuit)."""

    def par_defaut() -> dict[str, Any]:
        cle = os.environ.get("OPENROUTER_API_KEY")
        if not cle:
            raise KeyError("OPENROUTER_API_KEY absente")
        r = httpx.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {cle}"},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()["data"]

    try:
        d = (lire or par_defaut)()
    except KeyError as exc:
        return [Echec(4, str(exc))], []
    except Exception as exc:  # noqa: BLE001 — sans relevé, on ne démarre pas
        return [Echec(4, f"relevé de la clé impossible : {exc}")], []
    echecs: list[Echec] = []
    notes = [f"clé : usage {d.get('usage')} $, reste {d.get('limit_remaining')} $"]
    reste = d.get("limit_remaining")
    if reste is None:
        notes.append("la clé n'a pas de plafond propre : le reste du compte ne se lit pas")
    elif float(reste) < plafond:
        echecs.append(Echec(4, f"reste de la clé {reste} $ sous le plafond du run {plafond} $"))
    if expire := d.get("expires_at"):
        fin = dt.datetime.fromisoformat(str(expire).replace("Z", "+00:00"))
        if fin < dt.datetime.now(dt.UTC) + dt.timedelta(hours=delai_h):
            echecs.append(Echec(4, f"la clé expire le {expire}, avant la fin possible du run"))
        notes.append(f"expiration de la clé : {expire}")
    return echecs, notes


def dependances() -> list[Echec]:
    echecs = []
    for module in ("providall", "curl_cffi", "truststore"):
        try:
            __import__(module)
        except ImportError:
            echecs.append(
                Echec(6, f"module {module} absent : uv sync --group dev --group pipeline")
            )
    try:
        sortie = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True, timeout=10)
        version = (sortie.stdout + sortie.stderr).split("\n")[0].split()[-1]
        if version != PDFTOTEXT:
            echecs.append(Echec(6, f"pdftotext {version}, attendu {PDFTOTEXT}"))
    except (OSError, IndexError, subprocess.TimeoutExpired):
        echecs.append(Echec(6, "pdftotext absent"))
    venv = subprocess.run(
        ["uv", "sync", "--check", "--offline", "--group", "dev", "--group", "pipeline"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if venv.returncode != 0:
        echecs.append(
            Echec(6, "venv désynchronisé de uv.lock : uv sync --group dev --group pipeline")
        )
    return echecs


def fichiers_partages() -> list[Echec]:
    """Le catalogue entier se charge, faits compris : sinon tout ce qui suit échouerait."""
    try:
        from aides_schema import load_all_aides

        load_all_aides()
    except Exception as exc:  # noqa: BLE001 — le motif va au rapport
        return [Echec(5, f"catalogue ou faits invalides : {str(exc)[:300]}")]
    return []


def anciens_en_cours() -> list[str]:
    sortie = subprocess.run(
        ["pgrep", "-fl", "|".join(ANCIENS_SCRIPTS)], capture_output=True, text=True
    )
    return [ligne for ligne in sortie.stdout.splitlines() if ligne.strip()]


def prevol(reg: Registre, *, lire_cle: Callable[[], dict[str, Any]] | None = None) -> Prevol:
    p = Prevol()
    echecs, notes = cle_openrouter(reg.budgets.run.plafond_usd, reg.budgets.run.delai_h, lire_cle)
    p.echecs += echecs
    p.notes += notes
    p.echecs += dependances()
    p.echecs += fichiers_partages()
    if anciens := anciens_en_cours():
        p.echecs.append(Echec(8, f"ancien script du pipeline en cours : {anciens[0]}"))
    return p


# ------------------------------------------------------------------ copie et recopie


@contextmanager
def verrou_run(racine: Path) -> Iterator[bool]:
    """`True` si ce run tient le verrou du checkout, `False` si un autre run le tient."""
    chemin = racine / "backend" / ".run.lock"
    with chemin.open("a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def cloner(racine: Path, cible: Path) -> None:
    """Copie le dépôt (code, données, skills) par clone APFS, sans venv ni caches."""
    cible.mkdir(parents=True)
    for nom in ("backend", ".claude"):
        source = racine / nom
        if not source.exists():
            continue
        (cible / nom).mkdir()
        for enfant in source.iterdir():
            if enfant.name in EXCLUS or enfant.name == ".run.lock":
                continue
            if nom == ".claude" and enfant.name not in ("skills",):
                continue
            subprocess.run(["cp", "-cR", str(enfant), str(cible / nom / enfant.name)], check=True)


def etat_fichiers(racine: Path) -> dict[str, tuple[int, int]]:
    """(taille, date de modification) de chaque fichier que le run peut écrire."""
    etat: dict[str, tuple[int, int]] = {}
    for rel in ECRITS:
        base = racine / rel
        if base.is_dir():
            for p in base.rglob("*"):
                if p.is_file() and "logs" not in p.relative_to(base).parts:
                    st = p.stat()
                    etat[str(p.relative_to(racine))] = (st.st_size, st.st_mtime_ns)
    for rel in FICHIERS_ECRITS:
        p = racine / rel
        if p.is_file():
            st = p.stat()
            etat[rel] = (st.st_size, st.st_mtime_ns)
    return etat


def changes(avant: dict[str, tuple[int, int]], apres: dict[str, tuple[int, int]]) -> list[str]:
    return sorted(k for k, v in apres.items() if avant.get(k) != v) + sorted(
        k for k in avant if k not in apres
    )


# Ordre de recopie (section 7.6) : les faits, puis les YAML et leurs instantanés,
# puis le reste (manifeste, file, rapports).
def _rang(rel: str) -> int:
    if "facts" in rel:
        return 0
    if "/aides/" in rel or "/sources/" in rel:
        return 1
    return 2


def recopier(
    copie: Path,
    racine: Path,
    depart_racine: dict[str, tuple[int, int]],
    depart_copie: dict[str, tuple[int, int]],
) -> tuple[list[str], list[str]]:
    """(fichiers recopiés, conflits). Aucun fichier ne revient s'il y a un conflit."""
    a_recopier = changes(depart_copie, etat_fichiers(copie))
    actuel = etat_fichiers(racine)
    conflits = [rel for rel in a_recopier if actuel.get(rel) != depart_racine.get(rel)]
    if conflits:
        return [], conflits
    for rel in sorted(a_recopier, key=lambda r: (_rang(r), r)):
        source, cible = copie / rel, racine / rel
        if source.exists():
            cible.parent.mkdir(parents=True, exist_ok=True)
            temporaire = cible.with_name(f".{cible.name}.{os.getpid()}.tmp")
            shutil.copy2(source, temporaire)
            with temporaire.open("rb") as f:
                os.fsync(f.fileno())
            temporaire.replace(cible)
        elif cible.exists():
            cible.unlink()
    return a_recopier, []


# ------------------------------------------------------------------ étapes


@dataclass
class Etape:
    nom: str
    arguments: list[str]


def etapes(reg: Registre, journal: Path, parties: Path) -> list[Etape]:
    """Les étapes que le registre donne à la nouvelle chaîne, dans l'ordre de priorité du budget."""
    liste = []
    if reg.proprietaires["veille"] == "nouvelle":
        liste.append(
            Etape(
                "veille",
                ["veille", "--journal", str(journal), "--parties", str(parties / "veille.json")],
            )
        )
    if reg.proprietaires["prospection"] == "nouvelle":
        # Un quart des territoires chaque semaine (décision 2 : balayage mensuel).
        from prospection.territoires import charger_territoires

        noms = sorted(charger_territoires())
        quart = dt.date.today().isocalendar().week % 4
        for nom in noms[quart::4]:
            liste.append(
                Etape(
                    f"entree-{nom}",
                    [
                        "entree",
                        "--territoire",
                        nom,
                        "--journal",
                        str(journal),
                        "--parties",
                        str(parties / f"entree-{nom}.json"),
                    ],
                )
            )
    if reg.proprietaires["ingestion"] == "nouvelle":
        liste.append(
            Etape(
                "ingestion",
                [
                    "ingestion",
                    "--journal",
                    str(journal),
                    "--parties",
                    str(parties / "ingestion.json"),
                ],
            )
        )
    return liste


def lancer(copie: Path, etape: Etape, delai_s: float, reste_usd: float | None = None) -> int:
    arguments = list(etape.arguments)
    if reste_usd is not None and etape.arguments[0] in ("entree", "ingestion"):
        # Une étape ne dépense que ce qui reste du budget du run.
        arguments += ["--plafond", f"{max(reste_usd, 0.0):.4f}"]
    try:
        r = subprocess.run(
            [sys.executable, "-m", "catalogue", *arguments],
            cwd=copie / "backend",
            timeout=delai_s,
        )
    except subprocess.TimeoutExpired:
        return 9
    return r.returncode


def _depense_partie(chemin: Path) -> float:
    try:
        return float(json.loads(chemin.read_text(encoding="utf-8")).get("depense") or 0.0)
    except (OSError, ValueError):
        return 0.0


def notifier(code: int, chemin: Path | None) -> None:
    if code == 0:
        return
    message = f"run du catalogue : code {code} ({CODES.get(code, '?')})"
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "Monumia"'],
            timeout=10,
            capture_output=True,
        )
    print(message + (f" — {chemin}" if chemin else ""), file=sys.stderr)


def sauvegarder_journal(journal: Path, run: str) -> None:
    if journal.is_dir():
        cible = SECOURS / run
        shutil.copytree(journal, cible, dirs_exist_ok=True)


def semaine(
    racine: Path = RACINE,
    *,
    journal: Path = JOURNAL,
    copies: Path = COPIES,
    lire_cle: Callable[[], dict[str, Any]] | None = None,
    jour: dt.date | None = None,
) -> int:
    jour = jour or dt.date.today()
    run = f"{jour.isocalendar().year}-W{jour.isocalendar().week:02d}-{os.getpid()}"
    reviews = racine / "backend" / "data" / "reviews"
    rapport = Rapport(jour, run)
    with verrou_run(racine) as tenu:
        if not tenu:
            rapport.entete = ["- Run refusé : un autre run tient `.run.lock` sur ce checkout."]
            notifier(8, None)
            return 8
        try:
            reg = charger()
        except Exception as exc:  # noqa: BLE001
            rapport.entete = [f"- Run arrêté : registre invalide ({exc})."]
            chemin = rapport.ecrire(reviews)
            notifier(5, chemin)
            return 5
        p = prevol(reg, lire_cle=lire_cle)
        if p.code:
            rapport.entete = [
                f"- Run arrêté au pré-vol, code {p.code} ({CODES[p.code]}) ; aucun modèle appelé.",
                *[f"- {e.message}" for e in p.echecs],
                *[f"- {n}" for n in p.notes],
            ]
            chemin = rapport.ecrire(reviews)
            notifier(p.code, chemin)
            return p.code

        copie = copies / run
        depart_racine = etat_fichiers(racine)
        cloner(racine, copie)
        depart_copie = etat_fichiers(copie)
        code = 0
        fin = dt.datetime.now() + dt.timedelta(hours=reg.budgets.run.delai_h)
        faites: list[str] = []
        parties = copies / f"{run}-parties"
        parties.mkdir(parents=True, exist_ok=True)
        for e in etapes(reg, journal, parties):
            restant = (fin - dt.datetime.now()).total_seconds()
            if restant <= 0:
                code = 9
                break
            depense = sum(_depense_partie(f) for f in parties.glob("*.json"))
            reste = reg.budgets.run.plafond_usd - depense
            if reste <= 0:
                code = 2
                break
            c = lancer(copie, e, restant, reste)
            faites.append(f"{e.nom} : code {c}")
            code = code or c
            if c in (3, 4, 5, 6, 8, 9):
                break
        recopies, conflits = recopier(copie, racine, depart_racine, depart_copie)
        if conflits:
            code = 8
        else:
            shutil.rmtree(copie, ignore_errors=True)
        sauvegarder_journal(journal, run)

        entete = [
            f"- Run {'fini' if code == 0 else f'arrêté, code {code} ({CODES.get(code, chr(63))})'}.",
            f"- Étapes : {', '.join(faites) or 'aucune (le registre laisse tout à l’ancienne chaîne)'}.",
            *[f"- {n}" for n in p.notes],
            f"- Fichiers revenus dans le worktree : {len(recopies)}.",
        ]
        if conflits:
            entete.append(
                f"- Conflit : {len(conflits)} fichier(s) modifié(s) dans le worktree pendant le run "
                f"(premier : {conflits[0]}) ; rien n'est revenu, la copie reste dans {copie}."
            )
        if recopies:
            entete.append(
                "- À relire puis committer : `git diff -- backend/data` (le run ne fait aucune "
                "opération git)."
            )
        rapport.entete = entete
        for f in sorted(parties.glob("*.json")):
            ajouter_parties(rapport, f.read_text(encoding="utf-8"))
        # Dix cases de doute d'entrée au plus pour tout le run (section 8), les
        # territoires passant chacun les siennes.
        doutes = [c for c in rapport.cases if c.sorte == "entree-doute"]
        if len(doutes) > 10:
            rapport.cases = [c for c in rapport.cases if c.sorte != "entree-doute"] + doutes[:10]
            rapport.entete.append(
                f"- {len(doutes) - 10} doute(s) d'entrée en attente au-delà des dix cases."
            )
        shutil.rmtree(parties, ignore_errors=True)
        chemin = rapport.ecrire(reviews)
        (copies / f"{run}.json").parent.mkdir(parents=True, exist_ok=True)
        (copies / f"{run}.json").write_text(
            json.dumps({"code": code, "recopies": recopies, "conflits": conflits}, indent=1),
            encoding="utf-8",
        )
        notifier(code, chemin)
        return code
