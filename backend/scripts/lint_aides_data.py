"""
Linter des données d'aides (data/aides/*.yaml + data/facts.yaml).

Vérifie :
  - validation Pydantic de chaque fichier (enums, structure, slug = nom de fichier)
  - les `fact` référencés existent dans l'ontologie
  - les `field` (kind: auto, applies_if) existent dans FIELD_REGISTRY
  - l'opérateur du prédicat est compatible avec le type du fait / du champ
  - pour les faits enum et les champs à référentiel : valeurs du prédicat valides
  - les `auto_source` de l'ontologie pointent vers un champ du registre
  - statistiques de couverture du typage (untyped restants) et dette de quotes

Run (exit 1 si erreur — branchable en CI / pre-commit) :
    cd backend && uv run python scripts/lint_aides_data.py
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import (
    AIDES_DIR,
    COMBINATOR_OPS,
    FIELD_REGISTRY,
    OPS_BY_FACT_TYPE,
    OPS_BY_FIELD_TYPE,
    Aide,
    FactDef,
    Predicate,
    load_aide,
    load_facts,
    load_pending_facts,
)

# Kinds dont la condition est opposable à une source : la quote y est attendue
# à terme (les conditions issues des seeds legacy n'en ont pas encore).
EVALUABLE_KINDS = ("auto", "user_fact", "discretionary", "manual_check")


def _leaf_ops_and_values(predicate: dict) -> list[tuple[str, object]]:
    op, val = next(iter(predicate.items()))
    if op in COMBINATOR_OPS:
        return [leaf for p in val for leaf in _leaf_ops_and_values(p)]
    return [(op, val)]


def check_fact_predicate(
    where: str,
    fact_key: str | None,
    predicate: Predicate,
    facts: dict[str, FactDef],
) -> list[str]:
    errors: list[str] = []
    fact = facts.get(fact_key or "")
    if fact is None:
        errors.append(f"{where}: fait inconnu « {fact_key} » (absent de facts.yaml)")
        return errors
    allowed_ops = OPS_BY_FACT_TYPE[fact.type]
    for op, val in _leaf_ops_and_values(predicate.root):
        if op not in allowed_ops:
            errors.append(f"{where}: opérateur « {op} » invalide pour un fait {fact.type}")
        if fact.type == "enum":
            option_ids = {o.id for o in fact.options or []}
            vals = val if isinstance(val, list) else [val]
            bad = [v for v in vals if v not in option_ids]
            if bad:
                errors.append(f"{where}: valeur(s) hors options du fait : {bad}")
        if fact.type == "boolean" and not isinstance(val, bool):
            errors.append(f"{where}: un fait boolean se compare à true/false, reçu {val!r}")
    return errors


def check_field_predicate(where: str, field: str | None, predicate: Predicate) -> list[str]:
    errors: list[str] = []
    spec = FIELD_REGISTRY.get(field or "")
    if spec is None:
        errors.append(f"{where}: champ inconnu « {field} » (absent de FIELD_REGISTRY)")
        return errors
    allowed_ops = OPS_BY_FIELD_TYPE[spec["type"]]
    values = spec.get("values")
    for op, val in _leaf_ops_and_values(predicate.root):
        if op not in allowed_ops:
            errors.append(f"{where}: opérateur « {op} » invalide pour un champ {spec['type']}")
        if values is not None:
            vals = val if isinstance(val, list) else [val]
            bad = [v for v in vals if v not in values]
            if bad:
                errors.append(f"{where}: valeur(s) hors référentiel du champ : {bad}")
        if spec["type"] == "boolean" and not isinstance(val, bool):
            errors.append(f"{where}: un champ boolean se compare à true/false, reçu {val!r}")
    return errors


def check_aide(aide: Aide, facts: dict[str, FactDef]) -> list[str]:
    errors = []
    if aide.applies_if:
        errors.extend(
            check_fact_predicate(
                f"{aide.slug} (périmètre)",
                aide.applies_if.fact,
                aide.applies_if.predicate,
                facts,
            )
        )
    for cond in aide.conditions:
        where = f"{aide.slug} / {cond.id}"
        if cond.kind == "user_fact":
            assert cond.predicate is not None  # garanti par le schéma
            errors.extend(check_fact_predicate(where, cond.fact, cond.predicate, facts))
        elif cond.kind == "auto":
            assert cond.predicate is not None  # garanti par le schéma
            errors.extend(check_field_predicate(where, cond.field, cond.predicate))
        if cond.applies_if:
            w = f"{where} (applies_if)"
            if cond.applies_if.fact:
                errors.extend(
                    check_fact_predicate(w, cond.applies_if.fact, cond.applies_if.predicate, facts)
                )
            else:
                errors.extend(
                    check_field_predicate(w, cond.applies_if.field, cond.applies_if.predicate)
                )
    return errors


def check_facts(facts: dict[str, FactDef]) -> list[str]:
    return [
        f"facts.yaml / {key}: auto_source « {f.auto_source} » absent de FIELD_REGISTRY"
        for key, f in facts.items()
        if f.auto_source and f.auto_source not in FIELD_REGISTRY
    ]


def main() -> int:
    strict = "--strict" in sys.argv
    try:
        approved = load_facts()
        pending = load_pending_facts()
    except Exception as e:
        print(f"✗ facts.yaml / facts_pending.yaml invalide : {e}")
        return 1

    errors: list[str] = []
    collisions = sorted(set(approved) & set(pending))
    if collisions:
        errors.append(f"facts_pending.yaml: clé(s) déjà dans facts.yaml : {collisions}")
    # Les conditions sont validées contre l'union approuvés + pending : un fait
    # proposé est utilisable immédiatement par le typage, mais reste signalé
    # (bloquant en --strict, pour la CI) tant qu'il n'a pas été approuvé.
    facts = {**approved, **pending}
    errors.extend(check_facts(facts))
    aides: list[Aide] = []
    for path in sorted(AIDES_DIR.glob("*.yaml")):
        try:
            aide = load_aide(path)
        except Exception as e:
            errors.append(f"{path.name}: {e}")
            continue
        aides.append(aide)
        errors.extend(check_aide(aide, facts))

    kinds = Counter(c.kind for a in aides for c in a.conditions)
    # Usage : conditions ET clauses applies_if — un fait seulement ciblé par
    # un applies_if est bien « utilisé » (il déclenche une question).
    fact_usage = Counter(
        ref
        for a in aides
        for c in a.conditions
        for ref in [c.fact, c.applies_if.fact if c.applies_if else None]
        if ref
    )
    # Les faits de périmètre comptent comme utilisés : ils déclenchent la
    # première question du questionnaire.
    fact_usage.update(a.applies_if.fact for a in aides if a.applies_if and a.applies_if.fact)
    n_cond = sum(kinds.values())
    n_typed = n_cond - kinds.get("untyped", 0)

    print(f"aides   : {len(aides)} fichiers valides")
    print(f"faits   : {len(facts)} dans l'ontologie, {len(fact_usage)} utilisés")
    print(
        f"conditions : {n_cond} au total — typées {n_typed} ({n_typed * 100 // max(n_cond, 1)} %)"
    )
    for kind, n in kinds.most_common():
        print(f"  {kind:<14} {n}")
    if fact_usage:
        print("faits les plus référencés :")
        for fact, n in fact_usage.most_common(10):
            print(f"  {fact:<32} {n} condition(s)")
    unused = sorted(set(facts) - set(fact_usage))
    if unused:
        print(f"faits non référencés ({len(unused)}) : {', '.join(unused)}")

    if pending:
        refs = [
            f"{a.slug} / {c.id} → {ref}"
            for a in aides
            for c in a.conditions
            for ref in [c.fact, c.applies_if.fact if c.applies_if else None]
            if ref in pending
        ]
        print(f"⏳ faits en attente d'approbation ({len(pending)}) : {', '.join(sorted(pending))}")
        for ref in refs:
            print(f"   {ref}")
        if strict:
            errors.append(
                f"--strict : {len(pending)} fait(s) non approuvé(s) dans facts_pending.yaml "
                "— approuver (déplacer vers facts.yaml) avant merge"
            )

    # Dette de provenance : conditions opposables à une source mais sans quote.
    # Non bloquant pendant la transition (les conditions venues des seeds n'ont
    # pas de source) ; toute aide ré-ingérée depuis sa source doit être à zéro.
    evaluables = [c for a in aides for c in a.conditions if c.kind in EVALUABLE_KINDS]
    sans_quote = sum(1 for c in evaluables if not c.quote)
    if evaluables:
        print(
            f"quotes : {len(evaluables) - sans_quote}/{len(evaluables)} conditions "
            f"évaluables sourcées — dette : {sans_quote}"
        )

    sans_raison = sum(1 for a in aides if not a.raison)
    if sans_raison:
        print(f"raison : {sans_raison} aide(s) sans finalité — valeur en base préservée au load")

    # Dette de calendrier : sans `permanent` ni aucune date structurée, la
    # disponibilité (« maintenant » / « bientôt ») est indéterminable et l'aide
    # est réputée ouverte par défaut. Non bloquant, même en --strict : 22
    # fichiers sont dans ce cas et l'information n'est pas toujours sourçable.
    sans_calendrier = sorted(
        a.slug
        for a in aides
        if not a.calendrier.permanent
        and not a.calendrier.date_ouverture
        and not a.calendrier.date_limite
    )
    if sans_calendrier:
        print(
            f"calendrier : {len(sans_calendrier)} aide(s) non permanentes sans date "
            f"d'ouverture ni date limite — disponibilité indéterminable, réputée ouverte :"
        )
        for slug in sans_calendrier:
            print(f"  {slug}")

    if errors:
        print(f"\n✗ {len(errors)} erreur(s) :")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("\n✓ lint OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
