"""Ligne de base, en qualité, de l'extraction, du typage, de la vérification et de l'écriture.

Mesure M07 de la refonte des pipelines (phase 1, hors ligne, 0 $).

Commande (depuis backend/) :

    uv run python scripts/mesures/extraction_typage.py

Options : `--sections banc,citations,text_quote,typage,ecriture,verificateur`
(toutes par défaut) ; `--echantillon 50` (taille de l'échantillon tiré au sort
pour le test de re-sérialisation, graine 0, en plus du catalogue entier).

Produit, dans data/reviews/logs/refonte/2026-10-10-extraction-typage-1/ :
  - banc.json : scores de comparer_aides par aide et par modèle (références lues
    à 3b2ec426 et dans le worktree), rappel et précision poolés, provenance des
    références ;
  - citations.json : citations introuvables, conditions sans citation, dette
    connue (évaluables sans quote, manual_check gate, conditions sans `effect`) ;
  - text_quote.json, text_quote_exemples.json : écart entre `text` et `quote` ;
  - typage.json, typage_exemples.json : transitions de typage dans git
    (reproduction de transitions.json), devenir des conditions écrites par
    l'ingestion, par kind, effect et époque ;
  - ecriture.json : commentaires, bloc fiche, style des lignes fact:/levier:,
    test de re-sérialisation par la fonction d'écriture de l'ingestion ;
  - verificateur.json, verificateur_bloquants.jsonl : passages du vérificateur
    adversarial relus dans les journaux, devenir de chaque bloquant ;
  - resume.txt : les chiffres de la note, chacun avec son effectif.

Lecture seule partout ailleurs : aucun appel réseau ni de modèle, aucun script
du pipeline exécuté, aucune commande git qui écrit (seulement `git log` et
`git cat-file --batch`). Le cache disque de pdftotext n'est PAS alimenté :
`veille_collect.pdf_bytes_to_text` est remplacé, dans ce processus, par une
version qui lit le cache du checkout principal et sinon lance pdftotext sans
rien écrire. Modules importés : aides_schema, veille_text, veille_collect,
lint_aides_data, comparer_aides (aucun n'écrit à l'import).
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from difflib import SequenceMatcher
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
SCRIPTS = BACKEND / "scripts"
DATA = BACKEND / "data"
AIDES = DATA / "aides"
REVIEWS = DATA / "reviews"
LOGS = REVIEWS / "logs"
SORTIE = LOGS / "refonte" / "2026-10-10-extraction-typage-1"
CACHE_PDF_PRINCIPAL = Path("/Users/felixollivier/monumia/backend/.cache/pdftotext")

sys.path[:0] = [str(SCRIPTS), str(BACKEND)]

import veille_collect  # noqa: E402
from veille_text import find_quote_in_any, normalize  # noqa: E402

from aides_schema import Aide, charger_yaml  # noqa: E402


def _pdf_bytes_to_text_lecture_seule(content: bytes) -> str | None:
    """Comme veille_collect.pdf_bytes_to_text, sans jamais écrire de cache."""
    sha = hashlib.sha256(content).hexdigest()
    cache = CACHE_PDF_PRINCIPAL / f"{sha}.txt"
    try:
        if cache.is_file():
            return cache.read_text(encoding="utf-8")
    except OSError:
        pass
    return veille_collect._pdftotext(content)


veille_collect.pdf_bytes_to_text = _pdf_bytes_to_text_lecture_seule  # type: ignore[assignment]

import comparer_aides  # noqa: E402
from lint_aides_data import EVALUABLE_KINDS, check_quotes  # noqa: E402

COMMIT_BANC = "3b2ec426"  # main au moment du banc du 2026-10-07 (données = b9f3f43e)
COMMIT_CARTO = "fb918d57"  # HEAD de transitions.py (2026-10-07)
SLUGS_BANC = (
    "hdf-jardins-en-scene",
    "hdf-actes-fonds-appui-projets-locaux",
    "88-patrimoine-protege-mh",
    "bretagne-edifices-publics",
    "pdl-cap-pcc",
)
MODELES_BANC = ("or-glm", "or-mistral-large")
TRANSITIONS_JSON = LOGS / "refonte-entrees" / "be997c31-bilan-2026-10-07" / "transitions.json"
DOSSIERS_JOURNAUX = (LOGS, LOGS / "depuis-prospection-worktree", LOGS / "depuis-veille-hebdo")


# ---------------------------------------------------------------------------
# Outils communs
# ---------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def taux(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {
        "k": k,
        "n": n,
        "p": round(k / n, 4) if n else None,
        "ic95": [round(lo, 4), round(hi, 4)] if n else None,
    }


def fmt(k: int, n: int) -> str:
    if not n:
        return f"{k}/0"
    lo, hi = wilson(k, n)
    assert lo is not None and hi is not None
    return f"{k}/{n} = {100 * k / n:.1f} % [IC95 {100 * lo:.1f} ; {100 * hi:.1f}]"


class Git:
    """Lecture de blobs par `git cat-file --batch` (lecture seule)."""

    def __init__(self, racine: Path = RACINE) -> None:
        self.racine = racine
        self.p = subprocess.Popen(
            ["git", "-C", str(racine), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

    def lire(self, ref: str) -> str | None:
        assert self.p.stdin and self.p.stdout
        self.p.stdin.write((ref + "\n").encode())
        self.p.stdin.flush()
        entete = self.p.stdout.readline().decode().split()
        if len(entete) < 3 or entete[1] == "missing":
            return None
        taille = int(entete[2])
        data = self.p.stdout.read(taille)
        self.p.stdout.read(1)
        return data.decode("utf-8", errors="replace")

    def cmd(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.racine), *args], capture_output=True, text=True, check=True
        ).stdout


def ecrire_json(nom: str, objet) -> None:
    (SORTIE / nom).write_text(
        json.dumps(objet, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8"
    )


RESUME: list[str] = []


def dire(ligne: str = "") -> None:
    print(ligne)
    RESUME.append(ligne)


def fiches_ingestion() -> dict[str, dict]:
    """slug -> {pipeline: [dates], manuel: [dates]} d'après data/reviews/*-ingest-*.md."""
    out: dict[str, dict] = defaultdict(lambda: {"pipeline": [], "manuel": []})
    for chemin in sorted(REVIEWS.glob("*-ingest-*.md")):
        m = re.match(r"(\d{4}-\d\d-\d\d)-ingest-(.+)\.md$", chemin.name)
        if not m:
            continue
        date, slug = m.groups()
        tete = chemin.read_text(encoding="utf-8", errors="replace")[:600]
        cle = "pipeline" if "Généré par scripts/ingerer.py" in tete else "manuel"
        out[slug][cle].append(date)
    return dict(out)


def epoque(date: str) -> str:
    if date <= "2026-09-14":
        return "E1 2026-09-07 a 09-14"
    if date <= "2026-09-19":
        return "E2 2026-09-17 a 09-19"
    if date <= "2026-09-30":
        return "E3 2026-09-29 a 09-30"
    if date <= "2026-10-06":
        return "E4 2026-10-04 a 10-05"
    return "E5 2026-10-07 (banc)"


def conditions_brutes(texte: str | None) -> dict[str, dict]:
    """Conditions d'un YAML brut, `effect` par défaut comme le schéma (cf. transitions.py)."""
    if not texte:
        return {}
    try:
        brut = charger_yaml(texte) or {}
    except Exception:
        return {}
    if not isinstance(brut, dict):
        return {}
    out = {}
    for c in brut.get("conditions") or []:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        kind = c.get("kind", "untyped")
        effect = c.get("effect")
        if effect is None:
            effect = "info" if kind in ("info", "discretionary") else "gate"
        out[c["id"]] = {
            "kind": kind,
            "effect": effect,
            "fact": c.get("fact"),
            "field": c.get("field"),
            "levier": c.get("levier"),
            "predicate": c.get("predicate"),
            "applies_if": c.get("applies_if"),
            "derogation_possible": bool(c.get("derogation_possible")),
            "text": " ".join(str(c.get("text") or "").split()),
            "quote": " ".join(str(c.get("quote") or "").split()),
        }
    return out


def aide_brute(texte: str | None) -> dict:
    if not texte:
        return {}
    try:
        brut = charger_yaml(texte) or {}
    except Exception:
        return {}
    return brut if isinstance(brut, dict) else {}


# ---------------------------------------------------------------------------
# 1. Banc d'ingestion du 2026-10-07
# ---------------------------------------------------------------------------


