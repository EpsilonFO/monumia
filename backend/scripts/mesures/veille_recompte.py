"""Recompte adverse de la note `docs/refonte-pipeline/notes/veille.md` (2026-10-10).

Lecture seule. Ne réutilise pas `scripts/mesures/veille.py` : chaque chiffre est
recompté depuis les fichiers bruts (cas, étiquettes, caches Jev et étage C,
manifeste, journaux, git). Aucun appel réseau ni modèle ; `pdftotext` lit les
PDF vers la sortie standard, sans cache disque.

Sorties : `data/reviews/logs/refonte/2026-10-10-veille-recompte-1/` (un JSON par
question, plus `resume.txt`).

    cd backend && uv run python scripts/mesures/veille_recompte.py
"""

from __future__ import annotations

import collections
import datetime as dt
import glob
import json
import math
import os
import random
import re
import subprocess
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
DATA = BACKEND / "data"
LOGS = DATA / "reviews" / "logs"
JEV = LOGS / "veille-jev"
SORTIE = LOGS / "refonte" / "2026-10-10-veille-recompte-1"
SEUIL = 0.45
AVANT, APRES = "f2688777", "c36cbfd9"  # parent du commit de la veille, et ce commit
MOIS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.96) -> dict:
    if n == 0:
        return {"k": k, "n": n, "texte": f"{k}/0"}
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    bas, haut = max(0.0, c - h), min(1.0, c + h)
    texte = f"{k}/{n} = {100 * p:.1f} % [{100 * bas:.1f} ; {100 * haut:.1f}]".replace(".", ",")
    return {
        "k": k,
        "n": n,
        "p": round(p, 4),
        "ic95": [round(bas, 4), round(haut, 4)],
        "texte": texte,
    }


def git(*args: str) -> str:
    r = subprocess.run(["git", "-C", str(RACINE), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def yaml_a(rev: str, slug: str) -> dict:
    return yaml.safe_load(git("show", f"{rev}:backend/data/aides/{slug}.yaml")) or {}


def aplatir(d, p: str = "") -> dict:
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(aplatir(v, f"{p}.{k}" if p else k))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out.update(aplatir(v, f"{p}[{i}]"))
    else:
        out[p] = d
    return out


def norm(t: str) -> str:
    t = t.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    t = re.sub(r"[*_]", "", t)
    return re.sub(r"\s+", " ", t).lower()


def ecrire(nom: str, obj) -> None:
    (SORTIE / nom).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), "utf-8")


# --------------------------------------------------------------------------
# Données de base
# --------------------------------------------------------------------------


def etiquettes() -> dict[str, str]:
    """Parseur indépendant de la fiche d'étiquetage : dernière case cochée par bloc."""
    et, cour, coches = {}, None, collections.Counter()
    fiche = DATA / "reviews" / "2026-10-04-etiquettes-veille-jev.md"
    for ligne in fiche.read_text("utf-8").splitlines():
        if ligne.startswith("### "):
            cour = ligne[4:].strip()
        elif cour and (m := re.match(r"- \[[xX]\] (.+?)\s*$", ligne)):
            et[cour] = m.group(1)
            coches[cour] += 1
    assert not [k for k, v in coches.items() if v > 1], "bloc à plusieurs cases cochées"
    return et


def charger():
    cas = json.loads((JEV / "cas-2026-10-04.json").read_text("utf-8"))
    jev = [json.loads(x) for x in (JEV / "jev.jsonl").read_text("utf-8").splitlines()]
    etc = [json.loads(x) for x in (JEV / "etage-c.jsonl").read_text("utf-8").splitlines()]
    etat = yaml.safe_load((DATA / "veille-state.yaml").read_text("utf-8"))
    return cas, etiquettes(), jev, etc, etat


# --------------------------------------------------------------------------
# Q1 : changements manqués
# --------------------------------------------------------------------------


