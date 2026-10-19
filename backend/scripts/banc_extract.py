"""Banc d'Extract : les valeurs factuelles du catalogue se retrouvent-elles dans leur source ?

Pour chaque aide qui a un snapshot dans `data/sources/<slug>/`, ScaleDown
Extract relève dans la source les passages de six catégories (taux, montant
de l'aide, seuil ou plafond de dépense, plafond d'aides publiques, date limite,
date d'ouverture). Chaque valeur du YAML (`financement`, `cumul.plafond_public_pct`,
`calendrier.date_*`) est ensuite rangée :

- `accord` : un passage de la bonne catégorie porte cette valeur ;
- `partielle` (dates) : un passage de la bonne catégorie porte la date sans
  son année, ou sans son jour (« juillet 2026 ») ;
- `ailleurs` : seul un passage d'une autre catégorie la porte ;
- `absente` : Extract a relevé des passages de la bonne catégorie, aucun ne
  porte cette valeur ;
- `rien` : Extract n'a relevé aucun passage de la bonne catégorie.

En regard, le contrôle actuel de la veille (`controles.figure`) : la valeur
est-elle écrite quelque part dans la source ?

Le texte est celui de tous les snapshots les plus récents (pages et PDF), sans
la troncature à 25 000 caractères de la lecture : Extract lit un million de
jetons. Une réponse par aide, en cache dans
`data/reviews/logs/banc-extract/extract.jsonl` (hors git).

    uv run python scripts/banc_extract.py --echantillon 20
    uv run python scripts/banc_extract.py            # tout le stock, puis rapport

Ne modifie aucune aide : écrit le rapport `data/reviews/<date>-banc-extract.md`
et la liste des désaccords `data/reviews/logs/banc-extract/desaccords.json`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import statistics
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_destinataire import _FRONTMATTER, _derniers
from pipeline.llm import charger_env
from veille_collect import pdf_to_text

from catalogue.controles import figure, sans_accents

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
AIDES_DIR = DATA_DIR / "aides"
SOURCES_DIR = DATA_DIR / "sources"
REVIEWS_DIR = DATA_DIR / "reviews"
LOGS_DIR = REVIEWS_DIR / "logs" / "banc-extract"
CACHE = LOGS_DIR / "extract.jsonl"

URL = "https://openrouter.ai/api/v1/chat/completions"
MODELE = "scaledown/extract"
MAX_CAR = 400_000

# Les descriptions portent le sens exact : un plancher de dépense n'est pas un
# minimum d'aide, et Extract rendrait le même passage pour les deux.
CATEGORIES = {
    "taux de subvention": (
        "pourcentage de la dépense pris en charge par l'aide (taux de subvention, "
        "taux minimal ou maximal, taux d'aide)"
    ),
    "montant de l'aide": (
        "montant en euros de l'aide accordée au bénéficiaire (subvention minimale, "
        "maximale ou forfaitaire), pas le montant des travaux"
    ),
    "seuil de dépense": (
        "montant en euros de la dépense ou des travaux pris en compte : dépense "
        "minimale pour être éligible, plafond de dépense subventionnable, assiette"
    ),
    "plafond d'aides publiques": (
        "pourcentage maximal du projet que l'ensemble des aides publiques peut financer"
    ),
    "date limite de dépôt": (
        "date à laquelle les dossiers de demande doivent être déposés au plus tard "
        "(clôture de l'appel à projets ou du dépôt)"
    ),
    "date d'ouverture du dépôt": "date à partir de laquelle on peut déposer un dossier",
}

# Pour chaque champ du YAML : sa catégorie, et les autres où le chercher.
CHAMPS: dict[str, tuple[str, str]] = {
    "financement.taux_min": ("taux de subvention", "nombre"),
    "financement.taux_max": ("taux de subvention", "nombre"),
    "financement.montant_min": ("montant de l'aide", "nombre"),
    "financement.montant_max": ("montant de l'aide", "nombre"),
    "financement.plancher": ("seuil de dépense", "nombre"),
    "cumul.plafond_public_pct": ("plafond d'aides publiques", "nombre"),
    "calendrier.date_ouverture": ("date d'ouverture du dépôt", "date"),
    "calendrier.date_limite": ("date limite de dépôt", "date"),
}


# --------------------------------------------------------------------------
# Textes et valeurs
# --------------------------------------------------------------------------


def texte_complet(slug: str) -> str:
    d = SOURCES_DIR / slug
    morceaux: list[str] = []
    for f in _derniers(d.glob("*.md")):
        brut = f.read_text(encoding="utf-8", errors="replace")
        morceaux.append(f"## {f.name}\n\n{_FRONTMATTER.sub('', brut).strip()}")
    for f in _derniers(d.glob("*.pdf")):
        texte = pdf_to_text(f)
        if texte:
            morceaux.append(f"## {f.name}\n\n{texte.strip()}")
    return "\n\n".join(morceaux)[:MAX_CAR]


def valeurs_yaml(slug: str) -> dict[str, Any]:
    y = yaml.safe_load((AIDES_DIR / f"{slug}.yaml").read_text(encoding="utf-8")) or {}
    sortie: dict[str, Any] = {}
    for chemin in CHAMPS:
        section, cle = chemin.split(".")
        v = (y.get(section) or {}).get(cle)
        if v is not None and not isinstance(v, bool):
            sortie[chemin] = v
    return sortie


def aides_a_tester() -> list[str]:
    return [
        f.stem
        for f in sorted(AIDES_DIR.glob("*.yaml"))
        if (SOURCES_DIR / f.stem).is_dir() and valeurs_yaml(f.stem)
    ]


_NOMBRE = re.compile(r"\d{1,3}(?:[   .]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?")
_MULT = re.compile(r"^\s*(millions?|m\s*€|m€|md|milliards?|k\s*€|k€|keur|meur)", re.I)


def nombres(passage: str) -> set[float]:
    """Les nombres d'un passage : « 150 000 € », « 1,5 M€ », « 20% », « 80000 »."""
    sortie: set[float] = set()
    for m in _NOMBRE.finditer(passage):
        brut = m.group()
        if re.fullmatch(r"\d{1,3}(?:[   .]\d{3})+(?:,\d+)?", brut):
            n = float(re.sub(r"[   .]", "", brut).replace(",", "."))
        else:
            n = float(brut.replace(",", "."))
        suite = _MULT.match(passage[m.end() :])
        if suite:
            mot = suite.group(1).lower()
            n *= 1e9 if mot.startswith(("md", "milliard")) else 1e3 if "k" in mot else 1e6
        sortie.add(round(n, 4))
    return sortie


