"""Fige les comptes que la refonte des pipelines du catalogue devra réduire.

Commande (depuis backend/) :

    uv run python scripts/mesures/comptes_figes.py

Produit, dans data/reviews/logs/refonte/2026-10-10-comptes-figes-1/ :
  - comptes.json : tous les comptes (référence pour mesurer la baisse en fin de refonte) ;
  - fichiers.tsv, tests.tsv : wc -l et rôle (première ligne de docstring) par fichier ;
  - cli.tsv, env.tsv, echec.tsv : détail des options, des variables lues, des .yaml.echec.

Lecture seule : aucun appel réseau ni de modèle, aucun script du pipeline exécuté.
Les seuls imports de modules existants sont `pipeline.etat`, `prospection.tri`,
`prospection.arbitre`, `ingestion.contexte`, `aides_schema` et le registre de
providall, qui ne lisent que des fichiers. `veille_llm` n'est PAS importé (il
charge le .env à l'import) : son registre est lu par l'AST.
"""

from __future__ import annotations

import ast
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[2]
SCRIPTS = BACKEND / "scripts"
TESTS = BACKEND / "tests"
DATA = BACKEND / "data"
SORTIE = DATA / "reviews" / "logs" / "refonte" / "2026-10-10-comptes-figes-1"
PROVIDALL = BACKEND / ".venv" / "lib" / "python3.12" / "site-packages" / "providall"

sys.path[:0] = [str(SCRIPTS), str(BACKEND)]

GROUPES: dict[str, list[str]] = {
    "prospection": ["prospection/*.py", "prospecter.py", "balayage.py"],
    "ingestion": ["ingestion/*.py", "ingerer.py", "rediger_fiches.py"],
    "socle_pipeline": ["pipeline/*.py", "snapshot_source.py"],
    "veille": ["veille_*.py"],
    "outils": [
        "benchmark_destinataire.py",
        "comparer_aides.py",
        "lint_aides_data.py",
        "ontologie_regles.py",
        "auditer_ontologie.py",
        "auditer_raisons.py",
        "dedoublonner_aides.py",
        "faits_orphelins.py",
        "fusionner_faits.py",
        "retyper_faits.py",
        "mesure_questionnaire.py",
    ],
}

MOTIFS_TESTS = [
    "test_veille_*.py",
    "test_ingestion_*.py",
    "test_pipeline_*.py",
    "test_prospection.py",
    "test_balayage.py",
    "test_lint_aides_data.py",
    "test_ontologie_regles.py",
    "test_fusionner_faits.py",
    "test_retyper_faits.py",
    "test_faits_durables*.py",
]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(c - m, 4), round(c + m, 4)


def taux(k: int, n: int) -> dict:
    return {"k": k, "n": n, "p": round(k / n, 4) if n else None, "wilson95": wilson(k, n)}


def lignes(p: Path) -> int:
    return p.read_bytes().count(b"\n")


def role(p: Path) -> str:
    try:
        doc = ast.get_docstring(ast.parse(p.read_text(encoding="utf-8"))) or ""
    except SyntaxError:
        doc = ""
    for ligne in doc.splitlines():
        if ligne.strip():
            return ligne.strip()
    return "(pas de docstring)"


def rel(p: Path) -> str:
    return str(p.relative_to(BACKEND))


# --------------------------------------------------------------------------- 1


def perimetre() -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = {}
    for g, motifs in GROUPES.items():
        fichiers: list[Path] = []
        for m in motifs:
            fichiers += sorted(SCRIPTS.glob(m))
        out[g] = fichiers
    return out


def modules_du_perimetre(per: dict[str, list[Path]]) -> set[str]:
    noms = {"prospection", "ingestion", "pipeline"}
    for fichiers in per.values():
        for f in fichiers:
            if f.parent == SCRIPTS:
                noms.add(f.stem)
    return noms


def imports_de(p: Path) -> set[str]:
    try:
        arbre = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    out = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module.split(".")[0])
    return out


