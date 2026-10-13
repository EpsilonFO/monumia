"""Recompte adverse de la note M07 (extraction, typage, vérification, écriture).

Relecture indépendante de docs/refonte-pipeline/notes/extraction-typage.md :
ce script ne réutilise RIEN du script du mesureur (scripts/mesures/extraction_typage.py).
Il importe seulement les modules de production qui définissent les objets
mesurés (aides_schema, veille_text, veille_collect, comparer_aides), sans rien
leur faire écrire.

Commande (depuis backend/) :

    uv run python scripts/mesures/extraction_typage_recompte.py
    uv run python scripts/mesures/extraction_typage_recompte.py --sections verif,ecriture

Sections : banc, citations, textquote, typage, ecriture, verif.

Sorties : data/reviews/logs/refonte/2026-10-10-extraction-typage-recompte-1/
(un JSON par section et resume.txt).

Lecture seule : aucun appel réseau ni de modèle ; git seulement en lecture
(`log`, `cat-file --batch`) ; le cache disque de pdftotext n'est pas alimenté
(`veille_collect.pdf_bytes_to_text` est remplacé dans ce processus par une
lecture du cache du checkout principal, sinon un pdftotext vers la sortie
standard, sans écriture).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import string
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
SCRIPTS = BACKEND / "scripts"
DATA = BACKEND / "data"
AIDES = DATA / "aides"
REVIEWS = DATA / "reviews"
LOGS = REVIEWS / "logs"
SORTIE = LOGS / "refonte" / "2026-10-10-extraction-typage-recompte-1"
CACHES_PDF = (
    Path("/Users/felixollivier/monumia/backend/.cache/pdftotext"),
    BACKEND / ".cache" / "pdftotext",
)

sys.path[:0] = [str(SCRIPTS), str(BACKEND)]

import veille_collect  # noqa: E402
from veille_text import find_quote_in_any, normalize  # noqa: E402

from aides_schema import Aide, charger_yaml, load_aide  # noqa: E402


def _pdf_lecture_seule(content: bytes) -> str | None:
    sha = hashlib.sha256(content).hexdigest()
    for d in CACHES_PDF:
        f = d / f"{sha}.txt"
        if f.is_file():
            return f.read_text(encoding="utf-8")
    return veille_collect._pdftotext(content)


veille_collect.pdf_bytes_to_text = _pdf_lecture_seule  # type: ignore[assignment]

RESUME: list[str] = []


def dire(s: str = "") -> None:
    print(s, flush=True)
    RESUME.append(s)


def wilson(k: int, n: int) -> str:
    if n == 0:
        return f"{k}/0"
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return f"{k}/{n} = {100 * p:.1f} % [{100 * (c - m):.1f} ; {100 * (c + m):.1f}]"


def ecrire(nom: str, obj) -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / nom).write_text(
        json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )


class Cat:
    def __init__(self) -> None:
        self.p = subprocess.Popen(
            ["git", "-C", str(RACINE), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

    def lire(self, ref: str) -> str | None:
        assert self.p.stdin and self.p.stdout
        self.p.stdin.write((ref + "\n").encode())
        self.p.stdin.flush()
        tete = self.p.stdout.readline().decode().split()
        if len(tete) < 3 or tete[1] == "missing":
            return None
        data = self.p.stdout.read(int(tete[2]))
        self.p.stdout.read(1)
        return data.decode("utf-8", errors="replace")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(RACINE), *args], capture_output=True, text=True, check=True
    ).stdout


def charger(texte: str | None) -> dict:
    if not texte:
        return {}
    try:
        b = yaml.safe_load(texte)
    except yaml.YAMLError:
        return {}
    return b if isinstance(b, dict) else {}


def conds(brut: dict) -> dict[str, dict]:
    out = {}
    for c in brut.get("conditions") or []:
        if isinstance(c, dict) and c.get("id"):
            k = c.get("kind", "untyped")
            e = c.get("effect")
            if e is None:
                e = "info" if k in ("info", "discretionary") else "gate"
            d = dict(c)
            d["kind"], d["effect"] = k, e
            out[c["id"]] = d
    return out


TYPAGE = ("kind", "effect", "fact", "field", "predicate", "levier", "applies_if")


def groupe_par_slug() -> tuple[dict[str, str], dict[str, str]]:
    """Origine (pipeline / manuel) et date de la PREMIÈRE fiche d'ingestion."""
    premieres: dict[str, tuple[str, str]] = {}
    for f in sorted(REVIEWS.glob("*-ingest-*.md")):
        m = re.match(r"(\d{4}-\d\d-\d\d)-ingest-(.+)\.md$", f.name)
        if not m:
            continue
        date, slug = m.groups()
        tete = f.read_text(encoding="utf-8", errors="replace")[:400]
        orig = "pipeline" if "Généré par scripts/ingerer.py" in tete else "manuel"
        if slug not in premieres or date < premieres[slug][0]:
            premieres[slug] = (date, orig)
    return {s: v[1] for s, v in premieres.items()}, {s: v[0] for s, v in premieres.items()}


def epoque(d: str) -> str:
    if "2026-09-07" <= d <= "2026-09-14":
        return "E1"
    if "2026-09-17" <= d <= "2026-09-19":
        return "E2"
    if "2026-09-29" <= d <= "2026-09-30":
        return "E3"
    if "2026-10-04" <= d <= "2026-10-05":
        return "E4"
    return "autre"


# ---------------------------------------------------------------------------
# 1. Banc
# ---------------------------------------------------------------------------

BANC = LOGS / "bench-ingestion-2026-10-07" / "assemble"
SLUGS_BANC = (
    "hdf-jardins-en-scene",
    "hdf-actes-fonds-appui-projets-locaux",
    "88-patrimoine-protege-mh",
    "bretagne-edifices-publics",
    "pdl-cap-pcc",
)


