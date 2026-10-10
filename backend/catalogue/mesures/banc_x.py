"""Banc X : l'extraction d'une aide, agent actuel contre extraction structurée (I0, M3).

Commandes, depuis backend/ :

    uv run python -m catalogue.mesures.banc_x tirer
    uv run python -m catalogue.mesures.banc_x verifier <dossier>/<slug>.yaml [--faits <fichier>]
    uv run python -m catalogue.mesures.banc_x agent <dossier du banc> --copie <dossier hors du dépôt>
    uv run python -m catalogue.mesures.banc_x noter <dossier du banc>

`tirer` choisit les 12 aides du banc : les 5 du banc d'ingestion du 2026-10-07
(`2026-10-07-benchmark-mistral-large-4.md`), puis 7 aides tirées au hasard
(graine 20261014) pour que chaque portée ait sa part : 2 nationales de
restauration, 2 nationales hors restauration, 1 départementale de restauration,
2 départementales hors restauration. Les 5 aides fixes couvrent déjà le
régional (2 de restauration, 2 hors restauration) et une départementale de
restauration. Une aide est « de restauration » si ses `familles` contiennent
`restauration_bati`, ou, sans `familles`, si son nom ou sa description parle de
restauration. Une aide n'entre au tirage que si elle a au moins un instantané
dans `data/sources/<slug>/` et n'existe pas aussi en `.yaml.echec`. Sortie :
backend/data/reviews/logs/refonte/<date>-banc-x-<n>/aides.json.

`verifier` contrôle une extraction sans rien écrire : le YAML se charge
(`aides_schema.load_aide`), chaque condition a une ligne `effect`, aucune n'est
`untyped` ni `manual_check` en gate, chaque fait cité existe dans `facts.yaml`,
`facts_pending.yaml` ou le fichier de faits proposés passé par `--faits` (dont
chaque entrée doit se valider comme un fait), et chaque `quote` se retrouve dans
les instantanés de `data/sources/<slug>/` par `veille_text.find_quote_in_any`,
la recherche du lint. Il imprime un résumé JSON.

`agent` (payant, plafond 6 $) fait tourner l'agent d'ingestion actuel, deux
passes indépendantes sur chacune des 12 aides, trois aides à la fois, dans une
copie jetable du dépôt (`--copie`, hors du worktree, préparée par rsync sans le
venv, les caches, `data/sources` ni `data/reviews`). Chaque run passe par
`catalogue.mesures.lanceur_agent` : instantanés archivés rejoués au lieu du
réseau, coût facturé et modèle servi relevés à chaque appel. Réglages : `or-glm`,
vérificateur `or-ds41`, `--sans-audit`, tarif d'`or-glm` corrigé à 0,15 et
0,50 $ par million de jetons, délai de 3 600 s par aide (au-delà, le run est tué
et compté « délai »). Sorties recopiées dans `<banc>/agent/p<n>/<slug>/`, sans
les instantanés, avec un `resume.json` par run ; un run déjà résumé n'est pas
relancé.

`noter` compare chaque extraction (agent, extraction structurée b et c ; deux
passes) à la référence réconciliée (`reference/final/`) : appariement des
conditions de `comparer_aides` (identifiant, citation, texte), exigences
décisives de la référence (`gate` ou `modulateur`) retrouvées, et retrouvées
« avec un effet qui pèse » (le candidat les porte aussi en `gate` ou
`modulateur`, ou par un `hard_filters`) ; précision ; citations introuvables
dans les instantanés ; concordance du typage sur les conditions appariées ;
acceptation ; coût facturé ; durée. Il écrit notes.jsonl, notes.json et
notes.txt, avec le critère d'adoption fixé au journal avant la mesure.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import statistics
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import yaml
from comparer_aides import _couvert_par_filtre, apparier_conditions, comparer
from veille_collect import load_baselines
from veille_text import find_quote_in_any

from aides_schema import Aide, FactDef, load_aide, load_facts, load_pending_facts
from catalogue.mesures.jeu_e import _dossier_neuf

BACKEND = Path(__file__).resolve().parents[2]
AIDES = BACKEND / "data" / "aides"
SOURCES = BACKEND / "data" / "sources"
GRAINE = 20261014
FIXES = (
    "hdf-jardins-en-scene",
    "hdf-actes-fonds-appui-projets-locaux",
    "88-patrimoine-protege-mh",
    "bretagne-edifices-publics",
    "pdl-cap-pcc",
)
A_TIRER = {
    ("nationale", True): 2,
    ("nationale", False): 2,
    ("departementale", True): 1,
    ("departementale", False): 2,
}
PORTEES = {"region": "regionale", "departement": "departementale"}


def _strate(aide: dict[str, Any]) -> tuple[str, bool]:
    portee = PORTEES.get(aide.get("categorie") or "", "nationale")
    familles = aide.get("familles") or []
    if familles:
        restauration = "restauration_bati" in familles
    else:
        texte = f"{aide.get('nom') or ''} {aide.get('description') or ''}".lower()
        restauration = "restaur" in texte
    return portee, restauration


def _sources(slug: str) -> list[str]:
    dossier = SOURCES / slug
    if not dossier.is_dir():
        return []
    return sorted(p.name for p in dossier.iterdir() if not p.name.endswith(".meta.yaml"))


def tirer(_: argparse.Namespace) -> int:
    echecs = {p.name.removesuffix(".yaml.echec") for p in AIDES.glob("*.yaml.echec")}
    population: dict[tuple[str, bool], list[str]] = {}
    strates: dict[str, tuple[str, bool]] = {}
    for f in sorted(AIDES.glob("*.yaml")):
        aide = yaml.safe_load(f.read_text(encoding="utf-8"))
        slug = aide["slug"]
        strates[slug] = _strate(aide)
        if slug in FIXES or slug in echecs or not _sources(slug):
            continue
        population.setdefault(strates[slug], []).append(slug)
    rng = random.Random(GRAINE)
    choisies = [{"slug": s, "strate": strates[s], "origine": "banc du 2026-10-07"} for s in FIXES]
    for strate, n in A_TIRER.items():
        for slug in rng.sample(population[strate], n):
            choisies.append(
                {
                    "slug": slug,
                    "strate": strate,
                    "origine": f"tirage, {n} sur {len(population[strate])}",
                }
            )
    for c in choisies:
        c["sources"] = _sources(c["slug"])
        c["strate"] = {"portee": c["strate"][0], "restauration": c["strate"][1]}
    dossier = _dossier_neuf("banc-x")
    (dossier / "aides.json").write_text(
        json.dumps(
            {
                "graine": GRAINE,
                "population": {
                    f"{p}, {'restauration' if r else 'autre'}": len(v)
                    for (p, r), v in population.items()
                },
                "aides": choisies,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(dossier)
    for c in choisies:
        print(c["slug"], c["strate"], c["origine"], len(c["sources"]), "fichiers")
    return 0


def verifier_extraction(chemin: Path, faits_proposes: Path | None = None) -> dict[str, Any]:
    """Les contrôles de forme et de citation d'une extraction, sans rien écrire."""
    rapport: dict[str, Any] = {"fichier": str(chemin), "erreurs": []}
    erreurs: list[str] = rapport["erreurs"]
    brut = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    try:
        load_aide(chemin)
        rapport["charge"] = True
    except Exception as exc:  # noqa: BLE001 : le rapport dit pourquoi, le banc continue
        rapport["charge"] = False
        erreurs.append(f"chargement : {str(exc)[:500]}")
    proposes: dict[str, Any] = {}
    if faits_proposes is not None and faits_proposes.exists():
        proposes = yaml.safe_load(faits_proposes.read_text(encoding="utf-8")) or {}
        for cle, valeur in proposes.items():
            try:
                FactDef.model_validate(valeur)
            except Exception as exc:  # noqa: BLE001
                erreurs.append(f"fait proposé {cle} invalide : {str(exc)[:300]}")
    connus = set(load_facts()) | set(load_pending_facts()) | set(proposes)
    conditions = brut.get("conditions") or []
    documents, illisibles, _ = load_baselines(brut["slug"])
    citations = {"exacte": 0, "degradee": 0, "baseline_pdf": 0, "absente": 0}
    absentes: list[str] = []
    for c in conditions:
        ident = c.get("id", "?")
        if "effect" not in c:
            erreurs.append(f"{ident} : pas de ligne effect")
        if c.get("kind", "untyped") == "untyped":
            erreurs.append(f"{ident} : untyped")
        if c.get("kind") == "manual_check" and c.get("effect", "gate") == "gate":
            erreurs.append(f"{ident} : manual_check en gate")
        if c.get("fact") and c["fact"] not in connus:
            erreurs.append(f"{ident} : fait inconnu {c['fact']}")
        if c.get("quote"):
            _, correspondance = find_quote_in_any(c["quote"], documents)
            citations[correspondance.status] += 1
            if correspondance.status == "absente":
                absentes.append(ident)
    rapport.update(
        conditions=len(conditions),
        decisives=sum(1 for c in conditions if c.get("effect", "gate") in ("gate", "modulateur")),
        citations=citations,
        citations_absentes=absentes,
        documents=[nom for nom, _, _ in documents],
        pdf_illisibles=illisibles,
        faits_proposes=sorted(proposes),
    )
    return rapport


