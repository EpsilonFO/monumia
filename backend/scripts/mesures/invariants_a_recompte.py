"""Recompte adverse de la note « invariants A » (contrat, ingestion, modèles).

Relecture du 2026-10-10. Recompte INDÉPENDANT : ce script ne réutilise pas
`invariants_a.py` ; il relit les YAML à la main, recalcule les citations avec
les fonctions servies (`veille_text`, `veille_collect`) et rejoue les pannes de
chargement dans un dossier temporaire.

Lecture seule sur le dépôt. Les seules écritures :
  - les sorties brutes sous data/reviews/logs/refonte/2026-10-10-invariants-a-recompte-1/ ;
  - un cache `pdftotext` TEMPORAIRE (copie des caches existants), jamais celui
    du dépôt : `veille_collect.PDFTEXT_CACHE_DIR` est redirigé avant tout appel.

Aucun appel réseau, aucun appel de modèle.

Lancer depuis backend/ :
    PYTHONDONTWRITEBYTECODE=1 uv run python scripts/mesures/invariants_a_recompte.py
"""

from __future__ import annotations

import ast
import contextlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

SORTIE = BACKEND / "data" / "reviews" / "logs" / "refonte" / "2026-10-10-invariants-a-recompte-1"
AIDES = BACKEND / "data" / "aides"
FACTS = BACKEND / "data" / "facts.yaml"
PENDING = BACKEND / "data" / "facts_pending.yaml"
FILE_ATTENTE = BACKEND / "data" / "prospection" / "file-attente.yaml"
NOTE = RACINE / "docs" / "refonte-pipeline" / "notes" / "invariants-a.md"
CARTO = RACINE / "docs" / "refonte-pipeline" / "cartographie"
CACHES_PDF = [
    BACKEND / ".cache" / "pdftotext",
    Path("/Users/felixollivier/monumia/backend/.cache/pdftotext"),
]


def wilson(k: int, n: int, z: float = 1.959964) -> dict:
    if n == 0:
        return {"k": k, "n": n, "p": None, "wilson95": None}
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    demi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {
        "k": k,
        "n": n,
        "p": round(p, 4),
        "wilson95": [round(centre - demi, 4), round(centre + demi, 4)],
    }


def ecrire(nom: str, data) -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / nom).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(RACINE), *args], capture_output=True, text=True, check=True
    ).stdout


# ---------------------------------------------------------------------------
# 1. Verdicts de la note et effectifs de la cartographie
# ---------------------------------------------------------------------------


def verdicts_note() -> dict:
    lignes = NOTE.read_text(encoding="utf-8").split("\n")
    rangs: list[tuple[str, str]] = []
    for ligne in lignes:
        m = re.match(r"\| ((?:C|I|M)[IP]\d+) \|", ligne)
        if m:
            cellules = [c.strip() for c in ligne.split("|")[1:-1]]
            rangs.append((cellules[0], cellules[2]))
    brut = Counter(v for _, v in rangs)

    def classe(v: str) -> str:
        if v.startswith("R"):
            return "refute"
        if v.startswith("C"):
            return "confirme"
        if v.startswith("N"):
            return "nuance"
        if v.startswith("H"):
            return "hors_code"
        return "non_verifie"

    par_classe = Counter(classe(v) for _, v in rangs)
    mixtes = {k: v for k, v in rangs if v not in ("C", "N", "R", "H")}

    carto = {}
    for nom in ("contrat.md", "ingestion.md", "modeles.md"):
        section = None
        compte: Counter = Counter()
        for ligne in (CARTO / nom).read_text(encoding="utf-8").split("\n"):
            if ligne.startswith("## "):
                section = ligne[3:].strip()
            elif section in ("Invariants", "Pièges") and ligne.startswith("- "):
                compte[section] += 1
        carto[nom] = dict(compte)
    return {
        "lignes_de_tableau": len(rangs),
        "verdicts_bruts": dict(brut),
        "par_classe": dict(par_classe),
        "verdicts_mixtes": mixtes,
        "puces_de_premier_niveau_cartographie": carto,
        "note": "contrat.md Invariants compte 26 puces dont 5 sous-règles d'écriture d'un fait "
        "écrites au premier niveau : 21 invariants.",
    }


