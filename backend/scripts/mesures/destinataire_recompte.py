"""Recompte adverse de la note `docs/refonte-pipeline/notes/destinataire.md`.

    cd backend && PYTHONDONTWRITEBYTECODE=1 uv run python scripts/mesures/destinataire_recompte.py

Écrit indépendamment de `scripts/mesures/destinataire.py` (non importé) : les
étiquettes sont reconstruites depuis git (`git ls-tree`, `git show`), les
verdicts des modèles lus dans les caches copiés sous
`data/reviews/logs/benchmark-destinataire/`. Aucun appel réseau, aucun modèle.
Seule écriture : `data/reviews/logs/refonte/2026-10-10-destinataire-recompte-1/`.

Les seuls modules du dépôt importés sont `pipeline.etat` (fonctions pures
`retenir` et `indetermine`) et `prospection.arbitre` (constantes et `bande`),
pour vérifier que la simulation suit le code et non sa documentation.
"""

from __future__ import annotations

import json
import math
import random
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS.parent))
sys.path.insert(0, str(SCRIPTS))

from pipeline.etat import indetermine as etat_indetermine  # noqa: E402
from pipeline.etat import retenir as etat_retenir  # noqa: E402
from prospection import arbitre  # noqa: E402

BACKEND = SCRIPTS.parent
RACINE = BACKEND.parent
CACHE = BACKEND / "data" / "reviews" / "logs" / "benchmark-destinataire"
ENTREES = BACKEND / "data" / "reviews" / "logs" / "refonte-entrees"
SORTIE = BACKEND / "data" / "reviews" / "logs" / "refonte" / "2026-10-10-destinataire-recompte-1"
TRI_0922 = BACKEND / "data" / "reviews" / "2026-09-22-tri-catalogue.md"

LIGNES: list[str] = []


def dire(*morceaux: Any) -> None:
    LIGNES.append(" ".join(str(m) for m in morceaux))


# --------------------------------------------------------------------------
# Statistiques
# --------------------------------------------------------------------------


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    z = 1.959964
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - m), min(1.0, c + m))


def t(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f} % [{100 * lo:.1f} ; {100 * hi:.1f}]" if n else "0/0"


def auc(pos: list[float], neg: list[float]) -> float:
    """Mann-Whitney par les rangs moyens (ex aequo à 1/2)."""
    tout = sorted([(s, 1) for s in pos] + [(s, 0) for s in neg])
    rangs: list[float] = [0.0] * len(tout)
    i = 0
    while i < len(tout):
        j = i
        while j + 1 < len(tout) and tout[j + 1][0] == tout[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rangs[k] = r
        i = j + 1
    somme = sum(r for r, (_, g) in zip(rangs, tout, strict=True) if g)
    n1, n0 = len(pos), len(neg)
    return (somme - n1 * (n1 + 1) / 2) / (n1 * n0)


# --------------------------------------------------------------------------
# Étiquettes depuis git
# --------------------------------------------------------------------------


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(RACINE), *args], capture_output=True, text=True, check=True
    ).stdout


def etiquettes(commit: str) -> dict[str, dict[str, Any]]:
    """slug -> {garde, origine, motif, statut} : la règle de `cas_etiquetes`, rejouée au commit.

    Le snapshot est cherché AU COMMIT (fichier .md ou .pdf directement dans
    `data/sources/<slug>/`). Le banc d'origine le cherchait dans l'arbre de
    travail ; `etiquettes_arbre` mesure l'écart.
    """
    aides = git("ls-tree", "--name-only", commit, "backend/data/aides/").split("\n")
    yamls = {Path(p).name[: -len(".yaml")] for p in aides if p.endswith(".yaml")}
    echecs = {Path(p).name[: -len(".yaml.echec")] for p in aides if p.endswith(".yaml.echec")}
    snap: set[str] = set()
    for p in git("ls-tree", "-r", "--name-only", commit, "backend/data/sources/").split("\n"):
        parts = p.split("/")
        if len(parts) == 5 and (p.endswith(".md") or p.endswith(".pdf")):
            snap.add(parts[3])
    fa = yaml.safe_load(git("show", f"{commit}:backend/data/prospection/file-attente.yaml")) or {}
    out: dict[str, dict[str, Any]] = {}
    for s in sorted(yamls):
        if s in snap:
            out[s] = {
                "garde": True,
                "origine": "prospection" if s in fa else "catalogue",
                "motif": "",
                "statut": (fa.get(s) or {}).get("statut", ""),
            }
    for s, tache in sorted(fa.items()):
        motif = tache.get("motif_ignore") or ""
        if tache.get("statut") != "ignore" or "oublon" in motif:
            continue
        if not motif.startswith(("test du destinataire", "tri humain")):
            continue
        if s in yamls or s not in echecs or s not in snap:
            continue
        out[s] = {"garde": False, "origine": "prospection", "motif": motif, "statut": "ignore"}
    return out


def ordre_banc(lab: dict[str, dict[str, Any]]) -> list[str]:
    """L'ordre de `cas_etiquetes` : gardées triées, puis écartées triées (ordre de la file triée)."""
    g = sorted(s for s, v in lab.items() if v["garde"])
    e = sorted(s for s, v in lab.items() if not v["garde"])
    return g + e


# --------------------------------------------------------------------------
# Caches
# --------------------------------------------------------------------------


def lire(nom: str) -> tuple[dict[str, dict[str, Any]], int]:
    d: dict[str, dict[str, Any]] = {}
    n = 0
    for ligne in (CACHE / f"{nom}.jsonl").read_text(encoding="utf-8").splitlines():
        if ligne.strip():
            n += 1
            r = json.loads(ligne)
            d[r["slug"]] = r
    return d, n


