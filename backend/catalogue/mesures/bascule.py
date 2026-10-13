"""Comparaison de bascule (I8) : l'ancienne et la nouvelle veille sur une même collecte figée.

    uv run --no-sync python -m catalogue.mesures.bascule collecter <dossier>
    <python> -m catalogue.mesures.bascule veille-ancienne <dossier>   # dans une copie jetable
    <python> -m catalogue.mesures.bascule veille-nouvelle <dossier>   # dans une autre copie
    uv run --no-sync python -m catalogue.mesures.bascule comparer <dossier>

`collecter` télécharge une seule fois tout le parc (`veille_collect.collect`, une
seconde par hôte) et garde la collecte dans `<dossier>/collecte.pkl`. Les deux
veilles la rejouent sans rien re-télécharger ni ré-archiver :

- l'ancienne par ses propres fonctions (`analyze_all`, `traiter_acquittements`,
  `run_stage_c` à blanc, garde Jev à 0,45), comme `veille_aides.main` les
  enchaîne, sans écrire de rapport ;
- la nouvelle par `catalogue.veille.passer`, à blanc, avec un journal neuf (la
  référence est donc le dernier instantané archivé, comme pour l'ancienne).

Chacune écrit son verdict par aide dans `<dossier>/ancienne.json` ou
`nouvelle.json` ; `comparer` les croise dans `<dossier>/comparaison.md`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pickle
import secrets
from collections import Counter
from pathlib import Path
from typing import Any

from aides_schema import AIDES_DIR, load_aide


def _aides() -> dict[str, Any]:
    return {p.stem: load_aide(p) for p in sorted(AIDES_DIR.glob("*.yaml"))}


def collecter(dossier: Path) -> int:
    from catalogue.veille_collect import collect

    dossier.mkdir(parents=True, exist_ok=False)
    aides = _aides()
    debut = dt.datetime.now()
    collects = collect(list(aides.values()))
    with (dossier / "collecte.pkl").open("wb") as f:
        pickle.dump({"jour": dt.date.today().isoformat(), "collects": collects}, f)
    n = len({m.url for c in collects.values() for m in c.urls})
    (dossier / "collecte.json").write_text(
        json.dumps(
            {"aides": len(aides), "urls": n, "duree_s": (dt.datetime.now() - debut).total_seconds()}
        ),
        encoding="utf-8",
    )
    print(f"{len(aides)} aides, {n} URL, collecte gardée dans {dossier / 'collecte.pkl'}")
    return 0


def _charger(dossier: Path) -> tuple[dt.date, dict[str, Any], dict[str, Any]]:
    with (dossier / "collecte.pkl").open("rb") as f:
        d = pickle.load(f)
    aides = _aides()
    collects = {s: c for s, c in d["collects"].items() if s in aides}
    return dt.date.fromisoformat(d["jour"]), {s: aides[s] for s in collects}, collects


def veille_ancienne(dossier: Path) -> int:
    import veille_aides
    from veille_analyze import analyze_all
    from veille_arbitre import construire
    from veille_journal import Journal as Log

    jour, aides, collects = _charger(dossier)
    analyses = analyze_all(aides, collects, today=jour)
    manifest = veille_aides.load_manifest()
    veille_aides.traiter_acquittements(analyses, manifest)
    args = veille_aides.parse_args(["--dry-run", "--max-llm", "100000", "--model", "or-glm"])
    arbitre, motif = construire()
    majs = veille_aides.run_stage_c(
        args, aides, analyses, collects, jour, Log(), manifest=manifest, arbitre=arbitre
    )
    sortie = {
        slug: {
            "statut": an.statut,
            "etat": majs[slug].etat if slug in majs else None,
            "raison": (majs[slug].raison if slug in majs else "; ".join(an.raisons))[:300],
            "champs": majs[slug].champs if slug in majs else [],
            "garde": majs[slug].jev.get("garde") if slug in majs else None,
            "cout": (majs[slug].cout_usd + majs[slug].jev_cout_usd) if slug in majs else 0.0,
        }
        for slug, an in analyses.items()
    }
    (dossier / "ancienne.json").write_text(
        json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(
        f"ancienne veille : {Counter(v['etat'] or v['statut'] for v in sortie.values())} ; Jev : {motif}"
    )
    return 0


def veille_nouvelle(dossier: Path) -> int:
    import veille_aides

    from catalogue import veille
    from catalogue.budget import Budget
    from catalogue.journal import Journal, Vue
    from catalogue.openrouter import Client
    from catalogue.registre import charger

    jour, aides, collects = _charger(dossier)
    reg = charger()
    j = Journal(dossier / "journal-nouvelle")
    ctx = veille.Contexte(
        registre=reg,
        journal=j,
        vue=Vue(list(j.lire())),
        client=Client(journal=dossier / "appels-nouvelle.jsonl"),
        budget=Budget(reg.budgets.run.plafond_usd),
        run=f"bascule-{secrets.token_hex(2)}",
        aujourd_hui=jour,
        blobs=dossier / "blobs",
        ecrire=False,
    )
    bilan = veille.passer(ctx, aides, collects, manifeste=veille_aides.MANIFEST_PATH)
    sortie = {
        slug: {
            "statut": r.statut,
            "issue": r.issue,
            "raison": r.raison[:300],
            "champs": r.champs,
            "garde": r.garde,
            "panne": r.panne,
            "cout": r.cout_usd,
            "cases": [c.sorte for c in r.cases],
        }
        for slug, r in bilan.resultats.items()
    }
    (dossier / "nouvelle.json").write_text(
        json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"nouvelle veille : {bilan.compte()} ; {bilan.depense:.4f} $")
    return 0


# Ce que chaque issue fait du changement : écrit, gardé dû (case, zone, panne,
# échec mémorisé côté ancien), ou soldé (la référence avance sans retouche).
SOLDE_ANCIEN = {"inchange"}
SOLDE_NOUVEAU = {"inchange", "rearchivee"}


def comparer(dossier: Path) -> int:
    a = json.loads((dossier / "ancienne.json").read_text(encoding="utf-8"))
    n = json.loads((dossier / "nouvelle.json").read_text(encoding="utf-8"))
    communs = sorted(set(a) & set(n))
    statuts_differents = [s for s in communs if a[s]["statut"] != n[s]["statut"]]
    soumises = [s for s in communs if a[s]["statut"] == "MAJ_LLM"]
    croise = Counter((a[s]["etat"] or "-", n[s]["issue"]) for s in soumises)
    ecrit_a = [s for s in soumises if a[s]["etat"] == "applique"]
    ecrit_n = [s for s in soumises if n[s]["issue"] == "retouche"]
    solde_a = [s for s in soumises if a[s]["etat"] in SOLDE_ANCIEN]
    solde_n = [s for s in soumises if n[s]["issue"] in SOLDE_NOUVEAU]
    cases = Counter(c for s in communs for c in n[s].get("cases", []))
    lignes = [
        f"# Comparaison de bascule, veille ({dt.date.today().isoformat()})",
        "",
        f"- Aides comparées : {len(communs)} ; statut de l'analyse différent : {len(statuts_differents)}"
        + (f" ({', '.join(statuts_differents[:10])})" if statuts_differents else "")
        + ".",
        f"- Soumises au mandat (`MAJ_LLM`) : {len(soumises)}.",
        f"- Retouches écrites : ancienne {len(ecrit_a)}, nouvelle {len(ecrit_n)} ; dans les deux : {len(set(ecrit_a) & set(ecrit_n))}.",
        f"- Changements soldés sans retouche (référence avancée) : ancienne {len(solde_a)}, nouvelle {len(solde_n)}.",
        f"- Cases ouvertes par la nouvelle : {dict(cases)}.",
        f"- Coût : ancienne {sum(v['cout'] for v in a.values()):.4f} $ (estimé au tarif de `veille_llm`, Jev facturé), "
        f"nouvelle {sum(v['cout'] for v in n.values()):.4f} $ (facturé).",
        "",
        "## Issue de l'ancienne (lignes) contre issue de la nouvelle (colonnes), aides soumises au mandat",
        "",
    ]
    colonnes = sorted({c for _, c in croise})
    lignes += [
        "| ancienne \\ nouvelle | " + " | ".join(colonnes) + " |",
        "|---|" + "---|" * len(colonnes),
    ]
    for ligne in sorted({x for x, _ in croise}):
        lignes.append(
            f"| {ligne} | " + " | ".join(str(croise.get((ligne, c), 0)) for c in colonnes) + " |"
        )
    lignes += ["", "## Retouches de l'une sans l'autre", ""]
    for s in sorted(set(ecrit_a) ^ set(ecrit_n)):
        lignes.append(
            f"- `{s}` : ancienne {a[s]['etat']} ({', '.join(a[s]['champs'])}), nouvelle {n[s]['issue']} — {n[s]['raison'][:160]}"
        )
    (dossier / "comparaison.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m catalogue.mesures.bascule")
    p.add_argument(
        "action", choices=["collecter", "veille-ancienne", "veille-nouvelle", "comparer"]
    )
    p.add_argument("dossier", type=Path)
    args = p.parse_args(argv)
    return {
        "collecter": collecter,
        "veille-ancienne": veille_ancienne,
        "veille-nouvelle": veille_nouvelle,
        "comparer": comparer,
    }[args.action](args.dossier)


if __name__ == "__main__":
    raise SystemExit(main())
