"""Recompte adverse des comptes figés (note docs/refonte-pipeline/notes/comptes-figes.md).

Lecture seule : aucun appel réseau, aucun appel de modèle, aucun script du
pipeline exécuté. Les modules du pipeline sont seulement importés, pour lire
leurs constantes et assembler des prompts à partir de fichiers.

Ne réutilise PAS le script du mesureur (comptes_figes.py) : chaque compte est
refait ici par un autre chemin (AST, tokenize, YAML relu, pydantic).

    cd backend && uv run python scripts/mesures/comptes_figes_recompte.py

Écrit seulement dans data/reviews/logs/refonte/2026-10-10-comptes-figes-recompte-1/.
"""

from __future__ import annotations

import ast
import fnmatch
import io
import json
import math
import sys
import tokenize
from collections import Counter
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
SCRIPTS = BACKEND / "scripts"
TESTS = BACKEND / "tests"
DATA = BACKEND / "data"
AIDES = DATA / "aides"
SORTIE = DATA / "reviews" / "logs" / "refonte" / "2026-10-10-comptes-figes-recompte-1"

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(SCRIPTS))

OUTILS = [
    "benchmark_destinataire",
    "comparer_aides",
    "lint_aides_data",
    "ontologie_regles",
    "auditer_ontologie",
    "auditer_raisons",
    "dedoublonner_aides",
    "faits_orphelins",
    "fusionner_faits",
    "retyper_faits",
    "mesure_questionnaire",
]


def groupes() -> dict[str, list[Path]]:
    s = SCRIPTS
    return {
        "prospection": sorted(s.glob("prospection/*.py"))
        + [s / "prospecter.py", s / "balayage.py"],
        "ingestion": sorted(s.glob("ingestion/*.py")) + [s / "ingerer.py", s / "rediger_fiches.py"],
        "socle": sorted(s.glob("pipeline/*.py")) + [s / "snapshot_source.py"],
        "veille": sorted(s.glob("veille_*.py")),
        "outils": [s / f"{n}.py" for n in OUTILS],
    }


def wilson(k: int, n: int, z: float = 1.96) -> dict[str, float]:
    if n == 0:
        return {"k": k, "n": n, "p": float("nan"), "bas": float("nan"), "haut": float("nan")}
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {"k": k, "n": n, "p": round(p, 4), "bas": round(c - h, 4), "haut": round(c + h, 4)}


def nb_lignes(p: Path) -> int:
    return p.read_bytes().count(b"\n")


def decoupe_lignes(p: Path) -> dict[str, int]:
    """Lignes vides, commentaires, docstrings et reste (code), par tokenize et AST."""
    src = p.read_text(encoding="utf-8")
    lignes = src.split("\n")
    if src.endswith("\n"):
        lignes = lignes[:-1]
    doc: set[int] = set()
    for n in ast.walk(ast.parse(src)):
        porteur = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        if isinstance(n, porteur) and n.body and isinstance(n.body[0], ast.Expr):
            v = n.body[0].value
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                doc.update(range(n.body[0].lineno, (n.body[0].end_lineno or 0) + 1))
    com = {
        t.start[0]
        for t in tokenize.generate_tokens(io.StringIO(src).readline)
        if t.type == tokenize.COMMENT
    }
    r = Counter()
    for i, ligne in enumerate(lignes, 1):
        s = ligne.strip()
        if not s:
            r["vides"] += 1
        elif i in doc:
            r["docstrings"] += 1
        elif i in com and s.startswith("#"):
            r["commentaires"] += 1
        else:
            r["code"] += 1
    r["total"] = len(lignes)
    return dict(r)


def code() -> dict:
    out: dict = {"groupes": {}, "fichiers": {}}
    tot = Counter()
    for g, fichiers in groupes().items():
        c = Counter()
        for p in fichiers:
            d = decoupe_lignes(p)
            assert d["total"] == nb_lignes(p), p
            out["fichiers"][str(p.relative_to(BACKEND))] = d
            c.update(d)
            c["fichiers"] += 1
        out["groupes"][g] = dict(c)
        tot.update(c)
    out["total"] = dict(tot)
    return out


