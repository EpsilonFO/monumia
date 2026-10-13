"""Mesures du tri sur titre (étage 2 de la prospection). Lecture seule, zéro réseau, zéro modèle.

    cd backend && uv run python scripts/mesures/tri_titre.py

Lit, sans rien y écrire :
  - les fiches de prospection `data/reviews/*-prospection-*.md` de ce worktree ;
  - les intermédiaires `data/prospection/<territoire>/{candidats,tri,lectures}.jsonl`
    du checkout principal, du worktree `prospection` et de l'historique git de ce
    worktree (sept dossiers régionaux suivis par git) ;
  - `data/prospection/file-attente.yaml`, `data/aides/*.yaml` et `*.yaml.echec` ;
  - `data/reviews/logs/refonte-entrees/d6fb7845-jev-reel-2026-10-04/` (983 titres,
    294 pages, 1 038 titres du banc) et le cache `logs/benchmark-destinataire/jev.jsonl`.

Écrit dans `data/reviews/logs/refonte/2026-10-10-tri-titre-1/` :
  - `rapport.txt` : tout ce que la note cite, section par section ;
  - `fiches.json` : comptes par fiche de prospection (format, à trier, écartées au
    tri, douteuses, lues, requalifiées) ;
  - `versions.json` : chaque version distincte d'un `tri.jsonl`, ses comptes et la
    fiche qu'elle a produite ;
  - `memoire.json` : devenir des URL écartées au tri d'un passage au suivant ;
  - `reel_983.json` : croisement GLM, Jev sur titre et Jev sur page ;
  - `echantillon_controle.jsonl` et `echantillon_meta.json` : les 100 URL écartées
    tirées pour le contrôle humain, la graine, les strates, les hôtes ;
  - `leurres.jsonl` : 50 URL gardées au même tri, à mêler aux écartées ;
  - `lot_aveugle.jsonl` : les 150 URL dans un ordre mélangé, sous un identifiant neutre.

Lit aussi `data/prospection/territoires.yaml` et le catalogue pour estimer, sans
l'appeler, le coût d'un nouveau passage du tri (section 8 du rapport).
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

BACKEND = Path(__file__).resolve().parent.parent.parent
WT = BACKEND.parent
sys.path[:0] = [str(BACKEND / "scripts"), str(BACKEND)]

from prospection.collecte import cle_fiche, est_document  # noqa: E402
from prospection.lecture import LectureFiche  # noqa: E402
from prospection.tri import MOTIF_SANS_TITRE  # noqa: E402

MAIN = Path("/Users/felixollivier/monumia")
WT_PROSPECTION = MAIN / ".claude" / "worktrees" / "prospection"
REVIEWS = BACKEND / "data" / "reviews"
ENTREES = REVIEWS / "logs" / "refonte-entrees" / "d6fb7845-jev-reel-2026-10-04"
CACHE_BANC = REVIEWS / "logs" / "benchmark-destinataire" / "jev.jsonl"
SORTIE = REVIEWS / "logs" / "refonte" / "2026-10-10-tri-titre-1"

# Emplacements des intermédiaires, du plus ancien au plus récent par convention.
EMPLACEMENTS = {
    "principal": MAIN / "backend" / "data" / "prospection",
    "wt-prospection": WT_PROSPECTION / "backend" / "data" / "prospection",
}
REGIONS_SUIVIES = (
    "bretagne",
    "centre-val-de-loire",
    "grand-est",
    "hauts-de-france",
    "normandie",
    "occitanie",
    "pays-de-la-loire",
)
# Les 15 départements de la mesure du 2026-10-04 (tri_reel.py:36).
DEPTS_983 = [
    "02",
    "59",
    "60",
    "62",
    "80",
    "14",
    "50",
    "61",
    "76",
    "22",
    "44",
    "49",
    "53",
    "72",
    "85",
]
SEUILS_TITRE = (0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30)
GRAINE = 20261010
TAILLE_ECHANTILLON = 100
TAILLE_LEURRES = 50
# Moselle (57) du 2026-09-18 : 24 185 candidates nées d'un chemin qui tourne en
# rond (collecte.py, bloc « A3 »), sans fiche. Hors du tirage, compté à part.
EXCLUS_TIRAGE = {"57"}

URL_RE = re.compile(r"https?://[^\s|)>\]]+")
_rapport: list[str] = []


def dire(texte: str = "") -> None:
    _rapport.append(texte)
    print(texte)


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def taux(k: int, n: int) -> str:
    if n == 0:
        return f"{k}/0"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f} % [IC95 {100 * lo:.1f} ; {100 * hi:.1f}]"


def taux_dict(k: int, n: int) -> dict[str, Any]:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "p": (k / n if n else None), "ic95": [lo, hi]}


def jsonl(contenu: str) -> list[dict[str, Any]]:
    return [json.loads(li) for li in contenu.splitlines() if li.strip()]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(WT), *args], capture_output=True, text=True, check=False
    ).stdout


def ecrire_json(nom: str, donnees: Any) -> None:
    (SORTIE / nom).write_text(
        json.dumps(donnees, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------
# 1. Fiches de prospection
# --------------------------------------------------------------------------


def _sections(texte: str) -> dict[str, list[str]]:
    sortie: dict[str, list[str]] = {}
    courant = ""
    for ligne in texte.splitlines():
        if ligne.startswith("## "):
            courant = ligne[3:].strip()
            sortie[courant] = []
        elif courant:
            sortie[courant].append(ligne)
    return sortie


def _premiere_url(ligne: str) -> str | None:
    m = URL_RE.search(ligne)
    return m.group(0).rstrip(".,;") if m else None


def lire_fiche(chemin: Path) -> dict[str, Any] | None:
    m = re.match(r"(\d{4}-\d{2}-\d{2})-prospection-(.+)\.md$", chemin.name)
    if not m:
        return None
    jour, cle = m.groups()
    texte = chemin.read_text(encoding="utf-8")
    pipeline = "Fiche produite par `scripts/prospecter.py`" in texte
    secs = _sections(texte)
    nouveau = "Écartées au tri, sans ouvrir la page" in secs
    f: dict[str, Any] = {
        "fiche": str(chemin.relative_to(WT)),
        "date": jour,
        "territoire": cle,
        "pipeline": pipeline,
        "format": ("nouveau" if nouveau else "ancien") if pipeline else "manuel",
    }
    if not pipeline:
        return f
    retenues = [
        _premiere_url(li.split("|")[3])
        for li in secs.get("Candidates retenues", [])
        if re.match(r"^\| \d+ \|", li)
    ]
    a_trancher, ecart_test, ecart_tri = [], [], []
    if nouveau:
        for li in secs.get("À trancher à la main (destinataire ou objet indéterminé)", []):
            if li.startswith("- `"):
                a_trancher.append(_premiere_url(li))
        for li in secs.get("Écartées par le test du destinataire", []):
            if li.startswith("- ["):
                ecart_test.append(_premiere_url(li))
        for li in secs.get("Écartées au tri, sans ouvrir la page", []):
            if li.startswith("- http"):
                ecart_tri.append(li[2:].split(" \u2014 ")[0].strip())
    else:
        for li in secs.get("Écartées (et pourquoi)", []):
            if li.startswith("- **"):
                ecart_test.append(_premiere_url(li))
            elif li.startswith("- http"):
                ecart_tri.append(li[2:].split(" \u2014 ")[0].strip())
    notes = secs.get("Notes techniques", [])
    non_lues = [_premiere_url(li) for li in notes if li.startswith("- non lue : ")]
    en_file = [_premiere_url(li) for li in notes if li.startswith("- déjà en file d'attente")]
    au_catalogue = [_premiere_url(li) for li in notes if li.startswith("- déjà au catalogue : ")]
    douteuses = requalifiees = 0
    a_trier_note = None
    appels = None
    for li in notes:
        if mm := re.match(r"^- (\d+) candidate\(s\) douteuse\(s\) au tri", li):
            douteuses = int(mm.group(1))
        if mm := re.match(r"^- (\d+) élimination\(s\) prise\(s\) sans titre", li):
            requalifiees = int(mm.group(1))
        if mm := re.search(r"(\d+) URL de fiche trouvées.*?(\d+) à trier", li):
            a_trier_note = int(mm.group(2))
        if mm := re.search(r"coût du passage : (\d+) appel", li):
            appels = int(mm.group(1))
    lues = len(retenues) + len(a_trancher) + len(ecart_test) + len(non_lues)
    f.update(
        {
            "rejoue": any("rejoué depuis candidats.jsonl" in li for li in notes),
            "plafonnee": "Balayage plafonné" in texte,
            "retenues": retenues,
            "a_trancher": a_trancher,
            "ecartees_test": ecart_test,
            "non_lues": non_lues,
            "ecartees_tri": ecart_tri,
            "en_file": en_file,
            "au_catalogue": au_catalogue,
            "n_lues": lues,
            "n_ecartees_tri": len(ecart_tri),
            "n_douteuses": douteuses,
            "n_retenir_tri": lues - douteuses,
            "n_requalifiees": requalifiees,
            "n_a_trier": lues + len(ecart_tri),
            "n_a_trier_note": a_trier_note,
            "appels": appels,
        }
    )
    return f


def fiches() -> list[dict[str, Any]]:
    sortie = []
    for chemin in sorted(REVIEWS.glob("*-prospection-*.md")):
        f = lire_fiche(chemin)
        if f is not None:
            sortie.append(f)
    return sortie


def vague(jour: str) -> str:
    if jour <= "2026-09-07":
        return "2026-09-04..07 (skill, à la main)"
    if jour <= "2026-09-14":
        return "2026-09-08..14 (prospecter.py, premières régions)"
    if jour <= "2026-09-18":
        return "2026-09-17..18 (balayage du 2026-09-18)"
    if jour <= "2026-09-29":
        return "2026-09-28..29 (balayage du 2026-09-29)"
    return "2026-10-04 (18 départements + Occitanie)"


def section_volumes(fs: list[dict[str, Any]]) -> None:
    dire("=" * 78)
    dire("1. VOLUMES PAR FICHE ET PAR VAGUE (source : data/reviews/*-prospection-*.md)")
    dire("=" * 78)
    par_format = Counter(f["format"] for f in fs)
    dire(f"fiches : {len(fs)} ; formats : {dict(par_format)}")
    pipe = [f for f in fs if f["pipeline"]]
    ecart_note = [f for f in pipe if f["n_a_trier_note"] is not None]
    concordes = sum(1 for f in ecart_note if f["n_a_trier_note"] == f["n_a_trier"])
    dire(
        f"contrôle : « à trier » de la note de collecte = lues + écartées au tri dans "
        f"{concordes}/{len(ecart_note)} fiches qui portent la note"
    )
    for f in ecart_note:
        if f["n_a_trier_note"] != f["n_a_trier"]:
            dire(
                f"  écart {f['fiche']} : note {f['n_a_trier_note']} contre "
                f"{f['n_a_trier']} recomptées"
            )
    dire("")
    dire(
        f"{'vague':<52} {'fich':>4} {'à trier':>7} {'écart.':>6} {'dout.':>6} "
        f"{'ret.':>5} {'requal':>6} {'rejouées':>8}"
    )
    agg: dict[str, Counter] = defaultdict(Counter)
    for f in pipe:
        v = vague(f["date"])
        a = agg[v]
        a["fiches"] += 1
        a["a_trier"] += f["n_a_trier"]
        a["ecartees_tri"] += f["n_ecartees_tri"]
        a["douteuses"] += f["n_douteuses"]
        a["retenir_tri"] += f["n_retenir_tri"]
        a["requalifiees"] += f["n_requalifiees"]
        a["rejouees"] += int(f["rejoue"])
        a["lues"] += f["n_lues"]
        a["retenues_lecture"] += len(f["retenues"])
    total = Counter()
    for v in sorted(agg):
        a = agg[v]
        total.update(a)
        dire(
            f"{v:<52} {a['fiches']:>4} {a['a_trier']:>7} {a['ecartees_tri']:>6} "
            f"{a['douteuses']:>6} {a['retenir_tri']:>5} {a['requalifiees']:>6} {a['rejouees']:>8}"
        )
    dire(
        f"{'TOTAL fiches produites par prospecter.py':<52} {total['fiches']:>4} "
        f"{total['a_trier']:>7} {total['ecartees_tri']:>6} {total['douteuses']:>6} "
        f"{total['retenir_tri']:>5} {total['requalifiees']:>6} {total['rejouees']:>8}"
    )
    dire("")
    dire("Part écartée au tri sans ouvrir la page, par vague :")
    for v in sorted(agg):
        a = agg[v]
        dire(f"  {v:<52} {taux(a['ecartees_tri'], a['a_trier'])}")
    dire(f"  {'toutes fiches pipeline':<52} {taux(total['ecartees_tri'], total['a_trier'])}")
    hors_rejeu = [f for f in pipe if not f["rejoue"]]
    k = sum(f["n_ecartees_tri"] for f in hors_rejeu)
    n = sum(f["n_a_trier"] for f in hors_rejeu)
    dire(f"  {'fiches non rejouées seulement':<52} {taux(k, n)}")
    dire(
        "  (les fiches d'une même vague ne sont pas indépendantes : un territoire pèse "
        "son volume ; l'IC est indicatif)"
    )
    dire("")
    dire("Par territoire et par fiche : voir fiches.json (champs n_*).")
    ecrire_json(
        "fiches.json",
        [
            {
                k: v
                for k, v in f.items()
                if k
                not in (
                    "retenues",
                    "a_trancher",
                    "ecartees_test",
                    "non_lues",
                    "ecartees_tri",
                    "en_file",
                    "au_catalogue",
                )
            }
            | {"vague": vague(f["date"])}
            for f in fs
        ],
    )


# --------------------------------------------------------------------------
# 2. Versions des intermédiaires
# --------------------------------------------------------------------------


def _lire_version_fs(dossier: Path) -> dict[str, Any] | None:
    tri = dossier / "tri.jsonl"
    if not tri.is_file():
        return None
    brut = tri.read_text(encoding="utf-8")
    cand = dossier / "candidats.jsonl"
    lec = dossier / "lectures.jsonl"
    return {
        "brut": brut,
        "tries": jsonl(brut),
        "candidats": jsonl(cand.read_text(encoding="utf-8")) if cand.is_file() else [],
        "lectures": jsonl(lec.read_text(encoding="utf-8")) if lec.is_file() else [],
        "date": datetime.fromtimestamp(tri.stat().st_mtime).strftime("%Y-%m-%dT%H:%M"),
    }


def versions(fs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}

    def ajouter(territoire: str, source: str, v: dict[str, Any]) -> None:
        sha = hashlib.sha1(v["brut"].encode()).hexdigest()[:10]
        if not v["tries"]:
            return
        if sha in out:
            out[sha]["sources"].append(f"{source} ({v['date']})")
            out[sha]["date_min"] = min(out[sha]["date_min"], v["date"])
            return
        out[sha] = {
            "sha": sha,
            "territoire": territoire,
            "sources": [f"{source} ({v['date']})"],
            "date_min": v["date"],
            "tries": v["tries"],
            "candidats": v["candidats"],
            "lectures": v["lectures"],
        }

    commits = [
        li.split()
        for li in git(
            "log",
            "--all",
            "--format=%h %ad",
            "--date=format:%Y-%m-%dT%H:%M",
            "--",
            "backend/data/prospection/*/tri.jsonl",
        ).splitlines()
        if li.strip()
    ]
    for h, d in reversed(commits):
        for t in REGIONS_SUIVIES:
            base = f"backend/data/prospection/{t}"
            brut = git("show", f"{h}:{base}/tri.jsonl")
            if not brut.strip():
                continue
            ajouter(
                t,
                f"git {h}",
                {
                    "brut": brut,
                    "tries": jsonl(brut),
                    "candidats": jsonl(git("show", f"{h}:{base}/candidats.jsonl")),
                    "lectures": jsonl(git("show", f"{h}:{base}/lectures.jsonl")),
                    "date": d,
                },
            )
    for nom, base in EMPLACEMENTS.items():
        for dossier in sorted(p for p in base.iterdir() if p.is_dir()):
            v = _lire_version_fs(dossier)
            if v is not None:
                ajouter(dossier.name, nom, v)

    # Rattacher chaque version aux fiches qu'elle a produites : même ensemble
    # d'URL écartées au tri (indice de Jaccard sur cle_fiche).
    par_terr: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in fs:
        if f["pipeline"]:
            par_terr[f["territoire"]].append(f)
    for v in out.values():
        ecart = {cle_fiche(t["url"]) for t in v["tries"] if t["decision"] == "ecarter"}
        tous = {cle_fiche(t["url"]) for t in v["tries"]}
        rattachees = []
        for f in par_terr.get(v["territoire"], []):
            fe = {cle_fiche(u) for u in f["ecartees_tri"]}
            union = ecart | fe
            j = len(ecart & fe) / len(union) if union else 1.0
            lues_f = {
                cle_fiche(u)
                for u in f["retenues"] + f["a_trancher"] + f["ecartees_test"] + f["non_lues"]
                if u
            }
            couvre = len((fe | lues_f) & tous) / len(fe | lues_f) if (fe | lues_f) else 0.0
            if j >= 0.9 and couvre >= 0.9:
                rattachees.append({"fiche": f["fiche"], "jaccard": round(j, 3)})
        v["fiches"] = rattachees
        v["date_balayage"] = max(
            [Path(r["fiche"]).name[:10] for r in rattachees], default=v["date_min"][:10]
        )
    return out


def _texte_hors_balisage(extrait: str) -> str:
    """Le texte d'un extrait markdown une fois retirés liens, crochets et puces."""
    return re.sub(r"\]\([^)]*\)|[\[\]*_#>!-]", " ", extrait).strip()