def q1(cas, et, jev, etc, etat) -> dict:
    snap = [c for c in cas if c["origine"] == "snapshots"]
    inch = [c for c in snap if c["verdict_llm"] == "inchange"]
    faux = [c for c in inch if et[c["id"]] == "touche"]
    app = [c for c in snap if c["verdict_llm"] == "applique"]
    ids_faux = {c["id"] for c in faux}
    refus = {k for k, v in etat.items() if "maj_refusee" in v}
    direct = [c for c in cas if c["origine"] == "direct" and c["jeu"] == "A"]
    esc_c_touche = [c["slug"] for c in direct if c["slug"] in refus and et[c["id"]] == "touche"]
    esc_c_non = [c["slug"] for c in direct if c["slug"] in refus and et[c["id"]] != "touche"]
    esc_c_sans_cas = sorted(refus - {c["slug"] for c in direct})

    # Garde : notes du cache, par cas
    notes: dict[str, list[float]] = collections.defaultdict(list)
    for x in jev:
        if x["usage"] == "garde":
            notes[x["cas"]].append(x["p"])
    ids_banc72 = set(notes)  # 72 cas notés en garde (63 vrais + 9 faux au rapport)
    balayage = {}
    for s in (0.08, 0.20, 0.45, 0.60):
        for qui, idx in (("derniere_note", -1), ("premiere_note", 0)):
            perdus = sum(1 for i in ids_faux if notes[i][idx] < s)
            fa72 = sum(1 for i in ids_banc72 - ids_faux if notes[i][idx] >= s)
            fa54 = sum(1 for c in inch if c["id"] not in ids_faux and notes[c["id"]][idx] >= s)
            balayage[f"{s}:{qui}"] = {
                "perdus_sur_9": perdus,
                "fausses_alertes_sur_63": fa72,
                "fausses_alertes_sur_54": fa54,
            }
    pos = sorted(notes[i][-1] for i in ids_faux)
    loo = sum(1 for j, p in enumerate(pos) if p < 0.8 * min(pos[:j] + pos[j + 1 :]))

    # Étage C : par configuration, et bootstrap par cas (les 10 rejeux ne sont pas indépendants)
    lab = {c["id"]: et[c["id"]] for c in snap}
    par_cfg = collections.defaultdict(list)
    for x in etc:
        par_cfg[x["modele"]].append(x)
    cfg, tot = {}, collections.Counter()
    par_cas = collections.defaultdict(lambda: [0, 0, 0])  # essais, perdus sans, perdus avec
    for m, xs in sorted(par_cfg.items()):
        p = [x for x in xs if lab.get(x["cas"]) == "touche"]
        n = [x for x in xs if lab.get(x["cas"]) == "ne touche pas"]
        ls = [x for x in p if x["etat"] == "inchange"]
        lg = [x for x in ls if x["garde"] is None or x["garde"] < SEUIL]
        cfg[m] = {
            "positifs": len(p),
            "perdus_sans_garde": len(ls),
            "perdus_avec_garde": len(lg),
            "positifs_escalades": sum(x["etat"] == "escalade" for x in p),
            "negatifs": len(n),
            "fausses_retouches": sum(x["etat"] == "applique" for x in n),
            "negatifs_escalades": sum(x["etat"] == "escalade" for x in n),
        }
        for k, v in cfg[m].items():
            tot[k] += v
        for x in p:
            e = par_cas[x["cas"]]
            e[0] += 1
            e[1] += x["etat"] == "inchange"
            e[2] += x["etat"] == "inchange" and (x["garde"] is None or x["garde"] < SEUIL)
    rng = random.Random(20261010)
    cles = sorted(par_cas)
    tirages = {"sans": [], "avec": []}
    for _ in range(10000):
        ech = [par_cas[rng.choice(cles)] for _ in cles]
        essais = sum(e[0] for e in ech)
        tirages["sans"].append(sum(e[1] for e in ech) / essais)
        tirages["avec"].append(sum(e[2] for e in ech) / essais)

    def pct(v):
        v = sorted(v)
        return [round(v[int(0.025 * len(v))], 4), round(v[int(0.975 * len(v))], 4)]

    perdus_cas = collections.Counter(
        x["cas"]
        for x in etc
        if lab.get(x["cas"]) == "touche"
        and x["etat"] == "inchange"
        and (x["garde"] is None or x["garde"] < SEUIL)
    )
    # Les 9 positifs : la correction (ré-ingestion ou main) a-t-elle changé calendrier, financement, cumul ?
    preuve_correction = {}
    for c in faux:
        a, b = yaml_a(AVANT, c["slug"]), yaml_a(APRES, c["slug"])
        champs = sorted(
            k
            for sec in ("calendrier", "financement", "cumul")
            for k in set(aplatir(a.get(sec), sec)) | set(aplatir(b.get(sec), sec))
            if aplatir(a.get(sec), sec).get(k) != aplatir(b.get(sec), sec).get(k)
            and not k.endswith(("delai_instruction", "assiette"))
        )
        preuve_correction[c["slug"]] = {
            "note_garde": notes[c["id"]][-1],
            "etiquette_auto": c["etiquette_auto"] or "aucune (agents Claude)",
            "champs_mandat_changes_par_la_correction": champs,
            "conditions_avant_apres": [
                len(a.get("conditions") or []),
                len(b.get("conditions") or []),
            ],
        }
    n_reels_large = len(app) + len(faux) + len(esc_c_touche)
    return {
        "cas": {
            "snapshots": len(snap),
            "inchange_actuel": len(inch),
            "inchange_banc_notes": len(ids_banc72),
            "faux_inchange": len(faux),
            "faux_par_regle_de_code": sorted(c["slug"] for c in faux if c["etiquette_auto"]),
            "appliques": len(app),
            "notes_garde_hors_jeu_actuel": sorted(ids_banc72 - {c["id"] for c in inch}),
            "notes_doubles": {k: v for k, v in notes.items() if len(v) > 1},
        },
        "taux": {
            "faux_sur_72": wilson(len(faux), len(ids_banc72)),
            "faux_sur_63": wilson(len(faux), len(inch)),
            "perdus_sur_33_note": wilson(len(faux), len(app) + len(faux)),
            "perdus_sur_reels_vus_par_C_escalades_comprises": wilson(len(faux), n_reels_large),
            "perdus_avec_garde_sur_reels_vus_par_C": wilson(
                sum(1 for i in ids_faux if notes[i][-1] < SEUIL), n_reels_large
            ),
            "escalades_C_touche_sur_reels": wilson(len(esc_c_touche), n_reels_large),
            "garde_045_perdus_sur_9": wilson(sum(1 for i in ids_faux if notes[i][-1] < SEUIL), 9),
            "garde_045_perdus_sur_33": wilson(sum(1 for i in ids_faux if notes[i][-1] < SEUIL), 33),
            "garde_045_fausses_alertes_sur_63": wilson(
                balayage["0.45:derniere_note"]["fausses_alertes_sur_63"], 63
            ),
            "loo_regle_80pct": wilson(loo, 9),
        },
        "escalades_etage_C": {
            "n": len(refus),
            "cas_direct_touche": esc_c_touche,
            "cas_direct_ne_touche_pas": esc_c_non,
            "sans_cas": esc_c_sans_cas,
        },
        "balayage_garde": balayage,
        "notes_des_9": sorted((notes[i][-1], i) for i in ids_faux),
        "etage_c": {
            "par_configuration": cfg,
            "total": dict(tot),
            "perdus_sans_garde": wilson(tot["perdus_sans_garde"], tot["positifs"]),
            "perdus_avec_garde": wilson(tot["perdus_avec_garde"], tot["positifs"]),
            "rattrapes_par_garde": wilson(
                tot["perdus_sans_garde"] - tot["perdus_avec_garde"], tot["perdus_sans_garde"]
            ),
            "fausses_retouches": wilson(tot["fausses_retouches"], tot["negatifs"]),
            "positifs_escalades": wilson(tot["positifs_escalades"], tot["positifs"]),
            "bootstrap_par_cas_ic95": {
                "cas_distincts": len(cles),
                "perdus_sans_garde": pct(tirages["sans"]),
                "perdus_avec_garde": pct(tirages["avec"]),
            },
            "cas_perdus_avec_garde": dict(perdus_cas),
            "cas_distincts_perdus_sans_garde": sum(1 for e in par_cas.values() if e[1]),
            "cas_distincts_perdus_avec_garde": sum(1 for e in par_cas.values() if e[2]),
        },
        "preuve_correction_des_9": preuve_correction,
    }


