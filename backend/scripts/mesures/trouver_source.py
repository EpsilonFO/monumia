"""Ligne de base de l'operation « trouver une source » (collecte des URL d'un guide des aides).

Commande, depuis backend/ :

    uv run python scripts/mesures/trouver_source.py

Produit, dans data/reviews/logs/refonte/2026-10-10-trouver-source-1/ :

- recettes.json    : les 114 recettes de territoires.yaml (strategie, statut, bornes)
- fiches.json      : chaque fiche de prospection data/reviews/*-prospection-*.md, lue
                     (ligne de collecte, sections, notes techniques, cout)
- couverture.json  : un verdict par territoire (jamais balaye, collecte nulle, tout
                     ecarte, seulement a_valider, au moins une ingeree...)
- vagues.json      : rendement de la collecte par vague de balayage (date de fiche)
- decouverte.json  : les prefixes choisis par le LLM de decouverte et ce qu'ils ont rendu
- candidats.json   : les candidats.jsonl hors git (checkout principal et worktree
                     prospection), par territoire
- moselle.json     : l'incident de la Moselle relu dans les journaux de balayage
- doublons.json    : normalisation d'URL et doublons de la file et des .yaml.echec
- resume.txt       : les chiffres repris dans docs/refonte-pipeline/notes/trouver-source.md

Lecture seule : aucun appel reseau, aucun modele, aucune ecriture hors du dossier de
sortie. Les modules importes (prospection.collecte, prospection.territoires,
pipeline.etat, aides_schema) ne font que lire.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from pipeline.etat import FILE_ATTENTE, charger  # noqa: E402
from prospection.collecte import chemin_en_boucle, cle_fiche  # noqa: E402
from prospection.territoires import aides_existantes, charger_territoires  # noqa: E402
from veille_collect import cle_url  # noqa: E402

from aides_schema import load_all_aides  # noqa: E402
from labels import DEPARTEMENT_LABELS, REGION_LABELS  # noqa: E402

REVIEWS = BACKEND / "data" / "reviews"
SORTIE = REVIEWS / "logs" / "refonte" / "2026-10-10-trouver-source-1"
LOGS_BALAYAGE = REVIEWS / "logs" / "balayage"
# Intermediaires hors git (ignores par .gitignore), lus en place, jamais copies.
DEPOT = Path("/Users/felixollivier/monumia")
SOURCES_CANDIDATS = [
    DEPOT / "backend" / "data" / "prospection",
    DEPOT / ".claude" / "worktrees" / "prospection" / "backend" / "data" / "prospection",
]
# Les 7 dossiers versionnes de ce worktree portent la date du checkout (mtime du
# 2026-10-10), pas celle du balayage : ils ne servent qu'en dernier recours.
REPLI_CANDIDATS = BACKEND / "data" / "prospection"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Intervalle de Wilson a 95 % pour k succes sur n."""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - m), 3), round(min(1.0, c + m), 3))


def taux(k: int, n: int) -> str:
    if n == 0:
        return f"{k}/{n}"
    ic = wilson(k, n)
    assert ic is not None
    return f"{k}/{n} = {100 * k / n:.1f} % [IC95 {100 * ic[0]:.1f} ; {100 * ic[1]:.1f}]"


# ---------------------------------------------------------------------------
# 1. Recettes
# ---------------------------------------------------------------------------


def recettes(territoires) -> dict:
    lignes = []
    for cle, t in territoires.items():
        s = t.strategie
        lignes.append(
            {
                "cle": cle,
                "nom": t.nom,
                "type": t.type,
                "region": t.region,
                "statut": t.statut,
                "strategie": s.type,
                "guides": len(t.guides),
                "sitemaps": len(s.urls_sitemap),
                "max_candidats": s.max_candidats,
                "max_pages": s.max_pages if s.type == "decouverte" else None,
                "profondeur": s.profondeur if s.type == "decouverte" else None,
                "pagination": [s.de, s.a, s.pas] if s.type == "pagination" else None,
                "motif_fiche": bool(t.motif_fiche),
                "exclure": len(t.exclure),
                "entetes": t.entetes,
                "departements": t.departements,
            }
        )
    par_type = Counter(r["type"] for r in lignes)
    croise = Counter((r["strategie"], r["statut"]) for r in lignes)
    deps_fichier = {r["cle"] for r in lignes if r["type"] == "departement"}
    regions_fichier = {r["cle"] for r in lignes if r["type"] == "region"}
    return {
        "lignes": lignes,
        "n": len(lignes),
        "par_type": dict(par_type),
        "par_statut": dict(Counter(r["statut"] for r in lignes)),
        "par_strategie": dict(Counter(r["strategie"] for r in lignes)),
        "strategie_x_statut": {f"{a} / {b}": n for (a, b), n in sorted(croise.items())},
        "par_type_x_statut": {
            f"{a} / {b}": n
            for (a, b), n in sorted(Counter((r["type"], r["statut"]) for r in lignes).items())
        },
        "max_candidats_non_defaut": {
            r["cle"]: r["max_candidats"] for r in lignes if r["max_candidats"] != 800
        },
        "max_pages_non_defaut": {
            r["cle"]: r["max_pages"]
            for r in lignes
            if r["max_pages"] is not None and r["max_pages"] != 120
        },
        "sans_motif_fiche_hors_spe": sorted(
            r["cle"] for r in lignes if not r["motif_fiche"] and r["statut"] != "sans_point_entree"
        ),
        "entetes_navigateur": sorted(r["cle"] for r in lignes if r["entetes"] == "navigateur"),
        "departements_couverts_par_autre": {
            r["cle"]: r["departements"] for r in lignes if r["departements"]
        },
        "departements_absents_du_fichier": sorted(set(DEPARTEMENT_LABELS) - deps_fichier),
        "regions_absentes_du_fichier": sorted(set(REGION_LABELS) - regions_fichier),
        "departements_connus": len(DEPARTEMENT_LABELS),
        "regions_connues": len(REGION_LABELS),
    }


