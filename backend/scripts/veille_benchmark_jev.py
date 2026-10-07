"""Banc d'essai de Jev dans la veille, AVANT tout branchement.

Deux questions, deux jeux (plan : `data/reviews/2026-10-04-plan-jev-veille.md`) :

    jeu A  « ce diff touche-t-il le mandat ? » — fixe le seuil du FILTRE (sans
           le résumé du LLM) et celui de la GARDE (avec le résumé, sur les
           seuls « inchangé » du LLM) ;
    jeu B  « refonte réelle ou refonte de site ? » — fixe le seuil du tri des
           REFONTES, sur les escalades de la règle 6.

**L'étiquette est HUMAINE, jamais le verdict du LLM** : c'est précisément lui
qu'on soupçonne (deux faux « inchangé » le 2026-10-04). Le script produit une
fiche d'étiquetage, `data/reviews/<jour>-etiquettes-veille-jev.md`, un bloc par
cas avec deux cases à cocher. Sont cochés d'office : les retouches appliquées
ce jour-là (relues avant commit), les deux faux « inchangé » constatés au plan,
et les cas de `data/veille-golds.yaml` (construits à la main).

D'où viennent les cas :

- jeu A, **snapshots** : les aides dont une page a été ré-archivée le `<jour>`.
  Le diff se reconstruit sans réseau, snapshot précédent contre snapshot du
  jour, par la même analyse que la veille (chrome compris, calculé sur ces
  seules pages). Verdict et résumé du LLM viennent du rapport du jour ;
- jeu A, **en direct** (`--collecte`) : les aides encore `MAJ_LLM` aujourd'hui,
  dont les escalades de l'étage C, que rien n'a ré-archivées ;
- jeu A, **golds** : les cas fabriqués de `data/veille-golds.yaml` ;
- jeu B (`--collecte`) : les escalades de la règle 6, page fraîche comprise.

    uv run python scripts/veille_benchmark_jev.py preparer --collecte   # 4 min, zéro modèle
    # cocher les cases de la fiche d'étiquetage
    uv run python scripts/veille_benchmark_jev.py juger                 # quelques centimes
    uv run python scripts/veille_benchmark_jev.py                       # rapport seul

Chaque réponse de Jev est mise en cache (`data/reviews/logs/veille-jev/`, hors
git) : relancer ne repaie rien. Ne modifie aucune aide, aucun snapshot, aucun
manifeste : les seuls fichiers versionnés écrits sont la fiche d'étiquetage et
le rapport `data/reviews/<date>-benchmark-veille-jev.md`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.decision import ClientDecision, ErreurDecision
from snapshot_source import SOURCES_DIR
from veille_analyze import RATIO_DIFF_ESCALADE, analyze_all, resume_diff
from veille_arbitre import (
    QUESTIONS_MANDAT,
    QUESTIONS_REFONTE,
    empreinte_etat,
    etat_mandat,
    etat_refonte,
    fiche_pour_jev,
)
from veille_benchmark import charger_golds, contenu_frais
from veille_collect import (
    AideCollect,
    FetchResult,
    MonitoredUrl,
    est_http,
    pdf_to_text,
    url_d_origine,
)
from veille_text import normalized_diff, parse_front_matter
from veille_update import MAX_LIGNES_DIFF

from aides_schema import AIDES_DIR, DATA_DIR, Aide, charger_yaml, load_aide

REVIEWS_DIR = DATA_DIR / "reviews"
CACHE_DIR = REVIEWS_DIR / "logs" / "veille-jev"

# Les deux faux « inchangé » du passage du 2026-10-04, constatés au plan et
# corrigés à la main (étape 0) : le résumé du LLM décrivait lui-même le report.
TOUCHE_CONSTATEES = {
    "88-musee-centre-interpretation",
    "01-pactes-de-territoire-patrimoine-historique-bati",
}

# Lignes de diff montrées dans la fiche d'étiquetage : de quoi trancher, pas
# de quoi relire une page entière (le diff complet reste dans le cache).
LIGNES_FICHE = 40

ETIQUETTES = {
    "A": ("touche", "ne touche pas"),
    "B": ("règlement changé", "même règlement"),
}


@dataclass
class Cas:
    id: str  # « A · slug », « A · slug (en direct) », « A · gold:x », « B · slug »
    jeu: str  # "A" ou "B"
    slug: str
    origine: str  # snapshots, direct, gold
    diff: str = ""
    pages: list[tuple[str, str]] = field(default_factory=list)
    verdict_llm: str = ""  # applique, inchange, escalade… ; vide si non soumis
    resume_llm: str = ""
    raisons: list[str] = field(default_factory=list)
    etiquette_auto: str = ""  # case cochée d'office, et pourquoi
    motif_auto: str = ""
    # La fiche telle que la veille l'avait sous les yeux (`fiche_pour_jev`).
    # Pour un cas du passage étudié, c'est celle d'AVANT la retouche ou la
    # correction à la main : juger contre la fiche corrigée demanderait à Jev
    # si la fiche « dit déjà » ce qu'elle dit depuis.
    fiche: dict[str, Any] = field(default_factory=dict)
    # Le YAML complet de cette même fiche : de quoi REJOUER l'étage C dessus
    # (`veille_benchmark_etage_c.py`), même après le commit des retouches.
    yaml_avant: str = ""


# ---------------------------------------------------------------------------
# Préparation des cas
# ---------------------------------------------------------------------------


def _url_et_corps(path: Path) -> tuple[str | None, str | None, bytes | None]:
    """(URL d'origine, texte comparable, octets d'un PDF) d'un snapshot."""
    if path.suffix.lower() == ".md":
        meta, corps = parse_front_matter(path.read_text(encoding="utf-8"))
        url = meta.get("url")
        if not est_http(url):
            return None, None, None
        return url_d_origine(url)[0], corps, None
    if path.name.endswith(".pdf.meta.yaml"):
        meta = charger_yaml(path.read_text(encoding="utf-8")) or {}
        url = meta.get("url")
        pdf = path.with_name(path.name.removesuffix(".meta.yaml"))
        if not est_http(url) or not pdf.is_file():
            return None, None, None
        return url_d_origine(url)[0], pdf_to_text(pdf), pdf.read_bytes()
    return None, None, None


