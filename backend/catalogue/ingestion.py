"""Ingérer les aides que l'entrée a admises (incrément I7).

L'agent d'ingestion reste le décideur en service de l'extraction (`G-extraction`,
le banc de confirmation de l'extraction structurée ayant été abandonné le
2026-10-11). Il tourne sous le même contrat qu'une ré-extraction
(`catalogue.agent`) ; ce module décide de ce qui s'écrit :

- **acceptée** par les contrôles de l'agent : le YAML entre au catalogue, ses
  instantanés dans `data/sources/<slug>/`, ses faits neufs en fin de
  `facts_pending.yaml`, chacun en case `H-fait` (décision 5) ;
- **allongement du questionnaire** (l'agent rend un coût en questions) :
  l'aide attend en brouillon (`data/catalogue/brouillons/`), avec une case ;
- **slug déjà pris** par une aide en service : brouillon et case, jamais
  d'écrasement ;
- **refusée** : rebut (`data/catalogue/rebuts/`), jamais de `.yaml.echec` neuf ;
- **hors périmètre** selon l'agent : écartée, motif au journal ;
- **panne** (réseau, crédits, modèle substitué, vérificateur indisponible,
  délai) : rien n'est écrit, l'aide reste due.

Le bloc `fiche:` d'une aide neuve n'est pas rédigé ici (`rediger_fiches.py`
reste un outil lancé à la main) : une case « fiche à rédiger » le dit.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline import etat

from aides_schema import AIDES_DIR, DATA_DIR, FACTS_PENDING_FILE
from catalogue import reextraction as rx
from catalogue.cases import Case
from catalogue.journal import Evenement, Vue, empreinte
from catalogue.veille_collect import SOURCES_DIR

BROUILLONS = DATA_DIR / "catalogue" / "brouillons"


@dataclass
class Admise:
    """Une page admise par l'entrée, prête à ingérer."""

    objet: str
    url: str
    territoire: str
    lu: dict[str, Any]

    def tache(self) -> etat.Tache:
        lu = self.lu
        return etat.Tache(
            titre=lu.get("titre") or self.url,
            url=self.url,
            urls_pdf=list(lu.get("urls_pdf") or []),
            territoire=self.territoire,
            famille=lu.get("famille"),
            beneficiaires=lu.get("beneficiaires"),
            destinataire=lu.get("destinataire") or "indetermine",
            objet=lu.get("objet") or "indetermine",
            categorie_ecart=lu.get("categorie_ecart"),
            note=lu.get("note"),
            statut="valide",
        )


def admises_a_ingerer(vue: Vue) -> list[Admise]:
    """Les pages admises (par la règle, ou par Félix) que l'ingestion n'a pas encore tranchées."""
    sortie = []
    for (objet, decision), e in sorted(vue.derniere.items()):
        if decision != "entree":
            continue
        felix = vue.felix.get((objet, "entree-doute"))
        admise = e.issue == "admise" or (felix is not None and felix.issue == "admettre")
        faite = vue.derniere.get((objet, "ingestion"))
        if admise and (
            faite is None
            or faite.issue not in ("acceptee", "refusee", "hors_perimetre", "brouillon")
        ):
            d = e.donnees
            sortie.append(Admise(objet, d["url"], d.get("territoire", ""), d.get("lu") or {}))
    return sortie


def slug_pour(a: Admise, occupes: set[str]) -> str:
    from prospection import lecture
    from prospection.territoires import charger_territoires

    t = charger_territoires().get(a.territoire)
    propose = a.lu.get("slug") or lecture.kebab(a.lu.get("titre") or a.url)
    if t is None:
        return propose
    return lecture.slug_final(t, propose, a.lu.get("titre") or "", occupes)


@dataclass
class Bilan:
    slug: str
    issue: str
    raison: str = ""
    panne: str | None = None
    cout_usd: float = 0.0
    duree_s: float = 0.0
    cases: list[Case] = field(default_factory=list)
    snapshots: list[str] = field(default_factory=list)
    faits: list[str] = field(default_factory=list)


