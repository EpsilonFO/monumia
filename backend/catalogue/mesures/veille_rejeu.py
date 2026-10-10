"""Mesure d'I2 : la nouvelle veille rejouée sur les cas étiquetés du passage du 2026-10-04.

    uv run --no-sync python -m catalogue.mesures.veille_rejeu <dossier> [--plafond 1.0]
    uv run --no-sync python -m catalogue.mesures.veille_rejeu <dossier> --analyser

Mêmes cas que `scripts/veille_benchmark_etage_c.py` : ceux que le banc de Jev
a reconstruits depuis les instantanés (page d'avant, page du passage, YAML
d'avant le passage) et que des agents Claude ont étiquetés (« touche » ou « ne
touche pas » le mandat). Chaque cas passe par `catalogue.veille.etage_c`, à
blanc (aucune écriture : YAML dans un fichier temporaire, ni instantané ni
manifeste), avec le nouveau client, la garde et la zone prudente du registre.
Le journal de l'exécution est écrit dans `<dossier>/journal/`, les appels dans
`<dossier>/appels.jsonl`, le résultat par cas dans `<dossier>/resultats.jsonl`.

Un YAML d'avant que le schéma actuel ne charge plus (3 cas : codes travaux
renommés depuis le passage) est exclu, des deux côtés de la comparaison.

Issue d'un cas « touche » : retouche, case, zone prudente, échec ou escalade
gardent le changement dû ; « inchange » (la référence avancerait) le PERD.
Issue d'un cas « ne touche pas » : une retouche est une FAUSSE RETOUCHE.

`--analyser` compare chaque exécution à l'ancienne veille sur les mêmes cas,
lue dans le cache du banc de l'étage C (`logs/veille-jev/etage-c.jsonl`, garde
à 0,45), et écrit `<dossier>/analyse.md`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from veille_analyze import analyze_all
from veille_benchmark_jev import collect_depuis_snapshots, lire_cas, lire_etiquettes

from aides_schema import load_aide
from catalogue import veille
from catalogue.budget import Budget
from catalogue.journal import Journal, Vue
from catalogue.mesures.stats import wilson
from catalogue.openrouter import Client
from catalogue.registre import BACKEND, charger

JOUR = "2026-10-04"
CACHE_ANCIEN = BACKEND / "data" / "reviews" / "logs" / "veille-jev" / "etage-c.jsonl"
PERDU = "inchange"


def cas_du_banc() -> tuple[list[Any], dict[str, str]]:
    etiquettes = lire_etiquettes(JOUR)
    cas = [
        c
        for c in lire_cas(JOUR)
        if c.origine == "snapshots"
        and c.yaml_avant
        and etiquettes.get(c.id) in ("touche", "ne touche pas")
    ]
    return cas, etiquettes


def executer(dossier: Path, plafond: float) -> int:
    dossier.mkdir(parents=True, exist_ok=False)
    cas, etiquettes = cas_du_banc()
    slugs = sorted({c.slug for c in cas})
    collects = {s: col for s in slugs if (col := collect_depuis_snapshots(s, JOUR))}
    reg = charger()
    client = Client(journal=dossier / "appels.jsonl")
    journal = Journal(dossier / "journal")
    budget = Budget(plafond)
    sortie = (dossier / "resultats.jsonl").open("a", encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        chemins: dict[str, Path] = {}
        aides = {}
        for c in cas:
            if c.slug not in collects:
                continue
            chemin = Path(tmp) / f"{c.slug}.yaml"
            chemin.write_text(c.yaml_avant, encoding="utf-8")
            try:
                aides[c.slug] = load_aide(chemin)
            except Exception as exc:  # schéma changé depuis le passage (codes travaux)
                ligne = {"cas": c.id, "slug": c.slug, "etiquette": etiquettes[c.id]}
                ligne |= {"issue": "non_chargeable", "raison": str(exc)[:200], "cout": 0.0}
                sortie.write(json.dumps(ligne, ensure_ascii=False) + "\n")
                continue
            chemins[c.slug] = chemin
        # Le gabarit se calcule sur toutes les pages du passage, comme au banc.
        analyses = analyze_all(
            aides, {s: collects[s] for s in aides}, today=dt.date.fromisoformat(JOUR)
        )
        ctx = veille.Contexte(
            registre=reg,
            journal=journal,
            vue=Vue([]),
            client=client,
            budget=budget,
            run=f"rejeu-{dossier.name}",
            aujourd_hui=dt.date.fromisoformat(JOUR),
            blobs=dossier / "blobs",
            ecrire=False,
            chemin_yaml=lambda slug: chemins[slug],
        )
        for n, c in enumerate(cas, 1):
            if c.slug not in aides:
                continue
            an = analyses[c.slug]
            res = veille.Resultat(slug=c.slug, statut=an.statut, issue="ok")
            if an.statut == "MAJ_LLM":
                veille.etage_c(ctx, aides[c.slug], an, collects[c.slug], res)
            ligne = {
                "cas": c.id,
                "slug": c.slug,
                "etiquette": etiquettes[c.id],
                "statut": an.statut,
                "issue": res.issue,
                "garde": res.garde,
                "panne": res.panne,
                "champs": res.champs,
                "raison": res.raison[:300],
                "cout": res.cout_usd,
                "cases": [k.sorte for k in res.cases],
            }
            sortie.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            sortie.flush()
            print(f"[{n}/{len(cas)}] {c.slug} {an.statut} → {res.issue} ({budget.depense:.4f} $)")
    sortie.close()
    client.fermer()
    print(f"dépense facturée : {budget.depense:.4f} $, coûts inconnus : {budget.couts_inconnus}")
    return 0


def ancien(cas_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Les rejeux de l'ancienne veille (`or-glm`, `or-glm#2`...) par modèle, puis par cas."""
    par_modele: dict[str, dict[str, Any]] = {}
    for ligne in CACHE_ANCIEN.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        r = json.loads(ligne)
        if r["cas"] in cas_ids and r["modele"].startswith("or-glm") and "+docs" not in r["modele"]:
            par_modele.setdefault(r["modele"], {})[r["cas"]] = r
    return par_modele