def docs_de(dossier: Path) -> list[tuple[str, str, str]]:
    from veille_text import flatten_markdown_links, parse_front_matter

    out = []
    for p in sorted(dossier.iterdir()) if dossier.is_dir() else []:
        if p.suffix.lower() == ".md":
            _m, corps = parse_front_matter(p.read_text(encoding="utf-8", errors="replace"))
            out.append((p.name, flatten_markdown_links(corps), "text"))
        elif p.suffix.lower() == ".pdf":
            t = _pdf_lecture_seule(p.read_bytes())
            if t and len(t.strip()) >= veille_collect.PDF_MIN_TEXT:
                out.append((p.name, t, "pdf"))
    return out


def section_banc(cat: Cat) -> dict:
    from comparer_aides import apparier_conditions, comparer

    dire("== 1. Banc 2026-10-07 (comparer_aides.comparer, références à 3b2ec426)")
    res: dict = {}
    for modele in ("or-glm", "or-mistral-large"):
        tot = Counter()
        lignes = []
        for slug in SLUGS_BANC:
            cand_p = BANC / modele / "aides" / f"{slug}.yaml"
            if not cand_p.exists():
                echec = (BANC / modele / "aides" / f"{slug}.yaml.echec").exists()
                dire(f"  {modele:17} {slug:38} absent (echec={echec})")
                continue
            ref = Aide.model_validate(
                charger_yaml(cat.lire(f"3b2ec426:backend/data/aides/{slug}.yaml") or "")
            )
            cand = load_aide(cand_p)
            docs = docs_de(BANC / modele / "sources" / slug)
            comp = comparer(ref, cand, docs)
            paires, _manq, _trop = apparier_conditions(ref.conditions, cand.conditions)
            dec = {c.id for c in ref.conditions if c.effect in ("gate", "modulateur")}
            ke = sum(1 for r, c in paires if (r.kind, r.effect) == (c.kind, c.effect))
            dec_paires = [(r, c) for r, c in paires if r.id in dec]
            dec_decisif = sum(1 for _r, c in dec_paires if c.effect in ("gate", "modulateur"))
            dec_meme_effet = sum(1 for r, c in dec_paires if r.effect == c.effect)
            dec_meme_ke = sum(1 for r, c in dec_paires if (r.kind, r.effect) == (c.kind, c.effect))
            gates_ref = [c for c in ref.conditions if c.effect == "gate"]
            gates_ref_gate = sum(1 for r, c in paires if r.effect == "gate" and c.effect == "gate")
            # Statut des citations du candidat : exacte contiguë vs reconstituée.
            statuts = Counter()
            for c in cand.conditions:
                if c.quote:
                    _n, m = find_quote_in_any(c.quote, docs)
                    statuts[
                        ("trouvee_" + m.status + ("_reconstituee" if m.reconstitution else ""))
                        if m.found
                        else "introuvable"
                    ] += 1
            ligne = {
                "slug": slug,
                "score": comp.score,
                "decisives": (comp.decisives_retrouvees, comp.decisives_reference),
                "par_filtre": len(comp.couvertes_par_filtre),
                "precision": (comp.communes, comp.conditions_candidat),
                "quotes": (comp.citations_verifiees, comp.citations_candidat),
                "ke": (ke, len(paires)),
                "dec_appariees_et_decisives_chez_candidat": dec_decisif,
                "dec_appariees_meme_effect": dec_meme_effet,
                "dec_appariees_meme_kind_effect": dec_meme_ke,
                "gates_ref": len(gates_ref),
                "gates_ref_restes_gates": gates_ref_gate,
                "statuts_quotes": dict(statuts),
                "conditions_reference": comp.conditions_reference,
                "nb_docs": len(docs),
            }
            lignes.append(ligne)
            tot["dk"] += comp.decisives_retrouvees
            tot["dn"] += comp.decisives_reference
            tot["pk"] += comp.communes
            tot["pn"] += comp.conditions_candidat
            tot["qk"] += comp.citations_verifiees
            tot["qn"] += comp.citations_candidat
            tot["kek"] += ke
            tot["ken"] += len(paires)
            tot["dd"] += dec_decisif
            tot["dme"] += dec_meme_ke
            tot["filtre"] += len(comp.couvertes_par_filtre)
            tot["rn"] += comp.conditions_reference
            tot["score"] += comp.score
            for k, v in statuts.items():
                tot["q_" + k] += v
            dire(
                f"  {modele:17} {slug:38} score {comp.score:5.1f} | déc {comp.decisives_retrouvees}/"
                f"{comp.decisives_reference} (dont décisives AUSSI chez le candidat {dec_decisif}, "
                f"même kind+effect {dec_meme_ke}, par filtre {len(comp.couvertes_par_filtre)}) | "
                f"préc {comp.communes}/{comp.conditions_candidat} | quotes "
                f"{comp.citations_verifiees}/{comp.citations_candidat} {dict(statuts)} | ke {ke}/{len(paires)}"
            )
        n = len(lignes)
        dire(
            f"  {modele} poolé sur {n} aides : score moyen {tot['score'] / max(n, 1):.1f} ; "
            f"décisives {wilson(tot['dk'], tot['dn'])} ; décisives retrouvées ET typées décisives "
            f"par le candidat {wilson(tot['dd'], tot['dn'])} ; même kind+effect "
            f"{wilson(tot['dme'], tot['dn'])} ; précision {wilson(tot['pk'], tot['pn'])} ; "
            f"rappel toutes conditions {wilson(tot['pk'], tot['rn'])} ; quotes "
            f"{wilson(tot['qk'], tot['qn'])} ; kind+effect sur paires {wilson(tot['kek'], tot['ken'])}"
        )
        res[modele] = {"lignes": lignes, "total": dict(tot)}
    # Les deux modèles sur les MÊMES 4 aides (Mistral a échoué sur la 5e).
    communs = [
        s for s in SLUGS_BANC if all(any(li["slug"] == s for li in res[m]["lignes"]) for m in res)
    ]
    for m in res:
        dk = sum(li["decisives"][0] for li in res[m]["lignes"] if li["slug"] in communs)
        dn = sum(li["decisives"][1] for li in res[m]["lignes"] if li["slug"] in communs)
        pk = sum(li["precision"][0] for li in res[m]["lignes"] if li["slug"] in communs)
        pn = sum(li["precision"][1] for li in res[m]["lignes"] if li["slug"] in communs)
        dire(
            f"  {m} sur les {len(communs)} aides communes : décisives {wilson(dk, dn)} ; "
            f"précision {wilson(pk, pn)}"
        )
    ecrire("banc.json", res)
    return res


