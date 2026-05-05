"""
Helpers to derive (departement_codes, region_codes) for an aide ingested from
aides-territoires.beta.gouv.fr.

Two strategies, in this order:

1. Read the API payload's `perimeter_scale` / `perimeter_code` / `perimeter` /
   `region` fields — authoritative when present.
2. Fallback: parse the `organisme` string (e.g. "Conseil départemental de la
   Seine-Maritime") against the INSEE label tables.

Output formats are aligned with the join tables already in DB:
    aides_departements.departement_code  → INSEE numeric ("76", "2A", "971")
    aides_regions.region_code            → kebab-case   ("ile-de-france")
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Reuse the canonical label tables defined for the matching engine
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from matching_engine import DEPARTEMENT_LABELS, REGION_LABELS  # noqa: E402

# Inverse maps: label → code
_DEPARTEMENT_LABEL_TO_CODE = {label: code for code, label in DEPARTEMENT_LABELS.items()}
_REGION_LABEL_TO_CODE = {label: code for code, label in REGION_LABELS.items()}


def _word_pattern(label: str) -> re.Pattern:
    """Match `label` only when not glued to other letters/hyphens.

    Word-aware so that "Marne" doesn't match inside "Haute-Marne", and
    "Eure" doesn't match inside "Eure-et-Loir".
    """
    return re.compile(r"(?<![\w\-])" + re.escape(label) + r"(?![\w\-])")


# Pre-compile patterns sorted longest first (so "Haute-Marne" wins over "Marne")
_DEPT_PATTERNS = [
    (code, _word_pattern(label))
    for label, code in sorted(_DEPARTEMENT_LABEL_TO_CODE.items(), key=lambda kv: -len(kv[0]))
]
_REGION_PATTERNS = [
    (code, _word_pattern(label))
    for label, code in sorted(_REGION_LABEL_TO_CODE.items(), key=lambda kv: -len(kv[0]))
]


def parse_perimeter_from_at(aid: dict) -> tuple[list[str], list[str]]:
    """Extract (dept_codes, region_codes) from an aides-territoires payload.

    Returns empty lists when the perimeter is national (`Pays`) or ad-hoc
    (PNR, GAL, …) — those aids are treated as having no geo constraint.
    """
    scale = aid.get("perimeter_scale")
    perimeter = aid.get("perimeter") or ""
    perimeter_code = aid.get("perimeter_code") or ""

    if scale == "Département":
        if perimeter_code in DEPARTEMENT_LABELS:
            return [perimeter_code], []
        # Code unknown? Try the label as a backup.
        code = _DEPARTEMENT_LABEL_TO_CODE.get(perimeter)
        return ([code], []) if code else ([], [])

    if scale == "Région":
        # `perimeter_code` here is the INSEE numeric region code which we don't
        # store. Map via the human label instead.
        code = _REGION_LABEL_TO_CODE.get(perimeter)
        return ([], [code]) if code else ([], [])

    return [], []


def parse_perimeter_from_organisme(organisme: str | None) -> tuple[list[str], list[str]]:
    """Heuristic fallback: scan the organisme string for INSEE labels."""
    if not organisme:
        return [], []
    depts: list[str] = []
    regions: list[str] = []
    for code, pattern in _DEPT_PATTERNS:
        if pattern.search(organisme) and code not in depts:
            depts.append(code)
    for code, pattern in _REGION_PATTERNS:
        if pattern.search(organisme) and code not in regions:
            regions.append(code)
    return depts, regions


def derive_geo_constraints(
    aid: dict, *, organisme: str | None = None
) -> tuple[list[str], list[str]]:
    """Best-effort geo constraints for an aid.

    Tries the API perimeter first; if that yields nothing, falls back to
    parsing the `organisme` string. `organisme` defaults to `aid.get('organisme')`
    so this works on both raw API payloads and DB rows.
    """
    depts, regions = parse_perimeter_from_at(aid)
    if depts or regions:
        return depts, regions
    return parse_perimeter_from_organisme(organisme or aid.get("organisme"))
