"""Banc d'essai du test du destinataire : Jev contre le modèle de lecture.

La question posée : un modèle de DÉCISION (Jev, cf. `pipeline/decision.py`),
qui rend des probabilités au lieu d'un verdict, trie-t-il les aides mieux que
le LLM de l'étage de lecture — et surtout, existe-t-il des seuils au-delà
desquels il ne se trompe presque jamais ? Si oui, tout ce qui tombe hors de la
bande du milieu n'a plus besoin de passer sous les yeux d'un humain.

**La vérité terrain est HUMAINE, jamais un verdict de modèle** :

- gardée : `data/aides/<slug>.yaml` présent dans HEAD — le diff relu avant le
  commit est la revue ;
- écartée : `<slug>.yaml.echec` dont la tâche de la file porte un motif
  « test du destinataire : … » (fiche de requalification validée puis
  appliquée) ou « tri humain du … », doublons exclus : un doublon est écarté
  pour sa redondance, pas pour son destinataire.

Les deux ont un snapshot dans `data/sources/<slug>/`, qui est aussi le texte
sur lequel l'humain a jugé. Les deux modèles lisent exactement ce texte,
tronqué comme à la lecture (`MAX_CAR_PAGE`).

Chaque réponse est mise en cache (`data/reviews/logs/benchmark-destinataire/`,
hors git) : relancer ne repaie rien, et le rapport se régénère seul.

    uv run python scripts/benchmark_destinataire.py --dry-run
    uv run python scripts/benchmark_destinataire.py --jev --echantillon 40
    uv run python scripts/benchmark_destinataire.py --jev --llm
    uv run python scripts/benchmark_destinataire.py          # rapport seul

Ne modifie aucune aide, aucune tâche de la file : le seul fichier versionné
qu'il écrit est le rapport `data/reviews/<date>-benchmark-destinataire.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import statistics
import subprocess
import sys
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.decision import ClientDecision, ErreurDecision
from pipeline.etat import FILE_ATTENTE
from pipeline.llm import charger_env, client_pour
from prospection import arbitre
from prospection.lecture import MAX_CAR_PAGE, LectureFiche, consigne
from veille_collect import pdf_to_text

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
AIDES_DIR = DATA_DIR / "aides"
SOURCES_DIR = DATA_DIR / "sources"
REVIEWS_DIR = DATA_DIR / "reviews"
CACHE_DIR = REVIEWS_DIR / "logs" / "benchmark-destinataire"

# En dessous, le texte des pages archivées ne dit rien (SPA, bandeau seul) :
# on y ajoute alors le texte des PDF, comme la lecture le ferait d'un règlement.
SEUIL_TEXTE_PAGES = 1500

# Plafond toléré pour fixer les seuils : 1 % d'erreurs de chaque côté. Zéro
# absolu, sur quelques centaines de cas, ne mesurerait que le pire étiquetage.
TOLERANCE = 0.01


# --------------------------------------------------------------------------
# Le jeu étiqueté
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Cas:
    slug: str
    garde: bool
    # `prospection` : passé par la file d'attente (balayages de septembre) ;
    # `catalogue` : ingéré avant, à la main, par le skill. Les seconds sont
    # surtout des aides de restauration, plus faciles : le rapport sépare.
    origine: str
    motif: str = ""


def _slugs_dans_head() -> set[str]:
    sortie = subprocess.run(
        ["git", "ls-tree", "--name-only", "HEAD", "data/aides/"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {Path(p).name.removesuffix(".yaml") for p in sortie.split() if p.endswith(".yaml")}


def _a_un_snapshot(slug: str) -> bool:
    d = SOURCES_DIR / slug
    return d.is_dir() and any(f.suffix in (".md", ".pdf") for f in d.iterdir())


def cas_etiquetes() -> list[Cas]:
    file_attente: dict[str, dict[str, Any]] = yaml.safe_load(FILE_ATTENTE.read_text()) or {}
    gardes = _slugs_dans_head()
    cas = [
        Cas(s, True, "prospection" if s in file_attente else "catalogue")
        for s in sorted(gardes)
        if _a_un_snapshot(s)
    ]
    for slug, tache in sorted(file_attente.items()):
        motif = tache.get("motif_ignore") or ""
        if tache.get("statut") != "ignore" or "oublon" in motif:
            continue
        if not motif.startswith(("test du destinataire", "tri humain")):
            continue
        if slug in gardes or not (AIDES_DIR / f"{slug}.yaml.echec").exists():
            continue
        if _a_un_snapshot(slug):
            cas.append(Cas(slug, False, "prospection", motif))
    return cas


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)


def _rang(nom: str) -> tuple[int, str]:
    """La page de présentation d'abord, puis le règlement, puis le reste."""
    for i, mot in enumerate(("presentation", "dispositif", "reglement")):
        if mot in nom:
            return (i, nom)
    return (9, nom)