def collect_depuis_snapshots(slug: str, jour: str, *, complet: bool = False) -> AideCollect | None:
    """La collecte du `jour` reconstituée : précédent snapshot → snapshot du jour.

    Les snapshots postérieurs au `jour` (une ré-ingestion depuis) sont ignorés.
    `complet` : ajoute aussi les pages qui n'ont PAS bougé ce jour-là, comme
    documents frais identiques à leur baseline. C'est ce que la production
    envoie au modèle (`AideCollect.fresh_docs()` : toutes les URL surveillées) ;
    sans `complet`, le modèle ne lit que les pages modifiées.
    """
    dossier = SOURCES_DIR / slug
    par_url: dict[str, list[tuple[str, str | None, bytes | None]]] = {}
    for path in sorted(dossier.iterdir()):
        if path.name[:10] > jour:
            continue
        url, corps, octets = _url_et_corps(path)
        if url and corps:
            par_url.setdefault(url, []).append((path.name, corps, octets))
    urls, fetched, change = [], {}, False
    for url, versions in par_url.items():
        if len(versions) >= 2 and versions[-1][0].startswith(jour):
            (_, avant, _), (_, apres, octets) = versions[-2], versions[-1]
            change = True
        elif complet:
            (_, avant, octets) = versions[-1]
            apres = avant
        else:
            continue
        murl = MonitoredUrl(url=url, role="snapshot", baseline_body=avant)
        if octets is not None:
            res = FetchResult(url=url, status=200, is_binary=True, content=octets, texte_pdf=apres)
        else:
            res = FetchResult(url=url, status=200, raw_text=apres, body_md=apres)
        urls.append(murl)
        fetched[url] = res
    return AideCollect(slug=slug, urls=urls, fetched=fetched) if change else None