# ---------------------------------------------------------------------------
# 2. Catalogue relu à la main (YAML brut) puis par le schéma
# ---------------------------------------------------------------------------


def lire_brut() -> dict[str, dict]:
    out = {}
    for p in sorted(AIDES.glob("*.yaml")):
        out[p.stem] = yaml.load(p.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
    return out


def catalogue(brut: dict[str, dict]) -> dict:
    from aides_schema import load_all_aides, load_facts, load_pending_facts

    aides = load_all_aides()
    faits = {**load_facts(), **load_pending_facts()}

    n_cond = 0
    sans_effect = Counter()
    effets = Counter()
    gm_total = gm_sans_quote = 0
    gm_sans_quote_liste = []
    porteur_ops = Counter()
    porteur_aides = set()
    porteur_neq_aides = set()
    jamais = []
    champs_jamais = {"commune.programmes", "commune.eligible_detr", "commune.eligible_denormandie"}
    for slug, raw in brut.items():
        aide = aides[slug]
        if aide.applies_if and aide.applies_if.field in champs_jamais:
            jamais.append({"slug": slug, "ou": "aide.applies_if", "field": aide.applies_if.field})
        for rc, c in zip(raw.get("conditions") or [], aide.conditions, strict=True):
            n_cond += 1
            assert rc["id"] == c.id
            if "effect" not in rc:
                sans_effect[(c.kind, c.effect)] += 1
            effets[(c.kind, c.effect)] += 1
            if c.effect in ("gate", "modulateur"):
                gm_total += 1
                if not (c.quote or "").strip():
                    gm_sans_quote += 1
                    gm_sans_quote_liste.append(f"{slug}/{c.id} {c.kind}/{c.effect}")
            if c.fact == "statut_juridique_porteur" and c.effect == "gate":
                op = next(iter(c.predicate.root)) if c.predicate is not None else None
                porteur_ops[op] += 1
                porteur_aides.add(slug)
                if op in ("neq", "not_in", "none_in"):
                    porteur_neq_aides.add(slug)
            if c.kind == "auto" and c.field in champs_jamais:
                jamais.append({"slug": slug, "ou": f"{c.id} auto/{c.effect}", "field": c.field})
            if c.applies_if and c.applies_if.field in champs_jamais:
                jamais.append(
                    {"slug": slug, "ou": f"{c.id}.applies_if", "field": c.applies_if.field}
                )
    gates = sum(v for (k, e), v in effets.items() if e == "gate")
    porteur_total = sum(porteur_ops.values())
    porteur_neq = sum(porteur_ops[o] for o in ("neq", "not_in", "none_in"))
    # aides avec gate porteur au sens `aides_schema.gate_porteur` (applies_if d'aide compris)
    from aides_schema import gate_porteur

    return {
        "aides": len(aides),
        "conditions": n_cond,
        "effets_effectifs": {f"{k}/{e}": v for (k, e), v in sorted(effets.items())},
        "gates_effectifs": gates,
        "sans_effect_dans_le_yaml": {f"{k}/{e}": v for (k, e), v in sorted(sans_effect.items())},
        "sans_effect_total": wilson(sum(sans_effect.values()), n_cond),
        "gates_implicites": sum(v for (k, e), v in sans_effect.items() if e == "gate"),
        "gates_implicites_sur_gates": wilson(
            sum(v for (k, e), v in sans_effect.items() if e == "gate"), gates
        ),
        "gate_ou_modulateur_sans_quote": wilson(gm_sans_quote, gm_total),
        "gate_ou_modulateur_sans_quote_liste": gm_sans_quote_liste,
        "gates_porteur_operateurs": dict(porteur_ops),
        "gates_porteur_neq_not_in_none_in": wilson(porteur_neq, porteur_total),
        "aides_avec_gate_porteur_condition": len(porteur_aides),
        "aides_avec_gate_porteur_neq": len(porteur_neq_aides),
        "aides_gate_porteur_au_sens_du_schema": sum(1 for a in aides.values() if gate_porteur(a)),
        "conditions_sur_champs_jamais_alimentes": jamais,
        "conditions_sur_champs_jamais_alimentes_aides": len({j["slug"] for j in jamais}),
        "faits_ontologie": len(faits),
        "fiches": sum(1 for r in brut.values() if r.get("fiche")),
    }


# ---------------------------------------------------------------------------
# 3. Citations
# ---------------------------------------------------------------------------


def citations(brut: dict[str, dict]) -> dict:
    import veille_collect
    from veille_text import find_quote_in_any, normalize

    tmp = Path(tempfile.mkdtemp(prefix="recompte-pdftotext-"))
    copies = 0
    for src in CACHES_PDF:
        if src.is_dir():
            for f in src.iterdir():
                if not (tmp / f.name).exists():
                    shutil.copy2(f, tmp / f.name)
                    copies += 1
    veille_collect.PDFTEXT_CACHE_DIR = tmp
    avant = {f.name for f in tmp.iterdir()}

    t0 = time.perf_counter()
    statuts = Counter()
    reconst = Counter()
    absentes_par_cas = Counter()
    masquees_aides = Counter()
    aides_illisibles = 0
    n = 0
    texte_dans_quote = quote_dans_texte = texte_egal = 0
    par_aide_absentes: dict[str, int] = {}
    enregistrements: dict[tuple[str, str], tuple] = {}
    for slug, raw in brut.items():
        docs, illisibles, _prov = veille_collect.load_baselines(slug)
        if illisibles:
            aides_illisibles += 1
        for c in raw.get("conditions") or []:
            q = c.get("quote")
            if not q:
                continue
            n += 1
            tn, qn = normalize(c.get("text") or ""), normalize(q)
            if tn and tn in qn:
                texte_dans_quote += 1
            if qn and qn in tn:
                quote_dans_texte += 1
            if tn == qn:
                texte_egal += 1
            _nom, m = find_quote_in_any(q, docs)
            statuts[m.status] += 1
            enregistrements[(slug, c["id"])] = (
                _nom,
                m.status,
                m.start,
                m.end,
                m.prefix_len,
                m.reconstitution,
            )
            if m.reconstitution:
                reconst[m.reconstitution] += 1
            if not m.found:
                par_aide_absentes[slug] = par_aide_absentes.get(slug, 0) + 1
                if not docs:
                    absentes_par_cas["sans_snapshot_exploitable"] += 1
                elif illisibles:
                    absentes_par_cas["masquee_par_pdf_illisible"] += 1
                    masquees_aides[slug] += 1
                else:
                    absentes_par_cas["erreur_en_mono_slug"] += 1
    duree = time.perf_counter() - t0
    nouveaux = {f.name for f in tmp.iterdir()} - avant
    trouvees = n - statuts["absente"]
    verifiables = (
        n
        - absentes_par_cas["sans_snapshot_exploitable"]
        - absentes_par_cas["masquee_par_pdf_illisible"]
    )
    shutil.rmtree(tmp, ignore_errors=True)
    # Comparaison citation par citation avec le fichier de référence du mesureur.
    golden = SORTIE.parent / "2026-10-10-invariants-a-1" / "citations_golden.jsonl"
    comparaison = None
    if golden.is_file():
        egal = diff = absent = 0
        exemples = []
        for ligne in golden.read_text(encoding="utf-8").splitlines():
            g = json.loads(ligne)
            mien = enregistrements.get((g["slug"], g["id"]))
            if mien is None:
                absent += 1
                continue
            sien = (
                g["doc"],
                g["status"],
                g["start"],
                g["end"],
                g["prefix_len"],
                g["reconstitution"],
            )
            if mien == sien:
                egal += 1
            else:
                diff += 1
                if len(exemples) < 5:
                    exemples.append({"cle": [g["slug"], g["id"]], "mien": mien, "sien": sien})
        comparaison = {
            "identiques": egal,
            "differentes": diff,
            "absentes_de_mon_calcul": absent,
            "exemples": exemples,
        }
    return {
        "comparaison_avec_citations_golden_du_mesureur": comparaison,
        "secondes": round(duree, 1),
        "cache_pdftotext_temporaire": {
            "fichiers_copies": copies,
            "extractions_neuves": len(nouveaux),
        },
        "citations": n,
        "statuts": dict(statuts),
        "reconstitutions": dict(reconst),
        "trouvees_sur_toutes": wilson(trouvees, n),
        "trouvees_sur_verifiables": wilson(trouvees, verifiables),
        "trouvees_hors_baseline_pdf": wilson(statuts["exacte"] + statuts["degradee"], n),
        "absentes_par_cas": dict(absentes_par_cas),
        "masquees_sur_toutes": wilson(absentes_par_cas["masquee_par_pdf_illisible"], n),
        "masquees_sur_absentes": wilson(
            absentes_par_cas["masquee_par_pdf_illisible"], statuts["absente"]
        ),
        "masquees_par_aide": dict(masquees_aides),
        "aides_avec_pdf_illisible": aides_illisibles,
        "aides_avec_absente": len(par_aide_absentes),
        "texte_contenu_dans_quote": wilson(texte_dans_quote, n),
        "quote_contenue_dans_texte": wilson(quote_dans_texte, n),
        "texte_egal_quote": wilson(texte_egal, n),
        "texte_et_quote_sans_inclusion": wilson(
            n - texte_dans_quote - quote_dans_texte + texte_egal, n
        ),
    }


# ---------------------------------------------------------------------------
# 4. Chargement : pannes rejouées et temps
# ---------------------------------------------------------------------------

SAINE = {
    "slug": "saine",
    "nom": "Aide saine",
    "nom_court": "Saine",
    "organisme": "X",
    "categorie": "etat_drac",
    "type": "subvention",
    "description": "d",
    "conditions": [{"id": "c1", "text": "t", "kind": "info"}],
}


def _dump(d) -> str:
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False)


