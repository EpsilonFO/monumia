"""Hériter le typage des voisines plutôt que le faire juger par l'agent : la mesure.

Commande, depuis backend/ :

    uv run --no-sync python -m catalogue.mesures.heritage_typage --avant 1f5f870c

L'idée testée : à l'ingestion, l'agent ne fait que lister les conditions ; une
condition qui a une famille (voisines confirmées par Jev, typage dominant net,
les règles de `C1-coherence`) prend le typage de sa famille, et l'agent ne
type que les conditions isolées. Aujourd'hui l'agent type tout, et
`espace.controler_aide` ouvre une case quand il s'écarte de la famille.

Deux états du catalogue :

  - AVANT (`--avant`, le commit qui précède l'arbitrage du 2026-10-14) : le
    typage tel que les agents l'avaient écrit. Pour chaque condition, la
    famille est calculée comme le ferait l'ingestion (`Espace.candidates` :
    les 15 plus proches d'AUTRES aides au-dessus du cosinus, puis Jev), sur le
    catalogue d'alors. Quand l'agent et la famille divergent, la vérité est le
    typage d'après l'arbitrage, pour les conditions que Félix a examinées
    (membres des groupes de `2026-10-14-ecarts.yaml` et refs des deux plans).
  - APRÈS (le working tree) : le catalogue arbitré, celui dont hériterait une
    aide neuve. Couverture, et désaccords qui restent, dont les écarts que
    Félix a acceptés (`ecarts-acceptes.yaml`) : l'héritage les écraserait.

Un fait supprimé par l'arbitrage (fusionné dans un autre) est ramené au typage
qu'ont reçu la plupart de ses conditions, des deux côtés : un agent qui avait
choisi `depenses_engagees` n'a pas « tort » parce que le fait a été fusionné
depuis.

Les jugements de Jev sont lus dans une COPIE de `jugements.jsonl` (`--jugements`),
pour ne pas écrire dans le fichier suivi par git ; les paires jamais jugées le
sont (quelques centimes). Sortie : un dossier neuf sous
data/reviews/logs/refonte/ (hors git), `mesure.json` et `desaccords.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tarfile
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml

from aides_schema import AIDES_DIR, load_all_aides
from catalogue import coherence as co
from catalogue.espace import Reglages
from catalogue.mesures.jeu_e import _dossier_neuf
from catalogue.plongements import Plongeur, plus_proches

BACKEND = Path(__file__).resolve().parents[2]
TABLES = BACKEND / "data" / "coherence"
ACCEPTES = BACKEND / "data" / "catalogue" / "coherence" / "ecarts-acceptes.yaml"
PARTS = (0.6, 0.8, 1.0)


def _aides_au_commit(rev: str, dossier: Path) -> dict[str, Any]:
    archive = subprocess.run(
        ["git", "archive", rev, "data/aides"],
        cwd=BACKEND,
        capture_output=True,
        check=True,
    ).stdout
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        tar.extractall(dossier, filter="data")
    return load_all_aides(dossier / "data" / "aides")


def _lignes(aides: dict[str, Any]) -> list[co.Ligne]:
    return [ln for slug, aide in aides.items() for ln in co.lignes_de(slug, aide)]


@dataclass
class Famille:
    candidates: int
    confirmees: list[tuple[int, float]]


def familles(
    lignes: list[co.Ligne], plongeur: Plongeur, juge: co.Juge, r: Reglages
) -> list[Famille]:
    """Les voisines de chaque condition, comme `Espace.famille` les trouve à l'ingestion."""
    vecteurs = plongeur.vecteurs([ln.texte for ln in lignes])
    rangs, scores = plus_proches(vecteurs, vecteurs, r.voisins + 30)
    candidates: list[list[int]] = []
    for i, ligne in enumerate(lignes):
        retenues = []
        for j, s in zip(rangs[i], scores[i], strict=True):
            j = int(j)
            if lignes[j].slug == ligne.slug or s < r.cosinus:
                continue
            retenues.append(j)
            if len(retenues) == r.voisins:
                break
        candidates.append(retenues)

    paires = {tuple(sorted((i, j))) for i, cs in enumerate(candidates) for j in cs}
    neuves = sum(
        1
        for i, j in paires
        if juge.cle(co._etat(*co.paire(lignes[i], lignes[j]))) not in juge.connus
    )
    print(f"  {len(paires)} paires, {neuves} jamais jugées")

    def juger(p: tuple[int, int]) -> tuple[tuple[int, int], float | None]:
        i, j = p
        d = juge.juger(co._etat(*co.paire(lignes[i], lignes[j])))
        return p, None if d is None else d.get(co.MEME, 0.0)

    with ThreadPoolExecutor(co.PARALLELISME_JEV) as pool:
        probas = dict(pool.map(juger, paires))
    sortie = []
    for i, cs in enumerate(candidates):
        conf = []
        for j in cs:
            p = probas[tuple(sorted((i, j)))]
            if p is not None and p >= r.meme:
                conf.append((j, p))
        sortie.append(Famille(len(cs), conf))
    return sortie


def dominantes(
    lignes: list[co.Ligne], fams: list[Famille], r: Reglages, part: float
) -> list[co.Dominante | None]:
    return [
        co.dominante(ln, [(lignes[j], p) for j, p in f.confirmees], r.min_voisines, part)
        for ln, f in zip(lignes, fams, strict=True)
    ]


