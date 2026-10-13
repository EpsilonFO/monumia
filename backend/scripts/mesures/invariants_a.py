"""Invariants et pièges du contrat de données, de l'ingestion et des modèles, à HEAD.

    cd backend && uv run python scripts/mesures/invariants_a.py

Phase 1 de la refonte des pipelines : mesure seule. Le script n'exécute aucun
script du pipeline ni aucun banc, n'appelle aucun modèle et ne touche pas au
réseau. Il importe des modules existants (aides_schema, eligibility_engine,
veille_text, veille_collect, lint_aides_data, ingestion.contexte) et appelle
des fonctions qui ne font que lire. Deux précautions :

  - `veille_collect.pdf_bytes_to_text` est remplacée par une version qui lit
    le cache `pdftotext` (celui de ce worktree, puis celui du dépôt principal)
    et qui, à défaut, lance `pdftotext` SANS écrire de cache ;
  - les essais de chargement d'un catalogue cassé se font dans un dossier
    temporaire SOUS le dossier de sortie, effacé en fin de script.

Produit, dans `data/reviews/logs/refonte/2026-10-10-invariants-a-1/` :

    importeurs.json         importeurs de veille_text et veille_collect (AST), tests compris
    importeurs.md           la même liste, lisible
    schema.json             modèles pydantic, `extra`, essais de clé inconnue par niveau
    effet_implicite.json    effet par kind (schéma) et effets implicites du catalogue
    chargement.json         chargement du catalogue réel et pannes provoquées
    fail_closed.json        normalisation des réponses, prédicats, hard_filters inconnus
    catalogue.json          conformité du catalogue aux invariants (comptes)
    identifiants.json       identifiants persistés, clés de faits codées en dur
    citations.json          vérification des citations contre les snapshots
    citations_golden.jsonl  verdict exact de find_quote_in_any pour chaque citation
    normalize_golden.json   empreinte de normalize() sur toutes les citations
    tests_gardiens.json     occurrences des symboles gardés dans tests/
    lint_global.json        le lint global appelé en processus (sans --quotes)
    complements.json        formes des faits, gate porteur négatif, URL partagées, .echec
    divers.json             outils de l'agent, taille du prompt système, file d'attente
    resume.txt              chiffres clés, une ligne chacun
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
SCRIPTS = BACKEND / "scripts"
DATA = BACKEND / "data"
SORTIE = DATA / "reviews" / "logs" / "refonte" / "2026-10-10-invariants-a-1"
TMP = SORTIE / "_tmp"
CACHES_PDF = (
    BACKEND / ".cache" / "pdftotext",
    Path("/Users/felixollivier/monumia/backend/.cache/pdftotext"),
)

sys.path[:0] = [str(BACKEND), str(SCRIPTS)]

import veille_collect  # noqa: E402

_PDF_STATS: Counter[str] = Counter()


def _pdf_lecture_seule(content: bytes) -> str | None:
    """`pdf_bytes_to_text` sans écriture du cache disque (consigne : lecture seule)."""
    sha = hashlib.sha256(content).hexdigest()
    for dossier in CACHES_PDF:
        cache = dossier / f"{sha}.txt"
        try:
            if cache.is_file():
                _PDF_STATS["cache"] += 1
                return cache.read_text(encoding="utf-8")
        except OSError:
            pass
    _PDF_STATS["pdftotext"] += 1
    return veille_collect._pdftotext(content)


veille_collect.pdf_bytes_to_text = _pdf_lecture_seule  # type: ignore[assignment]

import veille_text  # noqa: E402
from lint_aides_data import check_quotes  # noqa: E402
from pydantic import BaseModel, ValidationError  # noqa: E402

import aides_schema as S  # noqa: E402
import eligibility_engine as E  # noqa: E402

# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - m, 4), round(c + m, 4)]


def taux(k: int, n: int) -> dict[str, Any]:
    return {"k": k, "n": n, "p": round(k / n, 4) if n else None, "wilson95": wilson(k, n)}


def ecrire(nom: str, contenu: Any) -> None:
    chemin = SORTIE / nom
    if isinstance(contenu, str):
        chemin.write_text(contenu, encoding="utf-8")
    else:
        chemin.write_text(
            json.dumps(contenu, ensure_ascii=False, indent=1, default=str) + "\n",
            encoding="utf-8",
        )


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(RACINE), *args], capture_output=True, text=True, check=True
    ).stdout


RESUME: list[str] = []


def note(ligne: str) -> None:
    RESUME.append(ligne)
    print(ligne)


# ---------------------------------------------------------------------------
# 1. Importeurs de veille_text et veille_collect
# ---------------------------------------------------------------------------

MODULES = ("veille_text", "veille_collect")


class _Visiteur(ast.NodeVisitor):
    def __init__(self) -> None:
        self.portee: list[str] = []
        self.imports: list[dict[str, Any]] = []
        self.alias: dict[str, str] = {}
        self.attributs: list[dict[str, Any]] = []
        self.chaines: list[dict[str, Any]] = []

    def _porte(self) -> str:
        return ".".join(self.portee) or "<module>"

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.portee.append(node.name)
        self.generic_visit(node)
        self.portee.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.portee.append(node.name)
        self.generic_visit(node)
        self.portee.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            if a.name in MODULES:
                self.alias[a.asname or a.name] = a.name
                self.imports.append(
                    {
                        "ligne": node.lineno,
                        "module": a.name,
                        "forme": "import",
                        "noms": [],
                        "portee": self._porte(),
                    }
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module in MODULES:
            self.imports.append(
                {
                    "ligne": node.lineno,
                    "module": node.module,
                    "forme": "from",
                    "noms": [a.name for a in node.names],
                    "portee": self._porte(),
                }
            )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id in self.alias:
            self.attributs.append(
                {
                    "ligne": node.lineno,
                    "module": self.alias[node.value.id],
                    "attribut": node.attr,
                    "ecriture": isinstance(getattr(node, "ctx", None), ast.Store),
                }
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # mock.patch.object(veille_collect, "SOURCES_DIR", ...) et mock.patch("veille_collect.X")
        args = node.args
        if (
            len(args) >= 2
            and isinstance(args[0], ast.Name)
            and args[0].id in self.alias
            and isinstance(args[1], ast.Constant)
            and isinstance(args[1].value, str)
        ):
            self.chaines.append(
                {
                    "ligne": node.lineno,
                    "module": self.alias[args[0].id],
                    "attribut": args[1].value,
                    "forme": "patch.object",
                }
            )
        for a in args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                m = re.match(r"^(veille_text|veille_collect)\.(\w+)$", a.value)
                if m:
                    self.chaines.append(
                        {
                            "ligne": node.lineno,
                            "module": m.group(1),
                            "attribut": m.group(2),
                            "forme": "patch('module.nom')",
                        }
                    )
        self.generic_visit(node)

    def visit_Tuple(self, node: ast.Tuple) -> None:
        # (veille_collect, "SOURCES_DIR", ...) dans une liste de patchs
        elts = node.elts
        if (
            len(elts) >= 2
            and isinstance(elts[0], ast.Name)
            and elts[0].id in self.alias
            and isinstance(elts[1], ast.Constant)
            and isinstance(elts[1].value, str)
        ):
            self.chaines.append(
                {
                    "ligne": node.lineno,
                    "module": self.alias[elts[0].id],
                    "attribut": elts[1].value,
                    "forme": "tuple(module, 'nom')",
                }
            )
        self.generic_visit(node)


def mesurer_importeurs() -> dict[str, Any]:
    fichiers = [f for f in git("ls-files", "--", "backend/*.py").splitlines() if f.endswith(".py")]
    resultats: list[dict[str, Any]] = []
    for rel in sorted(fichiers):
        chemin = RACINE / rel
        try:
            arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        v = _Visiteur()
        v.visit(arbre)
        if v.imports or v.chaines:
            resultats.append(
                {
                    "fichier": rel,
                    "test": "/tests/" in rel,
                    "imports": v.imports,
                    "attributs": sorted(
                        {(a["module"], a["attribut"], a["ecriture"]) for a in v.attributs}
                    ),
                    "patchs": v.chaines,
                }
            )
    # Noms utilisés par module (import from + attributs + patchs)
    noms: dict[str, Counter[str]] = {m: Counter() for m in MODULES}
    for r in resultats:
        for imp in r["imports"]:
            for n in imp["noms"]:
                noms[imp["module"]][n] += 1
        for mod, attr, _ in r["attributs"]:
            noms[mod][attr] += 1
        for p in r["patchs"]:
            noms[p["module"]][p["attribut"]] += 1
    par_module = {
        m: sorted({r["fichier"] for r in resultats for i in r["imports"] if i["module"] == m})
        for m in MODULES
    }
    # Importeurs de load_baselines / find_quote_in_any / normalize en particulier
    cibles = {
        "veille_text.normalize": ("veille_text", "normalize"),
        "veille_text.find_quote_in_any": ("veille_text", "find_quote_in_any"),
        "veille_collect.load_baselines": ("veille_collect", "load_baselines"),
    }
    par_cible: dict[str, list[str]] = {}
    for cle, (mod, nom) in cibles.items():
        par_cible[cle] = sorted(
            {
                f"{r['fichier']}:{i['ligne']}"
                for r in resultats
                for i in r["imports"]
                if i["module"] == mod and nom in i["noms"]
            }
            | {
                r["fichier"]
                for r in resultats
                if any(a[0] == mod and a[1] == nom for a in r["attributs"])
            }
        )
    # Importeurs hors git (autres sous-agents, copies de journaux) : comptés à part
    hors_git = []
    for p in sorted((BACKEND / "scripts" / "mesures").glob("*.py")) + sorted(
        (DATA / "reviews" / "logs").rglob("*.py")
    ):
        rel = str(p.relative_to(RACINE))
        if rel in fichiers:
            continue
        try:
            texte = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"\b(veille_text|veille_collect)\b", texte):
            hors_git.append(rel)
    sortie = {
        "fichiers_scannes": len(fichiers),
        "importeurs": resultats,
        "par_module": par_module,
        "par_cible": par_cible,
        "noms_utilises": {m: dict(noms[m].most_common()) for m in MODULES},
        "hors_git_mentionnant": hors_git,
    }
    ecrire("importeurs.json", sortie)

    md = ["# Importeurs de veille_text et veille_collect à HEAD (AST, fichiers suivis par git)", ""]
    md.append("| fichier | test | import (ligne, portée, noms) | attributs lus/écrits | patchs |")
    md.append("|---|---|---|---|---|")
    for r in resultats:
        imps = "; ".join(
            f"{i['module']}:{i['ligne']} [{i['portee']}] {','.join(i['noms']) or '(module)'}"
            for i in r["imports"]
        )
        attrs = ", ".join(f"{m}.{a}{' (écrit)' if w else ''}" for m, a, w in r["attributs"])
        patchs = ", ".join(f"{p['module']}.{p['attribut']}:{p['ligne']}" for p in r["patchs"])
        md.append(
            f"| {r['fichier']} | {'oui' if r['test'] else 'non'} | {imps} | {attrs} | {patchs} |"
        )
    md.append("")
    for cle, liste in par_cible.items():
        md.append(f"- {cle} : {len(liste)} importeur(s) : {', '.join(liste)}")
    ecrire("importeurs.md", "\n".join(md) + "\n")
    n_test = sum(1 for r in resultats if r["test"])
    note(
        f"importeurs veille_text/veille_collect : {len(resultats)} fichiers suivis "
        f"({n_test} tests, {len(resultats) - n_test} hors tests) ; "
        f"veille_text {len(par_module['veille_text'])}, veille_collect "
        f"{len(par_module['veille_collect'])} [importeurs.json]"
    )
    for cle, liste in par_cible.items():
        note(f"  {cle} : {len(liste)} importeur(s) [importeurs.json par_cible]")
    return sortie


# ---------------------------------------------------------------------------
# 2. Schéma : extra=forbid
# ---------------------------------------------------------------------------

AIDE_MIN: dict[str, Any] = {
    "slug": "essai",
    "nom": "Essai",
    "organisme": "Organisme",
    "categorie": "autre",
    "type": "subvention",
    "description": "x",
}


def _essai_cle(chemin: str, mutation) -> dict[str, Any]:
    import copy

    brut = copy.deepcopy(AIDE_MIN)
    mutation(brut)
    try:
        S.Aide.model_validate(brut)
        return {"niveau": chemin, "refuse": False, "erreur": None}
    except ValidationError as exc:
        e = exc.errors()[0]
        return {"niveau": chemin, "refuse": True, "erreur": f"{e['type']} @ {e['loc']}"}


def mesurer_schema() -> dict[str, Any]:
    import pieces_schema

    modeles = []
    for mod in (S, pieces_schema):
        for nom in dir(mod):
            obj = getattr(mod, nom)
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseModel)
                and obj.__module__ == mod.__name__
            ):
                modeles.append(
                    {
                        "module": mod.__name__,
                        "modele": nom,
                        "extra": obj.model_config.get("extra"),
                        "root": "root" in obj.model_fields,
                    }
                )
    cond = {"id": "c1", "text": "t", "kind": "info"}
    essais = [
        _essai_cle("aide", lambda b: b.update(cle_inconnue=1)),
        _essai_cle("source", lambda b: b.update(source={"x": 1})),
        _essai_cle("financement", lambda b: b.update(financement={"x": 1})),
        _essai_cle("cumul", lambda b: b.update(cumul={"x": 1})),
        _essai_cle("calendrier", lambda b: b.update(calendrier={"x": 1})),
        _essai_cle("hard_filters", lambda b: b.update(hard_filters={"x": 1})),
        _essai_cle("flags", lambda b: b.update(flags={"x": 1})),
        _essai_cle("conditions[]", lambda b: b.update(conditions=[{**cond, "x": 1}])),
        _essai_cle(
            "conditions[].applies_if",
            lambda b: b.update(
                conditions=[
                    {**cond, "applies_if": {"fact": "f", "predicate": {"eq": True}, "x": 1}}
                ]
            ),
        ),
        _essai_cle(
            "documents_requis[]", lambda b: b.update(documents_requis=[{"nom": "n", "x": 1}])
        ),
        _essai_cle("fiche", lambda b: b.update(fiche={"x": 1})),
        _essai_cle("fiche.essentiel", lambda b: b.update(fiche={"essentiel": {"x": 1}})),
        _essai_cle(
            "fiche.points.<id>",
            lambda b: b.update(fiche={"points": {"c1": {"titre": "t", "x": 1}}}),
        ),
        _essai_cle(
            "applies_if (aide)",
            lambda b: b.update(applies_if={"fact": "f", "predicate": {"eq": True}, "x": 1}),
        ),
        # Prédicat : un dict à clé unique, mais une clé inconnue de second niveau ?
        _essai_cle(
            "predicate à deux clés",
            lambda b: b.update(
                conditions=[
                    {
                        "id": "c1",
                        "text": "t",
                        "kind": "user_fact",
                        "effect": "gate",
                        "fact": "f",
                        "predicate": {"eq": True, "x": 1},
                    }
                ]
            ),
        ),
        _essai_cle(
            "predicate opérateur inconnu",
            lambda b: b.update(
                conditions=[
                    {
                        "id": "c1",
                        "text": "t",
                        "kind": "user_fact",
                        "effect": "gate",
                        "fact": "f",
                        "predicate": {"contains_any": ["a"]},
                    }
                ]
            ),
        ),
        _essai_cle(
            "none_in dans any_of",
            lambda b: b.update(
                conditions=[
                    {
                        "id": "c1",
                        "text": "t",
                        "kind": "user_fact",
                        "effect": "gate",
                        "fact": "f",
                        "predicate": {"any_of": [{"none_in": ["a"]}, {"eq": "b"}]},
                    }
                ]
            ),
        ),
        _essai_cle(
            "nom_court absent (accepté par le schéma ?)", lambda b: b.pop("nom_court", None)
        ),
    ]
    # Faits : clé inconnue dans un FactDef, une FactOption, un Levier
    essais_faits = []
    for niveau, brut in (
        ("FactDef", {"type": "boolean", "scope": "monument", "question": "q", "x": 1}),
        (
            "FactOption",
            {
                "type": "enum",
                "scope": "monument",
                "question": "q",
                "options": [{"id": "a", "label": "A", "x": 1}],
            },
        ),
        (
            "Levier",
            {
                "type": "boolean",
                "scope": "monument",
                "question": "q",
                "levier": {"resume": "r", "x": 1},
            },
        ),
        (
            "boolean sans oui",
            {
                "type": "boolean",
                "scope": "monument",
                "question": "q",
                "options": [{"id": "non", "label": "Non", "valeur": False}],
            },
        ),
    ):
        try:
            S.FactDef.model_validate(brut)
            essais_faits.append({"niveau": niveau, "refuse": False})
        except ValidationError as exc:
            essais_faits.append(
                {"niveau": niveau, "refuse": True, "erreur": str(exc.errors()[0]["msg"])[:160]}
            )
    sortie = {"modeles": modeles, "essais_aide": essais, "essais_faits": essais_faits}
    ecrire("schema.json", sortie)
    sans_forbid = [m["modele"] for m in modeles if m["extra"] != "forbid" and not m["root"]]
    note(
        f"schéma : {len(modeles)} modèles pydantic dans aides_schema+pieces_schema, "
        f"{sum(1 for m in modeles if m['extra'] == 'forbid')} en extra=forbid ; sans forbid : "
        f"{', '.join(sans_forbid) or 'aucun'} [schema.json]"
    )
    refuses = sum(1 for e in essais if e["refuse"])
    note(
        f"schéma : {refuses}/{len(essais)} essais de clé ou prédicat invalides refusés [schema.json]"
    )
    return sortie


# ---------------------------------------------------------------------------
# 3. Effet implicite selon le kind
# ---------------------------------------------------------------------------


def _cond(kind: str) -> dict[str, Any]:
    base: dict[str, Any] = {"id": "c1", "text": "t", "kind": kind}
    if kind == "user_fact":
        base.update(fact="f", predicate={"eq": True})
    elif kind == "auto":
        base.update(field="monument.protection", predicate={"eq": "classe"})
    return base


def mesurer_effet(aides_brutes: dict[str, dict]) -> dict[str, Any]:
    kinds = ["untyped", "auto", "user_fact", "discretionary", "info", "manual_check"]
    matrice: dict[str, dict[str, str]] = {}
    for k in kinds:
        ligne: dict[str, str] = {}
        try:
            ligne["(absent)"] = S.Condition.model_validate(_cond(k)).effect
        except ValidationError as exc:
            ligne["(absent)"] = "refus : " + exc.errors()[0]["msg"][:80]
        for eff in ("gate", "modulateur", "info"):
            try:
                ligne[eff] = S.Condition.model_validate({**_cond(k), "effect": eff}).effect
            except ValidationError as exc:
                ligne[eff] = "refus : " + exc.errors()[0]["msg"][:80]
        matrice[k] = ligne
    # Catalogue : effect présent dans le YAML brut ou non
    tally: Counter[tuple[str, str, bool]] = Counter()
    aides_mc_implicite: set[str] = set()
    for slug, brut in aides_brutes.items():
        for c in brut.get("conditions") or []:
            kind = c.get("kind", "untyped")
            explicite = "effect" in c
            effet = c.get("effect")
            if not explicite:
                effet = matrice.get(kind, {}).get("(absent)", "?")
            tally[(kind, effet, explicite)] += 1
            if kind == "manual_check" and not explicite:
                aides_mc_implicite.add(slug)
    lignes = [
        {"kind": k, "effect": e, "explicite": x, "n": n} for (k, e, x), n in sorted(tally.items())
    ]
    total = sum(tally.values())
    implicites = sum(n for (k, e, x), n in tally.items() if not x)
    gates_implicites = sum(n for (k, e, x), n in tally.items() if not x and e == "gate")
    mc_gate_impl = sum(
        n for (k, e, x), n in tally.items() if not x and e == "gate" and k == "manual_check"
    )
    sortie = {
        "matrice_schema": matrice,
        "catalogue": lignes,
        "total_conditions": total,
        "effect_absent": taux(implicites, total),
        "gates_implicites": gates_implicites,
        "manual_check_gate_implicites": mc_gate_impl,
        "aides_manual_check_sans_effect": sorted(aides_mc_implicite),
    }
    ecrire("effet_implicite.json", sortie)
    note(
        "effet implicite (schéma) : "
        + "; ".join(f"{k}→{v['(absent)']}" for k, v in matrice.items())
        + " [effet_implicite.json matrice_schema]"
    )
    note(
        f"catalogue : effect absent du YAML sur {implicites}/{total} conditions "
        f"(wilson {wilson(implicites, total)}), dont {gates_implicites} gates implicites et "
        f"{mc_gate_impl} manual_check gates implicites [effet_implicite.json]"
    )
    return sortie


# ---------------------------------------------------------------------------
# 4. Chargement du catalogue
# ---------------------------------------------------------------------------


def _ecrire_aide(
    dossier: Path, slug: str, extra: dict | None = None, texte: str | None = None
) -> None:
    import yaml

    if texte is None:
        brut = {**AIDE_MIN, "slug": slug, "nom_court": slug, **(extra or {})}
        texte = yaml.safe_dump(brut, allow_unicode=True, sort_keys=False)
    (dossier / f"{slug}.yaml").write_text(texte, encoding="utf-8")


def mesurer_chargement() -> dict[str, Any]:
    sortie: dict[str, Any] = {}
    # Réel
    S.load_all_aides.cache_clear()
    S.load_facts.cache_clear()
    S.load_pending_facts.cache_clear()
    t0 = time.perf_counter()
    aides = S.load_all_aides()
    t1 = time.perf_counter()
    facts = S.load_facts()
    pending = S.load_pending_facts()
    t2 = time.perf_counter()
    collisions = sorted(set(facts) & set(pending))
    union = {**facts, **pending}
    cites: dict[str, set[str]] = defaultdict(set)
    for slug, a in aides.items():
        if a.applies_if and a.applies_if.fact:
            cites[a.applies_if.fact].add(slug)
        for c in a.conditions:
            for f in (c.fact, c.levier, c.applies_if.fact if c.applies_if else None):
                if f:
                    cites[f].add(slug)
    pending_seuls = {f: sorted(s) for f, s in cites.items() if f in pending and f not in facts}
    absents = {f: sorted(s) for f, s in cites.items() if f not in union}
    aides_pending = sorted({s for ss in pending_seuls.values() for s in ss})
    echec = sorted(p.name for p in S.AIDES_DIR.glob("*.yaml.echec"))
    sortie["reel"] = {
        "aides": len(aides),
        "secondes_load_all_aides": round(t1 - t0, 3),
        "secondes_faits": round(t2 - t1, 3),
        "faits_facts_yaml": len(facts),
        "faits_pending": len(pending),
        "collisions_facts_pending": collisions,
        "faits_cites": len(cites),
        "faits_cites_seulement_pending": len(pending_seuls),
        "aides_citant_un_fait_pending": taux(len(aides_pending), len(aides)),
        "faits_cites_absents_des_deux": absents,
        "fichiers_yaml_echec": len(echec),
    }
    note(
        f"chargement réel : {len(aides)} aides en {t1 - t0:.2f} s ; facts.yaml {len(facts)} faits, "
        f"facts_pending {len(pending)} ; {len(pending_seuls)} faits cités ne sont qu'en pending, "
        f"cités par {len(aides_pending)}/{len(aides)} aides ; {len(absents)} faits cités absents "
        f"des deux [chargement.json reel]"
    )
    # Pannes provoquées
    essais: list[dict[str, Any]] = []
    TMP.mkdir(parents=True, exist_ok=True)

    def scenario(nom: str, preparer) -> None:
        dossier = TMP / f"aides-{nom}"
        dossier.mkdir(parents=True, exist_ok=True)
        _ecrire_aide(dossier, "saine")
        preparer(dossier)
        resultat: dict[str, Any] = {"scenario": nom}
        try:
            charge = S.load_all_aides(dossier)
            resultat.update(charge=True, slugs=sorted(charge))
            if "dupliquee" in charge:
                resultat["description_retenue"] = charge["dupliquee"].description
        except Exception as exc:  # noqa: BLE001
            resultat.update(charge=False, exception=type(exc).__name__, message=str(exc)[:240])
            # Une exception n'est pas mise en cache : chaque appel reparse tout.
            try:
                S.load_all_aides(dossier)
                resultat["second_appel"] = "chargé"
            except Exception as exc2:  # noqa: BLE001
                resultat["second_appel"] = f"relève {type(exc2).__name__}"
        essais.append(resultat)

    scenario("reference", lambda d: None)
    scenario("cle_inconnue", lambda d: _ecrire_aide(d, "fautive", {"cle_inconnue": 1}))
    scenario(
        "slug_different",
        lambda d: (d / "fautive.yaml").write_text(
            (d / "saine.yaml").read_text(encoding="utf-8").replace("slug: saine", "slug: autre"),
            encoding="utf-8",
        ),
    )
    scenario(
        "piece_id_inconnu",
        lambda d: _ecrire_aide(
            d, "fautive", {"documents_requis": [{"nom": "n", "piece_id": "piece_qui_n_existe_pas"}]}
        ),
    )
    scenario("yaml_syntaxe", lambda d: _ecrire_aide(d, "fautive", texte="slug: [fautive\n"))
    scenario("fichier_vide", lambda d: _ecrire_aide(d, "fautive", texte=""))
    scenario("liste_au_lieu_dun_objet", lambda d: _ecrire_aide(d, "fautive", texte="- a\n- b\n"))
    scenario(
        "yaml_echec_present",
        lambda d: (d / "fautive.yaml.echec").write_text("pas: [du yaml\n", encoding="utf-8"),
    )
    scenario(
        "fait_inconnu_cite",
        lambda d: _ecrire_aide(
            d,
            "fautive",
            {
                "conditions": [
                    {
                        "id": "c1",
                        "text": "t",
                        "kind": "user_fact",
                        "effect": "gate",
                        "fact": "fait_qui_n_existe_pas",
                        "predicate": {"eq": True},
                    }
                ]
            },
        ),
    )
    scenario(
        "champ_auto_hors_registre",
        lambda d: _ecrire_aide(
            d,
            "fautive",
            {
                "conditions": [
                    {
                        "id": "c1",
                        "text": "t",
                        "kind": "auto",
                        "effect": "gate",
                        "field": "monument.protecion",
                        "predicate": {"eq": "classe"},
                    }
                ]
            },
        ),
    )
    scenario(
        "cle_dupliquee",
        lambda d: _ecrire_aide(
            d,
            "dupliquee",
            texte=(
                "slug: dupliquee\nnom: N\nnom_court: N\norganisme: O\ncategorie: autre\n"
                "type: subvention\ndescription: premiere\ndescription: seconde\n"
            ),
        ),
    )
    scenario(
        "id_condition_double",
        lambda d: _ecrire_aide(
            d,
            "fautive",
            {
                "conditions": [
                    {"id": "c1", "text": "t", "kind": "info"},
                    {"id": "c1", "text": "u", "kind": "info"},
                ]
            },
        ),
    )
    scenario(
        "sous_dossier_ignore",
        lambda d: (d / "sous").mkdir(exist_ok=True) or _ecrire_aide(d / "sous", "cachee"),
    )
    sortie["pannes_provoquees"] = essais
    # Faits : facts.yaml invalide ; pending qui collisionne
    faits_essais = []
    dossier = TMP / "faits"
    dossier.mkdir(parents=True, exist_ok=True)
    f_invalide = dossier / "facts-invalide.yaml"
    f_invalide.write_text(
        "fait_a:\n  type: enum\n  scope: monument\n  question: q\n", encoding="utf-8"
    )
    try:
        S.load_facts(f_invalide)
        faits_essais.append({"scenario": "enum_sans_options", "charge": True})
    except Exception as exc:  # noqa: BLE001
        faits_essais.append(
            {
                "scenario": "enum_sans_options",
                "charge": False,
                "exception": type(exc).__name__,
                "message": str(exc)[:200],
            }
        )
    f_ok = dossier / "facts-ok.yaml"
    f_ok.write_text(
        "fait_a:\n  type: boolean\n  scope: monument\n  question: version approuvée\n",
        encoding="utf-8",
    )
    p_coll = dossier / "pending-collision.yaml"
    p_coll.write_text(
        "fait_a:\n  type: boolean\n  scope: monument\n  question: version en attente\n",
        encoding="utf-8",
    )
    fusion = {**S.load_facts(f_ok), **S.load_pending_facts(p_coll)}
    faits_essais.append(
        {
            "scenario": "pending_collisionne_facts",
            "charge": True,
            "question_servie": fusion["fait_a"].question,
            "note": "les appelants fusionnent {**facts, **pending} : la version en attente gagne",
        }
    )
    p_absent = dossier / "pending-absent.yaml"
    faits_essais.append({"scenario": "pending_absent", "resultat": S.load_pending_facts(p_absent)})
    sortie["faits"] = faits_essais
    ecrire("chargement.json", sortie)
    for e in essais:
        etat = "charge" if e.get("charge") else f"ÉCHEC {e.get('exception')}"
        note(f"  panne provoquée « {e['scenario']} » : {etat} [chargement.json pannes_provoquees]")
    return sortie


# ---------------------------------------------------------------------------
# 5. Fail-closed
# ---------------------------------------------------------------------------


def mesurer_fail_closed(facts: dict[str, S.FactDef]) -> dict[str, Any]:
    res: dict[str, Any] = {}
    enum_key = next(k for k, f in sorted(facts.items()) if f.type == "enum")
    multi_key = next(k for k, f in sorted(facts.items()) if f.type == "multi_enum")
    bool_key = next(k for k, f in sorted(facts.items()) if f.type == "boolean" and not f.options)
    bool_opts = [k for k, f in sorted(facts.items()) if f.type == "boolean" and f.options]
    unk = [(k, o.id) for k, f in sorted(facts.items()) if f.options for o in f.options if o.unknown]
    nulles = [
        (k, o.id)
        for k, f in sorted(facts.items())
        if f.type == "boolean" and f.options
        for o in f.options
        if o.valeur is None and not o.unknown
    ]
    na = E._normalize_answer
    cas = {
        "réponse None": na(facts[enum_key], None),
        "skip": na(facts[enum_key], "skip"),
        f"enum {enum_key} id inconnu": na(facts[enum_key], "option_inconnue"),
        f"multi {multi_key} ids inconnus": na(facts[multi_key], ["x", "y"]),
        f"multi {multi_key} vide": na(facts[multi_key], []),
        f"boolean implicite {bool_key} 'oui'": na(facts[bool_key], "oui"),
        f"boolean implicite {bool_key} 'peut-etre'": na(facts[bool_key], "peut-etre"),
        "fait absent de l'ontologie, réponse 'oui'": na(None, "oui"),
    }
    if unk:
        k, o = unk[0]
        cas[f"option unknown:true {k}.{o}"] = na(facts[k], o)
    if nulles:
        k, o = nulles[0]
        cas[f"boolean valeur null {k}.{o}"] = na(facts[k], o)
    res["normalize_answer"] = {k: repr(v) for k, v in cas.items()}
    res["options_unknown_au_catalogue"] = len(unk)
    res["booleens_a_options"] = len(bool_opts)
    res["options_booleennes_valeur_null"] = len(nulles)
    # Prédicats
    MV = S.MultiValue
    ep = S.evaluate_predicate
    res["evaluate_predicate"] = {
        "eq sur None": ep({"eq": True}, None),
        "eq True sur 'oui' (id brut)": ep({"eq": True}, "oui"),
        "neq cultuel sur {cultuel, activite_culturelle}": ep(
            {"neq": "cultuel"}, MV(("cultuel", "activite_culturelle"))
        ),
        "not_in [cultuel] sur {cultuel, activite_culturelle}": ep(
            {"not_in": ["cultuel"]}, MV(("cultuel", "activite_culturelle"))
        ),
        "none_in [cultuel] sur {cultuel, activite_culturelle}": ep(
            {"none_in": ["cultuel"]}, MV(("cultuel", "activite_culturelle"))
        ),
        "MultiValue vide": ep({"eq": "a"}, MV(())),
        "lt 1800 sur RangeValue(1401,1500)": ep({"lt": 1800}, S.RangeValue((1401, 1500))),
        "eq 1450 sur RangeValue(1401,1500)": ep({"eq": 1450}, S.RangeValue((1401, 1500))),
        "any_of(True, None)": ep({"any_of": [{"eq": 1}, {"eq": 2}]}, 1),
        "contains sur valeur non liste": ep({"contains": "a"}, "a"),
    }
    # Fait absent de l'ontologie : l'aide est-elle écartée par une réponse persistée ?
    aide_fantome = S.Aide.model_validate(
        {
            **AIDE_MIN,
            "slug": "fantome",
            "conditions": [
                {
                    "id": "c1",
                    "text": "t",
                    "kind": "user_fact",
                    "effect": "gate",
                    "fact": "fait_qui_n_existe_pas",
                    "predicate": {"eq": True},
                }
            ],
        }
    )
    monument = {"protection": "classe", "proprietaire": "public_commune"}
    try:
        r = E.run_deterministic_diagnostic(
            aides={"fantome": aide_fantome},
            facts=facts,
            monument=monument,
            population=1000,
            answers={"fait_qui_n_existe_pas": "oui"},
        )
        res["fait_absent_reponse_oui"] = {
            k: [
                {"statut": a.get("statut"), "elimineParReponse": a.get("elimineParReponse")}
                for a in v
            ]
            for k, v in r.items()
            if isinstance(v, list) and v and isinstance(v[0], dict)
        }
    except Exception as exc:  # noqa: BLE001
        res["fait_absent_reponse_oui"] = f"exception {type(exc).__name__}: {exc}"[:200]
    # hard_filters sur valeur inconnue
    hf_cas = {
        "protections": {"protections": ["classe"]},
        "proprietaires": {"proprietaires": ["public_commune"]},
        "regions": {"regions": [next(iter(S.REGION_LABELS))]},
        "departements": {"departements": ["88"]},
        "etats_conservation": {"etats_conservation": ["peril"]},
        "travaux": {"travaux": [next(iter(S.TRAVAUX_LABELS))]},
        "commune_max_population": {"commune_max_population": 2000},
    }
    hf_res = {}
    for nom, hf in hf_cas.items():
        try:
            aide = S.Aide.model_validate({**AIDE_MIN, "hard_filters": hf})
        except ValidationError as exc:
            hf_res[nom] = f"refus schéma : {exc.errors()[0]['msg']}"
            continue
        remplis, non = E._evaluate_hard_filters(aide, {}, None)
        hf_res[nom] = "élimine" if non else ("passe (rempli)" if remplis else "passe (ignoré)")
    res["hard_filters_valeur_inconnue"] = hf_res
    ecrire("fail_closed.json", res)
    note(
        "fail-closed : "
        + "; ".join(f"{k} → {v}" for k, v in res["normalize_answer"].items())
        + " [fail_closed.json]"
    )
    note(
        "hard_filters sur fiche vide : "
        + ", ".join(f"{k} {v}" for k, v in hf_res.items())
        + " [fail_closed.json]"
    )
    note(
        f"fait absent de l'ontologie + réponse « oui » : {res['fait_absent_reponse_oui']} [fail_closed.json]"
    )
    return res


# ---------------------------------------------------------------------------
# 6. Catalogue : conformité aux invariants
# ---------------------------------------------------------------------------


def mesurer_catalogue(
    aides: dict[str, S.Aide], facts: dict[str, S.FactDef], aides_brutes: dict[str, dict]
) -> dict[str, Any]:
    n = len(aides)
    conds = [(s, c) for s, a in aides.items() for c in a.conditions]
    kinds = Counter(c.kind for _, c in conds)
    untyped_aides = sorted({s for s, c in conds if c.kind == "untyped"})
    mc_gate = [(s, c.id) for s, c in conds if c.kind == "manual_check" and c.effect == "gate"]
    baseline = json.loads((DATA / "manual_check_baseline.json").read_text(encoding="utf-8"))
    base_gates = sum(v.get("gates", 0) for v in baseline.values())
    territoriales = [
        s
        for s, a in aides.items()
        if (champ := S.CATEGORIES_TERRITORIALES.get(a.categorie))
        and not getattr(a.hard_filters, champ)
    ]
    valo_sans_famille = [
        s for s, a in aides.items() if "valorisation_rayonnement" in a.raison and not a.familles
    ]
    nom_court_vide = [s for s, a in aides.items() if not (a.nom_court or "").strip()]
    sans_famille = [s for s, a in aides.items() if not a.familles]
    hf_travaux = [s for s, a in aides.items() if a.hard_filters.travaux]
    fiches = [s for s, a in aides.items() if a.fiche]
    porteur = [s for s, a in aides.items() if S.gate_porteur(a)]
    fail_open = [s for s, a in aides.items() if S.sans_rien_a_verifier(a)]
    suffixe2 = sorted(s for s in aides if re.search(r"-\d+$", s))
    # Conditions opposables sans citation
    opposables = [
        (s, c) for s, c in conds if c.effect in ("gate", "modulateur") and c.kind != "info"
    ]
    sans_quote = [(s, c.id) for s, c in opposables if not (c.quote or "").strip()]
    quotes = [(s, c) for s, c in conds if (c.quote or "").strip()]
    # FIELD_REGISTRY
    usage_field: Counter[str] = Counter()
    gates_jamais_resolus: list[tuple[str, str, str]] = []
    jamais = {"commune.programmes", "commune.eligible_detr", "commune.eligible_denormandie"}
    for s, c in conds:
        if c.kind == "auto" and c.field:
            usage_field[c.field] += 1
            if c.field in jamais and c.effect == "gate":
                gates_jamais_resolus.append((s, c.id, c.field))
        if c.applies_if and c.applies_if.field:
            usage_field[f"applies_if:{c.applies_if.field}"] += 1
            if c.applies_if.field in jamais:
                gates_jamais_resolus.append((s, c.id, "applies_if:" + c.applies_if.field))
    hors_registre = sorted(f for f in usage_field if f.split(":")[-1] not in S.FIELD_REGISTRY)
    # Prédicat `contains` sur monument.proprietaire
    contains_proprio = [
        (s, c.id)
        for s, c in conds
        if c.field == "monument.proprietaire"
        and c.predicate
        and any(op == "contains" for op, _ in S.predicate_leaves(c.predicate.root))
    ]
    cond_proprio = sum(1 for s, c in conds if c.field == "monument.proprietaire")
    # Style YAML : flux ou JSON, lus comme texte par plusieurs outils
    flux = []
    for p in sorted(S.AIDES_DIR.glob("*.yaml")):
        t = p.read_text(encoding="utf-8")
        if re.search(
            r"^\s*(-\s+)?(fact|levier|applies_if|predicate):\s*\{[^}]*\bfact\b", t, re.M
        ) or re.search(r"\{\s*['\"]?fact['\"]?\s*:", t):
            flux.append(p.stem)
    # Fiche : dernier bloc ?
    fiche_pas_derniere = []
    for slug, brut in aides_brutes.items():
        if "fiche" in brut and list(brut)[-1] != "fiche":
            fiche_pas_derniere.append(slug)
    # .yaml.echec
    echecs = sorted(S.AIDES_DIR.glob("*.yaml.echec"))
    avec_entete = [
        p.name
        for p in echecs
        if p.read_text(encoding="utf-8", errors="replace").startswith("# ÉCHEC D'INGESTION")
    ]
    sortie = {
        "aides": n,
        "conditions": len(conds),
        "kinds": dict(kinds),
        "untyped": {"conditions": kinds.get("untyped", 0), "aides": untyped_aides},
        "manual_check_gate": {"n": len(mc_gate), "liste": mc_gate, "baseline_total": base_gates},
        "territoriales_sans_hard_filter": territoriales,
        "valorisation_sans_familles": valo_sans_famille,
        "familles_vides": taux(len(sans_famille), n),
        "nom_court_vide": nom_court_vide,
        "hard_filters_travaux": taux(len(hf_travaux), n),
        "fiches": taux(len(fiches), n),
        "gate_porteur": taux(len(porteur), n),
        "sans_rien_a_verifier": fail_open,
        "slugs_suffixe_numerique": suffixe2,
        "opposables_sans_quote": {
            **taux(len(sans_quote), len(opposables)),
            "exemples": sans_quote[:30],
        },
        "conditions_avec_quote": len(quotes),
        "field_registry": {
            "chemins": len(S.FIELD_REGISTRY),
            "usage": dict(usage_field),
            "hors_registre_au_catalogue": hors_registre,
            "gates_sur_champs_jamais_alimentes": gates_jamais_resolus,
        },
        "proprietaire": {"conditions": cond_proprio, "contains": contains_proprio},
        "yaml_style_flux_sur_fact": flux,
        "fiche_pas_en_dernier_bloc": fiche_pas_derniere,
        "yaml_echec": {"fichiers": len(echecs), "avec_entete_worker": len(avec_entete)},
    }
    ecrire("catalogue.json", sortie)
    note(
        f"catalogue : {n} aides, {len(conds)} conditions ; untyped {kinds.get('untyped', 0)} "
        f"sur {len(untyped_aides)} aides ; manual_check gate {len(mc_gate)} (baseline {base_gates}) "
        f"[catalogue.json]"
    )
    note(
        f"catalogue : départ./région sans hard_filter {len(territoriales)} ; valorisation sans "
        f"familles {len(valo_sans_famille)} ; nom_court vide {len(nom_court_vide)} ; familles vides "
        f"{len(sans_famille)}/{n} ; hard_filters.travaux {len(hf_travaux)}/{n} ; fiches "
        f"{len(fiches)}/{n} ; gate porteur {len(porteur)}/{n} ; sans rien à vérifier "
        f"{len(fail_open)} [catalogue.json]"
    )
    note(
        f"catalogue : conditions gate/modulateur (hors info) sans quote {len(sans_quote)}/"
        f"{len(opposables)} (wilson {wilson(len(sans_quote), len(opposables))}) [catalogue.json]"
    )
    note(
        f"catalogue : FIELD_REGISTRY {len(S.FIELD_REGISTRY)} chemins ; champs hors registre "
        f"{hors_registre} ; gates sur champs jamais alimentés {len(gates_jamais_resolus)} ; "
        f"`contains` sur proprietaire {len(contains_proprio)}/{cond_proprio} [catalogue.json]"
    )
    note(
        f"catalogue : .yaml.echec {len(echecs)} dont {len(avec_entete)} avec en-tête du worker ; "
        f"slugs à suffixe numérique {len(suffixe2)} ; fiche hors dernier bloc "
        f"{len(fiche_pas_derniere)} ; YAML en flux sur fact {len(flux)} [catalogue.json]"
    )
    return sortie


# ---------------------------------------------------------------------------
# 7. Identifiants persistés
# ---------------------------------------------------------------------------


def mesurer_identifiants(aides: dict[str, S.Aide], facts: dict[str, S.FactDef]) -> dict[str, Any]:
    motif_fait = re.compile(r"^[a-z0-9_]+$")
    cles_hors_motif = sorted(k for k in facts if not motif_fait.match(k))
    noms_doubles = {
        s: [n for n, c in Counter(d.nom for d in a.documents_requis).items() if c > 1]
        for s, a in aides.items()
    }
    noms_doubles = {s: v for s, v in noms_doubles.items() if v}
    pieces = sum(len(a.documents_requis) for a in aides.values())
    # Clés de faits codées en dur dans le code servi (hors scripts et tests)
    code = sorted(
        [
            BACKEND / f
            for f in (
                "eligibility_engine.py",
                "aides_schema.py",
                "profils_questionnaire.py",
                "labels.py",
                "main.py",
            )
        ]
        + list((BACKEND / "services").glob("*.py"))
        + list((BACKEND / "routers").glob("*.py"))
    )
    en_dur: dict[str, set[str]] = defaultdict(set)
    for p in code:
        try:
            arbre = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for nd in ast.walk(arbre):
            if isinstance(nd, ast.Constant) and isinstance(nd.value, str) and nd.value in facts:
                en_dur[nd.value].add(str(p.relative_to(BACKEND)))
    # Clés de base : grep des migrations pour les tables clés slug
    migrations = sorted((RACINE / "supabase" / "migrations").glob("*.sql"))
    tables_slug = Counter()
    for m in migrations:
        t = m.read_text(encoding="utf-8", errors="replace")
        for table in (
            "dossiers",
            "aide_suivis",
            "aide_rappels_envoyes",
            "aides_veille_etat",
            "aides_retirees",
            "conditions_predicats",
            "faits_surcharges",
        ):
            if re.search(rf"create table (if not exists )?(public\.)?{table}\b", t, re.I):
                tables_slug[table] += 1
    sortie = {
        "slugs": len(aides),
        "cles_de_faits": len(facts),
        "cles_hors_motif": cles_hors_motif,
        "pieces_documents_requis": pieces,
        "noms_de_piece_en_double_dans_une_aide": noms_doubles,
        "cles_de_faits_en_dur": {k: sorted(v) for k, v in sorted(en_dur.items())},
        "tables_creees_dans_les_migrations": dict(tables_slug),
    }
    ecrire("identifiants.json", sortie)
    note(
        f"identifiants : {len(facts)} clés de faits (facts+pending), {len(cles_hors_motif)} hors "
        f"[a-z0-9_] ; {len(noms_doubles)} aides avec un nom de pièce en double ; "
        f"{len(en_dur)} clés de faits codées en dur dans le code servi [identifiants.json]"
    )
    return sortie


# ---------------------------------------------------------------------------
# 8. Citations
# ---------------------------------------------------------------------------


def mesurer_citations(aides: dict[str, S.Aide]) -> dict[str, Any]:
    t0 = time.perf_counter()
    statuts: Counter[str] = Counter()
    recon: Counter[str] = Counter()
    absentes: list[tuple[str, str]] = []
    masquees: list[tuple[str, str]] = []
    sans_doc: list[tuple[str, str]] = []
    aides_masquees: set[str] = set()
    aides_illisibles: set[str] = set()
    suffixes: Counter[str] = Counter()
    golden = []
    norm_h = hashlib.sha256()
    n_quotes = 0
    for slug in sorted(aides):
        aide = aides[slug]
        dossier = veille_collect.SOURCES_DIR / slug
        if dossier.is_dir():
            for p in dossier.iterdir():
                suffixes[
                    "".join(p.suffixes[-2:]).lower()
                    if p.name.endswith(".meta.yaml")
                    else p.suffix.lower()
                ] += 1
        docs, illisibles, _prov = veille_collect.load_baselines(slug)
        if illisibles:
            aides_illisibles.add(slug)
        abs_, deg, hors = check_quotes(aide, docs, illisibles)
        for c in aide.conditions:
            if not (c.quote or "").strip():
                continue
            n_quotes += 1
            q = c.quote or ""
            norm_h.update(f"{slug}\0{c.id}\0{veille_text.normalize(q)}\n".encode())
            nom, m = veille_text.find_quote_in_any(q, docs)  # type: ignore[arg-type]
            statuts[m.status] += 1
            if m.reconstitution:
                recon[m.reconstitution] += 1
            golden.append(
                {
                    "slug": slug,
                    "id": c.id,
                    "doc": nom,
                    "status": m.status,
                    "start": m.start,
                    "end": m.end,
                    "reconstitution": m.reconstitution,
                    "prefix_len": m.prefix_len,
                    "quote_len": m.quote_len,
                }
            )
        absentes += [(s, i) for s, i, _ in abs_]
        for s, i, _ in hors:
            if docs:
                masquees.append((s, i))
                aides_masquees.add(s)
            else:
                sans_doc.append((s, i))
    duree = time.perf_counter() - t0
    golden_txt = "".join(json.dumps(g, ensure_ascii=False, sort_keys=True) + "\n" for g in golden)
    ecrire("citations_golden.jsonl", golden_txt)
    ecrire(
        "normalize_golden.json",
        {
            "quotes": n_quotes,
            "sha256_normalize": norm_h.hexdigest(),
            "sha256_find_quote_in_any": hashlib.sha256(golden_txt.encode()).hexdigest(),
            "note": "empreintes à reproduire à l'identique après un déplacement des modules",
        },
    )
    trouvees = n_quotes - statuts["absente"]
    sortie = {
        "quotes": n_quotes,
        "secondes": round(duree, 1),
        "pdf": dict(_PDF_STATS),
        "statuts": dict(statuts),
        "reconstitutions": dict(recon),
        "trouvees": taux(trouvees, n_quotes),
        "absentes_en_erreur_si_mono_slug": {**taux(len(absentes), n_quotes), "liste": absentes},
        "absentes_masquees_par_pdf_illisible": {
            **taux(len(masquees), n_quotes),
            "aides": sorted(aides_masquees),
            "liste": masquees,
        },
        "aides_avec_pdf_illisible": sorted(aides_illisibles),
        "absentes_sans_aucun_snapshot": {**taux(len(sans_doc), n_quotes), "liste": sans_doc},
        "suffixes_dans_sources": dict(suffixes),
    }
    ecrire("citations.json", sortie)
    note(
        f"citations : {n_quotes} quotes ; trouvées {trouvees}/{n_quotes} (wilson "
        f"{wilson(trouvees, n_quotes)}) ; statuts {dict(statuts)} ; reconstitutions {dict(recon)} "
        f"[citations.json] ({duree:.0f} s, pdf {dict(_PDF_STATS)})"
    )
    note(
        f"citations : absentes qui seraient une erreur en mono-slug {len(absentes)} ; absentes "
        f"MASQUÉES par un PDF illisible {len(masquees)} sur {len(aides_masquees)} aides "
        f"({len(aides_illisibles)} aides ont un PDF illisible) ; absentes sans snapshot "
        f"{len(sans_doc)} [citations.json]"
    )
    note(f"citations : fichiers de sources par suffixe {dict(suffixes)} [citations.json]")
    return sortie


# ---------------------------------------------------------------------------
# 9. Tests gardiens (proxy : occurrences des symboles dans tests/)
# ---------------------------------------------------------------------------

SYMBOLES = [
    "extra_forbidden",
    "find_quote_in_any",
    "load_baselines",
    "normalize(",
    "check_quotes",
    "hors_portee",
    "illisibles",
    "_normalize_answer",
    "none_in",
    "MultiValue",
    "_evaluate_hard_filters",
    "OPTIONS_BOOLEEN_IMPLICITES",
    "FIELD_REGISTRY",
    "check_manual_check_ratchet",
    "check_portee_geographique",
    "check_famille_faire_vivre",
    "check_colonnes_non_nulles",
    "check_ecriture",
    "check_urls_partagees",
    "MAX_FAITS_PAR_AIDE",
    "ajouter_sous_verrou",
    "reecrire_sous_verrou",
    "_mettre_en_echec",
    "controler(",
    "declarer_hors_perimetre",
    "MAX_VERIFICATIONS",
    "modifiee_depuis_verification",
    "resoudre_snapshot",
    "Disjoncteur",
    "prompt_systeme",
    "retenir(",
    "indetermine(",
    "structure_ecarte",
    "STATUTS_TRANSITOIRES",
    "cout_inconnu",
    "surcharger_fait",
    "load_all_aides",
    "slug « ",
    "promesse",
    "facteur_arret_dur",
    "appels_identiques",
]


def mesurer_tests() -> dict[str, Any]:
    fichiers = sorted((BACKEND / "tests").glob("test_*.py"))
    textes = {p.name: p.read_text(encoding="utf-8") for p in fichiers}
    res = {}
    for sym in SYMBOLES:
        par = {n: t.count(sym) for n, t in textes.items() if sym in t}
        res[sym] = {"fichiers": len(par), "occurrences": sum(par.values()), "detail": par}
    ecrire("tests_gardiens.json", res)
    zero = [s for s, v in res.items() if v["fichiers"] == 0]
    note(f"tests : symboles absents de tests/ : {zero} [tests_gardiens.json]")
    return res


# ---------------------------------------------------------------------------
# 10. Divers : outils, prompt système, file d'attente
# ---------------------------------------------------------------------------


def mesurer_divers(aides: dict[str, S.Aide]) -> dict[str, Any]:
    res: dict[str, Any] = {}
    arbre = ast.parse((SCRIPTS / "ingestion" / "outils.py").read_text(encoding="utf-8"))
    outils = None
    for nd in ast.walk(arbre):
        if (
            isinstance(nd, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "outils" for t in nd.targets)
            and isinstance(nd.value, ast.ListComp)
        ):
            it = nd.value.generators[0].iter
            if isinstance(it, ast.Tuple):
                outils = [e.id for e in it.elts if isinstance(e, ast.Name)]
    res["outils_agent"] = outils
    try:
        from ingestion.contexte import prompt_systeme

        S.load_facts.cache_clear()
        S.load_pending_facts.cache_clear()
        texte = prompt_systeme(S.load_facts(), S.load_pending_facts())
        texte2 = prompt_systeme(S.load_facts(), S.load_pending_facts())
        res["prompt_systeme"] = {
            "caracteres": len(texte),
            "octets_utf8": len(texte.encode()),
            "identique_sur_deux_appels": texte == texte2,
            "sha256": hashlib.sha256(texte.encode()).hexdigest(),
        }
    except Exception as exc:  # noqa: BLE001
        res["prompt_systeme"] = f"indisponible : {type(exc).__name__}: {exc}"
    res["familles"] = len(S.FAMILLES)
    # File d'attente : statut ingere sans YAML
    import yaml

    fa = yaml.load(
        (DATA / "prospection" / "file-attente.yaml").read_text(encoding="utf-8"),
        Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader),
    )
    statuts = Counter(t.get("statut") for t in fa.values())
    ingere_sans = sorted(s for s, t in fa.items() if t.get("statut") == "ingere" and s not in aides)
    res["file_attente"] = {
        "taches": len(fa),
        "statuts": dict(statuts),
        "ingere_sans_yaml": len(ingere_sans),
        "liste": ingere_sans,
    }
    ecrire("divers.json", res)
    note(
        f"agent : {len(outils or [])} outils ; prompt système "
        f"{res['prompt_systeme']['caracteres'] if isinstance(res['prompt_systeme'], dict) else res['prompt_systeme']} "
        f"caractères ; familles {len(S.FAMILLES)} ; file d'attente {len(fa)} tâches, ingere sans "
        f"YAML {len(ingere_sans)} [divers.json]"
    )
    return res


def mesurer_complements(aides: dict[str, S.Aide], facts: dict[str, S.FactDef]) -> dict[str, Any]:
    """Compléments : formes des faits, porteur en neq, URL partagées, texte vs quote, .echec."""
    from lint_aides_data import check_urls_partagees
    from ontologie_regles import (
        MAX_CAR_LIBELLE_OPTION,
        booleen_a_seuil,
        libelles_trop_longs,
        polarites_suspectes,
        question_trop_longue,
    )

    res: dict[str, Any] = {}
    n = len(facts)
    q250 = sorted(k for k, f in facts.items() if question_trop_longue(f))
    q160 = sorted(k for k, f in facts.items() if question_trop_longue(f, maximum=160))
    longs = sorted(f"{k}.{o}" for k, f in facts.items() for o in libelles_trop_longs(f.options))
    seuils = sorted(k for k, f in facts.items() if f.type == "boolean" and booleen_a_seuil(k, f))
    polar = polarites_suspectes(facts)
    res["faits"] = {
        "n": n,
        "questions_sup_250": q250,
        "questions_sup_160": len(q160),
        "libelles_sup_max": {"max": MAX_CAR_LIBELLE_OPTION, "n": len(longs), "liste": longs[:20]},
        "booleens_a_seuil": seuils,
        "polarites_suspectes": polar,
    }
    # Gate porteur en neq / not_in
    neg = []
    for s, a in aides.items():
        for c in a.conditions:
            if c.fact == S.FAIT_PORTEUR and c.effect == "gate" and c.predicate:
                ops = {op for op, _ in S.predicate_leaves(c.predicate.root)}
                if ops & {"neq", "not_in", "none_in"}:
                    neg.append((s, c.id, sorted(ops)))
    gates_porteur = sum(
        1
        for a in aides.values()
        for c in a.conditions
        if c.fact == S.FAIT_PORTEUR and c.effect == "gate"
    )
    res["gate_porteur_negatif"] = {**taux(len(neg), gates_porteur), "liste": neg}
    # URL partagées (check_urls_partagees, non appelé par lint())
    groupes = check_urls_partagees(list(aides.values()))
    res["urls_partagees"] = {"groupes": len(groupes), "exemples": groupes[:10]}
    # text vs quote : le `text` est-il une sous-chaîne normalisée de la quote ?
    norm = veille_text.normalize
    avec = [
        (c.text, c.quote) for a in aides.values() for c in a.conditions if (c.quote or "").strip()
    ]
    contenu = sum(1 for tx, q in avec if norm(tx) and norm(tx) in norm(q or ""))
    res["text_dans_quote"] = taux(contenu, len(avec))
    # .yaml.echec : faits cités absents de l'ontologie
    ref = re.compile(r"\b(?:fact|levier):\s*['\"]?([A-Za-z0-9_]+)")
    echec_faits_absents = 0
    echec_concernes = 0
    for pth in sorted(S.AIDES_DIR.glob("*.yaml.echec")):
        cites = set(ref.findall(pth.read_text(encoding="utf-8", errors="replace")))
        absents = cites - set(facts)
        if absents:
            echec_concernes += 1
            echec_faits_absents += len(absents)
    total_echec = len(list(S.AIDES_DIR.glob("*.yaml.echec")))
    res["yaml_echec_citant_un_fait_absent"] = {
        **taux(echec_concernes, total_echec),
        "faits_absents_cumules": echec_faits_absents,
    }
    # Calendriers sans aucune date et non permanents
    res["calendrier_non_permanent_sans_date"] = sum(
        1
        for a in aides.values()
        if not a.calendrier.permanent
        and a.calendrier.date_ouverture is None
        and a.calendrier.date_limite is None
    )
    ecrire("complements.json", res)
    note(
        f"faits : {n} ; questions > 250 car. {len(q250)} ; > 160 car. {len(q160)} ; libellés > "
        f"{MAX_CAR_LIBELLE_OPTION} car. {len(longs)} ; booléens à seuil {len(seuils)} ; "
        f"polarités suspectes {len(polar)} [complements.json]"
    )
    note(
        f"gates porteur en neq/not_in/none_in : {len(neg)}/{gates_porteur} ; groupes d'URL "
        f"partagées {len(groupes)} ; `text` contenu dans sa quote {contenu}/{len(avec)} ; "
        f".yaml.echec citant un fait absent {echec_concernes}/{total_echec} [complements.json]"
    )
    return res


def mesurer_lint() -> dict[str, Any]:
    """Le lint global, appelé en processus (lecture seule, sans --update-baseline).

    `ratchet=True` lit `data/manual_check_baseline.json` sans l'écrire ; `quotes`
    reste à False : les citations sont mesurées à part (section 8).
    """
    from lint_aides_data import lint

    rapport = lint()
    res = {
        "ok": rapport.ok,
        "erreurs": rapport.erreurs,
        "avertissements": len(rapport.avertissements),
        "lignes": rapport.lignes,
    }
    ecrire("lint_global.json", res)
    note(
        f"lint global (en processus, sans --quotes) : ok={rapport.ok}, "
        f"{len(rapport.erreurs)} erreur(s), {len(rapport.avertissements)} avertissement(s) "
        "[lint_global.json]"
    )
    return res


# ---------------------------------------------------------------------------


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    note(f"HEAD {git('rev-parse', '--short', 'HEAD').strip()}, {time.strftime('%Y-%m-%d %H:%M')}")
    try:
        mesurer_importeurs()
        mesurer_schema()
        aides_brutes = {
            p.stem: S.charger_yaml(p.read_text(encoding="utf-8"))
            for p in sorted(S.AIDES_DIR.glob("*.yaml"))
        }
        mesurer_effet(aides_brutes)
        mesurer_chargement()
        S.load_all_aides.cache_clear()
        S.load_facts.cache_clear()
        S.load_pending_facts.cache_clear()
        aides = S.load_all_aides()
        facts = {**S.load_facts(), **S.load_pending_facts()}
        mesurer_fail_closed(facts)
        mesurer_catalogue(aides, facts, aides_brutes)
        mesurer_identifiants(aides, facts)
        mesurer_tests()
        mesurer_divers(aides)
        mesurer_lint()
        mesurer_complements(aides, facts)
        mesurer_citations(aides)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    ecrire("resume.txt", "\n".join(RESUME) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