# ---------------------------------------------------------------------------
# 2. Fiches de prospection
# ---------------------------------------------------------------------------

_COLLECTE_RE = re.compile(
    r"^- (\d+) URL de fiche trouvées, (\d+) déjà au catalogue, (\d+) déjà en file "
    r"d'attente, (\d+) à trier \((\d+) page\(s\) visitée\(s\)\)",
    re.M,
)
_STRAT_RE = re.compile(r"^Stratégie : (\w+) \(recette `(\w+)`\)", re.M)
_COUT_RE = re.compile(
    r"coût du passage : (\d+) appel\(s\)\s+([\d  ]+) jetons entrée / ([\d  ]+) sortie\s+\$([\d.]+)"
)
_PREFIXES_RE = re.compile(r"^- découverte : préfixes retenus (.+?) — (.*)$", re.M)
_SECTIONS = {
    "retenues": "## Candidates retenues",
    "a_trancher": "## À trancher à la main",
    "ecartees_test": "## Écartées par le test du destinataire",
    "ecartees_tri": "## Écartées au tri",
    "ecartees_ancien": "## Écartées (et pourquoi)",
}


def _section(md: str, titre: str) -> str | None:
    i = md.find(titre)
    if i < 0:
        return None
    reste = md[i + len(titre) :]
    j = reste.find("\n## ")
    return reste if j < 0 else reste[:j]


def _compter_items(bloc: str | None) -> int | None:
    if bloc is None:
        return None
    lignes = bloc.splitlines()
    rangs = [li for li in lignes if re.match(r"^\| ?\d+ ?\|", li)]
    puces = [li for li in lignes if re.match(r"^- (\*\*|https?://|`|\[)", li)]
    return len(rangs) + len(puces)


def _entier(s: str) -> int:
    return int(re.sub(r"\D", "", s))


def cle_de_fiche(nom: str, territoires) -> tuple[str, str]:
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-prospection-(.+)\.md$", nom)
    assert m
    date, reste = m.group(1), m.group(2)
    if reste in territoires:
        return date, reste
    tete = reste.split("-", 1)[0]
    if tete in territoires:
        return date, tete
    return date, reste


def fiches(territoires) -> list[dict]:
    sortie = []
    for chemin in sorted(REVIEWS.glob("*-prospection-*.md")):
        md = chemin.read_text(encoding="utf-8")
        date, cle = cle_de_fiche(chemin.name, territoires)
        f: dict = {
            "fiche": chemin.name,
            "date": date,
            "cle": cle,
            "connue": cle in territoires,
            "rejouee": "rejoué depuis candidats.jsonl" in md,
        }
        m = _STRAT_RE.search(md)
        f["strategie"], f["recette"] = (m.group(1), m.group(2)) if m else (None, None)
        m = _COLLECTE_RE.search(md)
        if m:
            trouvees, cat, fil, a_trier, pages = map(int, m.groups())
            f["collecte"] = {
                "trouvees": trouvees,
                "deja_catalogue": cat,
                "deja_file": fil,
                "a_trier": a_trier,
                "pages_visitees": pages,
            }
        for k, titre in _SECTIONS.items():
            f[k] = _compter_items(_section(md, titre))
        f["non_lues"] = len(re.findall(r"^- non lue : ", md, re.M))
        m = re.search(r"^- (\d+) candidate\(s\) douteuse\(s\) au tri", md, re.M)
        f["douteuses_tri"] = int(m.group(1)) if m else None
        m = _COUT_RE.search(md)
        if m:
            f["cout"] = {
                "appels": int(m.group(1)),
                "jetons_entree": _entier(m.group(2)),
                "jetons_sortie": _entier(m.group(3)),
                "dollars": float(m.group(4)),
            }
        notes = _section(md, "## Notes techniques") or ""
        f["plafonnee"] = bool(re.search(r"arrêt propre : plafond de \d+ candidates", notes))
        f["plafond_pages"] = "arrêtée au plafond de" in notes
        f["pages_erreur"] = re.findall(r"^- page en erreur : (\S+) → (.*)$", notes, re.M)
        f["pages_spa"] = re.findall(r"^- page vide ou SPA[^:]*: (\S+)", notes, re.M)
        f["sitemap_ko"] = re.findall(r"^- sitemap (?:injoignable|illisible) : (.*)$", notes, re.M)
        f["sitemap_enum"] = [
            (u, int(n))
            for u, n in re.findall(r"^- sitemap (\S+) : (\d+) URL énumérées", notes, re.M)
        ]
        m = re.search(r"^- découverte : (\d+) URL à chemin répétitif", notes, re.M)
        f["boucles"] = int(m.group(1)) if m else 0
        m = re.search(r"^- découverte : (\d+) document", notes, re.M)
        f["documents_ecartes"] = int(m.group(1)) if m else 0
        m = _PREFIXES_RE.search(md)
        if m:
            brut = m.group(1)
            f["prefixes"] = re.findall(r"'([^']+)'", brut)
            f["prefixes_aucun"] = "(aucun)" in brut
            f["prefixes_justification"] = m.group(2)[:400]
        f["prefixes_inventes"] = re.findall(
            r"^- découverte : préfixes inventés ignorés — (.*)$", notes, re.M
        )
        f["decouverte_sans_reponse"] = bool(
            re.search(r"^- découverte : le modèle n'a pas répondu", notes, re.M)
        )
        sortie.append(f)
    return sortie