def verdicts_du_rapport(jour: str) -> dict[str, tuple[str, str]]:
    """{slug: (état, résumé)} lus dans le rapport de veille du jour."""
    chemin = REVIEWS_DIR / f"{jour}-veille.md"
    if not chemin.exists():
        return {}
    verdicts: dict[str, tuple[str, str]] = {}
    slug = None
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("### "):
            slug = ligne[4:].strip()
        elif slug and (m := re.match(r"- \*\*étage C \([^)]*\)\*\* — (\w+) : (.*)", ligne)):
            verdicts[slug] = (m.group(1), m.group(2).strip())
    return verdicts


def yaml_a_la_revision(slug: str, rev: str) -> str:
    """Le YAML de la fiche à la révision `rev` (vide : celui du working tree)."""
    if not rev:
        return (AIDES_DIR / f"{slug}.yaml").read_text(encoding="utf-8")
    return subprocess.run(
        ["git", "show", f"{rev}:backend/data/aides/{slug}.yaml"],
        cwd=DATA_DIR.parent,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def cas_snapshots(jour: str, rev: str) -> list[Cas]:
    slugs = sorted(
        d.name
        for d in SOURCES_DIR.iterdir()
        if d.is_dir() and any(p.name.startswith(jour) for p in d.iterdir())
    )
    aides, collects = {}, {}
    for slug in slugs:
        chemin = AIDES_DIR / f"{slug}.yaml"
        if not chemin.exists():
            continue
        if col := collect_depuis_snapshots(slug, jour):
            aides[slug], collects[slug] = load_aide(chemin), col
    verdicts = verdicts_du_rapport(jour)
    cas = []
    for slug, an in analyze_all(aides, collects).items():
        diff = resume_diff(an, max_lignes=MAX_LIGNES_DIFF)
        if not diff:
            continue
        etat, resume = verdicts.get(slug, ("", ""))
        c = Cas(
            id=f"A · {slug}",
            jeu="A",
            slug=slug,
            origine="snapshots",
            diff=diff,
            verdict_llm=etat,
            resume_llm=resume,
            yaml_avant=(texte := yaml_a_la_revision(slug, rev)),
            fiche=fiche_pour_jev(Aide.model_validate(charger_yaml(texte))),
        )
        if slug in TOUCHE_CONSTATEES:
            c.etiquette_auto, c.motif_auto = "touche", "faux « inchangé » constaté au plan"
        elif etat == "applique":
            c.etiquette_auto, c.motif_auto = "touche", "retouche appliquée et relue"
        cas.append(c)
    return cas


def cas_golds() -> list[Cas]:
    cas = []
    for g in charger_golds():
        # Un gold dont l'aide a été écartée ou fusionnée depuis n'a plus de
        # fiche à juger contre.
        if not (AIDES_DIR / f"{g.slug}.yaml").exists():
            continue
        baseline, frais = contenu_frais(g)
        diff = normalized_diff(baseline, frais).text
        cas.append(
            Cas(
                id=f"A · gold:{g.id}",
                jeu="A",
                slug=g.slug,
                origine="gold",
                diff=f"{g.snapshot}\n{diff}" if diff else "",
                etiquette_auto="ne touche pas" if g.negatif else "touche",
                motif_auto=f"gold {g.type}",
                fiche=fiche_pour_jev(load_aide(AIDES_DIR / f"{g.slug}.yaml")),
            )
        )
    return [c for c in cas if c.diff]


def cas_en_direct(deja: set[str]) -> list[Cas]:
    """Étages A et B en direct sur tout le parc : zéro modèle, rien d'écrit."""
    from veille_collect import collect

    aides = {p.stem: load_aide(p) for p in sorted(AIDES_DIR.glob("*.yaml"))}
    collects = collect(list(aides.values()))
    cas = []
    for slug, an in analyze_all(aides, collects).items():
        if an.statut == "ESCALADE_INGESTION" and an.refonte:
            pages = [
                (u.murl.url, u.result.texte)
                for u in an.urls
                if u.diff and u.diff.ratio > RATIO_DIFF_ESCALADE and u.result and u.result.texte
            ]
            cas.append(
                Cas(
                    id=f"B · {slug}",
                    jeu="B",
                    slug=slug,
                    origine="direct",
                    diff=resume_diff(an, max_lignes=MAX_LIGNES_DIFF),
                    pages=pages,
                    raisons=an.raisons,
                    fiche=fiche_pour_jev(aides[slug]),
                )
            )
        elif an.statut == "MAJ_LLM" and (diff := resume_diff(an, max_lignes=MAX_LIGNES_DIFF)):
            cid = f"A · {slug}" + (" (en direct)" if f"A · {slug}" in deja else "")
            cas.append(
                Cas(
                    id=cid,
                    jeu="A",
                    slug=slug,
                    origine="direct",
                    diff=diff,
                    raisons=an.raisons,
                    fiche=fiche_pour_jev(aides[slug]),
                )
            )
    return cas


def chemin_cas(jour: str) -> Path:
    return CACHE_DIR / f"cas-{jour}.json"


def ecrire_cas(cas: list[Cas], jour: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    chemin_cas(jour).write_text(
        json.dumps([asdict(c) for c in cas], ensure_ascii=False, indent=1), encoding="utf-8"
    )


def lire_cas(jour: str) -> list[Cas]:
    chemin = chemin_cas(jour)
    if not chemin.exists():
        raise SystemExit(f"aucun cas préparé pour le {jour} : lancer `preparer` d'abord")
    return [
        Cas(**{**c, "pages": [tuple(p) for p in c["pages"]]})
        for c in json.loads(chemin.read_text(encoding="utf-8"))
    ]


# ---------------------------------------------------------------------------
# Fiche d'étiquetage
# ---------------------------------------------------------------------------


def chemin_fiche(jour: str) -> Path:
    return REVIEWS_DIR / f"{jour}-etiquettes-veille-jev.md"


def lire_etiquettes(jour: str) -> dict[str, str]:
    """{id de cas: étiquette cochée}. Un bloc sans case cochée n'a pas d'étiquette."""
    chemin = chemin_fiche(jour)
    if not chemin.exists():
        return {}
    etiquettes: dict[str, str] = {}
    courant = None
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("### "):
            courant = ligne[4:].strip()
        elif courant and (m := re.match(r"- \[[xX]\] (.+?)\s*$", ligne)):
            etiquettes[courant] = m.group(1)
    return etiquettes


def ecrire_fiche(cas: list[Cas], jour: str) -> Path:
    """La fiche, régénérée sans perdre une case déjà cochée à la main."""
    deja = lire_etiquettes(jour)
    out = [
        f"# Étiquettes du banc d'essai Jev de la veille ({jour})",
        "",
        "Cocher UNE case par bloc (`[x]`). Jeu A : le changement touche-t-il une échéance, "
        "un montant, un taux, un plafond de cumul ou une condition d'éligibilité de la fiche, "
        "que la fiche ne dit pas encore ? Jeu B : la page réécrite porte-t-elle un autre "
        "règlement que la fiche ? Les cases cochées d'office disent pourquoi ; les décocher "
        "si elles sont fausses.",
        "",
        "Relancer `preparer` conserve les cases cochées ; `uv run python "
        "scripts/veille_benchmark_jev.py` régénère le rapport.",
        "",
    ]
    for jeu, titre in (("A", "Jeu A : le diff touche-t-il le mandat ?"), ("B", "Jeu B : refontes")):
        bloc = [c for c in cas if c.jeu == jeu]
        if not bloc:
            continue
        out += [f"## {titre}", ""]
        for c in sorted(bloc, key=lambda c: (c.etiquette_auto != "", c.origine, c.id)):
            choisie = deja.get(c.id, c.etiquette_auto)
            out.append(f"### {c.id}")
            out.append("")
            infos = [f"origine : {c.origine}"]
            if c.verdict_llm:
                infos.append(f"verdict du LLM : `{c.verdict_llm}`")
            if c.motif_auto:
                infos.append(f"coché d'office : {c.motif_auto}")
            out.append("- " + " · ".join(infos))
            if c.resume_llm:
                out.append(f"- résumé du LLM : {c.resume_llm}")
            out += [f"- {r}" for r in c.raisons[:3]]
            lignes = c.diff.splitlines()
            out += ["", "```diff", *lignes[:LIGNES_FICHE]]
            if len(lignes) > LIGNES_FICHE:
                out.append(f"… ({len(lignes) - LIGNES_FICHE} ligne(s) de plus dans le cache)")
            out += ["```", ""]
            for option in ETIQUETTES[jeu]:
                out.append(f"- [{'x' if option == choisie else ' '}] {option}")
            out.append("")
    chemin = chemin_fiche(jour)
    chemin.write_text("\n".join(out), encoding="utf-8")
    return chemin


# ---------------------------------------------------------------------------
# Jugements de Jev
# ---------------------------------------------------------------------------

_verrou = threading.Lock()


def lire_cache() -> dict[str, dict[str, Any]]:
    chemin = CACHE_DIR / "jev.jsonl"
    if not chemin.exists():
        return {}
    cache = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.strip():
            r = json.loads(ligne)
            cache[r["cle"]] = r
    return cache


def ecrire_cache(r: dict[str, Any]) -> None:
    with _verrou, (CACHE_DIR / "jev.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")


def requetes(c: Cas) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """(usage, état, questions) d'un cas : exactement ce que la veille enverrait."""
    if c.jeu == "B":
        return [("refonte", etat_refonte(c.fiche, c.pages), QUESTIONS_REFONTE)]
    out = [("filtre", etat_mandat(c.fiche, c.diff), QUESTIONS_MANDAT)]
    if c.verdict_llm == "inchange":
        out.append(("garde", etat_mandat(c.fiche, c.diff, c.resume_llm), QUESTIONS_MANDAT))
    return out


def cle(usage: str, etat: dict[str, Any]) -> str:
    return f"{usage}:{empreinte_etat(etat)}"


def juger(cas: list[Cas], *, paralleles: int = 6) -> None:
    client = ClientDecision()
    cache = lire_cache()
    a_faire = []
    for c in cas:
        for usage, etat, questions in requetes(c):
            if (k := cle(usage, etat)) not in cache:
                a_faire.append((k, c.id, usage, etat, questions))
    print(f"{len(a_faire)} appel(s) Jev à faire ({len(cache)} réponse(s) en cache)")
    cout = 0.0

    def un(item):
        k, cid, usage, etat, questions = item
        d = client.decider(etat, questions)
        r = d.reponses
        q = "meme_reglement" if usage == "refonte" else "touche"
        return {
            "cle": k,
            "cas": cid,
            "usage": usage,
            "p": r[q].proba("true"),
            "section": r["section"].choix if "section" in r else None,
            "modele": d.modele,
            "cout": d.cout_usd or 0.0,
        }

    with ThreadPoolExecutor(paralleles) as pool:
        futurs = [pool.submit(un, item) for item in a_faire]
        for i, f in enumerate(as_completed(futurs), 1):
            try:
                r = f.result()
            except ErreurDecision as exc:
                print(f"  ! {exc}")
                continue
            cout += r["cout"]
            ecrire_cache(r)
            if i % 20 == 0:
                print(f"  {i}/{len(a_faire)} · {cout:.3f} $")
    client.fermer()
    print(f"terminé · {cout:.3f} $")


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------


def auc(positifs: list[float], negatifs: list[float]) -> float | None:
    if not positifs or not negatifs:
        return None
    gagnes = sum((p > n) + 0.5 * (p == n) for p in positifs for n in negatifs)
    return gagnes / (len(positifs) * len(negatifs))


def _f(x: float | None) -> str:
    return "—" if x is None else f"{x:.3f}".replace(".", ",")


def _pct(n: int, total: int) -> str:
    return f"{n}/{total} ({n / total:.0%})" if total else "0/0"


def rapport(cas: list[Cas], jour: str) -> str:
    etiquettes = lire_etiquettes(jour)
    cache = lire_cache()
    notes: dict[tuple[str, str], float] = {}
    for c in cas:
        for usage, etat, _ in requetes(c):
            if (r := cache.get(cle(usage, etat))) is not None:
                notes[(c.id, usage)] = r["p"]
    cout = sum(r.get("cout", 0.0) for r in cache.values())

    out = [
        f"# Banc d'essai Jev de la veille ({date.today().isoformat()})",
        "",
        f"Cas du passage du {jour} : fiche d'étiquetage `{chemin_fiche(jour).name}`. "
        f"{len(etiquettes)} cas étiquetés sur {len(cas)}, {len(notes)} note(s) de Jev "
        f"(coût cumulé du cache : {cout:.3f} $).",
        "",
        "**Règle de passage** : une décision n'est branchée que si son jeu montre un seuil "
        "sans AUCUN faux manquant. Le seuil proposé est la note du pire cas positif, avec une "
        "marge ; le gain est la part de négatifs qu'il trie.",
        "",
    ]

    def serie(usage: str, positif: str, filtre_cas=lambda c: True):
        pos, neg, manquants = [], [], []
        for c in cas:
            if (c.id, usage) not in notes or not filtre_cas(c):
                continue
            lab = etiquettes.get(c.id)
            if lab is None:
                manquants.append(c.id)
            elif lab == positif:
                pos.append((notes[(c.id, usage)], c.id))
            else:
                neg.append((notes[(c.id, usage)], c.id))
        return sorted(pos), sorted(neg), manquants

    # Filtre : un positif filtré est un faux manquant, donc seuil ≤ min(positifs).
    pos, neg, sans = serie("filtre", "touche", lambda c: c.jeu == "A")
    out += ["## Filtre avant le LLM (jeu A, sans le résumé)", ""]
    if pos:
        bas = pos[0][0]
        seuil = round(bas * 0.8, 3)
        tries = [n for n in neg if n[0] < seuil]
        out += [
            f"- {len(pos)} « touche », {len(neg)} « ne touche pas », {len(sans)} sans étiquette ; "
            f"AUC {_f(auc([p for p, _ in pos], [n for n, _ in neg]))}.",
            f"- note minimale d'un « touche » : **{_f(bas)}** ({pos[0][1]}).",
            f"- seuil proposé (80 % de ce minimum) : **{_f(seuil)}** → écarte sans appel au LLM "
            f"{_pct(len(tries), len(neg))} des « ne touche pas ».",
            f"- au minimum exact : {_pct(sum(1 for n in neg if n[0] < bas), len(neg))}.",
            "",
            "Les cinq « touche » les plus bas (ceux qui fixent le seuil) :",
            "",
            *(f"  - {_f(p)} · {cid}" for p, cid in pos[:5]),
            "",
        ]
    else:
        out += ["Aucun « touche » étiqueté et noté : seuil impossible à fixer.", ""]

    # Garde : un faux « inchangé » sous le seuil est perdu, donc seuil ≤ min(positifs).
    pos, neg, sans = serie("garde", "touche")
    out += ["## Garde avant le ré-archivage (« inchangé » du LLM, avec son résumé)", ""]
    if pos:
        bas = pos[0][0]
        seuil = round(bas * 0.8, 3)
        alertes = [n for n in neg if n[0] >= seuil]
        out += [
            f"- {len(pos)} faux « inchangé » étiqueté(s), {len(neg)} vrais, {len(sans)} sans "
            f"étiquette ; AUC {_f(auc([p for p, _ in pos], [n for n, _ in neg]))}.",
            *(f"  - faux « inchangé » : {_f(p)} · {cid}" for p, cid in pos),
            f"- seuil proposé : **{_f(seuil)}** → {_pct(len(alertes), len(neg))} fausses "
            "alertes (une relecture chacune).",
            "",
            "Les fausses alertes, de la plus haute à la plus basse :",
            "",
            *(f"  - {_f(p)} · {cid}" for p, cid in sorted(alertes, reverse=True)[:15]),
            "",
        ]
    else:
        out += ["Aucun faux « inchangé » étiqueté et noté : seuil impossible à fixer.", ""]

    # Refontes : une refonte réelle rétrogradée coûte une retouche manquée et
    # rattrapée par la garde ; le seuil doit dépasser la note de la plus haute.
    pos, neg, sans = serie("refonte", "règlement changé")
    out += ["## Tri des refontes (jeu B)", ""]
    if pos or neg:
        haut = pos[-1][0] if pos else 0.0
        seuil = round(min(0.99, haut + (1 - haut) * 0.2), 3) if pos else None
        retro = [n for n in neg if seuil is not None and n[0] >= seuil]
        out += [
            f"- {len(pos)} refonte(s) réelle(s), {len(neg)} refonte(s) de site, {len(sans)} "
            f"sans étiquette ; AUC {_f(auc([n for n, _ in neg], [p for p, _ in pos]))} "
            "(« même règlement » noté plus haut pour les refontes de site).",
            f"- note « même règlement » la plus haute d'une refonte réelle : **{_f(haut)}**"
            + (f" ({pos[-1][1]})" if pos else ""),
            f"- seuil proposé : **{_f(seuil)}** → rétrograde "
            f"{_pct(len(retro), len(neg))} des refontes de site."
            if seuil is not None
            else "- aucune refonte réelle étiquetée : seuil impossible à fixer sans risque.",
            "",
            *(f"  - {_f(p)} · {cid} (réelle)" for p, cid in pos),
            *(f"  - {_f(p)} · {cid} (site)" for p, cid in neg),
            "",
        ]
    else:
        out += ["Aucun cas de refonte étiqueté et noté.", ""]

    out += [
        "## Brancher",
        "",
        "Une fois les seuils retenus, les poser dans `scripts/veille_arbitre.py` "
        "(`SEUIL_FILTRE`, `SEUIL_GARDE`, `SEUIL_REFONTE`) ou dans `backend/.env` "
        "(`JEV_VEILLE_FILTRE`, …). Un seuil laissé à `None` laisse sa décision débranchée.",
        "",
    ]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="veille_benchmark_jev.py", description=__doc__.split("\n")[0])
    p.add_argument("action", nargs="?", default="rapport", choices=("preparer", "juger", "rapport"))
    p.add_argument("--jour", default="2026-10-04", help="passage de veille étudié")
    p.add_argument(
        "--collecte",
        action="store_true",
        help="preparer : ajoute les cas en direct (étages A+B sur tout le parc, ~4 min, zéro modèle)",
    )
    p.add_argument(
        "--fiche-depuis",
        default="HEAD",
        help=(
            "preparer : révision git des fiches d'avant le passage étudié, pour les cas "
            "reconstruits depuis les snapshots (défaut : HEAD, tant que les retouches du "
            "passage ne sont pas committées ; '' pour le working tree)"
        ),
    )
    p.add_argument("--paralleles", type=int, default=6)
    args = p.parse_args(argv)

    if args.action == "preparer":
        cas = cas_snapshots(args.jour, args.fiche_depuis)
        print(f"jeu A, snapshots du {args.jour} : {len(cas)} cas")
        golds = cas_golds()
        print(f"jeu A, golds : {len(golds)} cas")
        cas += golds
        if args.collecte:
            direct = cas_en_direct({c.id for c in cas})
            print(
                f"en direct : {sum(c.jeu == 'A' for c in direct)} cas A, "
                f"{sum(c.jeu == 'B' for c in direct)} cas B"
            )
            cas += direct
        elif chemin_cas(args.jour).exists():
            # Sans --collecte, les cas en direct déjà préparés sont conservés.
            for c in lire_cas(args.jour):
                if c.origine == "direct":
                    # Un cas en direct se juge contre la fiche du working tree.
                    c.fiche = c.fiche or fiche_pour_jev(load_aide(AIDES_DIR / f"{c.slug}.yaml"))
                    cas.append(c)
        ecrire_cas(cas, args.jour)
        fiche = ecrire_fiche(cas, args.jour)
        auto = sum(1 for c in cas if c.etiquette_auto)
        print(f"fiche d'étiquetage : {fiche.relative_to(DATA_DIR.parent)} ({auto} cochés d'office)")
        return 0

    cas = lire_cas(args.jour)
    if args.action == "juger":
        try:
            from pipeline.llm import charger_env

            charger_env()
        except ImportError:
            pass
        juger(cas, paralleles=args.paralleles)

    chemin = REVIEWS_DIR / f"{date.today().isoformat()}-benchmark-veille-jev.md"
    chemin.write_text(rapport(cas, args.jour), encoding="utf-8")
    print(f"rapport : {chemin.relative_to(DATA_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
