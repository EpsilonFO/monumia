"""
Conversion one-shot des seeds Python (scripts/seeds/seed_aide_*.py) vers le
format YAML déclaratif (data/aides/<slug>.yaml).

Extraction par AST — aucun seed n'est exécuté, aucune connexion DB. Le contenu
est préservé verbatim ; les puces de conditions_eligibilite_detail deviennent
des conditions `kind: untyped` à typer ensuite (ingestion, étape 2).

Run:
    cd backend && uv run python scripts/convert_seeds_to_yaml.py
"""

import ast
import re
import sys
import unicodedata
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SEEDS_DIR = Path(__file__).resolve().parent / "seeds"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "aides"

# Table de jointure → (clé hard_filters, clé du code dans la ligne insérée).
JOIN_TABLES = {
    "aides_protections": ("protections", "protection_code"),
    "aides_proprietaires": ("proprietaires", "proprietaire_code"),
    "aides_travaux": ("travaux", "travaux_code"),
    "aides_regions": ("regions", "region_code"),
    "aides_departements": ("departements", "departement_code"),
    "aides_etats_conservation": ("etats_conservation", "etat_conservation_code"),
}
FILTER_KEYS = tuple(k for k, _ in JOIN_TABLES.values())

# Colonnes du dict principal → emplacement dans le YAML.
TOP_LEVEL = {
    "nom",
    "nom_court",
    "organisme",
    "categorie",
    "type",
    "description",
    "description_longue",
    "documents_requis",
    "tags",
}
SOURCE_KEYS = {"url_officielle", "formulaire_url"}
FINANCEMENT_KEYS = {"montant_min", "montant_max", "taux_min", "taux_max", "plancher", "base_ttc"}
CALENDRIER_KEYS = {"permanent", "date_ouverture", "date_limite", "delai_instruction"}
FLAGS_KEYS = {"architecte_requis", "cofinancement_requis"}
SPECIAL_KEYS = {"conditions_eligibilite_detail", "demarche_description", "commune_max_population"}
KNOWN_KEYS = (
    TOP_LEVEL
    | SOURCE_KEYS
    | FINANCEMENT_KEYS
    | CALENDRIER_KEYS
    | FLAGS_KEYS
    | SPECIAL_KEYS
    | set(FILTER_KEYS)
)


# ── Extraction AST ──────────────────────────────────────────────────────────


def _table_name(node: ast.expr) -> str | None:
    """Remonte la chaîne supabase.table("x").insert(...) jusqu'au nom de table."""
    while isinstance(node, (ast.Call, ast.Attribute)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "table"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            return node.args[0].value
        node = node.func if isinstance(node, ast.Call) else node.value
    return None


def extract_inserts(tree: ast.AST, path: Path) -> tuple[dict, dict[str, list[str]]]:
    """Retourne (dict principal aides_v3, codes des tables de jointure)."""
    main: dict | None = None
    filters: dict[str, list[str]] = {}

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "insert"
            and node.args
        ):
            continue
        table = _table_name(node.func.value)
        arg = node.args[0]

        if table == "aides_v3":
            if main is not None:
                raise ValueError(f"{path.name}: plusieurs inserts aides_v3")
            main = ast.literal_eval(arg)  # échoue si valeur non littérale → voulu
        elif table in JOIN_TABLES:
            filter_key, code_key = JOIN_TABLES[table]
            codes = filters.setdefault(filter_key, [])
            if not isinstance(arg, ast.List):
                raise ValueError(f"{path.name}: insert {table} non littéral")
            for elt in arg.elts:
                if not isinstance(elt, ast.Dict):
                    continue
                for k, v in zip(elt.keys, elt.values, strict=True):
                    if (
                        isinstance(k, ast.Constant)
                        and k.value == code_key
                        and isinstance(v, ast.Constant)
                    ):
                        codes.append(v.value)
        elif table == "aides_segments":
            # Filtre segment retiré du produit (migration 20260516180000) :
            # la table n'existe plus, l'éligibilité passe par `proprietaire`.
            continue
        elif table is not None and table not in ("aides_v3", *JOIN_TABLES):
            raise ValueError(f"{path.name}: insert vers table inattendue « {table} »")

    if main is None:
        raise ValueError(f"{path.name}: aucun insert aides_v3 trouvé")
    return main, filters


# ── Découpage des conditions en puces (sans perte) ──────────────────────────


def _is_quote_line(line: str) -> bool:
    s = line.lstrip()
    return s.startswith(">") and (len(s) == 1 or s[1] in (" ", "\t"))


