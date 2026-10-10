"""Carte des étages actuels des pipelines du catalogue, et inventaire des décisions fermées.

Commande (depuis backend/) :

    uv run python scripts/mesures/carte_et_decisions.py

Produit, dans data/reviews/logs/refonte/2026-10-10-carte-et-decisions-1/ :
  - etages.tsv / etages.md : un étage par ligne (chaîne, opération rattachée,
    décideur, modèle, entrée, sortie, coût, volume, fichier:ligne résolus) ;
  - decisions.tsv / decisions.md : une décision fermée par ligne (question,
    options, décideur, fichier:ligne, opération, vérité terrain disponible) ;
  - sans_verite.md : les décisions sans vérité terrain et le coût estimé d'un
    échantillon de contrôle de 100 cas ;
  - ancres.tsv : chaque ancre (fichier, motif) et la ligne trouvée, ou MANQUANT ;
  - enums.json : les listes d'options lues dans le code par l'AST (aucun import) ;
  - comptes.json : les volumes recomptés dans les données (file, catalogue,
    faits, veille, journaux, jeux étiquetés) ;
  - verites.tsv : chaque fichier de vérité terrain cité, son existence et sa taille ;
  - resume.txt : les comptes de synthèse.

Lecture seule : aucun appel réseau ni de modèle, aucun script du pipeline
exécuté, aucun module du pipeline importé (les listes d'options sont lues par
l'AST, les données par yaml/json). Les numéros de ligne sont ceux du worktree
au moment du lancement : une ancre introuvable sort en MANQUANT, jamais en
silence.
"""

from __future__ import annotations

import ast
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

BACKEND = Path(__file__).resolve().parents[2]
RACINE = BACKEND.parent
DATA = BACKEND / "data"
LOGS = DATA / "reviews" / "logs"
SORTIE = LOGS / "refonte" / "2026-10-10-carte-et-decisions-1"
S = "backend/scripts/"
CHARGEUR = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

OPERATIONS = {
    "O1": "trouver une source",
    "O2": "l'archiver",
    "O3": "juger si elle relève du catalogue",
    "O4": "extraire des conditions citées",
    "O5": "les typer contre l'ontologie",
    "O6": "décider des faits",
    "O7": "vérifier",
    "O8": "écrire",
    "O9": "détecter un changement de source",
    "O10": "l'appliquer",
    "O11": "arbitrer le doute",
    "O12": "rendre compte à Félix",
}


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    demi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - demi), min(1.0, centre + demi))


def taux(k: int, n: int) -> str:
    bas, haut = wilson(k, n)
    p = 100 * k / n if n else 0.0
    return f"{k}/{n} = {p:.1f} % [{100 * bas:.1f} ; {100 * haut:.1f}]".replace(".", ",")


_LIGNES: dict[str, list[str]] = {}


def lignes(fichier: str) -> list[str]:
    if fichier not in _LIGNES:
        chemin = RACINE / fichier
        _LIGNES[fichier] = (
            chemin.read_text(encoding="utf-8").splitlines() if chemin.exists() else []
        )
    return _LIGNES[fichier]


ANCRES: list[tuple[str, str, str, str]] = []  # (id, fichier, motif, résultat)


def ancre(fichier: str, motif: str, ident: str = "") -> str:
    """`fichier:ligne` de la première ligne qui porte le motif, ou MANQUANT."""
    rx = re.compile(motif)
    for i, ligne in enumerate(lignes(fichier), 1):
        if rx.search(ligne):
            res = f"{fichier.removeprefix('backend/')}:{i}"
            ANCRES.append((ident, fichier, motif, res))
            return res
    res = f"MANQUANT {fichier}::{motif}"
    ANCRES.append((ident, fichier, motif, res))
    return res


def charger_yaml(chemin: Path) -> Any:
    return yaml.load(chemin.read_text(encoding="utf-8"), Loader=CHARGEUR)


# ---------------------------------------------------------------------------
# Listes d'options lues par l'AST (aucun import du pipeline)
# ---------------------------------------------------------------------------


def _chaines(noeud: ast.AST) -> list[str]:
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return [noeud.value]
    if isinstance(noeud, ast.Tuple | ast.List | ast.Set):
        return [v for e in noeud.elts for v in _chaines(e)]
    if isinstance(noeud, ast.Subscript):  # Literal[...] ou X | None
        return _chaines(noeud.slice)
    if isinstance(noeud, ast.BinOp):
        return _chaines(noeud.left) + _chaines(noeud.right)
    if isinstance(noeud, ast.Dict):
        return [k.value for k in noeud.keys if isinstance(k, ast.Constant)]
    if isinstance(noeud, ast.Call) and noeud.args:  # frozenset({...}), tuple(...)
        return _chaines(noeud.args[0])
    return []


def enum_ast(fichier: str, nom: str) -> list[str]:
    """Valeurs d'un `nom = Literal[...]`, d'un tuple de chaînes, des clés d'un
    dict littéral, ou d'un champ `Classe.champ` annoté Literal."""
    arbre = ast.parse((RACINE / fichier).read_text(encoding="utf-8"))
    classe, _, champ = nom.rpartition(".")
    portee: list[ast.stmt] = arbre.body
    if classe:
        portee = next(
            (n.body for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe), []
        )
        nom = champ
    for n in portee:
        if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == nom for t in n.targets
        ):
            return _chaines(n.value)
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == nom:
            if n.value is not None and not classe:
                return _chaines(n.value)
            return _chaines(n.annotation)
    return []


def questions_jev(fichier: str, nom: str) -> dict[str, list[str]]:
    """{question: options} d'un dict de questions Jev (`choix`, `noul`)."""
    arbre = ast.parse((RACINE / fichier).read_text(encoding="utf-8"))
    for n in arbre.body:
        cible = None
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            cible, valeur = n.target.id, n.value
        elif isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            cible, valeur = n.targets[0].id, n.value
        if cible != nom or not isinstance(valeur, ast.Dict):
            continue
        sortie: dict[str, list[str]] = {}
        for k, v in zip(valeur.keys, valeur.values, strict=True):
            if not (isinstance(k, ast.Constant) and isinstance(v, ast.Call)):
                continue
            fonction = getattr(v.func, "id", "")
            if fonction == "noul":
                sortie[k.value] = ["true", "false"]
            elif fonction == "choix" and len(v.args) > 1:
                sortie[k.value] = _chaines(v.args[1])
        return sortie
    return {}


def enums() -> dict[str, Any]:
    e: dict[str, Any] = {
        "tri.Famille": enum_ast(S + "prospection/tri.py", "Famille"),
        "tri.Decision": enum_ast(S + "prospection/tri.py", "Decision"),
        "territoires.Statut": enum_ast(S + "prospection/territoires.py", "Statut"),
        "territoires.Strategie.type": enum_ast(S + "prospection/territoires.py", "Strategie.type"),
        "territoires.entetes": enum_ast(S + "prospection/territoires.py", "Territoire.entetes"),
        "etat.STATUTS": enum_ast(S + "pipeline/etat.py", "STATUTS"),
        "etat.DESTINATAIRES": enum_ast(S + "pipeline/etat.py", "DESTINATAIRES"),
        "etat.OBJETS": enum_ast(S + "pipeline/etat.py", "OBJETS"),
        "etat.CATEGORIES_ECART": enum_ast(S + "pipeline/etat.py", "CATEGORIES_ECART"),
        "etat.FAMILLES_NON_PROMOUVABLES": enum_ast(
            S + "pipeline/etat.py", "FAMILLES_NON_PROMOUVABLES"
        ),
        "arbitre.QUESTIONS": questions_jev(S + "prospection/arbitre.py", "QUESTIONS"),
        "arbitre.Bande": enum_ast(S + "prospection/arbitre.py", "Bande"),
        "verification.AXES": enum_ast(S + "ingestion/verification.py", "AXES"),
        "verification.severite": enum_ast(S + "ingestion/verification.py", "Probleme.severite"),
        "verification.qualite_source": enum_ast(
            S + "ingestion/verification.py", "RapportVerification.qualite_source"
        ),
        "ontologie.Fusion.verdict": enum_ast(S + "ingestion/ontologie.py", "Fusion.verdict"),
        "boucle.Arret": enum_ast(S + "ingestion/boucle.py", "Arret"),
        "schema.ConditionKind": enum_ast("backend/aides_schema.py", "ConditionKind"),
        "schema.ConditionEffect": enum_ast("backend/aides_schema.py", "ConditionEffect"),
        "schema.FactDef.type": enum_ast("backend/aides_schema.py", "FactDef.type"),
        "schema.FactDef.scope": enum_ast("backend/aides_schema.py", "FactDef.scope"),
        "schema.RAISONS": enum_ast("backend/aides_schema.py", "RAISONS"),
        "schema.CATEGORIES": enum_ast("backend/aides_schema.py", "CATEGORIES"),
        "schema.TYPES": enum_ast("backend/aides_schema.py", "TYPES"),
        "schema.THEMES_REGLEMENT": enum_ast("backend/aides_schema.py", "THEMES_REGLEMENT"),
        "schema.TONS_EN_BREF": enum_ast("backend/aides_schema.py", "TONS_EN_BREF"),
        "labels.FAMILLES_LABELS": enum_ast("backend/labels.py", "FAMILLES_LABELS"),
        "labels.TRAVAUX_LABELS": enum_ast("backend/labels.py", "TRAVAUX_LABELS"),
        "veille_analyze.STATUTS": enum_ast(S + "veille_analyze.py", "STATUTS"),
        "veille_update.Etat": enum_ast(S + "veille_update.py", "Etat"),
        "veille_apply.Issue": enum_ast(S + "veille_apply.py", "Issue"),
        "veille_apply.op": enum_ast(S + "veille_apply.py", "ChangementCondition.op"),
        "veille_apply.NouvelleCondition.kind": enum_ast(
            S + "veille_apply.py", "NouvelleCondition.kind"
        ),
        "veille_arbitre.QUESTIONS_MANDAT": questions_jev(
            S + "veille_arbitre.py", "QUESTIONS_MANDAT"
        ),
        "veille_arbitre.QUESTIONS_REFONTE": questions_jev(
            S + "veille_arbitre.py", "QUESTIONS_REFONTE"
        ),
        "veille_audit.verdict": enum_ast(S + "veille_audit.py", "CritereAudit.verdict"),
        "veille_audit.Etat": enum_ast(S + "veille_audit.py", "Etat"),
        "veille_typage.kind": enum_ast(S + "veille_typage.py", "TypageCondition.kind"),
        "veille_typage.effect": enum_ast(S + "veille_typage.py", "TypageCondition.effect"),
        "veille_typage.Etat": enum_ast(S + "veille_typage.py", "Etat"),
    }
    pieces = charger_yaml(DATA / "pieces.yaml") or {}
    e["pieces.yaml"] = sorted(pieces) if isinstance(pieces, dict) else []
    return e


# ---------------------------------------------------------------------------
# Comptes recalculés dans les données
# ---------------------------------------------------------------------------


def _lignes_fichier(chemin: Path) -> int:
    with chemin.open(encoding="utf-8", errors="replace") as f:
        return sum(1 for ligne in f if ligne.strip())


def _taille_json(chemin: Path) -> Any:
    d = json.loads(chemin.read_text(encoding="utf-8"))
    if isinstance(d, dict) and len(d) > 10:
        return {"cles": len(d)}
    if isinstance(d, dict):
        return {k: (len(v) if isinstance(v, list | dict) else v) for k, v in d.items()}
    return len(d)


def _entrees_yaml(chemin: Path) -> int:
    d = charger_yaml(chemin)
    if isinstance(d, list):
        return len(d)
    if isinstance(d, dict):
        listes = [v for v in d.values() if isinstance(v, list)]
        return len(listes[0]) if listes else len(d)
    return 0


def comptes_file(c: dict[str, Any]) -> None:
    file = charger_yaml(DATA / "prospection" / "file-attente.yaml") or {}
    c["file.total"] = len(file)
    statuts = Counter(t.get("statut") for t in file.values())
    for s, n in statuts.items():
        c[f"file.statut.{s}"] = n
    # Promotion : la règle de `etat.motif_non_promotion`, recopiée pour ne rien importer.
    objets_retenus = {"bien_ou_lieu", "activite_dans_le_lieu"}

    def indetermine(d: str, o: str, cat: str | None) -> bool:
        if cat == "non_dispositif":
            return False
        if d not in ("indetermine", "proprietaire_gestionnaire"):
            return False
        if o != "indetermine" and o not in objets_retenus:
            return False
        return d == "indetermine" or o == "indetermine"

    motifs = Counter()
    for t in file.values():
        if t.get("statut") != "a_valider":
            continue
        d, o = t.get("destinataire", "indetermine"), t.get("objet", "indetermine")
        cat = t.get("categorie_ecart")
        if indetermine(d, o, cat):
            motifs["indetermine"] += 1
        elif not (d == "proprietaire_gestionnaire" and o in objets_retenus):
            motifs["hors_perimetre"] += 1
        elif (t.get("famille") or "adjacente") in ("adjacente", "hors_perimetre"):
            motifs["famille_non_promouvable"] += 1
        else:
            motifs["promouvable"] += 1
    for m, n in motifs.items():
        c[f"file.a_valider.{m}"] = n
    prefixes = Counter()
    categories = Counter()
    for t in file.values():
        if t.get("statut") != "ignore":
            continue
        motif = (t.get("motif_ignore") or "").strip()
        if not motif:
            prefixes["(sans motif)"] += 1
        elif motif.startswith("hors périmètre à l'ingestion"):
            prefixes["hors périmètre à l'ingestion"] += 1
        elif motif.startswith("hors périmètre"):
            prefixes["hors périmètre (lecture)"] += 1
        elif "oublon" in motif:
            prefixes["doublon"] += 1
        elif motif.startswith("test du destinataire"):
            prefixes["test du destinataire"] += 1
        elif motif.startswith("tri humain"):
            prefixes["tri humain"] += 1
        else:
            prefixes["autre"] += 1
        if t.get("categorie_ecart"):
            categories[t["categorie_ecart"]] += 1
    for p, n in prefixes.items():
        c[f"file.ignore.motif.{p}"] = n
    for p, n in categories.items():
        c[f"file.ignore.categorie.{p}"] = n
    ing = [t["ingestion"] for t in file.values() if t.get("ingestion")]
    c["file.avec_bloc_ingestion"] = len(ing)
    c["file.ingestion.modele_trace"] = sum(
        1 for i in ing if i.get("modele") and "(défaut" not in str(i.get("modele"))
    )
    c["file.ingestion.a_relire"] = sum(1 for t in file.values() if t.get("a_relire"))
    c["file.doublon_probable"] = sum(1 for t in file.values() if t.get("doublon_probable"))
    c["file.source_unique_vulgarisation"] = sum(
        1 for t in file.values() if t.get("source_unique_vulgarisation")
    )
    c["file.priorite"] = dict(Counter(t.get("priorite", "normale") for t in file.values()))
    c["file.familles_a_valider"] = dict(
        Counter(
            t.get("famille") or "adjacente" for t in file.values() if t.get("statut") == "a_valider"
        )
    )