def p_true(rep: dict[str, Any]) -> float:
    return float(rep["noul"])


def jev_scores(r: dict[str, Any]) -> dict[str, Any]:
    rep = r["reponses"]
    pdest = float(rep["destinataire"]["probabilities"].get("proprietaire_gestionnaire", 0))
    pobj = float(rep["objet"]["probabilities"].get("bien_ou_lieu", 0)) + float(
        rep["objet"]["probabilities"].get("activite_dans_le_lieu", 0)
    )
    disp = p_true(rep["dispositif"])
    dep = p_true(rep["deposable"])
    ecarte = (
        rep["destinataire"].get("choice") != "proprietaire_gestionnaire"
        or rep["objet"].get("choice") not in ("bien_ou_lieu", "activite_dans_le_lieu")
        or disp < 0.5
    )
    return {"deposable": dep, "structure": pdest * pobj * disp, "ecarte": ecarte}


def issue_llm(r: dict[str, Any]) -> str:
    """Recalculée depuis destinataire/objet/categorie_ecart avec le code actuel."""
    ret = etat_retenir(r["destinataire"], r["objet"]) and r["categorie_ecart"] != "non_dispositif"
    ind = etat_indetermine(r["destinataire"], r["objet"], r["categorie_ecart"])
    return "retenue" if ret else "humain" if ind else "ecartee"


def issue_llm_cache(r: dict[str, Any]) -> str:
    return "retenue" if r["retenir"] else "humain" if r["indeterminee"] else "ecartee"


# --------------------------------------------------------------------------
# Règles de décision
# --------------------------------------------------------------------------


def production(
    dep: float, ecarte: bool, llm: dict[str, Any] | None, bas: float, haut: float
) -> str:
    """Issue de `lecture.lire` + `_appliquer_arbitrage`, réécrite à la main.

    bande basse (dep < bas ET structure écarte) : écartée sans LLM ;
    LLM en erreur (absent du cache) : pas de tâche -> compté « humain » ici
    (variante « erreur » rendue à part) ;
    bande haute (dep > haut ET structure retient) : retenue, quoi que dise le LLM ;
    milieu : LLM retenue -> retenue ; LLM écart -> humain ; LLM indét. -> humain.
    """
    if dep < bas and ecarte:
        return "ecartee"
    if llm is None:
        return "erreur"
    if dep > haut and not ecarte:
        return "retenue"
    i = llm["_issue"] if "_issue" in llm else issue_llm(llm)
    return "retenue" if i == "retenue" else "humain"


def jev_seul(dep: float, bas: float, haut: float) -> str:
    return "ecartee" if dep < bas else "retenue" if dep > haut else "humain"


def bilan(paires: list[tuple[bool, str]]) -> dict[str, Any]:
    g = [i for garde, i in paires if garde]
    e = [i for garde, i in paires if not garde]
    return {
        "perdues": (sum(i == "ecartee" for i in g), len(g)),
        "admises": (sum(i == "retenue" for i in e), len(e)),
        "humain": (sum(i in ("humain", "erreur") for _, i in paires), len(paires)),
    }


def fb(b: dict[str, Any]) -> str:
    return f"perdues {t(*b['perdues'])} ; admises {t(*b['admises'])} ; humain {t(*b['humain'])}"


def tolerance(pts: list[tuple[float, bool]], tol: float = 0.01) -> tuple[float, float]:
    """Réécriture indépendante du réglage « tolérance » : bas = plus haut seuil
    qui perd au plus tol des gardées ; haut = plus bas seuil qui admet au plus tol des écartées."""
    pos = sorted(s for s, g in pts if g)
    neg = sorted((s for s, g in pts if not g), reverse=True)
    kp, kn = int(tol * len(pos)), int(tol * len(neg))
    bas = pos[kp] if kp < len(pos) else 1.0
    haut = neg[kn] if kn < len(neg) else 0.0
    return bas, max(bas, haut)


def a_charge(pts: list[tuple[float, bool]], part: float) -> tuple[float, float]:
    """Seuils (bas, haut) parmi les valeurs observées : minimise perdues% + admises%
    sous la contrainte part humaine RÉELLE (ex aequo compris) <= part."""
    vals = sorted({s for s, _ in pts} | {0.0, 1.01})
    n = len(pts)
    ng = sum(g for _, g in pts) or 1
    ne = (n - sum(g for _, g in pts)) or 1
    meilleur: tuple[float, float, float] | None = None
    for i, b in enumerate(vals):
        for h in vals[i:]:
            hum = sum(1 for s, _ in pts if b <= s <= h)
            if hum > part * n:
                continue
            perd = sum(1 for s, g in pts if g and s < b)
            adm = sum(1 for s, g in pts if not g and s > h)
            c = perd / ng + adm / ne
            if meilleur is None or c < meilleur[0] - 1e-12:
                meilleur = (c, b, h)
    assert meilleur is not None
    return meilleur[1], meilleur[2]