# --------------------------------------------------------------------------
# Q2 : exactitude des retouches
# --------------------------------------------------------------------------


def motifs_date(d: dt.date) -> tuple[list[str], list[str]]:
    js = [str(d.day), f"{d.day:02d}"] + (["1er"] if d.day == 1 else [])
    complets, sans_annee = [d.isoformat()], []
    for j in js:
        complets.append(f"{j} {MOIS[d.month - 1]} {d.year}")
        sans_annee.append(f"{j} {MOIS[d.month - 1]}")
        for sep in "/.-":
            complets += [f"{j}{sep}{d.month:02d}{sep}{d.year}", f"{j}{sep}{d.month}{sep}{d.year}"]
            sans_annee.append(f"{j}{sep}{d.month:02d}")
    return complets, sans_annee


def texte_snapshots(slug: str) -> str:
    out = []
    for f in sorted(glob.glob(str(DATA / "sources" / slug / "2026-10-04*"))):
        if f.endswith(".pdf"):
            out.append(
                subprocess.run(
                    ["pdftotext", "-layout", f, "-"], capture_output=True, text=True
                ).stdout
            )
        else:
            out.append(Path(f).read_text("utf-8", errors="replace"))
    return norm("\n".join(out))


def q2(cas) -> dict:
    apps = [
        c["slug"] for c in cas if c["origine"] == "snapshots" and c["verdict_llm"] == "applique"
    ]
    champs = []
    for slug in apps:
        a, b = yaml_a(AVANT, slug), yaml_a(APRES, slug)
        fa, fb = {}, {}
        for sec in ("calendrier", "financement", "cumul"):
            fa.update(aplatir(a.get(sec), sec))
            fb.update(aplatir(b.get(sec), sec))
        texte = texte_snapshots(slug)
        for k in sorted(set(fa) | set(fb)):
            if fa.get(k) == fb.get(k):
                continue
            v = fb.get(k)
            if isinstance(v, dt.date):
                complets, sans = motifs_date(v)
                if any(norm(m) in texte for m in complets):
                    cat = "tel_quel"
                elif any(
                    re.search(r"(?<!\d)" + re.escape(norm(m)) + r"(?!\d)", texte) for m in sans
                ):
                    cat = "sans_annee"
                else:
                    cat = "absent"
            elif isinstance(v, bool) or v is None or isinstance(v, str):
                cat = "non_verifiable"
            else:
                n = int(v)
                motifs = {str(n), f"{n:,}".replace(",", " "), f"{n:,}".replace(",", ".")}
                cat = (
                    "tel_quel"
                    if any(re.search(r"(?<!\d)" + re.escape(m) + r"(?!\d)", texte) for m in motifs)
                    else "absent"
                )
            champs.append({"slug": slug, "champ": k, "avant": fa.get(k), "apres": v, "cat": cat})
    cats = collections.Counter(c["cat"] for c in champs)
    verif = cats["tel_quel"] + cats["sans_annee"] + cats["absent"]

    # Ancienne valeur encore présente AILLEURS dans l'aide au HEAD (hors calendrier et financement)
    def motifs_anciens(v) -> list[str]:
        if isinstance(v, dt.date):
            j = "1er" if v.day == 1 else str(v.day)
            return [f"{j} {MOIS[v.month - 1]} {v.year}", f"{v.day} {MOIS[v.month - 1]} {v.year}"]
        if isinstance(v, int) and not isinstance(v, bool):
            return [f"{v:,}".replace(",", " ") + " €", f"{v} €", f"montant_max {v}"]
        return []

    def chaines(d, p=""):
        if isinstance(d, dict):
            for k, v in d.items():
                yield from chaines(v, f"{p}.{k}" if p else k)
        elif isinstance(d, list):
            for v in d:
                yield from chaines(v, p)
        elif isinstance(d, str):
            yield p, " ".join(d.replace(" ", " ").replace(" ", " ").split())

    restes = collections.defaultdict(set)
    for slug in apps:
        chemin = DATA / "aides" / f"{slug}.yaml"
        if not chemin.exists():
            chemin = chemin.with_name(chemin.name + ".echec")
        y = yaml.safe_load(chemin.read_text("utf-8"))
        for c in champs:
            if c["slug"] != slug:
                continue
            for p, s in chaines(y):
                if p.startswith(("calendrier", "financement")):
                    continue
                if any(m in s for m in motifs_anciens(c["avant"])):
                    restes[slug].add((c["champ"], p.split(".")[0]))
    return {
        "champs_changes": len(champs),
        "categories": dict(cats),
        "aides": len({c["slug"] for c in champs}),
        "tel_quel": wilson(cats["tel_quel"], verif),
        "detail": champs,
        "ancienne_valeur_ailleurs_au_HEAD": {k: sorted(v) for k, v in restes.items()},
        "aides_avec_ancienne_valeur_ailleurs": wilson(len(restes), len(apps)),
        "dont_dans_fiche": sorted(k for k, v in restes.items() if any(s == "fiche" for _, s in v)),
        "dont_dans_demarche": sorted(
            k for k, v in restes.items() if any(s == "demarche" for _, s in v)
        ),
        "dont_dans_conditions": sorted(
            k for k, v in restes.items() if any(s == "conditions" for _, s in v)
        ),
    }