# ---------------------------------------------------------------------------
# 3. Couverture par territoire
# ---------------------------------------------------------------------------


def couverture(territoires, les_fiches, file, corpus, candidats_par_cle) -> dict:
    par_cle_fiches = defaultdict(list)
    for f in les_fiches:
        par_cle_fiches[f["cle"]].append(f)
    taches = defaultdict(Counter)
    for t in file.values():
        taches[t.territoire][t.statut] += 1
    lignes = []
    for cle, t in territoires.items():
        fs = sorted(par_cle_fiches.get(cle, []), key=lambda f: f["date"])
        derniere = fs[-1] if fs else None
        st = taches.get(cle, Counter())
        derniere_collecte = next((f["collecte"] for f in reversed(fs) if "collecte" in f), None)
        cand = candidats_par_cle.get(cle)
        if st.get("ingere"):
            verdict = "au moins une ingeree"
        elif st.get("a_valider") or st.get("valide"):
            verdict = "seulement a_valider ou valide"
        elif not fs and not st and cand is None:
            verdict = "jamais balaye"
        elif not fs and cand is not None and cand["n"] > 0:
            verdict = "collecte sans fiche (run interrompu ou etape 1)"
        elif (derniere_collecte is not None and derniere_collecte["trouvees"] == 0) or (
            not st and cand is not None and cand["n"] == 0
        ):
            verdict = "collecte nulle"
        elif st:
            verdict = "tout ecarte (ignore ou echec seulement)"
        else:
            verdict = "balaye, rien en file"
        lignes.append(
            {
                "cle": cle,
                "type": t.type,
                "statut": t.statut,
                "strategie": t.strategie.type,
                "fiches": [f["fiche"] for f in fs],
                "derniere_fiche": derniere["fiche"] if derniere else None,
                "derniere_collecte": derniere_collecte,
                "candidats_jsonl": cand,
                "file": dict(st),
                "catalogue_actif": len(aides_existantes(cle, t, corpus)),
                "verdict": verdict,
            }
        )
    return {
        "lignes": lignes,
        "verdicts": dict(Counter(li["verdict"] for li in lignes)),
        "verdict_x_type": {
            f"{a} / {b}": n
            for (a, b), n in sorted(Counter((li["verdict"], li["type"]) for li in lignes).items())
        },
        "verdict_x_statut": {
            f"{a} / {b}": n
            for (a, b), n in sorted(Counter((li["verdict"], li["statut"]) for li in lignes).items())
        },
        "verdict_x_strategie": {
            f"{a} / {b}": n
            for (a, b), n in sorted(
                Counter((li["verdict"], li["strategie"]) for li in lignes).items()
            )
        },
    }


# ---------------------------------------------------------------------------
# 4. Candidats hors git
# ---------------------------------------------------------------------------


def candidats() -> dict[str, dict]:
    """Le candidats.jsonl le plus recent (mtime) de chaque territoire, toutes sources."""
    meilleurs: dict[str, dict] = {}
    for racine in [*SOURCES_CANDIDATS, REPLI_CANDIDATS]:
        if not racine.exists():
            continue
        for chemin in racine.glob("*/candidats.jsonl"):
            cle = chemin.parent.name
            mtime = chemin.stat().st_mtime
            if racine == REPLI_CANDIDATS:
                if cle in meilleurs:
                    continue
                mtime = 0.0
            elif cle in meilleurs and meilleurs[cle]["_mtime"] >= mtime:
                continue
            lignes = [
                json.loads(li)
                for li in chemin.read_text(encoding="utf-8").splitlines()
                if li.strip()
            ]
            tri = chemin.parent / "tri.jsonl"
            decisions = Counter()
            if tri.exists():
                for li in tri.read_text(encoding="utf-8").splitlines():
                    if li.strip():
                        decisions[json.loads(li).get("decision")] += 1
            via = Counter(c.get("trouve_via") for c in lignes)
            meilleurs[cle] = {
                "_mtime": mtime,
                "source": str(chemin),
                "n": len(lignes),
                "trouve_via": dict(via),
                "titre_vide": sum(1 for c in lignes if not (c.get("titre") or "").strip()),
                "avec_documents": sum(1 for c in lignes if c.get("documents")),
                "en_boucle": sum(1 for c in lignes if chemin_en_boucle(c["url"])),
                "cles_fiche_distinctes": len({cle_fiche(c["url"]) for c in lignes}),
                "hotes": dict(Counter(c["url"].split("/")[2] for c in lignes).most_common(3)),
                "tri": dict(decisions),
            }
    return meilleurs


# ---------------------------------------------------------------------------
# 5. Moselle, d'apres les journaux de balayage
# ---------------------------------------------------------------------------