def a_charge_prod(
    cas: list[tuple[str, bool]],
    sc: dict[str, dict[str, Any]],
    llm: dict[str, dict[str, Any]],
    part: float,
    grille: list[float],
) -> tuple[float, float]:
    meilleur: tuple[float, float, float] | None = None
    n = len(cas)
    ng = sum(g for _, g in cas) or 1
    ne = (n - sum(g for _, g in cas)) or 1
    for b in grille:
        for h in grille:
            if h < b:
                continue
            res = bilan(
                [
                    (g, production(sc[s]["deposable"], sc[s]["ecarte"], llm.get(s), b, h))
                    for s, g in cas
                ]
            )
            if res["humain"][0] > part * n:
                continue
            c = res["perdues"][0] / ng + res["admises"][0] / ne
            if meilleur is None or c < meilleur[0] - 1e-12:
                meilleur = (c, b, h)
    assert meilleur is not None
    return meilleur[1], meilleur[2]


def plis(cas: list[tuple[str, bool]], graine: int) -> tuple[list, list]:
    rng = random.Random(1000 + graine)
    a: list = []
    b: list = []
    for garde in (True, False):
        groupe = [c for c in cas if c[1] == garde]
        rng.shuffle(groupe)
        moitie = len(groupe) // 2
        a += groupe[:moitie]
        b += groupe[moitie:]
    return a, b


def resume(vals: list[float]) -> str:
    return (
        f"moyenne {100 * statistics.mean(vals):.1f} %, é.-t. {100 * statistics.pstdev(vals):.1f}, "
        f"de {100 * min(vals):.1f} à {100 * max(vals):.1f} (n = {len(vals)})"
    )


# --------------------------------------------------------------------------
# Tri du 2026-09-22
# --------------------------------------------------------------------------