def comptes_aides(c: dict[str, Any]) -> None:
    dossier = DATA / "aides"
    actifs = sorted(dossier.glob("*.yaml"))
    c["aides.yaml"] = len(actifs)
    c["aides.yaml_echec"] = len(list(dossier.glob("*.yaml.echec")))
    ke = Counter()
    n_cond = applies_aide = familles = travaux = permanent = date_limite = 0
    plancher = montant_min = derog = fiche = docs = docs_piece = levier = porteur = 0
    raisons = Counter()
    for chemin in actifs:
        a = charger_yaml(chemin) or {}
        conds = a.get("conditions") or []
        n_cond += len(conds)
        porteur += any(
            c.get("effect") == "gate" and c.get("fact") == "statut_juridique_porteur" for c in conds
        )
        for cond in conds:
            ke[f"{cond.get('kind')}/{cond.get('effect')}"] += 1
            derog += bool(cond.get("derogation_possible"))
            levier += bool(cond.get("levier"))
        applies_aide += bool(a.get("applies_if"))
        familles += bool(a.get("familles"))
        travaux += bool((a.get("hard_filters") or {}).get("travaux"))
        cal = a.get("calendrier") or {}
        permanent += cal.get("permanent") is True
        date_limite += bool(cal.get("date_limite"))
        fin = a.get("financement") or {}
        plancher += fin.get("plancher") is not None
        montant_min += fin.get("montant_min") is not None
        fiche += bool(a.get("fiche"))
        for d in a.get("documents_requis") or []:
            docs += 1
            docs_piece += bool(d.get("piece_id"))
        for r in a.get("raison") or []:
            raisons[r] += 1
    c["aides.conditions"] = n_cond
    c["aides.kind_effect"] = dict(ke.most_common())
    c["aides.applies_if_aide"] = applies_aide
    c["aides.familles_non_vides"] = familles
    c["aides.travaux_non_vide"] = travaux
    c["aides.permanent_true"] = permanent
    c["aides.date_limite"] = date_limite
    c["aides.plancher"] = plancher
    c["aides.montant_min"] = montant_min
    c["aides.derogation_possible"] = derog
    c["aides.levier"] = levier
    c["aides.gate_statut_juridique_porteur"] = porteur
    c["aides.fiche"] = fiche
    c["aides.documents_requis"] = docs
    c["aides.documents_avec_piece_id"] = docs_piece
    c["aides.raison"] = dict(raisons)


def comptes_faits(c: dict[str, Any]) -> None:
    faits = charger_yaml(DATA / "facts.yaml") or {}
    pending = charger_yaml(DATA / "facts_pending.yaml") or {}
    c["faits.facts"] = len(faits)
    c["faits.pending"] = len(pending)
    c["faits.porteurs_concernes"] = sum(1 for f in faits.values() if f.get("porteurs_concernes"))
    c["faits.pertinent_si"] = sum(1 for f in faits.values() if f.get("pertinent_si"))
    c["faits.levier"] = sum(1 for f in faits.values() if f.get("levier"))
    c["faits.type"] = dict(Counter(f.get("type") for f in faits.values()))
    c["faits.scope"] = dict(Counter(f.get("scope") for f in faits.values()))


def comptes_territoires(c: dict[str, Any]) -> None:
    t = charger_yaml(DATA / "prospection" / "territoires.yaml") or {}
    terr = t.get("territoires", t) if isinstance(t, dict) else {}
    c["territoires.total"] = len(terr)
    c["territoires.statut"] = dict(Counter((v or {}).get("statut", "?") for v in terr.values()))
    c["territoires.strategie"] = dict(
        Counter(((v or {}).get("strategie") or {}).get("type", "?") for v in terr.values())
    )


def comptes_prospection(c: dict[str, Any]) -> None:
    lect = Counter()
    arb = 0
    tri = Counter()
    for chemin in sorted((DATA / "prospection").glob("*/lectures.jsonl")):
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            if not ligne.strip():
                continue
            lect["lignes"] += 1
            if json.loads(ligne).get("arbitrage"):
                arb += 1
    for chemin in sorted((DATA / "prospection").glob("*/tri.jsonl")):
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                tri[json.loads(ligne).get("decision", "?")] += 1
    c["prospection.dossiers_lectures"] = len(list((DATA / "prospection").glob("*/lectures.jsonl")))
    c["prospection.lectures"] = lect["lignes"]
    c["prospection.lectures_avec_arbitrage_jev"] = arb
    c["prospection.tri_decisions_dossiers_locaux"] = dict(tri)


def comptes_veille(c: dict[str, Any]) -> None:
    m = charger_yaml(DATA / "veille-state.yaml") or {}
    c["veille.manifeste"] = len(m)
    c["veille.status"] = dict(Counter((v or {}).get("status", "?") for v in m.values()))
    c["veille.ack"] = sum(1 for v in m.values() if (v or {}).get("ack"))
    c["veille.maj_refusee"] = sum(1 for v in m.values() if (v or {}).get("maj_refusee"))
    c["veille.audit"] = sum(1 for v in m.values() if (v or {}).get("audit"))


_TOTAL_PROSP = re.compile(r"(\d+) appel\(s\)\s+[\d  ]+ jetons entrée / [\d  ]+ sortie\s+\$([\d.]+)")
_TOTAL_ING = re.compile(r"(\d+)/(\d+) aide\(s\) ingérée\(s\)\. (\d+) appel\(s\).*\$([\d.]+)")
_TOTAL_FICHES = re.compile(
    r"(\d+) fiche\(s\) écrite\(s\) sur (\d+) · (\d+) appel\(s\) · ([\d.]+) \$"
)


def comptes_journaux(c: dict[str, Any]) -> None:
    c["journaux.ingest_racine"] = len(list(LOGS.glob("ingest-*.log")))
    c["journaux.veille_racine"] = len(list(LOGS.glob("veille-*.log")))
    bal = LOGS / "balayage"
    for run in ("2026-09-18-0052", "2026-09-29-0053"):
        appels = cout = 0.0
        n = 0
        for chemin in sorted(bal.glob(f"{run}-prospection-*.log")):
            n += 1
            for m in _TOTAL_PROSP.finditer(chemin.read_text(encoding="utf-8", errors="replace")):
                appels += int(m.group(1))
                cout += float(m.group(2))
        c[f"balayage.{run}.territoires"] = n
        c[f"balayage.{run}.prospection_appels"] = int(appels)
        c[f"balayage.{run}.prospection_cout_usd"] = round(cout, 4)
    for chemin in sorted(bal.glob("*-ingestion.log")):
        for m in _TOTAL_ING.finditer(chemin.read_text(encoding="utf-8", errors="replace")):
            c[f"balayage.{chemin.stem}"] = {
                "ok": int(m.group(1)),
                "aides": int(m.group(2)),
                "appels": int(m.group(3)),
                "cout_usd": float(m.group(4)),
            }
    for chemin in sorted(bal.glob("*-fiches.log")):
        for m in _TOTAL_FICHES.finditer(chemin.read_text(encoding="utf-8", errors="replace")):
            c[f"balayage.{chemin.stem}"] = {
                "ecrites": int(m.group(1)),
                "sur": int(m.group(2)),
                "appels": int(m.group(3)),
                "cout_usd": float(m.group(4)),
            }
    for chemin in sorted(bal.glob("*-relecture-echecs.log")):
        for m in _TOTAL_PROSP.finditer(chemin.read_text(encoding="utf-8", errors="replace")):
            c[f"balayage.{chemin.stem}"] = {
                "appels": int(m.group(1)),
                "cout_usd": float(m.group(2)),
            }
    reviews = DATA / "reviews"
    # Même total lu dans les fiches de prospection : elles comptent aussi les
    # territoires passés hors balayage le même jour.
    for jour in ("2026-09-18", "2026-09-29", "2026-10-04"):
        appels = cout = 0.0
        n = 0
        for chemin in sorted(reviews.glob(f"{jour}-prospection-*.md")):
            m = re.search(r"(\d+) appel\(s\).*?\$([\d.]+)", chemin.read_text(encoding="utf-8"))
            if m:
                n += 1
                appels += int(m.group(1))
                cout += float(m.group(2))
        c[f"fiches_prospection.{jour}"] = {
            "fiches": n,
            "appels": int(appels),
            "cout_usd": round(cout, 4),
        }
    ingest = list(reviews.glob("*-ingest-*.md"))
    c["reviews.ingest"] = len(ingest)
    c["reviews.ingest_a_trancher"] = sum(
        1
        for p in ingest
        if "## ⚠ À trancher — bloquants non re-vérifiés"
        in p.read_text(encoding="utf-8", errors="replace")
    )
    c["reviews.ingest_hors_perimetre"] = sum(
        1
        for p in ingest
        if "Écartée à l'ingestion — hors périmètre"
        in p.read_text(encoding="utf-8", errors="replace")
    )
    c["reviews.prospection"] = len(list(reviews.glob("*-prospection-*.md")))
    c["reviews.etiquettes_veille_jev_cochees"] = sum(
        1
        for ligne in (reviews / "2026-10-04-etiquettes-veille-jev.md")
        .read_text(encoding="utf-8")
        .splitlines()
        if re.match(r"- \[[xX]\] ", ligne)
    )


# ---------------------------------------------------------------------------
# Vérités terrain : fichiers cités et leur taille
# ---------------------------------------------------------------------------

R = "backend/data/reviews/"
L = "backend/data/reviews/logs/"
RE_ = L + "refonte-entrees/"

VERITES: dict[str, dict[str, str]] = {
    "banc-destinataire": {
        "chemin": L + "benchmark-destinataire/jev.jsonl",
        "mesure": "lignes",
        "provenance": (
            "étiquette = règle de code (benchmark_destinataire.cas_etiquetes) : gardée = YAML au "
            "commit, écartée = tâche ignore « test du destinataire » ou « tri humain » + .yaml.echec ; "
            "412 des 465 écartées viennent du tri LLM du 2026-09-22 validé en bloc par Félix, 53 du "
            "tri humain du 2026-09-30 (notes/destinataire.md)"
        ),
        "bruit": "36 étiquettes retournées sur 78 désaccords relus à l'aveugle le 2026-10-04 (borne basse 3,4 %)",
    },
    "banc-destinataire-llm": {
        "chemin": L + "benchmark-destinataire/llm-or-glm.jsonl",
        "mesure": "lignes",
        "provenance": "mêmes étiquettes que banc-destinataire ; réponses or-glm en cache",
        "bruit": "idem banc-destinataire",
    },
    "banc-destinataire-variante": {
        "chemin": L + "benchmark-destinataire/variante.jsonl",
        "mesure": "lignes",
        "provenance": "réponses Jev à la question reformulée deposable_un",
        "bruit": "idem banc-destinataire",
    },
    "requalif-2026-09-22": {
        "chemin": R + "2026-09-22-tri-catalogue.md",
        "mesure": "octets",
        "provenance": "LLM (rôle lecture) sur YAML + review, fiche validée et corrigée par Félix en bloc",
        "bruit": "62 slugs « à écarter » jamais renommés (notes/destinataire.md) ; jugé sur le YAML, pas la page",
    },
    "requalif-2026-10-04": {
        "chemin": R + "2026-10-04-requalification-jev.md",
        "mesure": "octets",
        "provenance": "78 désaccords Jev/étiquette relus à l'aveugle par des sous-agents Claude, puis Félix",
        "bruit": "16 doutes restés ouverts",
    },
    "desaccords-2026-10-04": {
        "chemin": RE_ + "d2ecd4a8-requalification-2026-10-04/desaccords.json",
        "mesure": "json",
        "provenance": "Claude (sous-agents), relecture à l'aveugle",
        "bruit": "aucun double étiquetage",
    },
    "jev-titres-reels": {
        "chemin": RE_ + "d6fb7845-jev-reel-2026-10-04/tri_reel_titres.jsonl",
        "mesure": "lignes",
        "provenance": "titres d'une vraie collecte, verdict du tri LLM (pas d'humain)",
        "bruit": "aucune étiquette humaine",
    },
    "jev-residu-file": {
        "chemin": RE_ + "d6fb7845-jev-reel-2026-10-04/jev113_259.jsonl",
        "mesure": "lignes",
        "provenance": "notes Jev sur 259 a_valider ; référence des arbitrages : Claude",
        "bruit": "aucune étiquette de Félix",
    },
    "paires-faits": {
        "chemin": RE_ + "be997c31-bilan-2026-10-07/paires_etiquetees.json",
        "mesure": "json",
        "provenance": (
            "positives = fusions décidées à la main (data/fusions/) ; négatives = règle (faits "
            "approuvés dont la justification de l'un cite l'autre)"
        ),
        "bruit": "négatives non jugées paire par paire",
    },
    "transitions-typage": {
        "chemin": RE_ + "be997c31-bilan-2026-10-07/transitions.json",
        "mesure": "json",
        "provenance": "changements de typage relevés dans l'historique git (retypages Claude approuvés par Félix, scripts)",
        "bruit": "un retypage en masse n'est pas un jugement par condition",
    },
    "destin-pending": {
        "chemin": RE_ + "be997c31-bilan-2026-10-07/destin_pending.json",
        "mesure": "json",
        "provenance": "devenir des faits passés par facts_pending.yaml (git)",
        "bruit": "approbations en bloc (471 le 2026-09-17)",
    },
    "fusions-lot-2": {
        "chemin": "backend/data/fusions/lot-2-fusions-cle-pour-cle.yaml",
        "mesure": "yaml",
        "provenance": "table écrite par Claude, relue par Félix",
        "bruit": "approuvée en bloc",
    },
    "fusions-lot-3": {
        "chemin": "backend/data/fusions/lot-3-decisions-humaines.yaml",
        "mesure": "yaml",
        "provenance": "inventaire de cas « à décision humaine » (en-tête du fichier)",
        "bruit": "inventaire, pas une migration appliquée",
    },
    "fusions-revue-pending": {
        "chemin": "backend/data/fusions/2026-10-07-revue-pending-prospection.yaml",
        "mesure": "yaml",
        "provenance": "revue de facts_pending du 2026-10-07 (worktree prospection), Claude + Félix",
        "bruit": "petite taille",
    },
    "lot-4-engagements": {
        "chemin": "backend/data/fusions/lot-4-engagements-approuves.yaml",
        "mesure": "yaml",
        "provenance": "retypage des s_engage_* (promesses), règle + relecture",
        "bruit": "règle de préfixe appliquée en masse",
    },
    "lot-5-critere-demarche": {
        "chemin": "backend/data/fusions/lot-5-critere-demarche.yaml",
        "mesure": "yaml",
        "provenance": "classement de 457 faits par quatre agents Claude, validé par Félix le 2026-09-23 ; 31 faits tranchés nommément",
        "bruit": "validation en bloc hors des 31 cas nommés",
    },
    "tri-critere-demarche": {
        "chemin": R + "2026-09-23-tri-critere-demarche.md",
        "mesure": "octets",
        "provenance": "même revue (457 faits, 1 762 gates)",
        "bruit": "« À relire : c'est une proposition, pas un verdict » (l. 14)",
    },
    "doublons-url": {
        "chemin": "backend/data/doublons/2026-09-22-doublons-url.yaml",
        "mesure": "yaml",
        "provenance": "dedoublonner_aides.py --dry-run (règle par URL), relu par Claude/Félix",
        "bruit": "survivant choisi sur critères formels",
    },
    "doublons-arbitres": {
        "chemin": "backend/data/doublons/2026-09-24-doublons-arbitres.yaml",
        "mesure": "yaml",
        "provenance": "arbitrage à la main (en-tête du fichier)",
        "bruit": "petite taille",
    },
    "pieces-mapping": {
        "chemin": R + "pieces-mapping-2026-08-12.yaml",
        "mesure": "yaml",
        "provenance": "proposé par un LLM (map_pieces.py --proposer), relu à la main avant --appliquer",
        "bruit": "un libellé absent du mapping n'est pas une étiquette négative",
    },
    "familles-proposition": {
        "chemin": R + "2026-09-16-proposition-familles.md",
        "mesure": "octets",
        "provenance": "proposer_familles.py (règles, dont tri.jsonl écrit par le LLM du tri), relu au diff",
        "bruit": "la docstring attribue tri.jsonl à un humain : c'est le LLM du tri",
    },
    "familles-backfill": {
        "chemin": R + "2026-09-22-backfill-familles-faire-vivre.md",
        "mesure": "octets",
        "provenance": "backfill Claude, relu au diff",
        "bruit": "relecture en bloc",
    },
    "raisons-audit": {
        "chemin": R + "2026-09-16-audit-raisons.md",
        "mesure": "octets",
        "provenance": "auditer_raisons.py (signaux de code), tranché à la main",
        "bruit": "seules les aides bi-raison",
    },
    "gate-porteur": {
        "chemin": R + "2026-09-17-proposition-gate-porteur.md",
        "mesure": "octets",
        "provenance": "proposer_gate_porteur.py (règle, citation recontrôlée), relu au diff",
        "bruit": "seules les aides d'entreprise",
    },
    "porteurs-concernes": {
        "chemin": R + "2026-09-17-relecture-porteurs-concernes.md",
        "mesure": "octets",
        "provenance": "relecture du marqueur porteurs_concernes",
        "bruit": "petit volume",
    },
    "veille-jev-cas": {
        "chemin": L + "veille-jev/cas-2026-10-04.json",
        "mesure": "json",
        "provenance": "146 cas (87 reconstruits, 40 en direct, 4 golds, 15 refontes) ; étiquettes cochées par Claude ou d'office par règle (notes/veille.md)",
        "bruit": "aucune étiquette de Félix ; 24 « touche » d'office",
    },
    "veille-jev-etiquettes": {
        "chemin": R + "2026-10-04-etiquettes-veille-jev.md",
        "mesure": "octets",
        "provenance": "cases cochées (Claude, règle)",
        "bruit": "idem veille-jev-cas",
    },
    "veille-etage-c": {
        "chemin": L + "veille-jev/etage-c.jsonl",
        "mesure": "lignes",
        "provenance": "banc de l'étage C (10 configurations sur les mêmes cas)",
        "bruit": "essais non indépendants",
    },
    "veille-golds": {
        "chemin": "backend/data/veille-golds.yaml",
        "mesure": "yaml",
        "provenance": "cas fabriqués à la main sur snapshots réels (Claude)",
        "bruit": "modifications synthétiques",
    },
    "veille-golds-audit": {
        "chemin": "backend/data/veille-golds-audit.yaml",
        "mesure": "yaml",
        "provenance": "cas fabriqués (Claude)",
        "bruit": "5 cas",
    },
    "catalogue-yaml": {
        "chemin": "backend/data/aides",
        "mesure": "glob",
        "provenance": "sortie du pipeline mesuré, relue au diff (souvent en bloc) : pas une vérité terrain",
        "bruit": "62 « à écarter » jamais renommés ; typages antérieurs à la doctrine actuelle",
    },
    "fiches-incoherences": {
        "chemin": R + "2026-09-23-fiches-incoherences.md",
        "mesure": "octets",
        "provenance": "relevé d'incohérences des fiches rédigées (Claude), points à trancher",
        "bruit": "pas un jeu par fiche",
    },
}