def chargement() -> dict:
    import aides_schema
    from aides_schema import load_all_aides

    scen: dict[str, str | None] = {}
    fautive = dict(SAINE, slug="fautive")
    scen["temoin_sans_panne"] = None
    scen["cle_inconnue"] = _dump(dict(fautive, zz=1))
    scen["slug_different"] = _dump(dict(fautive, slug="autre"))
    scen["piece_id_inconnu"] = _dump(
        dict(fautive, documents_requis=[{"nom": "p", "piece_id": "zz_inexistante"}])
    )
    scen["syntaxe"] = "slug: [fautive\n"
    scen["fichier_vide"] = ""
    scen["liste"] = "- a\n- b\n"
    scen["id_condition_double"] = _dump(dict(fautive, conditions=SAINE["conditions"] * 2))
    scen["fait_inconnu"] = _dump(
        dict(
            fautive,
            conditions=[
                {
                    "id": "c1",
                    "text": "t",
                    "kind": "user_fact",
                    "fact": "zz_fait_inexistant",
                    "predicate": {"eq": True},
                }
            ],
        )
    )
    scen["champ_hors_registre"] = _dump(
        dict(
            fautive,
            conditions=[
                {
                    "id": "c1",
                    "text": "t",
                    "kind": "auto",
                    "field": "monument.protecion",
                    "predicate": {"eq": "classe"},
                }
            ],
        )
    )
    scen["cle_dupliquee"] = _dump(fautive) + "description: seconde\n"
    scen["kind_inconnu"] = _dump(
        dict(fautive, conditions=[{"id": "c1", "text": "t", "kind": "zz"}])
    )
    scen["effect_gate_sur_info"] = _dump(
        dict(fautive, conditions=[{"id": "c1", "text": "t", "kind": "info", "effect": "gate"}])
    )
    scen["encodage_latin1"] = None  # traité à part
    res = {}
    for nom, contenu in scen.items():
        d = Path(tempfile.mkdtemp(prefix="recompte-chargement-"))
        (d / "saine.yaml").write_text(_dump(SAINE), encoding="utf-8")
        if nom == "encodage_latin1":
            (d / "fautive.yaml").write_bytes(_dump(dict(fautive, nom="Église")).encode("latin-1"))
        elif contenu is not None:
            (d / "fautive.yaml").write_text(contenu, encoding="utf-8")
        load_all_aides.cache_clear()
        try:
            charge = load_all_aides(d)
            res[nom] = {"leve": False, "slugs": sorted(charge)}
            if nom == "cle_dupliquee":
                res[nom]["description"] = charge["fautive"].description
        except Exception as exc:  # noqa: BLE001
            res[nom] = {"leve": True, "exception": type(exc).__name__}
        shutil.rmtree(d, ignore_errors=True)
    load_all_aides.cache_clear()

    # Temps : 5 chargements à froid du vrai catalogue.
    temps = []
    for _ in range(5):
        load_all_aides.cache_clear()
        t0 = time.perf_counter()
        load_all_aides()
        temps.append(round(time.perf_counter() - t0, 3))

    # Une erreur interrompt-elle le parcours au premier fichier fautif ?
    # Copie du catalogue réel + une fautive en tête (« 000-… ») ou en queue (« zzz-… »).
    position = {}
    for nom in ("000-fautive", "zzz-fautive"):
        d = Path(tempfile.mkdtemp(prefix="recompte-position-"))
        for p in AIDES.glob("*.yaml"):
            shutil.copy2(p, d / p.name)
        (d / f"{nom}.yaml").write_text(_dump(dict(SAINE, slug=nom, zz=1)), encoding="utf-8")
        load_all_aides.cache_clear()
        t0 = time.perf_counter()
        try:
            load_all_aides(d)
            leve = False
        except Exception:  # noqa: BLE001
            leve = True
        position[nom] = {"leve": leve, "secondes": round(time.perf_counter() - t0, 3)}
        # second appel : l'exception n'est pas mise en cache
        t0 = time.perf_counter()
        with contextlib.suppress(Exception):
            load_all_aides(d)
        position[nom]["second_appel_secondes"] = round(time.perf_counter() - t0, 3)
        shutil.rmtree(d, ignore_errors=True)
    load_all_aides.cache_clear()
    pannes = [k for k in res if k != "temoin_sans_panne"]
    _ = aides_schema
    return {
        "scenarios": res,
        "pannes_rejouees": len(pannes),
        "pannes_qui_levent": sum(1 for k in pannes if res[k]["leve"]),
        "temps_chargement_reel_s": temps,
        "position_du_fichier_fautif": position,
    }


