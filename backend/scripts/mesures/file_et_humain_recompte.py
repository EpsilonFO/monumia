"""Recompte adverse de la note `docs/refonte-pipeline/notes/file-et-humain.md`.

Lecture seule : la file d'attente (fichier courant et versions git), le
catalogue `data/aides/`, `data/veille-state.yaml`, les fiches de `data/reviews/`
et les journaux de session Claude de `~/.claude/projects/`. Aucun appel réseau,
aucun appel de modèle. N'importe de `scripts/mesures/file_et_humain.py` RIEN :
chaque chiffre est recalculé ici par un chemin indépendant.

Seul import du code de production : `pipeline.etat` (`charger`,
`motif_non_promotion`), qui ne fait que lire.

Sorties : `data/reviews/logs/refonte/2026-10-10-file-et-humain-recompte-1/`.

Usage, depuis `backend/` :

    uv run python scripts/mesures/file_et_humain_recompte.py
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND / "scripts"))

from pipeline.etat import charger, motif_non_promotion  # noqa: E402

CHARGEUR = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
FILE = "backend/data/prospection/file-attente.yaml"
AIDES = BACKEND / "data/aides"
REVIEWS = BACKEND / "data/reviews"
SORTIE = BACKEND / "data/reviews/logs/refonte/2026-10-10-file-et-humain-recompte-1"
JOURNAUX = Path.home() / ".claude/projects"
SESSION_COURANTE = "2e3e5583-2e50-4f96-aef5-ca962a6eb567"

#: Les commits qui touchent la file, dans l'ordre topologique de HEAD
#: (`git log HEAD -- backend/data/prospection/file-attente.yaml`, inversé).
COMMITS = [
    "90009f77",
    "2d3096bd",
    "836e21cb",
    "84bdd821",
    "f032af72",
    "25d57a18",
    "b4226e37",
    "57f054d7",
    "1d94a758",
    "88d46d5d",
    "fdde0102",
    "0a974ed5",
    "6d6faf13",
]


def wilson(k: int, n: int) -> dict:
    if n == 0:
        return {"k": k, "n": n}
    z = 1.959964
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"k": k, "n": n, "p": round(p, 4), "ic95": [round(c - h, 4), round(c + h, 4)]}


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(BACKEND), *args], capture_output=True, text=True, check=False
    ).stdout


def version(commit: str) -> dict:
    return yaml.load(git("show", f"{commit}:{FILE}"), Loader=CHARGEUR) or {}


def statut(v: dict) -> str:
    return v.get("statut", "a_valider")


def famille(m: str | None) -> str:
    if not m:
        return "sans_motif"
    prefixes = [
        ("doublon", "doublon d'URL"),
        ("tri_2026_09_22", "test du destinataire"),
        ("tri_2026_09_30", "tri humain du 2026-09-30"),
        ("requalif_2026_10_04", "requalification du 2026-10-04"),
        ("ingestion_llm", "hors périmètre à l'ingestion"),
    ]
    for cle, p in prefixes:
        if m.startswith(p):
            return cle
    if "arbitrage humain du 2026-09-24" in m:
        return "arbitrage_2026_09_24"
    if m.startswith("hors périmètre"):
        return "lecture_llm"
    return "autre"


def ecrire(nom: str, obj) -> None:
    (SORTIE / nom).write_text(
        json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 1. File : état, sans motif, a_valider
# ---------------------------------------------------------------------------


def etat_file(cur: dict, V: dict) -> dict:
    st = Counter(statut(v) for v in cur.values())
    ign = [s for s, v in cur.items() if statut(v) == "ignore"]
    sans = [s for s in ign if not cur[s].get("motif_ignore")]
    av = [s for s, v in cur.items() if statut(v) == "a_valider"]
    dest = sum(1 for s in av if cur[s].get("destinataire", "indetermine") == "indetermine")
    obj = sum(1 for s in av if cur[s].get("objet", "indetermine") == "indetermine")
    naif = sum(
        1
        for s in av
        if "indetermine"
        in (cur[s].get("destinataire", "indetermine"), cur[s].get("objet", "indetermine"))
    )
    taches = charger(BACKEND / "data/prospection/file-attente.yaml")
    motifs = Counter(
        (motif_non_promotion(taches[s]) or "promouvable").split(" \u2014")[0].split(" :")[0]
        for s in av
    )
    # Première apparition des 111 sans motif dans l'historique.
    premiere = Counter()
    for s in sans:
        for c in COMMITS:
            if s in V[c]:
                premiere[f"{c}:{statut(V[c][s])}"] += 1
                break
    ho = BACKEND / "data/reviews/logs/refonte-entrees/d6fb7845-jev-reel-2026-10-04/jev113_ho.jsonl"
    ho_slugs = {json.loads(x)["slug"] for x in ho.read_text().splitlines() if x.strip()}
    return {
        "fichier_identique_HEAD": (BACKEND / "data/prospection/file-attente.yaml").read_text(
            encoding="utf-8"
        )
        == git("show", f"HEAD:{FILE}"),
        "entrees": len(cur),
        "statuts": dict(st),
        "ignore_sans_motif": wilson(len(sans), len(ign)),
        "sans_motif_par_ajoute_le": dict(Counter(str(cur[s].get("ajoute_le")) for s in sans)),
        "sans_motif_premiere_apparition": dict(premiere),
        "sans_motif_dans_jev113_ho": len(set(sans) & ho_slugs),
        "jev113_ho_n": len(ho_slugs),
        "jev113_ho_statut_actuel": dict(
            Counter(
                f"{statut(cur[s])}:{'motif' if cur[s].get('motif_ignore') else 'sans'}"
                for s in ho_slugs
                if s in cur
            )
        ),
        "a_valider": {
            "n": len(av),
            "destinataire_indetermine": wilson(dest, len(av)),
            "objet_indetermine": wilson(obj, len(av)),
            "l_un_des_deux_naif": wilson(naif, len(av)),
            "motif_non_promotion": dict(motifs),
        },
    }


# ---------------------------------------------------------------------------
# 2. Promotions : toutes celles de l'historique, pas les seules survivantes
# ---------------------------------------------------------------------------


def epoque(v: dict) -> str:
    d = str((v.get("ingestion") or {}).get("debut") or "")[:10]
    if not d:
        return "sans_date"
    if d <= "2026-09-20":
        return "avant_2026_09_21"
    if d <= "2026-09-30":
        return "2026_09_21_a_09_30"
    if d == "2026-10-04":
        return "2026_10_04"
    return "apres_2026_10_04"


def promotions(cur: dict, V: dict) -> dict:
    promues = set()
    for c in COMMITS:
        for s, v in V[c].items():
            if statut(v) in ("valide", "en_cours", "ingere", "echec") or v.get("ingestion"):
                promues.add(s)
    for s, v in cur.items():
        if v.get("ingestion") or statut(v) in ("valide", "en_cours", "ingere", "echec"):
            promues.add(s)
    survivantes = [s for s in promues if statut(cur[s]) in ("ingere", "echec")]
    sans_humain = [
        s for s in promues if epoque(cur[s]) in ("avant_2026_09_21", "2026_09_21_a_09_30")
    ]
    surv_sans_humain = [s for s in survivantes if s in sans_humain]
    return {
        "promues_dans_l_historique": len(promues),
        "statut_actuel": dict(Counter(statut(cur[s]) for s in promues)),
        "par_epoque_de_debut": dict(Counter(epoque(cur[s]) for s in promues)),
        "taux_sans_humain_toutes": wilson(len(sans_humain), len(promues)),
        "taux_sans_humain_survivantes_ingere_echec": wilson(
            len(surv_sans_humain), len(survivantes)
        ),
    }


def lot_2026_10_04() -> dict:
    taches = charger(BACKEND / "data/prospection/file-attente.yaml")
    lot = {s: t for s, t in taches.items() if str(t.ajoute_le) == "2026-10-04"}
    verdict = Counter()
    for t in lot.values():
        m = motif_non_promotion(t.model_copy(update={"statut": "a_valider"}))
        if m is None:
            verdict["regle_promeut"] += 1
        elif m.startswith("hors périmètre"):
            verdict["regle_ecarte"] += 1
        else:
            verdict["regle_ne_tranche_pas"] += 1
    detail = Counter()
    for t in lot.values():
        m = motif_non_promotion(t.model_copy(update={"statut": "a_valider"}))
        k = "promeut" if m is None else ("ecarte" if m.startswith("hors périmètre") else "humain")
        detail[f"{t.statut}|{'motif' if t.motif_ignore else 'sans'}|{k}"] += 1
    n = len(lot)
    return {
        "n": n,
        "verdict_de_la_regle_actuelle": dict(verdict),
        "detail": dict(detail),
        "ne_tranche_pas": wilson(verdict["regle_ne_tranche_pas"], n),
        "ne_tranche_pas_si_promotion_non_comptee": wilson(n - verdict["regle_ecarte"], n),
    }


def ingerees_puis_ecartees(cur: dict) -> dict:
    blk = {s: v for s, v in cur.items() if v.get("ingestion")}
    ok = {s: v for s, v in blk.items() if not v["ingestion"].get("motif_echec")}
    hors_doublon = [s for s, v in ok.items() if famille(v.get("motif_ignore")) != "doublon"]
    par = defaultdict(lambda: [0, 0])
    for s in hors_doublon:
        e = "avant_2026_09_21" if epoque(cur[s]) == "avant_2026_09_21" else "apres"
        par[e][1] += 1
        par[e][0] += statut(cur[s]) == "ignore"
    return {
        "avec_bloc": len(blk),
        "sans_motif_echec": len(ok),
        "familles": dict(
            Counter(f"{statut(v)}|{famille(v.get('motif_ignore'))}" for v in ok.values())
        ),
        "hors_doublons": wilson(
            sum(statut(cur[s]) == "ignore" for s in hors_doublon), len(hors_doublon)
        ),
        "par_epoque": {k: wilson(*v) for k, v in par.items()},
    }


def transitions(V: dict) -> dict:
    sortie = {}
    for nom, chemin in (
        ("via_fdde0102", [c for c in COMMITS if c != "88d46d5d"]),
        ("via_88d46d5d", [c for c in COMMITS if c != "fdde0102"]),
    ):
        traj: dict[str, list[str]] = defaultdict(list)
        for c in chemin:
            for s, v in V[c].items():
                if not traj[s] or traj[s][-1] != statut(v):
                    traj[s].append(statut(v))
        cpt = Counter(f"{a}>{b}" for t in traj.values() for a, b in zip(t, t[1:], strict=False))
        sortie[nom] = dict(cpt)
    cur = V["6d6faf13"]
    traj: dict[str, list[str]] = defaultdict(list)
    for c in [c for c in COMMITS if c != "88d46d5d"]:
        for s, v in V[c].items():
            if not traj[s] or traj[s][-1] != statut(v):
                traj[s].append(statut(v))
    for cle in ("ingere>ignore", "echec>ignore"):
        sl = [
            s
            for s, t in traj.items()
            if any(f"{a}>{b}" == cle for a, b in zip(t, t[1:], strict=False))
        ]
        sortie[f"{cle}_par_famille_de_motif"] = dict(
            Counter(famille(cur[s].get("motif_ignore")) for s in sl)
        )
    return sortie


def reouvertures(V: dict) -> list[dict]:
    a, b, z = V["1d94a758"], V["88d46d5d"], V["6d6faf13"]
    lignes = []
    for s in sorted(b):
        if s in a and statut(a[s]) == "ignore" and statut(b[s]) != "ignore":
            lignes.append(
                {
                    "slug": s,
                    "motif_avant": famille(a[s].get("motif_ignore")),
                    "statut_88d46d5d": statut(b[s]),
                    "statut_6d6faf13": statut(z[s]),
                    "motif_garde": bool(z[s].get("motif_ignore")),
                    "yaml": (AIDES / f"{s}.yaml").exists(),
                    "yaml_echec": (AIDES / f"{s}.yaml.echec").exists(),
                }
            )
    return lignes


def ingere_sans_yaml(cur: dict) -> dict:
    ing = [s for s, v in cur.items() if statut(v) == "ingere"]
    sans = [s for s in ing if not (AIDES / f"{s}.yaml").exists()]
    echec = [s for s in sans if (AIDES / f"{s}.yaml.echec").exists()]
    rien = [s for s in sans if s not in echec]
    supprime = Counter()
    for s in rien:
        d = git(
            "log", "--all", "--diff-filter=D", "--format=%h", "--", f"data/aides/{s}.yaml"
        ).split()
        supprime[d[0] if d else "jamais_committee"] += 1
    renomme = Counter()
    for s in echec:
        h = git("log", "--format=%h", "--", f"data/aides/{s}.yaml.echec").split()
        renomme[h[-1] if h else "?"] += 1
    return {
        "n": len(sans),
        "sur": len(ing),
        "dont_yaml_echec": len(echec),
        "commit_de_renommage": dict(renomme),
        "dont_aucun_fichier": dict(supprime),
    }


# ---------------------------------------------------------------------------
# 3. J3 et les 24 verdicts de Félix
# ---------------------------------------------------------------------------


def j3(cur: dict) -> dict:
    y = {p.name[:-5] for p in AIDES.glob("*.yaml")}
    e = {p.name[:-11] for p in AIDES.glob("*.yaml.echec")}
    eo = e - y
    nat = Counter()
    for s in eo:
        v = cur.get(s)
        nat["hors_file" if v is None else f"{statut(v)}|{famille(v.get('motif_ignore'))}"] += 1
    doublons = sum(n for k, n in nat.items() if k.endswith("|doublon"))
    echecs = sum(n for k, n in nat.items() if k.startswith("echec|"))
    return {
        "yaml": len(y),
        "yaml_echec": len(e),
        "deux_formes": len(y & e),
        "gardees": len(y - e),
        "gardees_dans_file": sum(1 for s in y - e if s in cur),
        "echec_seul": len(eo),
        "echec_seul_par_nature": dict(nat),
        "ecartees": len(eo) - doublons - echecs,
    }


VERDICTS_FELIX = [
    "non",
    "oui",
    "oui",
    "non",
    "non",
    "oui",
    "oui",
    "oui",
    "non",
    "oui",
    "non",
    "oui",
    "oui",
    "oui",
    "oui",
    "oui",
    "non",
    "oui",
    "oui",
    "oui",
    "non",
    "non",
    "oui",
    "oui",
]


def verdicts_felix(cur: dict) -> dict:
    """Les 24 « à regarder » du 2026-09-30, dans l'ordre du fichier, face aux verdicts de Félix.

    Verdicts recopiés du journal afbc9d8a, 2026-09-30T07:43:59Z.
    """
    texte = (REVIEWS / "2026-09-30-proposition-tri.md").read_text(encoding="utf-8")
    section = texte.split("## À REGARDER (24)")[1].split("## GARDER")[0]
    slugs = re.findall(r"^\| `([^`]+)`", section, re.M)
    requal = (REVIEWS / "2026-10-04-requalification-jev.md").read_text(encoding="utf-8")
    b2 = set(re.findall(r"^\| `([^`]+)`", requal.split("### B2.")[1].split("### B3.")[0], re.M))
    b1 = set(re.findall(r"^\| `([^`]+)`", requal.split("### B1.")[1].split("### B2.")[0], re.M))
    b3 = set(re.findall(r"^\| `([^`]+)`", requal.split("### B3.")[1], re.M))
    a1 = set(re.findall(r"^\| `([^`]+)`", requal.split("### A1.")[1].split("### A2.")[0], re.M))
    lignes = []
    for s, d in zip(slugs, VERDICTS_FELIX, strict=True):
        lignes.append(
            {
                "slug": s,
                "felix": d,
                "yaml": (AIDES / f"{s}.yaml").exists(),
                "yaml_echec": (AIDES / f"{s}.yaml.echec").exists(),
                "statut": statut(cur.get(s, {})),
                "B2_rouvrir": s in b2,
                "B3_doute": s in b3,
            }
        )
    non = [x for x in lignes if x["felix"] == "non"]
    return {
        "lignes": lignes,
        "non": len(non),
        "non_retournes_B2": sum(x["B2_rouvrir"] for x in non),
        "non_en_B3": sum(x["B3_doute"] for x in non),
        "requalification": {"B1": len(b1), "B2": len(b2), "B3": len(b3), "A1": len(a1)},
    }


# ---------------------------------------------------------------------------
# 4. Veille et fiches
# ---------------------------------------------------------------------------


def veille() -> dict:
    versions = git("log", "--all", "--format=%h", "--", "data/veille-state.yaml").split()
    acks = {
        c: git("show", f"{c}:backend/data/veille-state.yaml").count("\n  ack:") for c in versions
    }
    d = yaml.load((BACKEND / "data/veille-state.yaml").read_text(encoding="utf-8"), Loader=CHARGEUR)
    return {
        "versions_git": len(versions),
        "ack_par_version": acks,
        "entrees": len(d),
        "statuts": dict(Counter(v.get("status") for v in d.values())),
        "maj_refusee": sum(1 for v in d.values() if v.get("maj_refusee")),
    }


def fiches() -> dict:
    fs = git("ls-files", "data/reviews").split()
    ing = [f for f in fs if re.match(r"data/reviews/\d{4}-\d\d-\d\d-ingest-.*\.md$", f)]

    def sem(f: str) -> str:
        y, w, _ = date.fromisoformat(f.split("/")[-1][:10]).isocalendar()
        return f"{y}-W{w:02d}"

    par = Counter(sem(f) for f in ing)
    return {
        "fiches_ingestion": len(ing),
        "par_semaine": dict(sorted(par.items())),
        "W37_W40": sum(v for k, v in par.items() if "2026-W37" <= k <= "2026-W40"),
    }


# ---------------------------------------------------------------------------
# 5. Journaux de session : épisodes, enveloppe, chevauchement
# ---------------------------------------------------------------------------

EXCLUS = (
    "<task-notification>",
    "<command-",
    "<local-command",
    "This session is being continued",
    "[Request interrupted",
    "Caveat:",
    "Base directory for this skill",
    "Continue from where you left off",
    "Your response above was cut off",
    "<system-reminder>",
)
MOTS_PIPELINE = re.compile(
    r"prospecter\.py|ingerer\.py|balayage\.py|veille_aides\.py|dedoublonner_aides\.py|"
    r"fusionner_faits\.py|retyper_faits\.py|requalif|file-attente\.yaml|facts_pending|"
    r"ingest-aide|typer-aides|lint_aides_data\.py|rediger_fiches\.py"
)
#: Le même motif SANS le lint, qui tourne dans toute session qui touche un YAML d'aide.
MOTS_PIPELINE_STRICT = re.compile(
    r"prospecter\.py|ingerer\.py|balayage\.py|veille_aides\.py|file-attente\.yaml|facts_pending"
)

EPISODES = [
    ("7512812b", "2026-09-17T14:06", "2026-09-17T16:10"),
    ("0d752ad2", "2026-09-22T07:00", "2026-09-22T10:10"),
    ("0b9a25af", "2026-09-23T20:37", "2026-09-23T20:47"),
    ("afbc9d8a", "2026-09-30T07:22", "2026-09-30T07:44"),
    ("d6fb7845", "2026-10-04T12:02", "2026-10-04T13:00"),
    ("d2ecd4a8", "2026-10-04T17:17", "2026-10-04T17:22"),
    ("e63976a4", "2026-10-07T10:20", "2026-10-07T10:48"),
]
#: Épisodes de décision que la note ne retient pas, relevés à la lecture.
EPISODES_OMIS = [
    ("afbc9d8a", "2026-09-30T07:58", "2026-09-30T09:04", "74 faits en attente arbitrés par Claude"),
    (
        "4a7b8f48",
        "2026-10-02T19:30",
        "2026-10-02T20:33",
        "8 aides Grand Est culture en .yaml.echec",
    ),
]


def ts(x: str) -> datetime:
    return datetime.fromisoformat(x.replace("Z", "+00:00"))


def lire_session(f: Path) -> tuple[list[tuple[str, str]], bool, bool]:
    ev: list[tuple[str, str]] = []
    large = strict = False
    with f.open(encoding="utf-8", errors="replace") as fh:
        for brut in fh:
            try:
                o = json.loads(brut)
            except json.JSONDecodeError:
                continue
            if o.get("isSidechain") or o.get("isMeta"):
                continue
            m = o.get("message")
            t = o.get("type")
            if t not in ("user", "assistant") or not isinstance(m, dict) or not o.get("timestamp"):
                continue
            c = m.get("content")
            if t == "assistant":
                for b in c if isinstance(c, list) else []:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        j = json.dumps(b.get("input"), ensure_ascii=False)
                        large |= bool(MOTS_PIPELINE.search(j))
                        strict |= bool(MOTS_PIPELINE_STRICT.search(j))
                ev.append((o["timestamp"], "A"))
                continue
            if isinstance(c, list):
                if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
                    continue
                c = " ".join(
                    b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"
                )
            if not isinstance(c, str):
                continue
            c = re.sub(
                r"<(ide_opened_file|ide_selection|system-reminder)>.*?</\1>", "", c, flags=re.S
            ).strip()
            if not c or c.startswith(EXCLUS):
                continue
            large |= bool(MOTS_PIPELINE.search(c))
            strict |= bool(MOTS_PIPELINE_STRICT.search(c))
            ev.append((o["timestamp"], "F"))
    ev.sort()
    return ev, large, strict


def latences(ev: list[tuple[str, str]]) -> list[tuple[str, float | None]]:
    out = []
    dernier = None
    for t, k in ev:
        if k == "A":
            dernier = t
            continue
        out.append((t, (ts(t) - ts(dernier)).total_seconds() / 60 if dernier else None))
    return out


def union_minutes(intervalles: list[tuple[datetime, datetime]]) -> float:
    total = 0.0
    fin_cour = None
    deb_cour = None
    for d, f in sorted(intervalles):
        if fin_cour is None or d > fin_cour:
            if fin_cour is not None:
                total += (fin_cour - deb_cour).total_seconds() / 60
            deb_cour, fin_cour = d, f
        else:
            fin_cour = max(fin_cour, f)
    if fin_cour is not None:
        total += (fin_cour - deb_cour).total_seconds() / 60
    return total


def semaine(t: str) -> str:
    y, w, _ = ts(t).isocalendar()
    return f"{y}-W{w:02d}"


def journaux() -> dict:
    fichiers = {
        f.stem: f
        for f in JOURNAUX.glob("-Users-felixollivier-monumia*/*.jsonl")
        if f.stem != SESSION_COURANTE
    }
    sessions = {sid: lire_session(f) for sid, f in fichiers.items()}

    def episode(sid8: str, d: str, f: str) -> dict:
        sid = next(s for s in sessions if s.startswith(sid8))
        lat = [x for t, x in latences(sessions[sid][0]) if d <= t[:16] <= f]
        vals = [x for x in lat if x is not None]
        return {
            "messages_felix": len(lat),
            "min_plafond15": round(sum(min(x, 15) for x in vals), 1),
            "min_plafond5": round(sum(min(x, 5) for x in vals), 1),
            "latence_brute_max": round(max(vals), 1) if vals else None,
        }

    epi = {f"{s}:{d}": episode(s, d, f) for s, d, f in EPISODES}
    omis = {f"{s}:{d} {q}": episode(s, d, f) for s, d, f, q in EPISODES_OMIS}

    # Enveloppe : somme par session (méthode de la note) contre union des intervalles.
    env: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    inter: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    for ev, large, strict in sessions.values():
        for t, x in latences(ev):
            if x is None or t < "2026-08-01":
                continue
            w = semaine(t)
            for cle, ok in (("large", large), ("strict", strict)):
                if not ok:
                    continue
                env[w][f"{cle}_messages"] += 1
                for p in (5, 15):
                    env[w][f"{cle}_somme_p{p}"] += min(x, p)
                    inter[f"{w}|{cle}"][p].append((ts(t) - timedelta(minutes=min(x, p)), ts(t)))
    for cle, par_p in inter.items():
        w, sorte = cle.split("|")
        for p, ivs in par_p.items():
            env[w][f"{sorte}_union_p{p}"] = union_minutes(ivs)
    env_r = {w: {k: round(v, 1) for k, v in sorted(d.items())} for w, d in sorted(env.items())}
    fen = [w for w in env_r if "2026-W37" <= w <= "2026-W40"]
    moy = {
        k: round(sum(env_r[w].get(k, 0) for w in fen) / len(fen), 1)
        for k in (
            "large_messages",
            "large_somme_p5",
            "large_somme_p15",
            "large_union_p5",
            "large_union_p15",
            "strict_messages",
            "strict_somme_p5",
            "strict_somme_p15",
            "strict_union_p5",
            "strict_union_p15",
        )
    }
    return {
        "episodes": epi,
        "episodes_omis": omis,
        "enveloppe_par_semaine": env_r,
        "moyenne_W37_W40": moy,
    }


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    cur = yaml.load(
        (BACKEND / "data/prospection/file-attente.yaml").read_text(encoding="utf-8"),
        Loader=CHARGEUR,
    )
    V = {c: version(c) for c in COMMITS}
    resultats = {
        "etat_file": etat_file(cur, V),
        "promotions": promotions(cur, V),
        "lot_2026_10_04": lot_2026_10_04(),
        "ingerees_puis_ecartees": ingerees_puis_ecartees(cur),
        "transitions": transitions(V),
        "reouvertures": reouvertures(V),
        "ingere_sans_yaml": ingere_sans_yaml(cur),
        "j3": j3(cur),
        "verdicts_felix_2026_09_30": verdicts_felix(cur),
        "veille": veille(),
        "fiches": fiches(),
    }
    for nom, obj in resultats.items():
        ecrire(f"{nom}.json", obj)
    jr = journaux()
    ecrire("journaux.json", jr)
    resume = {
        k: v for k, v in resultats.items() if k not in ("reouvertures", "verdicts_felix_2026_09_30")
    }
    resume["journaux_moyenne_W37_W40"] = jr["moyenne_W37_W40"]
    resume["episodes"] = jr["episodes"]
    resume["episodes_omis"] = jr["episodes_omis"]
    print(json.dumps(resume, ensure_ascii=False, indent=1, default=str))
    print(f"\nSorties : {SORTIE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
