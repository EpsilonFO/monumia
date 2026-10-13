"""Banc de la veille de bout en bout : étage C + garde de Jev, sur des cas étiquetés.

La question : combien de changements réels la veille PERD-elle sans aucune
relecture, et combien de fiches retouche-t-elle à tort ? C'est la mesure qui
décide si la veille peut tourner seule chaque semaine.

Les cas et leurs étiquettes sont ceux du banc Jev (`veille_benchmark_jev.py`,
fiche `data/reviews/<jour>-etiquettes-veille-jev.md`). Seuls les cas
reconstruits depuis les snapshots sont rejoués : pour eux, on a la page
d'avant, la page d'après et la fiche d'avant le passage (`yaml_avant`). Chaque
cas passe par `mettre_a_jour` à blanc, exactement comme en production (même
prompt, même validation, même ancrage), puis par la garde si le modèle conclut
« inchangé ».

Issue d'un cas étiqueté « touche » :
    appliqué        la veille a écrit une retouche (juste ou non : non jugé ici)
    escaladé        renvoyé en ré-ingestion, le changement sera revu
    échec           validation refusée : rien d'écrit, le changement reste visible
    suspect         « inchangé » rattrapé par la garde
    PERDU           « inchangé » non rattrapé : la page serait ré-archivée
Issue d'un cas « ne touche pas » : inchangé (juste), suspect (fausse alerte),
appliqué (FAUSSE RETOUCHE), escaladé (ré-ingestion inutile), échec.

    uv run python scripts/veille_benchmark_etage_c.py --modele or-glm --modele or-ds41

Rien n'est écrit dans `data/aides/` ni `data/sources/` (dry-run sur une copie
temporaire de la fiche). Cache : `data/reviews/logs/veille-jev/etage-c.jsonl`.
Rapport : `data/reviews/<date>-benchmark-etage-c.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.decision import ClientDecision, ErreurDecision
from veille_analyze import analyze_all, resume_diff
from veille_arbitre import Arbitre, Seuils, seuils
from veille_benchmark_jev import (
    CACHE_DIR,
    REVIEWS_DIR,
    Cas,
    collect_depuis_snapshots,
    lire_cas,
    lire_etiquettes,
)
from veille_llm import resoudre_modele
from veille_update import MAX_LIGNES_DIFF, mettre_a_jour

from aides_schema import AIDES_DIR, DATA_DIR, load_aide

CACHE = CACHE_DIR / "etage-c.jsonl"
_verrou = threading.Lock()


def cle(modele: str, c: Cas, diff: str) -> str:
    brut = f"{modele}\n{c.id}\n{c.yaml_avant}\n{diff}"
    return hashlib.sha256(brut.encode()).hexdigest()[:20]


def lire_cache() -> dict[str, dict[str, Any]]:
    if not CACHE.exists():
        return {}
    out = {}
    for ligne in CACHE.read_text(encoding="utf-8").splitlines():
        if ligne.strip():
            r = json.loads(ligne)
            out[r["cle"]] = r
    return out


def ecrire_cache(r: dict[str, Any]) -> None:
    with _verrou, CACHE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")


def contextes(cas: list[Cas], jour: str, complet: bool) -> dict[str, tuple[Any, Any]]:
    """{slug: (analyse, collecte)} du passage, chrome calculé sur toutes les pages."""
    slugs = sorted({c.slug for c in cas})
    collects = {
        s: col for s in slugs if (col := collect_depuis_snapshots(s, jour, complet=complet))
    }
    aides = {s: load_aide(AIDES_DIR / f"{s}.yaml") for s in collects}
    analyses = analyze_all(aides, collects)
    return {s: (analyses[s], collects[s]) for s in collects}


def rejouer(
    c: Cas, an: Any, col: Any, modele: str, jour: date, arbitre: Arbitre | None
) -> dict[str, Any]:
    # « or-glm#2 » : deuxième essai du même modèle. Le modèle n'est pas
    # déterministe, et un seul rejeu ne dit pas sa variabilité.
    spec = resoudre_modele(modele.split("#")[0].removesuffix("+docs"))
    with tempfile.TemporaryDirectory() as tmp:
        chemin = Path(tmp) / f"{c.slug}.yaml"
        chemin.write_text(c.yaml_avant, encoding="utf-8")
        aide = load_aide(chemin)
        maj = mettre_a_jour(aide, an, col, spec, aujourd_hui=jour, dry_run=True, chemin=chemin)
        garde = None
        if maj.etat == "inchange" and arbitre is not None:
            diff = resume_diff(an, max_lignes=MAX_LIGNES_DIFF)
            try:
                garde = arbitre.mandat(aide, diff, resume=maj.resume).p
            except ErreurDecision:
                garde = None
    return {
        "etat": maj.etat,
        "resume": maj.resume,
        "raison": maj.raison[:300],
        "champs": maj.champs,
        "etape_echec": maj.etape_echec,
        "cout": maj.cout_usd,
        "garde": garde,
    }


def issue(r: dict[str, Any], seuil_garde: float | None) -> str:
    if r["etat"] != "inchange":
        return {"applique": "appliqué", "escalade": "escaladé", "echec": "échec"}[r["etat"]]
    if seuil_garde is not None and r.get("garde") is not None and r["garde"] >= seuil_garde:
        return "suspect"
    return "inchangé"


def rapport(cas: list[Cas], resultats: dict[str, dict[str, dict[str, Any]]], jour: str) -> str:
    etiquettes = lire_etiquettes(jour)
    s = seuils()
    out = [
        f"# Banc de l'étage C avec la garde ({date.today().isoformat()})",
        "",
        f"Cas du passage du {jour} reconstruits depuis les snapshots, étiquetés dans "
        f"`{jour}-etiquettes-veille-jev.md`. Garde de Jev au seuil "
        f"{s.garde if s.garde is not None else '— (débranchée)'}.",
        "",
        "| modèle | « touche » | appliqués | escaladés | échecs | rattrapés par la garde "
        "| **perdus** | « ne touche pas » | **fausses retouches** | fausses alertes "
        "| ré-ingestions inutiles | coût |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    details: list[str] = []
    for modele, par_cas in resultats.items():
        pos = {k: 0 for k in ("appliqué", "escaladé", "échec", "suspect", "inchangé")}
        neg = dict(pos)
        perdus, fausses = [], []
        cout = 0.0
        for c in cas:
            r = par_cas.get(c.id)
            lab = etiquettes.get(c.id)
            if r is None or lab is None:
                continue
            cout += r["cout"]
            i = issue(r, s.garde)
            if lab == "touche":
                pos[i] += 1
                if i == "inchangé":
                    perdus.append(f"{c.slug} (garde {r.get('garde')})")
            else:
                neg[i] += 1
                if i == "appliqué":
                    fausses.append(f"{c.slug} : {', '.join(r['champs'])} — {r['resume'][:160]}")
        n_pos, n_neg = sum(pos.values()), sum(neg.values())

        def pct(n: int, t: int) -> str:
            return f"{n} ({n / t:.0%})" if t else "0"

        out.append(
            f"| `{modele}` | {n_pos} | {pos['appliqué']} | {pos['escaladé']} | {pos['échec']} "
            f"| {pos['suspect']} | **{pct(pos['inchangé'], n_pos)}** | {n_neg} "
            f"| **{pct(neg['appliqué'], n_neg)}** | {neg['suspect']} | {neg['escaladé']} "
            f"| {cout:.3f} $ |"
        )
        details += [f"## `{modele}`", ""]
        details += ["Changements perdus :", ""] + [f"- {p}" for p in perdus or ["aucun"]] + [""]
        details += ["Fausses retouches :", ""] + [f"- {f}" for f in fausses or ["aucune"]] + [""]
    out += [
        "",
        "Une « fausse retouche » est une fiche modifiée alors que la page n'a rien changé "
        "dans le mandat. Un « appliqué » sur un cas « touche » n'est pas jugé juste ou faux "
        "ici : seule sa présence l'est.",
        "",
        *details,
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="veille_benchmark_etage_c.py")
    p.add_argument(
        "--modele",
        action="append",
        default=[],
        help="alias de veille_llm, répétable ; « or-glm#2 » pour un second essai du même modèle",
    )
    p.add_argument("--jour", default="2026-10-04")
    p.add_argument("--paralleles", type=int, default=4)
    p.add_argument("--sans-garde", action="store_true")
    p.add_argument(
        "--documents-complets",
        action="store_true",
        help="le modèle lit aussi les pages inchangées, comme en production (suffixe « +docs »)",
    )
    args = p.parse_args(argv)
    modeles = args.modele or ["or-glm"]

    etiquettes = lire_etiquettes(args.jour)
    cas = [
        c
        for c in lire_cas(args.jour)
        if c.origine == "snapshots" and c.yaml_avant and c.id in etiquettes
    ]
    ctx = contextes(cas, args.jour, args.documents_complets)
    if args.documents_complets:
        modeles = [f"{m}+docs" for m in modeles]
    cas = [c for c in cas if c.slug in ctx]
    jour = date.fromisoformat(args.jour)
    arbitre = None
    if not args.sans_garde:
        s = seuils()
        arbitre = Arbitre(client=ClientDecision(), seuils=Seuils(garde=s.garde or 0.0))

    cache = lire_cache()
    resultats: dict[str, dict[str, dict[str, Any]]] = {m: {} for m in modeles}
    a_faire = []
    for m in modeles:
        for c in cas:
            an, col = ctx[c.slug]
            k = cle(m, c, resume_diff(an, max_lignes=MAX_LIGNES_DIFF))
            if k in cache:
                resultats[m][c.id] = cache[k]
            else:
                a_faire.append((k, m, c, an, col))
    print(f"{len(cas)} cas × {len(modeles)} modèle(s) : {len(a_faire)} à rejouer")

    def un(item):
        k, m, c, an, col = item
        return k, m, c, rejouer(c, an, col, m, jour, arbitre)

    cout = 0.0
    with ThreadPoolExecutor(args.paralleles) as pool:
        futurs = [pool.submit(un, it) for it in a_faire]
        for n, f in enumerate(as_completed(futurs), 1):
            try:
                k, m, c, r = f.result()
            except Exception as exc:  # un cas en panne ne doit pas perdre les autres
                print(f"  ! {exc}")
                continue
            r = {"cle": k, "modele": m, "cas": c.id, **r}
            ecrire_cache(r)
            resultats[m][c.id] = r
            cout += r["cout"]
            if n % 10 == 0:
                print(f"  {n}/{len(a_faire)} · {cout:.3f} $")

    chemin = REVIEWS_DIR / f"{date.today().isoformat()}-benchmark-etage-c.md"
    chemin.write_text(rapport(cas, resultats, args.jour), encoding="utf-8")
    print(f"rapport : {chemin.relative_to(DATA_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