def section_banc(git: Git) -> dict:
    dire("== 1. Banc d'ingestion du 2026-10-07 (comparer_aides, lecture seule)")
    racine = LOGS / "bench-ingestion-2026-10-07" / "assemble"
    resultats = []
    pool: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for ref_label, lire_ref in (
        (f"git:{COMMIT_BANC}", lambda s: git.lire(f"{COMMIT_BANC}:backend/data/aides/{s}.yaml")),
        ("worktree", lambda s: (AIDES / f"{s}.yaml").read_text(encoding="utf-8")),
    ):
        for modele in MODELES_BANC:
            for slug in SLUGS_BANC:
                cand = racine / modele / "aides" / f"{slug}.yaml"
                ligne: dict = {"reference": ref_label, "modele": modele, "slug": slug}
                if not cand.exists():
                    ligne["absent"] = True
                    echec = cand.with_name(cand.name + ".echec")
                    ligne["echec_present"] = echec.exists()
                    resultats.append(ligne)
                    continue
                ref = Aide.model_validate(charger_yaml(lire_ref(slug)))
                candidat = Aide.model_validate(charger_yaml(cand.read_text(encoding="utf-8")))
                docs = comparer_aides._charger_documents(racine / modele / "sources" / slug)
                comp = comparer_aides.comparer(ref, candidat, docs)
                log = racine / modele / "reviews" / "logs" / f"ingest-{slug}.log"
                journal = comparer_aides.lire_log(log) if log.exists() else None
                paires, _manq, _trop = comparer_aides.apparier_conditions(
                    ref.conditions, candidat.conditions
                )
                meme_kind = sum(1 for r, c in paires if r.kind == c.kind)
                meme_effect = sum(1 for r, c in paires if r.effect == c.effect)
                meme_ke = sum(1 for r, c in paires if (r.kind, r.effect) == (c.kind, c.effect))
                ligne.update(
                    {
                        "score": comp.score,
                        "conditions_reference": comp.conditions_reference,
                        "conditions_candidat": comp.conditions_candidat,
                        "communes": comp.communes,
                        "decisives": [comp.decisives_retrouvees, comp.decisives_reference],
                        "gates": [comp.gates_retrouvees, comp.gates_reference],
                        "precision": round(comp.precision, 4),
                        "citations": [comp.citations_verifiees, comp.citations_candidat],
                        "couvertes_par_filtre": comp.couvertes_par_filtre,
                        "composites": comp.composites,
                        "manquantes": comp.manquantes,
                        "en_trop": comp.en_trop,
                        "divergences": [asdict(d) for d in comp.divergences],
                        "champs_divergents": [asdict(d) for d in comp.champs_divergents],
                        "avertissements": comp.avertissements(),
                        "paires_meme_kind": meme_kind,
                        "paires_meme_effect": meme_effect,
                        "paires_meme_kind_effect": meme_ke,
                        "journal": asdict(journal) if journal else None,
                        "kinds_candidat": Counter(
                            f"{c.kind}/{c.effect}" for c in candidat.conditions
                        ),
                        "kinds_reference": Counter(f"{c.kind}/{c.effect}" for c in ref.conditions),
                    }
                )
                p = pool[(ref_label, modele)]
                p["aides"] += 1
                p["score_somme"] += comp.score
                p["dec_k"] += comp.decisives_retrouvees
                p["dec_n"] += comp.decisives_reference
                p["communes"] += comp.communes
                p["cand"] += comp.conditions_candidat
                p["ref"] += comp.conditions_reference
                p["cit_k"] += comp.citations_verifiees
                p["cit_n"] += comp.citations_candidat
                p["paires"] += comp.communes
                p["meme_ke"] += meme_ke
                p["meme_effect"] += meme_effect
                resultats.append(ligne)

    synthese = {}
    for (ref_label, modele), p in pool.items():
        cle = f"{ref_label} | {modele}"
        synthese[cle] = {
            "aides": p["aides"],
            "score_moyen": round(p["score_somme"] / p["aides"], 1) if p["aides"] else None,
            "rappel_decisives": taux(p["dec_k"], p["dec_n"]),
            "precision_conditions": taux(p["communes"], p["cand"]),
            "rappel_toutes_conditions": taux(p["communes"], p["ref"]),
            "citations_retrouvees": taux(p["cit_k"], p["cit_n"]),
            "citations_inventees": p["cit_n"] - p["cit_k"],
            "accord_kind_effect_sur_paires": taux(p["meme_ke"], p["paires"]),
            "accord_effect_sur_paires": taux(p["meme_effect"], p["paires"]),
        }
    for cle, s in synthese.items():
        dire(
            f"  {cle} : score moyen {s['score_moyen']} sur {s['aides']} aide(s) ; "
            f"rappel décisives {fmt(s['rappel_decisives']['k'], s['rappel_decisives']['n'])} ; "
            f"précision {fmt(s['precision_conditions']['k'], s['precision_conditions']['n'])} ; "
            f"rappel toutes conditions "
            f"{fmt(s['rappel_toutes_conditions']['k'], s['rappel_toutes_conditions']['n'])} ; "
            f"citations {fmt(s['citations_retrouvees']['k'], s['citations_retrouvees']['n'])} ; "
            f"accord kind+effect sur paires "
            f"{fmt(s['accord_kind_effect_sur_paires']['k'], s['accord_kind_effect_sur_paires']['n'])}"
        )
    for r in resultats:
        if r["reference"] != f"git:{COMMIT_BANC}":
            continue
        if r.get("absent"):
            dire(f"    {r['modele']:<17} {r['slug']:<38} absent (.echec : {r['echec_present']})")
            continue
        j = r["journal"] or {}
        dire(
            f"    {r['modele']:<17} {r['slug']:<38} score {r['score']:>5} | décisives "
            f"{r['decisives'][0]}/{r['decisives'][1]} | précision {r['communes']}/"
            f"{r['conditions_candidat']} | quotes {r['citations'][0]}/{r['citations'][1]} | "
            f"kind+effect identiques {r['paires_meme_kind_effect']}/{r['communes']} | "
            f"tours {j.get('tours')} coût {j.get('cout_usd')}"
        )

    # Provenance des références et qualité de leurs propres citations
    provenance = {}
    for slug in SLUGS_BANC:
        hist = git.cmd(
            "log",
            "--format=%h|%ad|%an|%s",
            "--date=short",
            COMMIT_BANC,
            "--",
            f"backend/data/aides/{slug}.yaml",
        ).splitlines()
        ref_txt = git.lire(f"{COMMIT_BANC}:backend/data/aides/{slug}.yaml")
        ref = Aide.model_validate(charger_yaml(ref_txt))
        docs, illisibles, _ = veille_collect.load_baselines(slug)
        absentes, degradees, hors = check_quotes(ref, docs, illisibles)
        fiches = sorted(p.name for p in REVIEWS.glob(f"*-ingest-{slug}.md"))
        diff_wt = ref_txt != (AIDES / f"{slug}.yaml").read_text(encoding="utf-8")
        provenance[slug] = {
            "commits": hist,
            "fiches_ingestion": fiches,
            "fiche_generee_par_pipeline": [
                f
                for f in fiches
                if "Généré par scripts/ingerer.py"
                in (REVIEWS / f).read_text(encoding="utf-8")[:600]
            ],
            "conditions": len(ref.conditions),
            "quotes_reference": sum(1 for c in ref.conditions if c.quote),
            "quotes_reference_introuvables": len(absentes),
            "quotes_reference_hors_portee": len(hors),
            "reference_differe_du_worktree": diff_wt,
        }
        dire(
            f"    réf. {slug} : {len(hist)} commit(s), premier {hist[-1] if hist else '?'} ; "
            f"fiches {fiches} ; citations de la réf. introuvables {len(absentes)}/"
            f"{sum(1 for c in ref.conditions if c.quote)} ; diffère du worktree : {diff_wt}"
        )
    sortie = {"resultats": resultats, "synthese": synthese, "provenance_references": provenance}
    ecrire_json("banc.json", sortie)
    return sortie


# ---------------------------------------------------------------------------
# 2. Citations du catalogue
# ---------------------------------------------------------------------------