def voisins_hors_liste(per: dict[str, list[Path]], mods: set[str]) -> list[str]:
    dedans = {f for fs in per.values() for f in fs}
    out = []
    for f in sorted(SCRIPTS.glob("*.py")):
        if f in dedans:
            continue
        if imports_de(f) & mods:
            out.append(f"{rel(f)} importe {sorted(imports_de(f) & mods)}")
    return out


def tests_du_perimetre(mods: set[str]) -> tuple[list[Path], dict[str, str]]:
    choisis: dict[Path, str] = {}
    for m in MOTIFS_TESTS:
        for f in TESTS.glob(m):
            choisis[f] = f"motif {m}"
    for f in TESTS.glob("test_*.py"):
        if f in choisis:
            continue
        commun = imports_de(f) & mods
        if commun:
            choisis[f] = "importe " + ",".join(sorted(commun))
    fichiers = sorted(choisis)
    return fichiers, {rel(f): choisis[f] for f in fichiers}


# --------------------------------------------------------------------------- 2


def est_suppress(kw: ast.keyword) -> bool:
    v = kw.value
    return kw.arg == "help" and (
        (isinstance(v, ast.Attribute) and v.attr == "SUPPRESS")
        or (isinstance(v, ast.Name) and v.id == "SUPPRESS")
    )


def cli(p: Path) -> dict | None:
    src = p.read_text(encoding="utf-8")
    if '__name__ == "__main__"' not in src and "__name__ == '__main__'" not in src:
        return None
    arbre = ast.parse(src)
    options = cachees = sous = 0
    lignes_cachees = []
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr == "add_argument":
                options += 1
                if any(est_suppress(k) for k in n.keywords):
                    cachees += 1
                    lignes_cachees.append(n.lineno)
            elif n.func.attr == "add_parser":
                sous += 1
        # Sous-commandes à la main (prospecter.py : dict SOUS_COMMANDES).
        if (
            isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "SOUS_COMMANDES" for t in n.targets)
            and isinstance(n.value, ast.Dict)
        ):
            sous += len(n.value.keys)
    return {
        "add_argument": options,
        "sous_commandes": sous,
        "cachees": cachees,
        "lignes_cachees": lignes_cachees,
    }


def prospecter_effectif() -> dict:
    """Options réellement offertes par sous-commande (inclut `_options_communes`)."""
    import prospecter  # noqa: PLC0415 — n'importe que des modules sans écriture

    out = {}
    for nom, (fabrique, _) in prospecter.SOUS_COMMANDES.items():
        p = fabrique()
        out[nom] = sum(1 for a in p._actions if a.dest != "help")  # noqa: SLF001
    return out


# --------------------------------------------------------------------------- 3

RE_ENV = re.compile(
    r"""(?:os\.environ\.get|os\.getenv|environ\.get|os\.environ\.setdefault|env_str|env_int|env_float|env_bool|_seuil)\(\s*["']([A-Z][A-Z0-9_]+)["']"""
    r"""|(?:os\.)?environ\[\s*["']([A-Z][A-Z0-9_]+)["']\s*\]"""
)
RE_FOURNISSEUR = re.compile(
    r"""Fournisseur\(\s*["'][a-z_]+["'],\s*["']([A-Z][A-Z0-9_]+)["']""", re.S
)


def env_perimetre(per: dict[str, list[Path]]) -> dict[str, list[str]]:
    vues: dict[str, list[str]] = defaultdict(list)
    for fs in per.values():
        for f in fs:
            for i, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                for m in RE_ENV.finditer(ligne):
                    vues[m.group(1) or m.group(2)].append(f"{rel(f)}:{i}")
            texte = f.read_text(encoding="utf-8")
            for m in RE_FOURNISSEUR.finditer(texte):
                i = texte.count("\n", 0, m.start(1)) + 1
                vues[m.group(1)].append(f"{rel(f)}:{i} (veille_llm, via spec.env_key)")
    return dict(vues)