#: Classe de provenance de chaque jeu, du plus au moins fiable : « felix » (des
#: décisions de Félix cas par cas y figurent, même en partie), « bloc » (proposé
#: par un LLM ou Claude, approuvé en bloc par Félix), « claude » (Claude seul),
#: « regle » (règle de code ou sortie du pipeline mesuré).
CLASSES: dict[str, str] = {
    "banc-destinataire": "felix",
    "banc-destinataire-llm": "felix",
    "banc-destinataire-variante": "felix",
    "requalif-2026-09-22": "bloc",
    "requalif-2026-10-04": "felix",
    "desaccords-2026-10-04": "claude",
    "jev-titres-reels": "regle",
    "jev-residu-file": "claude",
    "paires-faits": "bloc",
    "transitions-typage": "bloc",
    "destin-pending": "bloc",
    "fusions-lot-2": "bloc",
    "fusions-lot-3": "felix",
    "fusions-revue-pending": "bloc",
    "lot-4-engagements": "bloc",
    "lot-5-critere-demarche": "felix",
    "tri-critere-demarche": "felix",
    "doublons-url": "bloc",
    "doublons-arbitres": "felix",
    "pieces-mapping": "bloc",
    "familles-proposition": "bloc",
    "familles-backfill": "bloc",
    "raisons-audit": "bloc",
    "gate-porteur": "bloc",
    "porteurs-concernes": "bloc",
    "veille-jev-cas": "claude",
    "veille-jev-etiquettes": "claude",
    "veille-etage-c": "claude",
    "veille-golds": "claude",
    "veille-golds-audit": "claude",
    "catalogue-yaml": "regle",
    "fiches-incoherences": "claude",
}
RANG_CLASSE = {"felix": 0, "bloc": 1, "claude": 2, "regle": 3}


def mesurer_verites(c: dict[str, Any]) -> list[tuple[str, str, str, str, str]]:
    sortie = []
    for cle, v in VERITES.items():
        chemin = RACINE / v["chemin"]
        if not chemin.exists():
            taille = "ABSENT"
        elif v["mesure"] == "lignes":
            taille = f"{_lignes_fichier(chemin)} lignes"
        elif v["mesure"] == "json":
            taille = json.dumps(_taille_json(chemin), ensure_ascii=False)
        elif v["mesure"] == "yaml":
            taille = f"{_entrees_yaml(chemin)} entrées"
        elif v["mesure"] == "glob":
            taille = f"{len(list(chemin.glob('*.yaml')))} .yaml, {len(list(chemin.glob('*.yaml.echec')))} .yaml.echec"
        else:
            taille = f"{chemin.stat().st_size} octets, {len(lignes(v['chemin']))} lignes"
        c[f"verite.{cle}"] = taille
        sortie.append((cle, v["chemin"], taille, v["provenance"], v["bruit"]))
    return sortie


# ---------------------------------------------------------------------------
# Carte des étages
# ---------------------------------------------------------------------------

P = S + "prospection/"
ING = S + "ingestion/"


