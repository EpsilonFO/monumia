"""Mesure M06 de la refonte : ligne de base des décisions sur les faits de l'ontologie.

    cd backend && uv run python scripts/mesures/faits.py
    cd backend && uv run python scripts/mesures/faits.py --sans-moteur   # saute la partie 5

Produit, dans `backend/data/reviews/logs/refonte/2026-10-10-faits-1/` (créé au besoin) :

- `resume.txt` : tout ce que le script imprime, chiffres et effectifs ;
- `j1_paires.json`, `j1_courbe.json`, `j1_validation_croisee.json`, `j1_alertes.json` :
  le contrôle lexical de doublon (`ingestion/faits.py::_proches`) rejoué sur les
  140 paires positives et les 208 négatives de `paires_etiquetees.json` ;
- `usage.json` : nombre d'aides qui citent chaque fait, à HEAD et à quatre commits ;
- `faits_par_balayage.json` : faits neufs par aide ingérée, trois méthodes d'attribution ;
- `devenir_pending.json` : devenir de chaque fait passé par `facts_pending.yaml` ;
- `j2.json` : vérité terrain du tri critère / démarche / promesse et erreur du typage initial ;
- `cout_questions.json` : coût en questions de chaque fait (16 profils) et temps de calcul ;
- `jev_estimation.json` : jetons et coût estimés d'une mesure de J1 et J2 par Jev.

Lecture seule : aucune écriture hors du dossier de sortie, aucun appel réseau ni
de modèle, aucune commande git qui écrit (seulement `rev-list`, `log`, `ls-tree`,
`cat-file`). Les entrées du bilan du 2026-10-07 sont lues dans
`backend/data/reviews/logs/refonte-entrees/be997c31-bilan-2026-10-07/`.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
SCRIPTS = BACKEND / "scripts"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(SCRIPTS))

from ingestion.faits import MAX_FAITS_PAR_AIDE, MAX_PROCHES, SEUIL_PROXIMITE, promesse  # noqa: E402
from ingestion.ontologie import SEUIL_AUDIT  # noqa: E402
from veille_text import normalize  # noqa: E402

ENTREES = BACKEND / "data/reviews/logs/refonte-entrees/be997c31-bilan-2026-10-07"
LOGS = BACKEND / "data/reviews/logs"
SORTIE_DEFAUT = BACKEND / "data/reviews/logs/refonte/2026-10-10-faits-1"
FACTS = "backend/data/facts.yaml"
PENDING = "backend/data/facts_pending.yaml"
AIDES = "backend/data/aides"
RAPPORT_TRI = BACKEND / "data/reviews/2026-09-23-tri-critere-demarche.md"
FUSIONS = BACKEND / "data/fusions"

_lignes: list[str] = []


def dire(texte: str = "") -> None:
    print(texte)
    _lignes.append(texte)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def taux(k: int, n: int) -> str:
    p, lo, hi = wilson(k, n)
    if n == 0:
        return f"{k}/0"
    return f"{k}/{n} = {100 * p:.1f} % [IC95 {100 * lo:.1f} ; {100 * hi:.1f}]"


def taux_json(k: int, n: int) -> dict:
    p, lo, hi = wilson(k, n)
    return {"k": k, "n": n, "p": p, "ic95": [lo, hi]}


# ---------------------------------------------------------------------------
# Git en lecture seule
# ---------------------------------------------------------------------------


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout


class Blobs:
    """`git cat-file --batch` : des milliers de blobs sans un processus chacun."""

    def __init__(self) -> None:
        self.p = subprocess.Popen(
            ["git", "-C", str(REPO), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        self.cache: dict[str, str | None] = {}

    def lire(self, ref: str) -> str | None:
        if ref in self.cache:
            return self.cache[ref]
        assert self.p.stdin and self.p.stdout
        self.p.stdin.write((ref + "\n").encode())
        self.p.stdin.flush()
        entete = self.p.stdout.readline().decode().split()
        if len(entete) < 3 or entete[1] == "missing":
            self.cache[ref] = None
            return None
        data = self.p.stdout.read(int(entete[2]))
        self.p.stdout.read(1)
        texte = data.decode("utf-8", errors="replace")
        self.cache[ref] = texte
        return texte


BLOBS = Blobs()
CLE_RE = re.compile(r"^([a-z0-9_]+):", re.M)


def cles(commit: str, chemin: str) -> set[str]:
    texte = BLOBS.lire(f"{commit}:{chemin}")
    return set(CLE_RE.findall(texte)) if texte else set()


def commits_chrono(*chemins: str) -> list[tuple[str, int, str]]:
    """(hash, date de commit en secondes, date courte), toute l'histoire, du plus ancien au plus récent."""
    sortie = git("log", "--full-history", "--format=%H %ct %cs", "HEAD", "--", *chemins)
    lignes = [li.split() for li in sortie.splitlines() if li.strip()]
    return sorted(((h, int(t), d) for h, t, d in lignes), key=lambda x: x[1])


def slugs_aides(commit: str) -> tuple[set[str], set[str]]:
    noms = git("ls-tree", "--name-only", commit, AIDES + "/").split()
    yamls = {n.split("/")[-1][: -len(".yaml")] for n in noms if n.endswith(".yaml")}
    echecs = {n.split("/")[-1][: -len(".yaml.echec")] for n in noms if n.endswith(".yaml.echec")}
    return yamls, echecs


# ---------------------------------------------------------------------------
# Histoire des faits : première apparition, présence à chaque commit
# ---------------------------------------------------------------------------


class Histoire:
    def __init__(self) -> None:
        self.commits = commits_chrono(FACTS, PENDING)
        self.facts_a: dict[str, set[str]] = {}
        self.pending_a: dict[str, set[str]] = {}
        self.premiere: dict[str, tuple[str, int, str]] = {}  # clé -> (commit, t, date)
        self.premiere_pending: dict[str, tuple[str, int, str]] = {}
        self.deja_approuve: set[str] = set()
        for h, t, d in self.commits:
            f = cles(h, FACTS)
            p = cles(h, PENDING)
            self.facts_a[h] = f
            self.pending_a[h] = p
            self.deja_approuve |= f
            for k in f | p:
                self.premiere.setdefault(k, (h, t, d))
            for k in p:
                self.premiere_pending.setdefault(k, (h, t, d))

    def pool(self, commit: str) -> set[str]:
        return self.facts_a[commit] | self.pending_a[commit]


# ---------------------------------------------------------------------------
# Partie 1 : J1, le contrôle lexical de doublon
# ---------------------------------------------------------------------------


def score_production(a: str, b: str, index: dict[str, dict]) -> float:
    """Le score de `ingestion/faits.py::_proches` (lignes 225-232), sur l'index historique."""
    return max(
        SequenceMatcher(
            None, normalize(index[a]["question"]), normalize(index[b]["question"])
        ).ratio(),
        SequenceMatcher(None, a.replace("_", " "), b.replace("_", " ")).ratio(),
    )


def sections_fleches(facts_txt: str) -> dict[str, str]:
    """Pour chaque clé à gauche d'une flèche en commentaire de facts.yaml, le titre de sa section."""
    section = "?"
    out: dict[str, str] = {}
    for li in facts_txt.splitlines():
        if re.match(r"^# (Fusions appliquées|Scissions|Renommages)", li):
            section = li[2:].split("(")[0].strip()
        elif re.match(r"^# ── Faits approuvés|^# ═+|^# Faits NEUFS|^# 66 faits", li):
            section = "autre bloc"
        m = re.match(r"^#\s+([a-z0-9_]+(?:,\s*[a-z0-9_]+)*),?\s*→\s*(.+)$", li)
        if m:
            for k in [s.strip() for s in m.group(1).split(",") if s.strip()]:
                out.setdefault(k, section)
    return out


