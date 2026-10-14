"""Un plan de correction des prédicats qui écartent une réponse que leur texte admet.

Commande, depuis backend/ :

    uv run --no-sync python -m catalogue.mesures.plan_polarite <dossier de catalogue.mesures.polarite>

Lit `gates.jsonl` d'une mesure de polarité et écrit, pour
`scripts/appliquer_typages.py`, un plan qui ÉLARGIT chaque prédicat aux
réponses que Jev juge admises par le texte (seuil `haut` de `P1-polarite`)
alors que le prédicat les écarte. Mesuré le 2026-10-14 : le prédicat avait
tort 34 fois sur 40 ; quand Jev se trompe, l'élargissement propose l'aide à
quelques demandeurs de trop, il n'en retire à personne.

Seules les formes simples s'élargissent mécaniquement :

  - `in: L` : la réponse s'ajoute à L ; `eq: v` devient `in: [v, …]` ;
  - `not_in: L` : la réponse sort de L (si L se vide, la gate ne trie plus
    personne : elle est laissée de côté) ;
  - un booléen, un `neq`, un combinateur : laissés de côté et listés, une
    gate booléenne dont les deux réponses rempliraient la condition n'en est
    plus une, et cela ne se décide pas mécaniquement.

Le plan garde le reste du typage de la condition (`kind`, `effect`, `fact`,
`derogation_possible`, `levier`) : `appliquer_typages.py` efface une clé de
typage absente du plan.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from aides_schema import AIDES_DIR, load_all_aides
from catalogue import registre as registre_mod
from catalogue.polarite import DECISION

BACKEND = Path(__file__).resolve().parents[2]


def elargi(predicat: dict[str, Any], admises: list[str]) -> dict[str, Any] | None:
    """Le prédicat qui admet aussi `admises`, ou None si la forme ne s'élargit pas seule."""
    if len(predicat) != 1:
        return None
    op, ref = next(iter(predicat.items()))
    if op == "in" and isinstance(ref, list):
        return {"in": ref + [a for a in admises if a not in ref]}
    if op == "eq" and isinstance(ref, str):
        return {"in": [ref] + [a for a in admises if a != ref]}
    if op == "not_in" and isinstance(ref, list):
        reste = [v for v in ref if v not in admises]
        return {"not_in": reste} if reste else None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mesure", type=Path)
    parser.add_argument(
        "--exclure",
        type=Path,
        help="étiquettes d'une relecture (`etiquettes.json`) : ces gates ont leur propre plan",
    )
    args = parser.parse_args()
    relues = set(json.loads(args.exclure.read_text(encoding="utf-8"))) if args.exclure else set()
    haut = registre_mod.charger().decisions[DECISION].seuils["haut"]

    par_gate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ligne in (args.mesure / "gates.jsonl").read_text(encoding="utf-8").splitlines():
        x = json.loads(ligne)
        if not x["admise"] and x["p_remplie"] >= haut and x["ref"] not in relues:
            par_gate[x["ref"]].append(x)

    aides = load_all_aides(AIDES_DIR)
    plan: list[dict[str, Any]] = []
    laissees: list[str] = []
    for ref, xs in sorted(par_gate.items()):
        slug, cid = ref.split("#", 1)
        c = next(c for c in aides[slug].conditions if c.id == cid)
        admises = [x["reponse"] for x in xs]
        nouveau = (
            elargi(c.predicate.root, admises)
            if c.predicate is not None and xs[0]["type"] != "boolean"
            else None
        )
        libelles = ", ".join(f"« {x['label']} » ({x['p_remplie']:.2f})" for x in xs)
        if nouveau is None:
            laissees.append(
                f"{ref} : `{json.dumps(c.predicate.root if c.predicate else None, ensure_ascii=False)}`, réponses {libelles}"
            )
            continue
        entree: dict[str, Any] = {"ref": ref, "kind": c.kind, "effect": c.effect, "fact": c.fact}
        entree["predicate"] = nouveau
        if c.derogation_possible:
            entree["derogation_possible"] = True
        if c.levier is not None:
            entree["levier"] = c.levier.model_dump(mode="json", exclude_none=True)
        entree["motif"] = (
            f"sens du prédicat (P1-polarite) : le texte admet {libelles} selon Jev, "
            "le prédicat les écartait."
        )
        plan.append(entree)

    jour = dt.date.today().isoformat()
    chemin = BACKEND / "data" / "coherence" / f"{jour}-plan-polarite-jev.yaml"
    entete = (
        f"# Plan du {jour} : prédicats élargis aux réponses que leur texte admet selon Jev\n"
        f"# (décision P1-polarite, data/reviews/2026-10-14-polarite.md). Produit par\n"
        f"# catalogue/mesures/plan_polarite.py depuis {args.mesure.name}.\n"
        f"# {len(plan)} condition(s) ; {len(laissees)} laissée(s) de côté (forme non élargissable) ;\n"
        f"# {len(relues)} gate(s) relue(s) exclue(s), qui ont leur propre plan.\n"
    )
    chemin.write_text(
        entete + yaml.safe_dump(plan, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    print(f"{len(plan)} condition(s) au plan : {chemin}")
    print(f"{len(laissees)} laissée(s) de côté :")
    for li in laissees:
        print(f"  - {li}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
