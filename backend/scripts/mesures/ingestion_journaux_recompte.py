"""Recompte indépendant des journaux d'ingestion (relecture adverse de M04).

Lecture seule. N'importe rien du script du mesureur (`ingestion_journaux.py`) :
le découpage des runs, les issues, les coûts et les jointures sont réécrits ici
pour que deux erreurs identiques ne se confirment pas l'une l'autre.

Depuis `backend/` :

    uv run python scripts/mesures/ingestion_journaux_recompte.py

Sorties dans `data/reviews/logs/refonte/2026-10-10-ingestion-journaux-recompte-1/`.
Aucun appel réseau, aucun appel de modèle.
"""

from __future__ import annotations

import csv
import json
import math
import random
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
LOGS = BACKEND / "data" / "reviews" / "logs"
AIDES = BACKEND / "data" / "aides"
FILE = BACKEND / "data" / "prospection" / "file-attente.yaml"
SORTIE = LOGS / "refonte" / "2026-10-10-ingestion-journaux-recompte-1"

SEP = "=" * 78
RE_ENTETE = re.compile(
    r"^(\S+) — (\d{4}-\d\d-\d\dT[\d:]+\+00:00) — ingestion (.+) / vérification (.+)$"
)
RE_TOUR = re.compile(
    r"^--- tour (\d+) — entrée (\d+) \(\+(\d+) cache\) / sortie (\d+) — cumul \$([\d.]+) — (.*)$"
)
RE_OK = re.compile(
    r"^\[\*\] OK — (\d+) tour\(s\), (\d+) appel\(s\)\s+([\d ]+) jetons entrée / ([\d ]+) sortie\s+"
    r"\$(\d+\.\d+)( — coût inconnu)?"
)
RE_DUREE = re.compile(r"durée (\d+) s")
RE_MODELE_ERR = re.compile(r"\[openrouter · ([\w.-]+)\]|\[deepseek · ([\w.-]+)\]")
DEBUT_BLOC = ("[appel]", "[sortie]", "[*]", "[texte]", "[raisonnement]", "--- tour ")

# Heures pleines DeepSeek V4.1 (commentaire de scripts/pipeline/llm.py:121-123) :
# lundi au vendredi, 01:00-04:00 et 06:00-10:00 UTC.