def compter_version(v: dict[str, Any]) -> dict[str, Any]:
    dec = Counter(t["decision"] for t in v["tries"])
    cand = {c["url"]: c for c in v["candidats"]}
    sans_info = sum(
        1
        for t in v["tries"]
        if t["url"] in cand
        and not (cand[t["url"]].get("titre") or "").strip()
        and not (cand[t["url"]].get("extrait") or "").strip()
    )
    sans_titre = sum(
        1
        for t in v["tries"]
        if t["url"] in cand and not (cand[t["url"]].get("titre") or "").strip()
    )
    # Le garde-fou `sans_information` (tri.py) teste `extrait.strip()`. Or
    # l'extrait est la ligne markdown du lien : « [ ](url) » n'est pas vide,
    # alors qu'il n'apporte aucun texte. On compte ces cas à part.
    vides = [
        t
        for t in v["tries"]
        if t["url"] in cand
        and not (cand[t["url"]].get("titre") or "").strip()
        and not _texte_hors_balisage(cand[t["url"]].get("extrait") or "")
    ]
    sans_texte = Counter(t["decision"] for t in vides)
    sans_texte_images = sum(
        1
        for t in vides
        if t["decision"] == "ecarter"
        and re.search(r"\.(jpe?g|png|gif|webp|svg)(\?|$)", t["url"], re.I)
    )
    return {
        "sha": v["sha"],
        "territoire": v["territoire"],
        "sources": v["sources"],
        "sans_titre_ni_texte_par_decision": dict(sans_texte),
        "sans_titre_ni_texte_ecartees_images": sans_texte_images,
        "date_balayage": v["date_balayage"],
        "fiches": v["fiches"],
        "n": len(v["tries"]),
        "decisions": dict(dec),
        "candidats": len(v["candidats"]),
        "tri_hors_candidats": sum(1 for t in v["tries"] if t["url"] not in cand),
        "sans_titre": sans_titre,
        "sans_titre_ni_contexte": sans_info,
        "requalifiees": sum(1 for t in v["tries"] if t["motif"].startswith(MOTIF_SANS_TITRE)),
        "lot_non_trie": sum(1 for t in v["tries"] if t["motif"].startswith("lot non trié")),
        "absente_reponse": sum(
            1 for t in v["tries"] if t["motif"].startswith("absente de la réponse")
        ),
        "deja_catalogue_motif": sum(
            1
            for t in v["tries"]
            if t["decision"] == "ecarter" and "catalogue" in t["motif"].lower()
        ),
        "lectures": len(v["lectures"]),
    }


