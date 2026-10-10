"""Recompte adverse de la note `docs/refonte-pipeline/notes/contradictions.md`.

Écrit indépendamment de `contradictions.py` (jamais importé ni relu pour le
calcul). Lecture seule : aucun appel réseau ni modèle, aucune écriture hors de
`data/reviews/logs/refonte/2026-10-10-contradictions-recompte-1/`.

    uv run python scripts/mesures/contradictions_recompte.py

Sections :
  A  règle de production de Jev rejouée sur les caches du banc du 2026-10-04,
     étiquettes reconstruites par git au commit 52bf6963, validation croisée ;
  D  outils de l'agent, motifs de `worker.controler`, prompt système ;
  E  premier tour d'ingestion (journaux ingest-*.log) ;
  H  catalogue : untyped, gate porteur, hard_filters.travaux ;
  T  `text` des conditions contre snapshots et quotes ;
  G  veille : cases cochées d'office ;
  Q  file d'attente : transitions de 88d46d5d.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import random
import re
import statistics
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

SORTIE = BACKEND / "data/reviews/logs/refonte/2026-10-10-contradictions-recompte-1"
CACHE_BANC = BACKEND / "data/reviews/logs/benchmark-destinataire"
COMMIT_BANC = "52bf6963"

RESULTATS: dict[str, Any] = {}


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - m, c + m)


def taux(k: int, n: int) -> dict[str, Any]:
    lo, hi = wilson(k, n)
    return {
        "k": k,
        "n": n,
        "pct": round(100 * k / n, 2) if n else None,
        "ic95": [round(100 * lo, 2), round(100 * hi, 2)],
    }


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(RACINE), *args], capture_output=True, text=True, check=True
    ).stdout


# ---------------------------------------------------------------------------
# A. Jev : règle de production
# ---------------------------------------------------------------------------

OBJETS_RETENUS = {"bien_ou_lieu", "activite_dans_le_lieu"}


def etiquettes_au_commit(commit: str) -> dict[str, tuple[bool, str]]:
    """Règle de `cas_etiquetes`, réécrite sur l'arbre git du commit."""
    noms = git("ls-tree", "--name-only", commit, "backend/data/aides/").split()
    yaml_ = {Path(p).name.removesuffix(".yaml") for p in noms if p.endswith(".yaml")}
    echec = {Path(p).name.removesuffix(".yaml.echec") for p in noms if p.endswith(".yaml.echec")}
    sources = git("ls-tree", "-r", "--name-only", commit, "backend/data/sources/").split()
    avec_snap: set[str] = set()
    for p in sources:
        parts = Path(p).parts
        if len(parts) == 5 and Path(p).suffix in (".md", ".pdf"):
            avec_snap.add(parts[3])
    fa = yaml.safe_load(git("show", f"{commit}:backend/data/prospection/file-attente.yaml")) or {}
    etiq: dict[str, tuple[bool, str]] = {}
    for s in yaml_:
        if s in avec_snap:
            etiq[s] = (True, "yaml")
    for slug, t in fa.items():
        motif = (t or {}).get("motif_ignore") or ""
        if (t or {}).get("statut") != "ignore" or "oublon" in motif:
            continue
        if not motif.startswith(("test du destinataire", "tri humain")):
            continue
        if slug in yaml_ or slug not in echec or slug not in avec_snap:
            continue
        etiq[slug] = (
            False,
            "tri humain" if motif.startswith("tri humain") else "test du destinataire",
        )
    return etiq