# ---------------------------------------------------------------------------
# 5. Importeurs (AST sur les fichiers suivis)
# ---------------------------------------------------------------------------

CIBLES = ("normalize", "find_quote_in_any", "load_baselines")


def importeurs() -> dict:
    fichiers = [f for f in git("ls-files", "backend").split("\n") if f.endswith(".py")]
    par_fichier: dict[str, dict] = {}
    for f in fichiers:
        chemin = RACINE / f
        try:
            arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        modules = set()
        noms: set[str] = set()
        alias_module: dict[str, str] = {}
        for node in ast.walk(arbre):
            if isinstance(node, ast.ImportFrom) and node.module:
                base = node.module.split(".")[-1]
                if base in ("veille_text", "veille_collect"):
                    modules.add(base)
                    for a in node.names:
                        noms.add(f"{base}.{a.name}")
            elif isinstance(node, ast.Import):
                for a in node.names:
                    base = a.name.split(".")[-1]
                    if base in ("veille_text", "veille_collect"):
                        modules.add(base)
                        alias_module[a.asname or a.name] = base
        # usages par attribut : veille_collect.load_baselines
        if alias_module:
            for node in ast.walk(arbre):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in alias_module
                ):
                    noms.add(f"{alias_module[node.value.id]}.{node.attr}")
        # importlib / chaînes (mock.patch("veille_collect.X"))
        texte = chemin.read_text(encoding="utf-8")
        for m in re.finditer(r"[\"'](veille_(?:text|collect))\.(\w+)[\"']", texte):
            noms.add(f"{m.group(1)}.{m.group(2)}")
            modules.add(m.group(1))
        if modules:
            par_fichier[f.removeprefix("backend/")] = {
                "modules": sorted(modules),
                "noms": sorted(noms),
            }
    tests = [f for f in par_fichier if f.startswith("tests/")]
    par_cible = {}
    for cible in CIBLES:
        mod = "veille_collect" if cible == "load_baselines" else "veille_text"
        par_cible[cible] = sorted(
            f for f, v in par_fichier.items() if f"{mod}.{cible}" in v["noms"]
        )
    # dépendance indirecte par lint_aides_data
    indirect = []
    for f in fichiers:
        t = (RACINE / f).read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\s*(from lint_aides_data import|import lint_aides_data)", t, re.M) or (
            "from scripts.lint_aides_data" in t
        ):
            indirect.append(f.removeprefix("backend/"))
    return {
        "fichiers": len(par_fichier),
        "tests": len(tests),
        "hors_tests": len(par_fichier) - len(tests),
        "par_fichier": par_fichier,
        "par_cible": {k: {"n": len(v), "fichiers": v} for k, v in par_cible.items()},
        "importeurs_de_lint_aides_data": sorted(indirect),
    }