def section_citations(groupes: dict[str, str]) -> dict:
    dire("== 2. Citations du catalogue (find_quote_in_any contre data/sources, lecture seule)")
    tot = Counter()
    par_groupe: dict[str, Counter] = defaultdict(Counter)
    introuvables = []
    sans_quote_normatives = []
    sans_effect = Counter()
    sans_effect_exemples = []
    mc_gate = []
    for chemin in sorted(AIDES.glob("*.yaml")):
        texte = chemin.read_text(encoding="utf-8")
        brut = aide_brute(texte)
        aide = Aide.model_validate(brut)
        g = groupes.get(aide.slug, "sans_fiche")
        for c in brut.get("conditions") or []:
            if "effect" not in c:
                kind = c.get("kind", "untyped")
                eff = "info" if kind in ("info", "discretionary") else "gate"
                sans_effect[f"{kind}->{eff}"] += 1
                if len(sans_effect_exemples) < 400:
                    sans_effect_exemples.append((aide.slug, c.get("id"), kind, eff))
        for c in aide.conditions:
            tot["conditions"] += 1
            par_groupe[g]["conditions"] += 1
            if c.kind == "manual_check" and c.effect == "gate":
                mc_gate.append((aide.slug, c.id))
            normative = c.effect in ("gate", "modulateur")
            evaluable = c.kind in EVALUABLE_KINDS
            if not c.quote:
                tot["sans_quote"] += 1
                if evaluable:
                    tot["evaluables_sans_quote"] += 1
                if normative:
                    tot["normatives_sans_quote"] += 1
                    sans_quote_normatives.append(
                        (aide.slug, c.id, c.kind, c.effect, g, (c.text or "")[:160])
                    )
            if evaluable:
                tot["evaluables"] += 1
            if normative:
                tot["normatives"] += 1
                par_groupe[g]["normatives"] += 1
        docs, illisibles, _ = veille_collect.load_baselines(aide.slug)
        absentes, degradees, hors = check_quotes(aide, docs, illisibles)
        if docs:
            for c in aide.conditions:
                if c.quote:
                    _nom, m = find_quote_in_any(c.quote, docs)  # type: ignore[arg-type]
                    tot[f"statut_{m.status}_{m.reconstitution or 'contigue'}"] += 1
        citees = sum(1 for c in aide.conditions if c.quote)
        tot["citees"] += citees
        tot["absentes"] += len(absentes)
        tot["degradees"] += len(degradees)
        tot["hors_portee"] += len(hors)
        par_groupe[g]["citees"] += citees
        par_groupe[g]["absentes"] += len(absentes)
        par_groupe[g]["hors_portee"] += len(hors)
        par_groupe[g]["aides"] += 1
        if absentes:
            par_groupe[g]["aides_avec_absente"] += 1
            tot["aides_avec_absente"] += 1
        if not docs:
            tot["aides_sans_snapshot"] += 1
        if illisibles:
            tot["aides_pdf_illisible"] += 1
        tot["aides"] += 1
        eff = {c.id: c.effect for c in aide.conditions}
        for slug, cid, quote in absentes:
            introuvables.append(
                {"slug": slug, "id": cid, "effect": eff.get(cid), "groupe": g, "quote": quote[:200]}
            )
    effet_abs = Counter(i["effect"] for i in introuvables)
    dire(
        f"  {tot['aides']} aides, {tot['conditions']} conditions, {tot['citees']} citées ; "
        f"introuvables {fmt(tot['absentes'], tot['citees'])} ; retrouvées après normalisation "
        f"ou reconstitution {tot['degradees']} ; hors portée (pas de snapshot ou PDF "
        f"illisible) {tot['hors_portee']} ; aides avec au moins une introuvable "
        f"{fmt(tot['aides_avec_absente'], tot['aides'])}"
    )
    dire(f"  introuvables par effect : {dict(effet_abs)}")
    dire(
        "  statut de la meilleure correspondance (aides avec snapshot) : "
        + str({k[7:]: v for k, v in sorted(tot.items()) if k.startswith("statut_")})
    )
    dire(
        f"  évaluables (kind in {EVALUABLE_KINDS}) sans quote : "
        f"{fmt(tot['evaluables_sans_quote'], tot['evaluables'])} ; normatives (effect gate ou "
        f"modulateur) sans quote : {fmt(tot['normatives_sans_quote'], tot['normatives'])}"
    )
    dire(f"  manual_check + gate : {len(mc_gate)} {mc_gate}")
    dire(
        f"  conditions sans ligne `effect` : {sum(sans_effect.values())} ; par kind -> effect "
        f"implicite : {dict(sans_effect)}"
    )
    for g, c in sorted(par_groupe.items()):
        dire(
            f"    groupe {g:<11} : {c['aides']} aides, introuvables "
            f"{fmt(c['absentes'], c['citees'])}, aides touchées {c['aides_avec_absente']}"
        )
    sortie = {
        "totaux": tot,
        "par_groupe": par_groupe,
        "introuvables": introuvables,
        "normatives_sans_quote": sans_quote_normatives,
        "manual_check_gate": mc_gate,
        "sans_effect": sans_effect,
        "sans_effect_exemples": sans_effect_exemples,
    }
    ecrire_json("citations.json", sortie)
    return sortie


# ---------------------------------------------------------------------------
# 3. text contre quote
# ---------------------------------------------------------------------------

_MOT = re.compile(r"[a-z0-9]+")
_NOMBRE = re.compile(r"(?<![0-9])[0-9]+(?:[.,][0-9]+)?(?![0-9])")


def _milliers(texte: str) -> str:
    """« 1 000 », « 10.000 » -> « 1000 », « 10000 » : séparateurs de milliers retirés."""
    return re.sub(r"(?<=[0-9])[ .](?=[0-9]{3}(?![0-9]))", "", texte)


def categorie_ecart(text: str, quote: str) -> tuple[str, float, float]:
    nt, nq = normalize(text), normalize(quote)
    ratio = SequenceMatcher(None, nt, nq, autojunk=False).ratio()
    mots_t = _MOT.findall(nt)
    mots_q = set(_MOT.findall(nq))
    couverture = sum(1 for m in mots_t if m in mots_q) / len(mots_t) if mots_t else 0.0
    if nt == nq:
        return "identique", ratio, couverture
    if nt and nt in nq:
        return "text_extrait_de_quote", ratio, couverture
    if nq and nq in nt:
        return "quote_incluse_dans_text", ratio, couverture
    if couverture >= 0.8:
        return "reformulation_legere", ratio, couverture
    if couverture >= 0.5:
        return "reformulation", ratio, couverture
    return "reecriture", ratio, couverture


def section_text_quote(groupes: dict[str, str]) -> dict:
    dire("== 3. text contre quote (veille_text.normalize)")
    cats = Counter()
    par_groupe: dict[str, Counter] = defaultdict(Counter)
    par_effect: dict[str, Counter] = defaultdict(Counter)
    ratios = []
    couvertures = []
    exemples: dict[str, list] = defaultdict(list)
    tirets = 0
    tirets_tous = 0
    chiffres = Counter()
    rng = random.Random(0)
    n = 0
    for chemin in sorted(AIDES.glob("*.yaml")):
        aide = Aide.model_validate(charger_yaml(chemin.read_text(encoding="utf-8")))
        g = groupes.get(aide.slug, "sans_fiche")
        docs, _ill, _prov = veille_collect.load_baselines(aide.slug)
        corpus = " ".join(_milliers(normalize(d[1])) for d in docs) if docs else ""
        for c in aide.conditions:
            if c.quote:
                nombres_t = set(_NOMBRE.findall(_milliers(normalize(c.text))))
                nombres_q = set(_NOMBRE.findall(_milliers(normalize(c.quote))))
                hors_q = nombres_t - nombres_q
                if nombres_t:
                    chiffres["text_avec_nombre"] += 1
                if hors_q:
                    chiffres["nombre_hors_quote"] += 1
                    if corpus:
                        chiffres["nombre_hors_quote_avec_corpus"] += 1
                        hors_corpus = {
                            x
                            for x in hors_q
                            if not re.search(rf"(?<![0-9]){re.escape(x)}(?![0-9])", corpus)
                        }
                        if hors_corpus:
                            chiffres["nombre_hors_corpus"] += 1
                            chiffres[f"nombre_hors_corpus_{c.effect}"] += 1
                            if len(exemples["nombre_hors_corpus"]) < 40:
                                exemples["nombre_hors_corpus"].append(
                                    {
                                        "slug": aide.slug,
                                        "id": c.id,
                                        "effect": c.effect,
                                        "nombres": sorted(hors_corpus),
                                        "text": c.text,
                                        "quote": c.quote,
                                    }
                                )
            if "—" in c.text:
                tirets += 1
            if "—" in c.text or "–" in c.text:
                tirets_tous += 1
            if not c.quote:
                continue
            n += 1
            cat, ratio, couv = categorie_ecart(c.text, c.quote)
            cats[cat] += 1
            par_groupe[g][cat] += 1
            par_effect[c.effect][cat] += 1
            ratios.append(ratio)
            couvertures.append(couv)
            ex = exemples[cat]
            item = {
                "slug": aide.slug,
                "id": c.id,
                "effect": c.effect,
                "ratio": round(ratio, 3),
                "couverture": round(couv, 3),
                "text": c.text,
                "quote": c.quote,
            }
            if len(ex) < 12:
                ex.append(item)
            elif rng.random() < 12 / max(cats[cat], 1):
                ex[rng.randrange(12)] = item
    differents = n - cats["identique"] - cats["text_extrait_de_quote"]
    dire(
        f"  {n} conditions citées ; ni identiques ni incluses dans la quote (définition de la "
        f"cartographie) : {fmt(differents, n)}"
    )
    for cat in (
        "identique",
        "text_extrait_de_quote",
        "quote_incluse_dans_text",
        "reformulation_legere",
        "reformulation",
        "reecriture",
    ):
        dire(f"    {cat:<24} {fmt(cats[cat], n)}")
    dire(
        f"  text contenant un tiret cadratin : {tirets} ; cadratin ou demi-cadratin : {tirets_tous}"
    )

    dire(
        f"  nombres : text citant un nombre {chiffres['text_avec_nombre']} ; text dont un nombre "
        f"est absent de la quote {fmt(chiffres['nombre_hors_quote'], n)} ; dont, parmi les aides "
        f"qui ont des sources lisibles, nombre absent de TOUTES les sources de l'aide "
        f"{fmt(chiffres['nombre_hors_corpus'], chiffres['nombre_hors_quote_avec_corpus'])} "
        f"(par effect : "
        + str({k[18:]: v for k, v in chiffres.items() if k.startswith("nombre_hors_corpus_")})
        + ")"
    )

    def deciles(v: list[float]) -> list[float]:
        s = sorted(v)
        return [round(s[int(i * (len(s) - 1) / 10)], 3) for i in range(11)] if s else []

    dire(f"  déciles du ratio SequenceMatcher : {deciles(ratios)}")
    dire(f"  déciles de la couverture lexicale du text par la quote : {deciles(couvertures)}")
    for g, c in sorted(par_groupe.items()):
        tg = sum(c.values())
        d = tg - c["identique"] - c["text_extrait_de_quote"]
        rw = c["reecriture"]
        dire(f"    groupe {g:<11} : différents {fmt(d, tg)} ; réécriture {fmt(rw, tg)}")
    for e, c in sorted(par_effect.items()):
        tg = sum(c.values())
        dire(
            f"    effect {e:<11} : réécriture {fmt(c['reecriture'], tg)} ; reformulation "
            f"{fmt(c['reformulation'], tg)}"
        )
    sortie = {
        "n": n,
        "categories": cats,
        "differents_definition_cartographie": differents,
        "tirets_cadratin": tirets,
        "tirets_cadratin_ou_demi": tirets_tous,
        "nombres": chiffres,
        "deciles_ratio": deciles(ratios),
        "deciles_couverture": deciles(couvertures),
        "par_groupe": par_groupe,
        "par_effect": par_effect,
        "seuils": "couverture lexicale (part des mots du text présents dans la quote) >= 0,8 "
        "légère, >= 0,5 reformulation, sinon réécriture ; seuils posés a priori, non calibrés",
    }
    ecrire_json("text_quote.json", sortie)
    ecrire_json("text_quote_exemples.json", exemples)
    return sortie


