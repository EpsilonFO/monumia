"""Recompte adverse de la note « trouver une source » (phase 1 de la refonte).

Lecture seule : aucun appel réseau, aucun modèle, aucune écriture hors du
dossier de sortie. Ne réutilise PAS le script du mesureur
(`scripts/mesures/trouver_source.py`) : chaque chiffre est recompté depuis les
données brutes, avec ses propres analyseurs.

    cd backend && uv run python scripts/mesures/trouver_source_recompte.py

Écrit `data/reviews/logs/refonte/2026-10-10-trouver-source-recompte-1/`.
"""

from __future__ import annotations

import collections
import glob
import json
import math
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import yaml

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from prospection.collecte import chemin_en_boucle, cle_fiche  # noqa: E402
from veille_collect import cle_url  # noqa: E402

DATA = BACKEND / "data"
REVIEWS = DATA / "reviews"
SORTIE = REVIEWS / "logs" / "refonte" / "2026-10-10-trouver-source-recompte-1"
DEPOT = Path("/Users/felixollivier/monumia")
SOURCES_CANDIDATS = [
    DEPOT / "backend" / "data" / "prospection",
    DEPOT / ".claude" / "worktrees" / "prospection" / "backend" / "data" / "prospection",
]
VAGUES_COMPARABLES = ("2026-09-28", "2026-09-29", "2026-10-04")

RE_COLLECTE = re.compile(
    r"(\d+) URL de fiche trouvées, (\d+) déjà au catalogue, (\d+) déjà en file "
    r"d'attente, (\d+) à trier \((\d+) page"
)
RE_STRATEGIE = re.compile(r"^Stratégie : (\w+) \(recette `(\w+)`\)", re.M)


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * max(0.0, c - m), 1), round(100 * min(1.0, c + m), 1)]


def taux(k: int, n: int) -> str:
    if n == 0:
        return f"{k}/0"
    ic = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f} % [{ic[0]} ; {ic[1]}]"  # type: ignore[index]


# --------------------------------------------------------------------------
# 1. Recettes, lues dans le YAML brut (sans charger_territoires)
# --------------------------------------------------------------------------


def recettes() -> dict:
    t = yaml.safe_load((DATA / "prospection" / "territoires.yaml").read_text("utf-8"))
    statut = collections.Counter(v.get("statut", "sans_point_entree") for v in t.values())
    strat_explicite = collections.Counter(
        (v.get("strategie") or {}).get("type", "(absente, défaut decouverte)") for v in t.values()
    )
    croise = collections.Counter(
        f"{(v.get('strategie') or {}).get('type', 'defaut')} / {v.get('statut')}"
        for v in t.values()
    )
    return {
        "n": len(t),
        "par_type": dict(collections.Counter(v["type"] for v in t.values())),
        "par_statut": dict(statut),
        "par_strategie_explicite": dict(strat_explicite),
        "strategie_x_statut": dict(croise),
        "max_candidats_non_defaut": {
            k: (v.get("strategie") or {}).get("max_candidats")
            for k, v in t.items()
            if (v.get("strategie") or {}).get("max_candidats")
        },
    }


# --------------------------------------------------------------------------
# 2. Fiches de prospection, analyseur propre
# --------------------------------------------------------------------------