def lire_jsonl(p: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for ligne in p.read_text().splitlines():
        if ligne.strip():
            r = json.loads(ligne)
            out[r["slug"]] = r
    return out


def proba(rep: dict[str, Any], option: str) -> float:
    if rep.get("type") == "noul":
        v = float(rep["noul"])
        return v if option == "true" else 1 - v
    return float((rep.get("probabilities") or {}).get(option, 0.0))


def jev_vue(r: dict[str, Any]) -> tuple[float, bool]:
    rep = r["reponses"]
    dep = proba(rep["deposable"], "true")
    dest = rep["destinataire"].get("choice") or ""
    obj = rep["objet"].get("choice") or ""
    disp = proba(rep["dispositif"], "true")
    ecarte = dest != "proprietaire_gestionnaire" or obj not in OBJETS_RETENUS or disp < 0.5
    return dep, ecarte


def bande(dep: float, ecarte: bool, bas: float, haut: float) -> str:
    if dep < bas and ecarte:
        return "ecartee"
    if dep > haut and not ecarte:
        return "retenue"
    return "milieu"


def issue_llm(r: dict[str, Any]) -> str:
    return "retenue" if r["retenir"] else "humain" if r["indeterminee"] else "ecartee"


def issue_prod(b: str, llm: str) -> str:
    """`lecture.lire` + `_appliquer_arbitrage`, relus ligne à ligne."""
    if b == "ecartee":
        return "ecartee"
    if b == "retenue":
        return "retenue"  # LLM retenue : inchangé ; sinon réécrit en retenue
    # milieu : un écart du LLM devient indétermination
    return "humain" if llm in ("ecartee", "humain") else "retenue"


def seuils_tolerance(couples: list[tuple[float, bool]], tol: float = 0.01) -> tuple[float, float]:
    """Même règle que `benchmark_destinataire.ajuster`, réécrite."""
    pos = sorted(s for s, g in couples if g)
    neg = sorted((s for s, g in couples if not g), reverse=True)
    kp, kn = int(tol * len(pos)), int(tol * len(neg))
    bas = pos[kp] if kp < len(pos) else 1.0
    haut = neg[kn] if kn < len(neg) else 0.0
    return bas, max(haut, bas)


def compter(cas: list[tuple[str, bool, float, bool, str]], bas: float, haut: float) -> dict:
    gp = sum(1 for _, g, *_ in cas if g)
    ep = len(cas) - gp
    c = Counter()
    for _, g, dep, ec, llm in cas:
        b = bande(dep, ec, bas, haut)
        i = issue_prod(b, llm)
        c[("bande", b)] += 1
        c[("issue", i)] += 1
        if g and i == "ecartee":
            c["gardees_ecartees"] += 1
        if not g and i == "retenue":
            c["ecartees_admises"] += 1
        if b != "ecartee":
            c["llm_appele"] += 1
        if b == "retenue" and llm != "retenue":
            c["retenue_reecrit"] += 1
        if b == "milieu" and llm == "ecartee":
            c["milieu_reecrit"] += 1
        if b != "milieu":
            c["jev_seul"] += 1
    n = len(cas)
    return {
        "seuils": [bas, haut],
        "gardees_ecartees_a_tort": taux(c["gardees_ecartees"], gp),
        "ecartees_admises": taux(c["ecartees_admises"], ep),
        "renvoyees_humain": taux(c[("issue", "humain")], n),
        "llm_appele": taux(c["llm_appele"], n),
        "bande_retenue": c[("bande", "retenue")],
        "bande_ecartee": c[("bande", "ecartee")],
        "bande_retenue_llm_corrige": c["retenue_reecrit"],
        "milieu_ecart_llm_renvoye": c["milieu_reecrit"],
        "tranchees_par_jev_seul": taux(c["jev_seul"], n),
    }


def section_a() -> None:
    etiq = etiquettes_au_commit(COMMIT_BANC)
    jev = lire_jsonl(CACHE_BANC / "jev.jsonl")
    llm = lire_jsonl(CACHE_BANC / "llm-or-glm.jsonl")
    res: dict[str, Any] = {
        "etiquettes": {
            "total": len(etiq),
            "gardees": sum(g for g, _ in etiq.values()),
            "ecartees": sum(not g for g, _ in etiq.values()),
            "origine_ecartees": Counter(o for g, o in etiq.values() if not g),
        },
        "jev_cache": len(jev),
        "llm_cache": len(llm),
        "jev_sans_etiquette": sorted(set(jev) - set(etiq)),
        "etiquette_sans_jev": len(set(etiq) - set(jev)),
        "questions_jev": sorted({q for r in jev.values() for q in r["reponses"]}),
        "cout_jev_usd": round(sum(r.get("cout_usd") or 0 for r in jev.values()), 4),
        "cout_llm_usd": round(sum(r.get("cout_usd") or 0 for r in llm.values()), 4),
    }
    cas = []
    for s in sorted(set(jev) & set(llm) & set(etiq)):
        dep, ec = jev_vue(jev[s])
        cas.append((s, etiq[s][0], dep, ec, issue_llm(llm[s])))
    res["communs"] = len(cas)
    res["production_0.12_0.57"] = compter(cas, 0.12, 0.57)
    # Jev seul (sans cohérence, sans LLM), comme le tableau du rapport
    for bas, haut in ((0.12, 0.57), (0.13, 0.48)):
        gp = sum(g for _, g, *_ in cas)
        k_g = sum(1 for _, g, d, _, _ in cas if g and d < bas)
        k_e = sum(1 for _, g, d, _, _ in cas if not g and d > haut)
        k_h = sum(1 for _, _, d, _, _ in cas if bas <= d <= haut)
        res[f"jev_seul_{bas}_{haut}"] = {
            "gardees_ecartees": taux(k_g, gp),
            "ecartees_retenues": taux(k_e, len(cas) - gp),
            "humain": taux(k_h, len(cas)),
        }
    gp = sum(g for _, g, *_ in cas)
    res["llm_seul"] = {
        "gardees_ecartees": taux(sum(1 for c in cas if c[1] and c[4] == "ecartee"), gp),
        "ecartees_retenues": taux(
            sum(1 for c in cas if not c[1] and c[4] == "retenue"), len(cas) - gp
        ),
        "humain": taux(sum(1 for c in cas if c[4] == "humain"), len(cas)),
    }
    # Le tri humain contre le test du destinataire : erreurs par origine
    prod = compter(cas, 0.12, 0.57)
    _ = prod
    par_origine = Counter()
    for s, g, d, ec, lm in cas:
        if g:
            continue
        o = etiq[s][1]
        i = issue_prod(bande(d, ec, 0.12, 0.57), lm)
        par_origine[(o, i)] += 1
    res["llm_seul_ecartees_retenues_par_origine"] = dict(
        Counter(etiq[s][1] for s, g, _, _, lm in cas if not g and lm == "retenue")
    )
    res["ecartees_par_origine_et_issue"] = {f"{o}|{i}": v for (o, i), v in par_origine.items()}

    # Seuils réglés sur tout le jeu : la règle `ajuster` les retrouve-t-elle ?
    couples = [(d, g) for _, g, d, _, _ in cas]
    res["ajuster_tout_le_jeu"] = seuils_tolerance(couples)

    # Validation croisée deux plis par `_moitie` (sha256 % 2), réécrite
    def moitie(s: str) -> int:
        return int(hashlib.sha256(s.encode()).hexdigest(), 16) % 2

    plis = []
    tot = Counter()
    for test in (0, 1):
        app = [c for c in cas if moitie(c[0]) != test]
        tst = [c for c in cas if moitie(c[0]) == test]
        bas, haut = seuils_tolerance([(d, g) for _, g, d, _, _ in app])
        r = compter(tst, bas, haut)
        plis.append({"pli_test": test, "n_app": len(app), "n_test": len(tst), **r})
        tot["g"] += r["gardees_ecartees_a_tort"]["k"]
        tot["gn"] += r["gardees_ecartees_a_tort"]["n"]
        tot["e"] += r["ecartees_admises"]["k"]
        tot["en"] += r["ecartees_admises"]["n"]
        tot["h"] += r["renvoyees_humain"]["k"]
        tot["n"] += r["renvoyees_humain"]["n"]
    res["vc_2_plis"] = {
        "plis": plis,
        "gardees_ecartees": taux(tot["g"], tot["gn"]),
        "ecartees_admises": taux(tot["e"], tot["en"]),
        "renvoyees": taux(tot["h"], tot["n"]),
    }

    # 200 tirages aléatoires moitié/moitié, stratifiés, pour la dispersion
    rng = random.Random(20261010)
    tg, te, th = [], [], []
    for _ in range(200):
        g_ = [c for c in cas if c[1]]
        e_ = [c for c in cas if not c[1]]
        rng.shuffle(g_)
        rng.shuffle(e_)
        app = g_[: len(g_) // 2] + e_[: len(e_) // 2]
        tst = g_[len(g_) // 2 :] + e_[len(e_) // 2 :]
        bas, haut = seuils_tolerance([(d, g) for _, g, d, _, _ in app])
        r = compter(tst, bas, haut)
        tg.append(r["gardees_ecartees_a_tort"]["pct"])
        te.append(r["ecartees_admises"]["pct"])
        th.append(r["renvoyees_humain"]["pct"])

    def resume(v: list[float]) -> dict[str, float]:
        v = sorted(v)
        return {
            "moyenne": round(statistics.mean(v), 2),
            "p05": v[int(0.05 * len(v))],
            "p95": v[int(0.95 * len(v)) - 1],
            "max": v[-1],
        }

    res["vc_200_tirages_moitie"] = {
        "gardees_ecartees_pct": resume(tg),
        "ecartees_admises_pct": resume(te),
        "renvoyees_pct": resume(th),
    }

    # Population de prospection seule (les gardées « catalogue » sont faciles)
    fa_head = yaml.safe_load(
        git("show", f"{COMMIT_BANC}:backend/data/prospection/file-attente.yaml")
    )
    pros = [c for c in cas if c[0] in fa_head]
    res["production_prospection_seule"] = compter(pros, 0.12, 0.57)
    res["prospection_seule_n"] = {
        "n": len(pros),
        "gardees": sum(c[1] for c in pros),
    }

    with (SORTIE / "jev-regle-production-recompte.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["slug", "garde", "origine", "deposable", "structure_ecarte", "bande", "llm", "issue"]
        )
        for s, g, d, ec, lm in cas:
            b = bande(d, ec, 0.12, 0.57)
            w.writerow([s, int(g), etiq[s][1], f"{d:.4f}", int(ec), b, lm, issue_prod(b, lm)])
    RESULTATS["A"] = res


# ---------------------------------------------------------------------------
# D. Ingestion : outils, motifs de contrôle, prompt système
# ---------------------------------------------------------------------------


def section_d() -> None:
    res: dict[str, Any] = {}
    src = (BACKEND / "scripts/ingestion/outils.py").read_text()
    arbre = ast.parse(src)
    for noeud in ast.walk(arbre):
        if (
            isinstance(noeud, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "outils" for t in noeud.targets)
            and isinstance(noeud.value, ast.ListComp)
        ):
            gen = noeud.value.generators[0].iter
            if isinstance(gen, ast.Tuple):
                res["outils"] = [e.id for e in gen.elts if isinstance(e, ast.Name)]
                res["outils_lignes"] = [noeud.lineno, noeud.end_lineno]
    res["n_outils"] = len(res.get("outils", []))
    # Motifs d'échec : chaînes rendues ou ajoutées dans `controler`
    wsrc = (BACKEND / "scripts/ingestion/worker.py").read_text()
    warbre = ast.parse(wsrc)
    motifs = []
    for f in ast.walk(warbre):
        if isinstance(f, ast.FunctionDef) and f.name == "controler":
            res["controler_lignes"] = [f.lineno, f.end_lineno]
            for n in ast.walk(f):
                if (
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "append"
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == "echecs"
                ):
                    motifs.append(("append", n.lineno))
                if isinstance(n, ast.Return) and isinstance(n.value, ast.List) and n.value.elts:
                    motifs.append(("return", n.lineno))
    res["motifs_controler"] = motifs
    res["n_motifs_controler"] = len(motifs)

    from ingestion.contexte import (
        ADAPTATIONS,
        condense_schema,
        estimer_jetons,
        index_faits,
        prompt_systeme,
    )

    from aides_schema import load_facts, load_pending_facts

    facts = dict(load_facts())
    pending = dict(load_pending_facts())
    systeme = prompt_systeme(facts, pending)
    res["prompt_systeme"] = {
        "faits": len(facts),
        "pending": len(pending),
        "car": len(systeme),
        "jetons_estimes_3_6": estimer_jetons(systeme),
        "index_faits_car": len(index_faits(facts, pending)),
        "schema_car": len(condense_schema()),
        "adaptations_car": len(ADAPTATIONS),
    }
    RESULTATS["D"] = res


# ---------------------------------------------------------------------------
# E. Premier tour des ingestions journalisées
# ---------------------------------------------------------------------------

_ENTETE = re.compile(r"^(\S+) — (\d{4}-\d{2}-\d{2}T[\d:+-]+) — ingestion (\S+)", re.M)
_TOUR1 = re.compile(r"^--- tour 1 — entrée (\d+) \(\+(\d+) cache\)", re.M)


def section_e() -> None:
    logs = BACKEND / "data/reviews/logs"
    vus: dict[tuple[str, str, str], tuple[int, int, str, str]] = {}
    fichiers = 0
    doublons = 0
    sans_tour1 = 0
    for p in sorted(logs.rglob("ingest-*.log")):
        if "refonte/" in str(p):
            continue
        fichiers += 1
        t = p.read_text(errors="replace")
        entetes = list(_ENTETE.finditer(t))
        for i, m in enumerate(entetes):
            fin = entetes[i + 1].start() if i + 1 < len(entetes) else len(t)
            m1 = _TOUR1.search(t, m.end(), fin)
            if not m1:
                sans_tour1 += 1
                continue
            cle = (m.group(1), m.group(2), m.group(3))
            if cle in vus:
                doublons += 1
                continue
            vus[cle] = (int(m1.group(1)), int(m1.group(2)), m.group(3), p.parent.name)
    v = sorted(x[0] + x[1] for x in vus.values())
    n = len(v)
    v_hors_cache = sorted(x[0] for x in vus.values())
    res = {
        "fichiers": fichiers,
        "tentatives_uniques": n,
        "doublons_ecartes": doublons,
        "tentatives_sans_tour1": sans_tour1,
        "mediane": statistics.median(v) if v else None,
        "p10": v[int(0.1 * n)] if v else None,
        "p90": v[int(0.9 * n)] if v else None,
        "min": v[0] if v else None,
        "max": v[-1] if v else None,
        "mediane_hors_cache": statistics.median(v_hors_cache) if v else None,
        "tour1_avec_cache_non_nul": sum(1 for x in vus.values() if x[1] > 0),
        "modeles": Counter(x[2] for x in vus.values()).most_common(),
        "dossiers": Counter(x[3] for x in vus.values()).most_common(),
    }
    RESULTATS["E"] = res
    with (SORTIE / "ingestion-tour1-recompte.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["slug", "horodatage", "entree_tour1", "cache_tour1", "modele", "dossier"])
        for (slug, h, _), (e, c, mo, d) in sorted(vus.items()):
            w.writerow([slug, h, e, c, mo, d])


# ---------------------------------------------------------------------------
# H. Catalogue
# ---------------------------------------------------------------------------


def section_h() -> None:
    from aides_schema import gate_porteur, load_all_aides

    aides = load_all_aides()
    n_cond = sum(len(a.conditions) for a in aides.values())
    kinds = Counter(c.kind for a in aides.values() for c in a.conditions)
    RESULTATS["H"] = {
        "aides": len(aides),
        "echec": len(list((BACKEND / "data/aides").glob("*.yaml.echec"))),
        "conditions": n_cond,
        "kinds": dict(kinds),
        "gate_porteur": sum(gate_porteur(a) for a in aides.values()),
        "hard_filters_travaux": sum(
            1 for a in aides.values() if a.hard_filters and a.hard_filters.travaux
        ),
    }


# ---------------------------------------------------------------------------
# T. `text` contre snapshots et quotes, matcher écrit ici
# ---------------------------------------------------------------------------

_TRAD = str.maketrans(
    {
        "\u2019": "'",
        "\u2018": "'",
        "\u02bc": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00ab": '"',
        "\u00bb": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2011": "-",
        "\u00a0": " ",
        "\u202f": " ",
        "\u2026": "...",
    }
)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.translate(_TRAD))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[*_`#>|\\]", " ", s)
    return " ".join(s.split())


def lache(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", norm(s))


def textes_snapshot(slug: str) -> list[str] | None:
    from veille_collect import pdf_to_text

    d = BACKEND / "data/sources" / slug
    if not d.is_dir():
        return None
    out = []
    for f in sorted(d.iterdir()):
        if f.suffix == ".md":
            out.append(f.read_text(errors="replace"))
        elif f.suffix == ".pdf":
            t = pdf_to_text(f)
            if t:
                out.append(t)
    return out or None


def section_t() -> None:
    from aides_schema import load_all_aides

    aides = load_all_aides()
    c = Counter()
    lignes = []
    for slug, a in sorted(aides.items()):
        docs = textes_snapshot(slug)
        dn = [norm(x) for x in docs] if docs else []
        dl = [lache(x) for x in docs] if docs else []
        for cond in a.conditions:
            c["conditions"] += 1
            q = cond.quote or ""
            t = cond.text or ""
            if q:
                c["avec_quote"] += 1
                if norm(q) == norm(t):
                    c["text_egal_quote"] += 1
                if lache(q) == lache(t):
                    c["text_egal_quote_lache"] += 1
            if not docs:
                c["sans_snapshot"] += 1
                lignes.append([slug, cond.id, "", "", "", ""])
                continue
            c["avec_snapshot"] += 1
            tn, tl = norm(t), lache(t)
            trouve = any(tn in d for d in dn)
            trouve_l = bool(tl) and any(tl in d for d in dl)
            c["text_trouve"] += trouve
            c["text_trouve_lache"] += trouve_l
            qt = ""
            if q:
                c["quote_avec_snapshot"] += 1
                qt = int(bool(lache(q)) and any(lache(q) in d for d in dl))
                c["quote_trouvee_lache"] += qt
            lignes.append([slug, cond.id, 1, int(trouve), int(trouve_l), qt])
    RESULTATS["T"] = {
        "compte": dict(c),
        "text_trouve": taux(c["text_trouve"], c["avec_snapshot"]),
        "text_trouve_lache": taux(c["text_trouve_lache"], c["avec_snapshot"]),
        "text_egal_quote": taux(c["text_egal_quote"], c["avec_quote"]),
        "text_egal_quote_lache": taux(c["text_egal_quote_lache"], c["avec_quote"]),
        "quote_trouvee_lache": taux(c["quote_trouvee_lache"], c["quote_avec_snapshot"]),
    }
    with (SORTIE / "text-vs-source-recompte.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "slug",
                "condition",
                "snapshot",
                "text_trouve",
                "text_trouve_lache",
                "quote_trouvee_lache",
            ]
        )
        w.writerows(lignes)


# ---------------------------------------------------------------------------
# G. Veille : fiche d'étiquetage du 2026-10-04
# ---------------------------------------------------------------------------


def section_g() -> None:
    t = (BACKEND / "data/reviews/2026-10-04-etiquettes-veille-jev.md").read_text()
    lignes = t.splitlines()
    blocs = re.split(r"\n(?=### [AB] · )", t)[1:]
    RESULTATS["G"] = {
        "occurrences_[x]_dans_le_fichier": t.count("[x]"),
        "lignes_case_cochee": sum(1 for x in lignes if x.startswith("- [x]")),
        "lignes_case_vide": sum(1 for x in lignes if x.startswith("- [ ]")),
        "blocs": len(blocs),
        "blocs_A": sum(1 for b in blocs if b.startswith("### A")),
        "blocs_B": sum(1 for b in blocs if b.startswith("### B")),
        "blocs_avec_une_case_cochee": sum(
            1 for b in blocs if sum(x.startswith("- [x]") for x in b.splitlines()) == 1
        ),
        "coches_d_office": Counter(
            x.split("coché d'office : ")[1] for x in lignes if "coché d'office : " in x
        ),
    }


# ---------------------------------------------------------------------------
# Q. File d'attente : requalification 88d46d5d, et ce qu'elle fait au banc
# ---------------------------------------------------------------------------


def section_q() -> None:
    def fa(c: str) -> dict[str, Any]:
        return yaml.safe_load(git("show", f"{c}:backend/data/prospection/file-attente.yaml")) or {}

    avant, apres, head = fa("88d46d5d^"), fa("88d46d5d"), fa("HEAD")
    trans = Counter()
    haut, bas = [], []
    for slug in set(avant) | set(apres):
        a = (avant.get(slug) or {}).get("statut")
        b = (apres.get(slug) or {}).get("statut")
        if a != b:
            trans[f"{a}->{b}"] += 1
            if a == "ignore" and b == "valide":
                haut.append(slug)
            if a == "ingere" and b == "ignore":
                bas.append(slug)
    garde_motif = [s for s in haut if (apres[s] or {}).get("motif_ignore")]
    ingere_motif_head = sorted(
        s
        for s, v in head.items()
        if (v or {}).get("statut") == "ingere" and (v or {}).get("motif_ignore")
    )
    banc = {}
    p = SORTIE / "jev-regle-production-recompte.csv"
    if p.exists():
        banc = {r["slug"]: r for r in csv.DictReader(p.open())}
    RESULTATS["Q"] = {
        "transitions": dict(trans),
        "ignore_vers_valide_motif_garde": len(garde_motif),
        "ingere_avec_motif_ignore_head": len(ingere_motif_head),
        "dont_issus_de_88d46d5d": len(set(ingere_motif_head) & set(garde_motif)),
        "banc_ignore_vers_valide": Counter(
            f"{banc[s]['origine']}|{banc[s]['issue']}" for s in haut if s in banc
        ),
        "banc_ingere_vers_ignore": Counter(
            f"garde={banc[s]['garde']}|{banc[s]['issue']}" for s in bas if s in banc
        ),
        "gardees_ecartees_par_la_regle_puis_requalifiees": sorted(
            s
            for s in bas
            if s in banc and banc[s]["garde"] == "1" and banc[s]["issue"] == "ecartee"
        ),
    }


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    section_a()
    section_d()
    section_e()
    section_h()
    section_t()
    section_g()
    section_q()
    (SORTIE / "recompte.json").write_text(
        json.dumps(RESULTATS, ensure_ascii=False, indent=1, default=str) + "\n"
    )
    print(json.dumps(RESULTATS, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