def env_providall() -> dict[str, list[str]]:
    from pipeline.llm import ROLES  # noqa: PLC0415
    from providall.registry import PROVIDERS  # noqa: PLC0415

    vues: dict[str, list[str]] = defaultdict(list)
    for f in sorted(PROVIDALL.glob("*.py")):
        for i, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in RE_ENV.finditer(ligne):
                vues[m.group(1) or m.group(2)].append(f"providall/{f.name}:{i}")
    cfg = PROVIDALL / "config.py"
    src = cfg.read_text(encoding="utf-8").splitlines()
    l_role = next(i for i, s in enumerate(src, 1) if "LLM_MODEL_{" in s)
    l_url = next(i for i, s in enumerate(src, 1) if '_BASE_URL"' in s and "upper()" in s)
    l_cle = next(i for i, s in enumerate(src, 1) if "spec.api_key_env" in s)
    for r in ROLES:
        vues[f"LLM_MODEL_{r.upper()}"].append(f"providall/config.py:{l_role} (rôle {r})")
    for nom, p in PROVIDERS.items():
        if p.api_key_env:
            vues[p.api_key_env].append(f"providall/config.py:{l_cle} (clé de {nom})")
        vues[f"{nom.upper()}_BASE_URL"].append(f"providall/config.py:{l_url} (surcharge {nom})")
    return dict(vues)


# --------------------------------------------------------------------------- 4

RE_TRANSITION = re.compile(r"""transition\([^)]*?["'](\w+)["'],\s*depuis=\(([^)]*)\)""")
RE_STATUT = re.compile(r"""statut["']?\s*[:=]\s*(?:["'](\w+)["']|(_statut_final))""")


def literaux(p: Path) -> dict[str, list[str]]:
    arbre = ast.parse(p.read_text(encoding="utf-8"))
    out = {}
    for n in arbre.body:
        if (
            isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Subscript)
            and isinstance(n.value.value, ast.Name)
            and n.value.value.id == "Literal"
        ):
            elts = n.value.slice.elts if isinstance(n.value.slice, ast.Tuple) else [n.value.slice]
            vals = [e.value for e in elts if isinstance(e, ast.Constant)]
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out[f"{t.id} ({rel(p)}:{n.lineno})"] = vals
    return out


def statuts(per: dict[str, list[Path]]) -> dict:
    from pipeline import etat  # noqa: PLC0415

    ecritures = []
    for fs in per.values():
        for f in fs:
            for i, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                for m in RE_TRANSITION.finditer(ligne):
                    ecritures.append(
                        {"ou": f"{rel(f)}:{i}", "vers": m.group(1), "depuis": m.group(2)}
                    )
                if (
                    "transition(" in ligne
                    and not RE_TRANSITION.search(ligne)
                    and "def transition" not in ligne
                    and "`transition(" not in ligne
                ):
                    ecritures.append({"ou": f"{rel(f)}:{i}", "multiligne": ligne.strip()})
                for m in RE_STATUT.finditer(ligne):
                    if "tache.statut" in ligne or "!=" in ligne or "==" in ligne:
                        continue
                    ecritures.append({"ou": f"{rel(f)}:{i}", "pose": m.group(1) or m.group(2)})
    veille_lit = {}
    for f in sorted(SCRIPTS.glob("veille_*.py")):
        veille_lit.update(literaux(f))
    etat_veille = yaml.safe_load((DATA / "veille-state.yaml").read_text(encoding="utf-8")) or {}
    champs_veille = Counter(k for e in etat_veille.values() for k in (e or {}))
    file = yaml.safe_load((DATA / "prospection" / "file-attente.yaml").read_text("utf-8")) or {}
    return {
        "file": {
            "statuts": list(etat.STATUTS),
            "champs_tache": list(etat.Tache.model_fields),
            "champs_ingestion": list(etat.Ingestion.model_fields),
            "destinataire": list(etat.Destinataire.__args__),
            "objet": list(etat.Objet.__args__),
            "categorie_ecart": list(etat.CategorieEcart.__args__),
            "ecritures_de_statut": ecritures,
            "repartition_file_attente": dict(
                Counter((t or {}).get("statut", "a_valider") for t in file.values())
            ),
            "entrees_file_attente": len(file),
        },
        "veille": {
            "literaux": veille_lit,
            "veille_state_entrees": len(etat_veille),
            "veille_state_status": dict(
                Counter((e or {}).get("status") for e in etat_veille.values())
            ),
            "veille_state_champs": dict(champs_veille),
        },
    }


