"""Les verdicts de toutes les citations du catalogue, comparés à la référence de la phase 1.

    uv run --no-sync python -m catalogue.mesures.citations [--reference <fichier.jsonl>]

Recalcule, pour chaque condition citée de chaque aide, le verdict de
`find_quote_in_any` sur les instantanés que charge `load_baselines`, exactement
comme `scripts/mesures/invariants_a.py` l'a fait le 2026-10-10 (11 255
citations, `citations_golden.jsonl`), et compare champ par champ. Sert de
contrôle au déplacement des modules de veille (incrément I5) : un seul verdict
qui change revaliderait ou invaliderait une citation du catalogue.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aides_schema import AIDES_DIR, load_aide
from catalogue import veille_collect, veille_text
from catalogue.registre import BACKEND

REFERENCE = (
    BACKEND
    / "data"
    / "reviews"
    / "logs"
    / "refonte"
    / "2026-10-10-invariants-a-1"
    / "citations_golden.jsonl"
)


def verdicts() -> list[dict]:
    sortie = []
    for chemin in sorted(AIDES_DIR.glob("*.yaml")):
        aide = load_aide(chemin)
        docs, _illisibles, _ = veille_collect.load_baselines(aide.slug)
        for c in aide.conditions:
            q = c.quote or ""
            if not q.strip():
                continue
            nom, m = veille_text.find_quote_in_any(q, docs)  # type: ignore[arg-type]
            sortie.append(
                {
                    "slug": aide.slug,
                    "id": c.id,
                    "doc": nom,
                    "status": m.status,
                    "start": m.start,
                    "end": m.end,
                    "reconstitution": m.reconstitution,
                    "prefix_len": m.prefix_len,
                    "quote_len": m.quote_len,
                }
            )
    return sortie


def comparer(reference: Path) -> tuple[int, list[str]]:
    attendu = {
        (d["slug"], d["id"]): d
        for d in map(json.loads, reference.read_text(encoding="utf-8").splitlines())
    }
    obtenu = {(d["slug"], d["id"]): d for d in verdicts()}
    ecarts = [
        f"{k} : {attendu.get(k)} -> {obtenu.get(k)}"
        for k in sorted(set(attendu) | set(obtenu))
        if attendu.get(k) != obtenu.get(k)
    ]
    return len(obtenu), ecarts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m catalogue.mesures.citations")
    p.add_argument("--reference", type=Path, default=REFERENCE)
    args = p.parse_args(argv)
    n, ecarts = comparer(args.reference)
    print(f"{n} citations, {len(ecarts)} verdict(s) différent(s) de la référence")
    for e in ecarts[:20]:
        print("  " + e)
    return 1 if ecarts else 0


if __name__ == "__main__":
    raise SystemExit(main())