def table_fusions(avant: list[co.Ligne], apres: dict[str, co.Ligne], faits_supprimes: set[str]):
    """Typage d'un fait supprimé → typage que la plupart de ses conditions ont reçu."""
    vers: dict[co.Typage, Counter[co.Typage]] = {}
    for ln in avant:
        if ln.typage[2] in faits_supprimes:
            vers.setdefault(ln.typage, Counter())[apres[ln.ref].typage] += 1
    return {t: c.most_common(1)[0][0] for t, c in vers.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--avant", required=True, help="commit qui précède l'arbitrage")
    parser.add_argument("--jugements", type=Path, required=True, help="copie de jugements.jsonl")
    args = parser.parse_args()

    r = Reglages.depuis()
    plongeur = Plongeur()
    juge = co.Juge(fichier=args.jugements)

    with tempfile.TemporaryDirectory() as tmp:
        avant = _lignes(_aides_au_commit(args.avant, Path(tmp)))
    apres_l = _lignes(load_all_aides(AIDES_DIR))
    apres = {ln.ref: ln for ln in apres_l}
    assert [ln.ref for ln in avant] == [ln.ref for ln in apres_l], "conditions différentes"

    examinees: set[str] = set()
    for nom in ("2026-10-14-plan.yaml", "2026-10-14-plan-anteriorite.yaml"):
        examinees |= {e["ref"] for e in yaml.safe_load((TABLES / nom).read_text())}
    ecarts = yaml.safe_load((TABLES / "2026-10-14-ecarts.yaml").read_text())
    examinees |= {m["ref"] for g in ecarts["groupes"] for m in g["membres"]}
    acceptes = {a["ref"] for a in yaml.safe_load(ACCEPTES.read_text())["acceptes"]}

    faits_avant = {ln.typage[2] for ln in avant if ln.condition.kind == "user_fact"}
    faits_apres = {ln.typage[2] for ln in apres_l if ln.condition.kind == "user_fact"}
    fusion = table_fusions(avant, apres, faits_avant - faits_apres)

    def norm(t: co.Typage) -> co.Typage:
        return fusion.get(t, t)

    def juste(t: co.Typage, ref: str) -> bool:
        final = apres[ref]
        return co.concorde(final, norm(t))

    print("Avant l'arbitrage :")
    fam_avant = familles(avant, plongeur, juge, r)
    print("Après l'arbitrage :")
    fam_apres = familles(apres_l, plongeur, juge, r)

    resultats: dict[str, Any] = {
        "conditions": len(avant),
        "examinees": len(examinees),
        "fusions": {co.libelle(a): co.libelle(b) for a, b in fusion.items()},
        "jev": {"appels": juge.appels, "cout_usd": round(juge.cout_usd, 4)},
        "avant": {},
        "apres": {},
    }
    desaccords: list[dict[str, Any]] = []

    # Vérité : erreurs de l'agent parmi les conditions examinées.
    erreurs_agent = {ln.ref for ln in avant if ln.ref in examinees and not juste(ln.typage, ln.ref)}
    resultats["erreurs_agent_examinees"] = len(erreurs_agent)

    for part in PARTS:
        doms = dominantes(avant, fam_avant, r, part)
        c: Counter[str] = Counter()
        for ln, d in zip(avant, doms, strict=True):
            if d is None:
                c["isolee"] += 1
                if ln.ref in erreurs_agent:
                    c["erreur_agent_isolee"] += 1
                continue
            c["famille"] += 1
            if co.concorde(ln, d.attendu):
                c["accord"] += 1
                if ln.ref in erreurs_agent:
                    c["accord_mais_faux"] += 1
                continue
            c["desaccord"] += 1
            if ln.ref not in examinees:
                verdict = "non_examine"
            else:
                a, v = juste(ln.typage, ln.ref), juste(d.attendu, ln.ref)
                verdict = "les_deux" if a and v else "agent" if a else "voisines" if v else "aucun"
            c[f"desaccord_{verdict}"] += 1
            if part == PARTS[0]:
                desaccords.append(
                    {
                        "ref": ln.ref,
                        "agent": co.libelle(ln.typage),
                        "voisines": co.libelle(d.attendu),
                        "part": d.part,
                        "final": co.libelle(apres[ln.ref].typage),
                        "verdict": verdict,
                        "texte": ln.texte[:300],
                    }
                )
        resultats["avant"][str(part)] = dict(c)

        doms = dominantes(apres_l, fam_apres, r, part)
        c = Counter()
        for ln, d in zip(apres_l, doms, strict=True):
            if d is None:
                c["isolee"] += 1
                continue
            c["famille"] += 1
            if co.concorde(ln, d.attendu):
                c["accord"] += 1
            else:
                c["desaccord"] += 1
                c["desaccord_accepte" if ln.ref in acceptes else "desaccord_autre"] += 1
        resultats["apres"][str(part)] = dict(c)

    # Couverture par kind, après l'arbitrage, au réglage du registre.
    doms = dominantes(apres_l, fam_apres, r, r.part_dominante)
    par_kind: dict[str, Counter[str]] = {}
    for ln, d in zip(apres_l, doms, strict=True):
        cle = f"{ln.condition.kind}/{ln.condition.effect}"
        par_kind.setdefault(cle, Counter())["famille" if d else "isolee"] += 1
    resultats["couverture_par_kind_apres"] = {
        k: dict(v) for k, v in sorted(par_kind.items(), key=lambda kv: -sum(kv[1].values()))
    }

    # Distribution du nombre de voisines confirmées, après l'arbitrage.
    resultats["voisines_confirmees_apres"] = dict(
        sorted(Counter(min(len(f.confirmees), 10) for f in fam_apres).items())
    )

    dossier = _dossier_neuf("heritage-typage")
    (dossier / "mesure.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=2))
    with (dossier / "desaccords.jsonl").open("w", encoding="utf-8") as f:
        for d in desaccords:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(json.dumps(resultats, ensure_ascii=False, indent=2))
    print(f"Sorties : {dossier}")
    juge.fermer()
    plongeur.fermer()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