# --------------------------------------------------------------------------- 5


def faits_cites(noeud) -> set[str]:
    out = set()
    if isinstance(noeud, dict):
        for k, v in noeud.items():
            if k == "fact" and isinstance(v, str):
                out.add(v)
            out |= faits_cites(v)
    elif isinstance(noeud, list):
        for v in noeud:
            out |= faits_cites(v)
    return out


def echecs() -> dict:
    aides = DATA / "aides"
    yamls = sorted(aides.glob("*.yaml"))
    fichiers = sorted(aides.glob("*.yaml.echec"))
    connus = set(yaml.safe_load((DATA / "facts.yaml").read_text("utf-8")) or {})
    connus |= set(yaml.safe_load((DATA / "facts_pending.yaml").read_text("utf-8")) or {})
    file = yaml.safe_load((DATA / "prospection" / "file-attente.yaml").read_text("utf-8")) or {}
    doublons_arbitres: dict[str, str] = {}
    for f in sorted((DATA / "doublons").glob("*.yaml")):
        for g in (yaml.safe_load(f.read_text("utf-8")) or {}).get("doublons", []):
            for s in g.get("ecarter", []):
                doublons_arbitres[s] = f"{rel(f)} (survivant {g.get('survivant')})"
    stems_yaml = {p.stem for p in yamls}
    lignes_tsv = []
    classes = Counter()
    sous_c = Counter()
    sans_analyse = 0
    absents_par_fichier = 0
    absents = Counter()
    slug_interne_diff = 0
    for f in fichiers:
        slug = f.name[: -len(".yaml.echec")]
        texte = f.read_text(encoding="utf-8")
        tache = file.get(slug) or {}
        motif = str(tache.get("motif_ignore") or "")
        if texte.startswith("# ÉCHEC D'INGESTION"):
            c, preuve = "a_echec_pipeline", texte.splitlines()[0][:120]
        elif slug in doublons_arbitres:
            c, preuve = "b_doublon", doublons_arbitres[slug]
        elif tache.get("doublon_de") or "doublon" in motif.lower():
            c, preuve = "b_doublon", f"file-attente : {motif or tache.get('doublon_de')}"
        elif tache.get("statut") == "ignore" and motif:
            c, preuve = "c_ecartee", f"file-attente : {motif[:100]}"
            sous_c[motif.split(":")[0].split("(")[0].strip()[:40]] += 1
        else:
            c = "d_autre"
            preuve = f"statut file={tache.get('statut', 'absent de la file')}"
        classes[c] += 1
        try:
            doc = yaml.safe_load(texte)
        except yaml.YAMLError:
            doc = None
        if not isinstance(doc, dict):
            sans_analyse += 1
            manquants: set[str] = set()
        else:
            if doc.get("slug") and doc.get("slug") != slug:
                slug_interne_diff += 1
            manquants = faits_cites(doc) - connus
        if manquants:
            absents_par_fichier += 1
            absents.update(manquants)
        lignes_tsv.append(
            "\t".join(
                [slug, c, str(slug in stems_yaml), str(len(manquants)), preuve.replace("\t", " ")]
            )
        )
    (SORTIE / "echec.tsv").write_text(
        "slug\tclasse\taussi_en_yaml\tfaits_absents\tpreuve\n" + "\n".join(lignes_tsv) + "\n",
        encoding="utf-8",
    )
    deux = sorted({f.name[: -len(".yaml.echec")] for f in fichiers} & stems_yaml)
    yaml_absents = 0
    for p in yamls:
        try:
            if faits_cites(yaml.safe_load(p.read_text("utf-8"))) - connus:
                yaml_absents += 1
        except yaml.YAMLError:
            pass
    n = len(fichiers)
    return {
        "yaml": len(yamls),
        "yaml_echec": n,
        "classes": dict(classes),
        "classes_taux": {k: taux(v, n) for k, v in classes.items()},
        "ecartees_par_motif": dict(sous_c.most_common()),
        "echec_non_analysables": sans_analyse,
        "echec_slug_interne_different_du_nom": slug_interne_diff,
        "slugs_en_yaml_et_echec": deux,
        "echec_citant_fait_absent": taux(absents_par_fichier, n),
        "faits_absents_distincts": len(absents),
        "yaml_citant_fait_absent": taux(yaml_absents, len(yamls)),
        "faits_connus": len(connus),
    }