# ---------------------------------------------------------------------------
# 2. Citations
# ---------------------------------------------------------------------------


def section_citations(origine: dict[str, str]) -> dict:
    dire("== 2. Citations du catalogue (find_quote_in_any, load_baselines, lecture seule)")
    stats = Counter()
    par_groupe = defaultdict(Counter)
    statuts = Counter()
    introuvables = []
    eval_sans_quote = []
    norm_sans_quote = []
    mc_gate = []
    sans_effect = Counter()
    for p in sorted(AIDES.glob("*.yaml")):
        brut = charger(p.read_text(encoding="utf-8"))
        aide = Aide.model_validate(brut)
        g = origine.get(aide.slug, "sans_fiche")
        for c in brut.get("conditions") or []:
            if "effect" not in c:
                k = c.get("kind", "untyped")
                sans_effect[f"{k}->{'info' if k in ('info', 'discretionary') else 'gate'}"] += 1
        for c in aide.conditions:
            stats["conditions"] += 1
            if c.kind in ("auto", "user_fact", "discretionary", "manual_check") and not c.quote:
                eval_sans_quote.append((aide.slug, c.id))
            if c.effect in ("gate", "modulateur") and not c.quote:
                norm_sans_quote.append((aide.slug, c.id, c.kind, c.effect))
            if c.effect in ("gate", "modulateur"):
                stats["normatives"] += 1
            if c.kind in ("auto", "user_fact", "discretionary", "manual_check"):
                stats["evaluables"] += 1
            if c.kind == "manual_check" and c.effect == "gate":
                mc_gate.append((aide.slug, c.id))
        docs, illisibles, _prov = veille_collect.load_baselines(aide.slug)
        citees = [c for c in aide.conditions if c.quote]
        stats["citees"] += len(citees)
        par_groupe[g]["aides"] += 1
        par_groupe[g]["citees"] += len(citees)
        if not docs:
            stats["hors_portee_sans_doc"] += len(citees)
            stats["aides_sans_doc"] += 1
            continue
        touche = False
        for c in citees:
            _n, m = find_quote_in_any(c.quote or "", docs)
            if m.found:
                statuts[m.status + ("+reconstitution" if m.reconstitution else "")] += 1
                continue
            if illisibles:
                stats["hors_portee_illisible"] += 1
                continue
            touche = True
            stats["introuvables"] += 1
            par_groupe[g]["introuvables"] += 1
            stats["introuvables_" + c.effect] += 1
            introuvables.append((aide.slug, c.id, c.effect, g))
        if touche:
            stats["aides_touchees"] += 1
    n_aides = len(list(AIDES.glob("*.yaml")))
    dire(
        f"  {n_aides} aides, {stats['conditions']} conditions, {stats['citees']} citées ; "
        f"introuvables {wilson(stats['introuvables'], stats['citees'])} ; hors portée "
        f"{stats['hors_portee_sans_doc']} (sans instantané, {stats['aides_sans_doc']} aides) + "
        f"{stats['hors_portee_illisible']} (aide avec PDF illisible) ; aides touchées "
        f"{stats['aides_touchees']} ; par effect gate {stats['introuvables_gate']}, modulateur "
        f"{stats['introuvables_modulateur']}, info {stats['introuvables_info']}"
    )
    citees_controlees = (
        stats["citees"] - stats["hors_portee_sans_doc"] - stats["hors_portee_illisible"]
    )
    dire(
        f"  introuvables rapportées aux seules citations contrôlables : "
        f"{wilson(stats['introuvables'], citees_controlees)}"
    )
    dire(f"  statut des citations retrouvées : {dict(statuts)}")
    for g, c in sorted(par_groupe.items()):
        dire(
            f"    groupe {g:10} aides {c['aides']:4} introuvables {wilson(c['introuvables'], c['citees'])}"
        )
    dire(
        f"  évaluables sans quote {wilson(len(eval_sans_quote), stats['evaluables'])} ; "
        f"gate ou modulateur sans quote {wilson(len(norm_sans_quote), stats['normatives'])} ; "
        f"manual_check gate {mc_gate} ; conditions sans clé effect {sum(sans_effect.values())} "
        f"{dict(sans_effect)}"
    )
    res = {
        "stats": dict(stats),
        "par_groupe": {k: dict(v) for k, v in par_groupe.items()},
        "statuts": dict(statuts),
        "introuvables": introuvables,
        "evaluables_sans_quote": eval_sans_quote,
        "normatives_sans_quote": norm_sans_quote,
        "manual_check_gate": mc_gate,
        "sans_effect": dict(sans_effect),
    }
    ecrire("citations.json", res)
    return res


# ---------------------------------------------------------------------------
# 3. text contre quote
# ---------------------------------------------------------------------------

_PONCT = re.compile(rf"[{re.escape(string.punctuation)}«»“”’…•·\-–—]+")


def plat(s: str) -> str:
    return " ".join(_PONCT.sub(" ", normalize(s)).split())


# Mots vides de quatre lettres et plus : la couverture « contenu » ne compte que
# les mots porteurs, pour séparer l'habillage (« La demande doit être déposée
# par ») d'un changement de sens.
_VIDES = frozenset(
    [
        "doit",
        "doivent",
        "etre",
        "sont",
        "dans",
        "pour",
        "avec",
        "cette",
        "celle",
        "celui",
        "leur",
        "leurs",
        "elle",
        "elles",
        "plus",
        "tout",
        "tous",
        "toute",
        "toutes",
        "vous",
        "votre",
        "avoir",
        "fait",
        "faire",
        "peut",
        "peuvent",
        "sous",
        "entre",
        "ainsi",
        "aussi",
        "dont",
        "mais",
        "donc",
        "lors",
        "afin",
    ]
)

_NOMBRE = re.compile(r"\d+(?:[ .  ]\d{3})*(?:,\d+)?")


def nombres(s: str) -> set[str]:
    return {re.sub(r"[ .  ]", "", n) for n in _NOMBRE.findall(s)}


