"""Recompte adverse de la note M06 (docs/refonte-pipeline/notes/faits.md).

Écrit sans réutiliser `scripts/mesures/faits.py` : historique git relu, formules
réimplémentées. Seules importations du code existant : `veille_text.normalize`
(la normalisation de production, pour reproduire le score exact de
`ingestion/faits.py::_proches`), `ingestion.faits` (constantes et `promesse`) et,
pour la partie coût, `profils_questionnaire` (aucune écriture à l'import).

Lecture seule : rien n'est écrit hors du dossier de sortie. Aucun appel réseau.

    cd backend && uv run python scripts/mesures/faits_recompte.py
"""

from __future__ import annotations

import json
import math
import random
import re
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND / "scripts"))
sys.path.insert(0, str(BACKEND))

from ingestion.faits import MAX_PROCHES, SEUIL_PROXIMITE, promesse  # noqa: E402
from veille_text import normalize  # noqa: E402

ENTREES = BACKEND / "data/reviews/logs/refonte-entrees/be997c31-bilan-2026-10-07"
SORTIE = BACKEND / "data/reviews/logs/refonte/2026-10-10-faits-recompte-1"
F_FACTS = "backend/data/facts.yaml"
F_PENDING = "backend/data/facts_pending.yaml"
CONTROLE_ACTIF = "f5801d88"  # 2026-09-16 20:12, naissance de SEUIL_PROXIMITE

LIGNES: list[str] = []


def lire_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def lire_yaml(p: Path):
    return yaml.safe_load(Path(p).read_text(encoding="utf-8"))


def dire(t: str = "") -> None:
    print(t)
    LIGNES.append(t)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def tx(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f} % [{100 * lo:.1f} ; {100 * hi:.1f}]" if n else f"{k}/0"


def git(*a: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *a], capture_output=True, text=True, check=False
    ).stdout


_BLOBS: dict[tuple[str, str], str] = {}


def blob(c: str, p: str) -> str:
    if (c, p) not in _BLOBS:
        _BLOBS[(c, p)] = git("show", f"{c}:{p}")
    return _BLOBS[(c, p)]


CLE = re.compile(r"^([a-z0-9_]+):", re.M)


def cles(c: str, p: str) -> set[str]:
    return set(CLE.findall(blob(c, p)))


# --------------------------------------------------------------------- histoire
def histoire() -> list[tuple[str, int]]:
    out = git("log", "--full-history", "--format=%h %ct", "HEAD", "--", F_FACTS, F_PENDING).split(
        "\n"
    )
    lst = [(x.split()[0], int(x.split()[1])) for x in out if x.strip()]
    lst.sort(key=lambda t: t[1])
    return lst


def ts(c: str) -> int:
    return int(git("log", "-1", "--format=%ct", c).strip())


def score(a: str, b: str, idx: dict) -> float:
    return max(
        SequenceMatcher(None, normalize(idx[a]["question"]), normalize(idx[b]["question"])).ratio(),
        SequenceMatcher(None, a.replace("_", " "), b.replace("_", " ")).ratio(),
    )


def auc(pos: list[float], neg: list[float]) -> float:
    s = 0.0
    for p in pos:
        for n in neg:
            s += 1.0 if p > n else 0.5 if p == n else 0.0
    return s / (len(pos) * len(neg))