def moselle() -> dict:
    sortie = {}
    for chemin in sorted(LOGS_BALAYAGE.glob("*-prospection-57.log")):
        texte = chemin.read_text(encoding="utf-8")
        d: dict = {"journal": str(chemin.relative_to(BACKEND))}
        m = re.search(r"\[1/3\] (\d+) candidat\(s\) à trier", texte)
        d["candidats"] = int(m.group(1)) if m else None
        lots = re.findall(r"\[2/3\] lot (\d+)/(\d+)", texte)
        d["lots_tri_journalises"] = len(lots)
        d["lots_tri_prevus"] = int(lots[0][1]) if lots else None
        m = re.search(r"\[2/3\] (\d+) retenue\(s\), (\d+) douteuse\(s\), (\d+) écartée\(s\)", texte)
        if m:
            d["tri"] = dict(
                zip(("retenues", "douteuses", "ecartees"), map(int, m.groups()), strict=True)
            )
        m = re.search(r"\[3/3\] (\d+) page\(s\) à lire", texte)
        d["a_lire"] = int(m.group(1)) if m else None
        lues = re.findall(r"\[3/3\]\s+\d+/\d+ (ERREUR|retenue|écartée|à trancher)", texte)
        d["lues_journalisees"] = len(lues)
        d["lues_par_verdict"] = dict(Counter(lues))
        temps = re.findall(r"\((\d+) s\)", texte)
        d["derniere_seconde_lecture"] = int(temps[-1]) if temps else None
        d["urls_en_boucle_dans_le_journal"] = sum(
            1
            for u in re.findall(r"(https://www\.moselle\.fr/\S+?)…?\s", texte)
            if u.count("/jcms/") >= 2
        )
        d["fin_propre"] = "fiche :" in texte
        sortie[chemin.name] = d
    return sortie


# ---------------------------------------------------------------------------
# 6. Doublons
# ---------------------------------------------------------------------------