def _derniers(fichiers: Iterable[Path]) -> list[Path]:
    """Le snapshot le plus récent de chaque document (la veille ré-archive)."""
    par_nom: dict[str, Path] = {}
    for f in sorted(fichiers):  # trié par date : le dernier écrase
        par_nom[_DATE.sub("", f.name)] = f
    return sorted(par_nom.values(), key=lambda f: _rang(_DATE.sub("", f.name)))


def texte_du_snapshot(slug: str) -> tuple[str, str]:
    """(url de la source principale, texte à juger) tiré de `data/sources/<slug>/`."""
    d = SOURCES_DIR / slug
    url = ""
    morceaux: list[str] = []
    for f in _derniers(d.glob("*.md")):
        brut = f.read_text(encoding="utf-8", errors="replace")
        if not url and (m := re.search(r"^url: (\S+)", brut, re.M)):
            url = m.group(1)
        morceaux.append(f"## {f.name}\n\n{_FRONTMATTER.sub('', brut).strip()}")
    if sum(len(m) for m in morceaux) < SEUIL_TEXTE_PAGES:
        for f in _derniers(d.glob("*.pdf")):
            texte = pdf_to_text(f)
            if texte:
                morceaux.append(f"## {f.name}\n\n{texte.strip()}")
    return url, "\n\n".join(morceaux)[:MAX_CAR_PAGE]


# --------------------------------------------------------------------------
# Les deux juges
# --------------------------------------------------------------------------

# Les questions et la doctrine sont celles de la production : mesurer autre
# chose que ce qui tourne ne servirait à rien.
QUESTIONS_JEV = arbitre.QUESTIONS


def juge_jev(client: ClientDecision) -> Callable[[Cas], dict[str, Any]]:
    def juger(cas: Cas) -> dict[str, Any]:
        url, texte = texte_du_snapshot(cas.slug)
        d = client.decider(arbitre.etat(url, texte), QUESTIONS_JEV)
        return {
            "modele": d.modele,
            "reponses": {k: d.brut["answers"][k] for k in QUESTIONS_JEV},
            "cout_usd": d.cout_usd,
            "jetons_entree": d.jetons_entree,
            "latence_s": round(d.latence_s, 3),
        }

    return juger


def juge_llm(modele: str | None) -> Callable[[Cas], dict[str, Any]]:
    """Le juge de production : même consigne, même schéma que `lecture.lire`."""
    client = client_pour("lecture", modele)
    systeme = consigne()

    def juger(cas: Cas) -> dict[str, Any]:
        url, texte = texte_du_snapshot(cas.slug)
        prompt = "\n\n".join(
            [
                f"URL : {url}",
                "Documents liés depuis cette page (les seuls que tu peux citer dans "
                "`urls_pdf`) :\n  (aucun)",
                "--- Contenu de la page ---",
                texte,
            ]
        )
        essai = client.try_complete_json(LectureFiche, prompt, system=systeme)
        if essai.data is None:
            raise RuntimeError(f"lecture impossible : {essai.response.error}")
        f = essai.data
        return {
            "modele": essai.response.model,
            "destinataire": f.destinataire,
            "objet": f.objet,
            "categorie_ecart": f.categorie_ecart,
            "retenir": f.retenir,
            "indeterminee": f.indeterminee,
            "cout_usd": essai.response.cost_usd,
            "jetons_entree": essai.response.usage.input_tokens,
            "latence_s": round(essai.response.latency_s, 3),
        }

    return juger


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------