def heure_pleine(t: datetime) -> bool:
    return t.weekday() < 5 and (1 <= t.hour < 4 or 6 <= t.hour < 10)


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    z = 1.959964
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def taux(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {
        "k": k,
        "n": n,
        "p": round(k / n, 4) if n else None,
        "ic95": [round(lo, 4), round(hi, 4)],
    }


def p90(xs: list[float]) -> float:
    # Rang le plus proche (pas d'interpolation), pour ne pas dépendre de la
    # convention du mesureur.
    s = sorted(xs)
    return s[max(0, math.ceil(0.9 * len(s)) - 1)]


def stats(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "mediane": statistics.median(xs),
        "moyenne": sum(xs) / len(xs),
        "p90_rang": p90(xs),
        "max": max(xs),
        "somme": sum(xs),
    }


# ---------------------------------------------------------------------------
# Découpage des runs
# ---------------------------------------------------------------------------


def fichiers() -> list[tuple[str, Path]]:
    out = [("racine", p) for p in sorted(LOGS.glob("ingest-*.log"))]
    out += [
        ("prospection", p)
        for p in sorted((LOGS / "depuis-prospection-worktree").glob("ingest-*.log"))
    ]
    out += [("veille", p) for p in sorted((LOGS / "depuis-veille-hebdo").glob("ingest-*.log"))]
    return out


def decouper(chemin: Path) -> list[dict]:
    lignes = chemin.read_text(encoding="utf-8").split("\n")
    debuts = []
    i = 0
    while i < len(lignes) - 2:
        if lignes[i] == SEP and lignes[i + 2] == SEP and RE_ENTETE.match(lignes[i + 1]):
            debuts.append(i)
            i += 3
        else:
            i += 1
    runs = []
    for j, d in enumerate(debuts):
        fin = debuts[j + 1] if j + 1 < len(debuts) else len(lignes)
        m = RE_ENTETE.match(lignes[d + 1])
        assert m
        runs.append(
            {
                "slug": m.group(1),
                "debut": m.group(2),
                "modele": m.group(3),
                "modele_verif": m.group(4),
                "fichier": str(chemin.relative_to(BACKEND)),
                "ligne": d + 2,
                "corps": lignes[d + 3 : fin],
            }
        )
    return runs


def blocs(corps: list[str]) -> list[tuple[str, list[str]]]:
    """Regroupe les lignes en blocs qui commencent par un préfixe connu."""
    out: list[tuple[str, list[str]]] = []
    for ligne in corps:
        if ligne.startswith(DEBUT_BLOC):
            out.append((ligne, []))
        elif out:
            out[-1][1].append(ligne)
    return out


def analyser(run: dict) -> dict:
    corps = run["corps"]
    r: dict = {k: v for k, v in run.items() if k != "corps"}
    tours = []
    ok = None
    echec = None
    duree = None
    fin_boucle = None
    erreurs: list[str] = []
    modeles_err: set[str] = set()
    ecr = Counter()
    n_ecr = 0
    yaml_err: list[str] = []
    verif_reels = 0
    verif_panne = 0
    hp_ok = 0
    hp_appels = 0
    bs = blocs(corps)
    for k, (tete, _suite) in enumerate(bs):
        m = RE_TOUR.match(tete)
        if m:
            tours.append(
                tuple(float(x) if i == 4 else int(x) for i, x in enumerate(m.groups()[0:5]))
            )
            continue
        if tete.startswith("[*] "):
            ev = tete[4:]
            mo = RE_OK.match(tete)
            if mo:
                ok = {
                    "tours": int(mo.group(1)),
                    "appels": int(mo.group(2)),
                    "cout": float(mo.group(5)),
                    "inconnu": bool(mo.group(6)),
                    "sortie": int(mo.group(4).replace(" ", "")),
                }
            elif ev.startswith("ÉCHEC"):
                echec = ev
            elif ev.startswith("terminé en"):
                fin_boucle = "termine"
            elif ev.startswith("arrêt"):
                if "tours atteints" in ev:
                    fin_boucle = "max_tours"
                elif "boucle" in ev:
                    fin_boucle = "boucle"
                elif "budget" in ev:
                    fin_boucle = "budget"
                elif "review" in ev:
                    fin_boucle = "sans_review"
                else:
                    fin_boucle = "arret_autre"
            elif ev.startswith("appel en échec"):
                erreurs.append(ev)
                for g in RE_MODELE_ERR.findall(ev):
                    modeles_err.add(g[0] or g[1])
            md = RE_DUREE.search(ev)
            if md and (ev.startswith("terminé") or ev.startswith("arrêt")):
                duree = int(md.group(1))
            continue
        if tete.startswith("[appel] ecrire_aide("):
            n_ecr += 1
            sortie = bs[k + 1][0] if k + 1 < len(bs) and bs[k + 1][0].startswith("[sortie]") else ""
            s = sortie[len("[sortie] ") :]
            if not s.startswith("ERREUR"):
                ecr["ecrite"] += 1
            elif "YAML invalide" in s:
                ecr["yaml_invalide"] += 1
                brut = tete[len("[appel] ecrire_aide(") :]
                brut = brut[:-1] if brut.endswith(")") else brut
                try:
                    yaml_err.append(json.loads(brut)["yaml_texte"])
                except (ValueError, KeyError, TypeError):
                    yaml_err.append("")
            elif "ne respecte pas le schéma" in s:
                ecr["hors_schema"] += 1
            elif "le slug du fichier" in s:
                ecr["slug"] += 1
            elif "yaml_texte" in s:
                ecr["sans_argument"] += 1
            else:
                ecr["autre"] += 1
            continue
        if tete.startswith("[appel] verification_adversariale("):
            sortie_bloc = (
                bs[k + 1] if k + 1 < len(bs) and bs[k + 1][0].startswith("[sortie]") else ("", [])
            )
            texte = "\n".join([sortie_bloc[0], *sortie_bloc[1]])
            if sortie_bloc[0].startswith("[sortie] ## Vérification adversariale"):
                verif_reels += 1
                if "Vérificateur indisponible" in texte:
                    verif_panne += 1
            continue
        if tete.startswith("[appel] declarer_hors_perimetre("):
            hp_appels += 1
            sortie = bs[k + 1][0] if k + 1 < len(bs) else ""
            if not sortie.startswith("[sortie] ERREUR"):
                hp_ok += 1
    # --- issue, par MA règle
    if ok:
        issue = "hors_perimetre" if hp_ok else "acceptee"
    elif echec:
        if fin_boucle in ("max_tours", "boucle", "budget", "sans_review"):
            issue = "abandon"
        elif fin_boucle == "termine":
            issue = "refusee_controles"
        elif erreurs:
            issue = "panne"
        else:
            issue = "echec_autre"
    else:
        issue = "interrompu"
    cumul = tours[-1][4] if tours else 0.0
    if ok and not ok["inconnu"]:
        cout, cout_connu = ok["cout"], True
    elif ok:
        cout, cout_connu = ok["cout"], False
    else:
        cout, cout_connu = cumul, False
    sous = ""
    if issue == "panne":
        derniere = erreurs[-1]
        sous = derniere.split(":")[1].strip() if ":" in derniere else derniere
    r.update(
        {
            "issue": issue,
            "sous_issue": sous,
            "fin_boucle": fin_boucle or "",
            "n_tours": len(tours),
            "duree_s": duree,
            "cout": cout,
            "cout_total_connu": cout_connu,
            "cumul_extracteur": cumul,
            "ok_appels": ok["appels"] if ok else None,
            "tours_x": [t[1] for t in tours],
            "tours_y": [t[2] for t in tours],
            "tours_z": [t[3] for t in tours],
            "n_ecrire": n_ecr,
            "ecr": dict(ecr),
            "verif_reels": verif_reels,
            "verif_panne": verif_panne,
            "hp_appels": hp_appels,
            "modeles_err": sorted(modeles_err),
            "echec": echec or "",
            "n_lignes": len(corps),
            "yaml_err": yaml_err,
        }
    )
    return r


# ---------------------------------------------------------------------------
# Régression par moindres carrés, sans numpy
# ---------------------------------------------------------------------------


def mco(X: list[list[float]], y: list[float]) -> list[float]:
    p = len(X[0])
    A = [[sum(x[i] * x[j] for x in X) for j in range(p)] for i in range(p)]
    b = [sum(x[i] * yy for x, yy in zip(X, y, strict=True)) for i in range(p)]
    # Gauss-Jordan
    M = [row[:] + [bb] for row, bb in zip(A, b, strict=True)]
    for c in range(p):
        piv = max(range(c, p), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        for r in range(p):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [a - f * bb for a, bb in zip(M[r], M[c], strict=True)]
    return [M[i][p] / M[i][i] for i in range(p)]


def r2(beta: list[float], X: list[list[float]], y: list[float]) -> float:
    pred = [sum(b * x for b, x in zip(beta, xs, strict=True)) for xs in X]
    my = sum(y) / len(y)
    ss_res = sum((a - b) ** 2 for a, b in zip(y, pred, strict=True))
    ss_tot = sum((a - my) ** 2 for a in y)
    return 1 - ss_res / ss_tot


# ---------------------------------------------------------------------------


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    agg: dict = {}

    # --- 1. corpus et homonymes
    tous = []
    nb_fichiers = Counter()
    for origine, chemin in fichiers():
        nb_fichiers[origine] += 1
        for run in decouper(chemin):
            run["origine"] = origine
            tous.append(run)
    agg["fichiers"] = dict(nb_fichiers)
    agg["entetes_bruts"] = len(tous)
    par_cle: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for run in tous:
        par_cle[(run["slug"], run["debut"])].append(run)
    doublons = {k: v for k, v in par_cle.items() if len(v) > 1}
    agg["cles_en_double"] = len(doublons)
    noms = defaultdict(set)
    for origine, chemin in fichiers():
        noms[chemin.name].add(origine)
    agg["noms_homonymes"] = sum(1 for v in noms.values() if len(v) > 1)
    # Contenu identique d'un run en double ?
    agg["doublons_corps_identiques"] = sum(
        1 for v in doublons.values() if all(x["corps"] == v[0]["corps"] for x in v)
    )
    runs = [analyser(v[0]) for v in par_cle.values()]
    # Slug de l'en-tête == nom de fichier ?
    agg["slug_entete_different_du_fichier"] = sum(
        1 for r in runs if Path(r["fichier"]).name != f"ingest-{r['slug']}.log"
    )
    n = len(runs)
    agg["runs"] = n
    agg["slugs"] = len({r["slug"] for r in runs})
    agg["date_min"] = min(r["debut"] for r in runs)
    agg["date_max"] = max(r["debut"] for r in runs)
    agg["runs_vides"] = sum(1 for r in runs if r["n_lignes"] <= 1)
    agg["par_origine"] = dict(Counter(r["origine"] for r in runs))

    # --- 2. issues
    iss = Counter(r["issue"] for r in runs)
    agg["issues"] = {k: taux(v, n) for k, v in iss.items()}
    agg["sous_issues_panne"] = dict(Counter(r["sous_issue"] for r in runs if r["issue"] == "panne"))
    agg["fin_boucle_abandon"] = dict(
        Counter(r["fin_boucle"] for r in runs if r["issue"] == "abandon")
    )
    # Pannes : combien ont quand même payé des tours ?
    pannes = [r for r in runs if r["issue"] == "panne"]
    agg["pannes_avec_tours"] = sum(1 for r in pannes if r["n_tours"] > 0)
    agg["pannes_cout"] = sum(r["cout"] for r in pannes)
    # Interrompus : vides ou non
    inter = [r for r in runs if r["issue"] == "interrompu"]
    agg["interrompus_vides"] = sum(1 for r in inter if r["n_tours"] == 0)
    agg["interrompus_avec_erreur"] = sum(
        1 for r in inter if r["n_tours"] == 0 and r["n_lignes"] > 1
    )

    # --- 3. coûts
    acc = [r for r in runs if r["issue"] == "acceptee"]
    acc_connu = [r for r in acc if r["cout_total_connu"]]
    agg["cout_total"] = sum(r["cout"] for r in runs)
    agg["cout_par_run_accepte_connu"] = stats([r["cout"] for r in acc_connu])
    agg["cout_accepte_inconnu"] = stats([r["cout"] for r in acc if not r["cout_total_connu"]])
    agg["cout_sans_ok"] = stats([r["cout"] for r in runs if r["ok_appels"] is None])
    agg["runs_cout_zero"] = sum(1 for r in runs if r["cout"] == 0)
    # Part du vérificateur : total OK - dernier cumul extracteur
    ext = sum(r["cumul_extracteur"] for r in acc_connu)
    tot = sum(r["cout"] for r in acc_connu)
    agg["verificateur_part"] = {"verif": tot - ext, "total": tot, "part": (tot - ext) / tot}
    par_jour = defaultdict(lambda: [0.0, 0.0, 0])
    for r in acc_connu:
        j = r["debut"][:10]
        par_jour[j][0] += r["cout"] - r["cumul_extracteur"]
        par_jour[j][1] += r["cout"]
        par_jour[j][2] += 1
    agg["verificateur_part_par_jour"] = {
        j: {"part": round(v[0] / v[1], 3), "runs": v[2]}
        for j, v in sorted(par_jour.items())
        if v[1]
    }
    jours5 = {j: v for j, v in agg["verificateur_part_par_jour"].items() if v["runs"] >= 5}
    agg["verificateur_part_jours5"] = {
        "jours": len(jours5),
        "min": min(v["part"] for v in jours5.values()),
        "max": max(v["part"] for v in jours5.values()),
    }
    # Contrôle : appels OK - tours = passages réels du vérificateur
    agg["controle_appels_moins_tours"] = Counter(
        (r["ok_appels"] - r["n_tours"]) == r["verif_reels"]
        for r in runs
        if r["ok_appels"] is not None
    )
    agg["controle_appels_moins_tours"] = {
        str(k): v for k, v in agg["controle_appels_moins_tours"].items()
    }

    # --- 4. modèles, heures pleines et tarif
    agg["modeles_entete"] = dict(Counter(r["modele"] for r in runs))
    defaut = [r for r in runs if r["modele"].startswith("(défaut")]
    agg["sans_modele_trace"] = taux(len(defaut), n)
    agg["defaut_revele"] = dict(Counter(",".join(r["modeles_err"]) or "rien" for r in defaut))
    ds = [r for r in runs if r["modele"] == "ds-v41" and r["n_tours"] > 0]
    pleines = sum(1 for r in ds if heure_pleine(datetime.fromisoformat(r["debut"])))
    agg["ds_v41_debut_en_heure_pleine"] = taux(pleines, len(ds))
    agg["ds_v41_cout"] = sum(r["cout"] for r in runs if r["modele"] == "ds-v41")
    # coût par tours : recalcul au tarif du registre
    #   or-glm : 0,07 in / 0,25 out, cache = in/10 (providall pricing.py:21)
    #   ds-v41 : 0,30 in / 1,20 out / 0,006 cache (scripts/pipeline/llm.py:127)
    ecart_glm = []
    for r in runs:
        if not r["tours_x"] or not r["modele"].startswith("(défaut"):
            continue
        c = sum(
            (x * 0.07 + y * 0.007 + z * 0.25) / 1e6
            for x, y, z in zip(r["tours_x"], r["tours_y"], r["tours_z"], strict=True)
        )
        ecart_glm.append(abs(c - r["cumul_extracteur"]))
    agg["defaut_cumul_vs_tarif_or_glm"] = {
        "n": len(ecart_glm),
        "ecart_max": max(ecart_glm),
        "egaux_a_0_001": sum(1 for e in ecart_glm if e < 0.001),
    }

    # --- 5. jetons
    X = [x for r in runs for x in r["tours_x"]]
    Y = [y for r in runs for y in r["tours_y"]]
    Z = [z for r in runs for z in r["tours_z"]]
    ctx = [x + y for x, y in zip(X, Y, strict=True)]
    agg["tours"] = len(X)
    agg["jetons"] = {"hors_cache": sum(X), "cache": sum(Y), "sortie": sum(Z)}
    agg["part_cache"] = sum(Y) / (sum(X) + sum(Y))
    agg["contexte_par_tour"] = stats(ctx)
    agg["tours_au_dessus_110k"] = taux(sum(1 for c in ctx if c > 110_000), len(ctx))
    # Le même agrégat par run (chaque run pèse 1)
    moy_run = [
        sum(a + b for a, b in zip(r["tours_x"], r["tours_y"], strict=True)) / len(r["tours_x"])
        for r in runs
        if r["tours_x"]
    ]
    agg["contexte_moyenne_des_runs"] = stats(moy_run)
    # Contexte par tour, selon le modèle
    for nom, filtre in (("defaut", "(défaut"), ("ds-v41", "ds-v41")):
        cx = [
            x + y
            for r in runs
            if r["modele"].startswith(filtre)
            for x, y in zip(r["tours_x"], r["tours_y"], strict=True)
        ]
        agg[f"contexte_par_tour_{nom}"] = stats(cx)

    # --- 6. écritures
    tot_ecr = sum(r["n_ecrire"] for r in runs)
    motifs = Counter()
    for r in runs:
        motifs.update(r["ecr"])
    refus = tot_ecr - motifs["ecrite"]
    agg["ecritures"] = {
        "appels": tot_ecr,
        "motifs": dict(motifs),
        "refusees": taux(refus, tot_ecr),
        "yaml_ou_schema": taux(motifs["yaml_invalide"] + motifs["hors_schema"], tot_ecr),
    }
    # Par run accepté : taux de refus par run, pour ne pas laisser 1 run de 57 refus peser
    tx_run = [
        (r["n_ecrire"] - r["ecr"].get("ecrite", 0)) / r["n_ecrire"] for r in runs if r["n_ecrire"]
    ]
    agg["ecritures_taux_moyen_par_run"] = stats(tx_run)
    for nom, filtre in (("defaut", "(défaut"), ("ds-v41", "ds-v41")):
        sel = [r for r in runs if r["modele"].startswith(filtre)]
        a = sum(r["n_ecrire"] for r in sel)
        e = sum(r["ecr"].get("ecrite", 0) for r in sel)
        agg[f"ecritures_refusees_{nom}"] = taux(a - e, a)

    # --- 7. vérificateur
    agg["verif_passages"] = sum(r["verif_reels"] for r in runs)
    agg["verif_pannes"] = sum(r["verif_panne"] for r in runs)
    acc_que_pannes = [r for r in acc if r["verif_reels"] and r["verif_reels"] == r["verif_panne"]]
    agg["acceptees_que_pannes"] = taux(len(acc_que_pannes), len(acc))
    agg["acceptees_zero_verif"] = sum(1 for r in acc if r["verif_reels"] == 0)
    agg["acceptees_au_moins_une_panne"] = sum(1 for r in acc if r["verif_panne"])
    agg["acceptees_cout_inconnu"] = sum(1 for r in acc if not r["cout_total_connu"])
    agg["inconnu_et_panne"] = sum(1 for r in acc if not r["cout_total_connu"] and r["verif_panne"])
    agg["hp"] = {
        "runs_avec_appel": sum(1 for r in runs if r["hp_appels"]),
        "dates": sorted(r["debut"][:10] for r in runs if r["hp_appels"]),
        "runs_depuis_2026_09_22": sum(1 for r in runs if r["debut"] >= "2026-09-22"),
    }

    # --- 8. refus par les contrôles
    ref = [r for r in runs if r["issue"] == "refusee_controles"]
    agg["refus_controles"] = {
        "n": len(ref),
        "lint_facts": sum(1 for r in ref if "facts.yaml" in r["echec"]),
        "par_jour": dict(Counter(r["debut"][:10] for r in ref if "facts.yaml" in r["echec"])),
    }

    # --- 9. durées
    durees = [r["duree_s"] for r in runs if r["duree_s"] is not None]
    agg["duree"] = stats(durees)
    top = sorted((r for r in runs if r["duree_s"] is not None), key=lambda r: -r["duree_s"])[:10]
    agg["durees_top10"] = [
        {
            "slug": r["slug"],
            "debut": r["debut"],
            "duree": r["duree_s"],
            "tours": r["n_tours"],
            "verif": r["verif_reels"],
            "issue": r["issue"],
        }
        for r in top
    ]
    # Régression : durée ~ verif + sortie(k) + tours + 1, trois découpages
    reg = [r for r in runs if r["duree_s"] is not None]
    reg.sort(key=lambda r: (r["debut"], r["slug"]))

    def ligne(r: dict) -> list[float]:
        return [r["verif_reels"], sum(r["tours_z"]) / 1000, r["n_tours"], 1.0]

    res = {}
    decoupes = {
        "rang_pair_impair": (
            [r for i, r in enumerate(reg) if i % 2 == 0],
            [r for i, r in enumerate(reg) if i % 2 == 1],
        ),
        "avant_apres_2026_09_17": (
            [r for r in reg if r["debut"] < "2026-09-17"],
            [r for r in reg if r["debut"] >= "2026-09-17"],
        ),
    }
    rnd = random.Random(20261010)
    melange = reg[:]
    rnd.shuffle(melange)
    decoupes["aleatoire_graine_20261010"] = (
        melange[: len(melange) // 2],
        melange[len(melange) // 2 :],
    )
    for nom, (app, ctl) in decoupes.items():
        beta = mco([ligne(r) for r in app], [r["duree_s"] for r in app])
        res[nom] = {
            "n_app": len(app),
            "n_ctl": len(ctl),
            "beta_verif_tours_sortie_k_const": [round(b, 2) for b in beta],
            "r2_controle": round(r2(beta, [ligne(r) for r in ctl], [r["duree_s"] for r in ctl]), 3),
            "r2_apprentissage": round(
                r2(beta, [ligne(r) for r in app], [r["duree_s"] for r in app]), 3
            ),
        }
    # Modèle nul : tours seuls
    app, ctl = decoupes["rang_pair_impair"]
    b2 = mco([[r["n_tours"], 1.0] for r in app], [r["duree_s"] for r in app])
    res["tours_seuls_rang_pair_impair"] = {
        "beta": [round(b, 2) for b in b2],
        "r2_controle": round(
            r2(b2, [[r["n_tours"], 1.0] for r in ctl], [r["duree_s"] for r in ctl]), 3
        ),
    }
    agg["regression"] = res

    # --- 10. semaines
    sem = defaultdict(lambda: {"runs": 0, "slugs": set(), "cout": 0.0, "issues": Counter()})
    for r in runs:
        iso = datetime.fromisoformat(r["debut"]).isocalendar()
        k = f"{iso[0]}-S{iso[1]:02d}"
        sem[k]["runs"] += 1
        sem[k]["slugs"].add(r["slug"])
        sem[k]["cout"] += r["cout"]
        sem[k]["issues"][r["issue"]] += 1
    agg["semaines"] = {
        k: {
            "runs": v["runs"],
            "slugs": len(v["slugs"]),
            "cout": round(v["cout"], 2),
            "issues": dict(v["issues"]),
        }
        for k, v in sorted(sem.items())
    }

    # --- 11. file d'attente et devenir
    with FILE.open(encoding="utf-8") as f:
        file = yaml.safe_load(f)
    blocs_ing = {
        s: t
        for s, t in file.items()
        if isinstance(t, dict) and isinstance(t.get("ingestion"), dict)
    }
    agg["file_blocs_ingestion"] = len(blocs_ing)
    sans_modele = sum(
        1 for t in blocs_ing.values() if str(t["ingestion"].get("modele", "")).startswith("(défaut")
    )
    agg["file_sans_modele"] = taux(sans_modele, len(blocs_ing))
    cout_file = sum(float(t["ingestion"].get("cout_usd") or 0) for t in blocs_ing.values())
    ign = {s: t for s, t in blocs_ing.items() if t.get("statut") == "ignore"}
    agg["file_cout"] = {
        "total": round(cout_file, 2),
        "ignore": round(sum(float(t["ingestion"].get("cout_usd") or 0) for t in ign.values()), 2),
        "n_ignore": len(ign),
    }
    # Jointure run <-> bloc de la file par début
    index_runs = {(r["slug"], r["debut"]): r for r in runs}
    joint = sum(
        1 for s, t in blocs_ing.items() if (s, str(t["ingestion"].get("debut"))) in index_runs
    )
    agg["file_blocs_retrouves_dans_journaux"] = joint
    # Les tâches `ignore` ont-elles une ingestion acceptée dans les journaux ?
    acc_slugs = {r["slug"] for r in acc}
    motif_court = Counter()
    for s, t in ign.items():
        m = str(t.get("motif_ignore") or "")
        mm = re.sub(r"(du \d{4}-\d\d-\d\d|de \S+|:).*$", "", m).strip()[:40]
        motif_court[(mm, s in acc_slugs)] += 1
    agg["file_ignore_par_motif_et_acceptation"] = {
        f"{k[0]} | accepte={k[1]}": v for k, v in motif_court.most_common()
    }
    # Slugs écartés (statut ignore, pas de .yaml)
    cout_slug = defaultdict(float)
    for r in runs:
        cout_slug[r["slug"]] += r["cout"]
    yaml_ok = {p.name[: -len(".yaml")] for p in AIDES.glob("*.yaml")}
    ecartes = [
        s
        for s, t in file.items()
        if isinstance(t, dict) and t.get("statut") == "ignore" and s not in yaml_ok
    ]
    ec_log = [s for s in ecartes if s in cout_slug]
    agg["slugs_ecartes_avec_journal"] = {
        "n": len(ec_log),
        "cout": round(sum(cout_slug[s] for s in ec_log), 2),
        "dont_acceptes": sum(1 for s in ec_log if s in acc_slugs),
        "cout_acceptes": round(sum(cout_slug[s] for s in ec_log if s in acc_slugs), 2),
        "a_zero": sum(1 for s in ec_log if cout_slug[s] == 0),
    }
    # Runs acceptés dont l'aide est écartée aujourd'hui
    acc_ec = [r for r in acc if r["slug"] in set(ecartes)]
    agg["acceptees_puis_ecartees"] = {
        **taux(len(acc_ec), len(acc)),
        "cout": round(sum(r["cout"] for r in acc_ec), 2),
    }

    # Doublons d'URL parmi les écartées, et "test du destinataire"
    def motif(s: str) -> str:
        return str(file.get(s, {}).get("motif_ignore") or "")

    agg["acceptees_puis_ecartees_par_motif"] = dict(
        Counter(re.sub(r"(du \d{4}|de |:).*$", "", motif(r["slug"]))[:30].strip() for r in acc_ec)
    )
    # Catalogue : coût des slugs avec .yaml
    au_cat = [s for s in cout_slug if s in yaml_ok]
    agg["au_catalogue"] = {"n": len(au_cat), "cout": round(sum(cout_slug[s] for s in au_cat), 2)}

    # --- 12. .yaml.echec
    echecs = sorted(AIDES.glob("*.yaml.echec"))
    sens = Counter()
    lignes_sens = []
    entete_worker = 0
    for p in echecs:
        s = p.name[: -len(".yaml.echec")]
        t = file.get(s) if isinstance(file.get(s), dict) else None
        tete = p.read_text(encoding="utf-8")[:400]
        ent = "ÉCHEC D'INGESTION" in tete
        entete_worker += ent
        m = str((t or {}).get("motif_ignore") or "")
        if s in yaml_ok:
            c = "coexiste_yaml"
        elif t is None:
            c = "hors_file"
        elif "doublon" in m.lower() or (t or {}).get("doublon_de"):
            c = "doublon"
        elif t.get("statut") == "echec" and ent:
            c = "echec_pipeline_en_cours"
        elif t.get("statut") == "ignore":
            c = "ecartee"
        else:
            c = f"statut_{t.get('statut')}" + ("_entete" if ent else "")
        sens[c] += 1
        lignes_sens.append([s, c, t.get("statut") if t else "", int(ent), m[:80]])
    agg["yaml_echec"] = {
        "fichiers": len(echecs),
        "sens": dict(sens),
        "entete_worker": entete_worker,
    }
    # L'en-tête du worker figure-t-il dans les .echec écrits par les tris ?
    with (SORTIE / "echec_sens.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["slug", "sens", "statut", "entete_worker", "motif_ignore"])
        w.writerows(lignes_sens)

    # --- 13. git : ces .yaml.echec ont-ils transité par un .yaml committé ?
    try:
        out = subprocess.run(
            [
                "git",
                "-C",
                str(RACINE),
                "log",
                "--format=",
                "--name-status",
                "-M",
                "--diff-filter=AR",
                "--",
                "backend/data/aides",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        renomme = sum(
            1 for li in out.splitlines() if li.startswith("R") and li.endswith(".yaml.echec")
        )
        ajoute = sum(
            1 for li in out.splitlines() if li.startswith("A") and li.endswith(".yaml.echec")
        )
        agg["git_yaml_echec"] = {"renommes_depuis_yaml": renomme, "ajoutes": ajoute}
    except subprocess.CalledProcessError as exc:
        agg["git_yaml_echec"] = {"erreur": str(exc)}

    # --- 14. compléments de la relecture adverse
    complements(runs, acc, agg, file, cout_slug)

    # --- écritures
    with (SORTIE / "runs.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        cols = [
            "slug",
            "debut",
            "origine",
            "fichier",
            "ligne",
            "modele",
            "modeles_err",
            "issue",
            "sous_issue",
            "fin_boucle",
            "n_tours",
            "duree_s",
            "cout",
            "cout_total_connu",
            "cumul_extracteur",
            "n_ecrire",
            "ecrites",
            "verif_reels",
            "verif_panne",
            "hp_appels",
            "echec",
        ]
        w.writerow(cols)
        for r in sorted(runs, key=lambda r: (r["debut"], r["slug"])):
            w.writerow(
                [
                    r["slug"],
                    r["debut"],
                    r["origine"],
                    r["fichier"],
                    r["ligne"],
                    r["modele"],
                    ",".join(r["modeles_err"]),
                    r["issue"],
                    r["sous_issue"],
                    r["fin_boucle"],
                    r["n_tours"],
                    r["duree_s"],
                    round(r["cout"], 4),
                    r["cout_total_connu"],
                    round(r["cumul_extracteur"], 4),
                    r["n_ecrire"],
                    r["ecr"].get("ecrite", 0),
                    r["verif_reels"],
                    r["verif_panne"],
                    r["hp_appels"],
                    r["echec"][:120],
                ]
            )
    (SORTIE / "agregats.json").write_text(
        json.dumps(agg, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    print(json.dumps(agg, ensure_ascii=False, indent=1, default=str))


RE_DP_FR = re.compile(r"\S\s+:\s|^\s*:\s")  # la règle du mesureur, reprise pour comparer


def complements(runs: list[dict], acc: list[dict], agg: dict, file: dict, cout_slug: dict) -> None:
    """Contrôles que la note M04 ne fait pas."""
    # (a) Empreinte tarifaire : le cumul de l'extracteur ds-v41 suit-il le tarif
    #     plein (0,30 / 0,006 / 1,20) ? Contrôle de la méthode d'empreinte.
    ecarts = []
    for r in runs:
        if r["modele"] != "ds-v41" or not r["tours_x"]:
            continue
        c = sum(
            (x * 0.30 + y * 0.006 + z * 1.20) / 1e6
            for x, y, z in zip(r["tours_x"], r["tours_y"], r["tours_z"], strict=True)
        )
        ecarts.append(abs(c - r["cumul_extracteur"]))
    agg["ds_v41_cumul_vs_tarif_plein"] = {
        "n": len(ecarts),
        "egaux_a_0_001": sum(1 for e in ecarts if e < 0.001),
    }
    # (b) Part du coût lue en cache, selon le tarif du registre
    cache_glm = sum(
        y * 0.007 / 1e6 for r in runs if r["modele"].startswith("(défaut") for y in r["tours_y"]
    )
    tot_glm = sum(r["cumul_extracteur"] for r in runs if r["modele"].startswith("(défaut"))
    agg["defaut_extracteur_part_cache_dans_cout"] = {
        "cache_usd": round(cache_glm, 2),
        "extracteur_usd": round(tot_glm, 2),
    }
    # (c) Sensibilité de la part du vérificateur au tarif creux (moitié prix hors
    #     heures pleines), pour les appels au tarif V4.1 : vérificateur partout
    #     (or-ds41 ou ds-v41), extracteur seulement sur ds-v41. Hypothèse : tout
    #     le run tombe dans la tranche de son heure de début.
    v_plein = e_plein = v_creux = e_creux = 0.0
    for r in acc:
        if not r["cout_total_connu"]:
            continue
        v = r["cout"] - r["cumul_extracteur"]
        e = r["cumul_extracteur"]
        f = 1.0 if heure_pleine(datetime.fromisoformat(r["debut"])) else 0.5
        v_plein += v
        e_plein += e
        v_creux += v * f
        e_creux += e * (f if r["modele"] == "ds-v41" else 1.0)
    agg["verificateur_part_si_tarif_creux"] = {
        "plein": round(v_plein / (v_plein + e_plein), 3),
        "creux_applique": round(v_creux / (v_creux + e_creux), 3),
        "total_plein": round(v_plein + e_plein, 2),
        "total_creux_applique": round(v_creux + e_creux, 2),
    }
    debuts_pleins = sum(1 for r in runs if heure_pleine(datetime.fromisoformat(r["debut"])))
    agg["runs_debut_heure_pleine"] = taux(debuts_pleins, len(runs))

    # (d) YAML invalides : la règle du mesureur, puis une règle stricte (le
    #     deux-points pointé par PyYAML est précédé d'une espace).
    regle_m = strict_fr = strict_en = autre_err = sans_marque = total = 0
    hors_mapping = 0
    for r in runs:
        for texte in r["yaml_err"]:
            total += 1
            if not texte:
                sans_marque += 1
                continue
            try:
                yaml.load(texte, Loader=yaml.CSafeLoader)
                autre_err += 1  # valide pour CSafeLoader : loader différent ?
                continue
            except yaml.MarkedYAMLError as exc:
                mq = exc.problem_mark
                prob = exc.problem or ""
            except yaml.YAMLError:
                sans_marque += 1
                continue
            if mq is None:
                sans_marque += 1
                continue
            lignes = texte.split("\n")
            vois = lignes[max(0, mq.line - 1) : mq.line + 1]
            if any(RE_DP_FR.search(v.split("#", 1)[0]) for v in vois):
                regle_m += 1
            if "mapping values are not allowed" not in prob:
                hors_mapping += 1
                continue
            ligne = lignes[mq.line] if mq.line < len(lignes) else ""
            col = mq.column
            if col < len(ligne) and ligne[col] == ":":
                if col > 0 and ligne[col - 1] == " ":
                    strict_fr += 1
                else:
                    strict_en += 1
    agg["yaml_invalide_diagnostic"] = {
        "total": total,
        "regle_mesureur": regle_m,
        "mapping_values_deux_points_precede_espace": strict_fr,
        "mapping_values_deux_points_colle": strict_en,
        "autres_messages": hors_mapping,
        "sans_marque_ou_illisible": sans_marque,
        "valide_au_rechargement": autre_err,
    }

    # (e) Concurrence : combien de runs tournaient en même temps (début et
    #     durée connus) ? La durée murale en dépend.
    fen = [
        (datetime.fromisoformat(r["debut"]).timestamp(), r["duree_s"])
        for r in runs
        if r["duree_s"] is not None
    ]
    debuts = sorted(datetime.fromisoformat(r["debut"]).timestamp() for r in runs)
    conc = []
    import bisect

    for t0, d in fen:
        # runs démarrés pendant ce run, ou dans l'heure qui précède et encore actifs
        i = bisect.bisect_left(debuts, t0)
        j = bisect.bisect_right(debuts, t0 + d)
        conc.append(j - i - 1)
    agg["concurrence_runs_demarres_pendant"] = stats([float(c) for c in conc])

    # (f) Ce que la file de la racine (checkout principal) dirait : non lue ici,
    #     voir la note. On compte en revanche les fiches de review d'ingestion.
    reviews = sorted((BACKEND / "data" / "reviews").glob("*-ingest-*.md"))
    agg["fiches_review_ingest"] = {
        "n": len(reviews),
        "avant_2026_09_07": sum(1 for p in reviews if p.name[:10] < "2026-09-07"),
        "premiere": reviews[0].name[:10] if reviews else None,
    }
    yaml_ok = {p.name[: -len(".yaml")] for p in AIDES.glob("*.yaml")}
    agg["catalogue_sans_journal"] = {
        "yaml": len(yaml_ok),
        "sans_aucun_run": len(yaml_ok - set(cout_slug)),
    }
    # (g) Outil declarer_hors_perimetre dans la liste des outils annoncée
    avec = sans = 0
    for p in sorted(LOGS.glob("ingest-*.log")):
        for ligne in p.read_text(encoding="utf-8").splitlines():
            if "Disponibles :" in ligne:
                if "declarer_hors_perimetre" in ligne:
                    avec += 1
                else:
                    sans += 1
    agg["listes_outils_avec_hors_perimetre"] = {"avec": avec, "sans": sans}
    # (h) Doublons marqués à la main (« tri humain ... Doublon de ») parmi les .yaml.echec
    agg["echec_tri_humain_doublon"] = sum(
        1
        for p in AIDES.glob("*.yaml.echec")
        if re.search(
            r"tri humain.*doublon",
            str((file.get(p.name[: -len(".yaml.echec")]) or {}).get("motif_ignore") or ""),
            re.I,
        )
    )


if __name__ == "__main__":
    main()