# --------------------------------------------------------------------------
# Q3 : coût, statuts, règles
# --------------------------------------------------------------------------


def q3(etat, cas, et) -> dict:
    journal = (LOGS / "depuis-veille-hebdo" / "veille-2026-10-04.log").read_text("utf-8")
    lignes = re.findall(
        r"\[(\d+)/117\]\s+(\S)\s+(\S+)\s+([\d.]+)¢\s+([\d.]+)s", journal
    )  # une ligne par appel
    cout = [float(x[3]) / 100 for x in lignes]
    lat = sorted(float(x[4]) for x in lignes)
    cout_s = sorted(cout)

    def quantile(v, q):  # rang inclusif, interpolé
        i = q * (len(v) - 1)
        b = int(i)
        return v[b] + (v[min(b + 1, len(v) - 1)] - v[b]) * (i - b)

    statuts = collections.Counter(v["status"] for v in etat.values())
    dates = collections.Counter((v["status"], v.get("checked_at")) for v in etat.values())
    rapport = (DATA / "reviews" / "2026-10-04-veille.md").read_text("utf-8")
    esc = re.search(
        r"## Escalades \u2014 ré-ingestion complète\n(.*?)\nCommande prête", rapport, re.S
    )
    regles = collections.Counter()
    for ligne in (esc.group(1) if esc else "").splitlines():
        if not ligne.startswith("- **"):
            continue
        if "page officielle morte" in ligne:
            regles["B_page_morte"] += 1
        elif "document binaire modifié" in ligne:
            regles["B_binaire"] += 1
        elif "refonte de" in ligne:
            regles["B_refonte"] += 1
        elif "non ancrée" in ligne:
            regles["C_ancrage"] += 1
        elif "condition(s) nouvelle" in ligne or "condition(s) disparue" in ligne:
            regles["C_structure"] += 1
        elif "changement majeur" in ligne:
            regles["C_majeur"] += 1
        else:
            regles["autre"] += 1
    # « inchangé » du LLM contre étiquettes : combien d'appels n'avaient vraiment rien dans le mandat ?
    # 74 « inchangé » au journal, moins les 9 étiquetés « touche » (les 65 autres sont
    # « ne touche pas » : 54 au jeu actuel, 9 sortis par le filtre Jalios, 2 passés en direct).
    faux = sum(
        1
        for c in cas
        if c["origine"] == "snapshots"
        and c["verdict_llm"] == "inchange"
        and et[c["id"]] == "touche"
    )
    ing = {}
    for f in sorted((LOGS / "depuis-veille-hebdo").glob("ingest-*.log")):
        t = f.read_text("utf-8")
        ok = re.findall(r"OK \u2014 \d+ tour\(s\), (\d+) appel\(s\).*?\$(\d+\.\d+)", t)
        duree = re.findall(r"terminé en \d+ tour\(s\), \$[\d.]+ / \$[\d.]+, durée (\d+) s", t)
        runs = t.count("\u2014 ingestion (défaut")
        cumul_par_run = [
            max([float(x) for x in re.findall(r"cumul \$([\d.]+)", seg)] or [0.0])
            for seg in re.split(r"\n=+\n[^\n]*\u2014 ingestion \(défaut[^\n]*\n", t)[1:]
        ]
        ing[f.stem] = {
            "appels": [int(x[0]) for x in ok],
            "cout_ok": [float(x[1]) for x in ok],
            "duree_s": [int(x) for x in duree],
            "lancements": runs,
            "cumul_ingestion_par_lancement": cumul_par_run,
        }
    cout_ok = sum(sum(v["cout_ok"]) for v in ing.values())
    non_compte = sum(
        v["cumul_ingestion_par_lancement"][0]
        for v in ing.values()
        if v["lancements"] > len(v["cout_ok"])
    )
    return {
        "etage_c": {
            "appels": len(lignes),
            "symboles": dict(collections.Counter(x[1] for x in lignes)),
            "cout_usd": round(sum(cout), 4),
            "cout_median": quantile(cout_s, 0.5),
            "cout_p90_inclusif": round(quantile(cout_s, 0.9), 5),
            "cout_max": max(cout),
            "latence_mediane": quantile(lat, 0.5),
            "latence_p90_inclusif": round(quantile(lat, 0.9), 2),
            "latence_max": max(lat),
            "latence_somme": round(sum(lat), 1),
        },
        "statuts_manifeste": dict(statuts),
        "statuts_x_checked_at": {f"{a}|{b}": n for (a, b), n in dates.items()},
        "escalades_par_regle_rapport": dict(regles),
        "inchange_vraiment_hors_mandat_selon_etiquettes": wilson(74 - faux, 117),
        "inchange_selon_llm": wilson(74, 117),
        "reingestions": ing,
        "reingestions_cout_ok": round(cout_ok, 4),
        "reingestions_cout_lancements_abandonnes_minimum": round(non_compte, 4),
    }