def _sections(texte: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    courant = None
    for li in texte.splitlines():
        if li.startswith("## "):
            courant = re.sub(r"\s*\(\d+\)\s*$", "", li[3:]).strip()
            out[courant] = []
        elif courant is not None:
            out[courant].append(li)
    return out


def analyser_fiche(chemin: Path) -> dict:
    nom = chemin.name
    date = nom[:10]
    territoire = nom[len(date) + len("-prospection-") : -3]
    texte = chemin.read_text("utf-8")
    sec = _sections(texte)
    m = RE_STRATEGIE.search(texte)
    col = RE_COLLECTE.search(texte)

    def lignes_table(nom_section: str) -> int:
        return sum(1 for li in sec.get(nom_section, []) if re.match(r"^\| \d+ \|", li))

    def puces(nom_section: str, prefixe: str = "- ") -> int:
        return sum(
            1 for li in sec.get(nom_section, []) if li.startswith(prefixe) and "_aucune_" not in li
        )

    notes = sec.get("Notes techniques", [])
    return {
        "fichier": nom,
        "date": date,
        "territoire": territoire,
        "strategie": m.group(1) if m else None,
        "statut_recette": m.group(2) if m else None,
        "collecte": (
            dict(
                zip(
                    ("trouvees", "deja_catalogue", "deja_file", "a_trier", "pages"),
                    map(int, col.groups()),
                    strict=True,
                )
            )
            if col
            else None
        ),
        "retenues": lignes_table("Candidates retenues"),
        "a_trancher": puces("À trancher à la main (destinataire ou objet indéterminé)"),
        "ecartees_test": puces("Écartées par le test du destinataire"),
        "ecartees_tri": puces("Écartées au tri, sans ouvrir la page"),
        "non_lues": sum(1 for li in notes if li.startswith("- non lue :")),
        "plafond_candidats": ("arrêt propre : plafond de" in texte)
        or ("Balayage plafonné" in texte),
        "plafond_pages": "découverte arrêtée au plafond de" in texte,
        "rejouee": "candidats.jsonl" in texte,
        "prefixes": next(
            (li for li in notes if li.startswith("- découverte : préfixes retenus")), None
        ),
    }


def fiches() -> list[dict]:
    return [analyser_fiche(p) for p in sorted(REVIEWS.glob("*-prospection-*.md"))]


def rendement(fs: list[dict]) -> dict:
    groupes: dict[str, list[dict]] = collections.defaultdict(list)
    for f in fs:
        g = "decouverte" if f["strategie"] == "decouverte" else "recettes"
        groupes[g].append(f)
    out = {}
    for g, lst in groupes.items():
        a_trier = sum(f["collecte"]["a_trier"] for f in lst)
        ret = sum(f["retenues"] for f in lst)
        tranch = sum(f["a_trancher"] for f in lst)
        zero = [f["territoire"] for f in lst if f["retenues"] == 0]
        nulles = [f["territoire"] for f in lst if f["collecte"]["a_trier"] == 0]
        zero_hors_nulles = [t for t in zero if t not in nulles]
        n_hors_nulles = len(lst) - len(nulles)
        # taux par fiche (grappe) : moyenne non pondérée et médiane
        par_fiche = [
            f["retenues"] / f["collecte"]["a_trier"] for f in lst if f["collecte"]["a_trier"]
        ]
        par_fiche.sort()
        mediane = par_fiche[len(par_fiche) // 2] if par_fiche else None
        out[g] = {
            "fiches": len(lst),
            "territoires_distincts": len({f["territoire"] for f in lst}),
            "a_trier": a_trier,
            "pages": sum(f["collecte"]["pages"] for f in lst),
            "retenues": taux(ret, a_trier),
            "retenues_plus_a_trancher": taux(ret + tranch, a_trier),
            "non_lues": sum(f["non_lues"] for f in lst),
            "fiches_zero_retenue": taux(len(zero), len(lst)),
            "fiches_collecte_nulle": nulles,
            "fiches_zero_retenue_hors_collecte_nulle": taux(len(zero_hors_nulles), n_hors_nulles),
            "taux_moyen_par_fiche_pct": round(100 * sum(par_fiche) / len(par_fiche), 1)
            if par_fiche
            else None,
            "taux_median_par_fiche_pct": round(100 * mediane, 1) if mediane is not None else None,
            "detail": [
                (f["date"], f["territoire"], f["collecte"]["a_trier"], f["retenues"]) for f in lst
            ],
        }
    return out


def permutation_grappes(detail_a: list, detail_b: list, n: int = 20000) -> dict:
    """Test de permutation au niveau de la fiche (grappe) sur l'écart de taux poolés."""
    import random

    rng = random.Random(20261010)

    def taux_poole(lst: list) -> float:
        a = sum(x[2] for x in lst)
        return sum(x[3] for x in lst) / a if a else 0.0

    # 1) écart des taux poolés (pondéré par les URL), fiches permutées
    obs = taux_poole(detail_b) - taux_poole(detail_a)
    tout = list(detail_a) + list(detail_b)
    na = len(detail_a)
    extremes = 0
    for _ in range(n):
        rng.shuffle(tout)
        if abs(taux_poole(tout[na:]) - taux_poole(tout[:na])) >= abs(obs) - 1e-12:
            extremes += 1
    # 2) test des rangs sur les taux par fiche (non pondéré), fiches à 0 à trier exclues
    ta = [x[3] / x[2] for x in detail_a if x[2]]
    tb = [x[3] / x[2] for x in detail_b if x[2]]
    valeurs = ta + tb
    ordre = sorted(range(len(valeurs)), key=lambda i: valeurs[i])
    rangs = [0.0] * len(valeurs)
    i = 0
    while i < len(ordre):
        j = i
        while j + 1 < len(ordre) and valeurs[ordre[j + 1]] == valeurs[ordre[i]]:
            j += 1
        for k in range(i, j + 1):
            rangs[ordre[k]] = (i + j) / 2 + 1
        i = j + 1
    ka = len(ta)

    def ecart_rangs(r: list[float]) -> float:
        return sum(r[ka:]) / len(tb) - sum(r[:ka]) / ka

    obs_r = ecart_rangs(rangs)
    ext_r = 0
    for _ in range(n):
        rng.shuffle(rangs)
        if abs(ecart_rangs(rangs)) >= abs(obs_r) - 1e-12:
            ext_r += 1
    return {
        "ecart_taux_poole_pts": round(100 * obs, 2),
        "p_bilateral_taux_poole": round((extremes + 1) / (n + 1), 4),
        "fiches_rangs": [ka, len(tb)],
        "p_bilateral_rangs_par_fiche": round((ext_r + 1) / (n + 1), 4),
    }


def vagues(fs: list[dict]) -> dict:
    comp = [f for f in fs if f["date"] in VAGUES_COMPARABLES]
    avec = [f for f in comp if f["collecte"]]
    somme = collections.Counter()
    for f in avec:
        somme.update(f["collecte"])
        for k in ("retenues", "a_trancher", "ecartees_test", "ecartees_tri", "non_lues"):
            somme[k] += f[k]
    terr = collections.Counter(f["territoire"] for f in avec)
    toutes = [f for f in fs if f["collecte"]]
    rps = rendement(avec)
    return {
        "test_permutation_fiches": permutation_grappes(
            rps["decouverte"]["detail"], rps["recettes"]["detail"]
        ),
        "fiches_comparables": len(comp),
        "avec_ligne_collecte": len(avec),
        "somme": dict(somme),
        "territoires_en_double": {t: n for t, n in terr.items() if n > 1},
        "plafond_candidats_toutes_fiches": taux(
            sum(f["plafond_candidats"] for f in toutes), len(toutes)
        ),
        "plafond_pages": sorted(
            (f["date"], f["territoire"], f["strategie"]) for f in fs if f["plafond_pages"]
        ),
        "fiches_decouverte_toutes_dates": sum(f["strategie"] == "decouverte" for f in fs),
        "fiches_avec_ligne_collecte_toutes_dates": len(toutes),
        "rendement_par_strategie": rendement(avec),
        "rendement_sans_09_28": rendement([f for f in avec if f["date"] != "2026-09-28"]),
        "rendement_derniere_fiche_par_territoire": rendement(
            list({f["territoire"]: f for f in sorted(avec, key=lambda f: f["date"])}.values())
        ),
    }


# --------------------------------------------------------------------------
# 3. Couverture par la file, et contre le catalogue
# --------------------------------------------------------------------------


def couverture() -> dict:
    t = yaml.safe_load((DATA / "prospection" / "territoires.yaml").read_text("utf-8"))
    file = yaml.safe_load((DATA / "prospection" / "file-attente.yaml").read_text("utf-8"))
    par_terr: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for v in file.values():
        par_terr[v["territoire"]][v["statut"]] += 1
    ingeres = {k for k, c in par_terr.items() if c["ingere"]}
    slugs = [Path(p).stem for p in glob.glob(str(DATA / "aides" / "*.yaml"))]
    ingere_sans_yaml = [
        s for s, v in file.items() if v["statut"] == "ingere" and s not in set(slugs)
    ]
    hors_file = {}
    for k, v in t.items():
        if k in ingeres:
            continue
        p = v["prefixe_slug"] + "-"
        n = [s for s in slugs if s.startswith(p) and s not in file]
        if n:
            hors_file[k] = n
    return {
        "file_taches": len(file),
        "file_statuts": dict(collections.Counter(v["statut"] for v in file.values())),
        "territoires_avec_ingere": len(ingeres),
        "dont_regions": sum(t[k]["type"] == "region" for k in ingeres),
        "ingere_sans_yaml": len(ingere_sans_yaml),
        "territoires_non_couverts_par_la_file_mais_au_catalogue": hors_file,
        "territoires_avec_aide_au_catalogue_prefixee": len(ingeres) + len(hors_file),
    }


# --------------------------------------------------------------------------
# 4. Candidats hors git : Moselle, boucles, pagination encodée
# --------------------------------------------------------------------------


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(li) for li in p.read_text("utf-8").splitlines() if li.strip()]


def candidats() -> dict:
    derniers: dict[str, Path] = {}
    for racine in SOURCES_CANDIDATS:
        for p in racine.glob("*/candidats.jsonl"):
            k = p.parent.name
            if k not in derniers or p.stat().st_mtime > derniers[k].stat().st_mtime:
                derniers[k] = p
    moselle = _jsonl(derniers["57"])
    urls57 = [c["url"] for c in moselle]

    def segs(u: str) -> list[str]:
        return [s for s in urlsplit(u).path.split("/") if s]

    def rep(u: str) -> int:
        s = segs(u)
        return max(collections.Counter(s).values()) if s else 0

    hors = [c["url"] for k, p in derniers.items() if k != "57" for c in _jsonl(p)]
    # pagination encodée : clés actuelles contre clés après décodage des crochets
    enc = [
        (k, c["url"])
        for k, p in derniers.items()
        if k != "57"
        for c in _jsonl(p)
        if "%5B" in c["url"].upper()
    ]
    pag_enc = [(k, u) for k, u in enc if re.search(r"currentpage|%40widget|pointer", u, re.I)]

    def decode(u: str) -> str:
        return u.replace("%5B", "[").replace("%5D", "]").replace("%5b", "[").replace("%5d", "]")

    par_terr_enc = collections.Counter(k for k, _ in pag_enc)
    return {
        "territoires_candidats": len(derniers),
        "moselle_n": len(urls57),
        "moselle_segments": dict(sorted(collections.Counter(len(segs(u)) for u in urls57).items())),
        "moselle_repetition_max": dict(collections.Counter(rep(u) for u in urls57)),
        "moselle_chemin_en_boucle": sum(chemin_en_boucle(u) for u in urls57),
        "moselle_repetition_seule": sum(rep(u) > 2 for u in urls57),
        "hors_moselle_n": len(hors),
        "hors_moselle_repetition_seule": sum(rep(u) > 2 for u in hors),
        "hors_moselle_repetition_ge_2": sum(rep(u) >= 2 for u in hors),
        "pagination_encodee_candidats": len(pag_enc),
        "pagination_encodee_par_territoire": dict(par_terr_enc),
        "pagination_encodee_cles_actuelles": len({cle_fiche(u) for _, u in pag_enc}),
        "pagination_encodee_cles_decodees": len({cle_fiche(decode(u)) for _, u in pag_enc}),
        "toutes_urls_crochets_encodes": len(enc),
        "exemples_pag_enc": [u for _, u in pag_enc[:4]],
    }


# --------------------------------------------------------------------------
# 5. Journal de la Moselle
# --------------------------------------------------------------------------


def journal_moselle() -> dict:
    p = REVIEWS / "logs" / "balayage" / "2026-09-18-0152-prospection-57.log"
    t = p.read_text("utf-8")
    lectures = re.findall(r"\[3/3\]\s+(\d+)/7704\s+(\S+)", t)
    return {
        "candidats": re.findall(r"(\d+) candidat\(s\) à trier", t),
        "lots_tri": len(re.findall(r"lot \d+/968", t)),
        "a_lire": re.findall(r"(\d+) page\(s\) à lire", t),
        "lectures": len(lectures),
        "lectures_par_verdict": dict(collections.Counter(v for _, v in lectures)),
        "derniere_seconde": re.findall(r"\((\d+) s\)", t)[-1],
    }


# --------------------------------------------------------------------------
# 6. Doublons : file et .yaml.echec
# --------------------------------------------------------------------------


def doublons() -> dict:
    file = yaml.safe_load((DATA / "prospection" / "file-attente.yaml").read_text("utf-8"))
    par_url = collections.defaultdict(list)
    par_cle = collections.defaultdict(list)
    for s, v in file.items():
        par_url[v["url"]].append(s)
        par_cle[cle_fiche(v["url"])].append(s)
    groupes = [g for g in par_url.values() if len(g) > 1]
    recents = [
        g for g in groupes if all(str(file[s].get("ajoute_le", "")) >= "2026-09-22" for s in g)
    ]
    recents_un = [
        g for g in groupes if any(str(file[s].get("ajoute_le", "")) >= "2026-09-22" for s in g)
    ]
    echecs = sorted(glob.glob(str(DATA / "aides" / "*.yaml.echec")))
    motifs = collections.Counter()
    doublon_url = []
    for p in echecs:
        slug = os.path.basename(p)[: -len(".yaml.echec")]
        v = file.get(slug)
        if v is None:
            motifs["(hors file)"] += 1
            continue
        mot = str(v.get("motif_ignore") or v.get("motif") or v.get("erreur") or "")
        if "doublon" in mot.lower():
            doublon_url.append(slug)
        motifs[v["statut"]] += 1
    return {
        "file_taches": len(file),
        "urls_brutes_distinctes": len(par_url),
        "cle_url_distinctes": len({cle_url(v["url"]) for v in file.values()}),
        "cle_fiche_distinctes": len(par_cle),
        "groupes_meme_url": len(groupes),
        "groupes_meme_url_tous_apres_09_22": len(recents),
        "groupes_meme_url_un_membre_apres_09_22": len(recents_un),
        "yaml_echec": len(echecs),
        "yaml_echec_statut_file": dict(motifs),
        "yaml_echec_motif_contient_doublon": len(doublon_url),
    }


def rappel_prefixes(fs: list[dict]) -> dict:
    """Rappel des préfixes de découverte, en séparant la référence circulaire.

    Une URL de la file posée PAR la fiche de découverte elle-même a été trouvée
    sous ces préfixes par construction : elle ne peut pas mesurer leur rappel.
    """
    from prospection.territoires import aides_existantes, charger_territoires

    from aides_schema import load_all_aides

    terr = charger_territoires()
    corpus = load_all_aides()
    file = yaml.safe_load((DATA / "prospection" / "file-attente.yaml").read_text("utf-8"))
    derniere: dict[str, dict] = {}
    for f in fs:
        if f["prefixes"] and f["strategie"] == "decouverte":
            derniere[f["territoire"]] = f
    tot = collections.Counter()
    lignes = []
    for cle, f in sorted(derniere.items()):
        prefs = re.findall(r"'([^']+)'", f["prefixes"].split(" — ")[0])
        if cle not in terr or not prefs:
            continue
        hotes = {urlsplit(p).netloc.removeprefix("www.") for p in prefs}
        fiche_rel = "data/reviews/" + f["fichier"]
        connues: dict[str, str] = {}
        for slug, a in aides_existantes(cle, terr[cle], corpus).items():
            if a.source.url_officielle:
                connues.setdefault(
                    a.source.url_officielle,
                    "catalogue_pipeline" if slug in file else "catalogue_hors_file",
                )
        for v in file.values():
            if v["territoire"] == cle and v["statut"] in ("ingere", "a_valider", "valide"):
                origine = "file_meme_fiche" if v.get("fiche") == fiche_rel else "file_autre_fiche"
                if connues.get(v["url"]) in (None, "catalogue_pipeline"):
                    connues[v["url"]] = origine
        for u, origine in connues.items():
            if urlsplit(u).netloc.removeprefix("www.") not in hotes:
                continue
            dedans = any(u.startswith(p) for p in prefs)
            tot[(origine, dedans)] += 1
            lignes.append((cle, origine, dedans, u))
    par_origine = {}
    for o in ("file_meme_fiche", "file_autre_fiche", "catalogue_pipeline", "catalogue_hors_file"):
        k, n = tot[(o, True)], tot[(o, True)] + tot[(o, False)]
        par_origine[o] = taux(k, n)
    k_ind = sum(tot[(o, True)] for o in par_origine if o != "file_meme_fiche")
    n_ind = sum(tot[(o, b)] for o in par_origine if o != "file_meme_fiche" for b in (True, False))
    k_all = sum(v for (o, b), v in tot.items() if b)
    n_all = sum(tot.values())
    return {
        "territoires": len(derniere),
        "total": taux(k_all, n_all),
        "hors_reference_circulaire": taux(k_ind, n_ind),
        "par_origine": par_origine,
        "territoires_hors_circulaire": len({c for c, o, _, _ in lignes if o != "file_meme_fiche"}),
        "par_territoire_hors_circulaire": {
            c: f"{sum(1 for c2, o, d, _ in lignes if c2 == c and o != 'file_meme_fiche' and d)}/"
            f"{sum(1 for c2, o, _, _ in lignes if c2 == c and o != 'file_meme_fiche')}"
            for c in sorted({c for c, o, _, _ in lignes if o != "file_meme_fiche"})
        },
        "hors_prefixe_hors_circulaire": [
            (c, o, u) for c, o, d, u in lignes if not d and o != "file_meme_fiche"
        ],
    }


def devenir_dans_la_file(fs: list[dict]) -> dict:
    """Statut actuel, dans la file, des tâches posées par les fiches des trois vagues."""
    file = yaml.safe_load((DATA / "prospection" / "file-attente.yaml").read_text("utf-8"))
    comp = {
        "data/reviews/" + f["fichier"]: f
        for f in fs
        if f["date"] in VAGUES_COMPARABLES and f["collecte"]
    }
    statuts: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for v in file.values():
        f = comp.get(v.get("fiche"))
        if f:
            g = "decouverte" if f["strategie"] == "decouverte" else "recettes"
            statuts[g][v["statut"]] += 1
    out = {}
    for g, c in statuts.items():
        n = sum(
            f["collecte"]["a_trier"]
            for f in comp.values()
            if (f["strategie"] == "decouverte") == (g == "decouverte")
        )
        out[g] = {
            "statuts": dict(c),
            "ingere_sur_a_trier": taux(c["ingere"], n),
            "ingere_ou_a_valider_sur_a_trier": taux(c["ingere"] + c["a_valider"], n),
        }
    return out


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    fs = fiches()
    res = {
        "recettes": recettes(),
        "fiches_total": len(fs),
        "vagues": vagues(fs),
        "couverture": couverture(),
        "candidats": candidats(),
        "journal_moselle": journal_moselle(),
        "doublons": doublons(),
        "rappel_prefixes": rappel_prefixes(fs),
        "devenir_dans_la_file": devenir_dans_la_file(fs),
    }
    (SORTIE / "recompte.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (SORTIE / "fiches.json").write_text(
        json.dumps(fs, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in res.items()}, ensure_ascii=False, indent=1)[:20000])


if __name__ == "__main__":
    main()