# Noms de mois, sans accents : formes longues et abrégées, français et anglais
# (des appels européens sont rédigés en anglais).
NOMS_MOIS = {
    1: "janvier|janv|january|jan",
    2: "fevrier|fevr|fev|february|feb",
    3: "mars|march",
    4: "avril|avr|april|apr",
    5: "mai|may",
    6: "juin|june",
    7: "juillet|juil|july",
    8: "aout|august|aug",
    9: "septembre|sept|september|sep",
    10: "octobre|oct|october",
    11: "novembre|nov|november",
    12: "decembre|dec|december",
}
_MOIS = "|".join(f"(?P<m{n}>{v})" for n, v in NOMS_MOIS.items())
_DATE_MOIS = re.compile(
    rf"\b(?:(?P<jour>1er|\d{{1,2}})(?:st|nd|rd|th)?\s+)?(?:{_MOIS})\b\.?(?:\s+(?P<annee>\d{{4}}))?"
)
_DATE_ANGLAISE = re.compile(rf"\b(?:{_MOIS})\s+(?P<jour>\d{{1,2}}),?\s+(?P<annee>\d{{4}})")
_DATE_NUM = re.compile(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4}|\d{2})\b")
_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

Date = tuple[int | None, int, int | None]  # année, mois, jour ; None : non écrit


def _mois(m: re.Match[str]) -> int:
    return next(n for n in NOMS_MOIS if m.group(f"m{n}"))


def dates(passage: str, annees_ecrites: str | None = None) -> set[Date]:
    """Les dates d'un passage, avec ce qui en est réellement écrit.

    Extract normalise parfois une date en ISO et en invente l'année (« avant le
    9 novembre » rendu « 2025-11-09 ») : une année ISO absente de
    `annees_ecrites` (la source autour du passage) ne compte pas.
    """
    p = sans_accents(passage)
    sortie: set[Date] = set()
    for rx in (_DATE_MOIS, _DATE_ANGLAISE):
        for m in rx.finditer(p):
            jour = m.group("jour")
            annee = m.group("annee")
            if not jour and not annee:
                continue  # un nom de mois seul : « mai » n'est pas une date
            sortie.add(
                (
                    int(annee) if annee else None,
                    _mois(m),
                    (1 if jour == "1er" else int(jour)) if jour else None,
                )
            )
    for m in _DATE_NUM.finditer(p):
        a = int(m.group(3))
        sortie.add((a + 2000 if a < 100 else a, int(m.group(2)), int(m.group(1))))
    for m in _DATE_ISO.finditer(p):
        annee = m.group(1) if annees_ecrites is None or m.group(1) in annees_ecrites else None
        sortie.add((int(annee) if annee else None, int(m.group(2)), int(m.group(3))))
    return sortie