def verifier(args: argparse.Namespace) -> int:
    rapport = verifier_extraction(Path(args.chemin), Path(args.faits) if args.faits else None)
    print(json.dumps(rapport, ensure_ascii=False, indent=1))
    return 0 if not rapport["erreurs"] and not rapport["citations_absentes"] else 1


PLAFOND_AGENT_USD = 6.0
RESERVE_RUN_USD = 0.5
DELAI_RUN_S = 3600
PARALLELE = 3
ARGUMENTS_AGENT = (
    "--model",
    "or-glm",
    "--model-verif",
    "or-ds41",
    "--sans-audit",
    "--tarif",
    "0.15,0.50",
)


def preparer_copie(copie: Path) -> None:
    """La copie jetable : backend sans venv ni caches ni sources ni reviews, et les skills."""
    racine = BACKEND.parent
    if copie.resolve().is_relative_to(racine.resolve()):
        raise SystemExit(f"la copie doit être hors du worktree : {copie}")
    (copie / "backend").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "rsync",
            "-a",
            "--delete",
            "--exclude",
            ".venv",
            "--exclude",
            ".cache",
            "--exclude",
            "__pycache__",
            "--exclude",
            "data/sources",
            "--exclude",
            "data/reviews",
            f"{BACKEND}/",
            f"{copie / 'backend'}/",
        ],
        check=True,
    )
    (copie / ".claude").mkdir(exist_ok=True)
    subprocess.run(
        [
            "rsync",
            "-a",
            "--delete",
            f"{racine / '.claude' / 'skills'}/",
            f"{copie / '.claude' / 'skills'}/",
        ],
        check=True,
    )


