"""Contradictions entre la documentation des pipelines et leur code : le vérifiable.

Commande (depuis backend/) :

    uv run python scripts/mesures/contradictions.py

Produit, dans data/reviews/logs/refonte/2026-10-10-contradictions-1/ :
  - verifications.json : toutes les mesures, chacune avec sa source ;
  - verifications.txt  : la même chose, à lire ;
  - jev-regle-production.csv : issue de la règle de production (Jev + LLM) par cas du banc ;
  - text-vs-source.csv : par condition du catalogue, `text` retrouvé ou non dans les snapshots ;
  - ingestion-tour1.csv : jetons d'entrée du premier tour de chaque tentative d'ingestion.

Lecture seule : aucun appel réseau ni de modèle, aucun script du pipeline exécuté.
Modules importés (lecture de fichiers seulement) : `aides_schema`, `labels`,
`prospection.tri`, `prospection.lecture`, `prospection.arbitre`,
`ingestion.contexte`, `veille_text`, `veille_collect.load_baselines`.
`veille_llm` et `veille_arbitre` sont lus par l'AST (le premier charge le .env).
La liste des fichiers vus par pyright vient de `pyright-verbose.txt`, écrit à
part par `PYRIGHT_PYTHON_IGNORE_WARNINGS=1 uv run --no-sync pyright --verbose .`.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
SCRIPTS = BACKEND / "scripts"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(SCRIPTS))

SORTIE = BACKEND / "data" / "reviews" / "logs" / "refonte" / "2026-10-10-contradictions-1"
LOGS = BACKEND / "data" / "reviews" / "logs"
BANC = LOGS / "benchmark-destinataire"
COMMIT_BANC = "52bf6963"  # HEAD de main pendant le banc du 2026-10-04 (16:14), avant 4ae34348

R: dict[str, Any] = {}


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - m), min(1.0, c + m))


def taux(k: int, n: int) -> dict[str, Any]:
    bas, haut = wilson(k, n)
    return {
        "k": k,
        "n": n,
        "pct": round(100 * k / n, 2) if n else None,
        "ic95": [round(100 * bas, 2), round(100 * haut, 2)],
    }


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(RACINE), *args], capture_output=True, text=True, check=False
    ).stdout


def grep_n(chemin: Path, motif: str) -> list[str]:
    """Les lignes (chemin:ligne: texte) où `motif` (regex) apparaît."""
    if not chemin.exists():
        return []
    rx = re.compile(motif)
    rel = chemin.relative_to(RACINE)
    return [
        f"{rel}:{i}: {ligne.strip()[:160]}"
        for i, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1)
        if rx.search(ligne)
    ]


def lire_jsonl(chemin: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.strip():
            r = json.loads(ligne)
            out[r["slug"]] = r
    return out


# --------------------------------------------------------------------------
# A. Jev au banc du destinataire : la règle de production rejouée
# --------------------------------------------------------------------------


def etiquettes_banc(commit: str) -> dict[str, bool]:
    """Reconstruit les étiquettes de `benchmark_destinataire.cas_etiquetes` à `commit`."""
    fichiers = git("ls-tree", "-r", "--name-only", commit, "backend/data/aides/").split()
    gardes = {Path(f).name[:-5] for f in fichiers if f.endswith(".yaml")}
    echecs = {Path(f).name[:-11] for f in fichiers if f.endswith(".yaml.echec")}
    sources = git("ls-tree", "-r", "--name-only", commit, "backend/data/sources/").split()
    snap = {f.split("/")[3] for f in sources if f.endswith((".md", ".pdf"))}
    file_ = yaml.safe_load(git("show", f"{commit}:backend/data/prospection/file-attente.yaml"))
    cas = {s: True for s in gardes if s in snap}
    for s, t in file_.items():
        motif = t.get("motif_ignore") or ""
        if t.get("statut") != "ignore" or "oublon" in motif:
            continue
        if not motif.startswith(("test du destinataire", "tri humain")):
            continue
        if s in gardes or s not in echecs or s not in snap:
            continue
        cas[s] = False
        MOTIFS_ECARTEES[s] = motif.split(" :")[0].split(" du ")[0]
    return cas


OBJETS_RETENUS = {"bien_ou_lieu", "activite_dans_le_lieu"}
MOTIFS_ECARTEES: dict[str, str] = {}


def bande(r: dict[str, Any], bas: float, haut: float) -> str:
    """`arbitre.bande` + `arbitre.structure_ecarte`, sur une réponse du cache."""
    rep = r["reponses"]
    dep = rep["deposable"]["noul"]
    ecarte = (
        rep["destinataire"].get("choice") != "proprietaire_gestionnaire"
        or rep["objet"].get("choice") not in OBJETS_RETENUS
        or rep["dispositif"]["noul"] < 0.5
    )
    if dep < bas and ecarte:
        return "ecartee"
    if dep > haut and not ecarte:
        return "retenue"
    return "milieu"


def issue_production(jev: dict[str, Any], llm: dict[str, Any], bas: float, haut: float):
    """`lecture.lire` + `_appliquer_arbitrage` : (issue, qui a tranché)."""
    b = bande(jev, bas, haut)
    if b == "ecartee":
        return "ecartee", "jev"
    if b == "retenue":
        return "retenue", "jev"  # le LLM est appelé, mais son écart est réécrit en retenue
    if llm["retenir"]:
        return "retenue", "llm"
    return "humain", "llm"  # indéterminée, ou écart du LLM rendu `indetermine`


def bilan(slugs, cas, jev, llm, bas, haut) -> dict[str, Any]:
    g = [s for s in slugs if cas[s]]
    e = [s for s in slugs if not cas[s]]
    iss = {s: issue_production(jev[s], llm[s], bas, haut) for s in slugs}
    return {
        "seuils": [bas, haut],
        "gardees_ecartees_a_tort": taux(sum(iss[s][0] == "ecartee" for s in g), len(g)),
        "ecartees_retenues_a_tort": taux(sum(iss[s][0] == "retenue" for s in e), len(e)),
        "renvoyees_humain": taux(sum(iss[s][0] == "humain" for s in slugs), len(slugs)),
        "tranchees_par_jev_seul": taux(sum(iss[s][1] == "jev" for s in slugs), len(slugs)),
    }


def ajuster(couples: list[tuple[float, bool]], tol: float = 0.01) -> tuple[float, float]:
    """`benchmark_destinataire.ajuster`, recopié pour ne pas importer le banc."""
    pos = sorted(s for s, g in couples if g)
    neg = sorted((s for s, g in couples if not g), reverse=True)
    bas = pos[int(tol * len(pos))]
    haut = neg[int(tol * len(neg))]
    return bas, max(haut, bas)


def jev_seul(slugs, cas, jev, bas, haut) -> dict[str, Any]:
    g = [s for s in slugs if cas[s]]
    e = [s for s in slugs if not cas[s]]
    d = {s: jev[s]["reponses"]["deposable"]["noul"] for s in slugs}
    return {
        "seuils": [bas, haut],
        "gardees_ecartees_a_tort": taux(sum(d[s] < bas for s in g), len(g)),
        "ecartees_retenues_a_tort": taux(sum(d[s] > haut for s in e), len(e)),
        "renvoyees_humain": taux(sum(bas <= d[s] <= haut for s in slugs), len(slugs)),
    }


def mesure_jev() -> None:
    jev = lire_jsonl(BANC / "jev.jsonl")
    llm = lire_jsonl(BANC / "llm-or-glm.jsonl")
    cas = etiquettes_banc(COMMIT_BANC)
    communs = sorted(s for s in cas if s in llm and s in jev)
    a: dict[str, Any] = {
        "source": f"{BANC.relative_to(RACINE)}/jev.jsonl + llm-or-glm.jsonl ; étiquettes "
        f"reconstruites à {COMMIT_BANC} comme benchmark_destinataire.cas_etiquetes",
        "jeu": {
            "cas": len(cas),
            "gardees": sum(cas.values()),
            "ecartees": len(cas) - sum(cas.values()),
            "juges_par_jev": len(set(cas) & set(jev)),
            "juges_par_les_deux": len(communs),
        },
        "questions_dans_le_cache": sorted(next(iter(jev.values()))["reponses"]),
        "modele_jev": sorted({r["modele"] for r in jev.values()}),
    }
    a["regle_production_dans_echantillon"] = bilan(communs, cas, jev, llm, 0.12, 0.57)
    a["origine_des_ecartees"] = dict(Counter(MOTIFS_ECARTEES.values()))
    # Le LLM de lecture est appelé sur toute page qui n'est pas dans la bande « écartée ».
    a["pages_ou_le_llm_est_appele"] = taux(
        sum(bande(jev[s], 0.12, 0.57) != "ecartee" for s in communs), len(communs)
    )
    a["pages_bande_retenue"] = taux(
        sum(bande(jev[s], 0.12, 0.57) == "retenue" for s in communs), len(communs)
    )
    a["bande_retenue_ou_jev_corrige_le_llm"] = sum(
        bande(jev[s], 0.12, 0.57) == "retenue" and not llm[s]["retenir"] for s in communs
    )
    # Validation croisée à deux plis, sur la même partition que le banc (`_moitie`).
    moitie = {s: int(hashlib.sha256(s.encode()).hexdigest(), 16) % 2 for s in communs}
    plis = []
    cumul = Counter()
    for m in (0, 1):
        app = [(jev[s]["reponses"]["deposable"]["noul"], cas[s]) for s in communs if moitie[s] == m]
        bas, haut = ajuster(app)
        test = [s for s in communs if moitie[s] != m]
        b = bilan(test, cas, jev, llm, bas, haut)
        plis.append({"appris_sur": m, "n_apprentissage": len(app), "n_controle": len(test), **b})
        for cle in (
            "gardees_ecartees_a_tort",
            "ecartees_retenues_a_tort",
            "renvoyees_humain",
            "tranchees_par_jev_seul",
        ):
            cumul[cle + "_k"] += b[cle]["k"]
            cumul[cle + "_n"] += b[cle]["n"]
    a["regle_production_validation_croisee"] = {
        "plis": plis,
        "cumul": {
            c: taux(cumul[c + "_k"], cumul[c + "_n"])
            for c in (
                "gardees_ecartees_a_tort",
                "ecartees_retenues_a_tort",
                "renvoyees_humain",
                "tranchees_par_jev_seul",
            )
        },
    }
    a["seuils_ajustes_sur_tout_le_jeu_commun"] = ajuster(
        [(jev[s]["reponses"]["deposable"]["noul"], cas[s]) for s in communs]
    )
    a["jev_seul_tolerance_0.12_0.57"] = jev_seul(communs, cas, jev, 0.12, 0.57)
    a["jev_seul_charge_egale_0.13_0.48"] = jev_seul(communs, cas, jev, 0.13, 0.48)
    g = [s for s in communs if cas[s]]
    e = [s for s in communs if not cas[s]]
    a["llm_seul"] = {
        "gardees_ecartees_a_tort": taux(
            sum(not llm[s]["retenir"] and not llm[s]["indeterminee"] for s in g), len(g)
        ),
        "ecartees_retenues_a_tort": taux(sum(bool(llm[s]["retenir"]) for s in e), len(e)),
        "renvoyees_humain": taux(sum(bool(llm[s]["indeterminee"]) for s in communs), len(communs)),
    }
    a["cout_jev_usd"] = round(sum(r.get("cout_usd") or 0 for r in jev.values()), 4)
    a["latence_mediane_jev_s"] = statistics.median(r["latence_s"] for r in jev.values())
    a["cout_lecture_or_glm_usd_par_page"] = round(
        sum(r.get("cout_usd") or 0 for r in llm.values()) / len(llm), 6
    )
    a["jetons_entree_lecture_mediane"] = statistics.median(r["jetons_entree"] for r in llm.values())
    a["jetons_entree_jev_mediane"] = statistics.median(r["jetons_entree"] for r in jev.values())
    R["A_jev_banc"] = a
    with (SORTIE / "jev-regle-production.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["slug", "garde", "deposable", "bande", "llm", "issue", "tranche_par"])
        for s in communs:
            i, qui = issue_production(jev[s], llm[s], 0.12, 0.57)
            lu = (
                "retenue"
                if llm[s]["retenir"]
                else "humain"
                if llm[s]["indeterminee"]
                else "ecartee"
            )
            w.writerow(
                [
                    s,
                    int(cas[s]),
                    jev[s]["reponses"]["deposable"]["noul"],
                    bande(jev[s], 0.12, 0.57),
                    lu,
                    i,
                    qui,
                ]
            )


# --------------------------------------------------------------------------
# B. Où Jev est branché
# --------------------------------------------------------------------------


def constantes(chemin: Path, noms: set[str]) -> dict[str, Any]:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    for n in arbre.body:
        cible = None
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            cible, val = n.targets[0].id, n.value
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value:
            cible, val = n.target.id, n.value
        if cible in noms:
            try:
                out[cible] = ast.literal_eval(val)
            except ValueError:
                out[cible] = ast.unparse(val)
    return out


def mesure_branchements_jev() -> None:
    utilisateurs = sorted(
        str(p.relative_to(RACINE))
        for p in SCRIPTS.rglob("*.py")
        if "mesures" not in p.parts
        and p.name != "decision.py"
        and re.search(r"pipeline\.decision|ClientDecision", p.read_text(encoding="utf-8"))
    )
    R["B_jev_branchements"] = {
        "modules_qui_importent_le_client": utilisateurs,
        "veille_arbitre_seuils": constantes(
            SCRIPTS / "veille_arbitre.py", {"SEUIL_FILTRE", "SEUIL_GARDE", "SEUIL_REFONTE"}
        ),
        "arbitre_seuils": constantes(
            SCRIPTS / "prospection" / "arbitre.py", {"SEUIL_BAS", "SEUIL_HAUT"}
        ),
        "appels_arbitre_pour_dans_prospecter": grep_n(
            SCRIPTS / "prospecter.py", r"arbitre = arbitre_pour"
        ),
        "balayage_mentionne_jev": grep_n(SCRIPTS / "balayage.py", r"(?i)jev"),
        "doc_un_seul_endroit": grep_n(RACINE / "docs" / "jev.md", r"un seul endroit"),
    }


# --------------------------------------------------------------------------
# C. Doctrine et prompts de la prospection
# --------------------------------------------------------------------------


def mesure_doctrine() -> None:
    from ingestion.contexte import titres
    from prospection import arbitre, lecture, tri

    doc = tri.doctrine()
    R["C_doctrine"] = {
        "titres_extraits_par_tri_doctrine": [t for t in titres(doc) if t.startswith("Étape")],
        "car_doctrine": len(doc),
        "car_consigne_lecture": len(lecture.consigne()),
        "car_CONSIGNE_DESTINATAIRE_ecrite_dans_le_code": len(lecture.CONSIGNE_DESTINATAIRE),
        "car_CONSIGNE_EXTRACTION": len(lecture.CONSIGNE_EXTRACTION),
        "car_etat_jev_doctrine": len(arbitre.etat("u", "")["doctrine"]),
        "questions_jev_production": list(arbitre.QUESTIONS),
        "appelants_de_doctrine": sorted(
            f"{p.relative_to(RACINE)}"
            for p in (SCRIPTS / "prospection").glob("*.py")
            if re.search(r"\bdoctrine\(", p.read_text(encoding="utf-8"))
        ),
        "claude_md_etape_3": grep_n(RACINE / "CLAUDE.md", r"étape 3 du skill"),
    }


# --------------------------------------------------------------------------
# D. Ingestion : prompt, outils, contrôles
# --------------------------------------------------------------------------


def _fonction(chemin: Path, nom: str) -> ast.FunctionDef:
    for n in ast.walk(ast.parse(chemin.read_text(encoding="utf-8"))):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise KeyError(nom)


def mesure_ingestion() -> None:
    from ingestion import contexte

    from aides_schema import load_facts, load_pending_facts

    facts = dict(load_facts())
    pending = dict(load_pending_facts())
    systeme = contexte.prompt_systeme(facts, pending)
    index = contexte.index_faits(facts, pending)
    schema = contexte.condense_schema()
    skill = contexte.sans_front_matter(contexte.SKILL_PATH.read_text(encoding="utf-8"))
    d: dict[str, Any] = {
        "prompt_systeme_car": len(systeme),
        "prompt_systeme_jetons_estimes_3.6": contexte.estimer_jetons(systeme),
        "dont_skill_car": len(skill),
        "dont_index_faits_car": len(index),
        "dont_schema_car": len(schema),
        "faits_indexes": len(facts) + len(pending),
        "doc_23000": grep_n(SCRIPTS / "ingestion" / "worker.py", r"23 000")
        + grep_n(SCRIPTS / "ingestion" / "contexte.py", r"23 [05]00|12 500 pour"),
    }
    # Outils : la liste passée à providall.tool dans construire_outils.
    src = (SCRIPTS / "ingestion" / "outils.py").read_text(encoding="utf-8")
    m = re.search(r"providall\.tool\(f\)\s*for f in \((.*?)\)", src, re.S)
    noms = re.findall(r"\b([a-z_]+),", m.group(1)) if m else []
    d["outils"] = noms
    d["nb_outils"] = len(noms)
    d["doc_nb_outils"] = (
        grep_n(SCRIPTS / "ingestion" / "outils.py", r"(?i)quatorze|treize|quinze")
        + grep_n(BACKEND / "tests" / "test_ingestion_bout_en_bout.py", r"(?i)treize|quatorze")
        + grep_n(BACKEND / "data" / "README.md", r"(?i)quinze|huit contr")
    )
    # Contrôles : chaque motif d'échec distinct de worker.controler.
    f = _fonction(SCRIPTS / "ingestion" / "worker.py", "controler")
    motifs = []
    for n in ast.walk(f):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "append":
            motifs.append(ast.unparse(n.args[0])[:70])
        if isinstance(n, ast.Return) and isinstance(n.value, ast.List) and n.value.elts:
            motifs.append(ast.unparse(n.value.elts[0])[:70])
    d["controler_motifs_distincts"] = motifs
    d["nb_controler_motifs"] = len(motifs)
    d["doc_nb_controles"] = grep_n(SCRIPTS / "ingestion" / "worker.py", r"six contrôles")
    # Premier tour de chaque tentative, dans tous les journaux copiés.
    rx_tete = re.compile(r"^(\S+) \u2014 (\d{4}-\d{2}-\d{2})T\S+ \u2014 ingestion (.+?) / ")
    rx_tour = re.compile(r"^--- tour 1 \u2014 entrée (\d+) \(\+(\d+) cache\)")
    lignes = []
    for journal in sorted(LOGS.rglob("ingest-*.log")):
        if "refonte" in journal.parts:
            continue
        tete = None
        with journal.open(encoding="utf-8", errors="replace") as fh:
            for ligne in fh:
                mt = rx_tete.match(ligne)
                if mt:
                    tete = mt.groups()
                    continue
                mr = rx_tour.match(ligne)
                if mr and tete:
                    lignes.append(
                        [tete[0], tete[1], tete[2], int(mr[1]) + int(mr[2]), journal.parent.name]
                    )
                    tete = None
    with (SORTIE / "ingestion-tour1.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["slug", "date", "modele", "jetons_entree_tour1", "dossier"])
        w.writerows(lignes)
    par_mois: dict[str, list[int]] = {}
    for _s, date_, modele, j, _d in lignes:
        par_mois.setdefault(f"{date_[:7]} {modele}", []).append(j)
    d["tour1_jetons_par_mois"] = {
        k: {"n": len(v), "mediane": statistics.median(v), "min": min(v), "max": max(v)}
        for k, v in sorted(par_mois.items())
    }
    d["tour1_tentatives"] = len(lignes)
    toutes = [li[3] for li in lignes]
    d["tour1_jetons_tous"] = {
        "n": len(toutes),
        "mediane": statistics.median(toutes),
        "p10": sorted(toutes)[len(toutes) // 10],
        "p90": sorted(toutes)[9 * len(toutes) // 10],
    }
    R["D_ingestion"] = d


# --------------------------------------------------------------------------
# E. Familles
# --------------------------------------------------------------------------


def mesure_familles() -> None:
    import typing

    from prospection.tri import Famille

    from labels import FAMILLES_LABELS

    skills = RACINE / ".claude" / "skills"
    R["E_familles"] = {
        "FAMILLES_LABELS": len(FAMILLES_LABELS),
        "adjacente_dans_FAMILLES_LABELS": "adjacente" in FAMILLES_LABELS,
        "Famille_du_tri": len(typing.get_args(Famille)),
        "mentions_13": grep_n(skills / "ingest-aide" / "SKILL.md", r"13 valeurs")
        + grep_n(skills / "prospecter-aides-region" / "SKILL.md", r"(?i)treize familles")
        + grep_n(SCRIPTS / "ingestion" / "worker.py", r"13 valeurs"),
        "mentions_14": grep_n(BACKEND / "data" / "TYPING.md", r"14 valeurs"),
        "vide_permis_par_la_doc": grep_n(skills / "ingest-aide" / "SKILL.md", r"vide = l'aide")
        + grep_n(BACKEND / "data" / "TYPING.md", r"Vide = l'aide"),
        "vide_refuse_par_le_code": grep_n(
            SCRIPTS / "ingestion" / "worker.py", r"not aide.familles"
        ),
        "famille_decidee_par_un_humain": grep_n(
            BACKEND / "data" / "TYPING.md", r"décidée par un humain"
        ),
        "famille_vient_de_la_lecture": grep_n(
            SCRIPTS / "prospection" / "fiche.py", r"famille=f\.famille"
        )
        + grep_n(SCRIPTS / "ingestion" / "worker.py", r"famille=tache\.famille"),
    }


# --------------------------------------------------------------------------
# F. pyright, CI, pre-commit
# --------------------------------------------------------------------------


def mesure_outillage() -> None:
    py = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    cfg = json.loads((BACKEND / "pyrightconfig.json").read_text(encoding="utf-8"))
    tous = [
        p
        for p in BACKEND.rglob("*.py")
        if ".venv" not in p.parts and "scripts" not in p.relative_to(BACKEND).parts[:1]
    ]
    par_dossier = Counter(p.relative_to(BACKEND).parts[0] if len(p.parts) else "" for p in tous)
    verbose = SORTIE / "pyright-verbose.txt"
    texte = verbose.read_text(encoding="utf-8") if verbose.exists() else ""
    m = re.search(r"Found (\d+) source files", texte)
    m_cfg = re.search(r"Loading configuration file at (\S+)", texte)
    hors_git = [p for p in tous if "logs" in p.parts]
    ci = (RACINE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    pc = (RACINE / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    R["F_outillage"] = {
        "pyproject_tool_pyright": py["tool"]["pyright"],
        "pyrightconfig_json": {k: cfg[k] for k in ("include", "exclude", "extraPaths")},
        "pyright_config_chargee": m_cfg[1] if m_cfg else None,
        "pyright_fichiers_trouves": int(m[1]) if m else None,
        "py_hors_scripts_et_venv": len(tous),
        "dont_routers": par_dossier.get("routers", 0),
        "dont_tests": par_dossier.get("tests", 0),
        "dont_services": par_dossier.get("services", 0),
        "dont_copies_hors_git_sous_data_reviews_logs": len(hors_git),
        "rapports_desactives_pyrightconfig": sorted(k for k, v in cfg.items() if v == "none"),
        "lint_aides_data_dans_ci": "lint_aides_data" in ci,
        "lint_aides_data_dans_pre_commit": "lint_aides_data" in pc,
        "pre_commit_git_add_u": [li.strip() for li in pc.splitlines() if "git add -u" in li],
        "pre_push_hooks": re.findall(r"- id: (\S+)\n(?:.*\n){1,5}?\s+stages: \[pre-push\]", pc),
        "doc_lint_ci": grep_n(SCRIPTS / "lint_aides_data.py", r"CI"),
        "doc_claude_pyright": grep_n(RACINE / "CLAUDE.md", r"pyright n'analyse pas"),
    }


# --------------------------------------------------------------------------
# G. Skill /typer-aides, incident d'écriture concurrente, étiquettes veille
# --------------------------------------------------------------------------


def mesure_divers() -> None:
    skills = sorted(p.name for p in (RACINE / ".claude" / "skills").iterdir() if p.is_dir())
    histo = git("log", "--all", "--format=%h", "--", ".claude/skills/typer-aides").split()
    fp_90009f77 = git("show", "90009f77:backend/data/facts_pending.yaml").splitlines()[:8]
    etiq = BACKEND / "data" / "reviews" / "2026-10-04-etiquettes-veille-jev.md"
    t = etiq.read_text(encoding="utf-8") if etiq.exists() else ""
    R["G_divers"] = {
        "skills_presents": skills,
        "typer_aides_present": (RACINE / ".claude" / "skills" / "typer-aides").exists(),
        "typer_aides_dans_historique_git_all": histo,
        "mentions_typer_aides": grep_n(RACINE / "CLAUDE.md", r"typer-aides")
        + grep_n(BACKEND / "data" / "README.md", r"typer-aides"),
        "incident_balayage": grep_n(SCRIPTS / "balayage.py", r"incident du 2026"),
        "incident_verrou": grep_n(SCRIPTS / "pipeline" / "verrou.py", r"2026-09-04"),
        "facts_pending_a_90009f77": [li for li in fp_90009f77 if "2026" in li],
        "creation_ingerer_et_verrou": git(
            "log",
            "--diff-filter=A",
            "--format=%h %ad",
            "--date=short",
            "--",
            "backend/scripts/pipeline/verrou.py",
        ).strip(),
        "etiquettes_veille_coches_d_office": t.count("coché d'office"),
        "etiquettes_veille_cases_x": t.count("[x]"),
        "etiquettes_dites_humaines": grep_n(SCRIPTS / "veille_benchmark_jev.py", r"HUMAINE")
        + grep_n(BACKEND / "data" / "README.md", r"HUMAINES"),
        "fichiers_suivis_mais_ignores": [
            li for li in git("ls-files", "-ci", "--exclude-standard").splitlines() if li
        ],
        "valeur_57_pct": grep_n(SCRIPTS / "pipeline" / "etat.py", r"57 %")
        + grep_n(SCRIPTS / "prospection" / "lecture.py", r"57 %"),
        "cout_lecture_ecrit": grep_n(SCRIPTS / "prospecter.py", r"0,004"),
        "modeles_docstring_ingerer": grep_n(SCRIPTS / "ingerer.py", r"LLM_MODEL_"),
        "balayage_modeles_par_defaut": grep_n(SCRIPTS / "balayage.py", r'default="ds-v41"'),
        "veille_modele_defaut": grep_n(SCRIPTS / "veille_llm.py", r"^MODELE_DEFAUT"),
        "max_ajouts": grep_n(SCRIPTS / "veille_audit.py", r"^MAX_AJOUTS_CONDITIONS")
        + grep_n(SCRIPTS / "veille_update.py", r"MAX_AJOUTS_CONDITIONS")
        + grep_n(RACINE / "docs" / "plan-veille-audit.md", r"MAX_AJOUTS_CONDITIONS"),
        "cache_banc_par_slug": grep_n(SCRIPTS / "benchmark_destinataire.py", r'r\["slug"\]\] = r'),
    }


# --------------------------------------------------------------------------
# H. Catalogue : chiffres datés de la doc contre l'état du worktree
# --------------------------------------------------------------------------


def mesure_catalogue() -> dict[str, Any]:
    from aides_schema import AIDES_DIR, gate_porteur, load_aide, load_facts, load_pending_facts

    aides = {p.stem: load_aide(p) for p in sorted(AIDES_DIR.glob("*.yaml"))}
    echec = len(list(AIDES_DIR.glob("*.yaml.echec")))
    untyped = [(s, c.id) for s, a in aides.items() for c in a.conditions if c.kind == "untyped"]
    citations: Counter[str] = Counter()
    for a in aides.values():
        for f in {c.fact for c in a.conditions if c.fact}:
            citations[f] += 1
    facts = load_facts()
    pending = load_pending_facts()
    connus = set(facts) | set(pending)
    cites = [f for f in connus if citations.get(f)]
    R["H_catalogue"] = {
        "yaml": len(aides),
        "yaml_echec": echec,
        "conditions": sum(len(a.conditions) for a in aides.values()),
        "conditions_untyped": len(untyped),
        "aides_avec_untyped": len({s for s, _ in untyped}),
        "faits_facts_yaml": len(facts),
        "faits_pending": len(pending),
        "faits_cites_par_une_seule_aide": taux(sum(citations[f] == 1 for f in cites), len(cites)),
        "faits_jamais_cites_par_un_champ_fact": len(connus) - len(cites),
        "aides_hard_filters_travaux": sum(bool(a.hard_filters.travaux) for a in aides.values()),
        "aides_gate_porteur": sum(gate_porteur(a) for a in aides.values()),
        "doc_typing_35_580": grep_n(
            BACKEND / "data" / "TYPING.md", r"35 aides seulement|580 aides sur 643"
        ),
        "doc_142_fiches": grep_n(BACKEND / "data" / "README.md", r"142 fiches"),
        "doc_5_aides_typees": grep_n(BACKEND / "data" / "README.md", r"kind: untyped`, à"),
    }
    return aides


# --------------------------------------------------------------------------
# I. `text` des conditions contre leurs sources
# --------------------------------------------------------------------------


def _pdf_sans_ecriture(content: bytes) -> str | None:
    """`veille_collect.pdf_bytes_to_text` sans écrire le cache disque (lecture seule)."""
    import veille_collect

    cache = veille_collect.PDFTEXT_CACHE_DIR / f"{hashlib.sha256(content).hexdigest()}.txt"
    if cache.is_file():
        return cache.read_text(encoding="utf-8")
    return veille_collect._pdftotext(content)


def mesure_text(aides: dict[str, Any]) -> None:
    import veille_collect
    from veille_collect import load_baselines
    from veille_text import find_quote_in_any, normalize

    # Le cache pdftotext s'écrit dans backend/.cache/ : hors de nos emplacements.
    veille_collect.pdf_bytes_to_text = _pdf_sans_ecriture  # type: ignore[assignment]

    lignes = []
    for slug, a in aides.items():
        documents, _illisibles, _prov = load_baselines(slug)
        for c in a.conditions:
            if not documents:
                lignes.append([slug, c.id, c.kind, "sans_snapshot", "", "", ""])
                continue
            _n, m = find_quote_in_any(c.text, documents)
            # Scission autorisée par TYPING.md : « préfixe de contexte : fragment ».
            fragment = c.text.split(" : ", 1)[1] if " : " in c.text else ""
            m2 = find_quote_in_any(fragment, documents)[1] if len(fragment) >= 20 else None
            egal = bool(c.quote) and normalize(c.text) == normalize(c.quote or "")
            lignes.append(
                [
                    slug,
                    c.id,
                    c.kind,
                    m.status,
                    "" if m2 is None else m2.status,
                    int(egal),
                    int(bool(c.quote)),
                ]
            )
    with (SORTIE / "text-vs-source.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "slug",
                "condition",
                "kind",
                "text_dans_source",
                "fragment_apres_prefixe",
                "text_egal_quote",
                "a_quote",
            ]
        )
        w.writerows(lignes)
    jugees = [li for li in lignes if li[3] != "sans_snapshot"]
    trouve = [li for li in jugees if li[3] != "absente"]
    trouve_frag = [li for li in jugees if li[3] != "absente" or li[4] not in ("", "absente")]
    avec_quote = [li for li in jugees if li[6] == 1]
    R["I_text"] = {
        "conditions": len(lignes),
        "sans_snapshot": len(lignes) - len(jugees),
        "text_retrouve_tel_quel_dans_les_snapshots": taux(len(trouve), len(jugees)),
        "text_retrouve_en_comptant_la_scission_prefixee": taux(len(trouve_frag), len(jugees)),
        "text_egal_a_sa_quote_normalisee": taux(sum(li[5] for li in avec_quote), len(avec_quote)),
        "doc_jamais_reformule": grep_n(RACINE / "CLAUDE.md", r"jamais reformulé")
        + grep_n(BACKEND / "data" / "README.md", r"jamais être réécrit"),
        "skill_reformulation": grep_n(
            RACINE / ".claude" / "skills" / "ingest-aide" / "SKILL.md", r"reformulation minimale"
        ),
    }


# --------------------------------------------------------------------------


def ecrire() -> None:
    (SORTIE / "verifications.json").write_text(
        json.dumps(R, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    with (SORTIE / "verifications.txt").open("w", encoding="utf-8") as fh:
        fh.write(f"HEAD {git('rev-parse', 'HEAD').strip()}\n\n")
        for cle, val in R.items():
            fh.write(f"== {cle}\n{json.dumps(val, ensure_ascii=False, indent=2, default=str)}\n\n")


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    mesure_jev()
    mesure_branchements_jev()
    mesure_doctrine()
    mesure_ingestion()
    mesure_familles()
    mesure_outillage()
    mesure_divers()
    aides = mesure_catalogue()
    mesure_text(aides)
    ecrire()
    print(f"écrit dans {SORTIE.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