# ======================================================================= J1
def partie_j1(hist, premiere, idx) -> dict:
    dire("=" * 78)
    dire("J1 : contrôle lexical de doublon")
    dire("=" * 78)
    dire(f"Constantes lues : SEUIL_PROXIMITE={SEUIL_PROXIMITE}, MAX_PROCHES={MAX_PROCHES}")
    pe = lire_json(ENTREES / "paires_etiquetees.json")
    pf = lire_json(ENTREES / "paires_fusion.json")
    # reconstruction indépendante des positives depuis paires_fusion
    pos = []
    for r, (src, vers) in pf.items():
        cible = vers.split()[0].strip("`,(") if vers else ""
        if r in idx and cible in idx and r != cible:
            pos.append((r, cible, src))
    dire(
        f"positives reconstruites : {len(pos)} (fichier : {len(pe['positives'])}) ; "
        f"négatives fichier : {len(pe['negatives'])}"
    )
    fichier = {(p[0], p[1]) for p in pe["positives"]}
    extra = [(a, b) for a, b, _ in pos if (a, b) not in fichier]
    dire(f"  paires de paires_fusion.json absentes du fichier étiqueté : {len(extra)} {extra}")
    pos = [(a, b, s) for a, b, s in pos if (a, b) in fichier]
    assert len(pos) == len(fichier)
    neg = [(a, b) for a, b, _ in pe["negatives"]]
    sp = [score(a, b, idx) for a, b, _ in pos]
    sn = [score(a, b, idx) for a, b in neg]
    ecarts = sum(
        1
        for p, s in zip(
            pe["positives"], [score(p[0], p[1], idx) for p in pe["positives"]], strict=True
        )
        if abs(p[2] - s) > 1e-9
    ) + sum(1 for n, s in zip(pe["negatives"], sn, strict=True) if abs(n[2] - s) > 1e-9)
    dire(f"scores recalculés : {ecarts} écart(s) au score stocké")
    s0 = SEUIL_PROXIMITE
    tp = sum(s >= s0 for s in sp)
    fp = sum(s >= s0 for s in sn)
    dire(f"rappel à {s0} : {tx(tp, len(sp))}")
    dire(f"alertes à {s0} : {tx(fp, len(sn))}")
    a = auc(sp, sn)
    dire(f"AUC (Mann-Whitney, ex aequo 0,5) : {a:.3f}")
    dire(f"médianes : positives {statistics.median(sp):.2f}, négatives {statistics.median(sn):.2f}")
    courbe = {}
    for t in [x / 100 for x in range(20, 96, 2)]:
        courbe[t] = (sum(s >= t for s in sp), sum(s >= t for s in sn))
    for t in (0.40, 0.50, 0.60, 0.68, 0.72, 0.80):
        k, f = (
            courbe[round(t, 2)]
            if round(t, 2) in courbe
            else (sum(s >= t for s in sp), sum(s >= t for s in sn))
        )
        dire(f"  seuil {t:.2f} : rappel {k}/140  alertes {f}/208")

    # Provenance des positives par section de facts.yaml (relecture des titres)
    txt = (BACKEND / "data/facts.yaml").read_text(encoding="utf-8")
    section = "?"
    sec_de: dict[str, str] = {}
    for li in txt.splitlines():
        m = re.match(r"^#\s*(Fusions appliquées|Scissions|Renommages|C\d+ —)", li)
        if m:
            section = m.group(1)
        elif re.match(r"^# ═", li) or re.match(r"^[a-z0-9_]+:", li):
            section = "?" if re.match(r"^[a-z0-9_]+:", li) else section
        m2 = re.match(r"^#\s+([a-z0-9_]+)\s+→", li)
        if m2:
            sec_de.setdefault(m2.group(1), section)
    par_sec = Counter()
    par_sec_tp = Counter()
    for (r, _c, src), s in zip(pos, sp, strict=True):
        k = src if src != "facts.yaml" else "facts.yaml/" + sec_de.get(r, "?")
        par_sec[k] += 1
        par_sec_tp[k] += s >= s0
    for r, c, src in pos:
        if src == "facts.yaml" and sec_de.get(r, "?") in ("?", "Renommages", "Scissions"):
            dire(f"    positive hors section Fusions : {r} -> {c} ({sec_de.get(r, '?')})")
    dire("positives par provenance (section) :")
    for k, n in par_sec.most_common():
        dire(f"  {k:55s} {tx(par_sec_tp[k], n)}")

    # Paires de doublons que le jeu a oubliées : lot-1 et revue 2026-10-07
    oublis = []
    for f in ("lot-1-suppressions-seches.yaml", "2026-10-07-revue-pending-prospection.yaml"):
        d = lire_yaml(BACKEND / "data/fusions" / f)
        for e in d.get("fusions") or []:
            r = e["retirer"]
            g = e.get("garder")
            if not g:
                m = re.search(r"`([a-z0-9_]+)`", e.get("motif") or "") or re.search(
                    r"\b(?:que|de|par)\s+([a-z0-9_]{6,})", e.get("motif") or ""
                )
                g = m.group(1) if m else None
            oublis.append((r, g, f))
    deja = {p[0] for p in pos}
    dire(f"  oublis déjà dans les positives : {sum(1 for r, _, _ in oublis if r in deja)}")
    utiles = [(r, g, f) for r, g, f in oublis if g and r in idx and g in idx and r not in deja]
    so = [score(r, g, idx) for r, g, _ in utiles]
    dire(
        f"paires de doublons hors du jeu (lot-1 et revue du 2026-10-07) : {len(oublis)}, "
        f"définitions retrouvées pour {len(utiles)} ; rappel à {s0} : "
        f"{tx(sum(s >= s0 for s in so), len(so))}"
    )
    tp2 = tp + sum(s >= s0 for s in so)
    dire(f"  rappel sur le jeu élargi (sans double compte) : {tx(tp2, len(sp) + len(so))}")
    # Hors des tables nées dans le même commit que le seuil (f5801d88 : lot-2, lot-3)
    hors = [s for (_r, _c, src), s in zip(pos, sp, strict=True) if not src.startswith("lot-")]
    dire(
        f"  rappel hors lot-2 et lot-3 (tables du commit qui a posé le seuil) : "
        f"{tx(sum(s >= s0 for s in hors), len(hors))}"
    )

    # Biais de sélection des négatives : le commentaire qui cite le voisin a-t-il été
    # écrit sous le contrôle (après f5801d88) ? Le contrôle exigeait alors de citer ou
    # lire tout voisin au-dessus de 0,68.
    t_ctrl = ts(CONTROLE_ACTIF)
    avant, apres = [], []
    for (a_, b_), s in zip(neg, sn, strict=True):
        ca = f"`{b_}`" in idx[a_]["commentaire"]
        cb = f"`{a_}`" in idx[b_]["commentaire"]
        citant = a_ if ca else b_
        if not (ca or cb):
            continue
        t = premiere.get(citant)
        (apres if t and t >= t_ctrl else avant).append(s)
    dire(
        f"négatives dont le fait citant est né avant le contrôle ({CONTROLE_ACTIF}) : "
        f"{len(avant)}, alertes à {s0} {tx(sum(s >= s0 for s in avant), len(avant))}"
    )
    dire(
        f"négatives dont le fait citant est né sous le contrôle : {len(apres)}, "
        f"alertes à {s0} {tx(sum(s >= s0 for s in apres), len(apres))}"
    )

    # Validation croisée indépendante : 2 plis stratifiés, 200 tirages
    def cv(contrainte: float, reps: int = 200) -> tuple[float, float, float, float, float]:
        rng = random.Random(7)
        seuils, rap, fa = [], [], []
        grille = [x / 100 for x in range(20, 100)]
        for _ in range(reps):
            ip = list(range(len(sp)))
            ineg = list(range(len(sn)))
            rng.shuffle(ip)
            rng.shuffle(ineg)
            hp, hn = len(ip) // 2, len(ineg) // 2
            for tr_p, te_p, tr_n, te_n in (
                (ip[:hp], ip[hp:], ineg[:hn], ineg[hn:]),
                (ip[hp:], ip[:hp], ineg[hn:], ineg[:hn]),
            ):
                best = None
                for t in grille:
                    f_ = sum(sn[i] >= t for i in tr_n) / len(tr_n)
                    r_ = sum(sp[i] >= t for i in tr_p) / len(tr_p)
                    if f_ <= contrainte and (best is None or r_ > best[1]):
                        best = (t, r_)
                t = best[0]
                seuils.append(t)
                rap.append(sum(sp[i] >= t for i in te_p) / len(te_p))
                fa.append(sum(sn[i] >= t for i in te_n) / len(te_n))
        q = statistics.quantiles
        return (
            statistics.median(seuils),
            statistics.median(rap),
            q(rap, n=40)[0],
            q(rap, n=40)[-1],
            statistics.median(fa),
        )

    cvs = {}
    for c in (0.03, 0.06, 0.10, 0.20):
        r = cv(c)
        cvs[c] = r
        dire(
            f"  VC alertes <= {100 * c:.0f} % : seuil médian {r[0]:.2f}, rappel tenu à part "
            f"{100 * r[1]:.1f} % (2,5-97,5 % : {100 * r[2]:.1f} à {100 * r[3]:.1f}), "
            f"alertes {100 * r[4]:.1f} %"
        )
    return {
        "scores_pos": sp,
        "scores_neg": sn,
        "pos": pos,
        "tp": tp,
        "fp": fp,
        "auc": a,
        "oublis": [
            (r, g, f, score(r, g, idx) if (g and r in idx and g in idx) else None)
            for r, g, f in oublis
        ],
        "neg_avant": len(avant),
        "neg_avant_alerte": sum(s >= s0 for s in avant),
        "neg_apres": len(apres),
        "neg_apres_alerte": sum(s >= s0 for s in apres),
        "cv": {str(k): v for k, v in cvs.items()},
    }


