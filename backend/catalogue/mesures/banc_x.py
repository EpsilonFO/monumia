"""Banc X : l'extraction d'une aide, agent actuel contre extraction structurée (I0, M3).

Commandes, depuis backend/ :

    uv run python -m catalogue.mesures.banc_x tirer
    uv run python -m catalogue.mesures.banc_x verifier <dossier>/<slug>.yaml [--faits <fichier>]

`tirer` choisit les 12 aides du banc : les 5 du banc d'ingestion du 2026-10-07
(`2026-10-07-benchmark-mistral-large-4.md`), puis 7 aides tirées au hasard
(graine 20261014) pour que chaque portée ait sa part : 2 nationales de
restauration, 2 nationales hors restauration, 1 départementale de restauration,
2 départementales hors restauration. Les 5 aides fixes couvrent déjà le
régional (2 de restauration, 2 hors restauration) et une départementale de
restauration. Une aide est « de restauration » si ses `familles` contiennent
`restauration_bati`, ou, sans `familles`, si son nom ou sa description parle de
restauration. Une aide n'entre au tirage que si elle a au moins un instantané
dans `data/sources/<slug>/` et n'existe pas aussi en `.yaml.echec`. Sortie :
backend/data/reviews/logs/refonte/<date>-banc-x-<n>/aides.json.

`verifier` contrôle une extraction sans rien écrire : le YAML se charge
(`aides_schema.load_aide`), chaque condition a une ligne `effect`, aucune n'est
`untyped` ni `manual_check` en gate, chaque fait cité existe dans `facts.yaml`,
`facts_pending.yaml` ou le fichier de faits proposés passé par `--faits` (dont
chaque entrée doit se valider comme un fait), et chaque `quote` se retrouve dans
les instantanés de `data/sources/<slug>/` par `veille_text.find_quote_in_any`,
la recherche du lint. Il imprime un résumé JSON.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import yaml
from veille_collect import load_baselines
from veille_text import find_quote_in_any

from aides_schema import FactDef, load_aide, load_facts, load_pending_facts
from catalogue.mesures.jeu_e import _dossier_neuf

BACKEND = Path(__file__).resolve().parents[2]
AIDES = BACKEND / "data" / "aides"
SOURCES = BACKEND / "data" / "sources"
GRAINE = 20261014
FIXES = (
    "hdf-jardins-en-scene",
    "hdf-actes-fonds-appui-projets-locaux",
    "88-patrimoine-protege-mh",
    "bretagne-edifices-publics",
    "pdl-cap-pcc",
)
A_TIRER = {
    ("nationale", True): 2,
    ("nationale", False): 2,
    ("departementale", True): 1,
    ("departementale", False): 2,
}
PORTEES = {"region": "regionale", "departement": "departementale"}


def _strate(aide: dict[str, Any]) -> tuple[str, bool]:
    portee = PORTEES.get(aide.get("categorie") or "", "nationale")
    familles = aide.get("familles") or []
    if familles:
        restauration = "restauration_bati" in familles
    else:
        texte = f"{aide.get('nom') or ''} {aide.get('description') or ''}".lower()
        restauration = "restaur" in texte
    return portee, restauration


def _sources(slug: str) -> list[str]:
    dossier = SOURCES / slug
    if not dossier.is_dir():
        return []
    return sorted(p.name for p in dossier.iterdir() if not p.name.endswith(".meta.yaml"))


def tirer(_: argparse.Namespace) -> int:
    echecs = {p.name.removesuffix(".yaml.echec") for p in AIDES.glob("*.yaml.echec")}
    population: dict[tuple[str, bool], list[str]] = {}
    strates: dict[str, tuple[str, bool]] = {}
    for f in sorted(AIDES.glob("*.yaml")):
        aide = yaml.safe_load(f.read_text(encoding="utf-8"))
        slug = aide["slug"]
        strates[slug] = _strate(aide)
        if slug in FIXES or slug in echecs or not _sources(slug):
            continue
        population.setdefault(strates[slug], []).append(slug)
    rng = random.Random(GRAINE)
    choisies = [{"slug": s, "strate": strates[s], "origine": "banc du 2026-10-07"} for s in FIXES]
    for strate, n in A_TIRER.items():
        for slug in rng.sample(population[strate], n):
            choisies.append(
                {
                    "slug": slug,
                    "strate": strate,
                    "origine": f"tirage, {n} sur {len(population[strate])}",
                }
            )
    for c in choisies:
        c["sources"] = _sources(c["slug"])
        c["strate"] = {"portee": c["strate"][0], "restauration": c["strate"][1]}
    dossier = _dossier_neuf("banc-x")
    (dossier / "aides.json").write_text(
        json.dumps(
            {
                "graine": GRAINE,
                "population": {
                    f"{p}, {'restauration' if r else 'autre'}": len(v)
                    for (p, r), v in population.items()
                },
                "aides": choisies,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(dossier)
    for c in choisies:
        print(c["slug"], c["strate"], c["origine"], len(c["sources"]), "fichiers")
    return 0


def verifier_extraction(chemin: Path, faits_proposes: Path | None = None) -> dict[str, Any]:
    """Les contrôles de forme et de citation d'une extraction, sans rien écrire."""
    rapport: dict[str, Any] = {"fichier": str(chemin), "erreurs": []}
    erreurs: list[str] = rapport["erreurs"]
    brut = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    try:
        load_aide(chemin)
        rapport["charge"] = True
    except Exception as exc:  # noqa: BLE001 : le rapport dit pourquoi, le banc continue
        rapport["charge"] = False
        erreurs.append(f"chargement : {str(exc)[:500]}")
    proposes: dict[str, Any] = {}
    if faits_proposes is not None and faits_proposes.exists():
        proposes = yaml.safe_load(faits_proposes.read_text(encoding="utf-8")) or {}
        for cle, valeur in proposes.items():
            try:
                FactDef.model_validate(valeur)
            except Exception as exc:  # noqa: BLE001
                erreurs.append(f"fait proposé {cle} invalide : {str(exc)[:300]}")
    connus = set(load_facts()) | set(load_pending_facts()) | set(proposes)
    conditions = brut.get("conditions") or []
    documents, illisibles, _ = load_baselines(brut["slug"])
    citations = {"exacte": 0, "degradee": 0, "baseline_pdf": 0, "absente": 0}
    absentes: list[str] = []
    for c in conditions:
        ident = c.get("id", "?")
        if "effect" not in c:
            erreurs.append(f"{ident} : pas de ligne effect")
        if c.get("kind", "untyped") == "untyped":
            erreurs.append(f"{ident} : untyped")
        if c.get("kind") == "manual_check" and c.get("effect", "gate") == "gate":
            erreurs.append(f"{ident} : manual_check en gate")
        if c.get("fact") and c["fact"] not in connus:
            erreurs.append(f"{ident} : fait inconnu {c['fact']}")
        if c.get("quote"):
            _, correspondance = find_quote_in_any(c["quote"], documents)
            citations[correspondance.status] += 1
            if correspondance.status == "absente":
                absentes.append(ident)
    rapport.update(
        conditions=len(conditions),
        decisives=sum(1 for c in conditions if c.get("effect", "gate") in ("gate", "modulateur")),
        citations=citations,
        citations_absentes=absentes,
        documents=[nom for nom, _, _ in documents],
        pdf_illisibles=illisibles,
        faits_proposes=sorted(proposes),
    )
    return rapport


def verifier(args: argparse.Namespace) -> int:
    rapport = verifier_extraction(Path(args.chemin), Path(args.faits) if args.faits else None)
    print(json.dumps(rapport, ensure_ascii=False, indent=1))
    return 0 if not rapport["erreurs"] and not rapport["citations_absentes"] else 1


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = parseur.add_subparsers(dest="commande", required=True)
    sous.add_parser("tirer").set_defaults(fonction=tirer)
    p = sous.add_parser("verifier")
    p.add_argument("chemin")
    p.add_argument("--faits")
    p.set_defaults(fonction=verifier)
    args = parseur.parse_args()
    return args.fonction(args)


if __name__ == "__main__":
    raise SystemExit(main())