def etages() -> list[dict[str, str]]:
    a = ancre
    return [
        # --- Prospection ---------------------------------------------------
        dict(
            id="P0",
            chaine="prospection",
            nom="Recette du territoire",
            op="O1",
            decideur="Félix ou Claude à la main ; deviner-sites : annuaire (code) puis LLM en repli",
            modele="rôle decouverte pour deviner-sites (LLM_MODEL_DECOUVERTE, or-glm dans .env.local)",
            entree="sondage manuel du site ; annuaire service-public pour un département",
            sortie="bloc YAML par territoire (guides, stratégie, motifs, en-têtes, statut)",
            cout="non mesuré (temps humain)",
            volume="[[territoires.total]] territoires, statuts [[territoires.statut]]",
            ou=", ".join(
                [
                    a(P + "territoires.py", r"^Statut = Literal"),
                    a(S + "prospecter.py", r"^def cmd_deviner_sites"),
                    a(P + "annuaire.py", r"^def sites_departementaux"),
                ]
            ),
        ),
        dict(
            id="P1",
            chaine="prospection",
            nom="Collecte et dédoublonnage",
            op="O1",
            decideur="code ; LLM pour les préfixes d'un site en découverte",
            modele="rôle decouverte (≤ 3 préfixes, filtrés par le code)",
            entree="recette, catalogue (url_officielle, formulaire_url), file entière",
            sortie="candidats.jsonl (url, titre, extrait ≤ 300 car., documents ≤ 25)",
            cout="0 $ hors découverte (1 appel par territoire en découverte)",
            volume="non recompté ici (notes/trouver-source.md) ; dossiers locaux : [[prospection.dossiers_lectures]]",
            ou=", ".join(
                [
                    a(P + "collecte.py", r"^def collecter"),
                    a(P + "collecte.py", r"^def _prefixes_probables"),
                    a(P + "collecte.py", r"^def dedoublonner"),
                ]
            ),
        ),
        dict(
            id="P2",
            chaine="prospection",
            nom="Tri sur titre",
            op="O3",
            decideur="LLM, garde-fous de code (oubli et lot en panne → douteux)",
            modele="rôle tri : or-glm (.env.local) ; ds-v41 imposé par balayage.py",
            entree="lots de 25 (URL, titre, contexte) ; doctrine du skill + familles + aides du territoire",
            sortie="tri.jsonl : retenir | douteux | ecarter, famille, motif",
            cout="compris dans le coût de prospection : [[balayage.2026-09-29-0053.prospection_cout_usd]] $ pour [[balayage.2026-09-29-0053.prospection_appels]] appels sur [[balayage.2026-09-29-0053.territoires]] territoires (tous rôles)",
            volume="environ 68 % écartées par vague (notes/tri-titre.md)",
            ou=", ".join(
                [
                    a(P + "tri.py", r"^TAILLE_LOT"),
                    a(P + "tri.py", r"^def prompt_systeme"),
                    a(P + "tri.py", r"^def trier_lot"),
                ]
            ),
        ),
        dict(
            id="P3a",
            chaine="prospection",
            nom="Arbitrage Jev avant la lecture",
            op="O3",
            decideur="Jev (bandes) + règle de cohérence en code",
            modele="typesafe/jev-1.13 (DECISION_MODEL), seuils 0,12 / 0,57 (JEV_SEUIL_BAS/HAUT)",
            entree="doctrine (INTRO + skill étapes 2-3) + page ≤ 25 000 car.",
            sortie="Arbitrage : deposable, destinataire, objet, dispositif, categorie_ecart, bande",
            cout="banc : 0,6189 $ pour 1 048 pages (2026-10-04-benchmark-destinataire.md:68)",
            volume="[[prospection.lectures_avec_arbitrage_jev]] arbitrage dans les [[prospection.lectures]] lectures locales : jamais lancé en balayage",
            ou=", ".join(
                [
                    a(P + "arbitre.py", r"^SEUIL_BAS"),
                    a(P + "arbitre.py", r"^QUESTIONS"),
                    a(P + "arbitre.py", r"^def bande"),
                    a(P + "lecture.py", r"arbitre_mod\.arbitrer\("),
                ]
            ),
        ),
        dict(
            id="P3b",
            chaine="prospection",
            nom="Lecture LLM d'une page",
            op="O3",
            decideur="LLM (jugements descriptifs + extraction)",
            modele="rôle lecture : or-glm (.env.local) ; ds-v41 dans balayage.py",
            entree="page ou PDF ≤ 25 000 car., documents liés, consigne complète (même en bande retenue)",
            sortie="LectureFiche (destinataire, objet, categorie_ecart, famille, note, urls_pdf, doublon_probable, priorite, source_unique_vulgarisation)",
            cout="banc : 0,6642 $ pour 1 045 pages (2026-10-04-benchmark-destinataire.md:18)",
            volume="505 à 679 pages par vague (cartographie/prospection.md, non recompté)",
            ou=", ".join(
                [
                    a(P + "lecture.py", r"^class LectureFiche"),
                    a(P + "lecture.py", r"^def lire"),
                    a(P + "lecture.py", r"system=consigne\(skill_path\)"),
                ]
            ),
        ),
        dict(
            id="P3c",
            chaine="prospection",
            nom="Dérivation du verdict d'entrée et correction Jev",
            op="O3",
            decideur="code",
            modele="aucun",
            entree="destinataire, objet, categorie_ecart ; bande Jev",
            sortie="retenue | indéterminée | écartée ; note préfixée de la correction",
            cout="0 $",
            volume="chaque page lue",
            ou=", ".join(
                [
                    a(S + "pipeline/etat.py", r"^def retenir"),
                    a(S + "pipeline/etat.py", r"^def indetermine"),
                    a(P + "lecture.py", r"^def _appliquer_arbitrage"),
                ]
            ),
        ),
        dict(
            id="P4",
            chaine="prospection",
            nom="Slugs, fiche de prospection, fusion dans la file",
            op="O12",
            decideur="code",
            modele="aucun",
            entree="lectures abouties, slugs occupés",
            sortie="data/reviews/<date>-prospection-<territoire>.md ; tâches a_valider ou ignore + motif",
            cout="0 $",
            volume="[[reviews.prospection]] fiches de prospection",
            ou=", ".join(
                [
                    a(P + "fiche.py", r"^def rendre_fiche"),
                    a(P + "fiche.py", r"^def taches"),
                    a(P + "lecture.py", r"^def slug_final"),
                    a(S + "pipeline/etat.py", r"^def fusionner"),
                ]
            ),
        ),
        dict(
            id="P5",
            chaine="prospection",
            nom="Promotion a_valider → valide",
            op="O11",
            decideur="code (promouvables) dans --auto, valider --tout et balayage ; Félix pour un slug nommé",
            modele="aucun",
            entree="tâches a_valider",
            sortie="valide, ignore (doublon d'URL), ou maintien avec motif imprimé",
            cout="temps humain",
            volume="[[file.statut.a_valider]] a_valider : [[file.a_valider.indetermine]] indéterminées, [[file.a_valider.famille_non_promouvable]] bloquées par la famille, [[file.a_valider.promouvable]] promouvables",
            ou=", ".join(
                [
                    a(S + "pipeline/etat.py", r"^def motif_non_promotion"),
                    a(S + "prospecter.py", r"^def _transitionner"),
                    a(S + "prospecter.py", r"^def _enchainer"),
                    a(S + "balayage.py", r"^def valider_en_attente"),
                ]
            ),
        ),
        dict(
            id="P6",
            chaine="prospection",
            nom="Annexes : relire, requalifier, comparer",
            op="O3",
            decideur="LLM + Jev (relire) ; LLM puis Félix (requalifier) ; code (comparer)",
            modele="rôle lecture (+ Jev pour relire)",
            entree="échecs de panne ; YAML + review ; liste d'URL externe",
            sortie="tâche requalifiée ; fiche de tri ; trois listes imprimées",
            cout="relecture des échecs 2026-09-29 : [[balayage.2026-09-29-0053-relecture-echecs]]",
            volume="requalification du 2026-09-22 : 950 aides (2026-09-22-tri-catalogue.md:3)",
            ou=", ".join(
                [
                    a(S + "prospecter.py", r"^def cmd_relire"),
                    a(S + "prospecter.py", r"^def cmd_requalifier"),
                    a(P + "requalification.py", r"^class Requalification"),
                    a(S + "prospecter.py", r"^def cmd_comparer"),
                ]
            ),
        ),
        # --- Ingestion -----------------------------------------------------
        dict(
            id="I0",
            chaine="ingestion",
            nom="Sélection, réservation, budgets",
            op="O4",
            decideur="code",
            modele="aucun",
            entree="tâches valide (ou --slug direct, hors file)",
            sortie="jeton en_cours, ThreadPool de --parallele workers",
            cout="budget 1,50 $ par aide, 50 $ par run (60 $ dans balayage)",
            volume="[[file.avec_bloc_ingestion]] tâches avec un bloc ingestion",
            ou=", ".join(
                [
                    a(S + "pipeline/etat.py", r"^def selectionner"),
                    a(ING + "orchestrateur.py", r"^def executer"),
                    a(ING + "orchestrateur.py", r"^def _budget_epuise"),
                ]
            ),
        ),
        dict(
            id="I1",
            chaine="ingestion",
            nom="Contexte partagé et gabarit",
            op="O4",
            decideur="code (choix du gabarit par classement lexicographique)",
            modele="aucun",
            entree="skill ingest-aide, extraits README/TYPING, schéma, facts + pending, catalogue",
            sortie="prompt système commun ; message initial avec consignes de prospection et gabarit ≤ 40 000 car.",
            cout="0 $ (préfixe mis en cache chez le fournisseur)",
            volume="1 par run et 1 par aide",
            ou=", ".join(
                [
                    a(ING + "contexte.py", r"^def prompt_systeme"),
                    a(ING + "contexte.py", r"^def prompt_initial"),
                    a(ING + "contexte.py", r"^def choisir_aide_reference"),
                ]
            ),
        ),
        dict(
            id="I2",
            chaine="ingestion",
            nom="Sources et snapshots",
            op="O2",
            decideur="LLM (quoi lire, quoi archiver) ; code (téléchargement, conversion, archivage)",
            modele="rôle ingestion : or-glm (.env.local) ; ds-v41 dans balayage.py",
            entree="URL et PDF de la tâche, liens suivis",
            sortie="data/sources/<slug>/<date>[-label].md|.pdf (+ sidecar)",
            cout="compris dans l'agent",
            volume="non recompté ici (notes/ingestion-journaux.md)",
            ou=", ".join(
                [
                    a(ING + "outils.py", r"def explorer_url\("),
                    a(ING + "outils.py", r"def snapshotter\("),
                    a(S + "snapshot_source.py", r"^def write_md_snapshot"),
                ]
            ),
        ),
        dict(
            id="I3",
            chaine="ingestion",
            nom="Périmètre révélé par la source",
            op="O3",
            decideur="LLM (agent), contrôles de forme en code",
            modele="rôle ingestion",
            entree="snapshots lus",
            sortie="arrêt, fiche courte, tâche ignore",
            cout="le coût de l'agent jusqu'à la déclaration",
            volume="[[reviews.ingest_hors_perimetre]] fiches d'ingestion « hors périmètre » sur [[reviews.ingest]] ; [[file.ignore.motif.hors périmètre à l'ingestion]] motifs dans la file",
            ou=", ".join(
                [
                    a(ING + "outils.py", r"def declarer_hors_perimetre\("),
                    a(ING + "orchestrateur.py", r"if resultat\.hors_perimetre is not None"),
                ]
            ),
        ),
        dict(
            id="I4",
            chaine="ingestion",
            nom="Extraction et typage des conditions",
            op="O5",
            decideur="LLM (agent), schéma et lint en code",
            modele="rôle ingestion",
            entree="snapshots, doctrine TYPING via le skill, index des faits",
            sortie="YAML entier réécrit à chaque ecrire_aide",
            cout="0,035 $ par aide hors vérification (or-glm, banc 2026-10-07, cartographie/modeles.md)",
            volume="[[aides.conditions]] conditions au catalogue",
            ou=", ".join(
                [
                    a(ING + "outils.py", r"def ecrire_aide\("),
                    a(ING + "outils.py", r"def _audit_citations\("),
                    a(".claude/skills/ingest-aide/SKILL.md", r"^## Étape 2"),
                ]
            ),
        ),
        dict(
            id="I5",
            chaine="ingestion",
            nom="Faits : chercher, proposer, retirer",
            op="O6",
            decideur="LLM (agent) ; refus en code (plafond 3, forme, proximité 0,68 non lue)",
            modele="rôle ingestion",
            entree="exigences de la source, index des faits",
            sortie="fact: existant ou bloc ajouté à facts_pending.yaml",
            cout="compris dans l'agent",
            volume="facts.yaml [[faits.facts]] faits, facts_pending [[faits.pending]]",
            ou=", ".join(
                [
                    a(ING + "faits.py", r"^def proposer"),
                    a(ING + "faits.py", r"^SEUIL_PROXIMITE"),
                    a(ING + "faits.py", r"^MAX_FAITS_PAR_AIDE"),
                    a(ING + "faits.py", r"^def _refus_de_forme"),
                ]
            ),
        ),
        dict(
            id="I6",
            chaine="ingestion",
            nom="Écriture, audit des citations, lint",
            op="O8",
            decideur="code",
            modele="aucun",
            entree="YAML complet",
            sortie="fichier écrit si le schéma passe ; rapport de lint mono-slug",
            cout="0 $",
            volume="par écriture",
            ou=", ".join(
                [
                    a(ING + "outils.py", r"def ecrire_aide\("),
                    a(ING + "outils.py", r"    def lint\(\)"),
                    a(S + "lint_aides_data.py", r"^def lint\("),
                ]
            ),
        ),
        dict(
            id="I7",
            chaine="ingestion",
            nom="Vérification adversariale",
            op="O7",
            decideur="LLM vérificateur ; plafond 3 en code",
            modele="rôle verification : or-ds41 (.env.local) ; ds-v41 dans balayage.py",
            entree="sources ≤ 120 000 car./document, YAML, audit des citations, verdicts précédents",
            sortie="RapportVerification (axe, sévérité, qualite_source)",
            cout="ds-pro 2,6 ¢ par aide, or-glm 0,11 ¢ (2026-09-06-benchmark-ingestion.md, cité par cartographie/modeles.md)",
            volume="[[file.ingestion.a_relire]] tâches a_relire dans la file",
            ou=", ".join(
                [
                    a(ING + "outils.py", r"def verification_adversariale\("),
                    a(ING + "verification.py", r"^def verifier"),
                    a(ING + "outils.py", r"^MAX_VERIFICATIONS"),
                ]
            ),
        ),
        dict(
            id="I8",
            chaine="ingestion",
            nom="Fiche de review",
            op="O12",
            decideur="LLM (rédaction) ; refus en code",
            modele="rôle ingestion",
            entree="état de l'agent, rapport de vérification",
            sortie="data/reviews/<date>-ingest-<slug>.md, bloc « À trancher » si a_relire",
            cout="compris dans l'agent",
            volume="[[reviews.ingest]] fiches d'ingestion, [[reviews.ingest_a_trancher]] avec « À trancher » en tête",
            ou=", ".join(
                [
                    a(ING + "outils.py", r"def ecrire_review\("),
                    a(ING + "outils.py", r"^MIN_CAR_REVIEW"),
                ]
            ),
        ),
        dict(
            id="I9",
            chaine="ingestion",
            nom="Post-contrôles, verdict, consignation",
            op="O7",
            decideur="code (10 contrôles, statut final, disjoncteur)",
            modele="aucun",
            entree="atelier, résultat de boucle, état des outils",
            sortie="ingere | valide (panne) | echec | ignore ; .yaml.echec si un contrôle échoue",
            cout="0 $",
            volume="[[file.statut.ingere]] ingere, [[file.statut.echec]] echec ; [[aides.yaml_echec]] .yaml.echec au catalogue",
            ou=", ".join(
                [
                    a(ING + "worker.py", r"^def controler"),
                    a(ING + "orchestrateur.py", r"^def _statut_final"),
                    a(ING + "orchestrateur.py", r"^class Disjoncteur"),
                    a(ING + "boucle.py", r"^def classe_erreur"),
                ]
            ),
        ),
        dict(
            id="I10",
            chaine="ingestion",
            nom="Audit d'ontologie de fin de run",
            op="O6",
            decideur="code (pré-filtre 0,60, 60 paires) puis LLM ; rien n'est appliqué",
            modele="rôle audit : or-ds41 (.env.local) ; ds-v41 dans balayage.py",
            entree="facts + pending relus du disque",
            sortie="rapport console (fusions proposées, orphelins, polarités)",
            cout="1 appel par run",
            volume="2026-09-29 : 60 paires jugées « distinctes » par le LLM (logs/balayage/2026-09-29-0053-ingestion.log)",
            ou=", ".join(
                [
                    a(ING + "ontologie.py", r"^SEUIL_AUDIT"),
                    a(ING + "ontologie.py", r"^def auditer"),
                    a(S + "ingerer.py", r"^def _auditer_ontologie"),
                ]
            ),
        ),
        dict(
            id="I11",
            chaine="ingestion",
            nom="Bilan de run",
            op="O12",
            decideur="code",
            modele="aucun",
            entree="résultats du run",
            sortie="tableau console ; bilan markdown dans balayage.py",
            cout="0 $",
            volume="1 par run",
            ou=", ".join(
                [
                    a(ING + "orchestrateur.py", r"^def bilan"),
                    a(S + "balayage.py", r"^def bilan_balayage"),
                ]
            ),
        ),
        # --- Veille --------------------------------------------------------
        dict(
            id="V0",
            chaine="veille",
            nom="Sélection et ordre de passage",
            op="O9",
            decideur="code (ancienneté)",
            modele="aucun",
            entree="aides, manifeste",
            sortie="ordre de passage",
            cout="0 $",
            volume="[[veille.manifeste]] entrées au manifeste",
            ou=a(S + "veille_aides.py", r"^def anciennete"),
        ),
        dict(
            id="V1",
            chaine="veille",
            nom="Étage A : collecte",
            op="O9",
            decideur="code",
            modele="aucun",
            entree="URL surveillées, snapshots comme baselines",
            sortie="AideCollect",
            cout="0 $ ; 4,1 min collecte + analyse le 2026-10-04 (cartographie/veille.md)",
            volume="1 439 URL (cartographie/veille.md, non recompté)",
            ou=", ".join(
                [
                    a(S + "veille_collect.py", r"^def monitored_urls"),
                    a(S + "veille_collect.py", r"^def collect\("),
                ]
            ),
        ),
        dict(
            id="V2",
            chaine="veille",
            nom="Étage B : analyse et classement",
            op="O9",
            decideur="code (9 règles ordonnées, gabarit appris sur le parc)",
            modele="aucun",
            entree="AideCollect du parc",
            sortie="AideAnalysis : 6 statuts",
            cout="0 $",
            volume="statuts au manifeste : [[veille.status]]",
            ou=", ".join(
                [
                    a(S + "veille_analyze.py", r"^def _decider"),
                    a(S + "veille_analyze.py", r"^def lignes_de_chrome"),
                ]
            ),
        ),
        dict(
            id="V3",
            chaine="veille",
            nom="Tri des refontes par Jev (débranché)",
            op="O9",
            decideur="Jev si SEUIL_REFONTE posé ; None aujourd'hui",
            modele="typesafe/jev-1.13",
            entree="escalades de la règle 6 + pages fraîches",
            sortie="rétrogradation en MAJ_LLM",
            cout="banc veille Jev : 227 notes pour 0,035 $ (cartographie/veille.md)",
            volume="15 refontes le 2026-10-04",
            ou=", ".join(
                [
                    a(S + "veille_arbitre.py", r"^SEUIL_REFONTE"),
                    a(S + "veille_aides.py", r"^def trier_refontes"),
                ]
            ),
        ),
        dict(
            id="V4",
            chaine="veille",
            nom="Filtre Jev avant le LLM (débranché)",
            op="O9",
            decideur="Jev si SEUIL_FILTRE posé ; None aujourd'hui",
            modele="typesafe/jev-1.13",
            entree="diff + fiche réduite",
            sortie="inchangé + ré-archivage sans LLM",
            cout="non engagé",
            volume="117 candidates le 2026-10-04",
            ou=", ".join(
                [
                    a(S + "veille_arbitre.py", r"^SEUIL_FILTRE"),
                    a(S + "veille_update.py", r"^def filtrable"),
                ]
            ),
        ),
        dict(
            id="V5",
            chaine="veille",
            nom="Préparation de l'étage C (mémoire des refus, plafond)",
            op="O10",
            decideur="code ; Félix pour --rearchiver",
            modele="aucun",
            entree="MAJ_LLM, maj_refusee, --max-llm",
            sortie="candidates soumises",
            cout="0 $",
            volume="[[veille.maj_refusee]] refus mémorisés au manifeste",
            ou=", ".join(
                [
                    a(S + "veille_aides.py", r"^def run_stage_c"),
                    a(S + "veille_update.py", r"^MAX_LLM_DEFAUT"),
                ]
            ),
        ),
        dict(
            id="V6",
            chaine="veille",
            nom="Appel LLM de l'étage C",
            op="O10",
            decideur="LLM (un appel par aide, une relance)",
            modele="VEILLE_MODEL=or-glm (.env.local) ; défaut du code glm-flash",
            entree="sections de la fiche, pages modifiées ≤ 60 000 car., diff ≤ 12 000 car.",
            sortie="VeilleLLMOutput (sections, conditions update/add/signaler_disparue, changement_majeur)",
            cout="0,141 $ pour 117 appels le 2026-10-04 (2026-10-04-veille.md:16)",
            volume="117 appels le 2026-10-04",
            ou=", ".join(
                [
                    a(S + "veille_llm.py", r"^SYSTEM = "),
                    a(S + "veille_llm.py", r"^MODELE_DEFAUT"),
                    a(S + "veille_update.py", r"^def mettre_a_jour"),
                ]
            ),
        ),
        dict(
            id="V7",
            chaine="veille",
            nom="Validation, édition par plages, verdict, garde Jev",
            op="O10",
            decideur="code ; Jev en garde (0,45)",
            modele="typesafe/jev-1.13 pour la garde",
            entree="réponse du LLM, documents frais, diff",
            sortie="applique | inchange | escalade | echec | suspect",
            cout="0 $ hors Jev",
            volume="2026-10-04 : 24 appliqués, 74 inchangés, 19 escalades (2026-10-04-veille.md:16, cartographie/veille.md)",
            ou=", ".join(
                [
                    a(S + "veille_apply.py", r"^def appliquer\("),
                    a(S + "veille_arbitre.py", r"^SEUIL_GARDE"),
                    a(S + "veille_update.py", r'res\.etat = "suspect"'),
                ]
            ),
        ),
        dict(
            id="V8",
            chaine="veille",
            nom="Ré-archivage des preuves",
            op="O2",
            decideur="code",
            modele="aucun",
            entree="pages changées hors proxy",
            sortie="nouveau snapshot = nouvelle baseline",
            cout="0 $",
            volume="par page changée",
            ou=a(S + "veille_update.py", r"^def rafraichir_snapshots"),
        ),
        dict(
            id="V9",
            chaine="veille",
            nom="Manifeste, rapport, journal",
            op="O12",
            decideur="code",
            modele="aucun",
            entree="analyses + MajResult",
            sortie="veille-state.yaml, data/reviews/<date>-veille.md, commande d'escalade imprimée",
            cout="0 $",
            volume="[[journaux.veille_racine]] journaux de veille copiés",
            ou=", ".join(
                [
                    a(S + "veille_aides.py", r"^def update_manifest"),
                    a(S + "veille_aides.py", r"^def build_report"),
                    a(S + "veille_aides.py", r"scripts/ingerer\.py \{slugs\}"),
                ]
            ),
        ),
        dict(
            id="V10",
            chaine="veille",
            nom="Aval humain : acquitter, ré-archiver, ré-ingérer, régénérer",
            op="O11",
            decideur="Félix",
            modele="aucun",
            entree="rapport + git diff",
            sortie="commits, commandes lancées",
            cout="temps humain",
            volume="acquittements posés : [[veille.ack]]",
            ou=", ".join(
                [
                    a(S + "veille_aides.py", r"^def traiter_acquittements"),
                    a(S + "veille_aides.py", r'"--acquitter"'),
                ]
            ),
        ),
        dict(
            id="V11",
            chaine="veille",
            nom="Étage D : audit d'exhaustivité (quasi mort)",
            op="O7",
            decideur="LLM",
            modele="VEILLE_MODEL",
            entree="fiche complète + corpus",
            sortie="conforme / absent / divergent ; ajouts en untyped",
            cout="0,048 à 0,052 $ par aide (cartographie/veille.md)",
            volume="audits au manifeste : [[veille.audit]]",
            ou=", ".join(
                [
                    a(S + "veille_audit.py", r"^class CritereAudit"),
                    a(S + "veille_audit.py", r"^MAX_AJOUTS_CONDITIONS"),
                ]
            ),
        ),
        dict(
            id="V12",
            chaine="veille",
            nom="Typage des untyped (veille_typage)",
            op="O5",
            decideur="LLM, validé par les fonctions du lint",
            modele="VEILLE_MODEL",
            entree="conditions untyped, index de l'ontologie",
            sortie="kind, effect, fait, prédicat",
            cout="non mesuré",
            volume="appelé seulement par veille_audit --typer",
            ou=a(S + "veille_typage.py", r"^class TypageCondition"),
        ),
        # --- Fiches ---------------------------------------------------------
        dict(
            id="F1",
            chaine="fiches",
            nom="Rédaction du bloc fiche:",
            op="O8",
            decideur="LLM ; refus en code avec 2 corrections",
            modele="LLM_MODEL_REDACTION jamais posé (il faut --model) ; ds-v41 dans balayage.py",
            entree="skills rediger-fiche + ecriture-propre, fiche étalon, YAML",
            sortie="bloc fiche: réécrit en fin de YAML",
            cout="2026-09-29 : [[balayage.2026-09-29-0053-fiches]]",
            volume="[[aides.fiche]] aides avec fiche sur [[aides.yaml]]",
            ou=", ".join(
                [
                    a(S + "rediger_fiches.py", r"^def controler"),
                    a(S + "rediger_fiches.py", r"^MAX_CORRECTIONS"),
                    a(S + "rediger_fiches.py", r"^def a_relire"),
                ]
            ),
        ),
        # --- Outils d'ontologie et de catalogue -----------------------------
        dict(
            id="T1",
            chaine="ontologie",
            nom="Audit d'ontologie hors run",
            op="O6",
            decideur="code (--sans-modele) ou LLM",
            modele="rôle audit",
            entree="facts + pending",
            sortie="fiche markdown, table de fusion proposée",
            cout="0 $ sans modèle",
            volume="à la main",
            ou=a(S + "auditer_ontologie.py", r"client = None if sans_modele"),
        ),
        dict(
            id="T2",
            chaine="ontologie",
            nom="Fusion et retypage par table",
            op="O6",
            decideur="Félix ou Claude écrivent la table ; le code applique et refuse l'incompatible",
            modele="aucun",
            entree="data/fusions/*.yaml",
            sortie="clés remplacées, conditions retypées, faits retirés",
            cout="temps humain",
            volume="16 tables dans data/fusions/",
            ou=", ".join(
                [
                    a(S + "fusionner_faits.py", r"^def _verifier_compatibilite"),
                    a(S + "retyper_faits.py", r"^def _retyper_condition"),
                ]
            ),
        ),
        dict(
            id="T3",
            chaine="ontologie",
            nom="Approbation des faits proposés",
            op="O6",
            decideur="Félix (en bloc)",
            modele="aucun",
            entree="facts_pending.yaml",
            sortie="sections datées de facts.yaml",
            cout="temps humain",
            volume="[[faits.pending]] fait en attente aujourd'hui",
            ou=a("backend/data/TYPING.md", r"^## Proposer un nouveau fait"),
        ),
        dict(
            id="T4",
            chaine="ontologie",
            nom="Dédoublonnage du catalogue",
            op="O3",
            decideur="code propose, humain corrige la table",
            modele="aucun",
            entree="catalogue groupé par URL",
            sortie="table de survivants, renommage .yaml.echec",
            cout="temps humain",
            volume="2 tables dans data/doublons/",
            ou=", ".join(
                [
                    a(S + "dedoublonner_aides.py", r"^def grouper"),
                    a(S + "dedoublonner_aides.py", r"^def _rang"),
                ]
            ),
        ),
        dict(
            id="T5",
            chaine="ontologie",
            nom="Backfills proposés (familles, gate porteur, raisons, pièces)",
            op="O5",
            decideur="code propose (map_pieces : LLM), humain relit le diff",
            modele="aucun (map_pieces : LLM one-shot)",
            entree="catalogue, snapshots, tri.jsonl",
            sortie="fiches de review, insertions textuelles des cas nets",
            cout="0 $",
            volume="à la main",
            ou=", ".join(
                [
                    a(S + "proposer_familles.py", r"^def proposer"),
                    a(S + "proposer_gate_porteur.py", r"^def analyser"),
                    a(S + "auditer_raisons.py", r"^def _signaux"),
                    a(S + "map_pieces.py", r"^def proposer"),
                ]
            ),
        ),
        dict(
            id="T6",
            chaine="ontologie",
            nom="Lint global et ratchets",
            op="O7",
            decideur="code",
            modele="aucun",
            entree="catalogue, faits, baseline",
            sortie="exit 0/1, avertissements",
            cout="0 $",
            volume="non lancé en CI ni en pre-commit (cartographie/contrat.md)",
            ou=", ".join(
                [
                    a(S + "lint_aides_data.py", r"^def check_manual_check_ratchet"),
                    a(S + "lint_aides_data.py", r"^def check_quotes"),
                ]
            ),
        ),
        # --- Orchestration ---------------------------------------------------
        dict(
            id="B0",
            chaine="orchestration",
            nom="Balayage : garde-fous, pré-vol, enchaînement",
            op="O11",
            decideur="Félix choisit territoires et options ; code applique",
            modele="un appel « ok » par alias, Jev non testé",
            entree="clés de régions, territoires.yaml, balayage.json",
            sortie="prospections, promotion, ingestion unique, fiches, bilan",
            cout="2026-09-29 : prospection [[balayage.2026-09-29-0053.prospection_cout_usd]] $, ingestion [[balayage.2026-09-29-0053-ingestion]]",
            volume="2 balayages journalisés (2026-09-18, 2026-09-29)",
            ou=", ".join(
                [
                    a(S + "balayage.py", r"^def main"),
                    a(S + "balayage.py", r"^def verifier_modeles"),
                    a(S + "balayage.py", r"^def runs_en_cours"),
                    a(S + "balayage.py", r'"--model-tri", default="ds-v41"'),
                ]
            ),
        ),
        dict(
            id="B1",
            chaine="orchestration",
            nom="Clôture humaine : commit, load, deploy",
            op="O11",
            decideur="Félix",
            modele="aucun",
            entree="diff, fiches, bilan",
            sortie="commit, upsert aides_v3",
            cout="temps humain",
            volume="chaque run",
            ou=a(S + "load_aides_yaml.py", r"^def main"),
        ),
    ]


