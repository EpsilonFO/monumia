"""Recomptage adverse de la note docs/refonte-pipeline/notes/tri-titre.md.

Écrit sans relire ni importer `tri_titre.py` (le script du mesureur) : chaque
chiffre est recompté depuis ses sources (fiches, intermédiaires, file, caches
de Jev). Lecture seule, aucun appel réseau ni modèle.

    cd backend && uv run python scripts/mesures/tri_titre_recompte.py

Sorties dans backend/data/reviews/logs/refonte/2026-10-10-tri-titre-recompte-1/.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

import yaml

WT = Path(__file__).resolve().parents[3]
BACKEND = WT / "backend"
REVIEWS = BACKEND / "data" / "reviews"
AIDES = BACKEND / "data" / "aides"
FILE = BACKEND / "data" / "prospection" / "file-attente.yaml"
PRINCIPAL = Path("/Users/felixollivier/monumia/backend/data/prospection")
WT_PROSP = Path(
    "/Users/felixollivier/monumia/.claude/worktrees/prospection/backend/data/prospection"
)
JEV = REVIEWS / "logs" / "refonte-entrees" / "d6fb7845-jev-reel-2026-10-04"
BANC = REVIEWS / "logs" / "benchmark-destinataire"
BALAYAGE_LOGS = REVIEWS / "logs" / "balayage"
SORTIE = REVIEWS / "logs" / "refonte" / "2026-10-10-tri-titre-recompte-1"
MESUREUR = REVIEWS / "logs" / "refonte" / "2026-10-10-tri-titre-1"

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

lignes_rapport: list[str] = []


def dire(*morceaux: object) -> None:
    texte = " ".join(str(m) for m in morceaux)
    print(texte)
    lignes_rapport.append(texte)


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    marge = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - marge), min(1.0, centre + marge))


def taux(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    p = 100 * k / n if n else float("nan")
    return f"{k}/{n} = {p:.1f} % [{100 * lo:.1f} ; {100 * hi:.1f}]"


def jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(li) for li in p.read_text(encoding="utf-8").splitlines() if li.strip()]


def jsonl_texte(t: str) -> list[dict]:
    return [json.loads(li) for li in t.splitlines() if li.strip()]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(WT), *args], capture_output=True, text=True, check=True
    ).stdout


def norm(url: str) -> str:
    """Clé de comparaison grossière : sans schéma, sans www, sans slash final."""
    u = url.strip().split("#")[0]
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u.rstrip("/")


# --------------------------------------------------------------------------
# 1. Fiches
# --------------------------------------------------------------------------
RE_URL = re.compile(r"https?://\S+")


def sections(md: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    courant = None
    for li in md.splitlines():
        if li.startswith("## "):
            courant = li[3:].strip()
            out[courant] = []
        elif courant is not None:
            out[courant].append(li)
    return out


def lire_fiche(p: Path) -> dict:
    md = p.read_text(encoding="utf-8")
    sec = sections(md)
    date, cle = p.name[:10], p.name[11:-3].replace("prospection-", "", 1)
    pipeline = "Fiche produite par `scripts/prospecter.py`" in md
    if "Écartées au tri, sans ouvrir la page" in sec:
        fmt = "nouveau"
    elif pipeline and "Écartées (et pourquoi)" in sec:
        fmt = "ancien"
    else:
        fmt = "manuel"
    r: dict = {"fiche": p.name, "date": date, "territoire": cle, "format": fmt}
    if fmt == "manuel":
        return r
    if fmt == "nouveau":
        ec = [
            RE_URL.search(li).group(0)  # type: ignore[union-attr]
            for li in sec["Écartées au tri, sans ouvrir la page"]
            if li.startswith("- http")
        ]
        lues_test = [
            li for li in sec.get("Écartées par le test du destinataire", []) if li.startswith("- [")
        ]
        trancher = [
            li
            for li in sec.get("À trancher à la main (destinataire ou objet indéterminé)", [])
            if li.startswith("- `")
        ]
        non_lues_ret = len(lues_test) + len(trancher)
    else:
        ec = []
        lues_bold = 0
        for li in sec["Écartées (et pourquoi)"]:
            if li.startswith("- **"):
                lues_bold += 1
            elif li.startswith("- http"):
                ec.append(RE_URL.search(li).group(0))  # type: ignore[union-attr]
        non_lues_ret = lues_bold
    retenues = [li for li in sec.get("Candidates retenues", []) if re.match(r"^\| *\d+ *\|", li)]
    notes = "\n".join(sec.get("Notes techniques", []))
    erreurs = len(re.findall(r"^- non lue :", notes, re.M))
    m = re.search(r"(\d[\d ]*) à trier", notes)
    a_trier = int(m.group(1).replace(" ", "")) if m else None
    m = re.search(r"- (\d+) candidate\(s\) douteuse\(s\) au tri", notes)
    douteuses = int(m.group(1)) if m else 0
    lues = len(retenues) + non_lues_ret + erreurs
    r.update(
        ecartees=[e.rstrip(".,;)") for e in ec],
        n_ecartees=len(ec),
        lues=lues,
        a_trier_note=a_trier,
        douteuses=douteuses,
        retenues_tri=lues - douteuses,
    )
    return r


def vague(date: str) -> str:
    if date <= "2026-09-14":
        return "2026-09-08..14"
    if date <= "2026-09-18":
        return "2026-09-17..18"
    if date <= "2026-09-29":
        return "2026-09-28..29"
    return "2026-10-04"


def section_fiches() -> list[dict]:
    dire("=" * 78)
    dire("1. FICHES DE PROSPECTION (recompte indépendant)")
    dire("=" * 78)
    fiches = [lire_fiche(p) for p in sorted(REVIEWS.glob("*-prospection-*.md"))]
    dire("fiches :", len(fiches), "; formats :", dict(Counter(f["format"] for f in fiches)))
    pipe = [f for f in fiches if f["format"] != "manuel"]
    ok = sum(1 for f in pipe if f["a_trier_note"] is not None)
    egal = sum(
        1
        for f in pipe
        if f["a_trier_note"] is not None and f["a_trier_note"] == f["lues"] + f["n_ecartees"]
    )
    dire(f"note « à trier » présente : {ok}/{len(pipe)} ; égale à lues + écartées : {egal}/{ok}")
    for f in pipe:
        if f["a_trier_note"] is not None and f["a_trier_note"] != f["lues"] + f["n_ecartees"]:
            dire(
                "  écart :",
                f["fiche"],
                "note",
                f["a_trier_note"],
                "lues",
                f["lues"],
                "écartées",
                f["n_ecartees"],
            )
    par_v: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])
    for f in pipe:
        n = f["lues"] + f["n_ecartees"]
        v = par_v[vague(f["date"])]
        v[0] += 1
        v[1] += n
        v[2] += f["n_ecartees"]
        v[3] += f["douteuses"]
        v[4] += f["retenues_tri"]
    tot = [0, 0, 0, 0, 0]
    for k in sorted(par_v):
        v = par_v[k]
        tot = [a + b for a, b in zip(tot, v, strict=True)]
        dire(
            f"  {k:16s} fiches {v[0]:3d} à trier {v[1]:5d} écartées {v[2]:5d} douteuses "
            f"{v[3]:5d} retenues {v[4]:4d} part écartée {taux(v[2], v[1])}"
        )
    dire(
        f"  {'TOTAL':16s} fiches {tot[0]:3d} à trier {tot[1]:5d} écartées {tot[2]:5d} douteuses "
        f"{tot[3]:5d} retenues {tot[4]:4d} part écartée {taux(tot[2], tot[1])}"
    )
    return fiches


# --------------------------------------------------------------------------
# 2. Intermédiaires
# --------------------------------------------------------------------------
COMMITS_TRI = ["b172e873", "836e21cb", "57f054d7", "fdde0102"]


def versions_tri() -> list[dict]:
    """Toutes les versions de tri.jsonl lisibles, avec le candidats.jsonl voisin."""
    vus: dict[str, dict] = {}

    def ajouter(terr: str, tri_txt: str, cand_txt: str, source: str) -> None:
        if not tri_txt.strip():
            return
        h = hashlib.sha1(tri_txt.encode()).hexdigest()[:10]
        if h in vus:
            vus[h]["sources"].append(source)
            return
        vus[h] = {
            "sha": h,
            "territoire": terr,
            "tri": jsonl_texte(tri_txt),
            "candidats": jsonl_texte(cand_txt) if cand_txt else [],
            "sources": [source],
        }

    for base, nom in ((PRINCIPAL, "principal"), (WT_PROSP, "wt-prospection")):
        for t in sorted(base.glob("*/tri.jsonl")):
            c = t.with_name("candidats.jsonl")
            ajouter(
                t.parent.name,
                t.read_text(encoding="utf-8"),
                c.read_text(encoding="utf-8") if c.exists() else "",
                nom,
            )
    suivis = git("ls-files", "backend/data/prospection/*/tri.jsonl").split()
    for commit in COMMITS_TRI:
        for chemin in suivis:
            try:
                tri_txt = git("show", f"{commit}:{chemin}")
            except subprocess.CalledProcessError:
                continue
            try:
                cand_txt = git("show", f"{commit}:{chemin.replace('tri.jsonl', 'candidats.jsonl')}")
            except subprocess.CalledProcessError:
                cand_txt = ""
            ajouter(chemin.split("/")[-2], tri_txt, cand_txt, f"git {commit}")
    return list(vus.values())


def section_intermediaires(fiches: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    dire("=" * 78)
    dire("2. INTERMÉDIAIRES tri.jsonl et dernier balayage de chaque territoire")
    dire("=" * 78)
    versions = versions_tri()
    dire("versions distinctes non vides :", len(versions))
    pipe = [f for f in fiches if f["format"] != "manuel"]
    # Rattachement d'une version à une fiche : ensemble des écartées identique.
    for v in versions:
        ec = {norm(x["url"]) for x in v["tri"] if x["decision"] == "ecarter"}
        v["ecartees"] = ec
        v["fiches"] = [
            f["fiche"]
            for f in pipe
            if f["territoire"] == v["territoire"]
            and {norm(u) for u in f["ecartees"]} == ec
            and len(f["ecartees"]) == len(ec)
        ]
    sans = [v for v in versions if not v["fiches"]]
    dire("versions sans fiche à écartées identiques :", len(sans))
    for v in sans:
        dire(
            "  ",
            v["territoire"],
            v["sha"],
            len(v["tri"]),
            dict(Counter(x["decision"] for x in v["tri"])),
            v["sources"],
        )
    # Dernière fiche pipeline de chaque territoire.
    derniere: dict[str, dict] = {}
    for f in sorted(pipe, key=lambda f: f["date"]):
        derniere[f["territoire"]] = f
    tot = Counter()
    par_date: dict[str, Counter] = defaultdict(Counter)
    for f in derniere.values():
        n = f["lues"] + f["n_ecartees"]
        tot["territoires"] += 1
        tot["n"] += n
        tot["ec"] += f["n_ecartees"]
        tot["dt"] += f["douteuses"]
        tot["rt"] += f["retenues_tri"]
        d = par_date[f["date"]]
        d["territoires"] += 1
        d["n"] += n
        d["ec"] += f["n_ecartees"]
    dire(
        f"dernière fiche de chaque territoire (fiches seules) : {tot['territoires']} territoires, "
        f"à trier {tot['n']}, écartées {tot['ec']}, douteuses {tot['dt']}, retenues {tot['rt']} ; "
        f"part écartée {taux(tot['ec'], tot['n'])}"
    )
    for d in sorted(par_date):
        c = par_date[d]
        dire(f"  {d} : {c['territoires']} territoires, {taux(c['ec'], c['n'])}")
    # Version de tri.jsonl de la dernière fiche.
    der_v: dict[str, dict] = {}
    for terr, f in derniere.items():
        cands = [v for v in versions if f["fiche"] in v["fiches"]]
        if cands:
            der_v[terr] = cands[0]
    dire("territoires dont la version de la dernière fiche est retrouvée :", len(der_v))
    manquants = sorted(set(derniere) - set(der_v))
    dire("  sans version retrouvée :", manquants)
    return versions, der_v


# --------------------------------------------------------------------------
# 3. Garde-fou sans titre, oublis
# --------------------------------------------------------------------------
RE_MD = re.compile(r"!?\[[^\]]*\]\([^)]*\)|[\[\]()*_#>`|\\-]")


def section_gardefou(der_v: dict[str, dict]) -> None:
    dire("=" * 78)
    dire("3. GARDE-FOU SANS TITRE, OUBLIS (dernière version de chaque territoire)")
    dire("=" * 78)
    n = requal = oublis = panne = 0
    sans_titre = Counter()
    sans_texte = Counter()
    images = 0
    par_terr = Counter()
    exemples = []
    for terr, v in der_v.items():
        cand = {c["url"]: c for c in v["candidats"]}
        for t in v["tri"]:
            n += 1
            if t["motif"].startswith("écart sur l'URL seule"):
                requal += 1
            if t["motif"].startswith("absente de la réponse"):
                oublis += 1
            if t["motif"].startswith("lot non trié"):
                panne += 1
            c = cand.get(t["url"])
            if c is None:
                continue
            titre = (c.get("titre") or "").strip()
            extrait = (c.get("extrait") or "").strip()
            if not titre:
                sans_titre[t["decision"]] += 1
                if not RE_MD.sub("", extrait).strip():
                    sans_texte[t["decision"]] += 1
                    if t["decision"] == "ecarter":
                        par_terr[terr] += 1
                        if re.search(r"\.(jpe?g|png|gif|webp|svg)(\?|$)", t["url"], re.I):
                            images += 1
                        if len(exemples) < 3:
                            exemples.append((terr, t["url"], extrait[:120], t["motif"][:80]))
    dire(
        "lignes",
        n,
        "; requalifiées par le code",
        requal,
        "; oublis",
        taux(oublis, n),
        "; pannes",
        panne,
    )
    dire("sans titre par décision", dict(sans_titre))
    dire("sans titre et extrait vide hors balisage, par décision", dict(sans_texte))
    dire("  écartées dans ce cas par territoire", dict(par_terr), "; dont images", images)
    for e in exemples:
        dire("  ex.", e)


# --------------------------------------------------------------------------
# 4. Mémoire d'un passage à l'autre
# --------------------------------------------------------------------------
def urls_section(md: str, titres: tuple[str, ...], filtre=None) -> set[str]:
    sec = sections(md)
    out: set[str] = set()
    for t in titres:
        for li in sec.get(t, []):
            if filtre is not None and not filtre(li):
                continue
            for u in RE_URL.findall(li):
                out.add(norm(u.rstrip(".,;)|")))
    return out


def tri_rejoue_selon_journal() -> dict[str, bool]:
    """fiche -> True si le journal de balayage montre un tri relu (aucun lot trié)."""
    out: dict[str, bool] = {}
    for j in BALAYAGE_LOGS.glob("*-prospection-*.log"):
        txt = j.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"fiche : data/reviews/(\S+\.md)", txt)
        if not m:
            continue
        lots = len(re.findall(r"\[2/3\] lot ", txt))
        a_trier = re.search(r"\[2/3\] (\d+) retenue", txt)
        out[m.group(1)] = lots == 0 and a_trier is not None
    return out


def section_memoire(fiches: list[dict]) -> dict:
    dire("=" * 78)
    dire("4. MÉMOIRE : devenir d'une écartée au passage suivant du même territoire")
    dire("=" * 78)
    journal = tri_rejoue_selon_journal()
    dire(
        "fiches de balayage dont le journal montre un tri RELU (0 lot) :",
        sorted(k for k, v in journal.items() if v),
    )
    pipe = sorted((f for f in fiches if f["format"] != "manuel"), key=lambda f: f["date"])
    par_terr: dict[str, list[dict]] = defaultdict(list)
    for f in pipe:
        par_terr[f["territoire"]].append(f)
    total = Counter()
    total_frais = Counter()
    paires = []
    for terr, fs in sorted(par_terr.items()):
        for a, b in zip(fs, fs[1:], strict=False):
            md_b = (REVIEWS / b["fiche"]).read_text(encoding="utf-8")
            ec_b = {norm(u) for u in b["ecartees"]}
            lues_b = urls_section(
                md_b,
                (
                    "Candidates retenues",
                    "À trancher à la main (destinataire ou objet indéterminé)",
                    "Écartées par le test du destinataire",
                ),
            ) | urls_section(md_b, ("Écartées (et pourquoi)",), lambda li: li.startswith("- **"))
            notes = sections(md_b).get("Notes techniques", [])
            filtrees = {
                norm(u.rstrip(".,;)|"))
                for li in notes
                if li.startswith(("- déjà au catalogue", "- déjà en file"))
                for u in RE_URL.findall(li)[:1]
            }
            erreurs = {
                norm(u.rstrip(".,;)|"))
                for li in notes
                if li.startswith("- non lue")
                for u in RE_URL.findall(li)[:1]
            }
            dev = Counter()
            for u in {norm(x) for x in a["ecartees"]}:
                if u in ec_b:
                    dev["re-écartée"] += 1
                elif u in lues_b or u in erreurs:
                    dev["ouverte"] += 1
                elif u in filtrees:
                    dev["filtrée (catalogue ou file)"] += 1
                else:
                    dev["absente"] += 1
            relu = journal.get(b["fiche"])
            paires.append((terr, a["date"], b["date"], relu, dict(dev)))
            total.update(dev)
            if not relu:
                total_frais.update(dev)
            dire(
                f"  {terr:28s} {a['date']} -> {b['date']} tri relu selon journal={relu} : {dict(dev)}"
            )
    dire("total", dict(total))
    dire("sans les tris relus (journal) :", dict(total_frais))
    k = total_frais["ouverte"]
    n = k + total_frais["re-écartée"]
    dire("part ouverte parmi les retriées :", taux(k, n))
    return {"paires": paires}


# --------------------------------------------------------------------------
# 5. Écartées revenues dans la file
# --------------------------------------------------------------------------
def urls_catalogue() -> dict[str, str]:
    out: dict[str, str] = {}
    for f in AIDES.glob("*.yaml"):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        src = d.get("source") or {}
        for k in ("url_officielle", "formulaire_url"):
            if src.get(k):
                out.setdefault(norm(src[k]), f.stem)
    return out


def section_revenues(fiches: list[dict]) -> None:
    dire("=" * 78)
    dire("5. ÉCARTÉES AU TRI REVENUES DANS LA FILE")
    dire("=" * 78)
    premiere: dict[str, str] = {}
    toutes: Counter = Counter()
    for f in sorted((f for f in fiches if f["format"] != "manuel"), key=lambda f: f["date"]):
        for u in {norm(x) for x in f["ecartees"]}:
            premiere.setdefault(u, f["date"])
            toutes[u] += 1
    dire("URL distinctes écartées dans au moins une fiche :", len(premiere))
    dire("  écartées dans au moins deux fiches :", sum(1 for v in toutes.values() if v >= 2))
    file = yaml.safe_load(FILE.read_text(encoding="utf-8")) or {}
    revenues = []
    for slug, t in file.items():
        u = norm(t.get("url") or "")
        if u in premiere and str(t.get("ajoute_le")) > premiere[u]:
            revenues.append((slug, t, premiere[u]))
    meme_jour = sum(
        1
        for slug, t in file.items()
        if norm(t.get("url") or "") in premiere
        and str(t.get("ajoute_le")) <= premiere[norm(t.get("url") or "")]
    )
    dire(
        "tâches de la file dont l'URL a été écartée au tri AVANT leur ajout :",
        len(revenues),
        dict(Counter(t.get("statut") for _, t, _ in revenues)),
    )
    dire(
        "  (tâches dont l'URL est écartée au tri le jour même ou après leur ajout :", meme_jour, ")"
    )
    actifs = [(s, d) for s, t, d in revenues if (AIDES / f"{s}.yaml").exists()]
    dire("  YAML actif sous le slug de file :", len(actifs))
    par_date = Counter(d for _, _, d in revenues)
    act_date = Counter(d for _, d in actifs)
    for d in sorted(par_date):
        dire(f"    écartées le {d} : {taux(act_date[d], par_date[d])} avec YAML actif")
    cat = urls_catalogue()
    ec_au_cat = {u: cat[u] for u in premiere if u in cat}
    dire(
        "URL écartées au tri un jour et présentes aujourd'hui au catalogue (par url_officielle, "
        "tout slug) :",
        len(ec_au_cat),
    )
    hors_slug = {u: s for u, s in ec_au_cat.items() if s not in {a for a, _ in actifs}}
    dire("  dont hors des 'revenues' ci-dessus :", len(hors_slug))
    for u, s in sorted(hors_slug.items(), key=lambda kv: kv[1])[:40]:
        dire("    ", s, "|", u, "| première écart", premiere[u])
    (SORTIE / "revenues.json").write_text(
        json.dumps(
            {
                "revenues": [
                    {
                        "slug": s,
                        "statut": t.get("statut"),
                        "ecartee_le": d,
                        "ajoute_le": str(t.get("ajoute_le")),
                    }
                    for s, t, d in revenues
                ],
                "ecartees_au_catalogue": ec_au_cat,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# 6. Les 983 titres réels du 2026-10-04
# --------------------------------------------------------------------------
OBJETS_RETENUS = {"bien_ou_lieu", "activite_dans_le_lieu"}


def bande_jev(r: dict, bas: float = 0.12, haut: float = 0.57) -> str:
    ecarte = (
        r.get("destinataire") != "proprietaire_gestionnaire"
        or r.get("objet") not in OBJETS_RETENUS
        or (r.get("dispositif") or 0) < 0.5
    )
    if r["deposable"] < bas and ecarte:
        return "ecartee"
    if r["deposable"] > haut and not ecarte:
        return "retenue"
    return "milieu"


def issue_lecture(le: dict) -> str:
    if le.get("erreur") or not le.get("fiche"):
        return "erreur"
    f = le["fiche"]
    d, o, c = f.get("destinataire"), f.get("objet"), f.get("categorie_ecart")
    # lecture.FicheLue.retenir : une page non_dispositif n'est jamais retenue.
    if c == "non_dispositif":
        return "ecartee"
    if d == "proprietaire_gestionnaire" and o in OBJETS_RETENUS:
        return "retenue"
    if d not in ("indetermine", "proprietaire_gestionnaire"):
        return "ecartee"
    if o != "indetermine" and o not in OBJETS_RETENUS:
        return "ecartee"
    return "indeterminee" if (d == "indetermine" or o == "indetermine") else "ecartee"


def section_983() -> dict:
    dire("=" * 78)
    dire("6. LES 983 TITRES RÉELS DU 2026-10-04")
    dire("=" * 78)
    cands = []
    lectures: dict[str, dict] = {}
    for d in DEPTS_983:
        base = WT_PROSP / d
        tri = {t["url"]: t["decision"] for t in jsonl(base / "tri.jsonl")}
        for c in jsonl(base / "candidats.jsonl"):
            cands.append(
                {
                    "dept": d,
                    "url": c["url"],
                    "titre": c.get("titre") or "",
                    "tri": tri.get(c["url"]),
                }
            )
        for le in jsonl(base / "lectures.jsonl"):
            lectures[le["url"]] = le
    jt = {x["url"]: x for x in jsonl(JEV / "tri_reel_titres.jsonl")}
    jp = {x["url"]: x for x in jsonl(JEV / "tri_reel_pages.jsonl")}
    dire("candidates", len(cands), "; URL distinctes", len({c["url"] for c in cands}))
    dire("couvertes par tri_reel_titres :", sum(1 for c in cands if c["url"] in jt), "/", len(jt))
    dec = Counter(c["tri"] for c in cands)
    dire("décisions du tri :", dict(dec))
    n = len(cands)
    dire("tri écarte :", taux(dec["ecarter"], n))
    dire("sans titre :", sum(1 for c in cands if not c["titre"].strip()))
    for seuil in (0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30):
        cr = Counter()
        for c in cands:
            j = jt[c["url"]]["deposable"] < seuil
            g = c["tri"] == "ecarter"
            cr[(g, j)] += 1
        je = cr[(True, True)] + cr[(False, True)]
        dire(
            f"  seuil {seuil:.2f} : les deux écartent {cr[(True, True)]}, tri écarte/Jev garde "
            f"{cr[(True, False)]}, tri garde/Jev écarte {cr[(False, True)]}, les deux gardent "
            f"{cr[(False, False)]} ; Jev écarte {taux(je, n)}"
        )
    cible = [c for c in cands if c["tri"] == "ecarter" and jt[c["url"]]["deposable"] >= 0.10]
    bandes = Counter()
    for c in cible:
        r = jp.get(c["url"])
        bandes["absente" if r is None else ("erreur" if "erreur" in r else bande_jev(r))] += 1
    dire(
        "pages visées (tri écarte, Jev titre >= 0,10) :",
        len(cible),
        "; bandes Jev page :",
        dict(bandes),
    )
    dire("  retenue :", taux(bandes["retenue"], len(cible)))
    dire("  retenue ou milieu :", taux(bandes["retenue"] + bandes["milieu"], len(cible)))
    # Gardées par le tri : issue de lecture.
    gardees = [c for c in cands if c["tri"] in ("retenir", "douteux")]
    iss = Counter(
        issue_lecture(lectures[c["url"]]) if c["url"] in lectures else "non lue" for c in gardees
    )
    dire("gardées au tri", len(gardees), "; issue de lecture :", dict(iss))
    hors_err = len(gardees) - iss["erreur"] - iss["non lue"]
    dire("  écartées à la lecture (hors erreurs) :", taux(iss["ecartee"], hors_err))
    dire("  retenues à la lecture (hors erreurs) :", taux(iss["retenue"], hors_err))
    for dec_ in ("retenir", "douteux"):
        g = [c for c in gardees if c["tri"] == dec_]
        k = sum(
            1 for c in g if c["url"] in lectures and issue_lecture(lectures[c["url"]]) == "retenue"
        )
        dire(f"  tri {dec_} -> lecture retenue : {taux(k, len(g))}")
    arb = sum(1 for le in lectures.values() if le.get("arbitrage"))
    dire("lectures portant un arbitrage Jev :", arb, "/", len(lectures))
    cout_t = sum(x.get("cout_usd") or 0 for x in jt.values())
    cout_p = sum(x.get("cout_usd") or 0 for x in jp.values())
    dire(f"coût Jev annoncé : titres {cout_t:.3f} $, pages {cout_p:.3f} $")
    return {"cands": cands, "jt": jt, "jp": jp, "lectures": lectures}


# --------------------------------------------------------------------------
# 7. Banc étiqueté : Jev sur titre contre Jev sur page
# --------------------------------------------------------------------------
SOURCES = BACKEND / "data" / "sources"


def a_snapshot(slug: str) -> bool:
    d = SOURCES / slug
    return d.is_dir() and any(f.suffix in (".md", ".pdf") for f in d.iterdir())


def etiquettes() -> dict[str, tuple[bool, str, str]]:
    """slug -> (gardée, origine, motif), recalculé au HEAD de ce worktree."""
    head = git("ls-tree", "--name-only", "HEAD", "backend/data/aides/").split()
    gardes = {Path(x).name[:-5] for x in head if x.endswith(".yaml")}
    file = yaml.safe_load(FILE.read_text(encoding="utf-8")) or {}
    out: dict[str, tuple[bool, str, str]] = {}
    for sl in gardes:
        if a_snapshot(sl):
            out[sl] = (True, "prospection" if sl in file else "catalogue", "")
    for sl, t in file.items():
        motif = t.get("motif_ignore") or ""
        if t.get("statut") != "ignore" or "oublon" in motif:
            continue
        if not motif.startswith(("test du destinataire", "tri humain")):
            continue
        if sl in gardes or not (AIDES / f"{sl}.yaml.echec").exists():
            continue
        if a_snapshot(sl):
            out[sl] = (False, "prospection", motif.split(" :")[0][:30])
    return out


def deposable(r: dict) -> float:
    v = r["reponses"]["deposable"]
    return float(v.get("noul", 0.0)) if isinstance(v, dict) else float(v)


def mon_auc(couples: list[tuple[float, bool]]) -> float:
    pos = sorted(x for x, g in couples if g)
    neg = sorted(x for x, g in couples if not g)
    # Mann-Whitney par rangs moyens.
    tous = sorted([(x, 1) for x in pos] + [(x, 0) for x in neg])
    rangs: dict[float, float] = {}
    i = 0
    while i < len(tous):
        j = i
        while j < len(tous) and tous[j][0] == tous[i][0]:
            j += 1
        rangs[tous[i][0]] = (i + j + 1) / 2
        i = j
    somme = sum(rangs[x] for x in pos)
    return (somme - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def moitie(slug: str) -> int:
    return int(hashlib.sha256(slug.encode()).hexdigest(), 16) % 2


def section_banc() -> None:
    dire("=" * 78)
    dire("7. BANC ÉTIQUETÉ : JEV TITRE CONTRE JEV PAGE")
    dire("=" * 78)
    et = etiquettes()
    titre = {x["slug"]: x for x in jsonl(JEV / "jev_titre.jsonl")}
    page = {x["slug"]: x for x in jsonl(BANC / "jev.jsonl")}
    communs = sorted(s for s in et if s in titre and s in page)
    dire(f"étiquetés {len(et)} ; titres {len(titre)} ; pages {len(page)} ; communs {len(communs)}")
    g = sum(et[s][0] for s in communs)
    dire(
        f"  gardées {g}, écartées {len(communs) - g} ; motifs des écartées",
        dict(Counter(et[s][2] for s in communs if not et[s][0])),
    )
    titres_hors_etiq = [s for s in titre if s not in et]
    dire(
        "  titres jugés le 2026-10-04 dont l'étiquette n'existe plus au HEAD :",
        len(titres_hors_etiq),
    )
    for nom, filtre in (
        ("tout", lambda s: True),
        ("prospection", lambda s: et[s][1] == "prospection"),
    ):
        sel = [s for s in communs if filtre(s)]
        cp = [(deposable(page[s]), et[s][0]) for s in sel]
        ct = [(deposable(titre[s]), et[s][0]) for s in sel]
        dire(f"  {nom} : {len(sel)} cas, AUC page {mon_auc(cp):.3f}, titre {mon_auc(ct):.3f}")
        for tol in (0.0, 0.01, 0.02):
            for a, b in ((0, 1), (1, 0)):
                app = sorted(deposable(titre[s]) for s in sel if moitie(s) == a and et[s][0])
                k = int(tol * len(app))
                seuil = app[k] if k < len(app) else 1.0
                test = [s for s in sel if moitie(s) == b]
                ec = [s for s in test if deposable(titre[s]) < seuil]
                perd = sum(et[s][0] for s in ec)
                gt = sum(et[s][0] for s in test)
                dire(
                    f"    tol {tol:.2f} réglé sur {a}, mesuré sur {b} : seuil {seuil:.3f} ; écarte "
                    f"{taux(len(ec), len(test))} ; gardées perdues {taux(perd, gt)}"
                )


# --------------------------------------------------------------------------
# 8. Contrôle de l'échantillon tiré par le mesureur
# --------------------------------------------------------------------------
RE_IMAGE = re.compile(r"\.(jpe?g|png|gif|webp|svg)(\?|$)", re.I)


def section_echantillon(der_v: dict[str, dict]) -> None:
    import random

    dire("=" * 78)
    dire("8. CONTRÔLE DE L'ÉCHANTILLON DU MESUREUR (echantillon_controle.jsonl, leurres.jsonl)")
    dire("=" * 78)
    pop: dict[str, list[str]] = {}
    pop_g: dict[str, list[str]] = {}
    for terr, v in der_v.items():
        if terr == "57":
            continue
        ec = sorted({x["url"] for x in v["tri"] if x["decision"] == "ecarter"})
        ga = sorted({x["url"] for x in v["tri"] if x["decision"] != "ecarter"})
        if ec:
            pop[terr] = ec
        if ga:
            pop_g[terr] = ga
    n_pop = sum(len(v) for v in pop.values())
    dire("population recomptée :", n_pop, "écartées dans", len(pop), "territoires")
    ech = jsonl(MESUREUR / "echantillon_controle.jsonl")
    leu = jsonl(MESUREUR / "leurres.jsonl")
    lot = jsonl(MESUREUR / "lot_aveugle.jsonl")
    dans = sum(1 for e in ech if e["url"] in set(pop.get(e["territoire"], [])))
    dire(
        "échantillon :",
        len(ech),
        "; dans la population recomptée :",
        dans,
        "; URL distinctes :",
        len({e["url"] for e in ech}),
    )
    dire(
        "leurres :",
        len(leu),
        "; gardés au tri dans la dernière version :",
        sum(1 for e in leu if e["url"] in set(pop_g.get(e["territoire"], []))),
    )
    dire(
        "lot aveugle :",
        len(lot),
        "; = échantillon + leurres :",
        {x["url"] for x in lot} == {e["url"] for e in ech} | {e["url"] for e in leu},
    )
    # Allocation proportionnelle, plus grands restes.
    quotas = {t: 100 * len(v) / n_pop for t, v in pop.items()}
    base = {t: int(q) for t, q in quotas.items()}
    reste = 100 - sum(base.values())
    for t in sorted(quotas, key=lambda t: (-(quotas[t] - base[t]), t))[:reste]:
        base[t] += 1
    obs = Counter(e["territoire"] for e in ech)
    ecarts = {t: (base[t], obs.get(t, 0)) for t in pop if base[t] != obs.get(t, 0)}
    dire("allocation recalculée = allocation observée :", not ecarts, ecarts if ecarts else "")
    dire("strates représentées :", len(obs))
    # Reproduction du tirage décrit.
    rng = random.Random(20261010)
    tire = set()
    for t in sorted(pop):
        if base[t]:
            tire |= set(rng.sample(pop[t], base[t]))
    dire(
        "tirage reproduit à l'identique (procédure décrite, une graine pour toutes les strates) :",
        tire == {e["url"] for e in ech},
        "; recouvrement",
        len(tire & {e["url"] for e in ech}),
    )
    hotes = Counter(urlparse(e["url"]).netloc for e in ech)
    hotes_lot = Counter(urlparse(x["url"]).netloc for x in lot)
    dire(
        "hôtes distincts : 100 écartées",
        len(hotes),
        "; lot de 150",
        len(hotes_lot),
        "; plus chargés",
        hotes.most_common(3),
        "; lot",
        hotes_lot.most_common(2),
    )
    imgs = [e for e in ech if RE_IMAGE.search(e["url"])]
    pop_img = sum(1 for v in pop.values() for u in v if RE_IMAGE.search(u))
    dire("images dans l'échantillon :", len(imgs), "; dans la population :", taux(pop_img, n_pop))
    sans_titre = sum(1 for e in ech if not (e.get("titre") or "").strip())
    dire("sans titre dans l'échantillon :", sans_titre)
    for resp in (0.5, 2.0):
        seq = len(lot) * (resp + 1.0) / 60
        par = max(hotes_lot.values()) * (resp + 1.0) / 60
        dire(
            f"  lot de 150, réponse {resp} s : séquentiel {seq:.1f} min ; un fil par hôte {par:.1f} min"
        )
    par_bal = Counter(e["balayage"] for e in ech)
    dire("par balayage :", dict(par_bal))
    # Population par modèle probable (cf. section 9).
    n_ds = sum(len(v) for t, v in pop.items() if der_v[t]["sources"])
    dire("  (population totale pour contrôle :", n_ds, ")")


# --------------------------------------------------------------------------
# 9. Quel modèle a trié ? Inférence par le coût au jeton
# --------------------------------------------------------------------------
PRIX = {  # $ par million : entrée, sortie, lecture de cache (providall + pipeline/llm.py)
    "or-glm": (0.07, 0.25, 0.007),
    "ds-v41": (0.30, 1.20, 0.006),
}
RE_COUT = re.compile(
    r"(\d+) appel\(s\)\s+([\d  ]+) jetons entrée / ([\d  ]+) sortie\s+\$([\d.]+)(.*)"
)


def compatibles(ent: int, sor: int, cout: float, inconnu: bool) -> list[str]:
    out = []
    for nom, (pi, po, pc) in PRIX.items():
        hi = (ent * pi + sor * po) / 1e6
        lo = (ent * min(pi, pc) + sor * po) / 1e6
        # Un coût « inconnu » est un minorant : seul le plafond tient.
        if cout <= hi * 1.02 and (inconnu or cout >= lo * 0.98):
            out.append(nom)
    return out


def section_modele() -> None:
    dire("=" * 78)
    dire("9. MODÈLE DU TRI : coût au jeton des journaux et des fiches")
    dire("=" * 78)
    par_vague: dict[str, Counter] = defaultdict(Counter)
    sources = [
        (j.name[:10], j.read_text(encoding="utf-8", errors="replace"))
        for j in BALAYAGE_LOGS.glob("*-prospection-*.log")
    ]
    sources += [
        (f.name[:10] + " (fiche)", f.read_text(encoding="utf-8"))
        for f in REVIEWS.glob("*-prospection-*.md")
    ]
    for date, txt in sources:
        tous_m = list(RE_COUT.finditer(txt))
        m = tous_m[-1] if tous_m else None
        if m is None:
            continue
        ent = int(re.sub(r"\D", "", m.group(2)))
        sor = int(re.sub(r"\D", "", m.group(3)))
        cout = float(m.group(4))
        if ent == 0:
            continue
        inconnu = "inconnu" in m.group(5)
        comp = compatibles(ent, sor, cout, inconnu)
        par_vague[date]["+".join(comp) or "aucun"] += 1
    for d in sorted(par_vague):
        dire(f"  {d} : {dict(par_vague[d])}")


def section_cout_lot() -> None:
    """Coût réel d'un lot de tri, estimé par moindres carrés sur les journaux de balayage.

    Retenus : les journaux où le nombre d'appels = lots de tri + pages lues sans
    ERREUR (pas de découverte ni de panne qui brouillent le compte).
    """
    dire("-" * 78)
    dire("9 bis. COÛT RÉEL D'UN LOT DE TRI (journaux de balayage, modèle au tarif ds-v41)")
    lignes_ = []
    for j in sorted(BALAYAGE_LOGS.glob("*-prospection-*.log")):
        txt = j.read_text(encoding="utf-8", errors="replace")
        lots = len(re.findall(r"\[2/3\] lot ", txt))
        m = re.search(r"\[3/3\] (\d+) page\(s\) à lire", txt)
        lire = int(m.group(1)) if m else 0
        err = len(re.findall(r"ERREUR", txt))
        tous_m = list(RE_COUT.finditer(txt))
        m = tous_m[-1] if tous_m else None
        if m is None or lots == 0:
            continue
        appels = int(m.group(1))
        ent = int(re.sub(r"\D", "", m.group(2)))
        sor = int(re.sub(r"\D", "", m.group(3)))
        if appels == lots + lire - err:
            lignes_.append((lots, lire - err, ent, sor, float(m.group(4))))
    n = len(lignes_)
    # Moindres carrés à deux variables sans intercept, résolus à la main.
    sxx = sum(a * a for a, *_ in lignes_)
    syy = sum(b * b for _, b, *_ in lignes_)
    sxy = sum(a * b for a, b, *_ in lignes_)
    det = sxx * syy - sxy * sxy
    for idx, nom in ((2, "jetons d'entrée"), (3, "jetons de sortie"), (4, "dollars")):
        sxz = sum(r[0] * r[idx] for r in lignes_)
        syz = sum(r[1] * r[idx] for r in lignes_)
        a = (sxz * syy - syz * sxy) / det
        b = (syz * sxx - sxz * sxy) / det
        dire(f"  {nom} : {a:.4g} par lot de tri, {b:.4g} par page lue (n = {n} journaux)")


# --------------------------------------------------------------------------
# 10. Moselle : la même page triée ~120 fois dans le même passage
# --------------------------------------------------------------------------
def section_moselle() -> None:
    dire("=" * 78)
    dire("10. MOSELLE 2026-09-18 : BRUIT DU TRI À CONSIGNE ET MODÈLE CONSTANTS")
    dire("=" * 78)
    base = PRINCIPAL / "57"
    tri = {t["url"]: t for t in jsonl(base / "tri.jsonl")}
    cands = jsonl(base / "candidats.jsonl")
    dire("lignes", len(tri), "; décisions", dict(Counter(t["decision"] for t in tri.values())))

    def fin(u: str) -> str:
        m = re.findall(r"jcms/([a-z]+_\d+)", u)
        return m[-1] if m else u

    dire("pages finales distinctes (dernier identifiant jcms) :", len({fin(u) for u in tri}))
    groupes: dict[tuple, list[str]] = defaultdict(list)
    for c in cands:
        t = tri.get(c["url"])
        if t is None or t["motif"].startswith(("absente", "lot non")):
            continue
        cle = (fin(c["url"]), (c.get("titre") or "").strip(), (c.get("extrait") or "").strip())
        groupes[cle].append(t["decision"])
    multi = {k: v for k, v in groupes.items() if len(v) >= 2}
    copies = sum(len(v) for v in multi.values())
    dire(
        f"groupes à titre et extrait identiques, >= 2 copies : {len(multi)} pages, {copies} copies "
        f"(oublis du modèle exclus)"
    )
    mixtes = [v for v in multi.values() if len({d == "ecarter" for d in v}) > 1]
    dire(
        "  pages où des copies identiques reçoivent écarter ET garder :",
        taux(len(mixtes), len(multi)),
    )
    num = den = 0.0
    for v in multi.values():
        n = len(v)
        e = sum(d == "ecarter" for d in v)
        num += e * (n - e)
        den += n * (n - 1) / 2
    dire(f"  désaccord écarter/garder entre deux copies tirées au hasard : {100 * num / den:.1f} %")
    maj = [v for v in multi.values() if sum(d == "ecarter" for d in v) > len(v) / 2]
    k = sum(1 for v in maj if any(d != "ecarter" for d in v))
    dire("  pages majoritairement écartées dont au moins une copie est gardée :", taux(k, len(maj)))
    ecs = sum(sum(d == "ecarter" for d in v) for v in maj)
    flips = sum(sum(d != "ecarter" for d in v) for v in maj)
    dire(
        "  parmi les copies de ces pages, part gardée (proba qu'un écart soit renversé au "
        f"retri, même consigne) : {taux(flips, ecs + flips)}"
    )
    st = [v for k_, v in multi.items() if not k_[1]]
    dire("  pages sans titre :", len(st), [dict(Counter(v)) for v in st])


# --------------------------------------------------------------------------
# 11. Que vaut la bande « milieu » de Jev ? (pour relire les 294 pages)
# --------------------------------------------------------------------------
def reponse_vers_plat(r: dict) -> dict:
    rep = r["reponses"]

    def choix(q: str) -> str:
        v = rep.get(q) or {}
        return v.get("choice") or ""

    def noul(q: str) -> float:
        v = rep.get(q) or {}
        return float(v.get("noul", 0.0))

    return {
        "deposable": noul("deposable"),
        "destinataire": choix("destinataire"),
        "objet": choix("objet"),
        "dispositif": noul("dispositif"),
    }


def section_milieu(reel: dict) -> None:
    dire("=" * 78)
    dire("11. BANDE « MILIEU » DE JEV SUR PAGE : CE QU'ELLE DEVIENT AU BANC")
    dire("=" * 78)
    et = etiquettes()
    page = {x["slug"]: x for x in jsonl(BANC / "jev.jsonl")}
    llm = {x["slug"]: x for x in jsonl(BANC / "llm-or-glm.jsonl")}
    par_bande: dict[str, Counter] = defaultdict(Counter)
    for sl, r in page.items():
        if sl not in et:
            continue
        b = bande_jev(reponse_vers_plat(r))
        par_bande[b]["n"] += 1
        par_bande[b]["gardee"] += int(et[sl][0])
        if sl in llm:
            par_bande[b]["llm_n"] += 1
            par_bande[b]["llm_retenir"] += int(bool(llm[sl].get("retenir")))
    for b in ("ecartee", "milieu", "retenue"):
        c = par_bande[b]
        dire(
            f"  bande {b:8s} : gardée au catalogue {taux(c['gardee'], c['n'])} ; "
            f"lecture or-glm retient {taux(c['llm_retenir'], c['llm_n'])}"
        )
    tot_g = sum(par_bande[b]["gardee"] for b in par_bande)
    dire(
        "  rappel de la bande retenue sur les gardées du banc :",
        taux(par_bande["retenue"]["gardee"], tot_g),
    )
    dire(
        "  (banc : aides déjà passées par le tri ; « gardée » = YAML dans HEAD, pas une "
        "étiquette humaine page par page ; seuils 0,12 / 0,57 réglés sur ce même banc)"
    )
    # La lecture or-glm comme référence : que retient-elle des gardées du banc ?
    issue = Counter()
    for sl, (garde, _o, _m) in et.items():
        x = llm.get(sl)
        if x is None:
            continue
        i = (
            "retenue"
            if x.get("retenir")
            else ("indeterminee" if x.get("indeterminee") else "ecartee")
        )
        issue[(garde, i)] += 1
    ng = sum(v for (g, _), v in issue.items() if g)
    ne = sum(v for (g, _), v in issue.items() if not g)
    dire(
        "  lecture or-glm sur le banc : gardées retenues",
        taux(issue[(True, "retenue")], ng),
        "; gardées écartées",
        taux(issue[(True, "ecartee")], ng),
        "; écartées écartées",
        taux(issue[(False, "ecartee")], ne),
    )
    # Les 294 : distribution du deposable page.
    jp = reel["jp"]
    cible = [
        c
        for c in reel["cands"]
        if c["tri"] == "ecarter" and reel["jt"][c["url"]]["deposable"] >= 0.10
    ]
    deps = sorted(
        jp[c["url"]]["deposable"] for c in cible if c["url"] in jp and "erreur" not in jp[c["url"]]
    )
    for seuil in (0.12, 0.2, 0.3, 0.45, 0.57):
        k = sum(1 for d in deps if d >= seuil)
        dire(f"  294 pages : deposable page >= {seuil:.2f} : {taux(k, len(deps))}")


def section_doubles_comptes(fiches: list[dict]) -> None:
    dire("-" * 78)
    dire("1 bis. DOUBLES COMPTES : fiches dont le tri a été RELU (journal : 0 lot trié)")
    journal = tri_rejoue_selon_journal()
    pipe = [f for f in fiches if f["format"] != "manuel"]
    note_rejeu = {
        f["fiche"]
        for f in pipe
        if "rejoué depuis candidats.jsonl" in (REVIEWS / f["fiche"]).read_text(encoding="utf-8")
    }
    relus = {k for k, v in journal.items() if v}
    dire(
        "fiches portant la note « rejoué depuis candidats.jsonl » (collecte relue) :",
        len(note_rejeu),
    )
    dire(
        "  dont tri relu selon le journal :",
        len(note_rejeu & relus),
        "; tri refait selon le journal :",
        len({x for x in note_rejeu if journal.get(x) is False}),
        "; sans journal :",
        len({x for x in note_rejeu if x not in journal}),
    )
    garde = [f for f in pipe if f["fiche"] not in relus]
    n = sum(f["lues"] + f["n_ecartees"] for f in garde)
    k = sum(f["n_ecartees"] for f in garde)
    dire(f"  sans les {len(pipe) - len(garde)} fiches à tri relu : {taux(k, n)}")


if __name__ == "__main__":
    SORTIE.mkdir(parents=True, exist_ok=True)
    dire("tri_titre_recompte.py, HEAD", git("rev-parse", "--short", "HEAD").strip())
    fiches = section_fiches()
    versions, der_v = section_intermediaires(fiches)
    section_gardefou(der_v)
    section_memoire(fiches)
    section_revenues(fiches)
    reel = section_983()
    section_banc()
    section_echantillon(der_v)
    section_modele()
    section_cout_lot()
    section_moselle()
    section_milieu(reel)
    section_doubles_comptes(fiches)
    (SORTIE / "rapport.txt").write_text("\n".join(lignes_rapport) + "\n", encoding="utf-8")