def ingerer(
    slug: str,
    tache: etat.Tache,
    *,
    plafond: float,
    delai_s: float,
    jour: dt.date,
    sorties: Path = rx.SORTIES,
    aides: Path = AIDES_DIR,
    sources: Path = SOURCES_DIR,
    pending: Path = FACTS_PENDING_FILE,
    rebuts: Path = rx.REBUTS,
    brouillons: Path = BROUILLONS,
    ecrire: bool = True,
    lanceur: Any = None,
) -> Bilan:
    """Une aide neuve, de l'agent à l'écriture. Ne lève pas : une erreur est une panne."""
    sortie = (
        sorties
        / f"{jour.isoformat()}-{slug}-{os.getpid()}-{dt.datetime.now().strftime('%H%M%S%f')}"
    )
    (sortie / "aides").mkdir(parents=True)
    (sortie / "tache.json").write_text(tache.model_dump_json(), encoding="utf-8")
    lancement = (lanceur or rx.lancer)(slug, sortie, plafond, delai_s)
    b = Bilan(slug, "panne", cout_usd=rx.depense(sortie), duree_s=lancement.duree_s)
    objet = f"a:{slug}"
    if lancement.resultat is None:
        b.raison, b.panne = f"agent sans résultat ({lancement.panne})", lancement.panne
        return b
    issue, raison, classe = rx.classer(lancement.resultat)
    b.issue, b.raison, b.panne = issue, raison, classe
    if issue == "refusee":
        if ecrire:
            rx.rebut(slug, sortie, raison, jour, rebuts)
        return b
    if issue != "acceptee":
        return b
    texte = (sortie / "aides" / f"{slug}.yaml").read_text(encoding="utf-8")
    questions = str(lancement.resultat.get("cout_questions") or "")
    collision = (aides / f"{slug}.yaml").exists()
    if questions or collision:
        b.issue = "brouillon"
        motif = (
            f"le slug `{slug}` est déjà pris par une aide en service"
            if collision
            else f"l'aide allonge le questionnaire : {questions}"
        )
        b.raison = motif
        b.cases.append(
            Case(
                "ingestion-brouillon",
                objet,
                "aide en brouillon",
                empreinte(texte),
                {"ecrire": "l'écrire au catalogue", "ecarter": "l'écarter"},
                (motif, f"Brouillon : `backend/data/catalogue/brouillons/{slug}.yaml`."),
            )
        )
        if ecrire:
            brouillons.mkdir(parents=True, exist_ok=True)
            (brouillons / f"{slug}.yaml").write_text(texte, encoding="utf-8")
        return b
    from aides_schema import load_facts, load_pending_facts

    try:
        connus = set(load_facts()) | set(load_pending_facts(pending))
        proposes = (
            load_pending_facts(sortie / "facts_pending.yaml")
            if (sortie / "facts_pending.yaml").exists()
            else {}
        )
    except ValueError as exc:
        b.issue, b.raison, b.panne = "panne", f"faits illisibles : {exc}"[:300], "fichier_partage"
        return b
    neufs = [f for f in proposes if f not in connus and f"fact: {f}" in texte]
    if ecrire:
        b.faits = rx.ajouter_faits(neufs, sortie / "facts_pending.yaml", pending)
        (sources / slug).mkdir(parents=True, exist_ok=True)
        for p in (
            sorted((sortie / "sources" / slug).iterdir())
            if (sortie / "sources" / slug).is_dir()
            else []
        ):
            if not (sources / slug / p.name).exists():
                shutil.copy2(p, sources / slug / p.name)
                b.snapshots.append(p.name)
        temporaire = aides / f".{slug}.yaml.{os.getpid()}.tmp"
        temporaire.write_text(texte, encoding="utf-8")
        temporaire.replace(aides / f"{slug}.yaml")
    for f in neufs:
        b.cases.append(
            Case(
                "H-fait",
                objet,
                f"fait neuf `{f}`",
                f,
                {"valider": "valider", "refuser": "refuser"},
                (f"Proposé par l'ingestion de `{slug}`.",),
            )
        )
    b.cases.append(
        Case(
            "ingestion-fiche",
            objet,
            "bloc `fiche:` à rédiger",
            empreinte(texte),
            {"vu": "rédigé (`rediger_fiches.py`)"},
            (f"`uv run python scripts/rediger_fiches.py --model or-glm {slug}`",),
        )
    )
    return b


# ------------------------------------------------------------------ projection inverse vers la file


def projeter_file(evenements: list[Evenement], chemin: Path) -> list[str]:
    """Reporte dans `file-attente.yaml` ce que la nouvelle chaîne a tranché.

    Pour que l'ancienne chaîne, relancée, ne rejuge ni ne réingère rien : une
    URL jugée par l'entrée y entre (écartée en `ignore` avec son motif, doute en
    `a_valider`, admise en `valide`), et une ingestion faite y passe `ingere`,
    `echec` ou `ignore`. Une tâche déjà présente n'est jamais réécrite, sauf
    pour son statut d'ingestion : une décision humaine de la file reste.
    """
    file = etat.charger(chemin) if chemin.exists() else {}
    par_url = {t.url: s for s, t in file.items()}
    occupes = set(file) | {p.stem for p in AIDES_DIR.glob("*.yaml")}
    nouvelles: dict[str, etat.Tache] = {}
    derniere: dict[str, Evenement] = {}
    ingestions: dict[str, Evenement] = {}
    for e in evenements:
        if e.type == "decision" and e.decision == "entree":
            derniere[e.donnees["url"]] = e
        elif e.type == "decision" and e.decision == "ingestion":
            ingestions[e.donnees.get("url", "")] = e
    for url, e in derniere.items():
        if url in par_url:
            continue
        d, lu = e.donnees, e.donnees.get("lu") or {}
        statut = {"admise": "valide", "ecartee": "ignore", "doute": "a_valider"}.get(
            e.issue or "", "a_valider"
        )
        slug = slug_pour(Admise(e.objet, url, d.get("territoire") or "", lu), occupes)
        occupes.add(slug)
        nouvelles[slug] = etat.Tache(
            titre=lu.get("titre") or url,
            url=url,
            territoire=d.get("territoire") or "",
            famille=lu.get("famille"),
            destinataire=lu.get("destinataire") or "indetermine",
            objet=lu.get("objet") or "indetermine",
            categorie_ecart=lu.get("categorie_ecart"),
            statut=statut,
            motif_ignore=(f"nouvelle chaîne : {d.get('motif')}" if statut == "ignore" else None),
        )
        par_url[url] = slug
    ajoutees = etat.fusionner(chemin, nouvelles) if nouvelles else []
    for url, e in ingestions.items():
        slug = e.donnees.get("slug") if e.donnees.get("slug") in file else par_url.get(url)
        if slug is None:
            continue
        statut = {"acceptee": "ingere", "refusee": "echec", "hors_perimetre": "ignore"}.get(
            e.issue or ""
        )
        if statut:
            etat.mettre_a_jour(chemin, slug, statut=statut)
    return list(ajoutees)