# --------------------------------------------------------------------------- 6


def registre_veille() -> dict:
    arbre = ast.parse((SCRIPTS / "veille_llm.py").read_text(encoding="utf-8"))
    out = {}
    for n in arbre.body:
        if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", "") == "REGISTRE":
            assert isinstance(n.value, ast.Dict)
            for k, v in zip(n.value.keys, n.value.values, strict=True):
                assert isinstance(k, ast.Constant) and isinstance(v, ast.Call)
                kw = {a.arg: a.value.value for a in v.keywords if isinstance(a.value, ast.Constant)}
                args = [a.value for a in v.args if isinstance(a, ast.Constant)]
                out[k.value] = {
                    "fournisseur": args[1] if len(args) > 1 else None,
                    "model_id": args[2] if len(args) > 2 else None,
                    "prix_in": kw.get("prix_in", 0.0),
                    "prix_out": kw.get("prix_out", 0.0),
                    "ligne": n.lineno,
                }
    return out


def piles() -> dict:
    import pipeline.llm as llm  # noqa: PLC0415 — enregistre MODELES_MAISON en mémoire
    from providall._registry_data import MODELS_DATA  # noqa: PLC0415
    from providall.registry import MODELS  # noqa: PLC0415

    maison = {
        m.alias: {"model_id": m.model_id, "in": m.price_in, "out": m.price_out}
        for m in llm.MODELES_MAISON
    }
    reg = {
        a: {"provider": d.get("provider"), "in": d.get("price_in"), "out": d.get("price_out")}
        for a, d in MODELS_DATA.items()
    }
    veille = registre_veille()
    return {
        "providall_registre": {
            "fichier": "providall/_registry_data.py (MODELS_DATA)",
            "modeles": len(reg),
            "avec_tarif": sum(1 for d in reg.values() if d["in"] is not None),
            "detail": reg,
        },
        "pipeline_llm_modeles_maison": {
            "fichier": "scripts/pipeline/llm.py (MODELES_MAISON)",
            "modeles": len(maison),
            "detail": maison,
        },
        "providall_registre_effectif_apres_import": len(MODELS),
        "veille_llm_registre": {
            "fichier": "scripts/veille_llm.py (REGISTRE)",
            "modeles": len(veille),
            "avec_tarif": sum(1 for d in veille.values() if d["prix_in"] or d["prix_out"]),
            "detail": veille,
        },
        "jev": {"fichier": "scripts/pipeline/decision.py", "table": 0},
        "roles_pipeline": list(llm.ROLES),
    }


# --------------------------------------------------------------------------- 7


def prompts() -> dict:
    from ingestion import contexte  # noqa: PLC0415
    from prospection import arbitre, tri  # noqa: PLC0415

    from aides_schema import load_facts, load_pending_facts  # noqa: PLC0415

    def mesure(t: str) -> dict:
        return {"car": len(t), "jetons_3_5": round(len(t) / 3.5), "jetons_3_6": round(len(t) / 3.6)}

    doc = tri.doctrine()
    facts = dict(load_facts(DATA / "facts.yaml"))
    pending = dict(load_pending_facts(DATA / "facts_pending.yaml"))
    systeme = contexte.prompt_systeme(facts, pending)
    blocs = systeme.split("\n\n---\n\n")
    etat_fixe = json.dumps(arbitre.etat("", ""), ensure_ascii=False)
    questions = json.dumps(arbitre.QUESTIONS, ensure_ascii=False)
    arbre = ast.parse((SCRIPTS / "ingestion" / "outils.py").read_text(encoding="utf-8"))
    n_outils = 0
    for n in ast.walk(arbre):
        if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "outils" for t in n.targets
        ):
            for g in ast.walk(n.value):
                if isinstance(g, ast.comprehension) and isinstance(g.iter, ast.Tuple):
                    n_outils = len(g.iter.elts)
    return {
        "tri_doctrine": mesure(doc),
        "ingestion_prompt_systeme": mesure(systeme),
        "ingestion_blocs": [{"debut": b.strip().splitlines()[0][:60], **mesure(b)} for b in blocs],
        "ingestion_faits_indexes": {"facts": len(facts), "pending": len(pending)},
        "jev_etat_fixe_json": mesure(etat_fixe),
        "jev_questions_json": mesure(questions),
        "jev_nb_questions": len(arbitre.QUESTIONS),
        "jev_fixe_total": mesure(etat_fixe + questions),
        "ingestion_outils": n_outils,
    }


