"""Les jeux de la relecture du sens des prédicats : corriger le stock, et améliorer Jev sans surapprendre.

Commande, depuis backend/ :

    uv run --no-sync python -m catalogue.mesures.polarite_jeux <dossier de catalogue.mesures.polarite>

À partir d'une mesure de polarité (`gates.jsonl`), constitue :

  - `CORRIGER` : les gates où Jev signale un prédicat qui écarte une réponse
    que le texte admet (seuil `haut` de `P1-polarite`). Toutes sont relues : les
    étiquettes corrigent les aides, réponse par réponse ;
  - un tirage de `ALEATOIRES` gates du reste du stock, hors celles déjà
    étiquetées par l'échantillon de la mesure ;
  - une coupe `diagnostic` / `controle`, PAR AIDE (deux conditions d'une même
    aide ne se retrouvent jamais de part et d'autre : leurs formulations se
    ressemblent). La moitié des gates à corriger va au diagnostic, l'autre au
    contrôle avec tout le tirage aléatoire.

Le diagnostic sert à lire les erreurs de Jev et à retoucher sa consigne. Le
contrôle ne se lit pas avant que la nouvelle consigne soit figée : il sert à
comparer les deux versions une seule fois. `jeux.json` (refs et appartenance)
est écrit à part des lots à étiqueter, qui ne disent ni le jeu, ni le
prédicat, ni l'avis de Jev.

Une gate à étiqueter porte toutes ses réponses : le juge dit, pour chacune, si
le texte de la condition l'admet. Sortie : `<mesure>/relecture/`.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from aides_schema import AIDES_DIR, load_all_aides, load_facts, load_pending_facts
from catalogue import polarite as pol
from catalogue import registre as registre_mod

GRAINE = 20261016
ALEATOIRES = 60
PAR_LOT = 40


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mesure", type=Path)
    args = parser.parse_args()
    haut = registre_mod.charger().decisions[pol.DECISION].seuils["haut"]

    lignes = [
        json.loads(li)
        for li in (args.mesure / "gates.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    deja = {
        json.loads(li)["ref"]
        for li in (args.mesure / "echantillon.jsonl").read_text(encoding="utf-8").splitlines()
    }
    a_corriger = sorted({x["ref"] for x in lignes if not x["admise"] and x["p_remplie"] >= haut})
    reste = sorted({x["ref"] for x in lignes} - set(a_corriger) - deja)
    hasard = random.Random(GRAINE)
    aleatoires = sorted(hasard.sample(reste, min(ALEATOIRES, len(reste))))

    # La coupe, par aide, sur les seules gates à corriger.
    par_aide: dict[str, list[str]] = defaultdict(list)
    for ref in a_corriger:
        par_aide[ref.split("#", 1)[0]].append(ref)
    aides_c = sorted(par_aide)
    hasard.shuffle(aides_c)
    moitie = set(aides_c[: len(aides_c) // 2])
    # Une aide du tirage aléatoire qui a aussi une gate au diagnostic : sa gate
    # aléatoire quitte le contrôle, pour ne pas lire deux fois la même aide.
    aleatoires = [r for r in aleatoires if r.split("#", 1)[0] not in moitie]
    jeux = {
        "diagnostic": sorted(r for r in a_corriger if r.split("#", 1)[0] in moitie),
        "controle_a_corriger": sorted(r for r in a_corriger if r.split("#", 1)[0] not in moitie),
        "controle_aleatoire": aleatoires,
    }

    faits = {**load_facts(), **load_pending_facts()}
    aides = load_all_aides(AIDES_DIR)
    refs = [r for v in jeux.values() for r in v]
    hasard.shuffle(refs)
    items: list[dict[str, Any]] = []
    for n, ref in enumerate(refs, 1):
        slug, cid = ref.split("#", 1)
        aide = aides[slug]
        c = next(c for c in aide.conditions if c.id == cid)
        g = pol.gate_de(slug, aide.nom, c, faits)
        assert g is not None, ref
        e = pol.etat(g)
        items.append(
            {
                "id": f"g{n:03d}",
                **{k: e[k] for k in ("aide", "condition", "question") if k in e},
                "citation": e.get("citation", ""),
                "reponses": [{"id": r.id, "label": r.label} for r in g.reponses],
            }
        )
    ids = {it["id"]: ref for it, ref in zip(items, refs, strict=True)}

    sortie = args.mesure / "relecture"
    sortie.mkdir(exist_ok=True)
    (sortie / "jeux.json").write_text(
        json.dumps({"jeux": jeux, "ids": ids}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    for k in range(0, len(items), PAR_LOT):
        lot = items[k : k + PAR_LOT]
        with (sortie / f"lot-{k // PAR_LOT + 1}.jsonl").open("w", encoding="utf-8") as f:
            for it in lot:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(
        f"{len(items)} gates : diagnostic {len(jeux['diagnostic'])}, contrôle à corriger "
        f"{len(jeux['controle_a_corriger'])}, contrôle aléatoire {len(jeux['controle_aleatoire'])} ; "
        f"{sum(len(it['reponses']) for it in items)} réponses ; "
        f"{(len(items) + PAR_LOT - 1) // PAR_LOT} lots dans {sortie}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