def modules_perimetre() -> set[str]:
    mods: set[str] = set()
    for fichiers in groupes().values():
        for p in fichiers:
            r = p.relative_to(SCRIPTS).with_suffix("")
            parts = [x for x in r.parts if x != "__init__"]
            mods.add(".".join(parts))
            mods.add(parts[0])
    return mods


def imports(p: Path) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            out.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            out.add(n.module)
    return out


def tests() -> dict:
    mods = modules_perimetre()
    motifs = [
        "test_veille_*",
        "test_ingestion_*",
        "test_pipeline_*",
        "test_prospection.py",
        "test_balayage.py",
        "test_lint_aides_data.py",
        "test_ontologie_regles.py",
        "test_fusionner_faits.py",
        "test_retyper_faits.py",
        "test_faits_durables*.py",
    ]
    retenus, mentions = {}, {}
    for p in sorted(TESTS.rglob("test_*.py")):
        par_motif = any(fnmatch.fnmatch(p.name, m) for m in motifs)
        imp = sorted(m for m in imports(p) if m in mods or m.split(".")[0] in mods)
        if par_motif or imp:
            retenus[p.name] = {"lignes": nb_lignes(p), "motif": par_motif, "imports": imp}
        else:
            src = p.read_text(encoding="utf-8")
            cites = sorted(m for m in mods if "." not in m and f"{m}.py" in src)
            if cites:
                mentions[p.name] = {"lignes": nb_lignes(p), "cite_sans_importer": cites}
    hors_test = [
        str(p.relative_to(BACKEND))
        for p in BACKEND.rglob("test_*.py")
        if ".venv" not in p.parts and TESTS not in p.parents
    ]
    return {
        "fichiers": len(retenus),
        "lignes": sum(v["lignes"] for v in retenus.values()),
        "detail": retenus,
        "sans_import_du_perimetre": sorted(k for k, v in retenus.items() if not v["imports"]),
        "citent_sans_importer": mentions,
        "tests_hors_backend_tests": hors_test,
    }


def cli() -> dict:
    lignes = {}
    for fichiers in groupes().values():
        for p in fichiers:
            src = p.read_text(encoding="utf-8")
            if '"__main__"' not in src and "'__main__'" not in src:
                continue
            n = cachees = 0
            for node in ast.walk(ast.parse(src)):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_argument"
                ):
                    n += 1
                    for k in node.keywords:
                        v = k.value
                        if (
                            k.arg == "help"
                            and isinstance(v, ast.Attribute)
                            and v.attr == "SUPPRESS"
                        ):
                            cachees += 1
            lignes[str(p.relative_to(SCRIPTS))] = {
                "add_argument": n,
                "cachees": cachees,
                "lit_sys_argv": "sys.argv" in src,
            }
    # Sous-commandes par dispatch maison, relevées à la main dans le code :
    sous = {
        "prospecter.py": "SOUS_COMMANDES, prospecter.py:870-878 (7)",
        "comparer_aides.py": "argv[0] == 'tableau', comparer_aides.py:625 (1)",
        "veille_benchmark_jev.py": "positionnel action choices preparer/juger/rapport, :636 (3)",
    }
    import prospecter

    effectives = {
        nom: len([a for a in fab()._actions if a.dest != "help"])
        for nom, (fab, _) in prospecter.SOUS_COMMANDES.items()
    }
    effectives["(principal)"] = len(
        [a for a in prospecter.construire_parser()._actions if a.dest != "help"]
    )
    return {
        "lancables": len(lignes),
        "add_argument": sum(v["add_argument"] for v in lignes.values()),
        "cachees": sum(v["cachees"] for v in lignes.values()),
        "sous_commandes_dispatch": {"prospecter": 7, "comparer_aides": 1},
        "actions_positionnelles_veille_benchmark_jev": 3,
        "sous_commandes_sources": sous,
        "prospecter_options_effectives": effectives,
        "par_script": lignes,
    }