# =================================================== J1 en place et charge
def partie_j1_en_place(hist, keys_at, premiere_c, idx, pos) -> dict:
    dire()
    dire("J1 tel qu'il tourne : pool au commit de première apparition du fait retiré")
    famille = defaultdict(set)
    for r, c, _ in pos:
        famille[c].add(r)
    n_cible, n_fam, n_vu, n_vu_cible = 0, 0, 0, 0
    rangs, rangs_j = [], []

    def mots(k: str) -> set[str]:
        d = idx[k]
        return set(
            normalize(
                " ".join([k.replace("_", " "), d.get("question") or "", d.get("help") or ""])
            ).split()
        )

    cache_m: dict[str, set[str]] = {}
    for r, c, _ in pos:
        c0 = premiere_c.get(r)
        if c0 is None:
            continue
        pool = (keys_at[c0] - {r}) & set(idx)
        fam = ({c} | famille[c]) - {r}
        if c in pool:
            n_cible += 1
        if not (fam & pool):
            continue
        n_fam += 1
        sc = sorted(((score(r, k, idx), k) for k in pool), key=lambda x: (-x[0], x[1]))
        top = [k for s, k in sc if s >= SEUIL_PROXIMITE][:MAX_PROCHES]
        if fam & set(top):
            n_vu += 1
        if c in pool and c in top:
            n_vu_cible += 1
        if r not in cache_m:
            cache_m[r] = mots(r)
        ma = cache_m[r]
        sj = []
        for k in pool:
            if k not in cache_m:
                cache_m[k] = mots(k)
            mb = cache_m[k]
            sj.append((len(ma & mb) / len(ma | mb) if ma | mb else 0.0, k))
        sj.sort(key=lambda x: (-x[0], x[1]))
        rangs_j.append(next(i for i, (_, k) in enumerate(sj) if k in fam) + 1)
        rang = next(i for i, (s, k) in enumerate(sc) if k in fam) + 1
        rangs.append(rang)
    dire(f"  cible gardée présente : {tx(n_cible, len(pos))}")
    dire(f"  cible ou famille présente : {tx(n_fam, len(pos))}")
    dire(f"  doublon dans les 6 voisins alertés : {tx(n_vu, n_fam)}")
    dire(
        f"  cible gardée elle-même dans les 6 voisins, quand elle existait : {tx(n_vu_cible, n_cible)}"
    )
    for k in (6, 20):
        dire(
            f"  rappel@{k} score de production sans seuil : {tx(sum(x <= k for x in rangs), n_fam)} ; "
            f"Jaccard des mots (clé + question + aide, ma tokenisation) : {tx(sum(x <= k for x in rangs_j), n_fam)}"
        )
    return {
        "n_cible": n_cible,
        "n_fam": n_fam,
        "n_vu": n_vu,
        "n_vu_cible": n_vu_cible,
        "rangs": rangs,
        "rangs_jaccard": rangs_j,
    }