def _titre_norm(titre: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", (titre or "").lower()).split())


def doublons(file, corpus) -> dict:
    sortie: dict = {}
    # a) Ce que cle_fiche ajoute a cle_url, sur les URL de la file
    urls = [t.url for t in file.values() if t.url]
    sortie["file_urls"] = len(urls)
    sortie["cle_url_distinctes"] = len({cle_url(u) for u in urls})
    sortie["cle_fiche_distinctes"] = len({cle_fiche(u) for u in urls})
    sortie["urls_brutes_distinctes"] = len(set(urls))

    # b) Groupes de la file sur cle_fiche
    groupes = defaultdict(list)
    for slug, t in file.items():
        groupes[cle_fiche(t.url)].append(slug)
    multi = {k: v for k, v in groupes.items() if len(v) > 1}
    sortie["groupes_cle_fiche_multiples"] = len(multi)
    sortie["taches_dans_groupes_multiples"] = sum(len(v) for v in multi.values())
    sortie["groupes_statuts"] = dict(
        Counter(" + ".join(sorted(file[s].statut for s in v)) for v in multi.values()).most_common(
            15
        )
    )
    meme_fiche = sum(1 for v in multi.values() if len({file[s].fiche for s in v}) == 1)
    sortie["groupes_tous_de_la_meme_fiche"] = meme_fiche
    meme_territoire = sum(1 for v in multi.values() if len({file[s].territoire for s in v}) == 1)
    sortie["groupes_meme_territoire"] = meme_territoire

    # c) Groupes sur le titre normalise, meme territoire, cle_fiche differente
    par_titre = defaultdict(list)
    for slug, t in file.items():
        par_titre[(t.territoire, _titre_norm(t.titre))].append(slug)
    titre_multi = {
        k: v
        for k, v in par_titre.items()
        if len(v) > 1 and len({cle_fiche(file[s].url) for s in v}) > 1
    }
    sortie["groupes_meme_titre_url_differente"] = len(titre_multi)
    sortie["exemples_meme_titre_url_differente"] = [
        {s: (file[s].statut, file[s].url) for s in v} for v in list(titre_multi.values())[:8]
    ]
    sortie["groupes_meme_titre_statuts"] = dict(
        Counter(
            " + ".join(sorted(file[s].statut for s in v)) for v in titre_multi.values()
        ).most_common(10)
    )

    # Depuis le commit des garde-fous (84bdd821, 2026-09-22) : ce qui passe encore
    from datetime import date as _date

    garde = _date(2026, 9, 22)
    sortie["apres_2026_09_22_groupes_meme_url"] = sum(
        1 for v in multi.values() if max(file[s].ajoute_le or _date.min for s in v) > garde
    )
    recents = [
        v for v in titre_multi.values() if max(file[s].ajoute_le or _date.min for s in v) > garde
    ]
    sortie["apres_2026_09_22_groupes_meme_titre_url_differente"] = len(recents)
    sortie["apres_2026_09_22_meme_titre_meme_fiche"] = sum(
        1 for v in recents if len({file[s].fiche for s in v}) == 1
    )
    sortie["apres_2026_09_22_meme_titre_statuts"] = dict(
        Counter(" + ".join(sorted(file[s].statut for s in v)) for v in recents)
    )
    sortie["apres_2026_09_22_exemples"] = [
        {s: (file[s].statut, file[s].url) for s in v} for v in recents[:6]
    ]

    # d) Slugs suffixes -N dont la base existe (catalogue ou file)
    connus = set(file) | set(corpus)
    suffixes = []
    for slug, t in file.items():
        m = re.match(r"^(.*)-(\d{1,2})$", slug)
        if not m or m.group(1) not in connus:
            continue
        base = m.group(1)
        url_base = file[base].url if base in file else (corpus[base].source.url_officielle or "")
        suffixes.append(
            {
                "slug": slug,
                "base": base,
                "statut": t.statut,
                "meme_cle_fiche": cle_fiche(t.url) == cle_fiche(url_base) if url_base else None,
                "meme_titre": (
                    _titre_norm(t.titre) == _titre_norm(file[base].titre) if base in file else None
                ),
            }
        )
    sortie["slugs_suffixes"] = len(suffixes)
    sortie["slugs_suffixes_meme_cle_fiche"] = sum(1 for s in suffixes if s["meme_cle_fiche"])
    sortie["slugs_suffixes_meme_titre"] = sum(1 for s in suffixes if s["meme_titre"])
    sortie["slugs_suffixes_statuts"] = dict(Counter(s["statut"] for s in suffixes))

    # e) Les .yaml.echec doublons : par quel etage auraient-ils du etre arretes ?
    echecs = sorted(
        p.name[: -len(".yaml.echec")] for p in (BACKEND / "data" / "aides").glob("*.yaml.echec")
    )
    sortie["yaml_echec"] = len(echecs)
    lignes = []
    for slug in echecs:
        t = file.get(slug)
        if t is None:
            continue
        motif = t.motif_ignore or ""
        humain_doublon = "tri humain" in motif and "oublon" in motif
        if not (motif.startswith("doublon d'URL") or humain_doublon):
            continue
        survivant = t.doublon_de
        if survivant is None:
            m = re.search(r"doublon d'URL de (\S+)", motif)
            survivant = m.group(1) if m else None
        s = file.get(survivant) if survivant else None
        url_s = (
            s.url
            if s
            else (corpus[survivant].source.url_officielle if survivant in corpus else None)
        )
        ligne = {
            "slug": slug,
            "motif": motif[:160],
            "survivant": survivant,
            "survivant_statut": s.statut if s else ("catalogue" if survivant in corpus else None),
            "url": t.url,
            "url_survivant": url_s,
            "meme_url_brute": url_s == t.url if url_s else None,
            "meme_cle_url": cle_url(url_s) == cle_url(t.url) if url_s else None,
            "meme_cle_fiche": cle_fiche(url_s) == cle_fiche(t.url) if url_s else None,
            "ajoute_le": str(t.ajoute_le),
            "survivant_ajoute_le": str(s.ajoute_le) if s else None,
            "meme_fiche": (s.fiche == t.fiche) if s else None,
            "meme_territoire": (s.territoire == t.territoire) if s else None,
            "meme_titre": (_titre_norm(s.titre) == _titre_norm(t.titre)) if s else None,
            "humain": humain_doublon,
        }
        # Etage qui aurait du l'arreter, deduit des seules donnees
        if not ligne["meme_cle_fiche"]:
            etage = (
                "aucun etage d'URL : URL differentes, seul un rapprochement par contenu ou titre"
            )
        elif ligne["meme_fiche"]:
            etage = "collecte, dedoublonnage interne au balayage (cle_fiche)"
        elif s and s.ajoute_le and t.ajoute_le and s.ajoute_le != t.ajoute_le:
            # Le plus recent des deux aurait du etre arrete a la collecte : l'autre
            # etait deja dans la file, quel que soit celui qui a survecu ensuite.
            etage = "collecte, dedoublonner contre la file (l'autre deja present)"
        elif s and s.ajoute_le == t.ajoute_le:
            etage = "meme jour, fiches differentes : dedoublonnage de la file avant promotion"
        else:
            etage = "indetermine"
        ligne["etage"] = etage
        lignes.append(ligne)
    sortie["yaml_echec_doublons"] = lignes
    sortie["yaml_echec_doublons_url"] = sum(1 for li in lignes if not li["humain"])
    sortie["yaml_echec_doublons_humains"] = sum(1 for li in lignes if li["humain"])
    sortie["yaml_echec_doublons_par_etage"] = dict(
        Counter(li["etage"] for li in lignes if not li["humain"])
    )
    sortie["yaml_echec_doublons_url_par_date"] = dict(
        Counter(li["ajoute_le"] for li in lignes if not li["humain"])
    )
    sortie["yaml_echec_doublons_url_egalites"] = {
        "meme_url_brute": sum(1 for li in lignes if not li["humain"] and li["meme_url_brute"]),
        "meme_cle_url": sum(1 for li in lignes if not li["humain"] and li["meme_cle_url"]),
        "meme_cle_fiche": sum(1 for li in lignes if not li["humain"] and li["meme_cle_fiche"]),
        "meme_fiche": sum(1 for li in lignes if not li["humain"] and li["meme_fiche"]),
        "meme_territoire": sum(1 for li in lignes if not li["humain"] and li["meme_territoire"]),
        "survivant_statut": dict(
            Counter(li["survivant_statut"] for li in lignes if not li["humain"])
        ),
    }
    return sortie


# ---------------------------------------------------------------------------
# Vagues
# ---------------------------------------------------------------------------


def vagues(les_fiches) -> dict:
    par_date = defaultdict(list)
    for f in les_fiches:
        par_date[f["date"]].append(f)
    sortie = {}
    for date, fs in sorted(par_date.items()):
        avec = [f for f in fs if "collecte" in f]
        somme = Counter()
        for f in avec:
            somme.update(f["collecte"])
        sortie[date] = {
            "fiches": len(fs),
            "fiches_avec_ligne_collecte": len(avec),
            "rejouees": sum(1 for f in fs if f["rejouee"]),
            "collecte": dict(somme),
            "collecte_nulle": sorted(f["cle"] for f in avec if f["collecte"]["trouvees"] == 0),
            "a_trier_zero": sorted(f["cle"] for f in avec if f["collecte"]["a_trier"] == 0),
            "plafonnees": sorted(f["cle"] for f in fs if f["plafonnee"]),
            "plafond_pages": sorted(f["cle"] for f in fs if f["plafond_pages"]),
            "ecartees_tri": sum(f["ecartees_tri"] or 0 for f in fs),
            "retenues": sum(f["retenues"] or 0 for f in fs),
            "a_trancher": sum(f["a_trancher"] or 0 for f in fs),
            "ecartees_test": sum(f["ecartees_test"] or 0 for f in fs),
            "non_lues": sum(f["non_lues"] for f in fs),
            "dollars": round(sum(f.get("cout", {}).get("dollars", 0) for f in fs), 4),
            "par_strategie": dict(Counter(f["strategie"] for f in fs)),
        }
        par_strat = {}
        for strat in sorted({f["strategie"] for f in avec if f["strategie"]}):
            g = [f for f in avec if f["strategie"] == strat]
            par_strat[strat] = {
                "fiches": len(g),
                "trouvees": sum(f["collecte"]["trouvees"] for f in g),
                "a_trier": sum(f["collecte"]["a_trier"] for f in g),
                "pages": sum(f["collecte"]["pages_visitees"] for f in g),
                "ecartees_tri": sum(f["ecartees_tri"] or 0 for f in g),
                "retenues": sum(f["retenues"] or 0 for f in g),
                "a_trancher": sum(f["a_trancher"] or 0 for f in g),
                "ecartees_test": sum(f["ecartees_test"] or 0 for f in g),
                "fiches_zero_retenue": sum(1 for f in g if not f["retenues"]),
            }
        sortie[date]["rendement_par_strategie"] = par_strat
    return sortie


def decouverte(les_fiches, couv) -> dict:
    verdict = {li["cle"]: li for li in couv["lignes"]}
    lignes = []
    for f in les_fiches:
        if f["strategie"] != "decouverte":
            continue
        lignes.append(
            {
                "fiche": f["fiche"],
                "cle": f["cle"],
                "prefixes": f.get("prefixes"),
                "aucun": f.get("prefixes_aucun"),
                "inventes": f["prefixes_inventes"],
                "sans_reponse": f["decouverte_sans_reponse"],
                "justification": f.get("prefixes_justification"),
                "collecte": f.get("collecte"),
                "boucles": f["boucles"],
                "documents_ecartes": f["documents_ecartes"],
                "plafond_pages": f["plafond_pages"],
                "plafonnee": f["plafonnee"],
                "retenues": f["retenues"],
                "a_trancher": f["a_trancher"],
                "ecartees_test": f["ecartees_test"],
                "ecartees_tri": f["ecartees_tri"],
                "verdict_territoire": verdict.get(f["cle"], {}).get("verdict"),
                "file_territoire": verdict.get(f["cle"], {}).get("file"),
                "cout": f.get("cout"),
            }
        )
    return {"lignes": lignes}


_SOCIAL = re.compile(
    r"social|handicap|enfance|famille|insertion|rsa|jeunesse|college|education|sante|"
    r"personnes|grand-age|autonomie|emploi|sport",
    re.I,
)
_AIDES = re.compile(r"aide|subvention|appel|projet|dispositif|financ|guide|soutien", re.I)


def complements(cands, les_fiches, file, territoires=None, corpus=None) -> dict:
    """Mesures annexes : garde-fou de boucle sur la Moselle, pagination encodee, prefixes."""
    sortie: dict = {}
    # a) La Moselle contre le garde-fou actuel et des variantes
    m57 = DEPOT / "backend" / "data" / "prospection" / "57" / "candidats.jsonl"
    if m57.exists():
        urls = [json.loads(li)["url"] for li in m57.read_text(encoding="utf-8").splitlines() if li]
        from urllib.parse import urlsplit

        def profil(u: str) -> tuple[int, int]:
            seg = [x for x in urlsplit(u).path.split("/") if x]
            return len(seg), max(Counter(seg).values()) if seg else 0

        profils = [profil(u) for u in urls]
        sortie["moselle_candidats"] = len(urls)
        sortie["moselle_segments"] = dict(sorted(Counter(p[0] for p in profils).items()))
        sortie["moselle_repetition_max"] = dict(sorted(Counter(p[1] for p in profils).items()))
        sortie["moselle_pris_par_chemin_en_boucle"] = sum(1 for u in urls if chemin_en_boucle(u))
        sortie["moselle_pris_si_repetition_seule"] = sum(1 for p in profils if p[1] > 2)
        sortie["moselle_pris_si_seuil_8_segments"] = sum(
            1 for u in urls if chemin_en_boucle(u, max_segments=8)
        )
        sortie["moselle_motif_note_yaml"] = sum(
            1
            for u in urls
            if re.search(r"^https://www\.moselle\.fr/jcms/[a-z]+_[0-9]+/fr/[^/]+$", u)
        )
    # Sur tous les candidats hors Moselle : faux positifs d'une regle « repetition seule »
    autres = 0
    pris = 0
    for cle, v in cands.items():
        if cle == "57":
            continue
        chemin = Path(v["source"])
        for li in chemin.read_text(encoding="utf-8").splitlines():
            if not li.strip():
                continue
            u = json.loads(li)["url"]
            autres += 1
            seg = [x for x in u.split("?")[0].split("/")[3:] if x]
            if seg and max(Counter(seg).values()) > 2:
                pris += 1
    sortie["hors_moselle_candidats"] = autres
    sortie["hors_moselle_pris_si_repetition_seule"] = pris

    # b) Pagination Typo3 encodee (%5B ... %5D) : cle_fiche la voit-elle ?
    enc = [
        t.url for t in file.values() if re.search(r"%5B(currentpage|pointer|page)%5D", t.url, re.I)
    ]
    sortie["file_urls_pagination_encodee"] = len(enc)
    groupes = defaultdict(set)
    for u in enc:
        groupes[
            cle_fiche(
                u.replace("%5B", "[").replace("%5D", "]").replace("%5b", "[").replace("%5d", "]")
            )
        ].add(cle_fiche(u))
    sortie["pagination_encodee_cles_actuelles"] = sum(len(v) for v in groupes.values())
    sortie["pagination_encodee_cles_si_decodee"] = len(groupes)
    cand_enc = 0
    for v in cands.values():
        for li in Path(v["source"]).read_text(encoding="utf-8").splitlines():
            if li.strip() and re.search(r"%5B(currentpage|pointer|page)%5D", li, re.I):
                cand_enc += 1
    sortie["candidats_pagination_encodee"] = cand_enc

    # c) Prefixes de la decouverte (etiquettes : regle de mots-cles ecrite pour cette mesure)
    lignes = []
    for f in les_fiches:
        if f.get("prefixes") is None and not f.get("prefixes_aucun"):
            continue
        prefs = f.get("prefixes") or []
        chemins = [p.split("/", 3)[3] if p.count("/") >= 3 else "" for p in prefs]
        lignes.append(
            {
                "fiche": f["fiche"],
                "n": len(prefs),
                "racine": sum(1 for c in chemins if c in ("", "/")),
                "sociaux": sum(1 for c in chemins if _SOCIAL.search(c) and not _AIDES.search(c)),
                "aides": sum(1 for c in chemins if _AIDES.search(c)),
                "retenues": f["retenues"],
                "trouvees": (f.get("collecte") or {}).get("trouvees"),
                "pages": (f.get("collecte") or {}).get("pages_visitees"),
                "plafond_pages": f["plafond_pages"],
            }
        )
    sortie["prefixes"] = lignes

    # c bis) Rappel des prefixes contre ce qu'on connait deja du territoire : URL
    # (catalogue actif + taches ingere, a_valider ou valide de la file) sur le meme
    # hote que le guide. Reference biaisee : elle sort du pipeline mesure.
    rappel = []
    if territoires is not None and corpus is not None:
        from urllib.parse import urlsplit

        derniere: dict[str, dict] = {}
        for f in les_fiches:
            if f.get("prefixes"):
                derniere[f["cle"]] = f
        for cle, f in sorted(derniere.items()):
            t = territoires.get(cle)
            if t is None:
                continue
            hotes = {urlsplit(p).netloc.removeprefix("www.") for p in f["prefixes"]}
            connues = set()
            for a in aides_existantes(cle, t, corpus).values():
                if a.source.url_officielle:
                    connues.add(a.source.url_officielle)
            for tache in file.values():
                if tache.territoire == cle and tache.statut in ("ingere", "a_valider", "valide"):
                    connues.add(tache.url)
            meme_hote = [u for u in connues if urlsplit(u).netloc.removeprefix("www.") in hotes]
            dedans = [u for u in meme_hote if any(u.startswith(p) for p in f["prefixes"])]
            rappel.append(
                {
                    "cle": cle,
                    "fiche": f["fiche"],
                    "connues_meme_hote": len(meme_hote),
                    "sous_un_prefixe": len(dedans),
                    "hors_prefixes": sorted(set(meme_hote) - set(dedans))[:10],
                }
            )
    sortie["rappel_prefixes"] = rappel
    sortie["rappel_prefixes_total"] = {
        "territoires": len(rappel),
        "avec_connues": sum(1 for r in rappel if r["connues_meme_hote"]),
        "connues_meme_hote": sum(r["connues_meme_hote"] for r in rappel),
        "sous_un_prefixe": sum(r["sous_un_prefixe"] for r in rappel),
    }
    n = len(lignes)
    sortie["prefixes_resume"] = {
        "fiches": n,
        "aucun_prefixe": sum(1 for li in lignes if li["n"] == 0),
        "un_prefixe_racine": sum(1 for li in lignes if li["racine"]),
        "tous_sociaux": sum(1 for li in lignes if li["n"] and li["sociaux"] == li["n"]),
        "au_moins_un_mot_aide": sum(1 for li in lignes if li["aides"]),
        "aucun_mot_aide": sum(1 for li in lignes if li["n"] and not li["aides"]),
        "retenues_si_mot_aide": [li["retenues"] for li in lignes if li["aides"]],
        "retenues_si_aucun_mot_aide": [
            li["retenues"] for li in lignes if li["n"] and not li["aides"]
        ],
        "plafond_pages": sum(1 for li in lignes if li["plafond_pages"]),
    }
    # d) Longueur des URL vues en decouverte (base de l'estimation du prompt)
    longueurs = []
    for v in cands.values():
        if "decouverte" not in v["trouve_via"] or v["n"] > 1000:
            continue
        for li in Path(v["source"]).read_text(encoding="utf-8").splitlines():
            if li.strip():
                longueurs.append(len(json.loads(li)["url"]))
    longueurs.sort()
    if longueurs:
        sortie["decouverte_longueur_url"] = {
            "n": len(longueurs),
            "mediane": longueurs[len(longueurs) // 2],
            "moyenne": round(sum(longueurs) / len(longueurs), 1),
            "p90": longueurs[int(0.9 * len(longueurs))],
        }
    return sortie


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    territoires = charger_territoires()
    corpus = load_all_aides()
    file = charger(FILE_ATTENTE)

    rec = recettes(territoires)
    les_fiches = fiches(territoires)
    cands = candidats()
    couv = couverture(territoires, les_fiches, file, corpus, cands)
    vag = vagues(les_fiches)
    dec = decouverte(les_fiches, couv)
    mos = moselle()
    dbl = doublons(file, corpus)
    comp = complements(cands, les_fiches, file, territoires, corpus)

    def ecrire(nom: str, donnees) -> None:
        (SORTIE / nom).write_text(
            json.dumps(donnees, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )

    ecrire("recettes.json", rec)
    ecrire("fiches.json", les_fiches)
    ecrire("couverture.json", couv)
    ecrire("vagues.json", vag)
    ecrire("decouverte.json", dec)
    ecrire(
        "candidats.json",
        {k: {kk: vv for kk, vv in v.items() if kk != "_mtime"} for k, v in cands.items()},
    )
    ecrire("moselle.json", mos)
    ecrire("doublons.json", dbl)
    ecrire("complements.json", comp)

    r: list[str] = []
    r.append(f"Corpus actif : {len(corpus)} aides ; file : {len(file)} taches")
    r.append(f"Recettes : {rec['n']} ; par type {rec['par_type']}")
    r.append(f"  par statut {rec['par_statut']}")
    r.append(f"  par strategie {rec['par_strategie']}")
    r.append(f"  strategie x statut {rec['strategie_x_statut']}")
    r.append(f"  type x statut {rec['par_type_x_statut']}")
    r.append(f"  max_candidats non defaut {rec['max_candidats_non_defaut']}")
    r.append(f"  max_pages non defaut {rec['max_pages_non_defaut']}")
    r.append(f"  sans motif_fiche (hors sans_point_entree) {len(rec['sans_motif_fiche_hors_spe'])}")
    r.append(f"  entetes navigateur {rec['entetes_navigateur']}")
    r.append(f"  departements absents du fichier {rec['departements_absents_du_fichier']}")
    r.append(f"  regions absentes du fichier {rec['regions_absentes_du_fichier']}")
    r.append("")
    r.append(
        f"Fiches de prospection : {len(les_fiches)} ; avec ligne de collecte : "
        f"{sum(1 for f in les_fiches if 'collecte' in f)} ; rejouees : "
        f"{sum(1 for f in les_fiches if f['rejouee'])}"
    )
    r.append("Vagues :")
    for d, v in vag.items():
        r.append(f"  {d} {json.dumps(v, ensure_ascii=False)}")
    r.append("")
    r.append(f"Couverture : {couv['verdicts']}")
    r.append(f"  verdict x type {couv['verdict_x_type']}")
    r.append(f"  verdict x strategie {couv['verdict_x_strategie']}")
    r.append(f"  verdict x statut {couv['verdict_x_statut']}")
    for verdict in sorted(set(couv["verdicts"])):
        cles = [li["cle"] for li in couv["lignes"] if li["verdict"] == verdict]
        r.append(f"  {verdict} ({len(cles)}) : {', '.join(cles)}")
    r.append("")
    n_dec = len(dec["lignes"])
    r.append(f"Decouverte : {n_dec} fiches en strategie decouverte")
    avec_pref = [li for li in dec["lignes"] if li["prefixes"] is not None or li["aucun"]]
    r.append(
        f"  avec ligne de prefixes : {len(avec_pref)} ; aucun prefixe : "
        f"{sum(1 for li in avec_pref if li['aucun'] or not li['prefixes'])} ; "
        f"prefixes inventes : {sum(1 for li in dec['lignes'] if li['inventes'])} ; "
        f"sans reponse : {sum(1 for li in dec['lignes'] if li['sans_reponse'])}"
    )
    zero = [li for li in dec["lignes"] if li["retenues"] == 0]
    r.append(f"  fiches decouverte avec 0 retenue : {taux(len(zero), n_dec)}")
    nd = [f for f in les_fiches if f["strategie"] and f["strategie"] != "decouverte"]
    zero_nd = [f for f in nd if f["retenues"] == 0]
    r.append(f"  fiches hors decouverte avec 0 retenue : {taux(len(zero_nd), len(nd))}")
    r.append("")
    r.append(f"Candidats hors git : {len(cands)} territoires")
    for k, v in sorted(cands.items()):
        r.append(
            f"  {k}: n={v['n']} via={v['trouve_via']} titre_vide={v['titre_vide']} "
            f"boucle={v['en_boucle']} tri={v['tri']}"
        )
    r.append("")
    r.append(f"Moselle : {json.dumps(mos, ensure_ascii=False)}")
    r.append("")
    r.append("Doublons :")
    for k, v in dbl.items():
        if k in ("yaml_echec_doublons", "exemples_meme_titre_url_differente"):
            continue
        r.append(f"  {k} : {v}")
    r.append("")
    r.append("Complements :")
    for k, v in comp.items():
        if k not in ("prefixes", "rappel_prefixes"):
            r.append(f"  {k} : {v}")
    (SORTIE / "resume.txt").write_text("\n".join(r) + "\n", encoding="utf-8")
    print("\n".join(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