# ---------------------------------------------------------------------------
# 6. Modèles pydantic
# ---------------------------------------------------------------------------


def modeles() -> dict:
    fichiers = [f for f in git("ls-files", "backend").split("\n") if f.endswith(".py")]
    out = []
    for f in fichiers:
        if "/tests/" in f or f.startswith("backend/tests/"):
            continue
        texte = (RACINE / f).read_text(encoding="utf-8")
        try:
            arbre = ast.parse(texte)
        except SyntaxError:
            continue
        for node in arbre.body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [ast.unparse(b) for b in node.bases]
            if not any("BaseModel" in b or "RootModel" in b for b in bases):
                continue
            extra = None
            for st in node.body:
                if isinstance(st, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "model_config" for t in st.targets
                ):
                    m = re.search(r"extra=['\"](\w+)['\"]", ast.unparse(st.value))
                    extra = m.group(1) if m else "defaut"
            out.append(
                {
                    "fichier": f.removeprefix("backend/"),
                    "classe": node.name,
                    "bases": bases,
                    "extra": extra
                    or ("root" if any("RootModel" in b for b in bases) else "defaut"),
                }
            )
    schema = [m for m in out if m["fichier"] in ("aides_schema.py", "pieces_schema.py")]
    hors_routers = [m for m in out if not m["fichier"].startswith("routers/")]
    return {
        "aides_schema_et_pieces_schema": {
            "n": len(schema),
            "par_extra": dict(Counter(m["extra"] for m in schema)),
        },
        "hors_routers": {
            "n": len(hors_routers),
            "par_extra": dict(Counter(m["extra"] for m in hors_routers)),
        },
        "non_forbid_hors_routers": [
            f"{m['fichier']}:{m['classe']} ({m['extra']})"
            for m in hors_routers
            if m["extra"] not in ("forbid",)
        ],
        "tous": out,
    }


