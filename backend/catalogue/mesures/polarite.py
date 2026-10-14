"""Le sens des prédicats du stock : où Jev et le prédicat divergent, et un échantillon à étiqueter.

Commande, depuis backend/ :

    uv run --no-sync --env-file .env.local python -m catalogue.mesures.polarite \\
        --jugements <fichier de jugements>

Juge chaque gate `user_fact` du catalogue sur un fait à réponses
(`catalogue.polarite`), puis écrit :

  - `gates.jsonl` : chaque gate, chaque réponse, ce qu'en fait le prédicat et
    la probabilité de Jev qu'elle remplisse la condition ;
  - `mesure.json` : les désaccords par sens et par seuil ;
  - `a_etiqueter.jsonl` : un échantillon (graine fixe) de réponses, tiré dans
    trois strates (écartée par le prédicat et admise par Jev, l'inverse, et
    accord), présenté SANS le prédicat ni l'avis de Jev, pour deux juges à
    l'aveugle.

Rien n'est modifié dans les aides. Sortie : un dossier neuf sous
data/reviews/logs/refonte/ (hors git).
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from aides_schema import AIDES_DIR, load_all_aides, load_facts, load_pending_facts
from catalogue import polarite as pol
from catalogue.mesures.jeu_e import _dossier_neuf

GRAINE = 20261015
PAR_STRATE = 40
SEUILS = ((0.7, 0.3), (0.8, 0.2), (0.9, 0.1))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jugements", type=Path, required=True)
    args = parser.parse_args()

    faits = {**load_facts(), **load_pending_facts()}
    gates = [
        g
        for slug, aide in load_all_aides(AIDES_DIR).items()
        for c in aide.conditions
        if (g := pol.gate_de(slug, aide.nom, c, faits)) is not None
    ]
    print(f"{len(gates)} gates à juger")
    juge = pol.Juge(args.jugements)
    with ThreadPoolExecutor(8) as pool:
        probas = list(pool.map(juge.juger, gates))

    lignes: list[dict[str, Any]] = []
    for g, p in zip(gates, probas, strict=True):
        if p is None:
            continue
        for r in g.reponses:
            if r.id not in p:
                continue
            lignes.append(
                {
                    "ref": g.ref,
                    "fait": g.condition.fact,
                    "type": g.fait.type,
                    "predicat": g.condition.predicate.root if g.condition.predicate else None,
                    "reponse": r.id,
                    "label": r.label,
                    "admise": r.admise,
                    "p_remplie": p[r.id],
                    "aide": g.nom,
                    "condition": " ".join(g.condition.text.split()),
                    "citation": " ".join((g.condition.quote or "").split())[:600],
                    "question": " ".join(g.fait.question.split()),
                }
            )

    resultats: dict[str, Any] = {
        "gates": len(gates),
        "pannes": sum(p is None for p in probas),
        "reponses_jugees": len(lignes),
        "jev": {"appels": juge.appels, "cout_usd": round(juge.cout_usd, 4)},
        "seuils": {},
    }
    for haut, bas in SEUILS:
        ecarte = [x for x in lignes if not x["admise"] and x["p_remplie"] >= haut]
        passe = [x for x in lignes if x["admise"] and x["p_remplie"] <= bas]
        resultats["seuils"][f"{haut}/{bas}"] = {
            "ecarte_a_tort": len(ecarte),
            "gates_ecarte_a_tort": len({x["ref"] for x in ecarte}),
            "laisse_passer": len(passe),
            "gates_laisse_passer": len({x["ref"] for x in passe}),
            "faits_ecarte_a_tort": Counter(x["fait"] for x in ecarte).most_common(8),
        }

    # Échantillon à étiqueter : trois strates au seuil du milieu.
    haut, bas = SEUILS[1]
    strates = {
        "ecarte_a_tort": [x for x in lignes if not x["admise"] and x["p_remplie"] >= haut],
        "laisse_passer": [x for x in lignes if x["admise"] and x["p_remplie"] <= bas],
        "accord": [
            x
            for x in lignes
            if (x["admise"] and x["p_remplie"] > bas) or (not x["admise"] and x["p_remplie"] < haut)
        ],
    }
    hasard = random.Random(GRAINE)
    echantillon = []
    for nom, xs in strates.items():
        for x in hasard.sample(xs, min(PAR_STRATE, len(xs))):
            echantillon.append({**x, "strate": nom, "taille_strate": len(xs)})
    hasard.shuffle(echantillon)
    for n, x in enumerate(echantillon, 1):
        x["id"] = f"p{n:03d}"
    resultats["echantillon"] = {k: min(PAR_STRATE, len(v)) for k, v in strates.items()}
    resultats["strates"] = {k: len(v) for k, v in strates.items()}

    dossier = _dossier_neuf("polarite")
    (dossier / "mesure.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=2))
    with (dossier / "gates.jsonl").open("w", encoding="utf-8") as f:
        for x in lignes:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with (dossier / "echantillon.jsonl").open("w", encoding="utf-8") as f:
        for x in echantillon:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with (dossier / "a_etiqueter.jsonl").open("w", encoding="utf-8") as f:
        for x in echantillon:
            aveugle = {
                k: x[k] for k in ("id", "aide", "condition", "citation", "question", "label")
            }
            f.write(json.dumps(aveugle, ensure_ascii=False) + "\n")
    print(json.dumps(resultats, ensure_ascii=False, indent=2))
    print(f"Sorties : {dossier}")
    juge.fermer()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