# ---------------------------------------------------------------------------
# 4. Typage : transitions dans git et devenir des conditions ingérées
# ---------------------------------------------------------------------------


def commits_aides(git: Git, rev: str) -> list[tuple[str, str, str, list[str]]]:
    log = git.cmd(
        "log",
        "--no-merges",
        "--full-history",
        "--format=@@%H %ad %s",
        "--date=short",
        "--name-only",
        rev,
        "--",
        "backend/data/aides",
    )
    out = []
    for bloc in log.split("@@")[1:]:
        lignes = [li for li in bloc.splitlines() if li.strip()]
        h, d, *sujet = lignes[0].split(" ")
        fichiers = [f for f in lignes[1:] if f.endswith((".yaml", ".yaml.echec"))]
        out.append((h, d, " ".join(sujet), fichiers))
    return out


def section_typage(
    git: Git, fiches: dict[str, dict], groupes: dict[str, str], runs: list[dict]
) -> dict:
    dire("== 4. Typage : retypages après écriture (git, lecture seule)")
    commits = commits_aides(git, "HEAD")
    atteignables_carto = set(git.cmd("rev-list", COMMIT_CARTO).split())
    sujets = {h[:8]: (d, s) for h, d, s, _ in commits}
    transitions = []
    n_paires = 0
    for h, d, _s, fichiers in commits:
        for f in fichiers:
            avant = git.lire(f"{h}^:{f}")
            apres = git.lire(f"{h}:{f}")
            if avant is None or apres is None:
                continue
            ca, cb = conditions_brutes(avant), conditions_brutes(apres)
            for cid in ca.keys() & cb.keys():
                a, b = ca[cid], cb[cid]
                n_paires += 1
                ka, kb = (a["kind"], a["effect"]), (b["kind"], b["effect"])
                if ka != kb:
                    nature = "kind_effect"
                elif a["fact"] != b["fact"] and a["fact"] and b["fact"]:
                    nature = "fait_change"
                else:
                    continue
                transitions.append(
                    {
                        "commit": h[:8],
                        "date": d,
                        "fichier": f.split("/")[-1],
                        "slug": f.split("/")[-1].removesuffix(".echec").removesuffix(".yaml"),
                        "id": cid,
                        "nature": nature,
                        "avant": f"{a['kind']}/{a['effect']}",
                        "apres": f"{b['kind']}/{b['effect']}",
                        "fait_avant": a["fact"],
                        "fait_apres": b["fact"],
                        "dans_fb918d57": h in atteignables_carto,
                        "text": b["text"][:240],
                    }
                )
    n_carto = sum(1 for t in transitions if t["dans_fb918d57"])
    ref = json.loads(TRANSITIONS_JSON.read_text(encoding="utf-8"))
    cles_ref = Counter((t["commit"], t["fichier"], t["id"]) for t in ref)
    cles_moi = Counter(
        (t["commit"], t["fichier"], t["id"]) for t in transitions if t["dans_fb918d57"]
    )
    dire(
        f"  {len(commits)} commits non-merge touchent data/aides à HEAD ; {n_paires} paires "
        f"(condition avant/après) ; transitions retrouvées : {len(transitions)} à HEAD, "
        f"{n_carto} sur les commits atteignables depuis {COMMIT_CARTO} ; transitions.json en "
        f"compte {len(ref)} ; écart symétrique des clés : "
        f"{sum((cles_ref - cles_moi).values())} / {sum((cles_moi - cles_ref).values())}"
    )
    par_commit = Counter(t["commit"] for t in transitions)
    dire("  transitions par commit (10 premiers) :")
    for c, k in par_commit.most_common(10):
        d, s = sujets.get(c, ("?", "?"))
        dire(f"    {c} {d} {k:>4}  {s[:90]}")
    paires_type = Counter(
        f"{t['avant']} -> {t['apres']}" for t in transitions if t["nature"] == "kind_effect"
    )
    dire(f"  transitions kind/effect les plus fréquentes : {paires_type.most_common(12)}")

    # Premier ajout de chaque fichier d'aide
    log_a = git.cmd(
        "log",
        "--no-merges",
        "--full-history",
        "--diff-filter=A",
        "--format=@@%H %ad",
        "--date=short",
        "--name-only",
        "HEAD",
        "--",
        "backend/data/aides",
    )
    premier_ajout: dict[str, tuple[str, str]] = {}
    for bloc in log_a.split("@@")[1:]:
        lignes = [li for li in bloc.splitlines() if li.strip()]
        h, d = lignes[0].split()
        for f in lignes[1:]:
            if f.endswith(".yaml"):
                slug = f.split("/")[-1].removesuffix(".yaml")
                # le log va du plus récent au plus ancien : le dernier vu est le premier ajout
                premier_ajout[slug] = (h, d)

    # Conditions écrites par l'ingestion : aides NOUVELLES dont la première fiche
    # pipeline précède (ou est du jour de) leur premier ajout dans git.
    trans_par_cond: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for t in transitions:
        trans_par_cond[(t["slug"], t["id"])].append(t)

    lignes_cond = []
    aides_niveau = []
    for slug, (h, d) in sorted(premier_ajout.items()):
        f = fiches.get(slug)
        if f and f["pipeline"] and min(f["pipeline"]) <= d:
            origine = "pipeline"
            date_ing = min(f["pipeline"])
        elif f and f["manuel"] and min(f["manuel"]) <= d:
            origine = "manuel"
            date_ing = min(f["manuel"])
        else:
            continue
        initial_txt = git.lire(f"{h}:backend/data/aides/{slug}.yaml")
        initial = conditions_brutes(initial_txt)
        chemin = AIDES / f"{slug}.yaml"
        etat = (
            "catalogue"
            if chemin.exists()
            else ("echec" if chemin.with_name(chemin.name + ".echec").exists() else "absente")
        )
        if etat == "catalogue":
            final_txt = chemin.read_text(encoding="utf-8")
        elif etat == "echec":
            final_txt = chemin.with_name(chemin.name + ".echec").read_text(encoding="utf-8")
        else:
            final_txt = None
        final = conditions_brutes(final_txt)
        ai, af = aide_brute(initial_txt), aide_brute(final_txt)
        aides_niveau.append(
            {
                "slug": slug,
                "origine": origine,
                "date_ingestion": date_ing,
                "premier_commit": d,
                "etat_head": etat,
                "applies_if_change": ai.get("applies_if") != af.get("applies_if"),
                "applies_if_ajoute": not ai.get("applies_if") and bool(af.get("applies_if")),
                "applies_if_retire": bool(ai.get("applies_if")) and not af.get("applies_if"),
                "familles_change": sorted(ai.get("familles") or [])
                != sorted(af.get("familles") or []),
                "hard_filters_change": (ai.get("hard_filters") or {})
                != (af.get("hard_filters") or {}),
            }
        )
        for cid, c in initial.items():
            fin = final.get(cid)
            ts = [t for t in trans_par_cond.get((slug, cid), []) if t["date"] >= d]
            ts = [t for t in ts if t["commit"] != h[:8]]
            lignes_cond.append(
                {
                    "slug": slug,
                    "id": cid,
                    "origine": origine,
                    "epoque": epoque(date_ing),
                    "etat_head": etat,
                    "initial": f"{c['kind']}/{c['effect']}",
                    "final": f"{fin['kind']}/{fin['effect']}" if fin else None,
                    "fait_change": bool(
                        fin and c["fact"] and fin["fact"] and c["fact"] != fin["fact"]
                    ),
                    "predicat_change": bool(fin and c["predicate"] != fin["predicate"]),
                    "retiree": fin is None,
                    "retypee_head": bool(
                        fin and (c["kind"], c["effect"]) != (fin["kind"], fin["effect"])
                    ),
                    "transitions_ke": sum(1 for t in ts if t["nature"] == "kind_effect"),
                    "transitions_fait": sum(1 for t in ts if t["nature"] == "fait_change"),
                    "commits_transitions": sorted({t["commit"] for t in ts}),
                    "text": c["text"][:240],
                    "fact_initial": c["fact"],
                    "fact_final": fin["fact"] if fin else None,
                }
            )

    # Écart entre la sortie du pipeline (dernier YAML écrit d'un run OK) et le
    # premier commit : ce que la relecture (humaine ou assistée) a changé avant
    # d'entrer dans git, invisible dans transitions.json.
    runs_ok: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        if r["issue"] == "ok" and r["yaml_final"]:
            runs_ok[r["slug"]].append(r)
    pre = Counter()
    pre_aides = Counter()
    pre_exemples = []
    for a in aides_niveau:
        if a["origine"] != "pipeline":
            continue
        candidats = [r for r in runs_ok.get(a["slug"], []) if r["date"] <= a["premier_commit"]]
        if not candidats:
            pre_aides["sans_run_ok_avant_commit"] += 1
            continue
        r = candidats[-1]
        h, _d = premier_ajout[a["slug"]]
        txt0 = git.lire(f"{h}:backend/data/aides/{a['slug']}.yaml")
        c_pipe, c_commit = conditions_brutes(r["yaml_final"]), conditions_brutes(txt0)
        a_pipe, a_commit = aide_brute(r["yaml_final"]), aide_brute(txt0)
        pre_aides["aides"] += 1
        sans_fiche = {k: v for k, v in a_commit.items() if k != "fiche"}
        if sans_fiche == a_pipe:
            pre_aides["identiques_hors_fiche"] += 1
        if a_commit.get("fiche"):
            pre_aides["fiche_ajoutee_avant_commit"] += 1
        for k in ("familles", "applies_if", "hard_filters", "financement", "calendrier"):
            if a_pipe.get(k) != a_commit.get(k):
                pre_aides[f"{k}_change"] += 1
        for cid, c in c_pipe.items():
            pre["conditions"] += 1
            pre[f"conditions_{c['kind']}/{c['effect']}"] += 1
            d2 = c_commit.get(cid)
            if d2 is None:
                pre["retirees"] += 1
            elif (c["kind"], c["effect"]) != (d2["kind"], d2["effect"]):
                pre["retypees"] += 1
                pre[f"retypees_{c['kind']}/{c['effect']}"] += 1
                if len(pre_exemples) < 30:
                    pre_exemples.append(
                        {
                            "slug": a["slug"],
                            "id": cid,
                            "pipeline": f"{c['kind']}/{c['effect']}",
                            "commit": f"{d2['kind']}/{d2['effect']}",
                            "text": c["text"][:200],
                        }
                    )
            elif c["fact"] != d2["fact"] or c["predicate"] != d2["predicate"]:
                pre["fait_ou_predicat_change"] += 1
            elif c["text"] != d2["text"] or c["quote"] != d2["quote"]:
                pre["texte_ou_quote_change"] += 1
        pre["ajoutees"] += sum(1 for cid in c_commit if cid not in c_pipe)
    dire(
        f"  sortie du pipeline (dernier YAML d'un run OK) contre premier commit : "
        f"{pre_aides['aides']} aides comparées ({pre_aides['sans_run_ok_avant_commit']} sans run "
        f"OK journalisé avant le commit) ; identiques hors fiche "
        f"{fmt(pre_aides['identiques_hors_fiche'], pre_aides['aides'])} ; conditions retypées "
        f"{fmt(pre['retypees'], pre['conditions'])}, retirées {pre['retirees']}, ajoutées "
        f"{pre['ajoutees']}, fait ou prédicat changé {pre['fait_ou_predicat_change']} ; "
        f"aide : {dict((k, v) for k, v in pre_aides.items() if k.endswith('_change'))}"
    )
    n_ufg = pre["conditions_user_fact/gate"]
    dire(
        f"    dont user_fact/gate retypés avant commit : {fmt(pre['retypees_user_fact/gate'], n_ufg)}"
    )

    def tableau(filtre, cle):
        out = {}
        groupes_ = defaultdict(list)
        for li in lignes_cond:
            if filtre(li):
                groupes_[cle(li)].append(li)
        for g, lis in sorted(groupes_.items()):
            vivantes = [li for li in lis if not li["retiree"]]
            out[g] = {
                "conditions": len(lis),
                "retypees_au_moins_une_fois": taux(
                    sum(1 for li in lis if li["transitions_ke"]), len(lis)
                ),
                "kind_effect_different_a_head": taux(
                    sum(1 for li in vivantes if li["retypee_head"]), len(vivantes)
                ),
                "fait_change_a_head": taux(
                    sum(1 for li in vivantes if li["fait_change"]), len(vivantes)
                ),
                "retirees_a_head": taux(sum(1 for li in lis if li["retiree"]), len(lis)),
            }
        return out

    def pipeline_catalogue(li):
        return li["origine"] == "pipeline" and li["etat_head"] == "catalogue"

    def pipeline_tout(li):
        return li["origine"] == "pipeline"

    def manuel_catalogue(li):
        return li["origine"] == "manuel" and li["etat_head"] == "catalogue"

    res = {
        "pipeline_catalogue_par_kind_effect": tableau(pipeline_catalogue, lambda li: li["initial"]),
        "pipeline_catalogue_par_epoque": tableau(pipeline_catalogue, lambda li: li["epoque"]),
        "pipeline_tout_par_etat_head": tableau(pipeline_tout, lambda li: li["etat_head"]),
        "manuel_catalogue_par_kind_effect": tableau(manuel_catalogue, lambda li: li["initial"]),
        "pipeline_catalogue_total": tableau(pipeline_catalogue, lambda li: "total"),
        "manuel_catalogue_total": tableau(manuel_catalogue, lambda li: "total"),
    }
    n_aides = Counter((a["origine"], a["etat_head"]) for a in aides_niveau)
    dire(
        f"  aides nouvelles rattachées à une fiche d'ingestion (origine, état à HEAD) : {dict(n_aides)}"
    )
    for titre, cle in (
        ("pipeline, aides au catalogue, total", "pipeline_catalogue_total"),
        ("manuel (skill), aides au catalogue, total", "manuel_catalogue_total"),
        (
            "pipeline, aides au catalogue, par kind/effect initial",
            "pipeline_catalogue_par_kind_effect",
        ),
        ("pipeline, aides au catalogue, par époque d'ingestion", "pipeline_catalogue_par_epoque"),
        ("pipeline, toutes, par état à HEAD", "pipeline_tout_par_etat_head"),
        ("manuel, aides au catalogue, par kind/effect initial", "manuel_catalogue_par_kind_effect"),
    ):
        dire(f"  {titre} :")
        for g, v in res[cle].items():
            r1, r2, r3, r4 = (
                v["retypees_au_moins_une_fois"],
                v["kind_effect_different_a_head"],
                v["fait_change_a_head"],
                v["retirees_a_head"],
            )
            dire(
                f"    {g:<28} n={v['conditions']:>5} | retypée >=1 fois {fmt(r1['k'], r1['n'])} | "
                f"kind/effect changé à HEAD {fmt(r2['k'], r2['n'])} | fait changé "
                f"{fmt(r3['k'], r3['n'])} | retirée {fmt(r4['k'], r4['n'])}"
            )
    # Commits responsables des retypages de conditions écrites par le pipeline
    resp = Counter()
    for li in lignes_cond:
        if li["origine"] == "pipeline":
            for c in li["commits_transitions"]:
                resp[c] += 1
    dire("  commits qui retypent des conditions écrites par le pipeline :")
    for c, k in resp.most_common(8):
        d, s = sujets.get(c, ("?", "?"))
        dire(f"    {c} {d} {k:>4}  {s[:90]}")
    # Aide-niveau
    for org in ("pipeline", "manuel"):
        lis = [a for a in aides_niveau if a["origine"] == org and a["etat_head"] == "catalogue"]
        dire(
            f"  {org}, aides au catalogue : applies_if ajouté {fmt(sum(a['applies_if_ajoute'] for a in lis), len(lis))}, "
            f"retiré {sum(a['applies_if_retire'] for a in lis)}, familles changées "
            f"{fmt(sum(a['familles_change'] for a in lis), len(lis))}, hard_filters changés "
            f"{fmt(sum(a['hard_filters_change'] for a in lis), len(lis))}"
        )
    # Gates retirés et décisives manquées : exemples
    gates_retires = [
        t
        for li in lignes_cond
        if li["origine"] == "pipeline"
        for t in trans_par_cond.get((li["slug"], li["id"]), [])
        if t["avant"].endswith("/gate") and not t["apres"].endswith("/gate")
    ]
    info_vers_gate = [
        t
        for li in lignes_cond
        if li["origine"] == "pipeline"
        for t in trans_par_cond.get((li["slug"], li["id"]), [])
        if not t["avant"].endswith("/gate") and t["apres"].endswith("/gate")
    ]
    dire(
        f"  sur les conditions écrites par le pipeline : {len(gates_retires)} transitions "
        f"gate -> non gate (gates retirés), {len(info_vers_gate)} transitions non gate -> gate"
    )
    dire(
        f"    gate retiré, par commit : {Counter(t['commit'] for t in gates_retires).most_common(6)}"
    )
    dire(
        f"    devenu gate, par commit : {Counter(t['commit'] for t in info_vers_gate).most_common(6)}"
    )
    rng = random.Random(0)
    exemples = {
        "gates_retires": rng.sample(gates_retires, min(25, len(gates_retires))),
        "devenus_gate": rng.sample(info_vers_gate, min(25, len(info_vers_gate))),
    }
    ecrire_json("typage_exemples.json", exemples)
    sortie = {
        "commits": len(commits),
        "transitions_head": len(transitions),
        "transitions_fb918d57": n_carto,
        "transitions_json": len(ref),
        "par_commit": {c: [k, *sujets.get(c, ("?", "?"))] for c, k in par_commit.most_common()},
        "paires_type": paires_type,
        "resultats": res,
        "aides": aides_niveau,
        "conditions": lignes_cond,
        "commits_retypant_pipeline": {
            c: [k, *sujets.get(c, ("?", "?"))] for c, k in resp.most_common()
        },
        "avant_commit": {"conditions": pre, "aides": pre_aides, "exemples": pre_exemples},
    }
    ecrire_json("typage.json", sortie)
    return sortie