# --------------------------------------------------------------------------
# Q4 : devenir, dans ce worktree et dans tous les checkouts
# --------------------------------------------------------------------------


def q4(etat) -> dict:
    lots = {
        s: sorted(k for k, v in etat.items() if v["status"] == s)
        for s in ("escalade_ingestion", "date_perimee_source_inchangee", "erreur_http")
    }
    racines = [Path("/Users/felixollivier/monumia")] + [
        Path(p) for p in sorted(glob.glob("/Users/felixollivier/monumia/.claude/worktrees/*"))
    ]
    out = {}
    for lot, slugs in lots.items():
        res = {"n": len(slugs), "snapshots_posterieurs_par_checkout": {}, "commits": {}}
        for r in racines:
            n = 0
            for s in slugs:
                d = r / "backend" / "data" / "sources" / s
                if d.is_dir() and any(f[:10] > "2026-10-04" for f in os.listdir(d)):
                    n += 1
            res["snapshots_posterieurs_par_checkout"][r.name] = n
        commits = collections.Counter()
        for s in slugs:
            for c in git(
                "log",
                "--since=2026-10-04T16:43",
                "--format=%h",
                "--",
                f"backend/data/aides/{s}.yaml",
                f"backend/data/aides/{s}.yaml.echec",
            ).split():
                commits[c] += 1
        res["commits"] = dict(commits)
        res["ack"] = sum(1 for s in slugs if "ack" in etat[s])
        res["traites"] = wilson(0, len(slugs))
        out[lot] = res
    branches = git("branch", "-a", "--contains", APRES).split()
    out["commit_veille_dans"] = [b for b in branches if b not in ("*", "+")]
    out["commit_veille_dans_main"] = "main" in branches
    out["commit_veille_dans_origin_main"] = "remotes/origin/main" in branches
    out["cvl_pact_cooperation_date_limite_sur_main"] = re.findall(
        r"date_limite: (\S+)", git("show", "main:backend/data/aides/cvl-pact-cooperation.yaml")
    )[:1]
    return out