_verrou_cache = threading.Lock()


def lire_cache(juge: str) -> dict[str, dict[str, Any]]:
    chemin = CACHE_DIR / f"{juge}.jsonl"
    resultats: dict[str, dict[str, Any]] = {}
    if chemin.exists():
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                r = json.loads(ligne)
                resultats[r["slug"]] = r  # la dernière ligne d'un slug fait foi
    return resultats


def ecrire_cache(juge: str, resultat: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with _verrou_cache, (CACHE_DIR / f"{juge}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(resultat, ensure_ascii=False) + "\n")


def faire_juger(
    nom: str, juger: Callable[[Cas], dict[str, Any]], cas: list[Cas], parallele: int
) -> None:
    deja = lire_cache(nom)
    a_faire = [c for c in cas if c.slug not in deja]
    print(f"[{nom}] {len(a_faire)} cas à juger ({len(cas) - len(a_faire)} déjà en cache)")
    erreurs = 0
    with ThreadPoolExecutor(max_workers=parallele) as pool:
        futurs = {pool.submit(juger, c): c for c in a_faire}
        for i, futur in enumerate(as_completed(futurs), 1):
            c = futurs[futur]
            try:
                r = futur.result()
            except ErreurDecision as exc:
                if exc.statut == 402:
                    print(f"[{nom}] crédits épuisés : arrêt ({exc})")
                    pool.shutdown(cancel_futures=True)
                    break
                erreurs += 1
                print(f"[{nom}] ✗ {c.slug} : {exc}")
                continue
            except Exception as exc:  # noqa: BLE001 — un cas raté ne tue pas le banc
                erreurs += 1
                print(f"[{nom}] ✗ {c.slug} : {exc}")
                continue
            ecrire_cache(nom, {"slug": c.slug, **r})
            if i % 25 == 0:
                print(f"[{nom}] {i}/{len(a_faire)}", flush=True)
    print(f"[{nom}] terminé, {erreurs} erreur(s)")


# --------------------------------------------------------------------------
# Mesures
# --------------------------------------------------------------------------


def _proba(reponse: dict[str, Any], option: str) -> float:
    if reponse.get("type") == "noul":
        return float(reponse["noul"]) if option == "true" else 1.0 - float(reponse["noul"])
    return float((reponse.get("probabilities") or {}).get(option, 0.0))


def scores_jev(r: dict[str, Any]) -> dict[str, float]:
    """Deux façons de dériver « retenir » des réponses de Jev.

    `structure` reproduit `etat.retenir` en probabilités : destinataire
    propriétaire × objet sur le lieu × page qui est un dispositif (les trois
    supposés indépendants, ce qui est faux mais monotone). `deposable` est la
    question opérante du skill, posée d'un bloc.
    """
    rep = r["reponses"]
    p_dest = _proba(rep["destinataire"], "proprietaire_gestionnaire")
    p_objet = _proba(rep["objet"], "bien_ou_lieu") + _proba(rep["objet"], "activite_dans_le_lieu")
    p_disp = _proba(rep["dispositif"], "true")
    return {
        "structure": p_dest * p_objet * p_disp,
        "deposable": _proba(rep["deposable"], "true"),
    }


def auc(couples: list[tuple[float, bool]]) -> float:
    """Probabilité qu'une gardée tirée au hasard soit mieux notée qu'une écartée."""
    pos = [s for s, g in couples if g]
    neg = [s for s, g in couples if not g]
    if not pos or not neg:
        return float("nan")
    gagne = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return gagne / (len(pos) * len(neg))


@dataclass(frozen=True)
class Bandes:
    bas: float  # en dessous : écartée sans humain
    haut: float  # au-dessus : retenue sans humain


def ajuster(couples: list[tuple[float, bool]], tolerance: float = TOLERANCE) -> Bandes:
    """Les seuils les plus ouverts qui restent sous `tolerance` d'erreurs de chaque côté.

    `bas` : le plus haut seuil tel que les gardées qu'il écarterait pèsent au
    plus `tolerance` des gardées. `haut` : le plus bas tel que les écartées
    qu'il retiendrait pèsent au plus `tolerance` des écartées.
    """
    pos = sorted(s for s, g in couples if g)
    neg = sorted((s for s, g in couples if not g), reverse=True)
    k_pos = int(tolerance * len(pos))
    k_neg = int(tolerance * len(neg))
    bas = pos[k_pos] if k_pos < len(pos) else 1.0  # strictement en dessous : écartée
    haut = neg[k_neg] if k_neg < len(neg) else 0.0  # strictement au-dessus : retenue
    return Bandes(bas=bas, haut=max(haut, bas))


def ajuster_a_charge(couples: list[tuple[float, bool]], part_humaine: float) -> Bandes:
    """Les seuils qui minimisent les erreurs quand l'humain voit au plus `part_humaine`.

    C'est la comparaison juste avec le LLM : à charge de relecture égale, qui
    se trompe le moins ? Les deux taux d'erreur pèsent autant, rapportés
    chacun à sa population.
    """
    pts = sorted(couples)
    n = len(pts)
    taille = max(1, int(part_humaine * n))
    n_g = sum(g for _, g in pts) or 1
    n_e = (n - sum(g for _, g in pts)) or 1
    gardees_avant = [0]
    for _, g in pts:
        gardees_avant.append(gardees_avant[-1] + g)
    meilleur: tuple[float, int] | None = None
    for i in range(n - taille + 1):
        j = i + taille  # la bande du milieu couvre pts[i:j]
        ecartees_a_tort = gardees_avant[i]
        retenues_a_tort = (n - j) - (gardees_avant[n] - gardees_avant[j])
        cout = ecartees_a_tort / n_g + retenues_a_tort / n_e
        if meilleur is None or cout < meilleur[0]:
            meilleur = (cout, i)
    assert meilleur is not None
    i = meilleur[1]
    return Bandes(bas=pts[i][0], haut=pts[i + taille - 1][0])


def appliquer(couples: list[tuple[float, bool]], b: Bandes) -> dict[str, int]:
    n = {"ecartees_a_tort": 0, "retenues_a_tort": 0, "milieu": 0, "auto_juste": 0}
    for s, g in couples:
        if s < b.bas:
            n["ecartees_a_tort" if g else "auto_juste"] += 1
        elif s > b.haut:
            n["auto_juste" if g else "retenues_a_tort"] += 1
        else:
            n["milieu"] += 1
    return n


def _moitie(slug: str) -> int:
    return int(hashlib.sha256(slug.encode()).hexdigest(), 16) % 2


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------


def _pct(n: int, total: int) -> str:
    return f"{n} ({100 * n / total:.1f} %)" if total else "0"


def rapport(cas: list[Cas], jev: dict[str, dict[str, Any]], llm: dict[str, dict[str, Any]]) -> str:
    par_slug = {c.slug: c for c in cas}
    lignes: list[str] = [f"# Banc d'essai du test du destinataire, {date.today().isoformat()}", ""]
    n_g = sum(c.garde for c in cas)
    lignes += [
        "Vérité terrain humaine : gardée = `.yaml` dans HEAD ; écartée = `.yaml.echec` "
        "avec motif « test du destinataire » (requalification validée) ou « tri humain ». "
        "Chaque modèle lit le snapshot de `data/sources/<slug>/`, tronqué à "
        f"{MAX_CAR_PAGE} caractères.",
        "",
        f"Jeu : **{len(cas)} aides**, {n_g} gardées, {len(cas) - n_g} écartées.",
        f"Jugées : Jev {len(jev)}, LLM de lecture {len(llm)}.",
        "",
    ]

    # --- LLM de lecture : trois issues, comme en production
    if llm:
        rs = [(par_slug[s], r) for s, r in llm.items() if s in par_slug]
        modeles = sorted({r["modele"] for _, r in rs})
        g = [r for c, r in rs if c.garde]
        e = [r for c, r in rs if not c.garde]
        lignes += [
            f"## LLM de lecture ({', '.join(modeles)})",
            "",
            "Issue de production : `retenir` calculé, `indeterminee` renvoyée à un humain, "
            "le reste écarté.",
            "",
            "| | gardées | écartées |",
            "|---|---:|---:|",
            f"| retenues | {_pct(sum(r['retenir'] for r in g), len(g))} "
            f"| **{_pct(sum(r['retenir'] for r in e), len(e))}** |",
            f"| indéterminées (humain) | {_pct(sum(r['indeterminee'] for r in g), len(g))} "
            f"| {_pct(sum(r['indeterminee'] for r in e), len(e))} |",
            f"| écartées | **{_pct(sum(not r['retenir'] and not r['indeterminee'] for r in g), len(g))}** "
            f"| {_pct(sum(not r['retenir'] and not r['indeterminee'] for r in e), len(e))} |",
            "",
            f"Coût : ${sum(r.get('cout_usd') or 0 for _, r in rs):.4f} pour {len(rs)} cas.",
            "",
        ]

    # --- Jev : séparation, calibration, bandes
    if jev:
        rs = [(par_slug[s], r, scores_jev(r)) for s, r in jev.items() if s in par_slug]
        modeles = sorted({r["modele"] for _, r, _ in rs})
        lignes += [f"## Jev ({', '.join(modeles)})", ""]
        lignes += [
            "AUC : probabilité qu'une gardée prise au hasard soit mieux notée qu'une "
            "écartée (0,5 = hasard, 1 = séparation parfaite).",
            "",
            "| score | AUC (tout) | AUC (prospection seule) |",
            "|---|---:|---:|",
        ]
        for nom in ("structure", "deposable"):
            tout = [(sc[nom], c.garde) for c, _, sc in rs]
            prosp = [(sc[nom], c.garde) for c, _, sc in rs if c.origine == "prospection"]
            lignes.append(f"| `{nom}` | {auc(tout):.3f} | {auc(prosp):.3f} |")
        lignes.append("")

        for nom in ("structure", "deposable"):
            couples = [(sc[nom], c.garde) for c, _, sc in rs]
            # Seuils ajustés sur une moitié, mesurés sur l'autre : sinon on
            # mesure seulement l'ajustement.
            a = [
                (s, g)
                for (s, g), (c, _, _) in zip(couples, rs, strict=True)
                if _moitie(c.slug) == 0
            ]
            b = [
                (s, g)
                for (s, g), (c, _, _) in zip(couples, rs, strict=True)
                if _moitie(c.slug) == 1
            ]
            bandes = ajuster(a)
            n = appliquer(b, bandes)
            gb = sum(g for _, g in b)
            lignes += [
                f"### Bandes sur `{nom}`",
                "",
                f"Seuils ajustés sur une moitié du jeu ({len(a)} cas, tolérance "
                f"{TOLERANCE:.0%} d'erreurs de chaque côté) : écartée sous "
                f"**{bandes.bas:.3f}**, retenue au-dessus de **{bandes.haut:.3f}**. "
                f"Mesurés sur l'autre moitié ({len(b)} cas) :",
                "",
                "| issue | cas |",
                "|---|---:|",
                f"| tranchés seuls et justes | {_pct(n['auto_juste'], len(b))} |",
                f"| bande du milieu (humain) | {_pct(n['milieu'], len(b))} |",
                f"| gardées écartées à tort | **{_pct(n['ecartees_a_tort'], gb)}** des gardées |",
                f"| écartées retenues à tort | **{_pct(n['retenues_a_tort'], len(b) - gb)}** des écartées |",
                "",
            ]

        couples = [(sc["deposable"], c.garde) for c, _, sc in rs]
        lignes += [
            "### Calibration de `deposable`",
            "",
            "Si Jev est calibré, la part de gardées dans chaque tranche suit la probabilité annoncée.",
            "",
            "| probabilité annoncée | cas | part de gardées |",
            "|---|---:|---:|",
        ]
        for i in range(10):
            lo, hi = i / 10, (i + 1) / 10
            tranche = [g for s, g in couples if lo <= s < hi or (i == 9 and s == 1.0)]
            if tranche:
                lignes.append(
                    f"| {lo:.1f} – {hi:.1f} | {len(tranche)} | {100 * sum(tranche) / len(tranche):.0f} % |"
                )
        lignes.append("")

        lat = [r["latence_s"] for _, r, _ in rs if r.get("latence_s")]
        cout = sum(r.get("cout_usd") or 0 for _, r, _ in rs)
        lignes += [
            f"Coût : ${cout:.4f} pour {len(rs)} cas ; latence médiane "
            f"{statistics.median(lat):.2f} s."
            if lat
            else "",
            "",
        ]

        # Les désaccords les plus francs : soit Jev se trompe, soit l'étiquette.
        def _ligne(c: Cas, sc: dict[str, float]) -> str:
            llm_r = llm.get(c.slug)
            v = "—"
            if llm_r:
                v = (
                    "retenue"
                    if llm_r["retenir"]
                    else "indét."
                    if llm_r["indeterminee"]
                    else "écartée"
                )
            return f"| `{c.slug}` | {sc['deposable']:.2f} | {sc['structure']:.2f} | {v} | {c.motif[:70]} |"

        gardees = sorted((x for x in rs if x[0].garde), key=lambda x: x[2]["deposable"])[:15]
        ecartees = sorted((x for x in rs if not x[0].garde), key=lambda x: -x[2]["deposable"])[:15]
        entete = [
            "| slug | deposable | structure | LLM | motif humain |",
            "|---|---:|---:|---|---|",
        ]
        lignes += ["### Gardées que Jev écarte le plus franchement", "", *entete]
        lignes += [_ligne(c, sc) for c, _, sc in gardees]
        lignes += ["", "### Écartées que Jev retient le plus franchement", "", *entete]
        lignes += [_ligne(c, sc) for c, _, sc in ecartees]
        lignes.append("")

    # --- Tête-à-tête sur les cas jugés par les deux
    communs = [s for s in jev if s in llm and s in par_slug]
    if communs:
        rs = [(par_slug[s], scores_jev(jev[s])["deposable"], llm[s]) for s in communs]
        couples = [(p, c.garde) for c, p, _ in rs]

        def issue_llm(r: dict[str, Any]) -> str:
            return "retenue" if r["retenir"] else "humain" if r["indeterminee"] else "ecartee"

        part_llm = sum(issue_llm(r) == "humain" for _, _, r in rs) / len(rs)
        bandes_jev = {
            "tolerance": ajuster(couples),
            "charge": ajuster_a_charge(couples, part_llm),
        }

        def issue_jev(p: float, b: Bandes) -> str:
            return "ecartee" if p < b.bas else "retenue" if p > b.haut else "humain"

        bt, bc = bandes_jev["tolerance"], bandes_jev["charge"]
        lignes += [
            f"## Tête-à-tête sur les {len(communs)} cas jugés par les deux",
            "",
            "Seuils de Jev ajustés sur ces mêmes cas : optimiste pour Jev, à lire avec "
            "les bandes mesurées sur une moitié à part plus haut. Deux réglages : "
            f"tolérance {TOLERANCE:.0%} (écartée sous {bt.bas:.3f}, retenue au-dessus "
            f"de {bt.haut:.3f}), et même part renvoyée à un humain que le LLM "
            f"(écartée sous {bc.bas:.3f}, retenue au-dessus de {bc.haut:.3f}).",
            "",
            "| | Jev (tolérance) | Jev (charge égale) | LLM |",
            "|---|---:|---:|---:|",
        ]
        for libelle, issue, verite in (
            ("gardées écartées à tort", "ecartee", True),
            ("écartées retenues à tort", "retenue", False),
            ("renvoyées à un humain", "humain", None),
        ):
            tot = sum(verite is None or c.garde == verite for c, _, _ in rs)
            cols = [
                _pct(
                    sum(
                        (verite is None or c.garde == verite) and issue_jev(p, b) == issue
                        for c, p, _ in rs
                    ),
                    tot,
                )
                for b in (bt, bc)
            ]
            nl = sum(
                (verite is None or c.garde == verite) and issue_llm(r) == issue for c, _, r in rs
            )
            lignes.append(f"| {libelle} | {cols[0]} | {cols[1]} | {_pct(nl, tot)} |")
        lignes.append("")

        rates = sorted((p, c.slug) for c, p, r in rs if c.garde and issue_llm(r) == "ecartee")
        if rates:
            lignes += [
                f"Les {len(rates)} gardées que le LLM écarte (sans recours en production) : "
                f"Jev en met {sum(p < bt.bas for p, _ in rates)} sous son seuil d'écart, "
                f"score médian {statistics.median(p for p, _ in rates):.2f}.",
                "",
                ", ".join(f"`{s}` ({p:.2f})" for p, s in rates),
                "",
            ]

    return "\n".join(lignes)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def echantillon(cas: list[Cas], n: int, graine: int = 0) -> list[Cas]:
    """`n` cas, moitié gardées moitié écartées, tirés de façon reproductible."""
    rng = random.Random(graine)
    g = [c for c in cas if c.garde]
    e = [c for c in cas if not c.garde]
    return rng.sample(g, min(n // 2, len(g))) + rng.sample(e, min(n - n // 2, len(e)))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="benchmark_destinataire.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--jev", action="store_true", help="faire juger par Jev (DECISION_MODEL)")
    p.add_argument("--llm", action="store_true", help="faire juger par le LLM de lecture")
    p.add_argument("--model-lecture", help="modèle du LLM (défaut : LLM_MODEL_LECTURE)")
    p.add_argument("--echantillon", type=int, help="n cas équilibrés au lieu du jeu entier")
    p.add_argument("--parallele", type=int, default=8)
    p.add_argument("--dry-run", action="store_true", help="décrire le jeu, n'appeler personne")
    args = p.parse_args(argv)

    charger_env()
    cas = cas_etiquetes()
    if args.echantillon:
        cas = echantillon(cas, args.echantillon)
    n_g = sum(c.garde for c in cas)
    print(f"{len(cas)} cas : {n_g} gardées, {len(cas) - n_g} écartées")

    if args.dry_run:
        tailles = [len(texte_du_snapshot(c.slug)[1]) for c in cas]
        print(
            f"texte médian {statistics.median(tailles):.0f} car., "
            f"{sum(t < SEUIL_TEXTE_PAGES for t in tailles)} cas sous {SEUIL_TEXTE_PAGES} car."
        )
        return 0

    if args.jev:
        client = ClientDecision()
        try:
            faire_juger("jev", juge_jev(client), cas, args.parallele)
        finally:
            client.fermer()
    if args.llm:
        faire_juger("llm", juge_llm(args.model_lecture), cas, args.parallele)

    slugs = {c.slug for c in cas}
    jev = {s: r for s, r in lire_cache("jev").items() if s in slugs}
    llm = {s: r for s, r in lire_cache("llm").items() if s in slugs}
    texte = rapport(cas, jev, llm)
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    chemin = REVIEWS_DIR / f"{date.today().isoformat()}-benchmark-destinataire.md"
    chemin.write_text(texte + "\n", encoding="utf-8")
    print(f"rapport : {chemin.relative_to(BACKEND_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
