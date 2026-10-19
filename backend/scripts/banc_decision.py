"""Banc des modèles de décision : Jev contre les autres, sur l'entrée au catalogue.

La question posée : un autre modèle de décision servi par l'API Decisions
d'OpenRouter (ScaleDown Classify-1, une autre version de Jev…) trie-t-il les
pages d'aides mieux ou moins bien que Jev 1.13, celui qui tourne ?

Le jeu, les textes et la vérité terrain sont ceux de `benchmark_destinataire.py`
(gardée = `.yaml` dans HEAD, écartée = `.yaml.echec` au motif humain), les
questions celles de la production (`arbitre.QUESTIONS`). Chaque modèle est
rejugé le même jour sur les mêmes textes : le cache `jev.jsonl` du 2026-10-04
a été produit avec quatre questions et des snapshots que la veille a pu
ré-archiver depuis.

Deux adaptations pour les modèles qui ne lisent pas la requête de Jev telle
quelle (`ADAPTATIONS`), mesurées le 2026-10-19 sur Classify-1 :

- l'état doit être du texte : un état JSON est refusé en 400. La doctrine et la
  page sont mises bout à bout sous deux titres, `doctrine` et `page`, que
  l'introduction de la doctrine cite déjà ;
- un `noul` n'y lit pas ses `criteria` (même probabilité, mêmes jetons avec ou
  sans) : leurs deux descriptions passent dans `instructions`.

Les probabilités de deux modèles ne se comparent pas : chaque modèle reçoit ses
propres seuils, réglés sur une moitié du jeu et mesurés sur l'autre, avec la
règle de production (`arbitre.bande`, cohérence des réponses détaillées
comprise).

Une réponse par modèle et par aide, mise en cache dans
`data/reviews/logs/benchmark-destinataire/decision-<modèle>.jsonl` (hors git) :
relancer ne repaie rien.

    uv run python scripts/banc_decision.py --dry-run
    uv run python scripts/banc_decision.py --modele typesafe/jev-1.13 \\
        --modele scaledown/classify-1 --echantillon 40
    uv run python scripts/banc_decision.py --modele typesafe/jev-1.13 \\
        --modele typesafe/jev-1.14 --modele scaledown/classify-1
    uv run python scripts/banc_decision.py      # rapport seul, sur les caches

Ne modifie ni aide ni file : le seul fichier versionné qu'il écrit est le
rapport `data/reviews/<date>-banc-decision.md`.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_destinataire import (
    BACKEND_DIR,
    CACHE_DIR,
    REVIEWS_DIR,
    Cas,
    _moitie,
    _pct,
    _proba,
    auc,
    cas_etiquetes,
    echantillon,
    faire_juger,
    lire_cache,
    scores_jev,
    texte_du_snapshot,
)
from pipeline.decision import ClientDecision
from pipeline.llm import charger_env
from prospection import arbitre

REFERENCE = "typesafe/jev-1.13"

# Part des gardées qu'une règle peut écarter sans recours, et des écartées
# qu'elle peut retenir sans relecture : le budget du registre pour E1.
BUDGET_PERTES = 0.02
BUDGET_ADMISSIONS = 0.10


# --------------------------------------------------------------------------
# Requêtes
# --------------------------------------------------------------------------


def etat_texte(url: str, texte: str) -> str:
    """L'état de production mis à plat, pour un modèle qui ne lit que du texte."""
    e = arbitre.etat(url, texte)
    return f"## doctrine\n\n{e['doctrine']}\n\n## page\n\nURL : {url}\n\n{texte}"


def questions_sans_criteres_noul(questions: dict[str, Any]) -> dict[str, Any]:
    """Les descriptions du oui et du non d'un `noul`, reportées dans la question."""
    sortie: dict[str, Any] = {}
    for cle, q in questions.items():
        if q["type"] == "noul":
            c = q["criteria"]
            q = {
                "type": "noul",
                "instructions": f"{q['instructions']} Oui : {c['true']} Non : {c['false']}",
            }
        sortie[cle] = q
    return sortie


Adaptation = tuple[
    Callable[[str, str], str | dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]
]

ADAPTATIONS: dict[str, Adaptation] = {
    "scaledown/": (etat_texte, questions_sans_criteres_noul),
}