# --------------------------------------------------------------------------
# Q5 : pannes comptées
# --------------------------------------------------------------------------


def q5(etat, jev, etc) -> dict:
    notes = [x["p"] for x in jev] + [x["garde"] for x in etc if x["garde"] is not None]
    refus = [v["maj_refusee"]["etat"] for v in etat.values() if "maj_refusee" in v]
    journaux = sorted(LOGS.glob("veille-*.log")) + sorted(
        (LOGS / "depuis-veille-hebdo").glob("veille-*.log")
    )
    return {
        "notes": len(notes),
        "notes_nulles": sum(1 for p in notes if p == 0),
        "note_min": min(notes),
        "maj_refusee": dict(collections.Counter(refus)),
        "inchange_banc_sans_note": sum(
            1 for x in etc if x["etat"] == "inchange" and x["garde"] is None
        ),
        "echec_banc": [
            (x["modele"], x["cas"], x["etape_echec"]) for x in etc if x["etat"] == "echec"
        ],
        "journaux_avec_jev": [j.name for j in journaux if "[Jev " in j.read_text("utf-8")],
        "journaux_appel_en_echec": [
            j.name for j in journaux if "appel au modèle en échec" in j.read_text("utf-8")
        ],
    }


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    cas, et, jev, etc, etat = charger()
    r1, r2, r3, r4, r5 = (
        q1(cas, et, jev, etc, etat),
        q2(cas),
        q3(etat, cas, et),
        q4(etat),
        q5(etat, jev, etc),
    )
    for nom, r in (("q1", r1), ("q2", r2), ("q3", r3), ("q4", r4), ("q5", r5)):
        ecrire(f"{nom}.json", r)
    t1, c = r1["taux"], r1["etage_c"]
    resume = [
        f"faux inchangé /72 : {t1['faux_sur_72']['texte']} ; /63 : {t1['faux_sur_63']['texte']}",
        f"perdus /33 (note) : {t1['perdus_sur_33_note']['texte']}",
        f"perdus /réels vus par C (escalades C comprises) : "
        f"{t1['perdus_sur_reels_vus_par_C_escalades_comprises']['texte']}",
        f"perdus avec garde /réels vus par C : {t1['perdus_avec_garde_sur_reels_vus_par_C']['texte']}",
        f"escalades C touche /réels : {t1['escalades_C_touche_sur_reels']['texte']}",
        f"garde 0,45 : {t1['garde_045_perdus_sur_9']['texte']} ; {t1['garde_045_perdus_sur_33']['texte']} ; "
        f"FA {t1['garde_045_fausses_alertes_sur_63']['texte']}",
        f"LOO règle 80 % : {t1['loo_regle_80pct']['texte']}",
        f"étage C sans garde {c['perdus_sans_garde']['texte']} avec {c['perdus_avec_garde']['texte']} "
        f"rattrapés {c['rattrapes_par_garde']['texte']} bootstrap {c['bootstrap_par_cas_ic95']}",
        f"étage C fausses retouches {c['fausses_retouches']['texte']} ; positifs escaladés "
        f"{c['positifs_escalades']['texte']}",
        f"Q2 {r2['categories']} tel quel {r2['tel_quel']['texte']} ; ancienne valeur ailleurs "
        f"{r2['aides_avec_ancienne_valeur_ailleurs']['texte']}",
        f"Q3 étage C {r3['etage_c']} ; statuts {r3['statuts_manifeste']} ; règles "
        f"{r3['escalades_par_regle_rapport']}",
        f"Q3 hors mandat selon étiquettes {r3['inchange_vraiment_hors_mandat_selon_etiquettes']['texte']}",
        f"Q3 ré-ingestions {r3['reingestions_cout_ok']} $ + lancements abandonnés ≥ "
        f"{r3['reingestions_cout_lancements_abandonnes_minimum']} $",
        f"Q4 commit de veille dans main : {r4['commit_veille_dans_main']} ; branches {r4['commit_veille_dans']}",
        f"Q5 {r5}",
    ]
    (SORTIE / "resume.txt").write_text("\n".join(resume) + "\n", "utf-8")
    print("\n".join(resume))


if __name__ == "__main__":
    main()