# ---------------------------------------------------------------------------
# Inventaire des décisions fermées
# ---------------------------------------------------------------------------


def decisions(e: dict[str, Any]) -> list[dict[str, Any]]:
    a = ancre
    q = e["arbitre.QUESTIONS"]
    qm = e["veille_arbitre.QUESTIONS_MANDAT"]
    qr = e["veille_arbitre.QUESTIONS_REFONTE"]

    def opts(liste: list[str]) -> str:
        return " | ".join(liste) + f" ({len(liste)})"

    D: list[dict[str, Any]] = []

    def d(ident, chaine, question, options, decideur, ou, op, verites=(), sans=None, volume=""):
        D.append(
            dict(
                id=ident,
                chaine=chaine,
                question=question,
                options=options,
                decideur=decideur,
                ou=ou,
                op=op,
                verites=list(verites),
                sans=sans,
                volume=volume,
            )
        )

    # --- Prospection : trouver une source ----------------------------------
    d(
        "statut-recette",
        "prospection",
        "Statut, stratégie et en-têtes de la recette d'un territoire",
        f"statut {opts(e['territoires.Statut'])} ; stratégie {opts(e['territoires.Strategie.type'])} ; en-têtes {opts(e['territoires.entetes'])}",
        "Félix ou Claude, à la main",
        a(P + "territoires.py", r"^Statut = Literal"),
        "O1",
        sans=(
            "100 territoires × recette rejouée : vérifier que la stratégie ramène la liste du guide",
            3.0,
            0.0,
        ),
        volume="[[territoires.total]] territoires",
    )
    d(
        "guide-departement",
        "prospection",
        "Cette URL est-elle le guide des aides du département ? (deviner-sites)",
        "proposée / rejetée",
        "code (annuaire) puis LLM decouverte en repli, GET de contrôle, humain colle le bloc",
        a(S + "prospecter.py", r"^def cmd_deviner_sites"),
        "O1",
        sans=("100 départements : URL proposée contre guide constaté à la main", 2.0, 0.0),
        volume="114 territoires",
    )
    d(
        "rubrique-decouverte",
        "prospection",
        "Sous quels préfixes d'URL vivent les fiches d'un site inconnu ?",
        "≤ 3 préfixes parmi les liens vus de l'accueil (préfixe inventé jeté par le code)",
        "LLM (rôle decouverte)",
        a(P + "collecte.py", r"^def _prefixes_probables"),
        "O1",
        sans=(
            "100 accueils de sites : préfixes justes contre préfixes des aides ingérées du site",
            2.0,
            0.07,
        ),
        volume="1 appel par territoire en découverte ([[territoires.statut]])",
    )
    d(
        "fiche-probable",
        "prospection",
        "Ce lien est-il une fiche de dispositif ou une page de navigation ? un document ?",
        "fiche / navigation ; document (pdf_probable, est_document)",
        "code (regex motif_fiche écrite par un humain)",
        a(P + "territoires.py", r"def fiche_probable"),
        "O1",
        sans=("100 liens tirés des collectes : fiche ou non, sur titre + URL", 0.3, 0.0),
    )
    d(
        "collecte-bornes",
        "prospection",
        "Page utilisable, chemin en boucle, plafond de candidates atteint ?",
        "utilisable / SPA ou PDF ou erreur ; boucle / non ; plafonnée / non",
        "code (seuil 500 car., segments répétés, max_candidats)",
        ", ".join(
            [
                a(P + "collecte.py", r"^def _page_utilisable"),
                a(P + "collecte.py", r"^def chemin_en_boucle"),
            ]
        ),
        "O1",
        sans=(
            "règle déterministe : 100 pages rejetées relues pour vérifier qu'aucune n'était exploitable",
            0.5,
            0.0,
        ),
    )
    d(
        "doublon-collecte",
        "prospection",
        "La candidate est-elle déjà au catalogue ou dans la file (toutes statuts) ?",
        "nouvelle / doublon catalogue / déjà en file",
        "code (cle_fiche)",
        a(P + "collecte.py", r"^def dedoublonner"),
        "O1",
        verites=["doublons-url"],
    )
    # --- Prospection : juger si elle relève du catalogue --------------------
    d(
        "tri-titre",
        "prospection",
        "Ouvrir la page ou l'écarter, sur titre et contexte ?",
        opts(e["tri.Decision"]),
        "LLM (rôle tri), garde-fous de code",
        ", ".join([a(P + "tri.py", r"^Decision = Literal"), a(P + "tri.py", r"^def trier_lot")]),
        "O3",
        sans=(
            "100 URL écartées au tri (échantillon déjà tiré, notes/tri-titre.md) + 50 leurres : page ouverte et jugée",
            1.5,
            0.0,
        ),
        volume="68 % écartées par vague (notes/tri-titre.md)",
    )
    d(
        "deja-catalogue-titre",
        "prospection",
        "Le titre désigne-t-il une aide déjà au catalogue (écart « déjà au catalogue ») ?",
        "écarter / ne rien dire",
        "LLM (rôle tri), sur la liste des aides du territoire injectée au prompt",
        a(P + "tri.py", r"déjà au catalogue"),
        "O3",
        sans=("100 écarts « déjà au catalogue » : retrouver l'aide nommée", 1.0, 0.0),
    )
    d(
        "famille-tri",
        "prospection",
        "Famille thématique d'une candidate (tri)",
        opts(e["tri.Famille"]),
        "LLM (rôle tri) ; le code rabat hors_perimetre sur adjacente quand la décision n'est pas ecarter",
        ", ".join(
            [a(P + "tri.py", r"^Famille = Literal"), a(P + "tri.py", r'"famille": "adjacente"')]
        ),
        "O5",
        verites=["catalogue-yaml", "familles-proposition", "familles-backfill"],
        volume="familles des a_valider : [[file.familles_a_valider]]",
    )
    for cle, libelle in (
        ("deposable", "Un propriétaire de monument peut-il déposer ? (bandes 0,12 / 0,57)"),
        ("destinataire", "Jev : à qui la source s'adresse-t-elle ?"),
        ("objet", "Jev : sur quoi porte la dépense ?"),
        (
            "dispositif",
            "Jev : la page décrit-elle un dispositif qu'on peut demander ? (seuil 0,5 en code)",
        ),
        ("categorie_ecart", "Jev : pourquoi le propriétaire ne peut pas déposer (motif seulement)"),
    ):
        d(
            f"jev-{cle}",
            "prospection",
            libelle,
            opts(q.get(cle, [])),
            "Jev",
            a(P + "arbitre.py", rf'^    "{cle}": '),
            "O3",
            verites=(
                ["banc-destinataire", "banc-destinataire-variante", "requalif-2026-10-04"]
                if cle in ("deposable", "destinataire", "objet", "dispositif")
                else []
            ),
            sans=(
                None
                if cle != "categorie_ecart"
                else ("100 pages écartées : catégorie juste ou non", 0.5, 0.06)
            ),
            volume="0 appel en production ; banc 1 048 pages",
        )
    d(
        "jev-bande",
        "prospection",
        "Bande d'une page selon Jev (cohérence score / réponses détaillées)",
        opts(e["arbitre.Bande"]),
        "code (bande(), structure_ecarte())",
        ", ".join(
            [a(P + "arbitre.py", r"^def structure_ecarte"), a(P + "arbitre.py", r"^def bande")]
        ),
        "O3",
        verites=["banc-destinataire"],
    )
    d(
        "lecture-destinataire",
        "prospection",
        "Lecture : à qui la source s'adresse-t-elle ?",
        opts(e["etat.DESTINATAIRES"]),
        "LLM (rôle lecture)",
        a(P + "lecture.py", r"^CONSIGNE_DESTINATAIRE"),
        "O3",
        verites=["banc-destinataire-llm", "requalif-2026-09-22"],
    )
    d(
        "lecture-objet",
        "prospection",
        "Lecture : sur quoi porte la dépense ?",
        opts(e["etat.OBJETS"]),
        "LLM (rôle lecture)",
        a(P + "lecture.py", r"^    objet: Objet"),
        "O3",
        verites=["banc-destinataire-llm"],
    )
    d(
        "lecture-categorie",
        "prospection",
        "Lecture : catégorie d'écart (non_dispositif DÉCIDE : jamais retenue, jamais indéterminée)",
        opts(e["etat.CATEGORIES_ECART"]) + " ou vide",
        "LLM (rôle lecture)",
        ", ".join(
            [
                a(P + "lecture.py", r"^    categorie_ecart: CategorieEcart"),
                a(S + "pipeline/etat.py", r'if categorie_ecart == "non_dispositif"'),
            ]
        ),
        "O3",
        sans=(
            "100 tâches ignore non_dispositif ([[file.ignore.categorie.non_dispositif]] dans la file) : page relue",
            1.0,
            0.0,
        ),
    )
    d(
        "verdict-entree",
        "prospection",
        "Issue du test du destinataire",
        "retenue | indéterminée | écartée (3)",
        "code (etat.retenir, etat.indetermine, LectureFiche.retenir)",
        ", ".join(
            [
                a(S + "pipeline/etat.py", r"^def retenir"),
                a(S + "pipeline/etat.py", r"^def indetermine"),
                a(P + "lecture.py", r"    def retenir"),
            ]
        ),
        "O3",
        verites=["banc-destinataire"],
    )
    d(
        "correction-jev",
        "prospection",
        "Le verdict du LLM est-il corrigé par la bande Jev ?",
        "retenue forcée (bande retenue) | renvoyée à un humain (bande milieu + écart LLM) | aucune (3)",
        "code",
        a(P + "lecture.py", r"^def _appliquer_arbitrage"),
        "O11",
        verites=["banc-destinataire"],
    )
    d(
        "famille-lecture",
        "prospection",
        "Famille thématique (lecture), défaut adjacente",
        opts(e["tri.Famille"]),
        "LLM (rôle lecture)",
        a(P + "lecture.py", r'^    famille: Famille = "adjacente"'),
        "O5",
        verites=["catalogue-yaml", "familles-proposition"],
    )
    d(
        "vulgarisation",
        "prospection",
        "La page est-elle une vulgarisation sans règlement ?",
        "vrai / faux",
        "LLM (rôle lecture)",
        a(P + "lecture.py", r"source_unique_vulgarisation: bool"),
        "O2",
        sans=("100 pages lues : règlement ou modalités précises présents ou non", 1.0, 0.0),
        volume="[[file.source_unique_vulgarisation]] tâches marquées dans la file",
    )
    d(
        "doublon-probable",
        "prospection",
        "Ce dispositif est-il un doublon d'une aide du catalogue ? lequel ?",
        "slug libre ou rien (aucune liste de candidats)",
        "LLM (rôle lecture)",
        a(P + "lecture.py", r"doublon_probable: str \| None"),
        "O3",
        verites=["doublons-url", "doublons-arbitres"],
        volume="[[file.doublon_probable]] tâches avec doublon_probable",
    )
    d(
        "priorite",
        "prospection",
        "Priorité d'ingestion",
        "haute | normale | basse (chaîne libre ramenée à normale si invalide)",
        "LLM (rôle lecture)",
        a(P + "lecture.py", r'priorite: str = "normale"'),
        "O11",
        sans=("100 tâches : ordre de valeur relu à la main", 0.5, 0.0),
        volume="[[file.priorite]]",
    )
    d(
        "urls-pdf",
        "prospection",
        "Quels documents liés snapshoter ?",
        "sous-ensemble des ≤ 25 documents vus (filtré par le code)",
        "LLM (rôle lecture), filtre de code",
        a(P + "lecture.py", r"fiche\.urls_pdf = \[u for u"),
        "O2",
        sans=("100 documents vus : règlement/cadre/formulaire du dispositif ou non", 0.5, 0.0),
    )
    d(
        "slug-collision",
        "prospection",
        "Slug occupé : suffixer ou reconnaître un doublon ?",
        "suffixe -2, -3… (toujours)",
        "code (slug_final)",
        a(P + "lecture.py", r"^def slug_final"),
        "O8",
        verites=["doublons-url"],
    )
    d(
        "entree-file",
        "prospection",
        "Ce qui entre dans la file après lecture",
        "a_valider (retenue, indéterminée) | ignore + motif (écartée) | hors file (erreur, écartée au tri) (3)",
        "code (fiche.taches)",
        a(P + "fiche.py", r"^def taches"),
        "O8",
        sans=(
            "100 lectures en erreur (hors file) : la page était-elle lisible et pertinente ?",
            1.0,
            0.0,
        ),
    )
    d(
        "promotion-regle",
        "prospection",
        "Une a_valider peut-elle passer en valide sans humain ?",
        "promouvable | indéterminée | hors périmètre | famille "
        + "/".join(e["etat.FAMILLES_NON_PROMOUVABLES"])
        + " (4 motifs)",
        "code (motif_non_promotion, promouvables) dans --auto, valider --tout, balayage",
        ", ".join(
            [
                a(S + "pipeline/etat.py", r"^def motif_non_promotion"),
                a(S + "pipeline/etat.py", r"^def promouvables"),
            ]
        ),
        "O11",
        sans=(
            "100 tâches promues par la règle puis ingérées : garder ou écarter (jeu J3/J4 en partie, notes/file-et-humain.md)",
            1.5,
            0.0,
        ),
        volume="[[file.a_valider.promouvable]] promouvables en attente",
    )
    d(
        "promotion-humaine",
        "prospection",
        "Valider ou ignorer une candidate nommée",
        "valide | ignore (sans motif écrit par ignorer)",
        "Félix (en pratique : proposition de Claude approuvée en bloc, notes/file-et-humain.md)",
        a(S + "prospecter.py", r"^def _transitionner"),
        "O11",
        sans=("100 a_valider indéterminées tranchées par Félix une par une", 1.5, 0.0),
        volume="[[file.a_valider.indetermine]] indéterminées en attente",
    )
    d(
        "doublon-url-file",
        "prospection",
        "Collision d'URL dans la file : qui survit ?",
        "ordre de survie ingere > en_cours > valide > a_valider > echec > ignore, puis date, puis slug",
        "code (doublons_par_url)",
        a(S + "pipeline/etat.py", r"^_RANG_SURVIE"),
        "O3",
        verites=["doublons-url"],
    )
    d(
        "echecs-a-relire",
        "prospection",
        "Quelles tâches echec repasser par la lecture ?",
        "relire / laisser (règle sur le motif et l'indétermination)",
        "code (echecs_a_relire)",
        a(S + "pipeline/etat.py", r"^def echecs_a_relire"),
        "O11",
        sans=("sans objet : règle appliquée une fois (351 échecs du 2026-09-18)", 0, 0.0),
    )
    d(
        "requalification",
        "prospection",
        "Garder ou écarter une aide déjà ingérée (sur YAML + review)",
        f"destinataire {len(e['etat.DESTINATAIRES'])} × objet {len(e['etat.OBJETS'])} × catégorie {len(e['etat.CATEGORIES_ECART'])} → retenue / à écarter / à trancher",
        "LLM (rôle lecture), puis Félix corrige la fiche et lance --appliquer",
        ", ".join(
            [
                a(P + "requalification.py", r"^class Requalification"),
                a(P + "requalification.py", r"^def appliquer"),
            ]
        ),
        "O3",
        verites=["requalif-2026-09-22", "requalif-2026-10-04", "desaccords-2026-10-04"],
    )
    # --- Ingestion ----------------------------------------------------------
    d(
        "ordre-ingestion",
        "ingestion",
        "Quelle aide lancer, dans quel ordre, sous quel budget ?",
        "priorité puis slug ; lancer / attendre (budget 1,50 $ par aide, 50 $ total)",
        "code",
        ", ".join(
            [
                a(S + "pipeline/etat.py", r"^def selectionner"),
                a(ING + "orchestrateur.py", r"^def _budget_epuise"),
            ]
        ),
        "O11",
        sans=(
            "sans objet : ordonnancement, pas de bonne réponse ; se teste par test unitaire",
            0,
            0.0,
        ),
    )
    d(
        "gabarit",
        "ingestion",
        "Quelle aide du catalogue sert de gabarit ?",
        "une aide parmi le catalogue (classement lexicographique)",
        "code (choisir_aide_reference)",
        a(ING + "contexte.py", r"^def choisir_aide_reference"),
        "O4",
        sans=("100 aides : gabarit choisi pertinent pour la famille de l'aide ou non", 0.5, 0.0),
    )
    d(
        "sources-archiver",
        "ingestion",
        "Quelles sources lire et archiver (citable) plutôt qu'explorer (non citable) ?",
        "snapshotter / explorer / ignorer, lien par lien",
        "LLM (agent d'ingestion)",
        ", ".join(
            [
                a(ING + "outils.py", r"def snapshotter\("),
                a(ING + "outils.py", r"def explorer_url\("),
            ]
        ),
        "O2",
        sans=("100 aides : la source qui porte le règlement a-t-elle été archivée ?", 3.0, 0.0),
    )
    d(
        "hors-perimetre-ingestion",
        "ingestion",
        "La source s'adresse-t-elle à un tiers ? (arrêt de l'agent)",
        opts(e["etat.CATEGORIES_ECART"])
        + " ou continuer ; motif ≥ 40 car., citation non vide (jamais recherchée dans le snapshot)",
        "LLM (agent d'ingestion)",
        a(ING + "outils.py", r"def declarer_hors_perimetre\("),
        "O3",
        verites=["requalif-2026-09-22", "banc-destinataire"],
        volume="[[reviews.ingest_hors_perimetre]] déclarations dans les fiches d'ingestion",
    )
    d(
        "doublon-ingestion",
        "ingestion",
        "La source décrit-elle le même dispositif que le doublon_probable ?",
        "même dispositif : s'arrêter sans YAML (le verdict code en fait un echec « aucun fichier YAML écrit ») / continuer",
        "LLM (agent d'ingestion)",
        a(ING + "contexte.py", r"Doublon probable de"),
        "O3",
        verites=["doublons-url", "doublons-arbitres"],
    )
    d(
        "exigence-a-extraire",
        "ingestion",
        "Cette phrase de la source est-elle une exigence à extraire en condition ?",
        "extraire (gate, modulateur, info) / laisser",
        "LLM (agent d'ingestion) ; omissions cherchées par le vérificateur (axe condition_manquante)",
        a(".claude/skills/ingest-aide/SKILL.md", r"^## Étape 2"),
        "O4",
        sans=(
            "100 phrases normatives tirées des snapshots de 10 aides : extraite ou omise à tort",
            1.0,
            0.0,
        ),
        volume="[[aides.conditions]] conditions au catalogue",
    )
    d(
        "kind-effect",
        "ingestion",
        "Kind et effect de chaque condition",
        f"kind {opts(e['schema.ConditionKind'])} × effect {opts(e['schema.ConditionEffect'])}",
        "LLM (agent d'ingestion) ; lint (forme, ratchet manual_check gate) ; vérificateur LLM",
        ", ".join(
            [
                a("backend/aides_schema.py", r"^ConditionKind"),
                a("backend/data/TYPING.md", r"^## L'arbre de décision"),
            ]
        ),
        "O5",
        verites=["transitions-typage", "lot-4-engagements", "lot-5-critere-demarche"],
        volume="[[aides.conditions]] conditions : [[aides.kind_effect]]",
    )
    d(
        "critere-demarche",
        "ingestion",
        "Avant de poser une question : critère, démarche ou promesse ?",
        "critère | démarche | promesse | à trancher (4)",
        "LLM (agent) ; regex _PROMESSE_RE refuse un fait-promesse",
        ", ".join(
            [
                a("backend/data/TYPING.md", r"^### Avant de poser une question"),
                a(ING + "faits.py", r"^_PROMESSE_RE"),
            ]
        ),
        "O5",
        verites=["lot-5-critere-demarche", "tri-critere-demarche", "lot-4-engagements"],
    )
    d(
        "fait-choix",
        "ingestion",
        "Réutiliser un fait (lequel), en proposer un, ou typer manual_check",
        "un fait parmi [[faits.facts]] + pending | nouveau | aucun (manual_check)",
        "LLM (agent) après recherche par mots-clés",
        ", ".join(
            [a(ING + "outils.py", r"def chercher_faits\("), a(ING + "faits.py", r"^def rechercher")]
        ),
        "O6",
        verites=[
            "paires-faits",
            "fusions-lot-2",
            "fusions-lot-3",
            "fusions-revue-pending",
            "destin-pending",
        ],
    )
    d(
        "garde-proximite",
        "ingestion",
        "Proposition refusée tant qu'un voisin proche n'a pas été lu ?",
        "refus (≥ 0,68 et voisin non lu par detail_fait) / accepté",
        "code (SequenceMatcher max(question, clé))",
        ", ".join(
            [a(ING + "faits.py", r"^SEUIL_PROXIMITE"), a(ING + "faits.py", r"^def _proches")]
        ),
        "O6",
        verites=["paires-faits"],
    )
    d(
        "forme-fait",
        "ingestion",
        "Le fait proposé a-t-il une forme refusée ?",
        "promesse | booléen à seuil | question trop longue | polarité suspecte | identifiant ou justification invalide | plafond de 3 | accepté",
        "code (heuristiques regex)",
        a(ING + "faits.py", r"^def _refus_de_forme"),
        "O6",
        sans=("100 propositions refusées ou acceptées : le refus était-il justifié ?", 1.0, 0.0),
    )
    d(
        "type-scope-fait",
        "ingestion",
        "Type et scope d'un fait neuf",
        f"type {opts(e['schema.FactDef.type'])} ; scope {opts(e['schema.FactDef.scope'])}",
        "LLM (agent)",
        a("backend/aides_schema.py", r"^    scope: Literal"),
        "O6",
        verites=["destin-pending"],
        volume="types au catalogue : [[faits.type]]",
    )
    d(
        "retirer-fait",
        "ingestion",
        "Retirer un fait que l'agent a lui-même proposé ?",
        "retirer / garder",
        "LLM (agent), refus en code si une aide le cite",
        a(ING + "outils.py", r"def retirer_fait\("),
        "O6",
        sans=("100 retraits : le fait retiré était-il un doublon ou une erreur ?", 1.0, 0.0),
    )
    d(
        "applies-if-aide",
        "ingestion",
        "Poser un applies_if de périmètre au niveau de l'aide, et sur quel fait ?",
        "aucun | un fait de périmètre (FAITS_DEDUITS_DES_FAMILLES et autres)",
        "LLM (agent), d'après la note de prospection",
        a("backend/data/TYPING.md", r"^## `applies_if` au niveau de l'AIDE"),
        "O5",
        sans=("100 aides hors restauration_bati : périmètre juste, absent ou faux", 2.0, 0.0),
        volume="[[aides.applies_if_aide]] aides avec applies_if d'aide",
    )
    d(
        "familles",
        "ingestion",
        "Familles thématiques de l'aide (plusieurs possibles)",
        opts(e["labels.FAMILLES_LABELS"]),
        "LLM (agent) ; contrôle de non-vacuité en code",
        a(ING + "worker.py", r"if aide is not None and not aide\.familles"),
        "O5",
        verites=["familles-proposition", "familles-backfill"],
        volume="[[aides.familles_non_vides]] aides avec familles",
    )
    d(
        "raison",
        "ingestion",
        "Raison de l'aide (plusieurs possibles)",
        opts(e["schema.RAISONS"]),
        "LLM (agent) ; contrôle mécanique au lint d'écriture",
        a("backend/aides_schema.py", r"^RAISONS = "),
        "O5",
        verites=["raisons-audit"],
        volume="[[aides.raison]]",
    )
    d(
        "travaux",
        "ingestion",
        "hard_filters.travaux : la source restreint-elle l'objet, à quels codes ?",
        opts(e["labels.TRAVAUX_LABELS"]) + " ; vide = aucune restriction",
        "LLM (agent)",
        a("backend/data/TYPING.md", r"^## Les critères structurés"),
        "O5",
        sans=("100 aides : restriction d'objet lue dans la source contre codes posés", 2.0, 0.0),
        volume="[[aides.travaux_non_vide]] aides avec travaux",
    )
    d(
        "gate-beneficiaires",
        "ingestion",
        "La source nomme-t-elle ses bénéficiaires, lesquels (gate statut_juridique_porteur) ?",
        "aucun gate | gate `in` sur un sous-ensemble des options du fait",
        "LLM (agent), bénéficiaires lus en prospection",
        a(ING + "contexte.py", r"Bénéficiaires lus à la prospection"),
        "O5",
        verites=["gate-porteur"],
        volume="[[aides.gate_statut_juridique_porteur]] gates statut_juridique_porteur",
    )
    d(
        "porteurs-concernes",
        "ontologie",
        "La question d'un fait n'a-t-elle de sens que pour une entreprise ou une exploitation ?",
        "marqué / non",
        "Félix ou Claude marquent à la main ; une regex de code alerte",
        a(S + "lint_aides_data.py", r"^def faits_entreprise_sans_marqueur"),
        "O6",
        verites=["porteurs-concernes"],
        volume="[[faits.porteurs_concernes]] faits marqués",
    )
    d(
        "champs-simples",
        "ingestion",
        "Type de bénéfice, catégorie du financeur, permanent, cumulable, derogation_possible",
        f"type {opts(e['schema.TYPES'])} ; catégorie {opts(e['schema.CATEGORIES'])} ; booléens",
        "LLM (agent)",
        a("backend/aides_schema.py", r"^TYPES = "),
        "O4",
        sans=("100 aides : chaque champ relu contre la source", 2.0, 0.0),
        volume="permanent vrai [[aides.permanent_true]], derogation_possible [[aides.derogation_possible]]",
    )
    d(
        "semantique-montant",
        "ingestion",
        "Un montant est-il un seuil de dépenses, un minimum d'aide, un plafond ou une condition sur le budget ?",
        "plancher | montant_min | plafond | condition budget_travaux_estime (4)",
        "LLM (agent)",
        a("backend/aides_schema.py", r"^    plancher: "),
        "O4",
        sans=("100 montants (planchers et montant_min) relus contre la source", 1.5, 0.0),
        volume="plancher [[aides.plancher]], montant_min [[aides.montant_min]]",
    )
    d(
        "calendrier-classe",
        "ingestion",
        "Calendrier : permanent, session datée ou clos ?",
        "permanent | session datée | clos (3)",
        "LLM (agent) ; lint d'écriture refuse permanent + date_limite",
        a("backend/aides_schema.py", r"^class Calendrier"),
        "O4",
        sans=("100 aides : classe du calendrier contre la source", 1.5, 0.0),
        volume="date_limite [[aides.date_limite]]",
    )
    d(
        "info-ou-exigence",
        "ingestion",
        "Une condition info cache-t-elle une exclusion ? une puce composite doit-elle être scindée ?",
        "garder info | gate | scinder",
        "LLM (agent), vérificateur LLM",
        a("backend/data/TYPING.md", r"^## Puces composites"),
        "O5",
        sans=("100 conditions info tirées au hasard : exigence cachée ou non", 1.0, 0.0),
    )
    d(
        "piece-id",
        "ingestion",
        "À quelle pièce canonique rattacher un document requis ?",
        opts(e["pieces.yaml"]) + " ou aucune",
        "LLM (agent) ; map_pieces.py une fois (LLM + relecture)",
        a(S + "map_pieces.py", r"^def proposer"),
        "O5",
        verites=["pieces-mapping"],
        volume="[[aides.documents_avec_piece_id]] documents rattachés sur [[aides.documents_requis]]",
    )
    d(
        "levier-pertinent-si",
        "ontologie",
        "Le fait est-il actionnable (levier) ? dépend-il d'un autre (pertinent_si) ?",
        "levier oui/non ; pertinent_si : aucun | un fait porte",
        "LLM (agent) puis Félix au diff",
        ", ".join(
            [
                a("backend/data/TYPING.md", r"^## `levier`"),
                a("backend/data/TYPING.md", r"^## `pertinent_si`"),
            ]
        ),
        "O6",
        verites=["lot-5-critere-demarche"],
        volume="faits avec levier [[faits.levier]], avec pertinent_si [[faits.pertinent_si]]",
    )
    d(
        "verif-axe-severite",
        "ingestion",
        "Axe et sévérité de chaque reproche du vérificateur",
        f"axe {opts(e['verification.AXES'])} × {opts(e['verification.severite'])}",
        "LLM vérificateur",
        a(ING + "verification.py", r"^Axe = Literal"),
        "O7",
        sans=(
            "100 reproches journalisés : fondés ou non, bloquants ou non, sur la source",
            2.0,
            0.0,
        ),
    )
    d(
        "qualite-source",
        "ingestion",
        "Qualité de la source lue par le vérificateur",
        opts(e["verification.qualite_source"]),
        "LLM vérificateur (non exploité par le code)",
        a(ING + "verification.py", r"qualite_source: Literal"),
        "O7",
        sans=("100 aides : nature de la source principale", 0.5, 0.0),
    )
    d(
        "verif-encore",
        "ingestion",
        "Relancer la vérification ?",
        "relancer (≤ 3, sinon a_relire) / écrire la fiche",
        "LLM (agent) sous plafond de code",
        a(ING + "outils.py", r"^MAX_VERIFICATIONS"),
        "O7",
        sans=(
            "100 aides au plafond de 3 vérifications : le bloquant restant est-il fondé ?",
            2.0,
            0.0,
        ),
    )
    d(
        "reproche-accepte",
        "ingestion",
        "Accepter ou contester un reproche du vérificateur",
        "corriger / contester (consigné dans la fiche)",
        "LLM (agent)",
        a(".claude/skills/ingest-aide/SKILL.md", r"^## Étape 4"),
        "O7",
        sans=("100 reproches contestés : la contestation tient-elle sur la source ?", 2.0, 0.0),
    )
    d(
        "review-recevable",
        "ingestion",
        "La fiche de review est-elle recevable ?",
        "refus (< 800 car., sans ##, sans vérification, YAML modifié depuis la vérification) / acceptée (+ a_relire si bloquant)",
        "code",
        a(ING + "outils.py", r"def ecrire_review\("),
        "O12",
        sans=("100 fiches refusées par le code : refus justifié ?", 0.5, 0.0),
    )
    d(
        "acceptation",
        "ingestion",
        "Accepter l'ingestion ?",
        "10 contrôles : accepté | .yaml.echec (+ motif)",
        "code (worker.controler)",
        a(ING + "worker.py", r"^def controler"),
        "O7",
        verites=["requalif-2026-09-22", "catalogue-yaml"],
        volume="[[file.statut.ingere]] ingere, [[aides.yaml_echec]] .yaml.echec",
    )
    d(
        "arret-boucle",
        "ingestion",
        "Arrêter l'agent ?",
        opts(e["boucle.Arret"]),
        "code (Limites : 120 tours, 1,50 $, boucles)",
        a(ING + "boucle.py", r"^Arret = Literal"),
        "O11",
        sans=(
            "100 arrêts boucle, max_tours ou budget (journaux) : l'agent progressait-il ?",
            2.0,
            0.0,
        ),
    )
    d(
        "classe-erreur",
        "ingestion",
        "Panne transitoire, fatale ou ni l'une ni l'autre ?",
        'transitoire | fatal | "" (3)',
        "code (types d'exception, motifs du message)",
        a(ING + "boucle.py", r"^def classe_erreur"),
        "O11",
        sans=("100 erreurs journalisées : classe transitoire/fatale juste ?", 0.3, 0.0),
    )
    d(
        "statut-final",
        "ingestion",
        "Statut de la tâche après l'ingestion",
        "ignore | ingere | valide (rejouer, < 3 tentatives) | echec (4)",
        "code",
        a(ING + "orchestrateur.py", r"^def _statut_final"),
        "O11",
        sans=("100 tâches echec : rejouables ou non ?", 0.5, 0.0),
    )
    d(
        "disjoncteur",
        "orchestration",
        "Continuer, pause ou arrêt du run ? relancer après coupure ?",
        "continuer | arrêt code 3 ; relance ≤ 2 sauf « erreur fatale » dans les 4 000 derniers car. du journal",
        "code",
        ", ".join(
            [
                a(ING + "orchestrateur.py", r"^class Disjoncteur"),
                a(S + "balayage.py", r"^def _panne_fatale"),
            ]
        ),
        "O11",
        sans=(
            "sans objet : événement rare (incidents du 2026-09-18), se teste sur journaux rejoués",
            0,
            0.0,
        ),
    )
    d(
        "cout-questions",
        "ingestion",
        "L'aide fait-elle entrer trop de questions au tronc commun ?",
        "alerte (≥ 3 questions sur un profil) / rien (informatif, jamais bloquant)",
        "code",
        a(ING + "worker.py", r"^SEUIL_ALERTE_QUESTIONS"),
        "O12",
        sans=("sans objet : mesure informative, aucune issue ne dépend d'elle", 0, 0.0),
    )
    d(
        "audit-paire",
        "ingestion",
        "Deux faits proches : doublon, polarité inversée ou distincts ?",
        opts(e["ontologie.Fusion.verdict"]),
        "code (pré-filtre 0,60, 60 paires) puis LLM (rôle audit) ; rien n'est appliqué",
        ", ".join(
            [
                a(ING + "ontologie.py", r"^class Fusion"),
                a(ING + "ontologie.py", r"^def paires_suspectes"),
            ]
        ),
        "O6",
        verites=["paires-faits", "fusions-lot-2", "fusions-lot-3"],
    )
    d(
        "approbation-fait",
        "ontologie",
        "Approuver un fait proposé (pending → facts.yaml) ?",
        "approuver | fusionner | retyper | retirer",
        "Félix (en bloc ; 471 le 2026-09-17 selon la mémoire)",
        a("backend/data/TYPING.md", r"^## Proposer un nouveau fait"),
        "O6",
        verites=["destin-pending", "fusions-lot-2", "fusions-revue-pending"],
    )
    d(
        "fusion-table",
        "ontologie",
        "Appliquer une ligne de table de fusion ou de retypage ?",
        "appliquée / refusée (types, scopes, options incompatibles, polarité)",
        "Félix ou Claude écrivent, code applique ou refuse",
        a(S + "fusionner_faits.py", r"^def _verifier_compatibilite"),
        "O6",
        verites=["fusions-lot-2", "fusions-lot-3"],
    )
    d(
        "orphelin",
        "ontologie",
        "Un fait est-il atteint par le catalogue ?",
        "utilisé / orphelin / nuance (clé vue dans un texte ou le code)",
        "code (faits_orphelins)",
        a(S + "faits_orphelins.py", r"^def fermeture"),
        "O6",
        sans=("100 faits déclarés orphelins : vraiment hors de portée du moteur ?", 0.3, 0.0),
    )
    d(
        "doublon-aide-survivant",
        "ontologie",
        "Groupe d'aides à même URL : quel survivant ?",
        "un slug survit, les autres en .yaml.echec",
        "code propose, humain corrige la table",
        a(S + "dedoublonner_aides.py", r"^def _rang"),
        "O3",
        verites=["doublons-url", "doublons-arbitres"],
    )
    d(
        "backfill-net",
        "ontologie",
        "Une proposition de backfill (familles, gate porteur) est-elle « nette » ?",
        "nette (appliquée) / ambiguë (fiche)",
        "code",
        ", ".join(
            [
                a(S + "proposer_familles.py", r"^def appliquer"),
                a(S + "proposer_gate_porteur.py", r"^def appliquer"),
            ]
        ),
        "O5",
        verites=["familles-proposition", "gate-porteur"],
    )
    d(
        "ratchet",
        "ontologie",
        "Le lint accepte-t-il le catalogue ?",
        "erreur bloquante / avertissement / rien ; ratchet manual_check gate",
        "code",
        a(S + "lint_aides_data.py", r"^def check_manual_check_ratchet"),
        "O7",
        sans=("sans objet : règle de non-régression", 0, 0.0),
    )
    d(
        "citation-retrouvee",
        "ingestion",
        "La quote se retrouve-t-elle dans un snapshot ?",
        "trouvée / introuvable (erreur en mono-slug, info en global)",
        "code",
        ", ".join(
            [
                a(ING + "outils.py", r"def _audit_citations\("),
                a(S + "lint_aides_data.py", r"^def check_quotes"),
            ]
        ),
        "O7",
        sans=(
            "100 citations introuvables : absence réelle ou faux négatif de normalisation ?",
            1.0,
            0.0,
        ),
    )
    # --- Veille -------------------------------------------------------------
    d(
        "ordre-veille",
        "veille",
        "Quelles aides passent, dans quel ordre, sous quel plafond --max-llm ?",
        "ancienneté ; plafond 20 soumises",
        "code",
        ", ".join(
            [
                a(S + "veille_aides.py", r"^def anciennete"),
                a(S + "veille_update.py", r"^MAX_LLM_DEFAUT"),
            ]
        ),
        "O9",
        sans=("sans objet : ordonnancement", 0, 0.0),
    )
    d(
        "statut-b",
        "veille",
        "Statut d'une aide après l'étage B (9 règles ordonnées)",
        opts(e["veille_analyze.STATUTS"]),
        "code (seuils figés à la main)",
        a(S + "veille_analyze.py", r"^def _decider"),
        "O9",
        sans=(
            "100 aides d'un passage : statut juste contre les deux versions de la page",
            2.0,
            0.0,
        ),
        volume="[[veille.status]]",
    )
    d(
        "gabarit-ligne",
        "veille",
        "Une ligne changée est-elle du gabarit de site ?",
        "gabarit (≥ 2 URL) / règlement",
        "code",
        ", ".join(
            [
                a(S + "veille_analyze.py", r"^CHROME_MIN_URLS"),
                a(S + "veille_analyze.py", r"^def lignes_de_chrome"),
            ]
        ),
        "O9",
        sans=(
            "100 lignes retirées comme gabarit : aucune ne porte de date, montant ou critère",
            0.2,
            0.0,
        ),
    )
    d(
        "panne-generale",
        "veille",
        "Le run est-il en panne réseau générale ?",
        "oui (> 30 % d'échecs) / non",
        "code",
        a(S + "veille_analyze.py", r"^SEUIL_PANNE_GENERALISEE"),
        "O9",
        sans=("sans objet : événement de run, pas de cas par aide", 0, 0.0),
    )
    d(
        "refonte",
        "veille",
        "Refonte du site ou nouveau règlement (règle 6) ?",
        f"{opts(qr.get('meme_reglement', []))} ; rétrograder en MAJ_LLM ou escalader",
        "code (> 50 % de lignes changées) ; Jev débranché (SEUIL_REFONTE None)",
        ", ".join(
            [
                a(S + "veille_analyze.py", r"^RATIO_DIFF_ESCALADE"),
                a(S + "veille_arbitre.py", r'^    "meme_reglement"'),
            ]
        ),
        "O9",
        verites=["veille-jev-cas"],
    )
    d(
        "deja-refuse",
        "veille",
        "Ce changement a-t-il déjà été soumis et refusé à l'identique ?",
        "ne pas resoumettre (escalade reste escalade, suspect reste suspect, échec silencieux) / soumettre",
        "code (empreinte du changement)",
        a(S + "veille_aides.py", r"^def empreinte_changement"),
        "O10",
        sans=(
            "refus mémorisés ([[veille.maj_refusee]] aujourd'hui, tout le stock) : la page a-t-elle changé dans le mandat ?",
            2.0,
            0.0,
        ),
        volume="[[veille.maj_refusee]] refus mémorisés",
    )
    d(
        "filtre-jev",
        "veille",
        "Le diff touche-t-il le mandat, avant le LLM ?",
        opts(qm.get("touche", [])),
        "Jev débranché (SEUIL_FILTRE None) : aujourd'hui tout part au LLM",
        a(S + "veille_arbitre.py", r'^    "touche"'),
        "O9",
        verites=["veille-jev-cas", "veille-jev-etiquettes"],
    )
    d(
        "section-jev",
        "veille",
        "Quelle section de la fiche le changement touche-t-il ?",
        opts(qm.get("section", [])),
        "Jev (rapport seulement)",
        a(S + "veille_arbitre.py", r'^    "section"'),
        "O12",
        sans=("100 diffs MAJ_LLM : section touchée", 1.0, 0.0),
    )
    d(
        "maj-llm",
        "veille",
        "Que change la source dans le mandat (calendrier, financement, cumul, conditions) ?",
        f"par section : rien | MajSection ; par condition : {opts(e['veille_apply.op'])}",
        "LLM (étage C)",
        a(S + "veille_apply.py", r"^class VeilleLLMOutput"),
        "O10",
        verites=["veille-golds", "veille-jev-cas", "veille-etage-c"],
    )
    d(
        "changement-majeur",
        "veille",
        "La page décrit-elle encore le même dispositif ?",
        "changement_majeur vrai / faux",
        "LLM (étage C)",
        a(S + "veille_apply.py", r"changement_majeur: bool"),
        "O10",
        sans=("100 pages escaladées ou retouchées : même dispositif ou non", 2.0, 0.0),
    )
    d(
        "validation-apply",
        "veille",
        "À quelle étape la réponse échoue-t-elle, et est-elle rattrapable ?",
        opts(e["veille_apply.Issue"]),
        "code",
        ", ".join(
            [
                a(S + "veille_apply.py", r"^Issue = Literal"),
                a(S + "veille_apply.py", r"    def rattrapable"),
            ]
        ),
        "O10",
        sans=(
            "100 rejets de l'étage C (quote, référentiel, cohérence) : rejet justifié ?",
            1.5,
            0.0,
        ),
    )
    d(
        "etat-maj",
        "veille",
        "Sort d'une aide à l'étage C",
        opts(e["veille_update.Etat"]),
        "code (d'après l'étape d'échec et l'égalité du texte)",
        a(S + "veille_update.py", r"^Etat = Literal"),
        "O10",
        verites=["veille-jev-cas"],
    )
    d(
        "garde-jev",
        "veille",
        "Un « inchangé » du LLM est-il suspect ?",
        opts(qm.get("touche", [])) + " ; suspect si p ≥ 0,45",
        "Jev (SEUIL_GARDE 0,45, choix de Félix)",
        ", ".join(
            [
                a(S + "veille_arbitre.py", r"^SEUIL_GARDE"),
                a(S + "veille_update.py", r'res\.etat = "suspect"'),
            ]
        ),
        "O9",
        verites=["veille-jev-cas", "veille-jev-etiquettes", "veille-etage-c"],
    )
    d(
        "ancrage",
        "veille",
        "Citation non ancrée dans le diff : divergence réelle ou faux négatif ?",
        "escalade (toujours)",
        "code (check_ancrage), puis humain",
        a(S + "veille_apply.py", r"^def check_ancrage"),
        "O10",
        sans=("100 escalades d'ancrage : fiche fausse ou rien à faire", 3.0, 0.0),
    )
    d(
        "structure",
        "veille",
        "Condition apparue ou disparue : exigence nouvelle ou reformulation ?",
        "escalade en ré-ingestion (toujours)",
        "LLM (op add / signaler_disparue) puis code",
        a(S + "veille_apply.py", r"^def _changements_structurels"),
        "O10",
        sans=("100 conditions add/disparue : exigence nouvelle ou reformulation", 2.0, 0.0),
    )
    d(
        "rearchiver",
        "veille",
        "La page fraîche devient-elle la nouvelle baseline ?",
        "ré-archiver / garder l'ancienne (suspect, escalade, échec)",
        "code après verdict ; Félix par --rearchiver",
        a(S + "veille_update.py", r"^def rafraichir_snapshots"),
        "O2",
        verites=["veille-jev-cas", "veille-etage-c"],
    )
    d(
        "acquittement",
        "veille",
        "Échéance passée, source inchangée : annonce sans année, nouvelle session ou aide close ?",
        "acquitter / attendre (aucune autre option dans le code)",
        "Félix (--acquitter), jamais fait",
        a(S + "veille_aides.py", r"^def traiter_acquittements"),
        "O11",
        sans=(
            "100 aides DATE_PERIMEE (31 au passage du 2026-10-04 : tout le stock) : classe relue sur la page",
            3.0,
            0.0,
        ),
        volume="[[veille.status]] ; ack [[veille.ack]]",
    )
    d(
        "lancer-reingestion",
        "veille",
        "Lancer la ré-ingestion d'une escalade ?",
        "lancer / laisser",
        "Félix (commande imprimée)",
        a(S + "veille_aides.py", r"scripts/ingerer\.py \{slugs\}"),
        "O11",
        sans=("100 escalades : ré-ingestion utile ou non (41 au passage du 2026-10-04)", 4.0, 0.15),
    )
    d(
        "regenerer-fiche",
        "veille",
        "Régénérer le bloc fiche: après une retouche de veille ?",
        "régénérer / laisser",
        "Félix, sans signal : la veille ne met pas à jour source.verified_at, que lit a_relire",
        ", ".join(
            [
                a(S + "rediger_fiches.py", r"^def a_relire"),
                a(S + "lint_aides_data.py", r"^def check_fiche"),
            ]
        ),
        "O11",
        sans=("100 retouches de veille : la fiche contredit-elle le YAML ?", 1.0, 0.0),
    )
    d(
        "audit-exhaustivite",
        "veille",
        "Chaque critère de la source est-il conforme, absent ou divergent ?",
        opts(e["veille_audit.verdict"]),
        "LLM (étage D, quasi jamais lancé)",
        a(S + "veille_audit.py", r"^class CritereAudit"),
        "O7",
        verites=["veille-golds-audit"],
    )
    d(
        "typage-veille",
        "veille",
        "Typage d'une condition untyped par la veille",
        f"kind {opts(e['veille_typage.kind'])} × effect {opts(e['veille_typage.effect'])}",
        "LLM (veille_typage)",
        a(S + "veille_typage.py", r"^class TypageCondition"),
        "O5",
        verites=["transitions-typage"],
    )
    # --- Fiches -------------------------------------------------------------
    d(
        "selection-fiche",
        "fiches",
        "Quelles aides rédiger ?",
        "sans fiche | fiche à relire (verified_at > redige_le) | slug nommé",
        "code",
        a(S + "rediger_fiches.py", r"^def selectionner"),
        "O8",
        sans=("sans objet : sélection par règle", 0, 0.0),
    )
    d(
        "theme-point",
        "fiches",
        "Rubrique de chaque point du règlement, ton de chaque puce « En bref »",
        f"rubrique {opts(e['schema.THEMES_REGLEMENT'])} ; ton {opts(e['schema.TONS_EN_BREF'])}",
        "LLM (rédaction)",
        a("backend/aides_schema.py", r"^THEMES_REGLEMENT"),
        "O8",
        verites=["fiches-incoherences"],
    )
    d(
        "controle-fiche",
        "fiches",
        "La fiche rédigée est-elle recevable ?",
        "refus (conditions inconnues ou sans point, pièces inconnues, point sans rubrique, tiret long, titre > 80) / écrite ; 2 corrections",
        "code",
        a(S + "rediger_fiches.py", r"^def controler"),
        "O7",
        sans=("100 fiches refusées : refus justifié ?", 0.5, 0.0),
    )
    # --- Orchestration --------------------------------------------------------
    d(
        "prevol",
        "orchestration",
        "Tous les modèles répondent-ils avant le balayage ?",
        "partir / refuser (code 1) ; Jev non testé",
        "code",
        a(S + "balayage.py", r"^def verifier_modeles"),
        "O7",
        sans=("sans objet : contrôle technique", 0, 0.0),
    )
    d(
        "concurrence",
        "orchestration",
        "Un autre run tourne-t-il sur la machine ?",
        "refuser / partir (pgrep)",
        "code",
        a(S + "balayage.py", r"^def runs_en_cours"),
        "O11",
        sans=("sans objet : contrôle technique", 0, 0.0),
    )
    d(
        "territoire-balaye",
        "orchestration",
        "Le territoire est-il balayé ?",
        "oui si code de sortie 0 (balayage.json) / non",
        "code",
        a(S + "balayage.py", r"^def phase_prospection"),
        "O12",
        sans=("100 territoires « balayés » : la collecte a-t-elle ramené le guide ?", 2.0, 0.0),
    )
    d(
        "modele-role",
        "orchestration",
        "Quel modèle pour chaque rôle ?",
        "alias providall par rôle (7 rôles + VEILLE_MODEL + DECISION_MODEL)",
        "Félix (.env.local) ; contredit par les défauts ds-v41 de balayage.py",
        ", ".join(
            [
                a(S + "pipeline/llm.py", r"^ROLES"),
                a(S + "balayage.py", r'"--model-tri", default="ds-v41"'),
            ]
        ),
        "O11",
        verites=["banc-destinataire-llm"],
    )
    d(
        "commit-load",
        "orchestration",
        "Committer et charger en base ?",
        "commit + load / rien",
        "Félix (Claude ne commit ni ne charge)",
        a(S + "load_aides_yaml.py", r"^def main"),
        "O11",
        sans=("sans objet : geste de Félix", 0, 0.0),
    )
    d(
        "surcouche-admin",
        "produit",
        "Retirer une aide, reformuler un fait, remplacer un prédicat (/admin)",
        "ligne posée / rétablie ; péremption code : perimee_texte | perimee_fait | a_revoir",
        "Félix (page /admin) ; péremption par le code",
        a("backend/services/catalogue_admin.py", r"^def catalogue_effectif"),
        "O11",
        sans=("sans objet : geste de Félix, lignes rares", 0, 0.0),
    )
    return D


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------