# ---------------------------------------------------------------------------
# 5. Écriture : propriétés des YAML et re-sérialisation
# ---------------------------------------------------------------------------

_FLOW_FACT = re.compile(r"\{[^}\n]*\b(fact|levier):")
_BLOC_FACT = re.compile(r"^\s*(?:- )?(fact|levier):\s*\S")


def reserialiser(texte: str) -> str:
    """La sérialisation de outils.ecrire_aide (outils.py, ecrire_aide), à l'identique."""
    return yaml.safe_dump(charger_yaml(texte), allow_unicode=True, sort_keys=False, width=100)


def section_ecriture(git: Git, taille_echantillon: int) -> dict:
    dire("== 5. Écriture : commentaires, bloc fiche, style, re-sérialisation en mémoire")
    chemins = sorted(AIDES.glob("*.yaml"))
    lignes = []
    for chemin in chemins:
        texte = chemin.read_text(encoding="utf-8")
        lignes_t = texte.splitlines()
        com_pleins = sum(1 for li in lignes_t if li.lstrip().startswith("#"))
        i_fiche = next((i for i, li in enumerate(lignes_t) if li.startswith("fiche:")), None)
        entete = 0
        if i_fiche is not None:
            j = i_fiche - 1
            while j >= 0 and lignes_t[j].lstrip().startswith("#"):
                entete += 1
                j -= 1
        sortie = reserialiser(texte)
        identique = sortie == texte
        meme_donnees = charger_yaml(sortie) == charger_yaml(texte)
        diff = list(difflib.unified_diff(lignes_t, sortie.splitlines(), lineterm="", n=0))
        retirees = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
        ajoutees = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
        com_sortie = sum(1 for li in sortie.splitlines() if li.lstrip().startswith("#"))
        lignes.append(
            {
                "slug": chemin.stem,
                "octets": len(texte.encode()),
                "commentaires_pleins": com_pleins,
                "commentaires_entete_fiche": entete,
                "commentaires_hors_entete": com_pleins - entete,
                "commentaires_apres": com_sortie,
                "bloc_fiche": any(li.startswith("fiche:") for li in lignes_t),
                "fact_levier_bloc": sum(1 for li in lignes_t if _BLOC_FACT.match(li)),
                "fact_levier_flux": sum(len(_FLOW_FACT.findall(li)) for li in lignes_t),
                "scalaires_plies": sum(1 for li in lignes_t if re.search(r":\s*[>|][-+]?\s*$", li)),
                "identique_octet": identique,
                "memes_donnees": meme_donnees,
                "lignes_retirees": retirees,
                "lignes_ajoutees": ajoutees,
                "lignes": len(lignes_t),
            }
        )
    n = len(lignes)
    avec_com = sum(1 for li in lignes if li["commentaires_pleins"])
    avec_fiche = sum(1 for li in lignes if li["bloc_fiche"])
    avec_bloc = sum(1 for li in lignes if li["fact_levier_bloc"])
    avec_flux = sum(1 for li in lignes if li["fact_levier_flux"])
    ident = sum(1 for li in lignes if li["identique_octet"])
    memes = sum(1 for li in lignes if li["memes_donnees"])
    com_perdus = sum(li["commentaires_pleins"] - li["commentaires_apres"] for li in lignes)
    dire(
        f"  {n} YAML : avec au moins un commentaire en ligne pleine {fmt(avec_com, n)} "
        f"({sum(li['commentaires_pleins'] for li in lignes)} lignes) ; bloc fiche: "
        f"{fmt(avec_fiche, n)} ; lignes fact:/levier: en style bloc dans {avec_bloc} fichiers "
        f"({sum(li['fact_levier_bloc'] for li in lignes)} lignes), en flux dans {avec_flux} "
        f"({sum(li['fact_levier_flux'] for li in lignes)})"
    )
    hors = [li for li in lignes if li["commentaires_hors_entete"]]
    dire(
        f"  commentaires : {sum(li['commentaires_entete_fiche'] for li in lignes)} lignes d'en-tête "
        f"du bloc fiche, {sum(li['commentaires_hors_entete'] for li in lignes)} lignes ailleurs "
        f"(justifications) dans {fmt(len(hors), n)} fichiers"
    )
    dire(
        f"  re-sérialisation par la fonction d'ecrire_aide : identique à l'octet "
        f"{fmt(ident, n)} ; mêmes données après rechargement {fmt(memes, n)} ; commentaires "
        f"perdus {com_perdus} lignes ; lignes retirées/ajoutées par le diff : "
        f"{sum(li['lignes_retirees'] for li in lignes)} / {sum(li['lignes_ajoutees'] for li in lignes)} "
        f"sur {sum(li['lignes'] for li in lignes)}"
    )
    rng = random.Random(0)
    ech = rng.sample(lignes, min(taille_echantillon, n))
    e_ident = sum(1 for li in ech if li["identique_octet"])
    dire(
        f"  échantillon de {len(ech)} (graine 0) : identique à l'octet {fmt(e_ident, len(ech))} ; "
        f"commentaires perdus {sum(li['commentaires_pleins'] - li['commentaires_apres'] for li in ech)}"
    )
    # Exemple documenté : la ré-extraction de veille du 2026-10-05
    exemple = {}
    try:
        diff = git.cmd(
            "diff",
            "b4226e37",
            "c36cbfd9",
            "--",
            "backend/data/aides/88-restauration-patrimoine.yaml",
        )
        exemple = {
            "commentaires_retires": [li for li in diff.splitlines() if re.match(r"^-\s*#", li)],
            "lignes_retirees": sum(
                1 for li in diff.splitlines() if li.startswith("-") and not li.startswith("---")
            ),
            "lignes_ajoutees": sum(
                1 for li in diff.splitlines() if li.startswith("+") and not li.startswith("+++")
            ),
        }
        dire(
            f"  88-restauration-patrimoine, b4226e37..c36cbfd9 : {len(exemple['commentaires_retires'])} "
            f"ligne(s) de commentaire retirée(s), {exemple['lignes_retirees']} - / "
            f"{exemple['lignes_ajoutees']} +"
        )
    except subprocess.CalledProcessError as exc:
        exemple = {"erreur": str(exc)}
    # Ré-extractions réelles du 2026-10-05 (worktree veille-hebdo), comparées à
    # l'état committé juste avant le commit qui les a reçues (c36cbfd9^).
    reext = []
    runs_vh: list[dict] = []
    for f in sorted((LOGS / "depuis-veille-hebdo").glob("ingest-*.log")):
        runs_vh += lire_runs(f)
    for r in runs_vh:
        if r["issue"] != "ok" or not r["yaml_final"]:
            continue
        avant = git.lire(f"c36cbfd9^:backend/data/aides/{r['slug']}.yaml")
        apres_commit = git.lire(f"c36cbfd9:backend/data/aides/{r['slug']}.yaml")
        b_av, b_ap = aide_brute(avant), aide_brute(r["yaml_final"])
        com_av = sum(1 for li in (avant or "").splitlines() if li.lstrip().startswith("#"))
        ids_av = set(conditions_brutes(avant))
        ids_ap = set(conditions_brutes(r["yaml_final"]))
        reext.append(
            {
                "slug": r["slug"],
                "fiche_avant": "fiche" in b_av,
                "fiche_sortie_pipeline": "fiche" in b_ap,
                "fiche_identique": b_av.get("fiche") == b_ap.get("fiche"),
                "fiche_dans_commit_c36cbfd9": "fiche" in aide_brute(apres_commit),
                "commentaires_avant": com_av,
                "commentaires_sortie": 0,
                "ids_conservees": len(ids_av & ids_ap),
                "ids_avant": len(ids_av),
                "ids_sortie": len(ids_ap),
            }
        )
    for x in reext:
        dire(
            f"  ré-extraction {x['slug']} : fiche avant {x['fiche_avant']}, en sortie "
            f"{x['fiche_sortie_pipeline']} (identique {x['fiche_identique']}), committée "
            f"{x['fiche_dans_commit_c36cbfd9']} ; commentaires {x['commentaires_avant']} -> 0 ; "
            f"ids conservés {x['ids_conservees']}/{x['ids_avant']} (sortie {x['ids_sortie']})"
        )
    sortie = {"fichiers": lignes, "exemple_88": exemple, "reextractions_2026_10_05": reext}
    ecrire_json("ecriture.json", sortie)
    return sortie