def _cout_appels(chemin: Path) -> tuple[float, int, list[dict[str, Any]]]:
    if not chemin.exists():
        return 0.0, 0, []
    appels = [json.loads(x) for x in chemin.read_text(encoding="utf-8").splitlines() if x]
    return sum(a.get("cout_usd") or 0.0 for a in appels), len(appels), appels


def _run_agent(copie: Path, banc: Path, passe: int, slug: str) -> dict[str, Any]:
    sortie = copie / "runs" / f"agent-p{passe}" / slug
    if sortie.exists():
        shutil.rmtree(sortie)
    sortie.mkdir(parents=True)
    commande = [
        sys.executable,
        "-m",
        "catalogue.mesures.lanceur_agent",
        "--sources",
        str(SOURCES / slug),
        "--appels",
        str(sortie / "appels.jsonl"),
        "--",
        "--slug",
        slug,
        "--sortie",
        str(sortie),
        *ARGUMENTS_AGENT,
    ]
    debut = time.monotonic()
    with (sortie / "console.log").open("w", encoding="utf-8") as console:
        try:
            code: int | str = subprocess.run(
                commande,
                cwd=copie / "backend",
                stdout=console,
                stderr=subprocess.STDOUT,
                timeout=DELAI_RUN_S,
            ).returncode
        except subprocess.TimeoutExpired:
            code = "delai"
    duree = round(time.monotonic() - debut, 1)
    aides = sortie / "aides"
    if (aides / f"{slug}.yaml").exists():
        issue = "acceptee"
    elif (aides / f"{slug}.yaml.echec").exists():
        issue = "refusee"
    else:
        issue = "sans_yaml"
    cout, n, appels = _cout_appels(sortie / "appels.jsonl")
    resume = {
        "slug": slug,
        "passe": passe,
        "code": code,
        "duree_s": duree,
        "issue": issue,
        "cout_facture_usd": round(cout, 6),
        "appels": n,
        "appels_en_erreur": sum(1 for a in appels if "erreur" in a),
        "appels_sans_cout": sum(
            1 for a in appels if "erreur" not in a and a.get("cout_usd") is None
        ),
        "modeles_servis": dict(Counter(a.get("modele_servi") for a in appels if "erreur" not in a)),
        "fournisseurs": dict(Counter(a.get("fournisseur") for a in appels if "erreur" not in a)),
    }
    destination = banc / "agent" / f"p{passe}" / slug
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(sortie, destination, ignore=shutil.ignore_patterns("sources"))
    (destination / "resume.json").write_text(
        json.dumps(resume, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return resume


def agent(args: argparse.Namespace) -> int:
    banc = Path(args.banc).resolve()
    copie = Path(args.copie).resolve()
    preparer_copie(copie)
    slugs = [
        a["slug"] for a in json.loads((banc / "aides.json").read_text(encoding="utf-8"))["aides"]
    ]
    taches = [
        (passe, slug)
        for passe in (1, 2)
        for slug in slugs
        if not (banc / "agent" / f"p{passe}" / slug / "resume.json").exists()
        and (not args.seulement or slug in args.seulement)
        and passe in args.passes
    ]
    deja = sum(
        json.loads(p.read_text(encoding="utf-8"))["cout_facture_usd"]
        for p in (banc / "agent").glob("p*/*/resume.json")
    )
    verrou = threading.Lock()
    etat = {"depense": deja, "en_cours": 0}
    resumes: list[dict[str, Any]] = []

    def executer(tache: tuple[int, str]) -> None:
        passe, slug = tache
        with verrou:
            if etat["depense"] + RESERVE_RUN_USD * (etat["en_cours"] + 1) > PLAFOND_AGENT_USD:
                print(
                    f"plafond : {slug} passe {passe} non lancé ({etat['depense']:.3f} $)",
                    flush=True,
                )
                return
            etat["en_cours"] += 1
        resume = _run_agent(copie, banc, passe, slug)
        with verrou:
            etat["en_cours"] -= 1
            etat["depense"] += resume["cout_facture_usd"]
            resumes.append(resume)
        print(
            f"p{passe} {slug} : {resume['issue']}, code {resume['code']}, {resume['duree_s']} s, "
            f"{resume['cout_facture_usd']:.4f} $, {resume['appels']} appels",
            flush=True,
        )

    with ThreadPoolExecutor(max_workers=PARALLELE) as pool:
        list(pool.map(executer, taches))
    print(f"{len(resumes)} runs ; dépense facturée de la série {etat['depense'] - deja:.4f} $")
    return 0


CONFIGURATIONS = ("agent", "structuree-b", "structuree-c")


def _lire_aide(dossier: Path, slug: str) -> Aide | None:
    for nom in (f"{slug}.yaml", f"{slug}.yaml.echec"):
        chemin = dossier / "aides" / nom
        if chemin.exists():
            try:
                return Aide.model_validate(yaml.safe_load(chemin.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001 : un YAML invalide compte comme absent
                return None
    return None


def acceptation_uniforme(dossier: Path, slug: str) -> tuple[bool | None, list[str]]:
    """Les mêmes contrôles de données pour toutes les configurations.

    Le YAML du candidat (`.yaml` ou `.yaml.echec`) est copié dans un dossier
    temporaire, puis : lint mono-slug avec citations et contrôles d'écriture
    (comme l'ingestion), contre les faits proposés du candidat ; `familles` non
    vide ; trois faits neufs au plus. L'agent a d'autres post-contrôles (fiche
    de review, vérification lancée) que l'extraction structurée sans
    vérificateur n'a pas : ils ne portent pas sur les données.
    """
    import tempfile

    from lint_aides_data import lint

    source = next(
        (
            dossier / "aides" / n
            for n in (f"{slug}.yaml", f"{slug}.yaml.echec")
            if (dossier / "aides" / n).exists()
        ),
        None,
    )
    if source is None:
        return None, ["aucun YAML"]
    pending = dossier / "facts_pending.yaml"
    load_pending_facts.cache_clear()
    reels = set(load_pending_facts())
    proposes = sorted(set(load_pending_facts(pending)) - reels) if pending.exists() else []
    load_pending_facts.cache_clear()
    erreurs: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        aides = Path(tmp) / "aides"
        aides.mkdir()
        shutil.copyfile(source, aides / f"{slug}.yaml")
        try:
            brut = yaml.safe_load(source.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            return False, [f"YAML illisible : {exc}"]
        if not brut.get("familles"):
            erreurs.append("familles vide")
        if len(proposes) > 3:
            erreurs.append(f"{len(proposes)} faits proposés")
        rapport = lint(
            [slug],
            quotes=True,
            ecriture=True,
            aides_dir=aides,
            pending_path=pending if pending.exists() else Path(tmp) / "vide.yaml",
            faits_du_run=tuple(proposes),
        )
        if not rapport.ok:
            erreurs.append("lint : " + rapport.texte()[:1500])
    load_pending_facts.cache_clear()
    return not erreurs, erreurs


def couverture(citation: str, documents: Any) -> float:
    """Part du texte normalisé d'une citation retrouvée dans un instantané, par blocs d'au moins 15 caractères.

    Mesure de fond, qui peut échouer : une citation recollée de passages réels
    est couverte à 100 % même quand la recherche du lint la refuse ; une
    citation inventée ne l'est pas.
    """
    from difflib import SequenceMatcher

    from veille_text import normalize

    cible = normalize(citation)
    if not cible:
        return 1.0
    meilleure = 0
    for _nom, texte, _type in documents:
        blocs = SequenceMatcher(None, cible, normalize(texte), autojunk=False).get_matching_blocks()
        meilleure = max(meilleure, sum(b.size for b in blocs if b.size >= 15))
    return meilleure / len(cible)


def noter_un(reference: Aide, candidat: Aide | None, documents: Any) -> dict[str, Any]:
    if candidat is None:
        decisives = sum(1 for c in reference.conditions if c.effect in ("gate", "modulateur"))
        return {"yaml": False, "decisives_reference": decisives, "decisives_pesantes": 0}
    comp = comparer(reference, candidat, documents)
    paires, manquantes, _ = apparier_conditions(reference.conditions, candidat.conditions)
    decisives = {c.id for c in reference.conditions if c.effect in ("gate", "modulateur")}
    pesantes = sum(
        1 for ref, cand in paires if ref.id in decisives and cand.effect in ("gate", "modulateur")
    ) + sum(1 for c in manquantes if c.id in decisives and _couvert_par_filtre(c, candidat))
    concordantes = sum(
        1
        for ref, cand in paires
        if (ref.kind, ref.effect, ref.fact, ref.field)
        == (cand.kind, cand.effect, cand.fact, cand.field)
    )
    introuvables = [
        c.quote
        for c in candidat.conditions
        if c.quote and not find_quote_in_any(c.quote, documents)[1].found
    ]
    couvertures = [round(couverture(q, documents), 3) for q in introuvables]
    return {
        "yaml": True,
        "couverture_citations_introuvables": couvertures,
        "conditions_reference": comp.conditions_reference,
        "conditions_candidat": comp.conditions_candidat,
        "communes": comp.communes,
        "decisives_reference": comp.decisives_reference,
        "decisives_retrouvees": comp.decisives_retrouvees,
        "decisives_pesantes": pesantes,
        "precision": round(comp.precision, 4),
        "citations": comp.citations_candidat,
        "citations_absentes": comp.citations_candidat - comp.citations_verifiees,
        "typage_concordant": concordantes,
        "familles": list(candidat.familles),
        "familles_reference": list(reference.familles),
        "avertissements": comp.avertissements(),
    }


def noter(args: argparse.Namespace) -> int:
    banc = Path(args.banc).resolve()
    slugs = [
        a["slug"] for a in json.loads((banc / "aides.json").read_text(encoding="utf-8"))["aides"]
    ]
    lignes: list[dict[str, Any]] = []
    for slug in slugs:
        ref_yaml = banc / "reference" / "final" / f"{slug}.yaml"
        if not ref_yaml.exists():
            lignes.append({"slug": slug, "reference": "absente ou hors périmètre"})
            continue
        reference = load_aide(ref_yaml)
        documents, _, _ = load_baselines(slug)
        for config in CONFIGURATIONS:
            for passe in (1, 2):
                dossier = banc / config / f"p{passe}" / slug
                chemin_resume = dossier / "resume.json"
                resume = (
                    json.loads(chemin_resume.read_text(encoding="utf-8"))
                    if chemin_resume.exists()
                    else {}
                )
                ligne = {
                    "slug": slug,
                    "configuration": config,
                    "passe": passe,
                    "issue": resume.get("issue", "absent"),
                    "cout_facture_usd": resume.get("cout_facture_usd"),
                    "duree_s": resume.get("duree_s"),
                    "appels": resume.get("appels"),
                    **noter_un(reference, _lire_aide(dossier, slug), documents),
                }
                ok, erreurs = acceptation_uniforme(dossier, slug)
                ligne.update(accepte_controle=ok, erreurs_controle=erreurs)
                lignes.append(ligne)
    (banc / "notes.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lignes), encoding="utf-8"
    )

    def rappel(x: dict[str, Any], acceptees_seulement: bool) -> float:
        if not x.get("decisives_reference"):
            return 1.0
        if acceptees_seulement and x["issue"] != "acceptee":
            return 0.0
        return x.get("decisives_pesantes", 0) / x["decisives_reference"]

    notees = [x for x in lignes if "configuration" in x]
    synthese: dict[str, Any] = {}
    for config in CONFIGURATIONS:
        xs = [x for x in notees if x["configuration"] == config and x["issue"] != "absent"]
        if not xs:
            continue
        couts = [x["cout_facture_usd"] for x in xs if x.get("cout_facture_usd") is not None]
        durees = [x["duree_s"] for x in xs if x.get("duree_s") is not None]
        couvertures = [c for x in xs for c in x.get("couverture_citations_introuvables", [])]
        acceptees = sum(1 for x in xs if x["issue"] == "acceptee")
        synthese[config] = {
            "couples": len(xs),
            "acceptees": acceptees,
            "acceptees_controle_uniforme": sum(1 for x in xs if x.get("accepte_controle")),
            "issues": dict(Counter(x["issue"] for x in xs)),
            "rappel_toutes_sorties": round(statistics.mean(rappel(x, False) for x in xs), 4),
            "rappel_acceptees_seulement": round(statistics.mean(rappel(x, True) for x in xs), 4),
            "decisives": f"{sum(x.get('decisives_pesantes', 0) for x in xs)}/{sum(x.get('decisives_reference', 0) for x in xs)}",
            "precision_moyenne": round(
                statistics.mean([x.get("precision", 0) for x in xs if x["yaml"]] or [0]), 4
            ),
            "citations_absentes": sum(x.get("citations_absentes", 0) for x in xs),
            "citations": sum(x.get("citations", 0) for x in xs),
            "couverture_minimale_des_introuvables": min(couvertures) if couvertures else None,
            "typage_concordant": f"{sum(x.get('typage_concordant', 0) for x in xs)}/{sum(x.get('communes', 0) for x in xs)}",
            "cout_moyen_usd": round(statistics.mean(couts), 4) if couts else None,
            "cout_par_acceptee_usd": round(sum(couts) / acceptees, 4) if acceptees else None,
            "duree_mediane_s": statistics.median(durees) if durees else None,
        }

    def intervalle(par_aide: dict[str, float]) -> dict[str, Any]:
        """Moyenne des différences par aide, intervalles à 95 % par rééchantillonnage des aides et t."""
        valeurs = list(par_aide.values())
        rng = random.Random(1)
        moyennes = sorted(
            statistics.mean(rng.choice(valeurs) for _ in valeurs) for _ in range(20000)
        )
        n = len(valeurs)
        moyenne = statistics.mean(valeurs)
        ecart = statistics.stdev(valeurs) / n**0.5 if n > 1 else 0.0
        t = {12: 2.201, 11: 2.228, 10: 2.262, 24: 2.069, 23: 2.074}.get(n, 2.0)
        return {
            "aides": n,
            "moyenne_points": round(100 * moyenne, 1),
            "ic95_reechantillonnage_points": [
                round(100 * moyennes[500], 1),
                round(100 * moyennes[19499], 1),
            ],
            "ic95_t_points": [
                round(100 * (moyenne - t * ecart), 1),
                round(100 * (moyenne + t * ecart), 1),
            ],
        }

    index = {(x["configuration"], x["slug"], x["passe"]): x for x in notees}
    comparaisons: dict[str, Any] = {}
    for config in ("structuree-b", "structuree-c"):
        bloc: dict[str, Any] = {}
        for lecture, seulement in (("toutes_sorties", False), ("acceptees_seulement", True)):
            par_aide: dict[str, float] = {}
            for slug in slugs:
                diffs = [
                    rappel(index[(config, slug, p)], seulement)
                    - rappel(index[("agent", slug, p)], seulement)
                    for p in (1, 2)
                    if (config, slug, p) in index and ("agent", slug, p) in index
                ]
                if diffs:
                    par_aide[slug] = statistics.mean(diffs)
            bloc[lecture] = intervalle(par_aide)
        # Là où l'agent a produit un YAML : la qualité d'extraction seule.
        par_aide_produit: dict[str, float] = {}
        for slug in slugs:
            diffs = [
                rappel(index[(config, slug, p)], False) - rappel(index[("agent", slug, p)], False)
                for p in (1, 2)
                if (config, slug, p) in index and index.get(("agent", slug, p), {}).get("yaml")
            ]
            if diffs:
                par_aide_produit[slug] = statistics.mean(diffs)
        bloc["la_ou_l_agent_produit"] = intervalle(par_aide_produit)
        comparaisons[config] = bloc
    resultat = {"synthese": synthese, "comparaisons_appariees": comparaisons}
    (banc / "notes.json").write_text(
        json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    texte = [f"{k} : {json.dumps(v, ensure_ascii=False)}" for k, v in synthese.items()]
    texte += [
        f"{k} contre l'agent : {json.dumps(v, ensure_ascii=False)}" for k, v in comparaisons.items()
    ]
    (banc / "notes.txt").write_text("\n".join(texte) + "\n", encoding="utf-8")
    print("\n".join(texte))
    return 0


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = parseur.add_subparsers(dest="commande", required=True)
    sous.add_parser("tirer").set_defaults(fonction=tirer)
    p = sous.add_parser("verifier")
    p.add_argument("chemin")
    p.add_argument("--faits")
    p.set_defaults(fonction=verifier)
    p = sous.add_parser("agent")
    p.add_argument("banc")
    p.add_argument("--copie", required=True)
    p.add_argument("--seulement", nargs="*", default=[])
    p.add_argument("--passes", nargs="*", type=int, default=[1, 2])
    p.set_defaults(fonction=agent)
    p = sous.add_parser("noter")
    p.add_argument("banc")
    p.set_defaults(fonction=noter)
    args = parseur.parse_args()
    return args.fonction(args)


if __name__ == "__main__":
    raise SystemExit(main())