def lire_tache(sortie: Path) -> etat.Tache | None:
    chemin = sortie / "tache.json"
    return (
        etat.Tache.model_validate(json.loads(chemin.read_text(encoding="utf-8")))
        if chemin.exists()
        else None
    )


# ------------------------------------------------------------------ commande


def commande(journal: Path, parties: Path | None, *, a_blanc: bool = False) -> int:
    """`python -m catalogue ingestion` : les admises en attente, une par une, sous le budget du run."""
    import secrets

    from pipeline.etat import FILE_ATTENTE

    from catalogue.budget import Budget, BudgetEpuise
    from catalogue.journal import Journal
    from catalogue.rapport import Rapport, Section, parties_json
    from catalogue.registre import BACKEND, charger

    reg = charger()
    jour = dt.date.today()
    run = f"{jour.isoformat()}-ingestion-{secrets.token_hex(2)}"
    j = Journal(journal)
    vue = Vue(list(j.lire()))
    budget = Budget(reg.budgets.run.plafond_usd)
    file = etat.charger(FILE_ATTENTE) if FILE_ATTENTE.exists() else {}
    par_url = {t.url: s for s, t in file.items()}
    occupes = set(file) | {p.stem for p in AIDES_DIR.glob("*.yaml")}
    bilans: list[Bilan] = []
    plafond = 1.875  # budget de l'agent par aide (1,50 $) × 1,25, vérification comprise
    for a in admises_a_ingerer(vue):
        slug = par_url.get(a.url) or slug_pour(a, occupes)
        occupes.add(slug)
        try:
            reservation = budget.reserver(plafond, f"ingestion {slug}")
        except BudgetEpuise:
            break  # le reste attend le run suivant ; le rapport le dit
        b = None
        try:
            b = ingerer(
                slug, a.tache(), plafond=plafond, delai_s=3600, jour=jour, ecrire=not a_blanc
            )
        finally:
            budget.regler(reservation, b.cout_usd if b is not None else None)
        bilans.append(b)
        donnees = {
            "url": a.url,
            "slug": slug,
            "raison": b.raison[:500],
            "cout_usd": b.cout_usd,
            "faits": b.faits,
            "snapshots": b.snapshots,
        }
        if b.panne:
            j.ajouter(
                Evenement(
                    "panne",
                    a.objet,
                    decision="ingestion",
                    decideur="agent",
                    run=run,
                    issue=b.panne,
                    donnees=donnees,
                )
            )
        else:
            j.ajouter(
                Evenement(
                    "decision",
                    a.objet,
                    decision="ingestion",
                    decideur="agent",
                    run=run,
                    issue=b.issue,
                    donnees=donnees,
                )
            )
    if not a_blanc and FILE_ATTENTE.exists():
        projeter_file(list(j.lire()), FILE_ATTENTE)
    from collections import Counter

    issues = Counter(b.issue for b in bilans)
    lignes = [
        f"{len(bilans)} aide(s) traitée(s) : {', '.join(f'{k} {v}' for k, v in sorted(issues.items())) or 'aucune'} ; {budget.depense:.4f} $."
    ]
    lignes += [
        f"- `{b.slug}` : {b.issue}{' (' + b.raison[:160] + ')' if b.raison else ''}" for b in bilans
    ]
    cases = [c for b in bilans for c in b.cases]
    entete = [f"- Ingestion : {len(bilans)} aide(s), {len(cases)} case(s), {budget.depense:.4f} $."]
    if parties is not None:
        parties.write_text(
            parties_json(entete, cases, [Section("Ingestion", lignes)]), encoding="utf-8"
        )
    else:
        r = Rapport(jour, run)
        r.entete, r.cases, r.sections = entete, cases, [Section("Ingestion", lignes)]
        print(f"rapport : {r.ecrire(BACKEND / 'data' / 'reviews')}")
    return 0
