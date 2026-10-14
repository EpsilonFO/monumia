"""La relecture du sens des prédicats : consolider les juges, corriger les aides, mesurer Jev.

Commandes, depuis backend/ (le dossier est `<mesure>/relecture`, cf. `polarite_jeux`) :

    uv run --no-sync python -m catalogue.mesures.polarite_relecture consolider <dossier>
    uv run --no-sync python -m catalogue.mesures.polarite_relecture corriger <dossier>
    uv run --no-sync --env-file .env.local python -m catalogue.mesures.polarite_relecture \\
        evaluer <dossier> --jeu diagnostic --jugements <fichier>

`consolider` réunit les deux juges de chaque lot (`juge-<lot>-<1|2>.json`) et
l'arbitre (`arbitre.json`, réponses où ils divergent) en `etiquettes.json`,
clé `<slug>#<condition>`. Tant qu'une divergence n'est pas arbitrée, il écrit
`a_arbitrer.jsonl` et s'arrête.

`corriger` écrit, pour `scripts/appliquer_typages.py`, le plan qui rend chaque
prédicat conforme aux étiquettes : une réponse étiquetée `remplie` doit être
admise, `non_remplie` écartée ; une réponse `indetermine` garde le sort que lui
fait le prédicat actuel. L'opérateur est gardé : `in`/`eq` deviennent un `in`
des réponses admises, `not_in`/`none_in` gardent leur forme sur les réponses
écartées. Laissées de côté et listées : un combinateur, un `neq`, et une gate
qui n'écarterait plus personne (toutes ses réponses admises).

`evaluer` juge les gates d'un jeu avec la consigne courante de Jev
(`catalogue.polarite`) et compare à leurs étiquettes : précision et rappel du
signal « le prédicat écarte une réponse que le texte admet », et du signal
inverse. Le jeu `controle` ne se lit qu'une fois la consigne figée.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import yaml

from aides_schema import AIDES_DIR, load_all_aides, load_facts, load_pending_facts
from catalogue import polarite as pol
from catalogue import registre as registre_mod

REMPLIE, NON, INDET = "remplie", "non_remplie", "indetermine"


def _jeux(dossier: Path) -> dict[str, Any]:
    return json.loads((dossier / "jeux.json").read_text(encoding="utf-8"))


def consolider(dossier: Path) -> int:
    jeux = _jeux(dossier)
    lots = sorted(dossier.glob("lot-*.jsonl"))
    items = {
        json.loads(li)["id"]: json.loads(li)
        for lot in lots
        for li in lot.read_text(encoding="utf-8").splitlines()
    }
    j1: dict[str, Any] = {}
    j2: dict[str, Any] = {}
    for lot in lots:
        n = lot.stem.split("-")[1]
        j1 |= json.loads((dossier / f"juge-{n}-1.json").read_text(encoding="utf-8"))
        j2 |= json.loads((dossier / f"juge-{n}-2.json").read_text(encoding="utf-8"))
    arbitre_f = dossier / "arbitre.json"
    arbitre = json.loads(arbitre_f.read_text(encoding="utf-8")) if arbitre_f.exists() else {}
    etiquettes: dict[str, dict[str, str]] = {}
    a_arbitrer = []
    accords = total = 0
    for gid, it in items.items():
        ref = jeux["ids"][gid]
        etiquettes[ref] = {}
        for r in it["reponses"]:
            a, b = j1[gid][r["id"]], j2[gid][r["id"]]
            total += 1
            if a == b:
                accords += 1
                etiquettes[ref][r["id"]] = a
            elif r["id"] in arbitre.get(gid, {}):
                etiquettes[ref][r["id"]] = arbitre[gid][r["id"]]
            else:
                a_arbitrer.append((gid, r["id"], a, b))
    print(f"accord des juges : {accords}/{total} réponses")
    if a_arbitrer:
        with (dossier / "a_arbitrer.jsonl").open("w", encoding="utf-8") as f:
            for gid in sorted({x[0] for x in a_arbitrer}):
                it = items[gid]
                f.write(
                    json.dumps(
                        {
                            **{
                                k: it[k]
                                for k in ("id", "aide", "condition", "citation", "question")
                            },
                            "a_trancher": [
                                {
                                    "id": rid,
                                    "label": next(
                                        r["label"] for r in it["reponses"] if r["id"] == rid
                                    ),
                                    "juge_1": a,
                                    "juge_2": b,
                                }
                                for g, rid, a, b in a_arbitrer
                                if g == gid
                            ],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        print(f"{len(a_arbitrer)} réponse(s) à arbitrer : {dossier / 'a_arbitrer.jsonl'}")
        return 1
    (dossier / "etiquettes.json").write_text(
        json.dumps(etiquettes, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(etiquettes)} gates étiquetées : {dossier / 'etiquettes.json'}")
    return 0


def _gates(refs: list[str]) -> dict[str, pol.Gate]:
    faits = {**load_facts(), **load_pending_facts()}
    aides = load_all_aides(AIDES_DIR)
    sortie = {}
    for ref in refs:
        slug, cid = ref.split("#", 1)
        c = next(c for c in aides[slug].conditions if c.id == cid)
        g = pol.gate_de(slug, aides[slug].nom, c, faits)
        if g is not None:
            sortie[ref] = g
    return sortie


def nouveau_predicat(g: pol.Gate, etiq: dict[str, str]) -> tuple[dict[str, Any] | None, str]:
    """(prédicat conforme aux étiquettes, ou None ; raison si None ou inchangé)."""
    admises = []
    for r in g.reponses:
        e = etiq.get(r.id, INDET)
        if e == REMPLIE or (e == INDET and r.admise):
            admises.append(r.id)
    if [r.id for r in g.reponses if r.admise] == admises:
        return None, "conforme"
    if len(admises) == len(g.reponses):
        return None, "toutes les réponses admises : la gate ne trierait plus personne"
    if not admises:
        return None, "aucune réponse admise : la gate écarterait tout le monde"
    pred = g.condition.predicate.root if g.condition.predicate else None
    if not isinstance(pred, dict) or len(pred) != 1:
        return None, "prédicat composé"
    op = next(iter(pred))
    if g.fait.type == "boolean":
        if op != "eq" or len(admises) != 1:
            return None, f"booléen ({op})"
        valeur = next(o.valeur for o in pol.options(g.fait) if o.id == admises[0])
        return {"eq": valeur}, ""
    if op in ("in", "eq"):
        return {"in": admises}, ""
    if op in ("not_in", "none_in"):
        return {op: [r.id for r in g.reponses if r.id not in admises]}, ""
    return None, f"opérateur `{op}`"


def corriger(dossier: Path) -> int:
    etiquettes = json.loads((dossier / "etiquettes.json").read_text(encoding="utf-8"))
    gates = _gates(sorted(etiquettes))
    plan: list[dict[str, Any]] = []
    laissees: list[str] = []
    raisons: Counter[str] = Counter()
    for ref, g in sorted(gates.items()):
        pred, raison = nouveau_predicat(g, etiquettes[ref])
        if pred is None:
            raisons[raison.split(" (")[0]] += 1
            if raison != "conforme":
                laissees.append(f"{ref} : {raison}")
            continue
        c = g.condition
        entree: dict[str, Any] = {"ref": ref, "kind": c.kind, "effect": c.effect, "fact": c.fact}
        entree["predicate"] = pred
        if c.derogation_possible:
            entree["derogation_possible"] = True
        if c.levier is not None:
            entree["levier"] = c.levier.model_dump(mode="json", exclude_none=True)
        changees = [
            f"« {r.label} » {'admise' if etiquettes[ref][r.id] == REMPLIE else 'écartée'}"
            for r in g.reponses
            if etiquettes[ref].get(r.id, INDET) != INDET
            and (etiquettes[ref][r.id] == REMPLIE) != r.admise
        ]
        entree["motif"] = (
            "sens du prédicat, relu à l'aveugle (deux juges, arbitre) : "
            + ", ".join(changees)
            + "."
        )
        plan.append(entree)
    chemin = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "coherence"
        / "2026-10-15-plan-polarite-relu.yaml"
    )
    entete = (
        "# Plan du 2026-10-15 : prédicats rendus conformes à leur texte, relus à l'aveugle\n"
        "# (deux juges et un arbitre par réponse ; data/reviews/2026-10-14-polarite.md).\n"
        f"# Produit par catalogue/mesures/polarite_relecture.py. {len(plan)} condition(s) ;\n"
        f"# {len(laissees)} laissée(s) de côté, listées en fin de rapport.\n"
    )
    chemin.write_text(
        entete + yaml.safe_dump(plan, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    print(f"{len(plan)} condition(s) au plan : {chemin}")
    print(f"sans changement ou laissées : {dict(raisons)}")
    for li in laissees:
        print(f"  - {li}")
    return 0


def evaluer(dossier: Path, jeu: str, jugements: Path) -> int:
    jeux = _jeux(dossier)["jeux"]
    refs = [r for nom, v in jeux.items() if nom.startswith(jeu) for r in v]
    etiquettes = json.loads((dossier / "etiquettes.json").read_text(encoding="utf-8"))
    gates = _gates(refs)
    juge = pol.Juge(jugements)
    with ThreadPoolExecutor(8) as pool:
        probas = dict(zip(gates, pool.map(juge.juger, gates.values()), strict=True))
    seuils = registre_mod.charger().decisions[pol.DECISION].seuils
    resultats: dict[str, Any] = {
        "jeu": jeu,
        "gates": len(gates),
        "empreinte": pol.EMPREINTE_QUESTIONS,
    }
    for haut, bas in ((0.7, 0.3), (seuils["haut"], seuils["bas"]), (0.9, 0.1)):
        c: Counter[str] = Counter()
        for ref, g in gates.items():
            p = probas[ref]
            if p is None:
                c["pannes"] += 1
                continue
            for r in g.reponses:
                e = etiquettes[ref].get(r.id, INDET)
                if e == INDET or r.id not in p:
                    continue
                faux = (e == REMPLIE) != r.admise
                ecarte = not r.admise
                signal = (ecarte and p[r.id] >= haut) or (r.admise and p[r.id] <= bas)
                sens = "ecarte" if ecarte else "admet"
                c[f"{sens}_faux"] += faux
                c[f"{sens}_signales"] += signal
                c[f"{sens}_signales_justes"] += signal and faux
        resultats[f"{haut}/{bas}"] = {
            **dict(c),
            "precision_ecarte": round(c["ecarte_signales_justes"] / c["ecarte_signales"], 3)
            if c["ecarte_signales"]
            else None,
            "rappel_ecarte": round(c["ecarte_signales_justes"] / c["ecarte_faux"], 3)
            if c["ecarte_faux"]
            else None,
            "precision_admet": round(c["admet_signales_justes"] / c["admet_signales"], 3)
            if c["admet_signales"]
            else None,
            "rappel_admet": round(c["admet_signales_justes"] / c["admet_faux"], 3)
            if c["admet_faux"]
            else None,
        }
    print(json.dumps(resultats, ensure_ascii=False, indent=2))
    juge.fermer()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["consolider", "corriger", "evaluer"])
    parser.add_argument("dossier", type=Path)
    parser.add_argument("--jeu", choices=["diagnostic", "controle"], default="diagnostic")
    parser.add_argument("--jugements", type=Path)
    args = parser.parse_args()
    if args.action == "consolider":
        return consolider(args.dossier)
    if args.action == "corriger":
        return corriger(args.dossier)
    assert args.jugements is not None, "--jugements est requis pour evaluer"
    return evaluer(args.dossier, args.jeu, args.jugements)


if __name__ == "__main__":
    raise SystemExit(main())