def tri_0922() -> tuple[dict[str, str], set[str]]:
    section = ""
    sections: dict[str, str] = {}
    liste: set[str] = set()
    for ligne in TRI_0922.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("## "):
            section = ligne[3:].strip()
            continue
        if section == "Slugs à écarter":
            if ligne.strip():
                liste.add(ligne.split()[0])
            continue
        m = re.match(r"- `([^`]+)`", ligne)
        if m and section in ("À écarter", "À trancher à la main", "Retenues"):
            sections[m.group(1)] = section
    return sections, liste


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    jev, nj = lire("jev")
    glm, ng = lire("llm-or-glm")
    mis, nm = lire("llm-or-mistral-large")
    var, nv = lire("variante")
    dire("# Caches")
    dire(
        f"jev {nj} lignes / {len(jev)} slugs ; or-glm {ng}/{len(glm)} ; mistral {nm}/{len(mis)} ; variante {nv}/{len(var)}"
    )
    dire("questions Jev :", Counter(tuple(sorted(r["reponses"])) for r in jev.values()))
    dire("modèles Jev :", Counter(r["modele"] for r in jev.values()))
    # Cohérence du cache LLM avec le code actuel
    diff = [s for s, r in glm.items() if issue_llm(r) != issue_llm_cache(r)]
    dire(
        f"or-glm : issues recalculées avec pipeline.etat actuel différentes du cache : {len(diff)} {diff[:10]}"
    )
    for r in glm.values():
        r["_issue"] = issue_llm(r)
    sc = {s: jev_scores(r) for s, r in jev.items()}
    for s, r in var.items():
        if s in sc:
            sc[s]["variante"] = float(r["p"])

    # 1. Étiquettes
    dire("\n# 1. Étiquettes")
    labs: dict[str, dict[str, dict[str, Any]]] = {}
    for c in ("52bf6963", "4ae34348", "88d46d5d", "b9f3f43e", "fb918d57"):
        lab = git("rev-parse", "--short=8", c).strip()
        labs[c] = etiquettes(c)
        L = labs[c]
        g = sum(v["garde"] for v in L.values())
        dire(
            f"{lab} : {len(L)} cas, {g} gardées, {len(L) - g} écartées ; notés Jev {sum(s in jev for s in L)} "
            f"(g {sum(s in jev and v['garde'] for s, v in L.items())}, e {sum(s in jev and not v['garde'] for s, v in L.items())}) ; "
            f"or-glm {sum(s in glm for s in L)}"
        )
    A = labs["4ae34348"]
    F = labs["fb918d57"]
    dire("slugs du cache Jev hors du jeu 4ae34348 :", sorted(set(jev) - set(A)))
    dire("slugs du jeu 4ae34348 hors du cache Jev :", sorted(set(A) - set(jev)))
    sections, liste = tri_0922()
    dire(f"tri 0922 : {len(sections)} slugs en section ; liste « Slugs à écarter » {len(liste)}")
    prov = Counter()
    for s, v in A.items():
        if v["garde"]:
            prov[("gardée", v["origine"], sections.get(s, "absent"))] += 1
        else:
            prov[("écartée", v["motif"].split(" :")[0][:30], sections.get(s, "absent"))] += 1
    for k, n in sorted(prov.items(), key=lambda x: -x[1]):
        dire(f"   {n:4d} {k}")
    g_liste = sorted(s for s, v in A.items() if v["garde"] and s in liste)
    g_sect = sorted(s for s, v in A.items() if v["garde"] and sections.get(s) == "À écarter")
    dire(
        f"gardées 4ae34348 dans la LISTE « Slugs à écarter » : {len(g_liste)} ; dans la SECTION « À écarter » : {len(g_sect)}"
    )
    dire("   en section mais pas dans la liste :", sorted(set(g_sect) - set(g_liste)))
    aides4 = git("ls-tree", "--name-only", "4ae34348", "backend/data/aides/").split("\n")
    y4 = {Path(p).name[:-5] for p in aides4 if p.endswith(".yaml")}
    e4 = {Path(p).name[:-11] for p in aides4 if p.endswith(".yaml.echec")}
    dire(
        f"liste 0922 à 4ae34348 : {len(liste & y4)} en .yaml (dont {len(liste & y4 & set(A))} dans le jeu), "
        f"{len(liste & e4)} en .yaml.echec, {len(liste - y4 - e4)} ni l'un ni l'autre"
    )
    # écartées « test du destinataire » que le tri 0922 n'avait pas mises à écarter
    td = [
        s for s, v in A.items() if not v["garde"] and v["motif"].startswith("test du destinataire")
    ]
    dire(
        f"écartées « test du destinataire » : {len(td)} ; dans la liste 0922 : {sum(s in liste for s in td)} ; "
        f"section à écarter {sum(sections.get(s) == 'À écarter' for s in td)}, à trancher "
        f"{sum(sections.get(s) == 'À trancher à la main' for s in td)}, retenues {sum(sections.get(s) == 'Retenues' for s in td)}"
    )
    td_ret = sorted(s for s in td if sections.get(s) == "Retenues")
    dire("   écartées « test du destinataire » rangées Retenues le 0922 :", td_ret)
    # dans quelle autre fiche de requalification sont-elles ?
    autres = {}
    for f in sorted((BACKEND / "data" / "reviews").glob("2026-09-2*-tri-*.md")):
        txt = f.read_text(encoding="utf-8")
        autres[f.name] = [s for s in td_ret if f"`{s}`" in txt or f"\n{s} " in txt]
    dire("   présence dans les autres fiches de tri :", {k: len(v) for k, v in autres.items()})

    # clos / périmé : doctrine changée à 4ae34348
    clos = [
        s
        for s, v in A.items()
        if not v["garde"]
        and re.search(r"clos|clôtur|périm|éteint|termin|ponctuel", v["motif"], re.I)
    ]
    dire(f"écartées dont le motif évoque un dispositif clos ou périmé : {len(clos)} {clos}")

    # changements
    ch = Counter()
    for s in sorted(set(A) | set(F)):
        a = "gardee" if s in A and A[s]["garde"] else "ecartee" if s in A else "absent"
        f = "gardee" if s in F and F[s]["garde"] else "ecartee" if s in F else "absent"
        if a != f:
            ch[(a, f, s in jev)] += 1
    dire("changements 4ae34348 -> fb918d57 :", dict(ch))

    # croisement
    cr = json.loads(
        (ENTREES / "d2ecd4a8-requalification-2026-10-04" / "croisement.json").read_text()
    )
    dire("croisement.json :", len(cr), Counter((x[0], x[1]) for x in cr))
    faux = sum(1 for x in cr if x[1].startswith("Jev a raison"))
    dire("   étiquette fausse :", t(faux, len(cr)))
    cr_slugs = {x[2]: x for x in cr}
    sortis = [s for s in A if A[s]["garde"] and s not in F and s in jev]
    dire(
        f"   gardées sorties du jeu (4ae -> fb9) notées par Jev : {len(sortis)} ; dont relues « Jev a raison » "
        f"{sum(1 for s in sortis if s in cr_slugs and cr_slugs[s][1].startswith('Jev a raison'))}"
    )
    devenues = [s for s in A if not A[s]["garde"] and s in F and F[s]["garde"]]
    dire(
        f"   écartées devenues gardées : {len(devenues)} ; relues « Jev a raison » "
        f"{sum(1 for s in devenues if s in cr_slugs and cr_slugs[s][1].startswith('Jev a raison'))}"
    )

    # 2. Reproduction
    dire("\n# 2. Reproduction (étiquettes 4ae34348)")
    for nom, lab in (("4ae34348", A), ("fb918d57", F)):
        cas = [s for s in lab if s in jev]
        for cle in ("deposable", "structure", "variante"):
            pos = [sc[s][cle] for s in cas if lab[s]["garde"] and cle in sc[s]]
            neg = [sc[s][cle] for s in cas if not lab[s]["garde"] and cle in sc[s]]
            dire(f"AUC {nom} {cle} : {auc(pos, neg):.4f} (g {len(pos)}, e {len(neg)})")
        pros = [s for s in cas if lab[s]["origine"] == "prospection"]
        pos = [sc[s]["deposable"] for s in pros if lab[s]["garde"]]
        neg = [sc[s]["deposable"] for s in pros if not lab[s]["garde"]]
        dire(f"AUC {nom} deposable prospection seule : {auc(pos, neg):.4f} (n {len(pros)})")

    # Bootstrap de l'AUC deposable à 4ae34348
    cas4 = [s for s in A if s in jev]
    rng = random.Random(7)
    G4 = [s for s in cas4 if A[s]["garde"]]
    E4 = [s for s in cas4 if not A[s]["garde"]]
    boots = []
    for _ in range(300):
        gp = [sc[rng.choice(G4)]["deposable"] for _ in G4]
        en = [sc[rng.choice(E4)]["deposable"] for _ in E4]
        boots.append(auc(gp, en))
    boots.sort()
    dire(
        f"AUC deposable 4ae34348, bootstrap stratifié 300 tirages : IC 95 % [{boots[7]:.3f} ; {boots[292]:.3f}]"
    )

    communs = [s for s in cas4 if s in glm]
    paires_llm = [(A[s]["garde"], issue_llm(glm[s])) for s in communs]
    b_llm = bilan(paires_llm)
    dire(f"LLM seul or-glm ({len(communs)}) : {fb(b_llm)}")
    part_llm = b_llm["humain"][0] / b_llm["humain"][1]
    pts = [(sc[s]["deposable"], A[s]["garde"]) for s in communs]
    bt = tolerance(pts)
    dire(f"réglage tolérance 1 % sur les {len(pts)} : {bt}")
    dire(f"Jev seul {bt} : {fb(bilan([(g, jev_seul(p, *bt)) for p, g in pts]))}")
    dire(f"Jev seul 0,12/0,57 : {fb(bilan([(g, jev_seul(p, 0.12, 0.57)) for p, g in pts]))}")
    dire(f"Jev seul 0,13/0,48 : {fb(bilan([(g, jev_seul(p, 0.13, 0.48)) for p, g in pts]))}")
    bc = a_charge(pts, part_llm)
    dire(
        f"réglage à charge RÉELLE <= {100 * part_llm:.1f} % (ex aequo comptés) : {bc} -> "
        f"{fb(bilan([(g, jev_seul(p, *bc)) for p, g in pts]))}"
    )
    # Ex aequo : combien de pages notées exactement 0,13 ou 0,48
    dire(
        f"pages notées exactement 0,13 : {sum(p == 0.13 for p, _ in pts)} ; 0,48 : {sum(p == 0.48 for p, _ in pts)} ; "
        f"0,12 : {sum(p == 0.12 for p, _ in pts)} ; 0,57 : {sum(p == 0.57 for p, _ in pts)}"
    )
    dire(
        "valeurs distinctes de deposable :",
        len({p for p, _ in pts}),
        "; pas observé :",
        sorted({p for p, _ in pts})[:8],
    )

    # Échantillon du 2026-10-07 : banc.echantillon(cas, 200) graine 0
    for c in ("b9f3f43e", "fb918d57"):
        L = labs[c]
        ordre = ordre_banc(L)
        rng0 = random.Random(0)
        g = [s for s in ordre if L[s]["garde"]]
        e = [s for s in ordre if not L[s]["garde"]]
        ech = rng0.sample(g, 100) + rng0.sample(e, 100)
        dire(
            f"échantillon 200 avec étiquettes {c} : {sum(s in mis for s in ech)} des {len(mis)} slugs Mistral dedans"
        )
        if c == "b9f3f43e":
            for nom, cache in (("or-glm", glm), ("mistral", mis)):
                pp = [(L[s]["garde"], issue_llm(cache[s])) for s in ech if s in cache]
                dire(f"   {nom} ({len(pp)}) : {fb(bilan(pp))}")
            pp = [(L[s]["garde"], jev_seul(sc[s]["deposable"], 0.12, 0.57)) for s in ech]
            dire(f"   Jev 0,12/0,57 : {fb(bilan(pp))}")
            hors = [s for s in mis if s not in ech]
            dire(
                "   slugs Mistral hors échantillon :",
                hors,
                [L.get(s, {}).get("garde") for s in hors],
            )

    # 3. Règle de production
    dire("\n# 3. Règle de production")
    for nom, lab in (("4ae34348", A), ("fb918d57", F)):
        cas = [s for s in lab if s in jev]
        iss = {
            s: production(sc[s]["deposable"], sc[s]["ecarte"], glm.get(s), 0.12, 0.57) for s in cas
        }
        # contrôle : la bande calculée par arbitre.bande
        bandes = Counter(
            arbitre.bande(sc[s]["deposable"], sc[s]["ecarte"], arbitre.Seuils(0.12, 0.57))
            for s in cas
        )
        b = bilan([(lab[s]["garde"], iss[s]) for s in cas])
        dire(f"{nom} ({len(cas)}) : {fb(b)}")
        dire(
            f"   bandes {dict(bandes)} ; erreurs de lecture {sum(i == 'erreur' for i in iss.values())}"
        )
        appels = sum(
            1 for s in cas if bandes and not (sc[s]["deposable"] < 0.12 and sc[s]["ecarte"])
        )
        dire(f"   appels LLM {t(appels, len(cas))}")
        # variante : erreur = pas de tâche (exclue)
        sans_err = [(lab[s]["garde"], iss[s]) for s in cas if iss[s] != "erreur"]
        dire(f"   erreurs exclues : {fb(bilan(sans_err))}")
        # pertes / admissions nommées
        dire("   perdues :", sorted(s for s in cas if lab[s]["garde"] and iss[s] == "ecartee"))
        adm = sorted(s for s in cas if not lab[s]["garde"] and iss[s] == "retenue")
        dire("   admises :", len(adm), Counter(lab[s]["motif"].split(" :")[0] for s in adm))
        # Mode dégradé LLM seul sur ce jeu
        cm = [s for s in cas if s in glm]
        dire(f"   LLM seul : {fb(bilan([(lab[s]['garde'], issue_llm(glm[s])) for s in cm]))}")
        # Part de l'humain où le LLM a écarté au milieu
        mil_ec = [
            s
            for s in cas
            if s in glm
            and arbitre.bande(sc[s]["deposable"], sc[s]["ecarte"], arbitre.Seuils(0.12, 0.57))
            == "milieu"
            and issue_llm(glm[s]) == "ecartee"
        ]
        dire(
            f"   milieu, écarts du LLM : {len(mil_ec)} ; faux (gardées) : "
            f"{t(sum(lab[s]['garde'] for s in mil_ec), len(mil_ec))}"
        )

    # Comparaison à charge strictement égale : production vs LLM seul vs Jev seul
    dire("\n# 3 ter. À charge humaine <= LLM seul, dans l'échantillon (4ae34348, 1045 communs)")
    cas_c = [(s, A[s]["garde"]) for s in communs]
    grille = [round(x * 0.01, 2) for x in range(0, 101)]
    grille_cv = [round(x * 0.01, 2) for x in range(5, 81)]
    bp = a_charge_prod(cas_c, sc, glm, part_llm, grille)
    dire(
        f"production réglée à charge <= {100 * part_llm:.1f} % : seuils {bp} -> "
        f"{fb(bilan([(g, production(sc[s]['deposable'], sc[s]['ecarte'], glm.get(s), *bp)) for s, g in cas_c]))}"
    )

    # 4. Validation croisée
    dire("\n# 4. Validation croisée à deux plis, 20 tirages stratifiés (graines 1000 à 1019)")
    res: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    choix: dict[str, Counter] = defaultdict(Counter)
    lignes_cv = [
        "regle,tirage,pli,bas,haut,perdues_k,perdues_n,admises_k,admises_n,humain_k,humain_n"
    ]
    for tir in range(20):
        a, b = plis(cas_c, tir)
        for reglage, mesure, pli in ((a, b, 0), (b, a, 1)):
            part = sum(issue_llm(glm[s]) == "humain" for s, _ in reglage) / len(reglage)
            ptsr = [(sc[s]["deposable"], g) for s, g in reglage]
            for nom, seuils, f in (
                ("jev_charge", a_charge(ptsr, part), "jev"),
                ("jev_tolerance", tolerance(ptsr), "jev"),
                ("prod_charge", a_charge_prod(reglage, sc, glm, part, grille_cv), "prod"),
                ("prod_tolerance", tolerance(ptsr), "prod"),
            ):
                if f == "jev":
                    bb = bilan([(g, jev_seul(sc[s]["deposable"], *seuils)) for s, g in mesure])
                else:
                    bb = bilan(
                        [
                            (
                                g,
                                production(
                                    sc[s]["deposable"], sc[s]["ecarte"], glm.get(s), *seuils
                                ),
                            )
                            for s, g in mesure
                        ]
                    )
                for k in ("perdues", "admises", "humain"):
                    res[nom][k].append(bb[k][0] / bb[k][1])
                choix[nom][(round(seuils[0], 2), round(seuils[1], 2))] += 1
                lignes_cv.append(
                    f"{nom},{tir},{pli},{seuils[0]},{seuils[1]},"
                    + ",".join(f"{bb[k][0]},{bb[k][1]}" for k in ("perdues", "admises", "humain"))
                )
        # LLM seul sur les plis de mesure, pour la même référence
        for mesure in (b, a):
            bb = bilan([(g, issue_llm(glm[s])) for s, g in mesure])
            for k in ("perdues", "admises", "humain"):
                res["llm_seul"][k].append(bb[k][0] / bb[k][1])
    for nom, d in res.items():
        dire(f"{nom} :")
        for k in ("perdues", "admises", "humain"):
            dire(f"   {k} {resume(d[k])}")
        if nom in choix:
            dire("   seuils les plus choisis :", choix[nom].most_common(4))
    (SORTIE / "validation-croisee.csv").write_text("\n".join(lignes_cv) + "\n", encoding="utf-8")

    # 7. Sans humain, seuil unique
    dire("\n# 7. Sans humain, un seuil unique")
    for nom, lab in (("fb918d57", F), ("4ae34348", A)):
        cas = [s for s in lab if s in jev]
        G = [s for s in cas if lab[s]["garde"]]
        E = [s for s in cas if not lab[s]["garde"]]
        for cle, seuil in (("deposable", 0.20), ("deposable", 0.25), ("variante", 0.40)):
            pk = sum(1 for s in G if sc[s].get(cle, 0) < seuil)
            ak = sum(1 for s in E if sc[s].get(cle, 0) >= seuil)
            nv_g = sum(1 for s in G if cle in sc[s])
            nv_e = sum(1 for s in E if cle in sc[s])
            dire(f"{nom} {cle} >= {seuil} : perdues {t(pk, nv_g)} ; admises {t(ak, nv_e)}")
    # seuil choisi hors échantillon (pertes <= 10 % sur le pli de réglage)
    casF = [(s, F[s]["garde"]) for s in F if s in jev]
    for cle in ("deposable", "variante"):
        pl, ad, ch = [], [], Counter()
        for tir in range(20):
            a, b = plis(casF, tir)
            for reglage, mesure in ((a, b), (b, a)):
                gs = sorted(sc[s][cle] for s, g in reglage if g)
                # plus haut seuil tel que la part de gardées < seuil soit <= 10 %
                cands = sorted({round(x * 0.01, 2) for x in range(0, 101)})
                ok = [c for c in cands if sum(v < c for v in gs) <= 0.10 * len(gs)]
                seuil = max(ok)
                ch[seuil] += 1
                gm = [sc[s][cle] for s, g in mesure if g]
                em = [sc[s][cle] for s, g in mesure if not g]
                pl.append(sum(v < seuil for v in gm) / len(gm))
                ad.append(sum(v >= seuil for v in em) / len(em))
        dire(
            f"fb918d57 {cle}, pertes <= 10 % sur le pli de réglage : perdues {resume(pl)} ; admises {resume(ad)} ; seuils {ch.most_common(4)}"
        )

    # 6. Coûts et jetons
    dire("\n# 6. Coûts et jetons")
    cj = [r["cout_usd"] for s, r in jev.items() if r.get("cout_usd") is not None]
    cg = [r["cout_usd"] for s, r in glm.items() if r.get("cout_usd") is not None]
    cm_ = [r["cout_usd"] for s, r in mis.items() if r.get("cout_usd") is not None]
    dire(
        f"Jev : n {len(cj)}, moyenne {statistics.mean(cj):.6f} $, médiane {statistics.median(cj):.6f}, total {sum(cj):.3f}"
    )
    dire(
        f"or-glm : n {len(cg)}, moyenne {statistics.mean(cg):.6f} $, médiane {statistics.median(cg):.6f}, total {sum(cg):.3f}"
    )
    dire(f"mistral : n {len(cm_)}, médiane {statistics.median(cm_):.6f}, total {sum(cm_):.3f}")
    jt = sorted(r["jetons_entree"] for r in jev.values())
    dire(f"jetons Jev : médiane {statistics.median(jt)}, min {jt[0]}, max {jt[-1]}")
    lat_j = statistics.median(r["latence_s"] for r in jev.values() if r.get("latence_s"))
    lat_g = statistics.median(r["latence_s"] for r in glm.values() if r.get("latence_s"))
    dire(f"latence médiane Jev {lat_j} s, or-glm {lat_g} s")
    # coût de la règle de production sur 1 000 pages : Jev partout + LLM sur les appels
    casA = [s for s in A if s in jev]
    appels = [s for s in casA if not (sc[s]["deposable"] < 0.12 and sc[s]["ecarte"])]
    cout_prod = sum(jev[s]["cout_usd"] for s in casA) + sum(
        glm[s]["cout_usd"] for s in appels if s in glm
    )
    dire(
        f"règle de production sur les {len(casA)} cas : {cout_prod:.3f} $ -> {1000 * cout_prod / len(casA):.3f} $ pour 1 000 pages ; "
        f"LLM seul {1000 * statistics.mean(cg):.3f} $ ; Jev seul {1000 * statistics.mean(cj):.3f} $"
    )
    # jetons d'entrée or-glm : fiabilité
    jg = sorted(r["jetons_entree"] for r in glm.values())
    dire(f"jetons or-glm : min {jg[0]}, médiane {statistics.median(jg)}, max {jg[-1]}")
    # régression jetons Jev ~ longueur du texte du snapshot (approx : variable non disponible) -> part fixe
    reel = ENTREES / "d6fb7845-jev-reel-2026-10-04"
    for lot in ("259", "ho"):
        rows = [
            json.loads(x)
            for x in (reel / f"jev113_{lot}.jsonl").read_text().splitlines()
            if x.strip()
        ]
        xs = [r["car_page"] for r in rows]
        ys = [r["jetons_entree"] for r in rows]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        pente = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sum(
            (x - mx) ** 2 for x in xs
        )
        dire(
            f"file réelle {lot} : n {len(rows)} ; milieu {t(sum(r['bande'] == 'milieu' for r in rows), len(rows))} ; "
            f"ordonnée {my - pente * mx:.0f} jetons, pente {pente:.3f} jeton/car ; jetons médians {statistics.median(ys)}"
        )
        # bande recalculée depuis deposable + structure_ecarte
        rec = Counter(
            arbitre.bande(r["deposable"], r["structure_ecarte"], arbitre.Seuils(0.12, 0.57))
            for r in rows
        )
        dire(f"   bande recalculée : {dict(rec)}")
    banc_mil = sum(
        1
        for s in casA
        if arbitre.bande(sc[s]["deposable"], sc[s]["ecarte"], arbitre.Seuils(0.12, 0.57))
        == "milieu"
    )
    dire(f"banc 4ae34348 : milieu {t(banc_mil, len(casA))}")

    # 8. Sous-groupes : provenance des écartées
    dire("\n# 8. Sous-groupes")
    for nom, filtre in (
        ("tri humain", lambda v: v["motif"].startswith("tri humain")),
        ("test du destinataire", lambda v: v["motif"].startswith("test du destinataire")),
    ):
        es = [s for s in communs if not A[s]["garde"] and filtre(A[s])]
        k_llm = sum(issue_llm(glm[s]) == "retenue" for s in es)
        k_prod = sum(
            production(sc[s]["deposable"], sc[s]["ecarte"], glm.get(s), 0.12, 0.57) == "retenue"
            for s in es
        )
        k_hum = sum(issue_llm(glm[s]) == "humain" for s in es)
        k_ec = sum(issue_llm(glm[s]) == "ecartee" for s in es)
        auc_s = auc(
            [sc[s]["deposable"] for s in communs if A[s]["garde"]], [sc[s]["deposable"] for s in es]
        )
        dire(
            f"écartées « {nom} » : LLM admet {t(k_llm, len(es))} ; LLM écarte {t(k_ec, len(es))} ; LLM humain {t(k_hum, len(es))} ; "
            f"production admet {t(k_prod, len(es))} ; AUC Jev gardées vs ce groupe {auc_s:.3f}"
        )
    # Écartées test du destinataire selon la section 0922 : accord du LLM
    for sec in ("À écarter", "À trancher à la main", "Retenues"):
        es = [
            s
            for s in communs
            if not A[s]["garde"] and A[s]["motif"].startswith("test du") and sections.get(s) == sec
        ]
        if es:
            dire(
                f"   écartées « test du destinataire » section {sec} : n {len(es)} ; LLM écarte {sum(issue_llm(glm[s]) == 'ecartee' for s in es)}, "
                f"admet {sum(issue_llm(glm[s]) == 'retenue' for s in es)}, humain {sum(issue_llm(glm[s]) == 'humain' for s in es)}"
            )
    # Gardées selon la section 0922
    for sec in ("À écarter", "À trancher à la main", "Retenues", None):
        gs = [s for s in communs if A[s]["garde"] and sections.get(s) == sec]
        dire(
            f"   gardées section {sec} : n {len(gs)} ; LLM écarte {t(sum(issue_llm(glm[s]) == 'ecartee' for s in gs), len(gs))} ; "
            f"production perd {sum(production(sc[s]['deposable'], sc[s]['ecarte'], glm.get(s), 0.12, 0.57) == 'ecartee' for s in gs)}"
        )
    gl = [s for s in communs if A[s]["garde"] and s in liste]
    dire(
        f"   gardées dans la LISTE 0922 : n {len(gl)} ; LLM écarte {t(sum(issue_llm(glm[s]) == 'ecartee' for s in gl), len(gl))}"
    )
    # LLM seul sans les 62 gardées douteuses ni les 53 « tri humain »
    propre = [s for s in communs if not (A[s]["garde"] and s in liste)]
    dire(
        f"LLM seul sans les gardées de la liste 0922 : {fb(bilan([(A[s]['garde'], issue_llm(glm[s])) for s in propre]))}"
    )
    propre_j = [s for s in propre]
    dire(
        f"production sans ces gardées : "
        f"{fb(bilan([(A[s]['garde'], production(sc[s]['deposable'], sc[s]['ecarte'], glm.get(s), 0.12, 0.57)) for s in propre_j]))}"
    )

    # 9. Écartées selon que l'étiquette est, ou non, un écart prononcé par le LLM du 2026-09-22
    dire("\n# 9. Écartées : verdict d'écart du LLM 0922 contre décision d'une autre source")
    G = [s for s in A if A[s]["garde"]]
    non_llm = [
        s
        for s in A
        if not A[s]["garde"]
        and (
            A[s]["motif"].startswith("tri humain")
            or sections.get(s) in ("À trancher à la main", "Retenues")
        )
    ]
    llm_ec = [s for s in A if not A[s]["garde"] and s not in non_llm]
    for nom, S in (
        ("hors verdict d'écart LLM (tri humain 0930, à trancher, retenues 0922)", non_llm),
        ("verdict d'écart LLM 0922", llm_ec),
        (
            "tri humain 0930 seul",
            [s for s in A if not A[s]["garde"] and A[s]["motif"].startswith("tri humain")],
        ),
    ):
        prod = Counter(
            production(sc[s]["deposable"], sc[s]["ecarte"], glm.get(s), 0.12, 0.57) for s in S
        )
        ll = Counter(issue_llm(glm[s]) for s in S if s in glm)
        a = auc([sc[s]["deposable"] for s in G], [sc[s]["deposable"] for s in S])
        rngb = random.Random(5)
        bs = sorted(
            auc(
                [sc[rngb.choice(G)]["deposable"] for _ in G],
                [sc[rngb.choice(S)]["deposable"] for _ in S],
            )
            for _ in range(500)
        )
        dire(
            f"{nom} : n {len(S)} ; production admet {t(prod['retenue'], len(S))}, humain {prod['humain'] + prod['erreur']}, écarte {prod['ecartee']} ; "
            f"LLM seul admet {t(ll['retenue'], sum(ll.values()))} ; AUC Jev gardées contre ce groupe {a:.3f} [bootstrap 95 % {bs[12]:.3f} ; {bs[487]:.3f}]"
        )

    # 10. Part fixe des jetons de Jev : sensibilité à la mesure de la longueur
    dire(
        "\n# 10. Jetons de Jev contre longueur du texte (snapshots .md de l'arbre de travail, cas sans PDF)"
    )
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}-")
    fm_re = re.compile(r"\A---\n.*?\n---\n", re.S)

    def rang(n: str) -> tuple[int, str]:
        for i, mot in enumerate(("presentation", "dispositif", "reglement")):
            if mot in n:
                return (i, n)
        return (9, n)

    xs_raw: list[float] = []
    xs_json: list[float] = []
    ys: list[float] = []
    for s, r in jev.items():
        d = BACKEND / "data" / "sources" / s
        if not d.is_dir():
            continue
        par: dict[str, Path] = {}
        for f in sorted(d.glob("*.md")):
            par[date_re.sub("", f.name)] = f
        url = ""
        morceaux = []
        for f in sorted(par.values(), key=lambda f: rang(date_re.sub("", f.name))):
            brut = f.read_text(encoding="utf-8", errors="replace")
            if not url and (m := re.search(r"^url: (\S+)", brut, re.M)):
                url = m.group(1)
            morceaux.append(f"## {f.name}\n\n{fm_re.sub('', brut).strip()}")
        if sum(len(m) for m in morceaux) < 1500:
            continue
        texte = "\n\n".join(morceaux)[:25000]
        xs_raw.append(len(texte))
        xs_json.append(len(json.dumps({"url": url, "texte": texte})))
        ys.append(r["jetons_entree"])

    def ols(x: list[float], y: list[float]) -> tuple[float, float]:
        mx, my = statistics.mean(x), statistics.mean(y)
        p = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / sum(
            (a - mx) ** 2 for a in x
        )
        return my - p * mx, p

    o1, p1 = ols(xs_raw, ys)
    o2, p2 = ols(xs_json, ys)
    dire(
        f"n {len(ys)} ; texte brut : ordonnée {o1:.0f}, pente {p1:.3f} ; JSON échappé ASCII : ordonnée {o2:.0f}, pente {p2:.3f} ; "
        f"tronqués à 25 000 : {sum(x >= 25000 for x in xs_raw)}"
    )

    (SORTIE / "rapport.txt").write_text("\n".join(LIGNES) + "\n", encoding="utf-8")
    print("\n".join(LIGNES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