def section_textquote(origine: dict[str, str]) -> dict:
    dire("== 3. text contre quote")
    cat_ = Counter()
    cat_plat = Counter()
    couv: Counter = Counter()
    par_effect = defaultdict(Counter)
    par_groupe = defaultdict(Counter)
    nb = Counter()
    hors_corpus = []
    for p in sorted(AIDES.glob("*.yaml")):
        aide = load_aide(p)
        g = origine.get(aide.slug, "sans_fiche")
        corpus = None
        for c in aide.conditions:
            if not c.quote:
                continue
            t, q = normalize(c.text), normalize(c.quote)
            if t == q:
                k = "identique"
            elif t in q:
                k = "text_dans_quote"
            elif q in t:
                k = "quote_dans_text"
            else:
                k = "autre"
            cat_[k] += 1
            if k == "autre":
                mt = re.findall(r"\w+", t)
                mq = set(re.findall(r"\w+", q))
                cov = sum(m in mq for m in mt) / len(mt) if mt else 0.0
                mtc = [m for m in mt if len(m) >= 4 and m not in _VIDES]
                covc = sum(m in mq for m in mtc) / len(mtc) if mtc else 1.0
                for nom_, v in (("brut", cov), ("contenu", covc)):
                    tr = "legere" if v >= 0.8 else "reformulation" if v >= 0.5 else "reecriture"
                    couv[(nom_, c.effect, tr)] += 1
                    couv[(nom_, "toutes", tr)] += 1
            tp, qp = plat(c.text), plat(c.quote)
            if tp == qp:
                kp = "identique"
            elif tp and tp in qp:
                kp = "text_dans_quote"
            elif qp and qp in tp:
                kp = "quote_dans_text"
            else:
                kp = "autre"
            cat_plat[kp] += 1
            par_effect[c.effect][k] += 1
            par_groupe[g][k] += 1
            nt = nombres(c.text)
            if nt:
                nb["text_avec_nombre"] += 1
                manquants = nt - nombres(c.quote)
                if manquants:
                    nb["nombre_absent_quote"] += 1
                    if corpus is None:
                        docs, _ill, _p = veille_collect.load_baselines(aide.slug)
                        corpus = set().union(*(nombres(d[1]) for d in docs)) if docs else set()
                    if corpus:
                        nb["controlables"] += 1
                        if manquants - corpus:
                            nb["hors_corpus"] += 1
                            hors_corpus.append(
                                (aide.slug, c.id, c.effect, sorted(manquants - corpus))
                            )
    n = sum(cat_.values())
    diff = n - cat_["identique"] - cat_["text_dans_quote"]
    dire(f"  {n} citées ; ni identiques ni text inclus dans la quote : {wilson(diff, n)}")
    dire(f"  catégories (normalize) : {dict(cat_)}")
    diffp = n - cat_plat["identique"] - cat_plat["text_dans_quote"]
    dire(
        f"  même mesure sans ponctuation ni puces : {wilson(diffp, n)} ; catégories {dict(cat_plat)}"
    )
    for nom_ in ("brut", "contenu"):
        for e in ("toutes", "gate", "modulateur", "info"):
            n_e = sum(par_effect[e].values()) if e != "toutes" else n
            dire(
                f"    couverture {nom_:8} effect {e:10} réécriture (<0,5) "
                f"{wilson(couv[(nom_, e, 'reecriture')], n_e)} ; reformulation "
                f"{couv[(nom_, e, 'reformulation')]} ; légère {couv[(nom_, e, 'legere')]}"
            )
    for e, c in sorted(par_effect.items()):
        m = sum(c.values())
        dire(f"    effect {e:10} différents {wilson(m - c['identique'] - c['text_dans_quote'], m)}")
    for g, c in sorted(par_groupe.items()):
        m = sum(c.values())
        dire(f"    groupe {g:10} différents {wilson(m - c['identique'] - c['text_dans_quote'], m)}")
    dire(
        f"  nombres : text citant un nombre {nb['text_avec_nombre']} ; nombre absent de la quote "
        f"{nb['nombre_absent_quote']} ; contrôlables (aide avec sources) {nb['controlables']} ; "
        f"absents de toutes les sources {wilson(nb['hors_corpus'], nb['controlables'])} ; "
        f"rapporté à toutes les citées {wilson(nb['hors_corpus'], n)}"
    )
    res = {
        "categories": dict(cat_),
        "categories_sans_ponctuation": dict(cat_plat),
        "nombres": dict(nb),
        "hors_corpus": hors_corpus,
    }
    ecrire("textquote.json", res)
    return res


# ---------------------------------------------------------------------------
# 4. Typage
# ---------------------------------------------------------------------------