def partie_j1(hist: Histoire, sortie: Path) -> dict:
    dire("=" * 78)
    dire("PARTIE 1. J1 : contrôle lexical de doublon (ingestion/faits.py::_proches)")
    dire("=" * 78)
    dire(
        f"Constantes lues dans le code : SEUIL_PROXIMITE = {SEUIL_PROXIMITE} "
        f"(scripts/ingestion/faits.py:64), MAX_PROCHES = {MAX_PROCHES} (:67), "
        f"SEUIL_AUDIT = {SEUIL_AUDIT:.2f} (scripts/ingestion/ontologie.py:54)"
    )
    index: dict[str, dict] = json.loads((ENTREES / "index_faits.json").read_text())
    paires = json.loads((ENTREES / "paires_etiquetees.json").read_text())
    brutes: dict[str, list] = json.loads((ENTREES / "paires_fusion.json").read_text())
    pos = paires["positives"]
    neg = paires["negatives"]
    dire(f"index_faits.json : {len(index)} clés (dernière définition connue dans git)")
    dire(
        f"paires_fusion.json : {len(brutes)} paires brutes, sources {dict(Counter(v[0] for v in brutes.values()))}"
    )
    dire(f"paires_etiquetees.json : {len(pos)} positives, {len(neg)} négatives")

    # 1.a recalcul des scores avec la formule de production
    ecarts = 0
    lignes_paires = []
    facts_txt = (BACKEND / "data/facts.yaml").read_text(encoding="utf-8")
    section = sections_fleches(facts_txt)
    for retire, garde, s_stocke, meme_type, meme_scope in pos:
        s = score_production(retire, garde, index)
        ecarts += abs(s - s_stocke) > 1e-9
        src = brutes.get(retire, ["?", ""])[0]
        lignes_paires.append(
            {
                "label": 1,
                "a": retire,
                "b": garde,
                "score": s,
                "meme_type": meme_type,
                "meme_scope": meme_scope,
                "source": src,
                "section_facts_yaml": section.get(retire) if src == "facts.yaml" else None,
                "type_a": index[retire]["type"],
                "type_b": index[garde]["type"],
            }
        )
    for a, b, s_stocke in neg:
        s = score_production(a, b, index)
        ecarts += abs(s - s_stocke) > 1e-9
        lignes_paires.append({"label": 0, "a": a, "b": b, "score": s})
    dire(f"scores recalculés avec la formule de production : {ecarts} écart(s) au score stocké")

    P = [x for x in lignes_paires if x["label"] == 1]
    N = [x for x in lignes_paires if x["label"] == 0]
    tp = sum(1 for x in P if x["score"] >= SEUIL_PROXIMITE)
    fp = sum(1 for x in N if x["score"] >= SEUIL_PROXIMITE)
    dire("")
    dire(f"Au seuil {SEUIL_PROXIMITE}, sur la paire (fait retiré, fait gardé) :")
    dire(f"  rappel des doublons connus : {taux(tp, len(P))}")
    dire(f"  voisins approuvés alertés  : {taux(fp, len(N))}")

    # 1.b composition et bruit des positives
    dire("")
    dire("Composition des positives (provenance) :")
    for (src, sec), n in Counter((x["source"], x["section_facts_yaml"]) for x in P).most_common():
        k = sum(
            1
            for x in P
            if (x["source"], x["section_facts_yaml"]) == (src, sec)
            and x["score"] >= SEUIL_PROXIMITE
        )
        dire(f"  {src:<35} section {str(sec):<22} {n:4d} paires, rappel {taux(k, n)}")
    absorb = [x for x in P if x["type_a"] != x["type_b"]]
    dire(
        f"  type différent entre retiré et gardé (absorption, souvent booléen -> enum/multi_enum) : {len(absorb)}/{len(P)}"
    )
    k_abs = sum(1 for x in absorb if x["score"] >= SEUIL_PROXIMITE)
    k_meme = sum(1 for x in P if x["type_a"] == x["type_b"] and x["score"] >= SEUIL_PROXIMITE)
    dire(f"    rappel sur ces absorptions : {taux(k_abs, len(absorb))}")
    dire(f"    rappel sur les paires de même type : {taux(k_meme, len(P) - len(absorb))}")
    # Négatives : même paire aussi positive ? un des deux fusionné plus tard ?
    cles_pos = {tuple(sorted((x["a"], x["b"]))) for x in P}
    retires = {x["a"] for x in P}
    neg_aussi_pos = sum(1 for x in N if tuple(sorted((x["a"], x["b"]))) in cles_pos)
    neg_un_retire = sum(1 for x in N if x["a"] in retires or x["b"] in retires)
    dire(
        f"Négatives aussi positives : {neg_aussi_pos} ; dont un membre a été fusionné ailleurs : {neg_un_retire}"
    )
    # Qui a écrit la justification qui fonde la négative ? (commentaire de tête du fait)
    auteur = Counter()
    for x in N:
        com = " ".join(index[a]["commentaire"] for a in (x["a"], x["b"]))
        if "Proposé par ingerer.py" in com:
            auteur["ingerer.py (LLM du pipeline)"] += 1
        elif re.search(r"ingest-aide|Proposé (le|par)", com):
            auteur["/ingest-aide ou proposition datée (Claude en session)"] += 1
        else:
            auteur["autre commentaire (revue, refonte)"] += 1
    dire(f"Provenance du commentaire qui fonde les négatives : {dict(auteur)}")

    # 1.c courbe
    courbe = []
    for i in range(20, 100, 2):
        s = i / 100
        k1 = sum(1 for x in P if x["score"] >= s)
        k0 = sum(1 for x in N if x["score"] >= s)
        courbe.append(
            {"seuil": s, "rappel": taux_json(k1, len(P)), "alertes": taux_json(k0, len(N))}
        )
    for s in (0.60, SEUIL_PROXIMITE):
        k1 = sum(1 for x in P if x["score"] >= s)
        k0 = sum(1 for x in N if x["score"] >= s)
        courbe.append(
            {"seuil": s, "rappel": taux_json(k1, len(P)), "alertes": taux_json(k0, len(N))}
        )
    courbe.sort(key=lambda c: c["seuil"])
    dire("")
    dire("Courbe rappel / fausses alertes selon le seuil (paires) :")
    for c in courbe:
        if round(c["seuil"] * 100) % 10 == 0 or c["seuil"] in (SEUIL_PROXIMITE, 0.6, 0.64, 0.72):
            r, a = c["rappel"], c["alertes"]
            dire(
                f"  seuil {c['seuil']:.2f} : rappel {r['k']:3d}/{r['n']} ({100 * r['p']:5.1f} %)"
                f"  alertes {a['k']:3d}/{a['n']} ({100 * a['p']:5.1f} %)"
            )
    sp = sorted(x["score"] for x in P)
    sn = sorted(x["score"] for x in N)
    dire(
        f"  positives : min {sp[0]:.2f}, médiane {sp[len(sp) // 2]:.2f}, max {sp[-1]:.2f} ; "
        f"négatives : min {sn[0]:.2f}, médiane {sn[len(sn) // 2]:.2f}, max {sn[-1]:.2f}"
    )
    auc = sum((p > n) + 0.5 * (p == n) for p in sp for n in sn) / (len(sp) * len(sn))
    dire(f"  AUC du score (positives contre négatives) : {auc:.3f}")

    # 1.d validation croisée du seuil (deux plis stratifiés, 200 tirages)
    rng = random.Random(20261010)
    grille = [i / 100 for i in range(20, 100)]
    resultats_cv = {"youden": [], "alertes_max_6pct": []}
    for _ in range(200):
        Pm, Nm = P[:], N[:]
        rng.shuffle(Pm)
        rng.shuffle(Nm)
        plis = [
            (Pm[: len(Pm) // 2], Nm[: len(Nm) // 2], Pm[len(Pm) // 2 :], Nm[len(Nm) // 2 :]),
            (Pm[len(Pm) // 2 :], Nm[len(Nm) // 2 :], Pm[: len(Pm) // 2], Nm[: len(Nm) // 2]),
        ]
        for pa, na, pb, nb in plis:

            def r(ps, s):
                return sum(1 for x in ps if x["score"] >= s) / len(ps)

            s_y = max(grille, key=lambda s: (r(pa, s) - r(na, s), -s))
            admissibles = [s for s in grille if r(na, s) <= 0.06]
            s_a = max(admissibles, key=lambda s: (r(pa, s), s)) if admissibles else 0.99
            resultats_cv["youden"].append((s_y, r(pb, s_y), r(nb, s_y)))
            resultats_cv["alertes_max_6pct"].append((s_a, r(pb, s_a), r(nb, s_a)))
    dire("")
    dire(
        "Validation croisée du choix de seuil (2 plis stratifiés, 70+104 / 70+104, 200 tirages, "
        "évaluation sur le pli tenu à part) :"
    )
    cv_json = {}
    for nom, res in resultats_cv.items():
        seuils = sorted(x[0] for x in res)
        rap = sorted(x[1] for x in res)
        ale = sorted(x[2] for x in res)

        def q(xs, f):
            return xs[int(f * (len(xs) - 1))]

        dire(
            f"  critère {nom:<17} : seuil médian {q(seuils, 0.5):.2f} [{q(seuils, 0.025):.2f} ; {q(seuils, 0.975):.2f}], "
            f"rappel tenu à part {100 * sum(rap) / len(rap):.1f} % [{100 * q(rap, 0.025):.1f} ; {100 * q(rap, 0.975):.1f}], "
            f"alertes {100 * sum(ale) / len(ale):.1f} % [{100 * q(ale, 0.025):.1f} ; {100 * q(ale, 0.975):.1f}]"
        )
        cv_json[nom] = {
            "seuil_median": q(seuils, 0.5),
            "rappel_moyen": sum(rap) / len(rap),
            "rappel_p2_5_p97_5": [q(rap, 0.025), q(rap, 0.975)],
            "alertes_moyen": sum(ale) / len(ale),
            "alertes_p2_5_p97_5": [q(ale, 0.025), q(ale, 0.975)],
        }

    # 1.e le contrôle tel qu'il tourne : pool du moment, 6 voisins au plus
    dire("")
    dire(
        "Le contrôle tel qu'il tourne : le fait retiré comparé aux faits présents (facts.yaml + "
        "facts_pending.yaml) au commit où il apparaît pour la première fois, 6 voisins au plus."
    )
    groupe: dict[str, set[str]] = defaultdict(set)
    for x in P:
        groupe[x["b"]].add(x["a"])
    stats = Counter()
    rangs_k: list[int | None] = []
    rangs_j: list[int | None] = []
    mots = {
        k: set(re.findall(r"[a-zà-ÿ]{4,}", normalize(v["question"] + " " + (v.get("help") or ""))))
        | {t for t in k.split("_") if len(t) > 2}
        for k, v in index.items()
    }

    def jaccard(u: str, v: str) -> float:
        x, y = mots[u], mots[v]
        return len(x & y) / len(x | y) if x and y else 0.0

    detail_moment = []
    for x in P:
        a, b = x["a"], x["b"]
        if a not in hist.premiere:
            stats["retire_absent_git"] += 1
            continue
        h, _t, d = hist.premiere[a]
        pool = (hist.pool(h) - {a}) & set(index)
        membres = ({b} | groupe[b]) - {a}
        presents = membres & pool
        cible_presente = b in pool
        stats["cible_presente"] += cible_presente
        stats["groupe_present"] += bool(presents)
        scores = sorted(((score_production(a, k, index), k) for k in pool), reverse=True)
        alerte = [(s, k) for s, k in scores if s >= SEUIL_PROXIMITE][:MAX_PROCHES]
        alerte_cles = {k for _s, k in alerte}
        rang = next((i for i, (_s, k) in enumerate(scores, 1) if k in presents), None)
        rangs_k.append(rang)
        sj = sorted(((jaccard(a, k), k) for k in pool), reverse=True)
        rangs_j.append(next((i for i, (_s, k) in enumerate(sj, 1) if k in presents), None))
        attrape = bool(presents & alerte_cles)
        stats["attrape"] += attrape
        stats["alerte_quelconque"] += bool(alerte)
        detail_moment.append(
            {
                "a": a,
                "b": b,
                "date": d,
                "cible_presente": cible_presente,
                "membres_presents": sorted(presents),
                "rang_meilleur_membre": rang,
                "alerte": [k for _s, k in alerte],
                "attrape": attrape,
            }
        )
    n_eval = len(detail_moment)
    dire(f"  positives datées dans git : {n_eval}/{len(P)}")
    dire(
        f"  cible gardée déjà présente au moment de la proposition : {taux(stats['cible_presente'], n_eval)}"
    )
    dire(
        f"  cible ou un fait de la même famille de fusion présent : {taux(stats['groupe_present'], n_eval)}"
    )
    n_g = stats["groupe_present"]
    dire(
        f"  parmi ces {n_g}, doublon présent dans les 6 voisins alertés : {taux(stats['attrape'], n_g)}"
    )
    for K in (1, 3, 6, 10, 20, 50):
        k = sum(1 for r in rangs_k if r is not None and r <= K)
        kj = sum(1 for r in rangs_j if r is not None and r <= K)
        dire(
            f"    rappel@{K:<2} sans seuil, score de production : {taux(k, n_g)} ; "
            f"Jaccard des mots (question + aide + clé) : {taux(kj, n_g)}"
        )
    tailles = sorted(len((hist.pool(hist.premiere[x["a"]][0]) - {x["a"]}) & set(index)) for x in P)
    dire(
        f"    taille du pool de candidats : médiane {tailles[len(tailles) // 2]}, de {tailles[0]} à {tailles[-1]}"
    )

    # 1.f taux d'alerte sur toutes les propositions passées par facts_pending
    alertes_props = []
    for k, (h, _t, d) in hist.premiere_pending.items():
        if k not in index:
            continue
        pool = (hist.pool(h) - {k}) & set(index)
        n_proches = sum(1 for o in pool if score_production(k, o, index) >= SEUIL_PROXIMITE)
        alertes_props.append({"cle": k, "date": d, "n_proches": n_proches})
    n_al = sum(1 for x in alertes_props if x["n_proches"])
    dire("")
    dire(
        "Charge du contrôle : part des faits passés par facts_pending.yaml qui auraient "
        "reçu au moins une alerte (pool du commit de première apparition, définitions de l'index) :"
    )
    dire(
        f"  {taux(n_al, len(alertes_props))} ; silence sur {taux(len(alertes_props) - n_al, len(alertes_props))} "
        "(la docstring, faits.py:57-60, annonce « se tait sur 60 % »)"
    )
    nb = sorted(x["n_proches"] for x in alertes_props if x["n_proches"])
    if nb:
        dire(
            f"  voisins au-dessus du seuil quand il y a alerte : médiane {nb[len(nb) // 2]}, max {nb[-1]}"
        )

    (sortie / "j1_paires.json").write_text(json.dumps(lignes_paires, ensure_ascii=False, indent=1))
    (sortie / "j1_courbe.json").write_text(json.dumps(courbe, ensure_ascii=False, indent=1))
    (sortie / "j1_validation_croisee.json").write_text(
        json.dumps(cv_json, ensure_ascii=False, indent=1)
    )
    (sortie / "j1_alertes.json").write_text(
        json.dumps(
            {"au_moment": detail_moment, "propositions": alertes_props},
            ensure_ascii=False,
            indent=1,
        )
    )
    return {"tp": tp, "n_pos": len(P), "fp": fp, "n_neg": len(N), "auc": auc, "index": index}


# ---------------------------------------------------------------------------
# Partie 2 : usage des faits, faits neufs par aide
# ---------------------------------------------------------------------------


def faits_cites(aide: dict) -> dict[str, set[str]]:
    """Faits cités par une aide brute, par voie (même logique que comptes.py du bilan)."""
    voies: dict[str, set[str]] = defaultdict(set)
    ai = aide.get("applies_if")
    if isinstance(ai, dict) and isinstance(ai.get("fact"), str):
        voies[ai["fact"]].add("perimetre_aide")
    for c in aide.get("conditions") or []:
        if not isinstance(c, dict):
            continue
        if isinstance(c.get("fact"), str):
            kind = c.get("kind", "untyped")
            effect = c.get("effect") or ("info" if kind in ("info", "discretionary") else "gate")
            voies[c["fact"]].add(f"cond_{kind}_{effect}")
        if isinstance(c.get("levier"), str):
            voies[c["levier"]].add("levier")
        cai = c.get("applies_if")
        if isinstance(cai, dict) and isinstance(cai.get("fact"), str):
            voies[cai["fact"]].add("applies_if_cond")
    return voies


def usage_au_commit(commit: str) -> tuple[dict[str, set[str]], dict[str, set[str]], set[str], int]:
    yamls, _ = slugs_aides(commit)
    par_fait: dict[str, set[str]] = defaultdict(set)
    par_fait_gate: dict[str, set[str]] = defaultdict(set)
    for slug in yamls:
        texte = BLOBS.lire(f"{commit}:{AIDES}/{slug}.yaml")
        if not texte:
            continue
        try:
            brut = yaml.safe_load(texte) or {}
        except yaml.YAMLError:
            continue
        for fait, voies in faits_cites(brut).items():
            par_fait[fait].add(slug)
            if "cond_user_fact_gate" in voies:
                par_fait_gate[fait].add(slug)
    ontologie = cles(commit, FACTS) | cles(commit, PENDING)
    return par_fait, par_fait_gate, ontologie, len(yamls)


def tranche(n: int) -> str:
    if n <= 2:
        return str(n)
    if n <= 5:
        return "3-5"
    if n <= 10:
        return "6-10"
    if n <= 50:
        return "11-50"
    return ">50"


def partie_usage(hist: Histoire, sortie: Path) -> dict:
    dire("")
    dire("=" * 78)
    dire("PARTIE 2. Usage des faits et faits neufs par aide")
    dire("=" * 78)
    head = git("rev-parse", "--short", "HEAD").strip()
    resultats: dict[str, Any] = {}
    for commit, nom in (
        ("HEAD", f"HEAD {head}"),
        ("836e21cb", "836e21cb (2026-09-18, avant le balayage)"),
        ("84bdd821", "84bdd821 (2026-09-22, balayage du 18 après tri)"),
        ("1d94a758", "1d94a758 (2026-09-30, balayage du 29 après tri)"),
    ):
        par_fait, par_gate, onto, n_aides = usage_au_commit(commit)
        dist = Counter(tranche(len(par_fait.get(k, ()))) for k in onto)
        dist_g = Counter(tranche(len(par_gate.get(k, ()))) for k in onto)
        un = dist["1"]
        dire("")
        dire(f"{nom} : {n_aides} aides .yaml, {len(onto)} faits (facts.yaml + facts_pending.yaml)")
        dire(
            "  aides citant le fait (voies : fact de condition, applies_if d'aide et de condition, levier) : "
            + ", ".join(
                f"{t}: {dist.get(t, 0)}" for t in ["0", "1", "2", "3-5", "6-10", "11-50", ">50"]
            )
        )
        dire(f"  cités par une seule aide : {taux(un, len(onto))}")
        cites = len(onto) - dist["0"]
        dire(f"  cités par une seule aide, parmi les faits cités : {taux(un, cites)}")
        dire(
            "  en ne comptant que les gates user_fact : "
            + ", ".join(
                f"{t}: {dist_g.get(t, 0)}" for t in ["0", "1", "2", "3-5", "6-10", "11-50", ">50"]
            )
        )
        inconnus = sorted(set(par_fait) - onto)
        if inconnus:
            dire(
                f"  cités mais absents de l'ontologie : {len(inconnus)} ({', '.join(inconnus[:5])}…)"
            )
        if commit == "HEAD":
            seuls = cles("HEAD", FACTS)
            un_f = sum(1 for k in seuls if len(par_fait.get(k, ())) == 1)
            dire(
                f"  facts.yaml seul ({len(seuls)} faits) : cités par une seule aide {taux(un_f, len(seuls))}"
            )
        resultats[commit] = {
            "n_aides": n_aides,
            "n_faits": len(onto),
            "distribution": dict(dist),
            "distribution_gates": dict(dist_g),
            "un_seul": taux_json(un, len(onto)),
            "un_seul_parmi_cites": taux_json(un, cites),
            "par_fait": {k: sorted(v) for k, v in par_fait.items()} if commit == "HEAD" else None,
        }

    # Faits neufs par aide : trois méthodes
    dire("")
    dire("Faits neufs par aide ingérée, trois méthodes d'attribution :")
    dire(
        "  (a) git : un fait appartient au commit où sa clé apparaît pour la première fois dans "
        "facts.yaml ou facts_pending.yaml (toute l'histoire), une aide au commit où son .yaml "
        "apparaît ; le balayage est le commit qui en porte les résultats."
    )
    commits_aides = commits_chrono(FACTS, PENDING, AIDES)
    premiere_aide: dict[str, str] = {}
    neufs_faits: Counter = Counter()
    neufs_aides: Counter = Counter()
    neufs_echec: Counter = Counter()
    premiere_echec: dict[str, str] = {}
    for h, _t, _d in commits_aides:
        y, e = slugs_aides(h)
        for s in y:
            if s not in premiere_aide:
                premiere_aide[s] = h
                neufs_aides[h] += 1
        for s in e:
            if s not in premiere_echec and s not in premiere_aide:
                premiere_echec[s] = h
                neufs_echec[h] += 1
    for _k, (h, _t, _d) in hist.premiere.items():
        neufs_faits[h] += 1
    fenetres = {
        "2026-09-18": ["84bdd821"],
        "2026-09-29": ["1d94a758"],
        "2026-10-04": ["fdde0102", "6d6faf13"],
    }
    par_balayage: dict[str, Any] = {}
    complets = {h[:8]: h for h, _t, _d in commits_aides}
    for nom, liste in fenetres.items():
        hs = [complets[c] for c in liste]
        f = sum(neufs_faits[h] for h in hs)
        a = sum(neufs_aides[h] for h in hs)
        e = sum(neufs_echec[h] for h in hs)
        ratio = f / a if a else float("nan")
        dire(
            f"    balayage {nom} -> {', '.join(liste)} : {f} faits neufs, {a} aides neuves "
            f"(+ {e} .yaml.echec neufs) = {ratio:.2f} fait par aide gardée"
        )
        par_balayage[nom] = {
            "git": {"commits": liste, "faits": f, "aides": a, "echecs": e, "ratio": ratio}
        }

    dire(
        "  (b) bilan imprimé par l'orchestrateur en fin de run (orchestrateur.py:482, différence "
        "entre facts_pending.yaml du début et de la fin, worker.py:115-123) :"
    )
    log29 = (LOGS / "balayage/2026-09-29-0053-ingestion.log").read_text(errors="replace")
    m = re.search(r"^(\d+) fait\(s\) proposé\(s\) dans", log29, re.M)
    n_ok = len(re.findall(r"^\S+\s+ok\s+\d+", log29, re.M))
    n_ech = len(re.findall(r"^\S+\s+ÉCHEC\s+\d+", log29, re.M))
    if m:
        f29 = int(m.group(1))
        dire(
            f"    2026-09-29 : {f29} faits proposés, {n_ok} aides ok, {n_ech} échecs "
            f"(balayage/2026-09-29-0053-ingestion.log) = {f29 / n_ok:.2f} par aide ok, "
            f"{f29 / (n_ok + n_ech):.2f} par aide tentée"
        )
        par_balayage["2026-09-29"]["bilan_run"] = {"faits": f29, "ok": n_ok, "echecs": n_ech}
    log18 = (LOGS / "balayage/2026-09-18-0152-ingestion.log").read_text(errors="replace")
    dire(
        "    2026-09-18 : le journal balayage/2026-09-18-0152-ingestion.log s'arrête sans bilan "
        f"({len(log18.splitlines())} lignes, aucune ligne « fait(s) proposé(s) ») ; 563 faits / 643 "
        "aides n'a qu'une source écrite : TYPING.md:83 et la docstring de faits.py:69-70."
    )
    dire(
        "  (c) journaux d'ingestion par aide (événements « [*] fait proposé », sorties « ajouté », "
        "écritures du bug d'enveloppe), fenêtre de dates de l'en-tête du bloc :"
    )
    blocs = journaux_ingestion()
    for nom, (debut, fin) in {
        "2026-09-18": ("2026-09-18", "2026-09-21"),
        "2026-09-29": ("2026-09-28T20", "2026-09-30T12"),
        "2026-10-04": ("2026-10-04", "2026-10-06"),
    }.items():
        bs = [b for b in blocs if debut <= b["date"] < fin]
        ok = [b for b in bs if b["ok"]]
        faits = set()
        faits_ok = set()
        for b in bs:
            faits |= b["faits"]
            if b["ok"]:
                faits_ok |= b["faits"]
        dire(
            f"    {nom} : {len(bs)} blocs, {len(ok)} ok, {len(faits)} faits distincts proposés "
            f"({len(faits_ok)} dans des blocs ok) = {len(faits) / max(1, len(ok)):.2f} par aide ok"
        )
        par_balayage[nom]["journaux"] = {
            "blocs": len(bs),
            "ok": len(ok),
            "faits": len(faits),
            "faits_blocs_ok": len(faits_ok),
        }
    recents = sorted(s for s, h in premiere_aide.items() if h[:8] in fenetres["2026-10-04"])
    (sortie / "usage.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1))
    (sortie / "faits_par_balayage.json").write_text(
        json.dumps(par_balayage, ensure_ascii=False, indent=1)
    )
    return {"usage": resultats, "balayages": par_balayage, "recents": recents}


def journaux_ingestion() -> list[dict]:
    entete = re.compile(r"^={20,}\n(\S+) — (\d{4}-\S+)(.*)\n={20,}$", re.M)
    out = []
    for dossier in (LOGS, LOGS / "depuis-prospection-worktree", LOGS / "depuis-veille-hebdo"):
        for f in sorted(dossier.glob("ingest-*.log")):
            texte = f.read_text(errors="replace")
            ms = list(entete.finditer(texte))
            for i, m in enumerate(ms):
                corps = texte[m.end() : ms[i + 1].start() if i + 1 < len(ms) else len(texte)]
                proposes = set(re.findall(r"^\[\*\] fait proposé : ([a-z0-9_]+)", corps, re.M))
                ajoutes = set(re.findall(r"^\[sortie\] Fait « ([a-z0-9_]+) » ajouté", corps, re.M))
                retires = set(re.findall(r"^\[\*\] fait retiré : ([a-z0-9_]+)", corps, re.M))
                enveloppe = set()
                for mm in re.finditer(
                    r'\[appel\] proposer_fait\(\{"fact_id": "([a-z0-9_]+)".*?\n\[sortie\] ERREUR : '
                    r"ValidationError(.*?)(?=\n\[|\n---|\Z)",
                    corps,
                    re.S,
                ):
                    if re.search(
                        r"^" + re.escape(mm.group(1)) + r"\n  Extra inputs", mm.group(2), re.M
                    ):
                        enveloppe.add(mm.group(1))
                out.append(
                    {
                        "fichier": f.name,
                        "slug": m.group(1),
                        "date": m.group(2)[:19],
                        "ok": "[*] OK —" in corps,
                        "faits": (proposes | ajoutes | enveloppe) - retires,
                    }
                )
    return out


# ---------------------------------------------------------------------------
# Partie 3 : devenir des faits passés par facts_pending.yaml
# ---------------------------------------------------------------------------


def tables_fusion() -> tuple[dict, dict, dict]:
    garder, seche, retype = {}, {}, {}
    for f in sorted(FUSIONS.glob("*.yaml")):
        brut = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for x in brut.get("fusions") or []:
            if x.get("garder"):
                garder[x["retirer"]] = (x["garder"], f.name)
            else:
                seche[x["retirer"]] = (x.get("motif") or "", f.name)
        for x in brut.get("retypages") or []:
            retype[x["fait"]] = (
                x.get("kind") or "",
                x.get("source") or "",
                f.name,
                x.get("motif") or "",
            )
    return garder, seche, retype


def partie_devenir(hist: Histoire, sortie: Path) -> dict:
    dire("")
    dire("=" * 78)
    dire("PARTIE 3. Devenir des faits passés par facts_pending.yaml")
    dire("=" * 78)
    facts_txt = (BACKEND / "data/facts.yaml").read_text(encoding="utf-8")
    fleches: dict[str, str] = {}
    for m in re.finditer(r"^#\s+([a-z0-9_]+(?:,\s*[a-z0-9_]+)*),?\s*→\s*(.+)$", facts_txt, re.M):
        for k in [s.strip() for s in m.group(1).split(",") if s.strip()]:
            fleches.setdefault(k, m.group(2).strip())
    garder, seche, retype = tables_fusion()
    facts_now = cles("HEAD", FACTS)
    pending_now = cles("HEAD", PENDING)
    destin = Counter()
    detail = {}
    for k, (_h, t, d) in hist.premiere_pending.items():
        if k in pending_now:
            dd = "encore_en_attente"
        elif k in facts_now:
            dd = "approuve_present"
        elif k in fleches or k in garder:
            dd = "fusionne"
        elif k in retype:
            dd = "retype_retire"
        elif k in seche:
            dd = "suppression_seche"
        elif k in hist.deja_approuve:
            dd = "approuve_puis_retire_sans_trace"
        else:
            dd = "disparu_sans_trace"
        cible = None
        refait_existant = None
        if dd == "fusionne":
            vers = garder[k][0] if k in garder else fleches[k]
            cible = vers.split()[0].strip("`,(")
            if cible in hist.premiere:
                tc = hist.premiere[cible][1]
                refait_existant = "avant" if tc < t else ("meme_commit" if tc == t else "apres")
            else:
                refait_existant = "jamais_vue"
        detail[k] = {
            "destin": dd,
            "premiere_pending": d,
            "cible": cible,
            "cible_anterieure": refait_existant,
            "table_retypage": retype[k][2] if k in retype else None,
        }
        destin[dd] += 1
    n = len(detail)
    avant_aout = sum(1 for v in detail.values() if v["premiere_pending"] < "2026-08-01")
    dire(
        f"{n} clés passées par facts_pending.yaml (toute l'histoire git de HEAD), dont {avant_aout} "
        "apparues avant le 2026-08-01"
    )
    for dd, c in destin.most_common():
        dire(f"  {dd:<34} {taux(c, n)}")
    ref = json.loads((ENTREES / "destin_pending.json").read_text())
    dire(
        f"  comparaison destin_pending.json du bilan : {dict(Counter(v['destin'] for v in ref.values()))}"
    )
    fus = [v for v in detail.values() if v["destin"] == "fusionne"]
    ant = sum(1 for v in fus if v["cible_anterieure"] == "avant")
    meme = sum(1 for v in fus if v["cible_anterieure"] == "meme_commit")
    dire(
        f"Fusionnés : {len(fus)} ; position de la cible : {dict(Counter(v['cible_anterieure'] for v in fus))}"
    )
    dire(
        f"  cible apparue dans un commit antérieur (il refaisait un fait existant) : {taux(ant, len(fus))} ; "
        f"au même commit (indécidable à cette granularité) : {taux(meme, len(fus))}"
    )
    dire(
        f"  part des {n} faits qui refaisaient un fait existant : {taux(ant, n)} (borne basse), {taux(ant + meme, n)} (borne haute)"
    )
    dire(
        f"  part des {n} faits fusionnés dans un autre (cible antérieure ou non) : {taux(len(fus), n)}"
    )
    tables = Counter(v["table_retypage"] for v in detail.values() if v["destin"] == "retype_retire")
    dire(f"  retypés puis retirés, par table : {dict(tables)}")
    survivants = destin["approuve_present"] + destin["encore_en_attente"]
    dire(f"  encore dans l'ontologie à HEAD : {taux(survivants, n)}")
    (sortie / "devenir_pending.json").write_text(json.dumps(detail, ensure_ascii=False, indent=1))
    return {"n": n, "destin": dict(destin), "fusionnes": len(fus), "refait_existant": ant}


# ---------------------------------------------------------------------------
# Partie 4 : J2, critère / démarche / promesse
# ---------------------------------------------------------------------------

SECTIONS_TRI = {
    "## Démarches : sortent du questionnaire": "demarche",
    "## Promesses : sortent du questionnaire": "promesse",
    "## À trancher": "a_trancher",
    "## Critères qui portent un levier à retirer": "critere",
    "## Critères : restent des questions": "critere",
}


def lire_tri() -> tuple[dict[str, str], dict[str, int], dict[str, str]]:
    """Verdict des agents (par section du rapport), nombre de gates, et classe arbitrée par Félix."""
    verdict: dict[str, str] = {}
    gates: dict[str, int] = {}
    section = None
    texte = RAPPORT_TRI.read_text(encoding="utf-8")
    for li in texte.splitlines():
        if li.startswith("## "):
            section = SECTIONS_TRI.get(li.strip())
            continue
        m = re.match(r"^\| `([a-z0-9_]+)` \| (\d+) \|", li)
        if m and section:
            verdict[m.group(1)] = section
            gates[m.group(1)] = int(m.group(2))
    arbitre: dict[str, str] = {}
    fin = texte.split("## Arbitrages du 2026-09-23", 1)[1]
    for motif, classe in (
        (r"\*\*Gardés en question \(critères\)\*\* :(.*)", "critere"),
        (r"\*\*Sortis du questionnaire en démarche\*\* :(.*)", "demarche"),
        (r"\*\*Sortis du questionnaire en promesse\*\* :(.*)", "promesse"),
        (r"- `visite_interieure_exterieure_possible` :(.*)", "demarche"),
        (r"- \*\*Promesses\*\* :(.*?)\(lot 5f", "promesse"),
    ):
        m = re.search(motif, fin)
        if m:
            for k in re.findall(r"`([a-z0-9_]+)`", m.group(1)):
                arbitre[k] = classe
    arbitre["visite_interieure_exterieure_possible"] = "demarche"
    # Troisième tour (« plus aucune question sur l'obtention d'un label ») : décrit en prose,
    # les faits sont ceux de la table lot-5g, appliqués en manual_check + info.
    for x in (yaml.safe_load((FUSIONS / "lot-5g-labels.yaml").read_text()) or {}).get(
        "retypages"
    ) or []:
        arbitre.setdefault(x["fait"], "demarche")
    return verdict, gates, arbitre


def classe_retypage(fait: str, kind: str) -> str:
    """Démarche ou promesse selon retyper_faits.py : `kind` explicite, sinon le préfixe."""
    if kind == "info" or (not kind and fait.startswith("s_engage")):
        return "promesse"
    return "demarche"


def partie_j2(hist: Histoire, sortie: Path, index: dict[str, dict]) -> dict:
    dire("")
    dire("=" * 78)
    dire("PARTIE 4. J2 : critère, démarche ou promesse")
    dire("=" * 78)
    verdict, gates, arbitre = lire_tri()
    dire(f"Rapport {RAPPORT_TRI.relative_to(REPO)} : {len(verdict)} faits classés par les agents")
    c_agents = Counter(verdict.values())
    dire(f"  verdicts des agents : {dict(c_agents)} ; gates {sum(gates.values())}")
    dire(f"  faits nommés dans les arbitrages de Félix (fin du rapport) : {len(arbitre)}")
    lot5: dict[str, tuple[str, str]] = {}
    for f in sorted(FUSIONS.glob("lot-5*.yaml")):
        for x in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("retypages") or []:
            lot5[x["fait"]] = (classe_retypage(x["fait"], x.get("kind") or ""), f.name)
    dire(
        f"  retypages des tables lot-5*.yaml : {len(lot5)} faits, {dict(Counter(v[0] for v in lot5.values()))}"
    )
    hors_tri = sorted(set(lot5) - set(verdict))
    dire(f"  faits retypés en lot-5* absents du rapport : {len(hors_tri)} {hors_tri[:8]}")

    # Classe retenue : lot-5* (démarche / promesse) ; sinon critère si le fait est resté
    # une question (présent après le tri) ou a été fusionné dans un fait qui l'est.
    garder, seche, retype = tables_fusion()
    facts_txt = (BACKEND / "data/facts.yaml").read_text(encoding="utf-8")
    fleches = {}
    for m in re.finditer(r"^#\s+([a-z0-9_]+(?:,\s*[a-z0-9_]+)*),?\s*→\s*(.+)$", facts_txt, re.M):
        for k in [s.strip() for s in m.group(1).split(",") if s.strip()]:
            fleches.setdefault(k, m.group(2).strip())
    apres_tri = "c6d1e85f"
    complet = git("rev-parse", apres_tri).strip()
    presents_apres = cles(complet, FACTS) | cles(complet, PENDING)
    fusions_tri = {
        "demarche_transition_ecologique": "projet_dimension_environnementale",
        "porteur_est_proprietaire": "titre_occupation_porteur",
        "porteur_titre_maitrise_ouvrage": "titre_occupation_porteur",
    }
    # Deux lectures de la vérité terrain :
    #  - `appliquee` : ce que les données montrent (lot-5* pour démarche / promesse ; sinon
    #    critère si le fait existe encore au commit qui clôt le tri, ou a été fusionné dans
    #    un fait qui reste une question ; sinon retiré sans table, en pratique orphelin) ;
    #  - `retenue` : la décision écrite, c'est-à-dire l'arbitrage de Félix quand il nomme le
    #    fait, sinon le verdict des agents (« Les verdicts des agents sont validés, sauf là où
    #    l'utilisateur a tranché autrement », fin du rapport), sinon la classe appliquée.
    classes = ["critere", "demarche", "promesse"]
    appliquee: dict[str, str] = {}
    for k in verdict:
        if k in lot5:
            appliquee[k] = lot5[k][0]
        elif k in presents_apres or k in fusions_tri or k in garder or k in fleches:
            appliquee[k] = "critere"
        elif k in retype:
            appliquee[k] = f"retire ({retype[k][2]})"
        else:
            appliquee[k] = "retire_sans_table"
    retenue: dict[str, str] = {}
    for k in verdict:
        if k in arbitre:
            retenue[k] = arbitre[k]
        elif verdict[k] in classes:
            retenue[k] = verdict[k]
        elif appliquee[k] in classes:
            retenue[k] = appliquee[k]
        else:
            retenue[k] = "indecis"
    dire(
        f"  classe appliquée (lot-5*, puis présence au commit {apres_tri}) : {dict(Counter(appliquee.values()))}"
    )
    dire(
        f"  classe retenue (arbitrage, sinon verdict validé des agents) : {dict(Counter(retenue.values()))}"
    )
    incoherents = {
        k: (retenue[k], appliquee[k])
        for k in verdict
        if appliquee[k] in classes and retenue[k] != appliquee[k]
    }
    dire(f"  décision écrite contredite par la table appliquée : {len(incoherents)} {incoherents}")
    orphelins_critere = [k for k in verdict if appliquee[k] == "retire_sans_table"]
    dire(
        f"  retirés au commit {apres_tri} sans table (orphelins d'aides écartées) : {len(orphelins_critere)}, "
        f"verdicts {dict(Counter(verdict[k] for k in orphelins_critere))}"
    )

    # Arbitrages et corrections de Félix
    corrections = {
        k: (verdict[k], c) for k, c in arbitre.items() if k in verdict and verdict[k] != c
    }
    tranches = {k: c for k, c in arbitre.items() if verdict.get(k) == "a_trancher"}
    confirms = {k for k, c in arbitre.items() if verdict.get(k) == c}
    dire(
        f"  arbitrages nommés : {len(arbitre)} ; dont « à trancher » résolus {len(tranches)}, "
        f"verdicts d'agent renversés {len([k for k in corrections if verdict[k] != 'a_trancher'])}, "
        f"confirmés {len(confirms)}"
    )
    renverses = {k: v for k, v in corrections.items() if v[0] != "a_trancher"}
    dire(f"    renversés : {renverses}")
    a_trancher_restants = [k for k, v in verdict.items() if v == "a_trancher" and k not in arbitre]
    dire(
        f"  « à trancher » non nommés dans les arbitrages : {len(a_trancher_restants)} ; "
        f"leur classe appliquée : {dict(Counter(appliquee[k] for k in a_trancher_restants))}"
    )

    # Matrice agents -> appliquée
    dire("")
    dire("Matrice verdict des agents (lignes) contre classe appliquée (colonnes) :")
    mat = Counter((verdict[k], appliquee[k]) for k in verdict)
    cols = sorted({c for _a, c in mat})
    dire("  " + " " * 12 + "".join(f"{c[:16]:>18}" for c in cols))
    for a in ["critere", "demarche", "promesse", "a_trancher"]:
        dire(f"  {a:<12}" + "".join(f"{mat.get((a, c), 0):>18}" for c in cols))
    tranches_nets = [k for k in verdict if verdict[k] in classes and appliquee[k] in classes]
    accord = sum(1 for k in tranches_nets if verdict[k] == appliquee[k])
    dire(
        f"  accord agents / appliquée, hors « à trancher » et retirés : {taux(accord, len(tranches_nets))}"
    )

    # Le décideur de l'ingestion : tous ces faits portaient un gate user_fact = critère
    evalues = [k for k in verdict if retenue[k] in classes]
    dire("")
    dire(
        "Décideur actuel (typage produit par l'ingestion) : les 457 faits du rapport sont, par "
        "construction du rapport, des faits GATÉS (user_fact + gate), donc classés critère."
    )
    dire(
        "Matrice classe retenue (lignes) contre typage de l'ingestion (colonne unique « critère ») :"
    )
    par_classe = {}
    for c in classes:
        n_c = sum(1 for k in evalues if retenue[k] == c)
        k_ok = n_c if c == "critere" else 0
        par_classe[c] = taux_json(k_ok, n_c)
        dire(
            f"  {c:<10} n = {n_c:3d} ; typés critère par l'ingestion {n_c:3d} ; rappel de la classe {taux(k_ok, n_c)}"
        )
    err = sum(1 for k in evalues if retenue[k] != "critere")
    dire(f"  erreur globale de l'ingestion (question posée à tort) : {taux(err, len(evalues))}")
    ev_app = [k for k in verdict if appliquee[k] in classes]
    err_app = sum(1 for k in ev_app if appliquee[k] != "critere")
    dire(f"  même mesure sur la classe appliquée : {taux(err_app, len(ev_app))}")
    g_err = sum(gates[k] for k in evalues if retenue[k] != "critere")
    g_tot = sum(gates[k] for k in evalues)
    dire(f"  en gates : {g_err}/{g_tot} = {100 * g_err / g_tot:.1f} % des gates de ces faits")

    # La règle de code à la proposition : regex de promesse (faits.py:273-290)
    dire("")
    dire(
        "Règle de code à la proposition (faits.py::promesse, s_engage_* ou « acceptez / vous engagez ») :"
    )
    q_par = {}
    for k in evalues:
        q = index.get(k, {}).get("question")
        q_par[k] = q
    sans_q = [k for k in evalues if not q_par[k]]

    class _F:
        def __init__(self, q: str) -> None:
            self.question = q

    regle = {k: promesse(k, _F(q_par[k] or "")) for k in evalues if q_par[k]}
    vp = sum(1 for k, v in regle.items() if v and retenue[k] == "promesse")
    fp_ = sum(1 for k, v in regle.items() if v and retenue[k] != "promesse")
    n_prom = sum(1 for k in regle if retenue[k] == "promesse")
    dire(f"  questions trouvées dans l'index : {len(regle)} ({len(sans_q)} sans question)")
    dire(
        f"  rappel des promesses : {taux(vp, n_prom)} ; faux positifs : {fp_} faits non-promesses marqués"
    )

    # Lot 4 (2026-09-22) : la famille s_engage, décision humaine antérieure
    lot4 = (yaml.safe_load((FUSIONS / "lot-4-engagements-approuves.yaml").read_text()) or {}).get(
        "retypages"
    ) or []
    dire(
        f"  lot-4 (2026-09-22, famille s_engage retypée en info) : {len(lot4)} faits, hors du rapport du 23"
    )

    # transitions.json : niveau condition
    trans = json.loads((ENTREES / "transitions.json").read_text())
    dire("")
    dire(
        f"transitions.json : {len(trans)} changements relevés dans git (kind/effect, ou fait à kind constant)"
    )
    tk = Counter()
    for t in trans:
        a, b = t["avant"], t["apres"]
        if (a["kind"], a.get("effect")) != (b["kind"], b.get("effect")):
            tk[(f"{a['kind']}+{a.get('effect')}", f"{b['kind']}+{b.get('effect')}")] += 1
        else:
            tk[(f"{a['kind']}+{a.get('effect')}", "même kind, fait changé")] += 1
    for (a, b), n in tk.most_common(14):
        dire(f"  {a:<26} -> {b:<26} {n}")
    lot5_conds = [
        t
        for t in trans
        if t["avant"]["kind"] == "user_fact"
        and t["avant"].get("fact") in lot5
        and t["apres"]["kind"] in ("manual_check", "info")
    ]
    par_table = Counter(lot5[t["avant"]["fact"]][1] for t in lot5_conds)
    dire(f"  par table : {dict(par_table)}")
    dire(
        f"  conditions user_fact retypées dont le fait est en lot-5* : {len(lot5_conds)} "
        f"({dict(Counter((t['commit'], t['apres']['kind'], t['apres'].get('effect')) for t in lot5_conds))}) ; "
        "le rapport annonce 340"
    )

    # Le décideur depuis la doctrine du 2026-09-23 : faits proposés après, devenir à la revue
    dire("")
    dire(
        "Depuis la doctrine critère / démarche (après le 2026-09-24), devenir des faits proposés :"
    )
    garder, seche, retype = tables_fusion()
    facts_now = cles("HEAD", FACTS)
    post = [k for k, (_h, _t, d) in hist.premiere_pending.items() if d >= "2026-09-24"]
    motifs_mc = 0
    for k in post:
        motif = (seche.get(k) or ("", ""))[0]
        if "manual_check" in motif or "Engagement" in motif:
            motifs_mc += 1
    dire(
        f"  {len(post)} faits apparus dans facts_pending.yaml après le 2026-09-24 ; approuvés présents "
        f"{sum(1 for k in post if k in facts_now)} ; sortis vers manual_check ou engagement (motif de "
        f"table) {motifs_mc}"
    )
    (sortie / "j2.json").write_text(
        json.dumps(
            {
                "verdict_agents": verdict,
                "gates": gates,
                "arbitrages_felix": arbitre,
                "classe_retenue": retenue,
                "classe_appliquee": appliquee,
                "corrections": corrections,
                "matrice_agents_retenue": {f"{a}->{c}": n for (a, c), n in mat.items()},
                "ingestion_par_classe": par_classe,
                "regle_promesse": {"vp": vp, "fp": fp_, "n_promesses": n_prom},
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return {"verdict": verdict, "retenue": retenue, "gates": gates, "evalues": evalues}


# ---------------------------------------------------------------------------
# Partie 5 : coût en questions d'un fait
# ---------------------------------------------------------------------------


def partie_cout(sortie: Path, usage_head: dict, slugs_recents: list[str]) -> dict:
    dire("")
    dire("=" * 78)
    dire("PARTIE 5. Coût en questions d'un fait (moteur, 16 profils, rien n'est écrit)")
    dire("=" * 78)
    t0 = time.perf_counter()
    from aides_schema import load_all_aides, load_facts, load_pending_facts
    from profils_questionnaire import PROFILS, delta_tronc, mesurer, parcours_simule

    aides = load_all_aides()
    facts = {**load_facts(), **load_pending_facts()}
    t_charge = time.perf_counter() - t0
    dire(f"chargement : {len(aides)} aides, {len(facts)} faits, {t_charge:.2f} s")
    t0 = time.perf_counter()
    tronc_par_profil = {}
    propres_par_profil = {}
    parcours_par_profil = {}
    for nom, profil in PROFILS.items():
        m = mesurer(aides, facts, profil)
        tronc_par_profil[nom] = {q["id"] for q in m.tronc}
        propres_par_profil[nom] = {q["id"] for q in m.propres}
    t_mesure = time.perf_counter() - t0
    t0 = time.perf_counter()
    for nom, profil in PROFILS.items():
        parcours_par_profil[nom] = parcours_simule(aides, facts, profil)
    t_parcours = time.perf_counter() - t0
    dire(
        f"16 diagnostics (tronc + propres) : {t_mesure:.2f} s ({1000 * t_mesure / 16:.0f} ms par profil) ; "
        f"16 parcours simulés : {t_parcours:.2f} s"
    )
    par_fait = usage_head["par_fait"] or {}
    cout = {}
    for k in facts:
        n_aides = len(par_fait.get(k, ()))
        cout[k] = {
            "aides": n_aides,
            "profils_tronc": sum(1 for p in PROFILS if k in tronc_par_profil[p]),
            "profils_propre": sum(1 for p in PROFILS if k in propres_par_profil[p]),
            "profils_parcours": sum(1 for p in PROFILS if k in parcours_par_profil[p]),
        }
    dire("")
    dire("Coût actuel de chaque fait, selon le nombre d'aides qui le citent :")
    for groupe, filtre in (
        ("1 aide", lambda n: n == 1),
        ("2 aides", lambda n: n == 2),
        ("3-10 aides", lambda n: 3 <= n <= 10),
        (">10 aides", lambda n: n > 10),
    ):
        ks = [k for k, v in cout.items() if filtre(v["aides"])]
        if not ks:
            continue
        en_tronc = sum(1 for k in ks if cout[k]["profils_tronc"])
        en_parcours = sum(1 for k in ks if cout[k]["profils_parcours"])
        moy_tronc = sum(cout[k]["profils_tronc"] for k in ks) / len(ks)
        en_propre = sum(1 for k in ks if cout[k]["profils_propre"])
        dire(
            f"  {groupe:<11} {len(ks):4d} faits ; au tronc d'au moins un profil {taux(en_tronc, len(ks))} ; "
            f"au parcours simulé d'au moins un profil {taux(en_parcours, len(ks))} ; "
            f"profils où il est au tronc, moyenne {moy_tronc:.2f} ; question propre (carte d'aide) "
            f"d'au moins un profil {taux(en_propre, len(ks))}"
        )
    tronc_tot = sum(len(v) for v in tronc_par_profil.values())
    dire(f"  questions de tronc, somme sur 16 profils : {tronc_tot}")

    # Le calcul « au moment où le fait est proposé » : delta_tronc d'une aide, comme
    # worker.cout_en_questions (worker.py:182-243), sur les aides les plus récentes.
    recentes = sorted(s for s in slugs_recents if s in aides)
    durees = []
    entrees: dict[str, int] = {}
    for slug in recentes:
        t0 = time.perf_counter()
        avant = {s: a for s, a in aides.items() if s != slug}
        delta = delta_tronc(avant, aides, facts)
        durees.append(time.perf_counter() - t0)
        entrees[slug] = max(len(v[2]) for v in delta.values())
    if durees:
        durees.sort()
        dire("")
        dire(
            f"delta_tronc (worker.cout_en_questions) sur les {len(durees)} aides du balayage du 2026-10-04 encore au catalogue : "
            f"médiane {durees[len(durees) // 2]:.2f} s, max {durees[-1]:.2f} s par aide (32 diagnostics), "
            f"hors chargement du catalogue ({t_charge:.2f} s)"
        )
        dire(
            f"  questions entrantes au pire profil : {dict(Counter(entrees.values()))} (nombre de questions : nombre d'aides)"
        )
    resultat = {
        "temps": {
            "chargement_s": t_charge,
            "mesurer_16_s": t_mesure,
            "parcours_16_s": t_parcours,
            "delta_tronc_par_aide_s": durees,
        },
        "par_fait": cout,
        "entrees_pire_profil": entrees,
    }
    (sortie / "cout_questions.json").write_text(json.dumps(resultat, ensure_ascii=False, indent=1))
    return resultat


# ---------------------------------------------------------------------------
# Partie 6 : estimation d'une mesure par Jev (aucun appel)
# ---------------------------------------------------------------------------

CAR_PAR_JETON = 3.6  # estimateur de la cartographie (ingestion.md:300)
PRIX_JEV = 0.042 / 1e6  # $ par jeton d'entrée, sortie gratuite (docs/jev.md)


def definition_courte(k: str, index: dict[str, dict]) -> str:
    f = index.get(k, {})
    opts = f" options={f.get('options')}" if f.get("options") else ""
    aide = f" aide : {f.get('help')}" if f.get("help") else ""
    return f"{k} [{f.get('type')}, {f.get('scope')}]{opts} « {f.get('question')} »{aide}"


def partie_jev(sortie: Path, index: dict[str, dict], j2: dict) -> dict:
    dire("")
    dire("=" * 78)
    dire("PARTIE 6. Ce que coûterait la mesure de J1 et J2 par Jev (estimation, aucun appel)")
    dire("=" * 78)
    paires = json.loads((sortie / "j1_paires.json").read_text())
    consigne_j1 = (
        "Deux faits sont le même fait dès qu'un propriétaire y répondrait toujours pareil. Un seuil "
        "différent n'y change rien ; deux territoires, deux listes officielles, deux scopes ou deux "
        "polarités opposées font deux faits. Lequel des faits candidats pose la même question que le "
        "fait proposé, ou aucun ?"
    )
    k = 6
    etats_j1 = []
    noms = sorted(index)
    for x in paires:
        a, b = x["a"], x["b"]
        voisins = sorted(
            noms,
            key=lambda o: -SequenceMatcher(None, a.replace("_", " "), o.replace("_", " ")).ratio(),
        )[: k - 1]
        cand = [b] + [v for v in voisins if v not in (a, b)][: k - 1]
        etat = (
            consigne_j1
            + "\nProposé : "
            + definition_courte(a, index)
            + "\n"
            + "\n".join(definition_courte(c, index) for c in cand)
        )
        etats_j1.append(len(etat) / CAR_PAR_JETON)
    tj1 = sum(etats_j1)
    dire(
        f"J1, une question choice par paire étiquetée ({len(paires)} appels, fait proposé + {k} candidats "
        f"dont le vrai, option « aucun ») : {tj1:,.0f} jetons, médiane {sorted(etats_j1)[len(etats_j1) // 2]:,.0f} "
        f"par appel, {tj1 * PRIX_JEV:.4f} $"
    )
    noul = [
        (
            len(consigne_j1)
            + len(definition_courte(x["a"], index))
            + len(definition_courte(x["b"], index))
        )
        / CAR_PAR_JETON
        for x in paires
    ]
    dire(
        f"J1, variante noul par paire (« même fait ? ») : {sum(noul):,.0f} jetons, {sum(noul) * PRIX_JEV:.4f} $"
    )
    consigne_j2 = (
        "Critère : ce que le propriétaire a ou n'a pas et ne peut pas changer. Démarche : ce qu'il peut "
        "rendre vrai avant le dépôt, par une démarche ponctuelle, sans changer de statut, d'usage ni de "
        "projet. Promesse : ce qu'il signe au dossier. Laquelle ? (critère, démarche, promesse, autre)"
    )
    etats_j2 = []
    trans = json.loads((ENTREES / "transitions.json").read_text())
    textes = defaultdict(list)
    for t in trans:
        f = t["avant"].get("fact")
        if f and len(textes[f]) < 3:
            textes[f].append((t["text"] or "")[:400] + " / " + (t["quote"] or "")[:400])
    for f in j2["evalues"]:
        etat = (
            consigne_j2 + "\n" + definition_courte(f, index) + "\n" + "\n".join(textes.get(f, []))
        )
        etats_j2.append(len(etat) / CAR_PAR_JETON)
    tj2 = sum(etats_j2)
    dire(
        f"J2, une question choice par fait ({len(etats_j2)} appels ; définition + 3 conditions au plus) : "
        f"{tj2:,.0f} jetons, médiane {sorted(etats_j2)[len(etats_j2) // 2]:,.0f}, {tj2 * PRIX_JEV:.4f} $"
    )
    n_cond = len(trans)
    dire(
        f"J2 au niveau condition (les {n_cond} changements de transitions.json, ~600 jetons chacun) : "
        f"{n_cond * 600:,} jetons, {n_cond * 600 * PRIX_JEV:.4f} $"
    )
    resultat = {
        "hypotheses": {
            "car_par_jeton": CAR_PAR_JETON,
            "prix_entree_par_jeton": PRIX_JEV,
            "k_candidats": k,
        },
        "j1_choice": {"appels": len(paires), "jetons": tj1, "cout": tj1 * PRIX_JEV},
        "j1_noul": {"appels": len(paires), "jetons": sum(noul), "cout": sum(noul) * PRIX_JEV},
        "j2_fait": {"appels": len(etats_j2), "jetons": tj2, "cout": tj2 * PRIX_JEV},
        "j2_condition": {"appels": n_cond, "jetons": n_cond * 600, "cout": n_cond * 600 * PRIX_JEV},
    }
    (sortie / "jev_estimation.json").write_text(json.dumps(resultat, ensure_ascii=False, indent=1))
    return resultat


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sortie", type=Path, default=SORTIE_DEFAUT)
    parser.add_argument("--sans-moteur", action="store_true")
    args = parser.parse_args()
    sortie: Path = args.sortie
    sortie.mkdir(parents=True, exist_ok=True)
    dire(
        f"HEAD {git('rev-parse', 'HEAD').strip()} ; plafond de faits neufs MAX_FAITS_PAR_AIDE = {MAX_FAITS_PAR_AIDE}"
    )
    hist = Histoire()
    dire(f"Histoire : {len(hist.commits)} commits touchent facts.yaml ou facts_pending.yaml")
    j1 = partie_j1(hist, sortie)
    us = partie_usage(hist, sortie)
    partie_devenir(hist, sortie)
    j2 = partie_j2(hist, sortie, j1["index"])
    if not args.sans_moteur:
        partie_cout(sortie, us["usage"]["HEAD"], us["recents"])
    partie_jev(sortie, j1["index"], j2)
    (sortie / "resume.txt").write_text("\n".join(_lignes) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