# ---------------------------------------------------------------------------
# 7. Clés de faits en dur dans le code servi
# ---------------------------------------------------------------------------


def faits_en_dur() -> dict:
    cles = set(yaml.load(FACTS.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)) | set(
        yaml.load(PENDING.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader) or {}
    )
    fichiers = [
        f
        for f in git("ls-files", "backend").split("\n")
        if f.endswith(".py")
        and (
            re.fullmatch(r"backend/[^/]+\.py", f)
            or f.startswith("backend/routers/")
            or f.startswith("backend/services/")
        )
    ]
    trouvees: dict[str, set] = defaultdict(set)
    for f in fichiers:
        arbre = ast.parse((RACINE / f).read_text(encoding="utf-8"))
        for node in ast.walk(arbre):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value in cles
            ):
                trouvees[node.value].add(f.removeprefix("backend/"))
    return {
        "cles_ontologie": len(cles),
        "cles_en_litteral_exact": len(trouvees),
        "detail": {k: sorted(v) for k, v in sorted(trouvees.items())},
    }


# ---------------------------------------------------------------------------
# 8. .yaml.echec et file d'attente
# ---------------------------------------------------------------------------


def echecs() -> dict:
    cles = set(yaml.load(FACTS.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)) | set(
        yaml.load(PENDING.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader) or {}
    )
    fichiers = sorted(AIDES.glob("*.yaml.echec"))
    avec_entete = 0
    citant_absent = 0
    citant_absent_parse = 0
    illisibles = 0
    sans_fait = 0
    for p in fichiers:
        t = p.read_text(encoding="utf-8")
        if t.startswith("# ÉCHEC D'INGESTION"):
            avec_entete += 1
        cites = set(re.findall(r"^\s*(?:-\s*)?(?:fact|levier):\s*['\"]?([A-Za-z0-9_]+)", t, re.M))
        if not cites:
            sans_fait += 1
        if cites - cles:
            citant_absent += 1
        try:
            d = yaml.load(t, Loader=yaml.CSafeLoader)
        except yaml.YAMLError:
            illisibles += 1
            continue
        refs = set()
        for c in (d or {}).get("conditions") or []:
            if isinstance(c, dict):
                if c.get("fact"):
                    refs.add(c["fact"])
                if c.get("levier"):
                    refs.add(c["levier"])
                ai = c.get("applies_if")
                if isinstance(ai, dict) and ai.get("fact"):
                    refs.add(ai["fact"])
        ai = (d or {}).get("applies_if")
        if isinstance(ai, dict) and ai.get("fact"):
            refs.add(ai["fact"])
        if refs - cles:
            citant_absent_parse += 1
    n = len(fichiers)
    return {
        "fichiers": n,
        "avec_entete_worker": avec_entete,
        "citant_un_fait_absent_regex": wilson(citant_absent, n),
        "citant_un_fait_absent_yaml_parse": wilson(citant_absent_parse, n),
        "illisibles_en_yaml": illisibles,
        "sans_aucun_fait_cite": sans_fait,
    }