def adaptation(modele: str) -> Adaptation:
    for prefixe, a in ADAPTATIONS.items():
        if modele.startswith(prefixe):
            return a
    return (arbitre.etat, lambda q: q)


def nom_cache(modele: str) -> str:
    return "decision-" + modele.replace("/", "_")


def juge(client: ClientDecision) -> Callable[[Cas], dict[str, Any]]:
    faire_etat, adapter = adaptation(client.modele)
    questions = adapter(arbitre.QUESTIONS)

    def juger(cas: Cas) -> dict[str, Any]:
        url, texte = texte_du_snapshot(cas.slug)
        d = client.decider(faire_etat(url, texte), questions)
        return {
            "modele": d.modele,
            "reponses": {k: d.brut["answers"][k] for k in questions},
            "cout_usd": d.cout_usd,
            "jetons_entree": d.jetons_entree,
            "latence_s": round(d.latence_s, 3),
        }

    return juger


# --------------------------------------------------------------------------
# Règle de production
# --------------------------------------------------------------------------


def lecture(r: dict[str, Any]) -> tuple[float, bool]:
    """(deposable, la structure écarte), comme `arbitre.arbitrer` les lit."""
    rep = r["reponses"]

    def choix(q: str) -> str:
        probas = rep[q].get("probabilities") or {}
        return rep[q].get("choice") or (max(probas, key=probas.get) if probas else "")

    ecarte = arbitre.structure_ecarte(
        choix("destinataire"), choix("objet"), _proba(rep["dispositif"], "true")
    )
    return _proba(rep["deposable"], "true"), ecarte


Point = tuple[float, bool, bool]  # deposable, structure écarte, gardée


def issue(p: Point, s: arbitre.Seuils) -> str:
    return arbitre.bande(p[0], p[1], s)


def regler(points: list[Point]) -> arbitre.Seuils:
    """Les seuils les plus ouverts qui tiennent le budget sur `points`.

    `bas` : le plus haut seuil tel que les gardées écartées pèsent au plus
    `BUDGET_PERTES` des gardées. `haut` : le plus bas tel que les écartées
    retenues pèsent au plus `BUDGET_ADMISSIONS` des écartées. Les deux se
    règlent séparément : une page n'est écartée que si la structure écarte,
    retenue que si elle n'écarte pas.
    """
    n_g = sum(g for *_, g in points) or 1
    n_e = (len(points) - sum(g for *_, g in points)) or 1
    candidats = sorted({p for p, *_ in points} | {0.0, 1.0})
    bas = 0.0
    for c in candidats:
        if sum(p < c and e and g for p, e, g in points) / n_g <= BUDGET_PERTES:
            bas = c
    haut = 1.0
    for c in reversed(candidats):
        if sum(p > c and not e and not g for p, e, g in points) / n_e <= BUDGET_ADMISSIONS:
            haut = c
    return arbitre.Seuils(bas=bas, haut=max(haut, bas))


def compter(points: list[Point], s: arbitre.Seuils) -> dict[str, int]:
    n = {"gardees": 0, "ecartees": 0, "perdues": 0, "admises": 0, "milieu": 0, "auto": 0}
    for p in points:
        g = p[2]
        n["gardees" if g else "ecartees"] += 1
        b = issue(p, s)
        if b == "milieu":
            n["milieu"] += 1
        elif b == "ecartee" and g:
            n["perdues"] += 1
        elif b == "retenue" and not g:
            n["admises"] += 1
        else:
            n["auto"] += 1
    return n


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------


def _ligne_regle(nom: str, n: dict[str, int], s: arbitre.Seuils) -> str:
    total = n["gardees"] + n["ecartees"]
    return (
        f"| {nom} | {s.bas:.3f} / {s.haut:.3f} | {_pct(n['perdues'], n['gardees'])} "
        f"| {_pct(n['admises'], n['ecartees'])} | {_pct(n['milieu'], total)} "
        f"| {_pct(n['auto'], total)} |"
    )