# --------------------------------------------------------------------------- main


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    per = perimetre()
    mods = modules_du_perimetre(per)
    tests, motifs = tests_du_perimetre(mods)

    tsv = ["groupe\tfichier\tlignes\trole"]
    totaux = {}
    for g, fs in per.items():
        totaux[g] = {"fichiers": len(fs), "lignes": sum(lignes(f) for f in fs)}
        tsv += [f"{g}\t{rel(f)}\t{lignes(f)}\t{role(f)}" for f in fs]
    (SORTIE / "fichiers.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    tsv_t = ["fichier\tlignes\tpourquoi\trole"]
    tsv_t += [f"{rel(f)}\t{lignes(f)}\t{motifs[rel(f)]}\t{role(f)}" for f in tests]
    (SORTIE / "tests.tsv").write_text("\n".join(tsv_t) + "\n", encoding="utf-8")

    clis = {}
    for fs in per.values():
        for f in fs:
            c = cli(f)
            if c:
                clis[rel(f)] = c
    (SORTIE / "cli.tsv").write_text(
        "fichier\tadd_argument\tsous_commandes\tcachees\n"
        + "\n".join(
            f"{k}\t{v['add_argument']}\t{v['sous_commandes']}\t{v['cachees']}"
            for k, v in clis.items()
        )
        + "\n",
        encoding="utf-8",
    )

    env_p = env_perimetre(per)
    env_v = env_providall()
    (SORTIE / "env.tsv").write_text(
        "variable\tlu_par\tou\n"
        + "\n".join(f"{k}\tperimetre\t{' ; '.join(v)}" for k, v in sorted(env_p.items()))
        + "\n"
        + "\n".join(f"{k}\tprovidall\t{' ; '.join(v)}" for k, v in sorted(env_v.items()))
        + "\n",
        encoding="utf-8",
    )

    head = subprocess.run(
        ["git", "-C", str(BACKEND), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    comptes = {
        "date": "2026-10-10",
        "head": head,
        "commande": "uv run python scripts/mesures/comptes_figes.py (depuis backend/)",
        "code": {
            "par_groupe": totaux,
            "total": {
                "fichiers": sum(t["fichiers"] for t in totaux.values()),
                "lignes": sum(t["lignes"] for t in totaux.values()),
            },
            "voisins_hors_liste_qui_importent_le_perimetre": voisins_hors_liste(per, mods),
        },
        "tests": {"fichiers": len(tests), "lignes": sum(lignes(f) for f in tests)},
        "cli": {
            "scripts_lancables": len(clis),
            "add_argument": sum(c["add_argument"] for c in clis.values()),
            "sous_commandes": sum(c["sous_commandes"] for c in clis.values()),
            "cachees": sum(c["cachees"] for c in clis.values()),
            "detail": clis,
            "prospecter_options_effectives_par_sous_commande": prospecter_effectif(),
        },
        "env": {
            "perimetre": sorted(env_p),
            "perimetre_total": len(env_p),
            "providall": sorted(env_v),
            "providall_total": len(env_v),
            "union_total": len(set(env_p) | set(env_v)),
        },
        "statuts": statuts(per),
        "echec": echecs(),
        "piles_modeles": piles(),
        "prompts": prompts(),
    }
    (SORTIE / "comptes.json").write_text(
        json.dumps(comptes, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: comptes[k] for k in ("code", "tests")}, ensure_ascii=False, indent=1))
    print("sortie :", SORTIE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