def _is_dash_line(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("-") and (len(s) == 1 or s[1] in (" ", "\t"))


def parse_bullets(text: str) -> list[str]:
    """Découpe en puces, sans perte : les lignes de continuation (sous-puces
    «•», en-têtes) sont rattachées à la puce courante au lieu d'être perdues.
    """
    if not text or not text.strip():
        return []
    lines = text.split("\n")

    if any(_is_quote_line(line) for line in lines):
        bullets, current = [], []
        for raw in lines:
            if _is_quote_line(raw):
                current.append(raw.lstrip()[1:].strip())
            elif raw.strip():
                # ligne hors '>' : rattachée à la puce courante ou puce isolée
                (current if current else bullets).append(raw.strip() if current else raw.strip())
            else:
                if current:
                    bullets.append(" ".join(p for p in current if p))
                    current = []
        if current:
            bullets.append(" ".join(p for p in current if p))
        return [b for b in bullets if b]

    if any(_is_dash_line(line) for line in lines):
        bullets: list[str] = []
        current: str | None = None
        for raw in lines:
            s = raw.strip()
            if not s:
                continue
            if _is_dash_line(raw):
                if current:
                    bullets.append(current)
                current = raw.lstrip()[1:].strip()
            elif current is None:
                current = s  # texte d'en-tête avant la première puce
            else:
                current += " " + s
        if current:
            bullets.append(current)
        return bullets

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return paragraphs if paragraphs else [text.strip()]


_SLUG_RE = re.compile(r"[a-z0-9]+")


def slugify(text: str, max_words: int = 5) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = _SLUG_RE.findall(ascii_text.lower())[:max_words]
    return "-".join(words)[:60] or "condition"


def build_conditions(detail: str | None) -> list[dict]:
    conditions = []
    seen: dict[str, int] = {}
    for bullet in parse_bullets(detail or ""):
        cid = slugify(bullet)
        seen[cid] = seen.get(cid, 0) + 1
        if seen[cid] > 1:
            cid = f"{cid}-{seen[cid]}"
        conditions.append({"id": cid, "text": bullet, "kind": "untyped"})
    return conditions


# ── Assemblage YAML ─────────────────────────────────────────────────────────


def _clean(d: dict) -> dict:
    """Retire les None et listes vides pour garder des YAML lisibles."""
    return {k: v for k, v in d.items() if v is not None and v != []}


def build_yaml_dict(slug: str, main: dict, filters: dict[str, list[str]], path: Path) -> dict:
    unknown = set(main) - KNOWN_KEYS
    if unknown:
        raise ValueError(f"{path.name}: clés non mappées {sorted(unknown)} — étendre le mapping")

    # Filtres : tables de jointure, ou colonnes array directement dans l'insert.
    hard_filters = {}
    for key in FILTER_KEYS:
        values = sorted(set(filters.get(key, []) + (main.get(key) or [])))
        if values:
            hard_filters[key] = values
    if main.get("commune_max_population") is not None:
        hard_filters["commune_max_population"] = main["commune_max_population"]

    out = {
        "slug": slug,
        "nom": main.get("nom"),
        "nom_court": main.get("nom_court"),
        "organisme": main.get("organisme"),
        "categorie": main.get("categorie"),
        "type": main.get("type"),
        "description": main.get("description"),
        "description_longue": main.get("description_longue"),
        "source": _clean({k: main.get(k) for k in ("url_officielle", "formulaire_url")}) or None,
        "financement": _clean(
            {
                k: main.get(k)
                for k in (
                    "montant_min",
                    "montant_max",
                    "taux_min",
                    "taux_max",
                    "plancher",
                    "base_ttc",
                )
            }
        )
        or None,
        "calendrier": _clean(
            {
                k: main.get(k)
                for k in ("permanent", "date_ouverture", "date_limite", "delai_instruction")
            }
        )
        or None,
        "hard_filters": hard_filters or None,
        "conditions": build_conditions(main.get("conditions_eligibilite_detail")),
        "flags": _clean(
            {k: main.get(k) for k in ("architecte_requis", "cofinancement_requis") if main.get(k)}
        )
        or None,
        "demarche": main.get("demarche_description"),
        "documents_requis": main.get("documents_requis") or None,
        "tags": main.get("tags") or None,
    }
    return _clean(out)


class _Dumper(yaml.SafeDumper):
    pass


def _str_representer(dumper: yaml.Dumper, data: str):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_Dumper.add_representer(str, _str_representer)


def dump_yaml(data: dict) -> str:
    return yaml.dump(
        data,
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        width=88,
        default_flow_style=False,
    )


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    force = "--force" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seeds = sorted(SEEDS_DIR.glob("seed_aide_*.py"))
    ok, skipped, failed = 0, 0, []
    n_conditions = 0

    for path in seeds:
        slug = path.stem.removeprefix("seed_aide_").replace("_", "-")
        target = OUT_DIR / f"{slug}.yaml"
        if target.exists() and not force:
            # Ne jamais écraser un YAML existant : il peut contenir du typage
            # manuel. La conversion est one-shot ; --force pour repartir de zéro.
            skipped += 1
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            main_dict, filters = extract_inserts(tree, path)
            doc = build_yaml_dict(slug, main_dict, filters, path)
            (OUT_DIR / f"{slug}.yaml").write_text(dump_yaml(doc), encoding="utf-8")
            n_conditions += len(doc.get("conditions", []))
            ok += 1
        except Exception as e:  # noqa: BLE001 — rapport exhaustif voulu
            failed.append((path.name, str(e)))

    print(f"✓ {ok}/{len(seeds)} seeds convertis → {OUT_DIR}")
    if skipped:
        print(f"  {skipped} déjà présents, non écrasés (--force pour forcer)")
    print(f"  {n_conditions} conditions extraites (kind: untyped)")
    if failed:
        print(f"\n✗ {len(failed)} échec(s) :")
        for name, err in failed:
            print(f"  - {name}: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