def rapport(cas: list[Cas], verdicts: dict[str, dict[str, dict[str, Any]]]) -> str:
    par_slug = {c.slug: c for c in cas}
    modeles = [m for m in verdicts if verdicts[m]]
    communs = sorted(s for s in par_slug if all(s in verdicts[m] for m in modeles))
    n_g = sum(par_slug[s].garde for s in communs)
    lignes = [
        f"# Banc des modèles de décision, {date.today().isoformat()}",
        "",
        "Entrée au catalogue (décision `E1-entree`) : questions et doctrine de production "
        "(`arbitre.QUESTIONS`), jeu et vérité terrain du banc destinataire "
        "(`benchmark_destinataire.py`). Chaque modèle a jugé les mêmes textes.",
        "",
        f"Cas jugés par tous : **{len(communs)}** ({n_g} gardées, {len(communs) - n_g} "
        f"écartées), sur {len(cas)} cas étiquetés.",
        "",
        "Adaptations : "
        + "; ".join(
            f"`{p}*` état aplati en texte, critères des `noul` reportés dans la question"
            for p in ADAPTATIONS
        )
        + ".",
        "",
    ]
    if not communs:
        return "\n".join(lignes)

    pts = {m: {s: (*lecture(verdicts[m][s]), par_slug[s].garde) for s in communs} for m in modeles}

    # --- Séparation : rien ne dépend d'un seuil
    lignes += [
        "## Séparation des gardées et des écartées",
        "",
        "AUC : probabilité qu'une gardée tirée au hasard soit mieux notée qu'une écartée. "
        "`structure` combine destinataire, objet et dispositif (`scores_jev`).",
        "",
        "| modèle | AUC `deposable` | AUC `structure` | coût | coût / 1 000 pages | jetons médians | latence médiane |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for m in modeles:
        rs = [verdicts[m][s] for s in communs]
        dep = [(pts[m][s][0], pts[m][s][2]) for s in communs]
        stru = [(scores_jev(verdicts[m][s])["structure"], par_slug[s].garde) for s in communs]
        cout = sum(r.get("cout_usd") or 0 for r in rs)
        jetons = statistics.median(r.get("jetons_entree") or 0 for r in rs)
        lat = statistics.median(r.get("latence_s") or 0 for r in rs)
        lignes.append(
            f"| `{m}` | {auc(dep):.3f} | {auc(stru):.3f} | ${cout:.3f} "
            f"| ${1000 * cout / len(rs):.3f} | {jetons:.0f} | {lat:.2f} s |"
        )
    lignes.append("")

    # --- Règle de production, seuils propres à chaque modèle
    a = [s for s in communs if _moitie(s) == 0]
    b = [s for s in communs if _moitie(s) == 1]
    lignes += [
        "## Règle de production, seuils réglés pour chaque modèle",
        "",
        f"Seuils réglés sur une moitié du jeu ({len(a)} cas) au budget du registre "
        f"(au plus {BUDGET_PERTES:.0%} des gardées écartées, {BUDGET_ADMISSIONS:.0%} des "
        f"écartées retenues), puis mesurés sur l'autre moitié ({len(b)} cas). Une page "
        "n'est tranchée que si `deposable` et les réponses détaillées concordent "
        "(`arbitre.bande`). « Milieu » : la page part au LLM de lecture.",
        "",
        "| modèle | seuils bas / haut | gardées écartées | écartées retenues | milieu | tranchées justes |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for m in modeles:
        s = regler([pts[m][x] for x in a])
        lignes.append(_ligne_regle(f"`{m}`", compter([pts[m][x] for x in b], s), s))
    lignes += [
        "",
        "Les mêmes seuils réglés sur le jeu entier et mesurés dessus (optimiste, mais sur "
        "deux fois plus de cas) :",
        "",
        "| modèle | seuils bas / haut | gardées écartées | écartées retenues | milieu | tranchées justes |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for m in modeles:
        tous = list(pts[m].values())
        s = regler(tous)
        lignes.append(_ligne_regle(f"`{m}`", compter(tous, s), s))
    lignes += [
        "",
        f"Pour mémoire, les seuils de production ({arbitre.SEUIL_BAS} / {arbitre.SEUIL_HAUT}, "
        "réglés pour Jev 1.13) appliqués tels quels :",
        "",
        "| modèle | seuils bas / haut | gardées écartées | écartées retenues | milieu | tranchées justes |",
        "|---|---|---:|---:|---:|---:|",
    ]
    prod = arbitre.Seuils()
    for m in modeles:
        lignes.append(_ligne_regle(f"`{m}`", compter(list(pts[m].values()), prod), prod))
    lignes.append("")

    # --- Calibration
    lignes += [
        "## Calibration de `deposable`",
        "",
        "Part de gardées dans chaque tranche de probabilité annoncée (cas / part).",
        "",
        "| tranche | " + " | ".join(f"`{m}`" for m in modeles) + " |",
        "|---|" + "---:|" * len(modeles),
    ]
    for i in range(10):
        lo, hi = i / 10, (i + 1) / 10
        cols = []
        for m in modeles:
            t = [g for p, _, g in pts[m].values() if lo <= p < hi or (i == 9 and p == 1.0)]
            cols.append(f"{len(t)} / {100 * sum(t) / len(t):.0f} %" if t else "")
        lignes.append(f"| {lo:.1f} à {hi:.1f} | " + " | ".join(cols) + " |")
    lignes.append("")

    # --- Désaccords avec la référence
    if REFERENCE in modeles:
        for m in modeles:
            if m == REFERENCE:
                continue
            ref, aut = pts[REFERENCE], pts[m]
            s_ref, s_aut = regler(list(ref.values())), regler(list(aut.values()))
            pertes_ref = {x for x in communs if issue(ref[x], s_ref) == "ecartee" and ref[x][2]}
            pertes_aut = {x for x in communs if issue(aut[x], s_aut) == "ecartee" and aut[x][2]}
            lignes += [
                f"## `{m}` face à `{REFERENCE}`",
                "",
                "Gardées écartées à tort, seuils réglés sur le jeu entier : "
                f"{len(pertes_ref & pertes_aut)} par les deux, {len(pertes_ref - pertes_aut)} "
                f"par `{REFERENCE}` seul, {len(pertes_aut - pertes_ref)} par `{m}` seul.",
                "",
            ]
            if pertes_aut - pertes_ref:
                lignes += [
                    f"Perdues par `{m}` seul : "
                    + ", ".join(
                        f"`{x}` ({aut[x][0]:.2f} contre {ref[x][0]:.2f})"
                        for x in sorted(pertes_aut - pertes_ref)
                    ),
                    "",
                ]
            if pertes_ref - pertes_aut:
                lignes += [
                    f"Perdues par `{REFERENCE}` seul : "
                    + ", ".join(
                        f"`{x}` ({ref[x][0]:.2f} contre {aut[x][0]:.2f})"
                        for x in sorted(pertes_ref - pertes_aut)
                    ),
                    "",
                ]
    return "\n".join(lignes)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="banc_decision.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--modele", action="append", default=[], help="modèle de décision à faire juger ; répétable"
    )
    p.add_argument("--echantillon", type=int, help="n cas équilibrés au lieu du jeu entier")
    p.add_argument("--parallele", type=int, default=8)
    p.add_argument("--dry-run", action="store_true", help="décrire le jeu, n'appeler personne")
    args = p.parse_args(argv)

    charger_env()
    cas = cas_etiquetes()
    if args.echantillon:
        cas = echantillon(cas, args.echantillon)
    n_g = sum(c.garde for c in cas)
    print(f"{len(cas)} cas : {n_g} gardées, {len(cas) - n_g} écartées")
    if args.dry_run:
        for m in args.modele:
            print(f"{m} : {len(lire_cache(nom_cache(m)))} réponses en cache")
        return 0

    for m in args.modele:
        client = ClientDecision(m)
        try:
            faire_juger(nom_cache(m), juge(client), cas, args.parallele)
        finally:
            client.fermer()

    slugs = {c.slug for c in cas}
    verdicts: dict[str, dict[str, dict[str, Any]]] = {}
    for f in sorted(CACHE_DIR.glob("decision-*.jsonl")):
        rs = {s: r for s, r in lire_cache(f.stem).items() if s in slugs}
        if rs:
            modele = next(iter(rs.values()))["modele"]
            # Le nom servi porte une date (`…-20260917`) : on garde le nom demandé.
            verdicts[f.stem.removeprefix("decision-").replace("_", "/", 1)] = rs
            print(f"{f.stem} : {len(rs)} cas, servi par {modele}")
    texte = rapport(cas, verdicts)
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    chemin = REVIEWS_DIR / f"{date.today().isoformat()}-banc-decision.md"
    chemin.write_text(texte + "\n", encoding="utf-8")
    print(f"rapport : {chemin.relative_to(BACKEND_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