def partie_charge(keys_at, premiere_c, pending_ever, idx) -> dict:
    dire()
    dire("Charge : part des faits passés par facts_pending.yaml qui reçoivent une alerte")
    n, k_al, sans_def = 0, 0, 0
    nb = []
    cache_q = {k: normalize(v["question"]) for k, v in idx.items()}
    for r in sorted(pending_ever):
        c0 = premiere_c.get(r)
        if r not in idx or c0 is None:
            sans_def += 1
            continue
        n += 1
        pool = (keys_at[c0] - {r}) & set(idx)
        qa = cache_q[r]
        ka = r.replace("_", " ")
        cnt = 0
        for k in pool:
            # bornes supérieures exactes de ratio() d'abord : même résultat, plus vite
            sm = SequenceMatcher(None, ka, k.replace("_", " "))
            if (
                sm.real_quick_ratio() >= SEUIL_PROXIMITE
                and sm.quick_ratio() >= SEUIL_PROXIMITE
                and sm.ratio() >= SEUIL_PROXIMITE
            ):
                cnt += 1
                continue
            sq = SequenceMatcher(None, qa, cache_q[k])
            if (
                sq.real_quick_ratio() >= SEUIL_PROXIMITE
                and sq.quick_ratio() >= SEUIL_PROXIMITE
                and sq.ratio() >= SEUIL_PROXIMITE
            ):
                cnt += 1
        if cnt:
            k_al += 1
            nb.append(cnt)
    dire(
        f"  clés passées par pending : {len(pending_ever)} ; sans définition dans l'index : {sans_def}"
    )
    dire(
        f"  au moins une alerte : {tx(k_al, n)} ; voisins médiane {statistics.median(nb)}, max {max(nb)}"
    )
    return {"n": n, "alertes": k_al}


# ======================================================================= usage
def refs_rec(o, acc: set[str]) -> None:
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("fact", "levier") and isinstance(v, str):
                acc.add(v)
            else:
                refs_rec(v, acc)
    elif isinstance(o, list):
        for v in o:
            refs_rec(v, acc)


def usage_head() -> dict:
    dire()
    dire("=" * 78)
    dire("Usage des faits à HEAD (parcours récursif de chaque aide : toute clé fact ou levier)")
    dire("=" * 78)
    facts = lire_yaml(BACKEND / "data/facts.yaml") or {}
    pend = lire_yaml(BACKEND / "data/facts_pending.yaml") or {}
    tous = set(facts) | set(pend)
    par = defaultdict(set)
    n_aides = 0
    for f in sorted((BACKEND / "data/aides").glob("*.yaml")):
        d = lire_yaml(f)
        n_aides += 1
        acc: set[str] = set()
        # fiche exclue : texte rédigé, pas des prédicats
        refs_rec({k: v for k, v in d.items() if k != "fiche"}, acc)
        for x in acc:
            par[x].add(f.stem)
    dist = Counter()
    for k in tous:
        n = len(par.get(k, ()))
        dist[n] += 1
    un = dist[1]
    dire(
        f"  {n_aides} aides, {len(facts)} faits dans facts.yaml, {len(pend)} dans pending, {len(tous)} au total"
    )
    dire(f"  cités par 0 : {dist[0]} ; par 1 : {tx(un, len(tous))}")
    un_f = sum(1 for k in facts if len(par.get(k, ())) == 1)
    dire(f"  facts.yaml seul : {tx(un_f, len(facts))}")
    hors = sorted(set(par) - tous)
    dire(f"  clés citées par une aide mais absentes de l'ontologie : {len(hors)} {hors[:8]}")
    return {"par": {k: sorted(v) for k, v in par.items()}, "dist": dict(dist), "tous": sorted(tous)}


# =========================================================== faits par balayage
def aides_at(c: str) -> set[str]:
    out = git("ls-tree", "--name-only", f"{c}:backend/data/aides")
    return {x for x in out.split("\n") if x.endswith(".yaml")}


def partie_balayages(premiere_c) -> dict:
    dire()
    dire("=" * 78)
    dire("Faits neufs par aide, attribution git (premier commit où la clé apparaît)")
    dire("=" * 78)
    res = {}
    for nom, commits in (
        ("2026-09-18", ["84bdd821"]),
        ("2026-09-29", ["1d94a758"]),
        ("2026-10-04", ["fdde0102", "6d6faf13"]),
    ):
        neufs_f: set[str] = set()
        neufs_a: set[str] = set()
        cites_par_neuves = 0
        orph = 0
        for c in commits:
            full = git("rev-parse", "--short=8", c).strip()
            neufs_f |= {k for k, cc in premiere_c.items() if cc[:8] == full[:8]}
            avant = aides_at(f"{c}^")
            neufs_a |= aides_at(c) - avant
        # orphelins : faits neufs cités par aucune aide au commit
        c = commits[-1]
        par = defaultdict(set)
        for a in aides_at(c):
            d = yaml.safe_load(blob(c, f"backend/data/aides/{a}")) or {}
            acc: set[str] = set()
            refs_rec({k: v for k, v in d.items() if k != "fiche"}, acc)
            for x in acc:
                par[x].add(a)
        for k in neufs_f:
            if not par.get(k):
                orph += 1
            elif par[k] & neufs_a:
                cites_par_neuves += 1
        r = len(neufs_f) / len(neufs_a) if neufs_a else float("nan")
        dire(
            f"  {nom} {commits} : {len(neufs_f)} faits neufs / {len(neufs_a)} aides neuves = {r:.2f} ; "
            f"faits neufs orphelins au commit {orph} ; cités par une aide neuve {cites_par_neuves} ; "
            f"ratio sans orphelins {(len(neufs_f) - orph) / len(neufs_a):.2f}"
        )
        res[nom] = {
            "slugs_aides": sorted(x[:-5] for x in neufs_a),
            "faits": len(neufs_f),
            "aides": len(neufs_a),
            "orphelins": orph,
            "cites_par_neuves": cites_par_neuves,
        }
    return res