def section_typage(cat: Cat, origine: dict[str, str], date_fiche: dict[str, str]) -> dict:
    dire("== 4. Typage (git, lecture seule)")
    log = git(
        "log",
        "--no-merges",
        "--full-history",
        "--format=@@%H %ad",
        "--date=short",
        "--name-only",
        "HEAD",
        "--",
        "backend/data/aides",
    )
    commits = []
    for bloc in log.split("@@")[1:]:
        li = [x for x in bloc.splitlines() if x.strip()]
        h, d = li[0].split()
        commits.append((h, d, [f for f in li[1:] if f.endswith((".yaml", ".yaml.echec"))]))
    dire(f"  {len(commits)} commits non-merge touchent data/aides")
    mes_cles = set()
    mes_ke = set()
    paires = 0
    # par fichier : liste (date, commit, id, kind/effect avant, après, typage changé)
    ev_par_fichier: dict[str, list] = defaultdict(list)
    ajout: dict[str, tuple[str, str]] = {}
    for h, d, fichiers in commits:
        for f in fichiers:
            av, ap = cat.lire(f"{h}^:{f}"), cat.lire(f"{h}:{f}")
            nom = f.split("/")[-1]
            if av is None and ap is not None and nom.endswith(".yaml"):
                s = nom[:-5]
                if s not in ajout or d < ajout[s][0]:
                    ajout[s] = (d, h)
            if av is None or ap is None:
                continue
            ca, cb = conds(charger(av)), conds(charger(ap))
            for cid in ca.keys() & cb.keys():
                a, b = ca[cid], cb[cid]
                paires += 1
                ke = (a["kind"], a["effect"]) != (b["kind"], b["effect"])
                fa = a.get("fact") != b.get("fact") and a.get("fact") and b.get("fact")
                if ke or fa:
                    mes_cles.add((h[:8], nom, cid))
                if ke:
                    mes_ke.add((h[:8], nom, cid))
                ev_par_fichier[nom].append(
                    (d, h[:8], cid, (a["kind"], a["effect"]), (b["kind"], b["effect"]))
                )
    ref = json.loads(
        (LOGS / "refonte-entrees" / "be997c31-bilan-2026-10-07" / "transitions.json").read_text(
            encoding="utf-8"
        )
    )
    ref_cles = {(x["commit"], x["fichier"], x["id"]) for x in ref}
    ref_ke = {
        (x["commit"], x["fichier"], x["id"])
        for x in ref
        if (x["avant"]["kind"], x["avant"]["effect"]) != (x["apres"]["kind"], x["apres"]["effect"])
    }
    dire(
        f"  paires {paires} ; changements (kind/effect ou fait) {len(mes_cles)} contre "
        f"{len(ref_cles)} dans transitions.json (en trop {len(mes_cles - ref_cles)}, manquants "
        f"{len(ref_cles - mes_cles)}) ; dont changements de kind/effect {len(mes_ke)} "
        f"(transitions.json : {len(ref_ke)}), le reste ({len(ref_cles) - len(ref_ke)}) sont des "
        f"changements de fait à kind/effect constant"
    )

    # Conditions écrites par le pipeline, aides au catalogue à HEAD.
    stats = defaultdict(Counter)
    par_ep_uf = defaultdict(Counter)
    exposees = Counter()
    dest_head: Counter = Counter()
    dest_trans: Counter = Counter()
    for p in sorted(AIDES.glob("*.yaml")):
        s = p.stem
        if origine.get(s) != "pipeline" or s not in ajout:
            continue
        d_aj, h_aj = ajout[s]
        if date_fiche[s] > d_aj:
            continue
        init = conds(charger(cat.lire(f"{h_aj}:backend/data/aides/{s}.yaml")))
        head = conds(charger(p.read_text(encoding="utf-8")))
        evs = [e for e in ev_par_fichier.get(p.name, []) if e[1] != h_aj[:8] and e[0] >= d_aj]
        retypees = {e[2] for e in evs if e[3] != e[4]}
        ep = epoque(date_fiche[s])
        for cid, c in init.items():
            k = f"{c['kind']}/{c['effect']}"
            for cle in ("total", k, f"ep_{ep}"):
                stats[cle]["n"] += 1
                stats[cle]["retypee"] += cid in retypees
                if cid in head:
                    stats[cle]["head_n"] += 1
                    stats[cle]["head_change"] += (head[cid]["kind"], head[cid]["effect"]) != (
                        c["kind"],
                        c["effect"],
                    )
                else:
                    stats[cle]["retiree"] += 1
            if k == "user_fact/gate":
                if cid in head and (head[cid]["kind"], head[cid]["effect"]) != (
                    c["kind"],
                    c["effect"],
                ):
                    dest_head[f"{head[cid]['kind']}/{head[cid]['effect']}"] += 1
                for e in evs:
                    if e[2] == cid and e[3] != e[4]:
                        dest_trans[(e[1], f"{e[4][0]}/{e[4][1]}")] += 1
                par_ep_uf[ep]["n"] += 1
                par_ep_uf[ep]["retypee"] += cid in retypees
                avant_doctrine = d_aj < "2026-09-23"
                exposees["avant" if avant_doctrine else "apres"] += 1
                exposees["avant_r" if avant_doctrine else "apres_r"] += cid in retypees
    for cle in ("total", "user_fact/gate", "user_fact/modulateur", "auto/gate", "info/info"):
        c = stats[cle]
        dire(
            f"    {cle:22} retypée >=1 fois {wilson(c['retypee'], c['n'])} ; à HEAD "
            f"{wilson(c['head_change'], c['head_n'])} ; retirées {c['retiree']}"
        )
    for ep in ("E1", "E2", "E3", "E4", "autre"):
        c = stats[f"ep_{ep}"]
        u = par_ep_uf[ep]
        dire(
            f"    époque {ep:5} toutes {wilson(c['retypee'], c['n'])} ; user_fact/gate "
            f"{wilson(u['retypee'], u['n'])}"
        )
    dire(f"  user_fact/gate retypés, état à HEAD : {dict(dest_head)}")
    dire(
        f"  user_fact/gate, transitions par commit et destination : {dict(dest_trans.most_common(12))}"
    )
    dire(
        f"  user_fact/gate du pipeline ajoutés au catalogue AVANT le 2026-09-23 (exposés aux "
        f"campagnes de doctrine) : {wilson(exposees['avant_r'], exposees['avant'])} ; après : "
        f"{wilson(exposees['apres_r'], exposees['apres'])}"
    )
    # Sortie du pipeline (dernier YAML d'un run OK, journal) contre premier commit.
    fichiers = (
        sorted(LOGS.glob("ingest-*.log"))
        + sorted((LOGS / "depuis-prospection-worktree").glob("ingest-*.log"))
        + sorted((LOGS / "depuis-veille-hebdo").glob("ingest-*.log"))
    )
    derniers: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for f in fichiers:
        for r in lire_runs(f):
            if r["issue"] == "ok" and r["yamls"]:
                derniers[r["slug"]].append((r["date"], r["yamls"][-1]))
    comp = Counter()
    diff_slugs = []
    for s_, (d_aj, h_aj) in sorted(ajout.items()):
        if origine.get(s_) != "pipeline" or date_fiche.get(s_, "9") > d_aj:
            continue
        cands = [x for x in derniers.get(s_, []) if x[0] <= d_aj]
        if not cands:
            comp["sans_run"] += 1
            continue
        sortie = charger(max(cands, key=lambda x: x[0])[1])
        commit = charger(cat.lire(f"{h_aj}:backend/data/aides/{s_}.yaml"))
        sortie.pop("fiche", None)
        commit.pop("fiche", None)
        comp["n"] += 1
        if sortie == commit:
            comp["identiques"] += 1
        else:
            cles = sorted(k for k in set(sortie) | set(commit) if sortie.get(k) != commit.get(k))
            diff_slugs.append((s_, cles))
            for k in cles:
                comp["cle_" + k] += 1
    dire(
        f"  sortie du pipeline contre premier commit (hors fiche) : identiques "
        f"{wilson(comp['identiques'], comp['n'])} ; sans run OK avant l'ajout {comp['sans_run']} ; "
        f"clés qui diffèrent : {dict((k, v) for k, v in comp.items() if k.startswith('cle_'))}"
    )
    res = {
        "cles_en_trop": sorted(mes_cles - ref_cles),
        "cles_manquantes": sorted(ref_cles - mes_cles),
        "stats": {k: dict(v) for k, v in stats.items()},
        "user_fact_gate_par_epoque": {k: dict(v) for k, v in par_ep_uf.items()},
        "exposition": dict(exposees),
        "ajout": ajout,
        "avant_commit": dict(comp),
        "avant_commit_differences": diff_slugs,
    }
    ecrire("typage.json", res)
    return res