def file_attente() -> dict:
    d = yaml.load(FILE_ATTENTE.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
    statuts = Counter(v.get("statut") for v in d.values())
    ingere = [k for k, v in d.items() if v.get("statut") == "ingere"]
    sans_yaml = [k for k in ingere if not (AIDES / f"{k}.yaml").exists()]
    avec_echec = [k for k in sans_yaml if (AIDES / f"{k}.yaml.echec").exists()]
    return {
        "taches": len(d),
        "statuts": dict(statuts),
        "ingere_sans_yaml": len(sans_yaml),
        "dont_avec_yaml_echec": len(avec_echec),
        "sans_yaml_ni_echec": sorted(set(sans_yaml) - set(avec_echec)),
        "taux_sur_ingere": wilson(len(sans_yaml), len(ingere)),
    }


# ---------------------------------------------------------------------------
# 9. Prompt système de l'ingestion
# ---------------------------------------------------------------------------


def prompt() -> dict:
    import hashlib

    from ingestion.contexte import estimer_jetons, prompt_systeme

    from aides_schema import load_facts, load_pending_facts

    facts = dict(load_facts())
    pending = dict(load_pending_facts())
    a = prompt_systeme(facts, pending)
    b = prompt_systeme(dict(facts), dict(pending))
    return {
        "caracteres": len(a),
        "identique": a == b,
        "sha256": hashlib.sha256(a.encode()).hexdigest(),
        "estimer_jetons_du_code": estimer_jetons(a),
        "jetons_a_4_car": round(len(a) / 4),
        "jetons_a_3_5_car": round(len(a) / 3.5),
    }


def lint_et_fail_closed(masquees: list[str]) -> dict:
    """Lint en processus (lecture seule) et essai du fail-closed sur un fait absent."""
    import veille_collect

    tmp = Path(tempfile.mkdtemp(prefix="recompte-pdftotext-lint-"))
    for src in CACHES_PDF:
        if src.is_dir():
            for f in src.iterdir():
                if not (tmp / f.name).exists():
                    shutil.copy2(f, tmp / f.name)
    veille_collect.PDFTEXT_CACHE_DIR = tmp
    from lint_aides_data import lint

    from aides_schema import evaluate_predicate
    from eligibility_engine import _normalize_answer

    out = {}
    r = lint()
    out["global"] = {"ok": r.ok, "erreurs": len(r.erreurs), "avertissements": len(r.avertissements)}
    r = lint(strict=True)
    out["global_strict"] = {"ok": r.ok, "erreurs": len(r.erreurs)}
    r = lint(quotes=True)
    out["global_quotes"] = {
        "ok": r.ok,
        "erreurs": len(r.erreurs),
        "absentes": len(r.quotes_absentes),
        "hors_portee": len(r.quotes_hors_portee),
    }
    mono = {}
    for slug in masquees:
        r = lint([slug], quotes=True)
        mono[slug] = {
            "ok": r.ok,
            "erreurs_de_citation": sum(1 for e in r.erreurs if "quote introuvable" in e),
            "erreurs": len(r.erreurs),
            "hors_portee": len(r.quotes_hors_portee),
        }
    out["mono_slug_quotes_sur_les_aides_masquees"] = mono
    brute = _normalize_answer(None, "oui")
    out["fait_absent"] = {
        "_normalize_answer(None, 'oui')": brute,
        "evaluate_predicate({'eq': True}, valeur)": evaluate_predicate({"eq": True}, brute),
    }
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    resume = {}
    resume["verdicts"] = verdicts_note()
    ecrire("verdicts.json", resume["verdicts"])
    brut = lire_brut()
    resume["catalogue"] = catalogue(brut)
    ecrire("catalogue.json", resume["catalogue"])
    resume["modeles"] = modeles()
    ecrire("modeles.json", resume["modeles"])
    resume["importeurs"] = importeurs()
    ecrire("importeurs.json", resume["importeurs"])
    resume["faits_en_dur"] = faits_en_dur()
    ecrire("faits_en_dur.json", resume["faits_en_dur"])
    resume["echecs"] = echecs()
    ecrire("echecs.json", resume["echecs"])
    resume["file_attente"] = file_attente()
    ecrire("file_attente.json", resume["file_attente"])
    resume["prompt"] = prompt()
    ecrire("prompt.json", resume["prompt"])
    resume["chargement"] = chargement()
    ecrire("chargement.json", resume["chargement"])
    resume["citations"] = citations(brut)
    ecrire("citations.json", resume["citations"])
    resume["lint"] = lint_et_fail_closed(sorted(resume["citations"]["masquees_par_aide"]))
    ecrire("lint.json", resume["lint"])
    resume["head"] = git("rev-parse", "HEAD").strip()
    print(
        json.dumps({k: v for k, v in resume.items() if k != "modeles"}, ensure_ascii=False)[:6000]
    )


if __name__ == "__main__":
    main()