# ===================================================================== devenir
def partie_devenir(hist, keys_at, premiere_c, pending_ever) -> dict:
    dire()
    dire("=" * 78)
    dire("Devenir des faits passés par facts_pending.yaml")
    dire("=" * 78)
    head_f = set((lire_yaml(BACKEND / "data/facts.yaml") or {}).keys())
    head_p = set((lire_yaml(BACKEND / "data/facts_pending.yaml") or {}).keys())
    txt = (BACKEND / "data/facts.yaml").read_text(encoding="utf-8")
    fleches = {}
    hors_doublon = set()
    section = ""
    for li in txt.splitlines():
        mt = re.match(r"^#\s*(Fusions appliquées|Scissions|Renommages)", li)
        if mt:
            section = mt.group(1)
        elif re.match(r"^[a-z0-9_]+:", li) or li.startswith("# ═"):
            section = ""
        m = re.match(r"^#\s+([a-z0-9_]+)\s+→\s+`?([a-z0-9_]+)", li)
        if m:
            fleches.setdefault(m.group(1), m.group(2))
            if section in ("Scissions", "Renommages"):
                hors_doublon.add(m.group(1))
    dire(
        f"  flèches de facts.yaml : {len(fleches)}, dont scissions ou renommages {len(hors_doublon)}"
    )
    tables_fus, tables_ret, seches = {}, {}, {}
    for f in sorted((BACKEND / "data/fusions").glob("*.yaml")):
        d = lire_yaml(f) or {}
        for e in d.get("fusions") or []:
            if e.get("garder"):
                tables_fus.setdefault(e["retirer"], (e["garder"], f.name))
            else:
                seches.setdefault(e["retirer"], (e.get("motif") or "", f.name))
        for e in d.get("retypages") or []:
            tables_ret.setdefault(e["fait"], f.name)
    cat = Counter()
    detail = {}
    for k in pending_ever:
        if k in head_p:
            c = "encore_en_attente"
        elif k in head_f:
            c = "present_facts_yaml"
        elif k in fleches or k in tables_fus:
            c = "fusionne"
        elif k in tables_ret:
            c = "retire_par_table_retypage:" + tables_ret[k]
        elif k in seches:
            c = "suppression_table_sans_garder:" + seches[k][1]
        else:
            c = "sans_trace"
        cat[c] += 1
        detail[k] = c
    n = len(pending_ever)
    dire(f"  clés passées par pending : {n}")
    for c, v in cat.most_common():
        dire(f"    {c:70s} {tx(v, n)}")
    ret_orph = sum(v for c, v in cat.items() if "orphelins" in c)
    dire(f"  dont tables d'orphelins (aide écartée, aucun retypage de condition) : {ret_orph}")

    # « Refaisait un fait existant » : cible ou jumeau (famille) vu dans un commit ANTÉRIEUR
    ordre = {c: i for i, (c, _) in enumerate(hist)}
    cible_de = {}
    for k in pending_ever:
        if k in fleches:
            cible_de[k] = fleches[k]
        elif k in tables_fus:
            cible_de[k] = tables_fus[k][0]
    for k, (motif, _f) in seches.items():
        if k in pending_ever:
            m = re.search(r"`([a-z0-9_]+)`", motif)
            if m:
                cible_de.setdefault(k, m.group(1))
    famille = defaultdict(set)
    for k, c in cible_de.items():
        famille[c].add(k)
    pos = Counter()
    for k in hors_doublon:
        cible_de.pop(k, None)
    for k, c in cible_de.items():
        i0 = ordre.get(premiere_c.get(k))
        cand = ({c} | famille[c]) - {k}
        icand = [ordre[premiere_c[x]] for x in cand if x in premiere_c and premiere_c[x] in ordre]
        icible = ordre.get(premiere_c.get(c)) if c in premiere_c else None
        orig = "seche" if k in seches and k not in fleches and k not in tables_fus else "fusion"
        if icible is not None and i0 is not None and icible < i0:
            pos[(orig, "cible_avant")] += 1
        elif icand and i0 is not None and min(icand) < i0:
            pos[(orig, "jumeau_avant")] += 1
        elif (icible is not None and icible == i0) or (icand and min(icand) == i0):
            pos[(orig, "meme_commit")] += 1
        else:
            pos[(orig, "apres_ou_jamais")] += 1
    dire(f"  paires (fait retiré -> fait gardé ou jumeau nommé) : {len(cible_de)}")
    for k_, v in sorted(pos.items()):
        dire(f"    {k_} : {v}")
    bas = sum(v for (o, p), v in pos.items() if p in ("cible_avant", "jumeau_avant"))
    haut = bas + sum(v for (o, p), v in pos.items() if p == "meme_commit")
    dire(
        f"  refaisait un fait existant (cible ou jumeau antérieur) : borne basse {tx(bas, n)}, haute {tx(haut, n)}"
    )
    return {
        "categories": dict(cat),
        "position": {f"{a}|{b}": v for (a, b), v in pos.items()},
        "bas": bas,
        "haut": haut,
        "n": n,
    }