# ---------------------------------------------------------------------------
# 5. Écriture
# ---------------------------------------------------------------------------


def dump_ingestion(texte: str) -> str:
    # La sérialisation d'ecrire_aide (scripts/ingestion/outils.py, ecrire_aide).
    return yaml.safe_dump(charger_yaml(texte), allow_unicode=True, sort_keys=False, width=100)


def sans_fiche(texte: str) -> str:
    li = texte.splitlines(keepends=True)
    i = next((k for k, x in enumerate(li) if x.startswith("fiche:")), None)
    if i is None:
        return texte
    j = next((k for k in range(i + 1, len(li)) if re.match(r"[A-Za-z_]", li[k])), len(li))
    while i > 0 and li[i - 1].startswith("#"):
        i -= 1
    return "".join(li[:i] + li[j:])


def section_ecriture(cat: Cat) -> dict:
    import difflib

    dire("== 5. Écriture")
    fichiers = sorted(AIDES.glob("*.yaml"))
    ident = ident_hors_fiche = memes = 0
    com_tot = com_justif = fich_justif = fiche_n = 0
    lignes_tot = diff_tot = diff_hors_fiche = 0
    lignes_hors_fiche_tot = 0
    par = {}
    for p in fichiers:
        t = p.read_text(encoding="utf-8")
        s = dump_ingestion(t)
        ident += s == t
        memes += charger_yaml(s) == charger_yaml(t)
        tl = t.splitlines()
        com = [x for x in tl if x.lstrip().startswith("#")]
        th = sans_fiche(t)
        com_h = [x for x in th.splitlines() if x.lstrip().startswith("#")]
        com_tot += len(com)
        com_justif += len(com_h)
        fich_justif += bool(com_h)
        fiche_n += any(x.startswith("fiche:") for x in tl)
        # hors fiche : la sérialisation de la partie hors fiche
        sh = dump_ingestion(th)
        ident_hors_fiche += sh == th
        d = sum(
            1
            for x in difflib.unified_diff(tl, s.splitlines(), lineterm="", n=0)
            if x.startswith("-") and not x.startswith("---")
        )
        dh = sum(
            1
            for x in difflib.unified_diff(th.splitlines(), sh.splitlines(), lineterm="", n=0)
            if x.startswith("-") and not x.startswith("---")
        )
        lignes_tot += len(tl)
        lignes_hors_fiche_tot += len(th.splitlines())
        diff_tot += d
        diff_hors_fiche += dh
        par[p.stem] = s == t
    n = len(fichiers)
    dire(
        f"  {n} YAML ; identiques à l'octet après safe_dump {wilson(ident, n)} ; mêmes données "
        f"{memes}/{n} ; commentaires {com_tot} lignes dont hors en-tête de fiche {com_justif} "
        f"dans {fich_justif} fichiers ; bloc fiche {fiche_n}"
    )
    dire(
        f"  lignes retirées par le diff : {diff_tot}/{lignes_tot} ; HORS bloc fiche : "
        f"{diff_hors_fiche}/{lignes_hors_fiche_tot} ; fichiers identiques hors bloc fiche "
        f"{wilson(ident_hors_fiche, n)}"
    )
    for graine in (0, 1):
        ech = random.Random(graine).sample(fichiers, 50)
        k = sum(par[x.stem] for x in ech)
        dire(f"  échantillon 50 (graine {graine}, tirage sur la liste triée) : {wilson(k, 50)}")

    # Ré-extractions du 2026-10-05 (veille-hebdo) : fiche avant / à la sortie.
    reext = []
    for f in sorted((LOGS / "depuis-veille-hebdo").glob("ingest-*.log")):
        for run in lire_runs(f):
            if run["issue"] != "ok" or not run["yamls"]:
                continue
            s = run["slug"]
            avant = charger(cat.lire(f"c36cbfd9^:backend/data/aides/{s}.yaml"))
            sortie = charger(run["yamls"][-1])
            commit = charger(cat.lire(f"c36cbfd9:backend/data/aides/{s}.yaml"))
            fa, fs, fc = avant.get("fiche"), sortie.get("fiche"), commit.get("fiche")
            cles_diff = (
                sorted(k for k in set(fa) | set(fs) if fa.get(k) != fs.get(k))
                if isinstance(fa, dict) and isinstance(fs, dict)
                else None
            )
            reext.append(
                {
                    "slug": s,
                    "fiche_avant": fa is not None,
                    "fiche_sortie": fs is not None,
                    "identique": fa == fs,
                    "cles_fiche_differentes": cles_diff,
                    "fiche_commit_egale_avant": fc == fa,
                    "fiche_commit_egale_sortie": fc == fs,
                }
            )
            dire(
                f"    {s:50} fiche avant {fa is not None} sortie {fs is not None} identique "
                f"{fa == fs} ; clés différentes {cles_diff} ; commit = avant {fc == fa}, "
                f"commit = sortie {fc == fs}"
            )
    res = {"identiques_octet": ident, "n": n, "reextractions": reext}
    ecrire("ecriture.json", res)
    return res