# ---------------------------------------------------------------------------
# 6. Vérificateur adversarial, relu dans les journaux
# ---------------------------------------------------------------------------

_ENTETE = re.compile(r"^(\S+) — (\d{4}-\d\d-\d\d)T\S+ — ingestion (.+) / vérification (.+)$")
_EVT_VERIF = re.compile(
    r"^\[\*\] vérification(?: (\d+)/\d+)? : (\d+) problème\(s\), (\d+) bloquant\(s\)"
)
_PROB = re.compile(r"^- \*\*(BLOQUANT|MINEUR) / (\w+)\*\*(?: \[([^\]]+)\])? — ")
_ENTETE_VERIF = re.compile(r"Vérification adversariale : (\d+) problème\(s\), dont (\d+) bloquant")

CHAMPS_TYPAGE = (
    "kind",
    "effect",
    "fact",
    "field",
    "predicate",
    "levier",
    "applies_if",
    "derogation_possible",
)


def _yaml_de_appel(ligne: str) -> str | None:
    debut = ligne.find("(")
    if debut < 0 or not ligne.rstrip().endswith(")"):
        return None
    try:
        args = json.loads(ligne[debut + 1 : ligne.rstrip().rfind(")")])
    except json.JSONDecodeError:
        return None
    return args.get("yaml_texte") if isinstance(args, dict) else None