# ========================================================================== J2
SECTIONS = {
    "## Démarches": "demarche",
    "## Promesses": "promesse",
    "## À trancher": "a_trancher",
    "## Critères qui portent": "critere",
    "## Critères : restent": "critere",
}


def lire_rapport() -> tuple[dict, dict, list[str]]:
    lignes = (
        (BACKEND / "data/reviews/2026-09-23-tri-critere-demarche.md")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    verdict, gates = {}, {}
    sec = None
    fin = None
    for i, li in enumerate(lignes):
        if li.startswith("## "):
            sec = next((v for k, v in SECTIONS.items() if li.startswith(k)), None)
            if li.startswith("## Arbitrages"):
                fin = i
        m = re.match(r"^\| `([a-z0-9_]+)` \| (\d+) \|", li)
        if m and sec:
            if m.group(1) in verdict and verdict[m.group(1)] != sec:
                dire(f"  ! {m.group(1)} classé deux fois : {verdict[m.group(1)]} et {sec}")
            verdict.setdefault(m.group(1), sec)
            gates.setdefault(m.group(1), int(m.group(2)))
    return verdict, gates, lignes[fin:]


def partie_j2(idx) -> dict:
    dire()
    dire("=" * 78)
    dire("J2 : critère / démarche / promesse")
    dire("=" * 78)
    verdict, gates, arb = lire_rapport()
    c = Counter(verdict.values())
    dire(f"  faits du rapport : {len(verdict)} {dict(c)} ; gates {sum(gates.values())}")
    texte = "\n".join(arb)

    def bloc(debut: str) -> set[str]:
        m = re.search(re.escape(debut) + r"(.*?)\n\n", texte, re.S)
        return set(re.findall(r"`([a-z0-9_]+)`", m.group(1))) if m else set()

    r1_crit = bloc("**Gardés en question (critères)**")
    r1_dem = bloc("**Sortis du questionnaire en démarche**")
    r1_pro = bloc("**Sortis du questionnaire en promesse**")
    dire(f"  tour 1 : critères {len(r1_crit)}, démarches {len(r1_dem)}, promesses {len(r1_pro)}")
    retenue = dict(verdict)
    source = dict.fromkeys(verdict, "agents")
    for s, v in ((r1_crit, "critere"), (r1_dem, "demarche"), (r1_pro, "promesse")):
        for k in s:
            if k in retenue:
                retenue[k] = v
                source[k] = "felix_tour1"
    # tour 2
    t2_pro = {
        "prevoit_programme_valorisation",
        "projet_actions_culturelles",
        "developpe_activites_valorisation",
    }
    for k in t2_pro:
        if k in retenue:
            retenue[k] = "promesse"
            source[k] = "felix_tour2"
    if "visite_interieure_exterieure_possible" in retenue:
        retenue["visite_interieure_exterieure_possible"] = "demarche"
        source["visite_interieure_exterieure_possible"] = "felix_tour2"
    # tour 3 : labels (lot-5g)
    l5g = lire_yaml(BACKEND / "data/fusions/lot-5g-labels.yaml") or {}
    t3 = {e["fait"]: e.get("kind", "manual_check") for e in l5g.get("retypages") or []}
    for k in t3:
        if k in retenue:
            retenue[k] = "demarche"
            source[k] = "felix_tour3"
    attente = {"appellation_musee_de_france", "bateau_interet_patrimonial", "label_pij_bij_obtenu"}
    dans = attente & set(verdict)
    dire(
        f"  tour 3, « non traités, en attente » présents dans les 457 : {sorted(dans)} "
        f"(verdict agents : {[verdict[k] for k in sorted(dans)]})"
    )
    nommes = {k for k, s in source.items() if s != "agents"}
    renv = {k for k in nommes if verdict[k] not in ("a_trancher", retenue[k])}
    conf = {k for k in nommes if verdict[k] == retenue[k]}
    tr = {k for k in nommes if verdict[k] == "a_trancher"}
    dire(
        f"  faits du rapport nommés par une décision de Félix : {len(nommes)} ; "
        f"à trancher tranchés {len(tr)}, renversés {len(renv)}, confirmés {len(conf)}"
    )
    dire(f"    renversés : {sorted((k, verdict[k], retenue[k]) for k in renv)}")
    restant = [k for k, v in retenue.items() if v == "a_trancher"]
    dire(f"  « à trancher » restés sans décision nommée : {len(restant)} {restant}")
    # tables lot-5*
    applique = {}
    for f in sorted((BACKEND / "data/fusions").glob("lot-5*.yaml")):
        for e in (lire_yaml(f) or {}).get("retypages") or []:
            k = e["fait"]
            kind = e.get("kind") or ("info" if k.startswith("s_engage") else "manual_check")
            applique[k] = ("promesse" if kind == "info" else "demarche", f.name)
    c_app = Counter(v[0] for k, v in applique.items() if k in verdict)
    dire(f"  lot-5* : {len(applique)} faits, dans le rapport {sum(c_app.values())} {dict(c_app)}")
    # classe retenue : décision de Félix, sinon agents ; à trancher restants -> table si présente
    fin_ = {}
    for k, v in retenue.items():
        if v == "a_trancher":
            v = applique[k][0] if k in applique else "critere"
        fin_[k] = v
    cf = Counter(fin_.values())
    dire(f"  classe retenue (ma reconstruction) : {dict(cf)}")
    # désaccords table / décision écrite
    contra = sorted(
        (k, fin_[k], applique[k][0]) for k in applique if k in fin_ and fin_[k] != applique[k][0]
    )
    dire(f"  décision écrite != table appliquée : {len(contra)} {contra}")
    # Accord agents / classe appliquée (table lot-5*, sinon présent à c6d1e85f -> critère)
    k_c6 = cles("c6d1e85f", F_FACTS) | cles("c6d1e85f", F_PENDING)
    app = {}
    for k in verdict:
        if k in applique:
            app[k] = applique[k][0]
        elif k in k_c6:
            app[k] = "critere"
        else:
            app[k] = "retire_sans_table"
    ev = [k for k in verdict if verdict[k] != "a_trancher" and app[k] != "retire_sans_table"]
    acc = sum(verdict[k] == app[k] for k in ev)
    dire(
        f"  accord agents / classe appliquée (hors à trancher et retirés) : {tx(acc, len(ev))} ; "
        f"retirés sans table {sum(v == 'retire_sans_table' for v in app.values())}"
    )
    # Décideur : tous critère
    err = sum(1 for v in fin_.values() if v != "critere")
    g_err = sum(gates[k] for k, v in fin_.items() if v != "critere")
    dire(
        f"  faits non-critère parmi les 457 : {tx(err, len(fin_))} ; gates {tx(g_err, sum(gates.values()))}"
    )
    dire(
        f"  précision de la classe « critère » posée par le typage : {tx(len(fin_) - err, len(fin_))}"
    )

    # promesse regex
    class F:
        def __init__(self, q):
            self.question = q

    pro = [k for k, v in fin_.items() if v == "promesse"]
    nonpro = [k for k, v in fin_.items() if v != "promesse"]
    vu = sum(promesse(k, F(idx[k]["question"])) for k in pro if k in idx)
    fpos = [k for k in nonpro if k in idx and promesse(k, F(idx[k]["question"]))]
    dire(
        f"  règle promesse() : rappel {tx(vu, len(pro))} ; non-promesses marquées {len(fpos)} {fpos}"
    )
    return {
        "verdict": verdict,
        "retenue": fin_,
        "source": source,
        "gates": gates,
        "nommes": len(nommes),
        "renverses": sorted(renv),
        "confirmes": sorted(conf),
        "tranches": len(tr),
        "restants": restant,
        "attente": sorted(dans),
        "classe": dict(cf),
        "err": err,
        "g_err": g_err,
        "promesse_vu": vu,
        "promesse_n": len(pro),
    }


def partie_j2_origine(j2) -> dict:
    """Le gate des 457 a-t-il été posé par l'ingestion, ou par un retypage ultérieur ?"""
    dire()
    dire(
        "J2 : origine des gates user_fact des 457 (transitions.json, changements relevés dans git)"
    )
    tr = lire_json(ENTREES / "transitions.json")
    faits = set(j2["verdict"])
    vers_uf = defaultdict(int)
    for t in tr:
        av, ap = t["avant"], t["apres"]
        if t["date"] > "2026-09-23":
            continue
        if (
            ap.get("kind") == "user_fact"
            and ap.get("effect") == "gate"
            and ap.get("fact") in faits
            and av.get("kind") != "user_fact"
        ):
            vers_uf[ap["fact"]] += 1
    nf = len(vers_uf)
    ng = sum(vers_uf.values())
    dire(
        f"  faits du rapport dont au moins un gate est né d'un retypage vers user_fact avant le 2026-09-23 : "
        f"{tx(nf, len(faits))} ; conditions concernées {ng}"
    )
    nonc = [k for k in vers_uf if j2["retenue"][k] != "critere"]
    dire(f"    parmi eux, classe retenue non-critère : {len(nonc)}")
    return {"faits_retypes_vers_user_fact": nf, "conditions": ng, "non_critere": len(nonc)}


# ======================================================================= coût
def partie_cout(usage, recentes_slugs: list[str]) -> dict:
    dire()
    dire("=" * 78)
    dire("Coût en questions (profils_questionnaire importé, rien n'est écrit)")
    dire("=" * 78)
    from aides_schema import load_all_aides, load_facts, load_pending_facts
    from profils_questionnaire import PROFILS, delta_tronc, mesurer

    t0 = time.perf_counter()
    aides = load_all_aides()
    facts = {**load_facts(), **load_pending_facts()}
    tchg = time.perf_counter() - t0
    dire(f"  chargement : {len(aides)} aides, {len(facts)} faits, {tchg:.2f} s")
    t0 = time.perf_counter()
    tronc_ids: dict[str, set[str]] = {}
    for nom, p in PROFILS.items():
        m = mesurer(aides, facts, p)
        tronc_ids[nom] = {q["id"] for q in m.tronc}
    t16 = time.perf_counter() - t0
    dire(f"  {len(PROFILS)} diagnostics : {t16:.2f} s")
    un = [k for k in usage["tous"] if len(usage["par"].get(k, [])) == 1]
    au_tronc = [k for k in un if any(k in s for s in tronc_ids.values())]
    dire(
        f"  faits à une aide au tronc d'au moins un profil : {tx(len(au_tronc), len(un))} {au_tronc[:5]}"
    )
    # chronométrage de delta_tronc sur 10 aides récentes
    recentes = [a for a in recentes_slugs if a in aides][:12]
    durees = []
    for s in recentes:
        sans = {k: v for k, v in aides.items() if k != s}
        t0 = time.perf_counter()
        delta_tronc(sans, aides, facts)
        durees.append(time.perf_counter() - t0)
    dire(
        f"  delta_tronc sur {len(durees)} aides : médiane {statistics.median(durees):.2f} s, "
        f"max {max(durees):.2f} s"
    )
    return {
        "chargement_s": tchg,
        "diag16_s": t16,
        "un_au_tronc": len(au_tronc),
        "un": len(un),
        "delta_mediane_s": statistics.median(durees),
        "delta_max_s": max(durees),
    }


# ======================================================================= Jev
def partie_jev() -> dict:
    dire()
    dire(
        "Jev : arithmétique du coût annoncé (0,042 $ par million de jetons d'entrée, docs/jev.md:20)"
    )
    out = {}
    for nom, j in (
        ("J1 choice k=6", 245_837),
        ("J1 noul", 110_101),
        ("J2 choice", 115_561),
        ("J2 condition", 1_082_400),
    ):
        out[nom] = j * 0.042e-6
        dire(f"  {nom} : {j} jetons -> {out[nom]:.4f} $")
    return out


# ================================================================== journaux
ENTETE = re.compile(r"^(\S+) — (\d{4}-\d{2}-\d{2})T\S* — ingestion")
AJOUTE = re.compile(r"^\[sortie\] Fait « ([a-z0-9_]+) » ajouté")


def partie_journaux() -> dict:
    """Comptage indépendant et volontairement étroit : un fait compte s'il a reçu la
    sortie « Fait « x » ajouté » de proposer_fait ; une aide est ok si son bloc porte
    « [*] OK ». Fenêtres : 2026-09-18 et 19 ; 2026-09-29 ; 2026-10-04 et 05."""
    dire()
    dire("Journaux d'ingestion par aide (logs/ingest-*.log), comptage étroit")
    fen = {
        "2026-09-18": ("2026-09-18", "2026-09-19"),
        "2026-09-29": ("2026-09-29", "2026-09-29"),
        "2026-10-04": ("2026-10-04", "2026-10-05"),
    }
    res = {}
    blocs = []
    vus: set[str] = set()
    for f in sorted((BACKEND / "data/reviews/logs").rglob("ingest-*.log")):
        if "refonte" in f.parts:
            continue
        cur = None
        for li in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = ENTETE.match(li)
            if m:
                if li in vus:  # même bloc copié dans deux dossiers
                    cur = None
                    continue
                vus.add(li)
                cur = {"slug": m.group(1), "date": m.group(2), "ok": False, "faits": set()}
                blocs.append(cur)
                continue
            if cur is None:
                continue
            if li.startswith("[*] OK"):
                cur["ok"] = True
            m2 = AJOUTE.match(li)
            if m2:
                cur["faits"].add(m2.group(1))
    for nom, (d0, d1) in fen.items():
        bl = [b for b in blocs if d0 <= b["date"] <= d1]
        ok = {b["slug"] for b in bl if b["ok"]}
        faits = set().union(*[b["faits"] for b in bl]) if bl else set()
        dire(
            f"  {nom} : {len(bl)} blocs, {len(ok)} aides ok, {len(faits)} faits « ajouté » "
            f"= {len(faits) / len(ok) if ok else float('nan'):.2f} par aide ok"
        )
        res[nom] = {"blocs": len(bl), "ok": len(ok), "faits": len(faits)}
    return res


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    idx = lire_json(ENTREES / "index_faits.json")
    hist = histoire()
    dire(
        f"HEAD {git('rev-parse', '--short=8', 'HEAD').strip()} ; {len(hist)} commits touchent les deux fichiers de faits"
    )
    keys_at: dict[str, set[str]] = {}
    pending_ever: set[str] = set()
    premiere_c: dict[str, str] = {}
    premiere_t: dict[str, int] = {}
    for c, t in hist:
        kf, kp = cles(c, F_FACTS), cles(c, F_PENDING)
        keys_at[c] = kf | kp
        pending_ever |= kp
        for k in kf | kp:
            if k not in premiere_c:
                premiere_c[k] = c
                premiere_t[k] = t
    dire(f"clés passées par facts_pending.yaml : {len(pending_ever)}")
    r = {}
    r["j1"] = partie_j1(hist, premiere_t, idx)
    r["j1_en_place"] = partie_j1_en_place(hist, keys_at, premiere_c, idx, r["j1"]["pos"])
    r["charge"] = partie_charge(keys_at, premiere_c, pending_ever, idx)
    r["usage"] = usage_head()
    full = {c: git("rev-parse", c).strip() for c, _ in hist}
    pc = {k: full[c] for k, c in premiere_c.items()}
    r["balayages"] = partie_balayages(pc)
    r["devenir"] = partie_devenir(hist, keys_at, premiere_c, pending_ever)
    r["j2"] = partie_j2(idx)
    r["j2_origine"] = partie_j2_origine(r["j2"])
    r["cout"] = partie_cout(r["usage"], r["balayages"]["2026-10-04"]["slugs_aides"])
    r["jev"] = partie_jev()
    r["journaux"] = partie_journaux()
    r["usage"] = {"dist": r["usage"]["dist"]}
    r["j1"].pop("pos")
    (SORTIE / "resume.txt").write_text("\n".join(LIGNES) + "\n", encoding="utf-8")
    (SORTIE / "resultats.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=1, default=list), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
