"""Mesure d'I4 : les 7 ré-extractions du 2026-10-05 rejouées par la nouvelle chaîne.

    uv run --no-sync python -m catalogue.mesures.reextraction_banc <dossier> [--plafond-serie 3]
    uv run --no-sync python -m catalogue.mesures.reextraction_banc <dossier> --analyser

Le 2026-10-05, Félix a fait ré-ingérer 7 aides dont la veille du 2026-10-04
avait manqué le changement (commit `c36cbfd9`). On rejoue ces ré-extractions
depuis l'état d'avant : le YAML de `c36cbfd9^`, les instantanés archivés
jusqu'au 2026-10-04, `facts_pending.yaml` de la branche. L'agent sous contrat
(`catalogue.agent`) relit les sources en ligne aujourd'hui ; la ré-extraction
(`catalogue.reextraction`) applique ses règles de retour et l'éditeur par
plages. Tout s'écrit dans `<dossier>/` (catalogue de travail, sorties de
l'agent, rebuts), jamais dans `data/`.

Ce qui est relevé, par aide : l'issue, les cases par sorte, les lignes changées
du YAML (contre celles de la ré-ingestion du 2026-10-05, qui réécrivait tout le
fichier), le coût relevé, la durée ; et si le calendrier et le financement
rejoignent ceux que la ré-ingestion avait posés (`c36cbfd9`).
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from aides_schema import charger_yaml
from catalogue import reextraction as rx
from catalogue.registre import BACKEND

AIDES = (
    "88-restauration-patrimoine",
    "aura-villages-remarquables-labellisation",
    "feder-occitanie-equipements-culturels-rural",
    "normandie-contrats-natura-2000-feder-region",
    "normandie-non-proteges-tpn",
    "paca-nos-communes-dabord",
    "region-grand-est-soutien-initiatives-artistiques",
)
AVANT, APRES = "c36cbfd9^", "c36cbfd9"
JOUR_PASSAGE = "2026-10-04"


def git_show(rev: str, chemin: str) -> str:
    return subprocess.run(
        ["git", "show", f"{rev}:{chemin}"], cwd=BACKEND, capture_output=True, text=True, check=True
    ).stdout


def lignes_changees(a: str, b: str) -> int:
    return sum(
        1
        for x in difflib.unified_diff(a.split("\n"), b.split("\n"), n=0)
        if x[:1] in "+-" and not x.startswith(("+++", "---"))
    )


def preparer(dossier: Path) -> None:
    (dossier / "aides").mkdir(parents=True)
    for slug in AIDES:
        (dossier / "aides" / f"{slug}.yaml").write_text(
            git_show(AVANT, f"backend/data/aides/{slug}.yaml"), encoding="utf-8"
        )
        cible = dossier / "sources" / slug
        cible.mkdir(parents=True)
        for p in sorted((BACKEND / "data" / "sources" / slug).iterdir()):
            if p.name[:10] <= JOUR_PASSAGE:
                shutil.copy2(p, cible / p.name)
    shutil.copy2(BACKEND / "data" / "facts_pending.yaml", dossier / "facts_pending.yaml")


def executer(dossier: Path, plafond_serie: float) -> int:
    dossier.mkdir(parents=True, exist_ok=False)
    preparer(dossier)
    total = 0.0
    with (dossier / "resultats.jsonl").open("a", encoding="utf-8") as sortie:
        for slug in AIDES:
            if total >= plafond_serie:
                print(f"plafond de série atteint ({total:.3f} $) : {slug} et suivantes non lancées")
                break
            avant = (dossier / "aides" / f"{slug}.yaml").read_text(encoding="utf-8")
            b = rx.reextraire(
                slug,
                plafond=1.875,
                delai_s=3600,
                jour=dt.date.today(),
                etat=f"banc-{slug}",
                sorties=dossier / "sorties",
                aides=dossier / "aides",
                sources=dossier / "sources",
                pending=dossier / "facts_pending.yaml",
                rebuts=dossier / "rebuts",
            )
            total += b.cout_usd
            apres = (dossier / "aides" / f"{slug}.yaml").read_text(encoding="utf-8")
            ligne = {
                "slug": slug,
                "issue": b.issue,
                "raison": b.raison[:400],
                "panne": b.panne,
                "cout_usd": round(b.cout_usd, 6),
                "duree_s": round(b.duree_s, 1),
                "cases": Counter(c.sorte for c in b.cases),
                "changements": b.changements,
                "faits": b.faits,
                "snapshots": b.snapshots,
                "lignes_changees": lignes_changees(avant, apres),
            }
            sortie.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            sortie.flush()
            print(f"{slug} : {b.issue} ({b.raison[:120]}) {b.cout_usd:.3f} $ {b.duree_s:.0f} s")
    print(f"dépense relevée de la série : {total:.4f} $")
    return 0


def _sections(d: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        json.dumps({k: d.get(k) for k in ("calendrier", "financement", "cumul")}, default=str)
    )


def analyser(dossier: Path) -> str:
    rs = [
        json.loads(x)
        for x in (dossier / "resultats.jsonl").read_text(encoding="utf-8").splitlines()
        if x
    ]
    lignes = [
        "| Aide | Issue | Cases | Lignes changées (nouvelle) | Lignes changées (2026-10-05) | Sections égales à la ré-ingestion | Coût | Durée |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rs:
        avant = git_show(AVANT, f"backend/data/aides/{r['slug']}.yaml")
        reingere = git_show(APRES, f"backend/data/aides/{r['slug']}.yaml")
        nouveau = (dossier / "aides" / f"{r['slug']}.yaml").read_text(encoding="utf-8")
        egales = _sections(charger_yaml(nouveau)) == _sections(charger_yaml(reingere))
        cases = ", ".join(f"{k} {v}" for k, v in sorted(r["cases"].items())) or "aucune"
        lignes.append(
            f"| `{r['slug']}` | {r['issue']} | {cases} | {r['lignes_changees']} | "
            f"{lignes_changees(avant, reingere)} | {'oui' if egales else 'non'} | "
            f"{r['cout_usd']:.3f} $ | {r['duree_s']:.0f} s |"
        )
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m catalogue.mesures.reextraction_banc")
    p.add_argument("dossier", type=Path)
    p.add_argument("--plafond-serie", type=float, default=3.0)
    p.add_argument("--analyser", action="store_true")
    args = p.parse_args(argv)
    if args.analyser:
        texte = analyser(args.dossier)
        (args.dossier / "analyse.md").write_text(texte + "\n", encoding="utf-8")
        print(texte)
        return 0
    return executer(args.dossier, args.plafond_serie)


if __name__ == "__main__":
    raise SystemExit(main())