def lire_runs(chemin: Path) -> list[dict]:
    runs: list[dict] = []
    courant: dict | None = None
    yaml_attente: str | None = None
    attente_verif = False
    probs_en_cours: list | None = None
    lignes = chemin.read_text(encoding="utf-8", errors="replace").splitlines()
    for li in lignes:
        m = _ENTETE.match(li)
        if m:
            courant = {
                "fichier": str(chemin.relative_to(LOGS)),
                "slug": m.group(1),
                "date": m.group(2),
                "modele": m.group(3),
                "modele_verif": m.group(4),
                "verifs": [],
                "yaml_courant": None,
                "yaml_final": None,
                "issue": None,
                "plafond": False,
                "indisponible": 0,
            }
            runs.append(courant)
            continue
        if courant is None:
            continue
        if li.startswith("[appel] "):
            probs_en_cours = None
            attente_verif = li.startswith("[appel] verification_adversariale")
            yaml_attente = _yaml_de_appel(li) if li.startswith("[appel] ecrire_aide(") else None
            continue
        if li.startswith("[sortie] "):
            corps = li[len("[sortie] ") :]
            if yaml_attente is not None and corps.startswith("Écrit :"):
                courant["yaml_courant"] = yaml_attente
                courant["yaml_final"] = yaml_attente
            yaml_attente = None
            if attente_verif:
                attente_verif = False
                v = {
                    "yaml": courant["yaml_courant"],
                    "annonce": None,
                    "problemes": [],
                    "plafond": corps.startswith("Plafond atteint"),
                    "indisponible": False,
                }
                if v["plafond"]:
                    courant["plafond"] = True
                m2 = _ENTETE_VERIF.search(corps)
                if m2:
                    v["annonce"] = (int(m2.group(1)), int(m2.group(2)))
                elif "aucun problème relevé" in corps:
                    v["annonce"] = (0, 0)
                courant.setdefault("sorties_verif", []).append(v)
                probs_en_cours = v["problemes"]
            continue
        if li.startswith("--- tour") or li.startswith("[*]"):
            probs_en_cours = None
        if probs_en_cours is not None:
            m3 = _PROB.match(li)
            if m3:
                probs_en_cours.append(
                    {
                        "severite": m3.group(1).lower(),
                        "axe": m3.group(2),
                        "condition_id": m3.group(3),
                    }
                )
            if "Vérificateur indisponible" in li:
                courant["indisponible"] += 1
                if courant.get("sorties_verif"):
                    courant["sorties_verif"][-1]["indisponible"] = True
        m4 = _EVT_VERIF.match(li)
        if m4:
            courant["verifs"].append(
                {
                    "passage": int(m4.group(1)) if m4.group(1) else len(courant["verifs"]) + 1,
                    "problemes": int(m4.group(2)),
                    "bloquants": int(m4.group(3)),
                }
            )
            continue
        if li.startswith("[*] OK"):
            courant["issue"] = "ok"
        elif li.startswith("[*] ÉCHEC"):
            courant["issue"] = "echec"
        elif li.startswith("[*] hors périmètre") or "declarer_hors_perimetre" in li[:40]:
            pass
    return runs


_HEAD_CACHE: dict[str, dict] = {}


def head_conditions(slug: str) -> dict:
    if slug not in _HEAD_CACHE:
        chemin = AIDES / f"{slug}.yaml"
        _HEAD_CACHE[slug] = conditions_brutes(
            chemin.read_text(encoding="utf-8") if chemin.exists() else None
        )
    return _HEAD_CACHE[slug]


def _devenir(cond_v: dict | None, cond_f: dict | None) -> str:
    if cond_v is None:
        return "absente_au_passage"
    if cond_f is None:
        return "retiree"
    if any(cond_v.get(k) != cond_f.get(k) for k in CHAMPS_TYPAGE):
        return "retypee"
    if cond_v.get("quote") != cond_f.get("quote") or cond_v.get("text") != cond_f.get("text"):
        return "texte_ou_quote_modifie"
    return "inchangee"


def _hors_conditions(brut: dict) -> dict:
    return {k: v for k, v in brut.items() if k not in ("conditions", "fiche", "source")}


def charger_runs() -> tuple[list[Path], list[dict], list[dict]]:
    fichiers: list[Path] = []
    for d in DOSSIERS_JOURNAUX:
        fichiers += sorted(d.glob("ingest-*.log"))
    runs: list[dict] = []
    for f in fichiers:
        runs += lire_runs(f)
    # Banc du 2026-10-07 à part
    banc: list[dict] = []
    for f in sorted(
        (LOGS / "bench-ingestion-2026-10-07" / "assemble").glob("*/reviews/logs/*.log")
    ):
        banc += lire_runs(f)
    return fichiers, runs, banc