def classer(
    valeur: Any, nature: str, cat: str, entites: list[dict[str, Any]], texte: str = ""
) -> str:
    par_cat: dict[str, list[dict[str, Any]]] = {}
    for e in entites:
        par_cat.setdefault(e["type"], []).append(e)
    if nature == "date":
        d = valeur if isinstance(valeur, dt.date) else dt.date.fromisoformat(str(valeur))

        def porte(es: list[dict[str, Any]]) -> str | None:
            ds: set[Date] = set()
            for e in es:
                autour = (
                    texte[max(0, (e["start"] or 0) - 80) : (e["end"] or 0) + 80] if texte else None
                )
                ds |= dates(e["text"], autour)
            if (d.year, d.month, d.day) in ds:
                return "accord"
            if (None, d.month, d.day) in ds or (d.year, d.month, None) in ds:
                return "partielle"
            return None
    else:
        v = round(float(valeur), 4)

        def porte(es: list[dict[str, Any]]) -> str | None:
            return "accord" if any(v in nombres(e["text"]) for e in es) else None

    if r := porte(par_cat.get(cat, [])):
        return r
    if porte([e for c, es in par_cat.items() if c != cat for e in es]):
        return "ailleurs"
    return "absente" if par_cat.get(cat) else "rien"


# --------------------------------------------------------------------------
# Appel
# --------------------------------------------------------------------------

_verrou = threading.Lock()


def lire_cache() -> dict[str, dict[str, Any]]:
    sortie: dict[str, dict[str, Any]] = {}
    if CACHE.exists():
        for ligne in CACHE.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                r = json.loads(ligne)
                sortie[r["slug"]] = r
    return sortie


def extraire(http: httpx.Client, slug: str) -> dict[str, Any]:
    texte = texte_complet(slug)
    corps = {
        "model": MODELE,
        "messages": [{"role": "user", "content": texte}],
        "provider": {"options": {"scaledown": {"entities": CATEGORIES}}},
    }
    derniere = ""
    for n in range(4):
        debut = time.monotonic()
        r = http.post(URL, json=corps)
        if r.status_code == 200:
            data = r.json()
            contenu = json.loads(data["choices"][0]["message"]["content"])
            return {
                "slug": slug,
                "modele": data.get("model"),
                "car": len(texte),
                "entites": [
                    {k: e.get(k) for k in ("type", "text", "confidence", "start", "end")}
                    for e in contenu.get("entities") or []
                ],
                "cout_usd": (data.get("usage") or {}).get("cost"),
                "latence_s": round(time.monotonic() - debut, 2),
            }
        derniere = f"HTTP {r.status_code} : {r.text[:300]}"
        if r.status_code not in (408, 429, 500, 502, 503, 504):
            break
        time.sleep(2**n)
    raise RuntimeError(derniere)


def faire(slugs: list[str], parallele: int) -> None:
    deja = lire_cache()
    a_faire = [s for s in slugs if s not in deja]
    print(f"{len(a_faire)} aides à extraire ({len(slugs) - len(a_faire)} en cache)")
    cle = os.environ["OPENROUTER_API_KEY"]
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with (
        httpx.Client(timeout=300, headers={"Authorization": f"Bearer {cle}"}) as http,
        ThreadPoolExecutor(max_workers=parallele) as pool,
    ):
        futurs = {pool.submit(extraire, http, s): s for s in a_faire}
        for i, f in enumerate(as_completed(futurs), 1):
            try:
                r = f.result()
            except Exception as exc:  # noqa: BLE001 — une aide ratée ne tue pas le banc
                print(f"✗ {futurs[f]} : {exc}")
                continue
            with _verrou, CACHE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            if i % 25 == 0:
                print(f"{i}/{len(a_faire)}", flush=True)


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------

ISSUES = ("accord", "partielle", "ailleurs", "absente", "rien")