# ---------------------------------------------------------------------------
# 6. Journaux d'ingestion : vérificateur
# ---------------------------------------------------------------------------

_TETE = re.compile(r"^(\S+) — (\d{4}-\d\d-\d\d)T\S+ — ingestion (.+?) / vérification (.+)$")
_VERIF = re.compile(r"^\[\*\] vérification(?: (\d+)/\d+)? : (\d+) problème\(s\), (\d+) bloquant")
_BLOQ = re.compile(r"^- \*\*BLOQUANT / (\w+)\*\*(?: \[([^\]]+)\])?")


def lire_runs(chemin: Path) -> list[dict]:
    runs: list[dict] = []
    r: dict | None = None
    attente_yaml: str | None = None
    dans_verif = False
    for ligne in chemin.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _TETE.match(ligne)
        if m:
            r = {
                "fichier": chemin.name,
                "slug": m.group(1),
                "date": m.group(2),
                "ext": m.group(3),
                "verif": m.group(4),
                "yamls": [],
                "passages": [],
                "sorties_verif": [],
                "issue": None,
            }
            runs.append(r)
            continue
        if r is None:
            continue
        if ligne.startswith("[appel] "):
            dans_verif = ligne.startswith("[appel] verification_adversariale")
            attente_yaml = None
            if ligne.startswith("[appel] ecrire_aide("):
                corps = ligne[len("[appel] ecrire_aide(") :].rstrip()
                if corps.endswith(")"):
                    try:
                        a = json.loads(corps[:-1])
                        attente_yaml = a.get("yaml_texte") if isinstance(a, dict) else None
                    except json.JSONDecodeError:
                        attente_yaml = None
            continue
        if ligne.startswith("[sortie] "):
            corps = ligne[len("[sortie] ") :]
            if attente_yaml is not None and corps.startswith("Écrit :"):
                r["yamls"].append(attente_yaml)
            attente_yaml = None
            if dans_verif:
                r["sorties_verif"].append(
                    {
                        "yaml_idx": len(r["yamls"]) - 1,
                        "indisponible": False,
                        "plafond": corps.startswith("Plafond atteint"),
                        "bloquants": [],
                    }
                )
            continue
        if ligne.startswith(("--- tour", "[*]", "[texte]", "[raisonnement]")):
            dans_verif = False if not ligne.startswith("[*] vérification") else dans_verif
        if dans_verif and r["sorties_verif"]:
            sv = r["sorties_verif"][-1]
            if "Vérificateur indisponible" in ligne:
                sv["indisponible"] = True
            mb = _BLOQ.match(ligne)
            if mb:
                sv["bloquants"].append((mb.group(1), mb.group(2)))
        mv = _VERIF.match(ligne)
        if mv:
            r["passages"].append((int(mv.group(2)), int(mv.group(3))))
            dans_verif = False
            continue
        if ligne.startswith("[*] OK"):
            r["issue"] = "ok"
        elif ligne.startswith("[*] ÉCHEC"):
            r["issue"] = "echec"
    return runs