def section_verificateur(fichiers: list[Path], runs: list[dict], banc: list[dict]) -> dict:
    dire("== 6. Vérificateur adversarial (journaux d'ingestion, lecture seule)")
    dire(f"  {len(fichiers)} journaux, {len(runs)} runs (+ {len(banc)} runs du banc)")

    bloquants_lignes = []
    stats: dict[str, Counter] = defaultdict(Counter)
    axes = Counter()
    axes_tous = Counter()
    for run in runs + banc:
        per = "banc" if run in banc else epoque(run["date"])
        st = stats[per]
        st["runs"] += 1
        vs = run["verifs"]
        if not vs:
            continue
        st["runs_verifies"] += 1
        st[f"issue_{run['issue']}"] += 1
        if vs[0]["bloquants"]:
            st["bloquant_passage1"] += 1
        if vs[-1]["bloquants"]:
            st["bloquant_dernier_passage"] += 1
        if any(v["bloquants"] for v in vs):
            st["bloquant_un_passage"] += 1
        if run["plafond"]:
            st["plafond"] += 1
        if run["indisponible"]:
            st["indisponible"] += 1
        st["passages"] += len(vs)
        if vs[0]["bloquants"] and not vs[-1]["bloquants"]:
            st["bloquant_resolu_au_dernier"] += 1
        if any(v["bloquants"] for v in vs):
            st[f"avec_bloquant_issue_{run['issue']}"] += 1
        # Devenir des bloquants par condition
        final = conditions_brutes(run["yaml_final"])
        final_aide = _hors_conditions(aide_brute(run["yaml_final"]))
        for i, sv in enumerate(run.get("sorties_verif", [])):
            if sv["annonce"]:
                st["bloquants_annonces"] += sv["annonce"][1]
            au_passage = conditions_brutes(sv["yaml"])
            aide_passage = _hors_conditions(aide_brute(sv["yaml"]))
            for p in sv["problemes"]:
                axes_tous[(p["severite"], p["axe"])] += 1
                if p["severite"] != "bloquant":
                    continue
                st["bloquants_lus"] += 1
                axes[p["axe"]] += 1
                cid = p["condition_id"]
                if cid:
                    dev = _devenir(au_passage.get(cid), final.get(cid))
                else:
                    dev = "fiche_modifiee" if aide_passage != final_aide else "fiche_inchangee"
                st[f"devenir_{dev}"] += 1
                etat_head = (
                    "catalogue"
                    if (AIDES / f"{run['slug']}.yaml").exists()
                    else "echec"
                    if (AIDES / f"{run['slug']}.yaml.echec").exists()
                    else "absente"
                )
                plus_tard = None
                if (
                    cid
                    and etat_head == "catalogue"
                    and dev in ("inchangee", "texte_ou_quote_modifie")
                ):
                    head = head_conditions(run["slug"]).get(cid)
                    vf = final.get(cid)
                    if head is None:
                        plus_tard = "retiree_plus_tard"
                    elif vf and any(vf.get(k) != head.get(k) for k in CHAMPS_TYPAGE):
                        plus_tard = "retypee_plus_tard"
                    else:
                        plus_tard = "identique_a_head"
                    st[f"inchangee_puis_{plus_tard}"] += 1
                st[f"modeles_{run['modele']} / {run['modele_verif']}"] += 0
                bloquants_lignes.append(
                    {
                        "periode": per,
                        "modeles": f"{run['modele']} / {run['modele_verif']}",
                        "plus_tard": plus_tard,
                        "fichier": run["fichier"],
                        "slug": run["slug"],
                        "date": run["date"],
                        "passage": i + 1,
                        "axe": p["axe"],
                        "condition_id": cid,
                        "devenir": dev,
                        "issue_run": run["issue"],
                        "plafond_run": run["plafond"],
                        "etat_head": etat_head,
                    }
                )
    par_modeles: dict[str, Counter] = defaultdict(Counter)
    etat_runs_bloquant = Counter()
    for run in runs:
        vs = run["verifs"]
        if not vs:
            continue
        cle = f"{epoque(run['date'])[:2]} {run['modele']} / {run['modele_verif']}"
        pm = par_modeles[cle]
        pm["runs_verifies"] += 1
        pm["bloquant_passage1"] += bool(vs[0]["bloquants"])
        pm["bloquant_dernier"] += bool(vs[-1]["bloquants"])
        pm["passages"] += len(vs)
        if any(v["bloquants"] for v in vs):
            etat = (
                "catalogue"
                if (AIDES / f"{run['slug']}.yaml").exists()
                else "echec"
                if (AIDES / f"{run['slug']}.yaml.echec").exists()
                else "absente"
            )
            etat_runs_bloquant[(run["issue"], etat, bool(vs[-1]["bloquants"]))] += 1
    for cle, pm in sorted(par_modeles.items()):
        dire(
            f"  {cle:<70} vérifiés {pm['runs_verifies']:>4} ; bloquant au 1er passage "
            f"{fmt(pm['bloquant_passage1'], pm['runs_verifies'])} ; au dernier "
            f"{fmt(pm['bloquant_dernier'], pm['runs_verifies'])} ; passages/run "
            f"{pm['passages'] / pm['runs_verifies']:.2f}"
        )
    total = Counter()
    for per, st in stats.items():
        if per != "banc":
            total.update(st)
    stats["TOTAL hors banc"] = total
    for per in sorted(stats):
        st = stats[per]
        n = st["runs_verifies"]
        dire(
            f"  {per:<22} runs {st['runs']:>5}, vérifiés {n:>5} ; bloquant au 1er passage "
            f"{fmt(st['bloquant_passage1'], n)} ; au dernier {fmt(st['bloquant_dernier_passage'], n)} ; "
            f"plafond {st['plafond']} ; indisponible {st['indisponible']} ; passages {st['passages']}"
        )
    t = stats["TOTAL hors banc"]
    nb = t["bloquants_lus"]
    dire(
        f"  bloquants lus dans les sorties : {nb} (annoncés {t['bloquants_annonces']} ; la sortie "
        f"est tronquée à 3 000 caractères dans le journal)"
    )
    for k in sorted(k for k in t if k.startswith("devenir_")):
        dire(f"    {k:<36} {fmt(t[k], nb)}")
    dire(f"  axes des bloquants : {axes.most_common()}")
    runs_b = t["bloquant_un_passage"]
    dire(
        f"  runs avec au moins un bloquant : {runs_b} ; issue ok {t['avec_bloquant_issue_ok']}, "
        f"échec {t['avec_bloquant_issue_echec']}, sans issue {t['avec_bloquant_issue_None']}"
    )
    dire(
        "  runs avec au moins un bloquant, par (issue, état à HEAD, bloquant au dernier passage) : "
        + str({f"{a}|{b}|{c}": n for (a, b, c), n in sorted(etat_runs_bloquant.items(), key=str)})
    )
    for k in sorted(k for k in t if k.startswith("inchangee_puis_")):
        dire(f"    bloquant sur condition inchangée, aide au catalogue : {k} = {t[k]}")
    etat_runs = Counter(b["etat_head"] for b in bloquants_lignes if b["periode"] != "banc")
    dire(f"  état à HEAD des aides visées par un bloquant (par bloquant) : {dict(etat_runs)}")
    # Fiches : bloc « À trancher » en tête
    a_trancher = 0
    mention_bloquant = 0
    fiches_p = 0
    for chemin in REVIEWS.glob("*-ingest-*.md"):
        tete = chemin.read_text(encoding="utf-8", errors="replace")
        if "Généré par scripts/ingerer.py" not in tete[:600]:
            continue
        fiches_p += 1
        if "## ⚠ À trancher — bloquants non re-vérifiés" in tete:
            a_trancher += 1
        if re.search(r"bloquant", tete, re.I):
            mention_bloquant += 1
    dire(
        f"  fiches pipeline portant le bloc « À trancher — bloquants non re-vérifiés » "
        f"(plafond de vérification) : {fmt(a_trancher, fiches_p)} ; fiches qui emploient le mot "
        f"« bloquant » : {fmt(mention_bloquant, fiches_p)}"
    )
    with (SORTIE / "verificateur_bloquants.jsonl").open("w", encoding="utf-8") as fh:
        for b in bloquants_lignes:
            fh.write(json.dumps(b, ensure_ascii=False) + "\n")
    sortie = {
        "journaux": len(fichiers),
        "runs": len(runs),
        "stats": {k: dict(v) for k, v in stats.items()},
        "axes_bloquants": axes,
        "axes_tous": {f"{s}/{a}": n for (s, a), n in axes_tous.items()},
        "fiches_pipeline": fiches_p,
        "fiches_a_trancher": a_trancher,
        "modeles": Counter(f"{r['modele']} / {r['modele_verif']}" for r in runs),
        "par_modeles": {k: dict(v) for k, v in par_modeles.items()},
        "runs_avec_bloquant": {f"{a}|{b}|{c}": n for (a, b, c), n in etat_runs_bloquant.items()},
    }
    ecrire_json("verificateur.json", sortie)
    return sortie


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--sections",
        default="banc,citations,text_quote,typage,ecriture,verificateur",
    )
    parser.add_argument("--echantillon", type=int, default=50)
    args = parser.parse_args()
    SORTIE.mkdir(parents=True, exist_ok=True)
    sections = set(args.sections.split(","))
    git = Git()
    fiches = fiches_ingestion()
    groupes: dict[str, str] = {}
    for slug, f in fiches.items():
        if f["pipeline"] and (not f["manuel"] or min(f["pipeline"]) < min(f["manuel"])):
            groupes[slug] = "pipeline"
        else:
            groupes[slug] = "manuel"
    dire(
        f"Fiches d'ingestion : {sum(len(f['pipeline']) for f in fiches.values())} pipeline, "
        f"{sum(len(f['manuel']) for f in fiches.values())} manuelles, {len(fiches)} slugs ; "
        f"aides du catalogue par groupe : "
        f"{dict(Counter(groupes.get(p.stem, 'sans_fiche') for p in AIDES.glob('*.yaml')))}"
    )
    if "banc" in sections:
        section_banc(git)
    if "citations" in sections:
        section_citations(groupes)
    if "text_quote" in sections:
        section_text_quote(groupes)
    fichiers, runs, banc = charger_runs() if sections & {"typage", "verificateur"} else ([], [], [])
    if "typage" in sections:
        section_typage(git, fiches, groupes, runs)
    if "ecriture" in sections:
        section_ecriture(git, args.echantillon)
    if "verificateur" in sections:
        section_verificateur(fichiers, runs, banc)
    (SORTIE / "resume.txt").write_text("\n".join(RESUME) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