def env() -> dict:
    import providall.registry as reg
    import veille_llm
    from pipeline.llm import ROLES

    perimetre = {
        "DECISION_MODEL",
        "DECISION_URL",
        "OPENROUTER_API_KEY",
        "JEV_SEUIL_BAS",
        "JEV_SEUIL_HAUT",
        "JEV_VEILLE_FILTRE",
        "JEV_VEILLE_GARDE",
        "JEV_VEILLE_REFONTE",
        "VEILLE_MODEL",
    } | {f.env_key for f in veille_llm.FOURNISSEURS.values()}
    fixes = {
        "LLM_MODEL",
        "LLM_PROVIDER",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MAX_TOKENS",
        "LLM_EFFORT",
        "LLM_TEMPERATURE",
        "LLM_RETRIES",
        "LLM_TIMEOUT",
        "LLM_TIMEOUT_MS",
        "PROVIDALL_NO_DOTENV",
        "LLM_DEBUG",
    }
    providall_vars = (
        fixes
        | {f"LLM_MODEL_{r.upper()}" for r in ROLES}
        | {p.api_key_env for p in reg.PROVIDERS.values() if p.api_key_env}
        | {f"{n.upper()}_BASE_URL" for n in reg.PROVIDERS}
    )
    return {
        "perimetre": sorted(perimetre),
        "providall": sorted(providall_vars),
        "nb_perimetre": len(perimetre),
        "nb_providall": len(providall_vars),
        "nb_communes": len(perimetre & providall_vars),
        "nb_union": len(perimetre | providall_vars),
    }


def file_et_veille() -> dict:
    from pipeline import etat as E

    f = yaml.safe_load((DATA / "prospection" / "file-attente.yaml").read_text(encoding="utf-8"))
    statuts = Counter(t["statut"] for t in f.values())
    statut_motif = Counter(
        f"{t['statut']}|{'motif' if t.get('motif_ignore') else '-'}" for t in f.values()
    )
    ingere_sans_yaml = [
        s for s, t in f.items() if t["statut"] == "ingere" and not (AIDES / f"{s}.yaml").exists()
    ]
    yamls = {p.stem for p in AIDES.glob("*.yaml")}
    v = yaml.safe_load((DATA / "veille-state.yaml").read_text(encoding="utf-8"))
    v = v.get("aides", v)
    return {
        "file_entrees": len(f),
        "file_statuts": dict(statuts),
        "file_statut_x_motif": dict(statut_motif),
        "ignore_sans_motif": wilson(statut_motif["ignore|-"], statuts["ignore"]),
        "ingere_avec_motif_ignore": statut_motif["ingere|motif"],
        "ingere_sans_yaml": wilson(len(ingere_sans_yaml), statuts["ingere"]),
        "yaml_hors_file": wilson(len(yamls - set(f)), len(yamls)),
        "champs_tache": len(E.Tache.model_fields),
        "champs_ingestion": len(E.Ingestion.model_fields),
        "statuts_declares": list(E.STATUTS),
        "veille_entrees": len(v),
        "veille_statuts": dict(Counter(x.get("status") for x in v.values())),
        "sites_ecriture_statut": {
            "transition_garde": [
                "ingestion/orchestrateur.py:130",
                ":171",
                ":221",
                ":257",
                ":259",
            ],
            "controle_du_statut_sous_le_meme_verrou": [
                "balayage.py:356 (statut != a_valider -> on saute)",
                "balayage.py:365 (promouvables -> motif_non_promotion exige a_valider, etat.py:362)",
                "prospecter.py:836-846 relire -> prospection/fiche.py:328 (seul un echec bouge)",
                "prospecter.py:272 etat.fusionner, etat.py:250-277 (cree si absent, prospection/fiche.py:284)",
            ],
            "controle_hors_verrou_TOCTOU": [
                "prospecter.py:370 (--tout, promouvables lu avant mettre_a_jour)",
                "prospecter.py:402 (slugs nommes ou --tout ; DEPUIS_NOMME inclut ignore, motif conserve)",
                "prospecter.py:948 (--auto)",
            ],
            "aucun_controle_du_statut_courant": [
                "ingestion/orchestrateur.py:315 (apres le jeton en_cours)",
                "dedoublonner_aides.py:323",
                "prospection/requalification.py:465",
            ],
            "pas_une_ecriture_de_la_file": [
                "ingerer.py:191 (tache en memoire, ingerer.py:162-166)"
            ],
        },
    }