def section_verif(cat: Cat) -> dict:
    dire("== 6. Vérificateur (journaux ingest-*.log)")
    fichiers = (
        sorted(LOGS.glob("ingest-*.log"))
        + sorted((LOGS / "depuis-prospection-worktree").glob("ingest-*.log"))
        + sorted((LOGS / "depuis-veille-hebdo").glob("ingest-*.log"))
    )
    runs = [r for f in fichiers for r in lire_runs(f)]
    dire(f"  {len(fichiers)} journaux, {len(runs)} runs")
    # Les sorties de vérification sont associées aux passages dans l'ordre.
    par_ep = defaultdict(Counter)
    par_conf = defaultdict(Counter)
    for r in runs:
        if not r["passages"]:
            continue
        ep = epoque(r["date"])
        conf = f"{ep} {r['ext']} / {r['verif']}"
        prem_bloq = r["passages"][0][1] > 0
        dern_bloq = r["passages"][-1][1] > 0
        sv = [s for s in r["sorties_verif"] if not s["plafond"]]
        prem_indispo = bool(sv) and sv[0]["indisponible"]
        indispo = sum(1 for s in sv if s["indisponible"])
        for cle, dico in ((ep, par_ep), (conf, par_conf), ("TOTAL", par_ep)):
            c = dico[cle]
            c["verifies"] += 1
            c["prem_bloq"] += prem_bloq
            c["dern_bloq"] += dern_bloq
            c["passages"] += len(r["passages"])
            c["prem_indispo"] += prem_indispo
            c["runs_avec_indispo"] += indispo > 0
            c["passages_indispo"] += indispo
            if not prem_indispo:
                c["verifies_prem_dispo"] += 1
                c["prem_bloq_dispo"] += prem_bloq
    for cle in ("E1", "E2", "E3", "E4", "TOTAL"):
        c = par_ep[cle]
        dire(
            f"  {cle:5} vérifiés {c['verifies']:4} ; bloquant au 1er passage "
            f"{wilson(c['prem_bloq'], c['verifies'])} ; au dernier {wilson(c['dern_bloq'], c['verifies'])} ; "
            f"passages {c['passages']} ; 1er passage indisponible {c['prem_indispo']} ; passages "
            f"indisponibles {c['passages_indispo']} ; 1er passage disponible : bloquant "
            f"{wilson(c['prem_bloq_dispo'], c['verifies_prem_dispo'])}"
        )
    for cle, c in sorted(par_conf.items()):
        dire(
            f"    {cle:75} vérifiés {c['verifies']:4} ; 1er bloquant {wilson(c['prem_bloq'], c['verifies'])} ; "
            f"1er indispo {c['prem_indispo']} ; 1er bloquant si 1er disponible "
            f"{wilson(c['prem_bloq_dispo'], c['verifies_prem_dispo'])}"
        )

    # Devenir des bloquants lus, et contrôle par les conditions NON signalées.
    devenir = Counter()
    annonces = 0
    lus = 0
    inchangees_catalogue = []
    signalees_par_run = defaultdict(set)
    finales: dict[tuple[str, str], dict] = {}
    for r in runs:
        if not r["yamls"]:
            continue
        final = conds(charger(r["yamls"][-1]))
        sv_utiles = [s for s in r["sorties_verif"] if not s["plafond"]]
        if len(sv_utiles) != len(r["passages"]):
            devenir["_runs_desalignes"] += 1
        for (_np, nb), sv in zip(r["passages"], sv_utiles, strict=False):
            annonces += nb
            if sv["yaml_idx"] < 0:
                continue
            courant = conds(charger(r["yamls"][sv["yaml_idx"]]))
            for axe, cid in sv["bloquants"]:
                lus += 1
                if not cid or cid not in courant:
                    devenir["sans_condition_ou_absente"] += 1
                    continue
                signalees_par_run[(r["fichier"], r["date"], r["slug"])].add(cid)
                a = courant[cid]
                b = final.get(cid)
                if b is None:
                    devenir["retiree"] += 1
                elif any(a.get(k) != b.get(k) for k in TYPAGE):
                    devenir["retypee"] += 1
                elif a.get("text") != b.get("text") or a.get("quote") != b.get("quote"):
                    devenir["texte_quote"] += 1
                else:
                    devenir["inchangee"] += 1
                    if r["issue"] == "ok" and (AIDES / f"{r['slug']}.yaml").exists():
                        inchangees_catalogue.append((r["slug"], cid, axe, r["date"], b))
        if r["issue"] == "ok":
            finales[(r["slug"], r["date"])] = final
    n_dev = sum(devenir.values())
    dire(
        f"  bloquants annoncés {annonces}, lus {lus} ; devenir : "
        + " ; ".join(f"{k} {wilson(v, n_dev)}" for k, v in devenir.most_common())
    )
    # Ceux restés inchangés dans une aide au catalogue : état à HEAD.
    head_cache: dict[str, dict] = {}

    def head(slug: str) -> dict:
        if slug not in head_cache:
            head_cache[slug] = conds(charger((AIDES / f"{slug}.yaml").read_text(encoding="utf-8")))
        return head_cache[slug]

    vus = set()
    issue = Counter()
    for slug, cid, _axe, _d, b in inchangees_catalogue:
        if (slug, cid) in vus:
            continue
        vus.add((slug, cid))
        h = head(slug).get(cid)
        if h is None:
            issue["retiree_a_head"] += 1
        elif any(h.get(k) != b.get(k) for k in TYPAGE):
            issue["typage_change_a_head"] += 1
        else:
            issue["identique"] += 1
    n_inch = len(inchangees_catalogue)
    dire(
        f"  bloquants « inchangée » dans une aide au catalogue : {n_inch} occurrences, "
        f"{len(vus)} conditions distinctes ; à HEAD : {dict(issue)} ; corrigées plus tard "
        f"(conditions distinctes) {wilson(issue['retiree_a_head'] + issue['typage_change_a_head'], len(vus))}"
    )
    # Taux de base : conditions NON signalées des mêmes runs (aides au catalogue).
    base = Counter()
    for r in runs:
        if r["issue"] != "ok" or not r["yamls"] or not (AIDES / f"{r['slug']}.yaml").exists():
            continue
        cles = signalees_par_run.get((r["fichier"], r["date"], r["slug"]))
        if not cles:
            continue
        final = conds(charger(r["yamls"][-1]))
        for cid, b in final.items():
            if cid in cles:
                continue
            h = head(r["slug"]).get(cid)
            k = f"{b['kind']}/{b['effect']}"
            for cle in ("toutes", k):
                base[cle + "_n"] += 1
                base[cle + "_change"] += h is None or any(h.get(x) != b.get(x) for x in TYPAGE)
    dire(
        f"  taux de base : conditions NON signalées des mêmes runs (aides au catalogue), "
        f"changées ou retirées à HEAD {wilson(base['toutes_change'], base['toutes_n'])} ; "
        f"user_fact/gate {wilson(base['user_fact/gate_change'], base['user_fact/gate_n'])}"
    )
    # Même chose, stratifié sur le kind/effect des bloquants inchangés.
    strat = Counter()
    for slug, cid in vus:
        b = next(x[4] for x in inchangees_catalogue if x[0] == slug and x[1] == cid)
        h = head(slug).get(cid)
        k = f"{b['kind']}/{b['effect']}"
        strat[k + "_n"] += 1
        strat[k + "_change"] += h is None or any(h.get(x) != b.get(x) for x in TYPAGE)
    dire(
        "  bloquants inchangés, par kind/effect : "
        + " ; ".join(
            f"{k[:-2]} {wilson(strat[k[:-2] + '_change'], strat[k])}"
            for k in sorted(strat)
            if k.endswith("_n")
        )
    )
    res = {
        "par_epoque": {k: dict(v) for k, v in par_ep.items()},
        "par_configuration": {k: dict(v) for k, v in par_conf.items()},
        "devenir": dict(devenir),
        "annonces": annonces,
        "lus": lus,
        "inchangees_catalogue_head": dict(issue),
        "taux_de_base": dict(base),
        "strates": dict(strat),
    }
    ecrire("verif.json", res)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", default="banc,citations,textquote,typage,ecriture,verif")
    args = ap.parse_args()
    sections = set(args.sections.split(","))
    cat = Cat()
    origine, date_fiche = groupe_par_slug()
    dire(
        f"fiches d'ingestion : {Counter(origine.values())} slugs ; catalogue par origine : "
        f"{Counter(origine.get(p.stem, 'sans_fiche') for p in AIDES.glob('*.yaml'))}"
    )
    if "banc" in sections:
        section_banc(cat)
    if "citations" in sections:
        section_citations(origine)
    if "textquote" in sections:
        section_textquote(origine)
    if "typage" in sections:
        section_typage(cat, origine, date_fiche)
    if "ecriture" in sections:
        section_ecriture(cat)
    if "verif" in sections:
        section_verif(cat)
    SORTIE.mkdir(parents=True, exist_ok=True)
    nom = "resume-" + "-".join(sorted(sections)) + ".txt"
    (SORTIE / nom).write_text("\n".join(RESUME) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