def derniere_par_territoire(vs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    par: dict[str, dict[str, Any]] = {}
    for v in vs.values():
        t = v["territoire"]
        cle = (v["date_balayage"], v["date_min"])
        if t not in par or cle > (par[t]["date_balayage"], par[t]["date_min"]):
            par[t] = v
    return par


def section_versions(vs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    dire("")
    dire("=" * 78)
    dire("2. INTERMÉDIAIRES : VERSIONS DISTINCTES DE tri.jsonl")
    dire("=" * 78)
    comptes = [compter_version(v) for v in vs.values()]
    dire(
        f"versions distinctes non vides : {len(comptes)} (checkout principal, worktree "
        f"prospection, historique git de {len(REGIONS_SUIVIES)} dossiers régionaux)"
    )
    sans_fiche = [c for c in comptes if not c["fiches"]]
    dire(f"versions sans fiche rattachée : {len(sans_fiche)}")
    for c in sorted(sans_fiche, key=lambda c: c["territoire"]):
        dire(
            f"  {c['territoire']:<26} {c['sha']} n={c['n']:<6} {c['decisions']} "
            f"sources={c['sources'][0]}"
        )
    derniere = derniere_par_territoire(vs)
    dc = [compter_version(v) for v in derniere.values()]
    hors57 = [c for c in dc if c["territoire"] not in EXCLUS_TIRAGE]
    n = sum(c["n"] for c in hors57)
    ec = sum(c["decisions"].get("ecarter", 0) for c in hors57)
    dt = sum(c["decisions"].get("douteux", 0) for c in hors57)
    rt = sum(c["decisions"].get("retenir", 0) for c in hors57)
    dire("")
    dire(
        f"Dernier balayage de chaque territoire : {len(dc)} territoires "
        f"({len(hors57)} hors Moselle)"
    )
    dire(f"  à trier {n} ; écartées {ec} ; douteuses {dt} ; retenues au tri {rt}")
    dire(f"  part écartée sans ouvrir la page (hors Moselle) : {taux(ec, n)}")
    for c in dc:
        if c["territoire"] in EXCLUS_TIRAGE:
            dire(
                f"  Moselle (57), {c['date_balayage']} : {c['n']} lignes, {c['decisions']}, "
                f"fiche : {c['fiches'] or 'aucune'}"
            )
    par_date: dict[str, Counter] = defaultdict(Counter)
    for c in hors57:
        d = par_date[c["date_balayage"]]
        d["territoires"] += 1
        d["n"] += c["n"]
        for k, v in c["decisions"].items():
            d[k] += v
    for jour, d in sorted(par_date.items()):
        dire(
            f"    balayage {jour} : {d['territoires']} territoires, {d['n']} à trier, "
            f"{d['ecarter']} écartées, {d['douteux']} douteuses, {d['retenir']} retenues"
        )
    dire(
        "  par territoire (dernier balayage) : territoire, date, à trier, écartées, douteuses, retenues"
    )
    for c in sorted(hors57, key=lambda c: c["territoire"]):
        dire(
            f"    {c['territoire']:<26} {c['date_balayage']} {c['n']:>5} "
            f"{c['decisions'].get('ecarter', 0):>5} {c['decisions'].get('douteux', 0):>5} "
            f"{c['decisions'].get('retenir', 0):>5}"
        )
    sans_titre = sum(c["sans_titre"] for c in hors57)
    sans_info = sum(c["sans_titre_ni_contexte"] for c in hors57)
    requal = sum(c["requalifiees"] for c in hors57)
    dire(
        f"  sans titre : {sans_titre} ; sans titre ni contexte : {sans_info} ; "
        f"requalifiées en douteux par le code : {requal}"
    )
    st = Counter()
    for c in hors57:
        st.update(c["sans_titre_ni_texte_par_decision"])
    dire(
        f"  sans titre et extrait sans texte hors balisage markdown (garde-fou contourné) : "
        f"{dict(st)}"
    )
    par_t = {
        c["territoire"]: c["sans_titre_ni_texte_par_decision"].get("ecarter", 0)
        for c in hors57
        if c["sans_titre_ni_texte_par_decision"].get("ecarter")
    }
    dire(f"    écartées dans ce cas, par territoire : {par_t}")
    dire(
        "    dont URL d'image (.jpg, .png...) : "
        f"{sum(c['sans_titre_ni_texte_ecartees_images'] for c in hors57)}"
    )
    dire(
        f"  lots non triés (panne) : {sum(c['lot_non_trie'] for c in hors57)} ; "
        f"oubliées par le modèle : {sum(c['absente_reponse'] for c in hors57)} ; "
        f"écarts motivés « catalogue » : {sum(c['deja_catalogue_motif'] for c in hors57)}"
    )
    ecrire_json(
        "versions.json",
        {
            "toutes": sorted(comptes, key=lambda c: (c["territoire"], c["date_balayage"])),
            "derniere_par_territoire": {c["territoire"]: c["sha"] for c in dc},
        },
    )
    return derniere


# --------------------------------------------------------------------------
# 3. Mémoire d'un passage à l'autre
# --------------------------------------------------------------------------


def charger_file() -> dict[str, dict[str, Any]]:
    return yaml.safe_load((BACKEND / "data/prospection/file-attente.yaml").read_text()) or {}


def charger_catalogue() -> dict[str, tuple[str, str]]:
    """cle_fiche(url) → (slug, 'actif' | 'echec')."""
    sortie: dict[str, tuple[str, str]] = {}
    for chemin in sorted((BACKEND / "data/aides").iterdir()):
        if chemin.name.endswith(".yaml"):
            etat, slug = "actif", chemin.name.removesuffix(".yaml")
        elif chemin.name.endswith(".yaml.echec"):
            etat, slug = "echec", chemin.name.removesuffix(".yaml.echec")
        else:
            continue
        try:
            d = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        src = d.get("source") or {}
        for u in (src.get("url_officielle"), src.get("formulaire_url")):
            if u:
                cle = cle_fiche(u)
                if cle not in sortie or etat == "actif":
                    sortie[cle] = (slug, etat)
    return sortie


def section_memoire(
    fs: list[dict[str, Any]], vs: dict[str, dict[str, Any]], file: dict, catalogue: dict
) -> None:
    dire("")
    dire("=" * 78)
    dire("3. MÉMOIRE DES ÉCARTS D'UN BALAYAGE À L'AUTRE")
    dire("=" * 78)
    dire(
        "Code : tri.jsonl est réécrit à chaque passage (prospecter.py:195-197) ; seules "
        "les pages LUES entrent dans la file (fiche.taches, fiche.py:233-289) ; la collecte "
        "ne retire que ce que le catalogue et la file connaissent (collecte.dedoublonner, "
        "collecte.py:685-729). Une URL écartée au tri est donc recollectée et retriée."
    )
    pipe = sorted((f for f in fs if f["pipeline"]), key=lambda f: (f["territoire"], f["date"]))
    par_terr: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in pipe:
        par_terr[f["territoire"]].append(f)
    paires = []
    devenir_total: Counter = Counter()
    devenir_independant: Counter = Counter()
    for t, liste in par_terr.items():
        for a, b in zip(liste, liste[1:], strict=False):
            ea = {cle_fiche(u) for u in a["ecartees_tri"]}
            lues_b = {
                cle_fiche(u)
                for u in b["retenues"] + b["a_trancher"] + b["ecartees_test"] + b["non_lues"]
                if u
            }
            eb = {cle_fiche(u) for u in b["ecartees_tri"]}
            fb = {cle_fiche(u) for u in b["en_file"] if u}
            cb = {cle_fiche(u) for u in b["au_catalogue"] if u}
            dev = Counter()
            for u in ea:
                if u in eb:
                    dev["re-écartée au tri"] += 1
                elif u in lues_b:
                    dev["ouverte (douteuse ou retenue au tri)"] += 1
                elif u in fb:
                    dev["déjà en file, non retriée"] += 1
                elif u in cb:
                    dev["déjà au catalogue, non retriée"] += 1
                else:
                    dev["absente du passage suivant"] += 1
            paires.append(
                {
                    "territoire": t,
                    "avant": a["fiche"],
                    "apres": b["fiche"],
                    "apres_rejoue": b["rejoue"],
                    "ecartees_avant": len(ea),
                    "devenir": dict(dev),
                }
            )
            devenir_total.update(dev)
            if not b["rejoue"]:
                devenir_independant.update(dev)
    dire(f"\nPaires de fiches consécutives d'un même territoire : {len(paires)}")
    for p in paires:
        avant, apres = Path(p["avant"]).name[:10], Path(p["apres"]).name[:10]
        # Ce qui a changé dans la consigne du tri entre les deux passages : le
        # retest n'en est un que si rien n'a bougé.
        p["commits_consigne_entre"] = [
            li
            for li in git(
                "log",
                "--format=%h %ad",
                "--date=short",
                f"--since={avant}T00:00",
                f"--until={apres}T00:00",
                "--",
                "backend/scripts/prospection/tri.py",
                ".claude/skills/prospecter-aides-region/SKILL.md",
            ).splitlines()
            if li.strip()
        ]
        dire(
            f"  {p['territoire']:<26} {avant} → {apres}"
            f"{' (rejouée)' if p['apres_rejoue'] else ''} : "
            f"{p['ecartees_avant']} écartées → {p['devenir']} ; consigne modifiée entre-temps "
            f"par {len(p['commits_consigne_entre'])} commit(s)"
        )
    dire(f"  total : {dict(devenir_total)}")
    dire(f"  sans les passages rejoués : {dict(devenir_independant)}")
    retriees = (
        devenir_independant["re-écartée au tri"]
        + devenir_independant["ouverte (douteuse ou retenue au tri)"]
    )
    dire(
        "  parmi les écartées retriées à un passage suivant non rejoué, part ouverte la "
        f"fois suivante : {taux(devenir_independant['ouverte (douteuse ou retenue au tri)'], retriees)}"
    )

    # Test-retest sur les intermédiaires : deux versions d'un même territoire.
    dire("\nDécisions du tri sur les URL communes à deux versions d'un même territoire :")
    par_t: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for v in vs.values():
        par_t[v["territoire"]].append(v)
    retest = []
    for t, liste in sorted(par_t.items()):
        liste.sort(key=lambda v: (v["date_balayage"], v["date_min"]))
        for a, b in zip(liste, liste[1:], strict=False):
            da = {cle_fiche(x["url"]): x["decision"] for x in a["tries"]}
            db = {cle_fiche(x["url"]): x["decision"] for x in b["tries"]}
            communs = sorted(set(da) & set(db))
            if not communs:
                continue
            croise = Counter(f"{da[u]}→{db[u]}" for u in communs)
            ea = [u for u in communs if da[u] == "ecarter"]
            change = sum(1 for u in ea if db[u] != "ecarter")
            retest.append(
                {
                    "territoire": t,
                    "avant": f"{a['sha']} ({a['date_balayage']})",
                    "apres": f"{b['sha']} ({b['date_balayage']})",
                    "communs": len(communs),
                    "croisement": dict(croise),
                    "ecartees_avant_puis_gardees": taux_dict(change, len(ea)),
                }
            )
            dire(
                f"  {t:<22} {a['sha']} ({a['date_balayage']}) → {b['sha']} "
                f"({b['date_balayage']}) : {len(communs)} communes ; écartées puis gardées "
                f"{taux(change, len(ea))} ; {dict(croise)}"
            )

    # Retour par la file : URL écartée au tri dans une fiche, puis dans la file.
    dire("\nURL écartées au tri dans une fiche, présentes aujourd'hui dans la file :")
    premiere_ecart: dict[str, str] = {}
    for f in pipe:
        for u in f["ecartees_tri"]:
            c = cle_fiche(u)
            premiere_ecart[c] = min(premiere_ecart.get(c, f["date"]), f["date"])
    dire(f"  URL distinctes écartées au tri dans au moins une fiche : {len(premiere_ecart)}")
    nb_fiches_ecart = Counter()
    for f in pipe:
        for c in {cle_fiche(u) for u in f["ecartees_tri"]}:
            nb_fiches_ecart[c] += 1
    dire(
        f"  dont écartées dans au moins deux fiches : "
        f"{sum(1 for v in nb_fiches_ecart.values() if v >= 2)}"
    )
    revenues = []
    for slug, t in file.items():
        if not t.get("url"):
            continue
        c = cle_fiche(t["url"])
        if c in premiere_ecart and str(t.get("ajoute_le") or "") > premiere_ecart[c]:
            cat = catalogue.get(c)
            revenues.append(
                {
                    "slug": slug,
                    "url": t["url"],
                    "ecartee_le": premiere_ecart[c],
                    "ajoute_le": str(t.get("ajoute_le")),
                    "statut": t.get("statut"),
                    "motif_ignore": t.get("motif_ignore"),
                    "catalogue": cat[1] if cat else None,
                    "yaml_actif": (BACKEND / "data/aides" / f"{slug}.yaml").exists(),
                }
            )
    st = Counter(r["statut"] for r in revenues)
    dire(f"  revenues dans la file à un passage ultérieur : {len(revenues)} ; statuts {dict(st)}")
    for jour in sorted({r["ecartee_le"] for r in revenues}):
        sel = [r for r in revenues if r["ecartee_le"] == jour]
        dire(
            f"    écartées au tri le {jour} : {len(sel)} revenues, statuts "
            f"{dict(Counter(r['statut'] for r in sel))}, YAML actif "
            f"{sum(r['yaml_actif'] for r in sel)}"
        )
    actifs = [r for r in revenues if r["yaml_actif"]]
    dire(f"  dont YAML actif au catalogue sous leur slug de file : {len(actifs)}")
    for r in actifs:
        dire(f"    {r['slug']} (écartée au tri le {r['ecartee_le']}, ajoutée le {r['ajoute_le']})")
    ecrire_json(
        "memoire.json",
        {
            "paires_fiches": paires,
            "retest_versions": retest,
            "revenues_dans_la_file": revenues,
        },
    )


# --------------------------------------------------------------------------
# 4. Les 983 titres réels et les 294 pages
# --------------------------------------------------------------------------


def _issue_lecture(le: dict[str, Any] | None) -> str:
    if le is None:
        return "non lue"
    if le.get("erreur") or not le.get("fiche"):
        return "erreur"
    brut = dict(le["fiche"])
    if "destinataire" not in brut:
        # Lecture d'avant le test du destinataire (2026-09-21) : `retenir` était
        # rendu par le modèle.
        return "retenue (ancien format)" if brut.get("retenir") else "non retenue (ancien format)"
    brut.pop("famille", None)  # familles renommées depuis : sans effet sur l'issue
    f = LectureFiche.model_validate(brut)
    if f.retenir:
        return "retenue"
    if f.indeterminee:
        return "indeterminee"
    return "ecartee"


def _bande(r: dict[str, Any], bas: float = 0.12, haut: float = 0.57) -> str:
    from prospection import arbitre

    ecarte = arbitre.structure_ecarte(r["destinataire"] or "", r["objet"] or "", r["dispositif"])
    return arbitre.bande(r["deposable"], ecarte, arbitre.Seuils(bas=bas, haut=haut))


def _moitie(url: str) -> int:
    return int(hashlib.sha256(url.encode()).hexdigest(), 16) % 2


def section_983(file: dict, catalogue: dict) -> None:
    dire("")
    dire("=" * 78)
    dire("4. LES 983 TITRES RÉELS DU 2026-10-04 (15 départements)")
    dire("=" * 78)
    base = EMPLACEMENTS["wt-prospection"]
    jt = {x["url"]: x for x in jsonl((ENTREES / "tri_reel_titres.jsonl").read_text())}
    jp = {x["url"]: x for x in jsonl((ENTREES / "tri_reel_pages.jsonl").read_text())}
    par_url_file = {}
    for slug, t in file.items():
        if t.get("url"):
            par_url_file.setdefault(
                cle_fiche(t["url"]), (slug, t.get("statut"), t.get("motif_ignore"))
            )
    lignes = []
    for d in DEPTS_983:
        tri = {t["url"]: t for t in jsonl((base / d / "tri.jsonl").read_text())}
        lec = {t["url"]: t for t in jsonl((base / d / "lectures.jsonl").read_text())}
        for c in jsonl((base / d / "candidats.jsonl").read_text()):
            u = c["url"]
            fi = par_url_file.get(cle_fiche(u))
            cat = catalogue.get(cle_fiche(u))
            lignes.append(
                {
                    "dept": d,
                    "url": u,
                    "titre": c.get("titre") or "",
                    "via": c.get("trouve_via") or "",
                    "glm": tri[u]["decision"] if u in tri else None,
                    "motif_tri": tri[u]["motif"] if u in tri else None,
                    "jev_titre": jt.get(u),
                    "jev_page": jp.get(u),
                    "lecture": _issue_lecture(lec.get(u)),
                    "jev_lecture": bool(lec.get(u, {}).get("arbitrage")),
                    "file": fi[1] if fi else None,
                    "file_motif": fi[2] if fi else None,
                    "catalogue": cat[1] if cat else None,
                }
            )
    n = len(lignes)
    dire(
        f"candidates : {n} ; jugées par Jev sur titre : {sum(1 for x in lignes if x['jev_titre'])} ;"
        f" pages jugées : {sum(1 for x in lignes if x['jev_page'])}"
    )
    dire(
        f"tri GLM : {dict(Counter(x['glm'] for x in lignes))} ; collecte : {dict(Counter(x['via'] for x in lignes))}"
    )
    dire(
        f"sans titre : {sum(1 for x in lignes if not x['titre'].strip())} ; lectures portant un "
        f"arbitrage de Jev : {sum(1 for x in lignes if x['jev_lecture'])}"
    )
    ecart_glm = sum(1 for x in lignes if x["glm"] == "ecarter")
    dire(f"GLM écarte sans ouvrir la page : {taux(ecart_glm, n)}")
    cout_t = sum((x["jev_titre"] or {}).get("cout_usd") or 0 for x in lignes)
    cout_p = sum((x["jev_page"] or {}).get("cout_usd") or 0 for x in lignes)
    dire(
        f"coût déjà payé le 2026-10-04 (champ cout_usd) : titres {cout_t:.3f} $, pages {cout_p:.3f} $"
    )

    dire("\nGLM (écarter / garder) × Jev sur titre (deposable < seuil = écarte) :")
    dire(
        f"  {'seuil':>6} {'G éc/J éc':>10} {'G éc/J ga':>10} {'G ga/J éc':>10} {'G ga/J ga':>10} {'Jev écarte':>24}"
    )
    croisements = {}
    for s in SEUILS_TITRE:
        c = Counter()
        for x in lignes:
            g = "ec" if x["glm"] == "ecarter" else "ga"
            j = "ec" if x["jev_titre"]["deposable"] < s else "ga"
            c[f"{g}/{j}"] += 1
        croisements[str(s)] = dict(c)
        jec = c["ec/ec"] + c["ga/ec"]
        dire(
            f"  {s:>6.2f} {c['ec/ec']:>10} {c['ec/ga']:>10} {c['ga/ec']:>10} {c['ga/ga']:>10} "
            f"{taux(jec, n):>24}"
        )
    bandes_titre = Counter(_bande(x["jev_titre"]) for x in lignes)
    dire(f"Jev sur titre, bandes de production (0,12 / 0,57 + cohérence) : {dict(bandes_titre)}")
    dep = sorted(x["jev_titre"]["deposable"] for x in lignes)
    dire(
        f"deposable sur titre : min {dep[0]}, médiane {dep[n // 2]}, p90 {dep[int(0.9 * n)]}, max {dep[-1]}"
    )

    dire(
        "\nLes 294 pages : écartées par GLM sur titre et deposable Jev sur titre ≥ 0,10 (tri_reel.py:94)"
    )
    pages = [x for x in lignes if x["jev_page"]]
    assert all(x["glm"] == "ecarter" for x in pages)
    cible = [x for x in lignes if x["glm"] == "ecarter" and x["jev_titre"]["deposable"] >= 0.10]
    dire(f"  population visée {len(cible)}, jugées {len(pages)}")
    bp = Counter(_bande(x["jev_page"]) for x in pages)
    dire(f"  bande de Jev sur la page (0,12 / 0,57) : {dict(bp)}")
    hautes = [x for x in pages if x["jev_page"]["deposable"] >= 0.45]
    dire(f"  deposable page ≥ 0,45 : {len(hautes)} ; bande retenue : {bp['retenue']}")
    dire(f"  part « retenue » par Jev sur page parmi les 294 : {taux(bp['retenue'], len(pages))}")
    dire(f"  part retenue ou milieu : {taux(bp['retenue'] + bp['milieu'], len(pages))}")
    for x in sorted(pages, key=lambda x: -x["jev_page"]["deposable"]):
        if _bande(x["jev_page"]) == "retenue" or x["jev_page"]["deposable"] >= 0.45:
            dire(
                f"    {x['jev_page']['deposable']:.2f} {_bande(x['jev_page']):<8} {x['dept']} "
                f"titre {x['jev_titre']['deposable']:.2f} | {x['titre'][:70]} | {x['url']}"
                f" | file={x['file']} cat={x['catalogue']}"
            )
    non_juges = [x for x in lignes if x["glm"] == "ecarter" and x["jev_titre"]["deposable"] < 0.10]
    dire(f"  écartées par GLM et par Jev sur titre (< 0,10), jamais ouvertes : {len(non_juges)}")

    dire("\nLes 332 gardées par GLM (retenir + douteux) : issue de la lecture GLM et de la file")
    gardees = [x for x in lignes if x["glm"] in ("retenir", "douteux")]
    dire(f"  issue de lecture : {dict(Counter(x['lecture'] for x in gardees))}")
    dire(f"  statut file aujourd'hui : {dict(Counter(x['file'] for x in gardees))}")
    dire(f"  catalogue aujourd'hui : {dict(Counter(x['catalogue'] for x in gardees))}")
    for g in ("retenir", "douteux"):
        sel = [x for x in gardees if x["glm"] == g]
        k = sum(1 for x in sel if x["lecture"] == "retenue")
        dire(f"  GLM {g} → lecture retenue : {taux(k, len(sel))}")
    sel = [x for x in gardees if x["lecture"] != "erreur"]
    k = sum(1 for x in sel if x["lecture"] == "ecartee")
    dire(f"  gardées au tri puis écartées à la lecture (hors erreurs) : {taux(k, len(sel))}")

    dire(
        "\nJev sur titre écarterait-il des pages que la lecture retient ? (référence : lecture GLM)"
    )
    for s in SEUILS_TITRE:
        ret = [x for x in gardees if x["lecture"] == "retenue"]
        perdues = [x for x in ret if x["jev_titre"]["deposable"] < s]
        dire(f"  seuil {s:.2f} : {taux(len(perdues), len(ret))} des retenues à la lecture")
    s = 0.10
    ret = [x for x in gardees if x["lecture"] == "retenue" and x["jev_titre"]["deposable"] < s]
    for x in ret:
        dire(
            f"    titre {x['jev_titre']['deposable']:.2f} | {x['titre'][:70]} | file={x['file']} cat={x['catalogue']}"
        )

    # Seuil réglé sur une moitié, mesuré sur l'autre. Positifs provisoires :
    # lecture GLM retenue (gardées) ou bande « retenue » de Jev sur la page
    # (écartées). Deux juges-modèles : pas une vérité terrain.
    dire("\nSeuil de Jev sur titre réglé sur une moitié (hash d'URL), mesuré sur l'autre.")
    dire("  positifs provisoires = lecture GLM retenue OU Jev page « retenue » (juges-modèles)")
    pos = {x["url"] for x in lignes if x["lecture"] == "retenue"} | {
        x["url"] for x in pages if _bande(x["jev_page"]) == "retenue"
    }
    cv = []
    for tol in (0.0, 0.02, 0.05, 0.10):
        for app, test in ((0, 1), (1, 0)):
            sp = sorted(
                x["jev_titre"]["deposable"]
                for x in lignes
                if _moitie(x["url"]) == app and x["url"] in pos
            )
            k = int(tol * len(sp))
            seuil = sp[k] if k < len(sp) else 1.0
            tt = [x for x in lignes if _moitie(x["url"]) == test]
            tp = [x for x in tt if x["url"] in pos]
            ecartes = [x for x in tt if x["jev_titre"]["deposable"] < seuil]
            perdus = [x for x in tp if x["jev_titre"]["deposable"] < seuil]
            cv.append(
                {
                    "tolerance": tol,
                    "apprentissage": app,
                    "seuil": seuil,
                    "test_n": len(tt),
                    "test_positifs": len(tp),
                    "ecartes": taux_dict(len(ecartes), len(tt)),
                    "positifs_perdus": taux_dict(len(perdus), len(tp)),
                }
            )
            dire(
                f"  tolérance {tol:.2f}, moitié {app}→{test} : seuil {seuil:.3f} ; écarte "
                f"{taux(len(ecartes), len(tt))} ; positifs perdus {taux(len(perdus), len(tp))}"
            )
    ecrire_json(
        "reel_983.json",
        {
            "lignes": [
                {k: v for k, v in x.items() if k not in ("jev_titre", "jev_page")}
                | {
                    "jev_titre_deposable": x["jev_titre"]["deposable"],
                    "jev_titre_bande": _bande(x["jev_titre"]),
                    "jev_page_deposable": (x["jev_page"] or {}).get("deposable"),
                    "jev_page_bande": _bande(x["jev_page"]) if x["jev_page"] else None,
                }
                for x in lignes
            ],
            "croisements_glm_jev_titre": croisements,
            "validation_croisee": cv,
        },
    )


def section_banc_titre() -> None:
    """jev_titre.jsonl : Jev sur titre contre Jev sur page, au banc étiqueté."""
    dire("")
    dire("=" * 78)
    dire("5. BANC ÉTIQUETÉ : JEV SUR TITRE CONTRE JEV SUR PAGE (jev_titre.jsonl)")
    dire("=" * 78)
    import benchmark_destinataire as banc

    cas = {c.slug: c for c in banc.cas_etiquetes()}
    page = {x["slug"]: x for x in jsonl(CACHE_BANC.read_text())}
    titre = {x["slug"]: x for x in jsonl((ENTREES / "jev_titre.jsonl").read_text())}
    communs = sorted(s for s in titre if s in page and s in cas)
    # Même règle que titre_vs_page.jeu() : le titre de la file s'il existe,
    # sinon le nom du catalogue (plus propre qu'un libellé de lien).
    file = charger_file()
    src = Counter(
        "collecte" if (file.get(s) or {}).get("titre") else "nom du catalogue" for s in communs
    )
    dire(f"source du titre jugé (règle de titre_vs_page.py) : {dict(src)}")
    dire(
        f"titres jugés {len(titre)} ; pages au cache {len(page)} ; cas étiquetés aujourd'hui "
        f"{len(cas)} ; communs {len(communs)}"
    )
    dire(
        "étiquette (benchmark_destinataire.cas_etiquetes, HEAD de ce worktree) : gardée = "
        "YAML dans HEAD ; écartée = .yaml.echec au motif « test du destinataire » ou "
        "« tri humain »"
    )
    dire(
        "écartées par motif : "
        f"{dict(Counter(cas[s].motif.split(' :')[0][:30] for s in communs if not cas[s].garde))}"
        f" ; gardées par origine : "
        f"{dict(Counter(cas[s].origine for s in communs if cas[s].garde))}"
    )
    for nom, filtre in (
        ("tout", lambda s: True),
        ("prospection", lambda s: cas[s].origine == "prospection"),
    ):
        sel = [s for s in communs if filtre(s)]
        g = sum(cas[s].garde for s in sel)
        cp = [(banc.scores_jev(page[s])["deposable"], cas[s].garde) for s in sel]
        ct = [(banc.scores_jev(titre[s])["deposable"], cas[s].garde) for s in sel]
        dire(
            f"  {nom:<12} {len(sel)} cas ({g} gardées, {len(sel) - g} écartées) : AUC deposable "
            f"page {banc.auc(cp):.3f}, titre {banc.auc(ct):.3f}"
        )
        for tol in (0.0, 0.01, 0.02):
            for app in (0, 1):
                a = sorted(
                    banc.scores_jev(titre[s])["deposable"]
                    for s in sel
                    if banc._moitie(s) == app and cas[s].garde
                )
                k = int(tol * len(a))
                seuil = a[k] if k < len(a) else 1.0
                test = [s for s in sel if banc._moitie(s) != app]
                ec = [s for s in test if banc.scores_jev(titre[s])["deposable"] < seuil]
                gt = sum(cas[s].garde for s in test)
                perdues = sum(cas[s].garde for s in ec)
                dire(
                    f"    tol {tol:.2f} moitié {app}: seuil {seuil:.3f} ; écarte "
                    f"{taux(len(ec), len(test))} ; gardées perdues {taux(perdues, gt)} ; "
                    f"écartées attrapées {taux(len(ec) - perdues, len(test) - gt)}"
                )


# --------------------------------------------------------------------------
# 6. Vérité terrain humaine sur une URL écartée au tri
# --------------------------------------------------------------------------


def section_verite(fs: list[dict[str, Any]], vs: dict[str, dict[str, Any]], file: dict) -> None:
    dire("")
    dire("=" * 78)
    dire("6. VÉRITÉ TERRAIN HUMAINE SUR UNE URL ÉCARTÉE AU TRI ?")
    dire("=" * 78)
    ecartees: set[str] = set()
    for f in fs:
        if f["pipeline"]:
            ecartees |= {cle_fiche(u) for u in f["ecartees_tri"]}
    moselle: set[str] = set()
    for v in vs.values():
        e = {cle_fiche(t["url"]) for t in v["tries"] if t["decision"] == "ecarter"}
        if v["territoire"] in EXCLUS_TIRAGE:
            moselle |= e
        else:
            ecartees |= e
    dire(
        f"URL distinctes écartées au tri (fiches + intermédiaires, hors Moselle) : "
        f"{len(ecartees)} ; Moselle seule : {len(moselle)}"
    )
    ecartees |= moselle
    motifs = Counter()
    humains = []
    for slug, t in file.items():
        m = t.get("motif_ignore") or ""
        if "tri humain" in m:
            motifs["tri humain"] += 1
            if t.get("url") and cle_fiche(t["url"]) in ecartees:
                humains.append((slug, t.get("statut"), m[:100]))
        elif m.startswith("test du destinataire"):
            motifs["test du destinataire (requalification validée)"] += 1
        if re.search(r"\btri\b", m) and "tri humain" not in m:
            motifs["autre motif citant « tri »"] += 1
    dire(f"motifs de la file : {dict(motifs)}")
    dire(f"tâches « tri humain » dont l'URL a été écartée au tri un jour : {len(humains)}")
    for h in humains:
        dire(f"  {h}")
    statuts = Counter()
    for t in file.values():
        if t.get("url") and cle_fiche(t["url"]) in ecartees:
            statuts[t.get("statut")] += 1
    dire(f"tâches de la file dont l'URL a été écartée au tri un jour, par statut : {dict(statuts)}")
    log = git("log", "--all", "--format=%h %ad %s", "--date=short", "-i", "-P", r"--grep=\btri\b")
    dire("commits dont le message contient le mot « tri » :")
    for li in log.splitlines():
        dire(f"  {li}")


# --------------------------------------------------------------------------
# 7. Échantillon de contrôle
# --------------------------------------------------------------------------


def _strates(
    derniere: dict[str, dict[str, Any]], decisions: tuple[str, ...]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    strates: dict[str, list[dict[str, Any]]] = {}
    exclus: dict[str, int] = {}
    for t, v in sorted(derniere.items()):
        cand = {c["url"]: c for c in v["candidats"]}
        lec = {le["url"]: le for le in v["lectures"]}
        lot = [
            {
                "url": x["url"],
                "titre": (cand.get(x["url"]) or {}).get("titre", ""),
                "territoire": t,
                "balayage": v["date_balayage"],
                "version_tri": v["sha"],
                "verdict_tri": x["decision"],
                "famille_tri": x.get("famille"),
                "motif_tri": x.get("motif"),
                "issue_lecture": _issue_lecture(lec.get(x["url"]))
                if x["decision"] != "ecarter"
                else None,
            }
            for x in v["tries"]
            if x["decision"] in decisions
        ]
        if t in EXCLUS_TIRAGE:
            exclus[t] = len(lot)
        elif lot:
            strates[t] = lot
    return strates, exclus


def _tirer(
    strates: dict[str, list[dict[str, Any]]], taille: int, rng: random.Random
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Allocation proportionnelle (plus grands restes), tirage sans remise par strate."""
    population = sum(len(s) for s in strates.values())
    quotas = {t: taille * len(s) / population for t, s in strates.items()}
    alloc = {t: int(q) for t, q in quotas.items()}
    reste = taille - sum(alloc.values())
    for t in sorted(quotas, key=lambda t: (-(quotas[t] - alloc[t]), t))[:reste]:
        alloc[t] += 1
    tires = []
    for t in sorted(strates):
        pool = sorted(strates[t], key=lambda x: x["url"])
        for x in rng.sample(pool, alloc[t]):
            tires.append(x | {"poids": len(pool) / alloc[t]})
    return tires, alloc


CHAMPS_ECHANTILLON = (
    "id",
    "id_aveugle",
    "url",
    "titre",
    "territoire",
    "balayage",
    "verdict_tri",
    "famille_tri",
    "motif_tri",
    "issue_lecture",
    "version_tri",
    "poids",
)


def section_echantillon(derniere: dict[str, dict[str, Any]]) -> None:
    dire("")
    dire("=" * 78)
    dire("7. ÉCHANTILLON DE CONTRÔLE : 100 URL ÉCARTÉES AU TRI (+ 50 leurres)")
    dire("=" * 78)
    strates, exclus = _strates(derniere, ("ecarter",))
    population = sum(len(s) for s in strates.values())
    dire(
        f"population : {population} URL écartées au dernier balayage de {len(strates)} "
        f"territoires ; exclus : {exclus} (Moselle, chemin en boucle, sans fiche)"
    )
    rng = random.Random(GRAINE)
    tires, alloc = _tirer(strates, TAILLE_ECHANTILLON, rng)
    for i, x in enumerate(sorted(tires, key=lambda x: (x["territoire"], x["url"])), 1):
        x["id"] = f"T{i:03d}"
    # Leurres : des URL GARDÉES au même tri (douteuses ou retenues), mêlées aux
    # écartées dans le lot d'étiquetage pour que l'étiqueteur ne puisse pas
    # deviner le verdict de la composition du lot. Leur issue de lecture sert
    # aussi de contrôle de l'étiqueteur.
    strates_g, _ = _strates(derniere, ("retenir", "douteux"))
    leurres, _ = _tirer(strates_g, TAILLE_LEURRES, random.Random(GRAINE + 1))
    for i, x in enumerate(sorted(leurres, key=lambda x: (x["territoire"], x["url"])), 1):
        x["id"] = f"G{i:03d}"
    lot = tires + leurres
    random.Random(GRAINE + 2).shuffle(lot)
    for i, x in enumerate(lot, 1):
        x["id_aveugle"] = f"E{i:03d}"
    hotes = Counter(urlsplit(x["url"]).netloc.lower() for x in tires)
    hotes_lot = Counter(urlsplit(x["url"]).netloc.lower() for x in lot)
    docs = sum(1 for x in tires if est_document(x["url"]))
    sans_titre = sum(1 for x in tires if not x["titre"].strip())
    dire(
        f"tirées {len(tires)} ; strates représentées "
        f"{sum(1 for a in alloc.values() if a)}/{len(strates)} ; par balayage "
        f"{dict(sorted(Counter(x['balayage'] for x in tires).items()))}"
    )
    dire(f"hôtes distincts : {len(hotes)} ; les plus chargés : {hotes.most_common(3)}")
    dire(f"documents (pdf, doc...) : {docs} ; sans titre : {sans_titre}")
    dire(
        f"leurres {len(leurres)} : {dict(Counter(x['verdict_tri'] for x in leurres))}, issue de "
        f"lecture {dict(Counter(x['issue_lecture'] for x in leurres))}"
    )
    dire(f"lot d'étiquetage : {len(lot)} URL, {len(hotes_lot)} hôtes distincts")
    # Durée : délai poli d'une seconde par hôte (pipeline/web.py:57) plus un
    # temps de réponse supposé r. Un hôte à la fois : n × (1 + r) ; un fil par
    # hôte : l'hôte le plus chargé fixe la durée.
    for nom, h in (("100 écartées", hotes), ("lot de 150", hotes_lot)):
        for r in (0.5, 2.0):
            n = sum(h.values())
            dire(
                f"  durée {nom}, réponse {r} s : séquentiel {n * (1 + r) / 60:.1f} min ; "
                f"un fil par hôte {max(h.values()) * (1 + r) / 60:.1f} min"
            )

    def ecrire(nom: str, lignes: list[dict[str, Any]], champs: tuple[str, ...]) -> None:
        with (SORTIE / nom).open("w", encoding="utf-8") as fo:
            for x in lignes:
                fo.write(json.dumps({k: x.get(k) for k in champs}, ensure_ascii=False) + "\n")

    ecrire("echantillon_controle.jsonl", sorted(tires, key=lambda x: x["id"]), CHAMPS_ECHANTILLON)
    ecrire("leurres.jsonl", sorted(leurres, key=lambda x: x["id"]), CHAMPS_ECHANTILLON)
    ecrire("lot_aveugle.jsonl", sorted(lot, key=lambda x: x["id_aveugle"]), ("id_aveugle", "url"))
    ecrire_json(
        "echantillon_meta.json",
        {
            "graine": GRAINE,
            "taille": len(tires),
            "leurres": len(leurres),
            "methode": "allocation proportionnelle par territoire (plus grands restes), tirage "
            "sans remise dans chaque strate triée par URL, strates en ordre alphabétique ; "
            "écartées : random.Random(graine) ; leurres (douteux ou retenir du même tri) : "
            "random.Random(graine + 1) ; ordre du lot aveugle : random.Random(graine + 2)",
            "population": population,
            "population_leurres": sum(len(s) for s in strates_g.values()),
            "exclus": exclus,
            "strates": {
                t: {
                    "ecartees": len(s),
                    "tirees": alloc[t],
                    "balayage": s[0]["balayage"],
                    "version_tri": s[0]["version_tri"],
                }
                for t, s in sorted(strates.items())
            },
            "hotes": dict(hotes.most_common()),
            "hotes_lot": dict(hotes_lot.most_common()),
            "documents": docs,
        },
    )


def section_cout(derniere: dict[str, dict[str, Any]]) -> None:
    """Ce que coûterait un nouveau passage du tri (retest), sans l'appeler."""
    dire("")
    dire("=" * 78)
    dire("8. COÛT ESTIMÉ D'UN RETEST DU TRI (aucun appel fait)")
    dire("=" * 78)
    from prospection import tri as tri_mod
    from prospection.collecte import Candidat
    from prospection.territoires import aides_existantes, charger_territoires
    from providall._registry_data import MODELS_DATA

    from aides_schema import load_all_aides

    prix = MODELS_DATA.get("or-glm", {})
    territoires = charger_territoires()
    corpus = load_all_aides()
    CAR_PAR_JETON = 3.5  # hypothèse pour du français, non mesurée ici

    def estimer(cles: list[str]) -> dict[str, float]:
        appels = car_sys = car_lots = car_sortie = 0
        for cle in cles:
            v = derniere.get(cle)
            if v is None or cle not in territoires:
                continue
            systeme = tri_mod.prompt_systeme(
                territoires[cle], aides_existantes(cle, territoires[cle], corpus)
            )
            cand = {c["url"]: c for c in v["candidats"]}
            objets = [
                Candidat(
                    url=t["url"],
                    titre=(cand.get(t["url"]) or {}).get("titre", ""),
                    extrait=(cand.get(t["url"]) or {}).get("extrait", ""),
                )
                for t in v["tries"]
            ]
            for lot in tri_mod.lots(objets):
                appels += 1
                car_sys += len(systeme)
                car_lots += len(tri_mod._rendre_lot(lot))
            car_sortie += sum(len(json.dumps(t, ensure_ascii=False)) for t in v["tries"])
        ji = (car_sys + car_lots) / CAR_PAR_JETON
        jo = car_sortie / CAR_PAR_JETON
        cout = ji / 1e6 * prix.get("price_in", 0) + jo / 1e6 * prix.get("price_out", 0)
        return {
            "appels": appels,
            "car_systeme_moyen": car_sys / appels if appels else 0,
            "jetons_entree": ji,
            "jetons_sortie": jo,
            "cout_usd": cout,
        }

    for nom, cles in (
        ("les 15 départements des 983 titres", DEPTS_983),
        (
            "dernier balayage de tous les territoires hors Moselle",
            [t for t in derniere if t not in EXCLUS_TIRAGE],
        ),
    ):
        e = estimer(cles)
        dire(
            f"  {nom} : {e['appels']} appels, prompt système moyen "
            f"{e['car_systeme_moyen']:.0f} car., ~{e['jetons_entree'] / 1e6:.2f} M jetons "
            f"d'entrée, ~{e['jetons_sortie'] / 1e6:.2f} M de sortie, ~{e['cout_usd']:.2f} $ au "
            f"tarif or-glm ({prix.get('price_in')} / {prix.get('price_out')} $ par M, "
            f"providall/_registry_data.py), {CAR_PAR_JETON} car. par jeton supposés"
        )


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    dire(
        f"tri_titre.py, {datetime.now().isoformat(timespec='seconds')}, HEAD {git('rev-parse', '--short', 'HEAD').strip()}"
    )
    fs = fiches()
    section_volumes(fs)
    vs = versions(fs)
    derniere = section_versions(vs)
    file = charger_file()
    catalogue = charger_catalogue()
    section_memoire(fs, vs, file, catalogue)
    section_983(file, catalogue)
    section_banc_titre()
    section_verite(fs, vs, file)
    section_echantillon(derniere)
    section_cout(derniere)
    (SORTIE / "rapport.txt").write_text("\n".join(_rapport) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