_PLACE = re.compile(r"\[\[([^\]]+)\]\]")


def remplir(texte: str, c: dict[str, Any]) -> str:
    def rempl(m: re.Match[str]) -> str:
        v = c.get(m.group(1), f"?{m.group(1)}?")
        if isinstance(v, dict):
            return ", ".join(f"{k} {w}" for k, w in v.items())
        return str(v)

    return _PLACE.sub(rempl, texte)


def cellule(t: str) -> str:
    return t.replace("|", "/").replace("\n", " ")


def main() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    c: dict[str, Any] = {}
    for f in (
        comptes_file,
        comptes_aides,
        comptes_faits,
        comptes_territoires,
        comptes_prospection,
        comptes_veille,
        comptes_journaux,
    ):
        f(c)
    e = enums()
    ver = mesurer_verites(c)
    E = etages()
    D = decisions(e)

    for x in E:
        for k in ("volume", "cout"):
            x[k] = remplir(x[k], c)
    for x in D:
        x["volume"] = remplir(x["volume"], c)
        x["options"] = remplir(x["options"], c)

    (SORTIE / "enums.json").write_text(
        json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (SORTIE / "comptes.json").write_text(
        json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    with (SORTIE / "ancres.tsv").open("w", encoding="utf-8") as f:
        f.write("id\tfichier\tmotif\tresultat\n")
        for ident, fichier, motif, res in ANCRES:
            f.write(f"{ident}\t{fichier}\t{motif}\t{res}\n")
    with (SORTIE / "verites.tsv").open("w", encoding="utf-8") as f:
        f.write("cle\tclasse\tchemin\ttaille\tprovenance\tbruit\n")
        for ligne in ver:
            f.write("\t".join((ligne[0], CLASSES[ligne[0]], *ligne[1:])) + "\n")

    cles_e = [
        "id",
        "chaine",
        "nom",
        "op",
        "decideur",
        "modele",
        "entree",
        "sortie",
        "cout",
        "volume",
        "ou",
    ]
    with (SORTIE / "etages.tsv").open("w", encoding="utf-8") as f:
        f.write("\t".join(cles_e) + "\n")
        for x in E:
            f.write("\t".join(cellule(str(x[k])) for k in cles_e) + "\n")
    md = [
        "| id | chaîne | étage | op. | décideur | modèle | entrée | sortie | coût | volume | où |",
        "|" + "---|" * 11,
    ]
    for x in E:
        md.append(
            "| "
            + " | ".join(
                cellule(str(x[k] if k != "op" else f"{x['op']} {OPERATIONS[x['op']]}"))
                for k in cles_e
            )
            + " |"
        )
    (SORTIE / "etages.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    with (SORTIE / "decisions.tsv").open("w", encoding="utf-8") as f:
        f.write("id\tchaine\tquestion\toptions\tdecideur\tou\top\tverite\tvolume\n")
        for x in D:
            v = "; ".join(x["verites"]) or "aucune"
            f.write(
                "\t".join(
                    cellule(str(x[k]))
                    for k in ("id", "chaine", "question", "options", "decideur", "ou", "op")
                )
                + f"\t{v}\t{cellule(x['volume'])}\n"
            )
    md = [
        "| id | question | options | décideur | où | op. | volume | vérité terrain |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for x in D:
        if x["verites"]:
            v = "<br>".join(f"`{k}` ({c.get('verite.' + k)}, {CLASSES[k]})" for k in x["verites"])
        elif x["sans"] is not None and x["sans"][1] == 0:
            v = "aucune (sans objet : " + x["sans"][0].removeprefix("sans objet : ") + ")"
        else:
            v = "**aucune**"
        md.append(
            "| "
            + " | ".join(
                cellule(s)
                for s in (
                    x["id"],
                    x["question"],
                    x["options"],
                    x["decideur"],
                    x["ou"],
                    x["op"],
                    x["volume"],
                )
            )
            + f" | {v} |"
        )
    (SORTIE / "decisions.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # Rattachement par opération : étages, décisions, et part des décisions avec vérité.
    md = [
        "| opération | étages | décisions | avec vérité terrain | sans vérité (échantillon) | sans objet |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for op, nom in OPERATIONS.items():
        es = [x["id"] for x in E if x["op"] == op]
        ds = [x for x in D if x["op"] == op]
        avec = sum(1 for x in ds if x["verites"])
        objet = sum(1 for x in ds if not x["verites"] and x["sans"] and x["sans"][1] == 0)
        md.append(
            f"| {op} {nom} | {', '.join(es) or '(aucun)'} | {len(ds)} | {avec} "
            f"| {len(ds) - avec - objet} | {objet} |"
        )
    (SORTIE / "par_operation.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # Échantillons de contrôle : minutes de Félix et dollars de modèle pour 100 cas.
    def num(v: float, fmt: str = "g") -> str:
        return format(v, fmt).replace(".", ",")

    sans = [x for x in D if not x["verites"] and x["sans"] is not None and x["sans"][1] > 0]
    sans_objet = [x for x in D if not x["verites"] and x["sans"] is not None and x["sans"][1] == 0]
    md = [
        "| id | échantillon de 100 cas | min/cas | minutes Félix | $ machine | op. |",
        "|---|---|---:|---:|---:|---|",
    ]
    total_min = total_usd = 0.0
    for x in sans:
        quoi, mpc, usd = x["sans"]
        total_min += 100 * mpc
        total_usd += usd
        md.append(
            f"| {x['id']} | {cellule(remplir(quoi, c))} | {num(mpc)} | {num(100 * mpc)} "
            f"| {num(usd, '.2f')} | {x['op']} |"
        )
    md.append(f"| total | {len(sans)} décisions | | {num(total_min)} | {num(total_usd, '.2f')} | |")
    md += ["", "| id | sans objet | op. |", "|---|---|---|"]
    for x in sans_objet:
        md.append(f"| {x['id']} | {cellule(remplir(x['sans'][0], c))} | {x['op']} |")
    (SORTIE / "sans_verite.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    manquantes = [x for x in ANCRES if x[3].startswith("MANQUANT")]
    par_op = Counter(x["op"] for x in D)
    par_decideur = Counter()
    for x in D:
        dec = x["decideur"].lower()
        for cle in ("félix", "jev", "llm", "code"):
            if cle in dec:
                par_decideur[cle] += 1
    regles = sans_objet

    def principal(texte: str) -> str:
        """Le premier décideur nommé : c'est celui qui tranche aujourd'hui."""
        t = texte.lower()
        positions = {k: t.find(k) for k in ("félix", "jev", "llm", "code") if t.find(k) >= 0}
        if "claude" in t and ("félix" not in positions or t.find("claude") < positions["félix"]):
            positions["félix"] = t.find("claude")
        return min(positions, key=positions.get) if positions else "?"

    par_principal = Counter(principal(x["decideur"]) for x in D)
    meilleure = Counter(
        min((CLASSES[k] for k in x["verites"]), key=RANG_CLASSE.get) for x in D if x["verites"]
    )
    par_chaine = Counter(x["chaine"] for x in D)
    etages_chaine = Counter(x["chaine"] for x in E)
    resume = [
        f"étages : {len(E)} ; décisions fermées : {len(D)}",
        f"décisions avec vérité terrain citée : {sum(1 for x in D if x['verites'])}",
        f"décisions sans vérité terrain, échantillon chiffré : {len(sans)}",
        f"décisions sans objet pour un échantillon (ordonnancement, technique, geste) : {len(regles)}",
        f"décisions par opération : {dict(sorted(par_op.items(), key=lambda kv: int(kv[0][1:])))}",
        f"décideurs cités (une décision peut en citer plusieurs) : {dict(par_decideur)}",
        f"décideur principal (premier nommé ; Claude compté avec Félix) : {dict(par_principal)}",
        f"décisions par chaîne : {dict(par_chaine)} ; étages par chaîne : {dict(etages_chaine)}",
        f"meilleure provenance de la vérité terrain, par décision : {dict(meilleure)}",
        f"échantillons : {total_min:g} minutes de Félix, {total_usd:.2f} $ de modèle",
        f"ancres : {len(ANCRES)}, manquantes : {len(manquantes)}",
        *[f"  MANQUANT {m[0]} {m[1]} {m[2]}" for m in manquantes],
        f"taux de modèle tracé dans la file : {taux(c['file.ingestion.modele_trace'], c['file.avec_bloc_ingestion'])}",
    ]
    (SORTIE / "resume.txt").write_text("\n".join(resume) + "\n", encoding="utf-8")
    print("\n".join(resume))
    return 0 if not manquantes else 1


if __name__ == "__main__":
    sys.exit(main())