def rapport(slugs: list[str]) -> tuple[str, list[dict[str, Any]]]:
    cache = lire_cache()
    lignes_par_champ: dict[str, Counter[str]] = {c: Counter() for c in CHAMPS}
    desaccords: list[dict[str, Any]] = []
    jugees = [s for s in slugs if s in cache]
    for slug in jugees:
        r = cache[slug]
        brut = texte_complet(slug)
        texte = sans_accents(brut)
        for chemin, valeur in valeurs_yaml(slug).items():
            cat, nature = CHAMPS[chemin]
            issue = classer(valeur, nature, cat, r["entites"], brut)
            fig = figure(valeur, texte)
            lignes_par_champ[chemin][issue] += 1
            lignes_par_champ[chemin]["figure" if fig else "figure_non"] += 1
            if issue not in ("accord", "partielle"):
                desaccords.append(
                    {
                        "slug": slug,
                        "champ": chemin,
                        "valeur": str(valeur),
                        "issue": issue,
                        "figure": fig,
                        "candidats": [
                            f"{e['text']} ({e['confidence']:.2f})"
                            for e in r["entites"]
                            if e["type"] == cat
                        ][:8],
                    }
                )
    couts = [cache[s].get("cout_usd") or 0 for s in jugees]
    lat = [cache[s].get("latence_s") or 0 for s in jugees]
    lignes = [
        f"# Banc d'Extract sur les valeurs du catalogue, {date.today().isoformat()}",
        "",
        f"{len(jugees)} aides avec snapshot et au moins une valeur, sur {len(slugs)}. "
        f"Modèle `{MODELE}` via OpenRouter, tous les snapshots les plus récents (pages et "
        f"PDF), {MAX_CAR} caractères au plus. Coût total ${sum(couts):.3f}, latence "
        f"médiane {statistics.median(lat) if lat else 0:.1f} s.",
        "",
        "`accord` : un passage de la bonne catégorie porte la valeur ; `partielle` : date "
        "sans année ou sans jour ; `ailleurs` : seulement un passage d'une autre catégorie ; "
        "`absente` : des passages de la bonne catégorie, aucun ne la porte ; `rien` : aucun "
        "passage de la bonne catégorie. « figure » : le contrôle actuel de la veille, la "
        "valeur écrite quelque part dans la source.",
        "",
        "| champ | valeurs | accord | partielle | ailleurs | absente | rien | figure |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    total: Counter[str] = Counter()
    for chemin, c in lignes_par_champ.items():
        n = sum(c[i] for i in ISSUES)
        if not n:
            continue
        total.update(c)
        lignes.append(
            f"| `{chemin}` | {n} | "
            + " | ".join(f"{c[i]} ({100 * c[i] / n:.0f} %)" for i in ISSUES)
            + f" | {c['figure']} ({100 * c['figure'] / n:.0f} %) |"
        )
    n = sum(total[i] for i in ISSUES)
    if n:
        lignes.append(
            f"| **total** | {n} | "
            + " | ".join(f"{total[i]} ({100 * total[i] / n:.0f} %)" for i in ISSUES)
            + f" | {total['figure']} ({100 * total['figure'] / n:.0f} %) |"
        )
    croise = Counter((d["issue"], d["figure"]) for d in desaccords)
    lignes += [
        "",
        "Désaccords selon le contrôle actuel :",
        "",
        "| issue | la valeur figure dans la source | n'y figure pas |",
        "|---|---:|---:|",
    ]
    for i in ("ailleurs", "absente", "rien"):
        lignes.append(f"| {i} | {croise[(i, True)]} | {croise[(i, False)]} |")
    lignes.append("")
    return "\n".join(lignes), desaccords


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="banc_extract.py", description=__doc__)
    p.add_argument("--echantillon", type=int)
    p.add_argument("--parallele", type=int, default=8)
    p.add_argument("--rapport-seul", action="store_true")
    args = p.parse_args(argv)
    charger_env()
    slugs = aides_a_tester()
    if args.echantillon:
        slugs = random.Random(0).sample(slugs, args.echantillon)
    print(f"{len(slugs)} aides")
    if not args.rapport_seul:
        faire(slugs, args.parallele)
    texte, desaccords = rapport(slugs)
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    chemin = REVIEWS_DIR / f"{date.today().isoformat()}-banc-extract.md"
    chemin.write_text(texte + "\n", encoding="utf-8")
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "desaccords.json").write_text(
        json.dumps(desaccords, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"rapport : {chemin.relative_to(BACKEND_DIR)} ; {len(desaccords)} désaccords")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