def classes_echec() -> dict:
    f = yaml.safe_load((DATA / "prospection" / "file-attente.yaml").read_text(encoding="utf-8"))
    dbl: set[str] = set()
    for p in (DATA / "doublons").glob("*.yaml"):
        for g in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("doublons", []):
            dbl.update(g.get("ecarter", []))
    echecs = sorted(AIDES.glob("*.yaml.echec"))
    yamls = {p.stem for p in AIDES.glob("*.yaml")}
    cls: dict[str, str] = {}
    trace_d: dict[str, str] = {}
    for p in echecs:
        s = p.name[: -len(".yaml.echec")]
        t = f.get(s) or {}
        m = t.get("motif_ignore") or ""
        premiere = p.read_text(encoding="utf-8").split("\n", 1)[0]
        if premiere.startswith("# ÉCHEC D'INGESTION"):
            cls[s] = "a"
        elif s in dbl or t.get("doublon_de") or "doublon" in m.lower():
            cls[s] = "b"
        elif t.get("statut") == "ignore" and m:
            cls[s] = "c"
        else:
            cls[s] = "d"
            trace_d[s] = f"{t.get('statut', 'absent')}|{m[:60]}"
    n = len(echecs)
    c = Counter(cls.values())
    d_avec_motif = {s: v for s, v in trace_d.items() if v.split("|", 1)[1]}
    deux = sorted(set(cls) & yamls)
    # faits absents
    from aides_schema import load_facts, load_pending_facts

    connus = set(load_facts()) | set(load_pending_facts())

    def faits(o, acc):
        if isinstance(o, dict):
            for k, val in o.items():
                if k == "fact" and isinstance(val, str):
                    acc.add(val)
                else:
                    faits(val, acc)
        elif isinstance(o, list):
            for x in o:
                faits(x, acc)

    def absents(glob):
        k, distincts, nb = 0, set(), 0
        for p in AIDES.glob(glob):
            nb += 1
            acc: set[str] = set()
            faits(yaml.safe_load(p.read_text(encoding="utf-8")), acc)
            if acc - connus:
                k += 1
                distincts |= acc - connus
        return wilson(k, nb), len(distincts)

    ech_abs, ech_dist = absents("*.yaml.echec")
    yml_abs, yml_dist = absents("*.yaml")
    return {
        "yaml": len(yamls),
        "yaml_echec": n,
        "classes": {k: wilson(c[k], n) for k in "abcd"},
        "d_avec_motif_dans_la_file": d_avec_motif,
        "classes_si_motif_suffit": {
            "c": wilson(c["c"] + len(d_avec_motif), n),
            "d": wilson(c["d"] - len(d_avec_motif), n),
        },
        "slugs_yaml_et_echec": deux,
        "slugs_yaml_et_echec_par_classe": dict(Counter(cls[s] for s in deux)),
        "echec_citant_fait_absent": ech_abs,
        "echec_faits_absents_distincts": ech_dist,
        "yaml_citant_fait_absent": yml_abs,
        "yaml_faits_absents_distincts": yml_dist,
        "faits_connus": len(connus),
    }


def modeles() -> dict:
    import veille_llm
    from providall import _registry_data as R

    avant = len(R.MODELS_DATA)
    import pipeline.llm as L

    prov_tarifes = sum(
        1
        for d in R.MODELS_DATA.values()
        if d.get("price_in") is not None or d.get("price_out") is not None
    )
    veille_tarifes = sum(1 for s in veille_llm.REGISTRE.values() if s.tarif_connu)
    return {
        "providall": {"modeles": avant, "tarifes": prov_tarifes},
        "modeles_maison": {
            "modeles": len(L.MODELES_MAISON),
            "alias": [m.alias for m in L.MODELES_MAISON],
        },
        "veille_llm": {"modeles": len(veille_llm.REGISTRE), "tarifes": veille_tarifes},
        "entrees": avant + len(L.MODELES_MAISON) + len(veille_llm.REGISTRE),
        "alias_communs_providall_veille": len(set(R.MODELS_DATA) & set(veille_llm.REGISTRE)),
        "ds_flash": {
            "providall": [
                R.MODELS_DATA["ds-flash"]["price_in"],
                R.MODELS_DATA["ds-flash"]["price_out"],
            ],
            "veille": [
                veille_llm.REGISTRE["ds-flash"].prix_in,
                veille_llm.REGISTRE["ds-flash"].prix_out,
            ],
        },
    }