def issue_ancienne(r: dict[str, Any], seuil: float = 0.45) -> str:
    if r["etat"] != "inchange":
        return r["etat"]
    if r.get("garde") is not None and r["garde"] >= seuil:
        return "suspect"
    return PERDU


def tableau(nom: str, issues: dict[str, str], etiquettes: dict[str, str]) -> list[str]:
    pos = [c for c in issues if etiquettes[c] == "touche"]
    neg = [c for c in issues if etiquettes[c] == "ne touche pas"]
    perdus = sorted(c for c in pos if issues[c] == PERDU)
    fausses = sorted(c for c in neg if issues[c] in ("retouche", "applique"))
    cp, cn = Counter(issues[c] for c in pos), Counter(issues[c] for c in neg)
    return [
        f"### {nom}",
        "",
        f"- Cas « touche » : {len(pos)} ; issues : {dict(cp)}.",
        f"- Changements perdus : {wilson(len(perdus), len(pos)).texte()} : {', '.join(perdus) or 'aucun'}.",
        f"- Cas « ne touche pas » : {len(neg)} ; issues : {dict(cn)}.",
        f"- Fausses retouches : {wilson(len(fausses), len(neg)).texte()} : {', '.join(fausses) or 'aucune'}.",
        "",
    ]


def analyser(dossiers: list[Path]) -> str:
    cas, etiquettes = cas_du_banc()
    lignes = [f"# Rejeu de la nouvelle veille sur les cas du {JOUR}", ""]
    communs: set[str] | None = None
    executions: dict[str, dict[str, str]] = {}
    couts: dict[str, float] = {}
    for d in dossiers:
        rs = [
            json.loads(x)
            for x in (d / "resultats.jsonl").read_text(encoding="utf-8").splitlines()
            if x
        ]
        # Une escalade de l'analyse (étage B) devient une case, sans appel :
        # le script ne passe que les `MAJ_LLM` à l'étage C.
        executions[d.name] = {
            r["cas"]: "escalade" if r.get("statut") == "ESCALADE_INGESTION" else r["issue"]
            for r in rs
        }
        couts[d.name] = sum(r["cout"] for r in rs)
        ids = {r["cas"] for r in rs if r["issue"] != "non_chargeable"}
        communs = ids if communs is None else communs & ids
    assert communs is not None
    for nom, issues in executions.items():
        lignes += tableau(
            f"nouvelle veille, {nom} ({couts[nom]:.4f} $ facturés)",
            {c: issues[c] for c in communs},
            etiquettes,
        )
    for nom, par_cas in sorted(ancien(communs).items()):
        issues = {c: issue_ancienne(r) for c, r in par_cas.items()}
        lignes += tableau(f"ancienne veille, {nom}, garde 0,45 (cache du banc)", issues, etiquettes)
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m catalogue.mesures.veille_rejeu")
    p.add_argument("dossiers", type=Path, nargs="+")
    p.add_argument("--plafond", type=float, default=1.0)
    p.add_argument("--analyser", action="store_true")
    args = p.parse_args(argv)
    if args.analyser:
        texte = analyser(args.dossiers)
        (args.dossiers[-1] / "analyse.md").write_text(texte + "\n", encoding="utf-8")
        print(texte)
        return 0
    return executer(args.dossiers[0], args.plafond)


if __name__ == "__main__":
    raise SystemExit(main())