def prompts() -> dict:
    import rediger_fiches
    import veille_audit
    import veille_llm
    import veille_typage
    from ingestion import contexte, ontologie, verification
    from prospection import arbitre, lecture, requalification, tri

    from aides_schema import load_facts, load_pending_facts

    def m(s: str) -> dict[str, int]:
        return {"caracteres": len(s), "jetons_3_5": round(len(s) / 3.5)}

    facts, pending = load_facts(), load_pending_facts()
    ps = contexte.prompt_systeme(facts, pending)
    etat = arbitre.etat("", "")
    skill = contexte.sans_front_matter(contexte.SKILL_PATH.read_text(encoding="utf-8"))
    res = {
        "tri.doctrine": m(tri.doctrine()),
        "ingestion.prompt_systeme": m(ps),
        "ingestion.blocs": len(ps.split("\n\n---\n\n")),
        "ingestion.index_faits": m(contexte.index_faits(facts, pending)),
        "jev.etat_json": m(json.dumps(etat, ensure_ascii=False)),
        "jev.questions_json": m(json.dumps(arbitre.QUESTIONS, ensure_ascii=False)),
        "jev.etat_json_ascii": m(json.dumps(etat, ensure_ascii=True)),
        "jev.questions_json_ascii": m(json.dumps(arbitre.QUESTIONS, ensure_ascii=True)),
        # Prompts fixes que la note ne mesure pas :
        "lecture.consigne": m(lecture.consigne()),
        "requalification.consigne": m(requalification.consigne()),
        "rediger_fiches.consigne": m(rediger_fiches.consigne()),
        "verification.prompt_verificateur": m(verification.prompt_verificateur(skill)),
        "ontologie.CONSIGNE": m(ontologie.CONSIGNE),
        "veille_llm.SYSTEM": m(veille_llm.SYSTEM),
        "veille_audit.SYSTEM_AUDIT": m(veille_audit.SYSTEM_AUDIT),
        "veille_typage.SYSTEM_TYPAGE": m(veille_typage.SYSTEM_TYPAGE),
    }
    skills = BACKEND.parent / ".claude" / "skills"
    res["skills_md"] = {
        p.parent.name: {"octets": p.stat().st_size, "lignes": nb_lignes(p)}
        for p in sorted(skills.glob("*/SKILL.md"))
    }
    return res


def outils_agent() -> int:
    src = (SCRIPTS / "ingestion" / "outils.py").read_text(encoding="utf-8")
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "outils" for t in n.targets
        ):
            gen = n.value
            if isinstance(gen, ast.ListComp):
                it = gen.generators[0].iter
                if isinstance(it, ast.Tuple):
                    return len(it.elts)
    raise RuntimeError("liste des outils introuvable")


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    res = {
        "date": "2026-10-10",
        "commande": "cd backend && uv run python scripts/mesures/comptes_figes_recompte.py",
        "code": code(),
        "tests": tests(),
        "cli": cli(),
        "env": env(),
        "file_et_veille": file_et_veille(),
        "echec": classes_echec(),
        "modeles": modeles(),
        "prompts": prompts(),
        "outils_agent_ingestion": outils_agent(),
    }
    (SORTIE / "recompte.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    c = res["code"]["total"]
    print(f"code : {c['fichiers']} fichiers, {c['total']} lignes, {c['code']} de code")
    print(f"tests : {res['tests']['fichiers']} fichiers, {res['tests']['lignes']} lignes")
    print(
        f"cli : {res['cli']['lancables']} lançables, {res['cli']['add_argument']} add_argument, "
        f"{res['cli']['cachees']} cachées"
    )
    e = res["env"]
    print(f"env : {e['nb_perimetre']} + {e['nb_providall']} - {e['nb_communes']} = {e['nb_union']}")
    print(f"echec : {json.dumps(res['echec']['classes'])}")
    print(f"outils : {res['outils_agent_ingestion']}")
    print(f"écrit : {SORTIE / 'recompte.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
