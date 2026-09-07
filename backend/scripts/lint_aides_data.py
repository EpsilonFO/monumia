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
  - avec `--quotes`, que chaque citation se retrouve dans un snapshot archivé
  - ratchet des `manual_check` : aucune aide ne peut dépasser son compte de
    `manual_check` gate ni de `manual_check` sans notes enregistré dans
    data/manual_check_baseline.json — objectif zéro gate à terme

Deux modes, et la différence est importante :

  - GLOBAL (sans argument) : tout le catalogue, statistiques comprises. C'est
    le mode de la CI et du pre-commit. La dette historique (quotes introuvables
    des aides converties depuis les seeds) y est une INFORMATION : elle ne peut
    pas casser un build pour une faute que personne n'a commise aujourd'hui.
  - MONO-SLUG (`lint_aides_data.py <slug> …`) : seulement ces aides, sans
    statistique globale, et la dette y devient une ERREUR. C'est le mode d'une
    aide qu'on vient d'écrire — elle, on la veut irréprochable, et c'est ce
    contrat que l'agent d'ingestion doit satisfaire avant de rendre la main.

Run (exit 1 si erreur — branchable en CI / pre-commit) :
    cd backend && uv run python scripts/lint_aides_data.py
    cd backend && uv run python scripts/lint_aides_data.py <slug> --quotes
Après un batch de résorption relu, abaisser le plafond :
    uv run python scripts/lint_aides_data.py --update-baseline
"""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import (
    AIDES_DIR,
    COMBINATOR_OPS,
    ENUM_FACT_TYPES,
    FACTS_FILE,
    FACTS_PENDING_FILE,
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from veille_collect import load_baselines
from veille_text import find_quote_in_any

# Kinds dont la condition est opposable à une source : la quote y est attendue
# à terme (les conditions issues des seeds legacy n'en ont pas encore).
EVALUABLE_KINDS = ("auto", "user_fact", "discretionary", "manual_check")

# Ratchet de la dette `manual_check` : {slug: {"gates": n, "sans_notes": m}}.
# Un manual_check + gate rend l'aide indécidable (toujours « À confirmer »,
# sans question posée) : chaque compte ne peut que baisser, une aide nouvelle
# part de zéro. Le fichier ne se réécrit que via --update-baseline, après
# relecture (le diff git du baseline EST la revue de la dette).
BASELINE_FILE = Path(__file__).resolve().parent.parent / "data" / "manual_check_baseline.json"

# (slug, id de condition, quote) — le triplet suffit à retrouver la ligne.
Citation = tuple[str, str, str]


def manual_check_counts(aides: list[Aide]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for aide in aides:
        mc = [c for c in aide.conditions if c.kind == "manual_check"]
        gates = sum(1 for c in mc if c.effect == "gate")
        sans_notes = sum(1 for c in mc if not (c.notes or "").strip())
        if gates or sans_notes:
            counts[aide.slug] = {"gates": gates, "sans_notes": sans_notes}
    return counts


def check_manual_check_ratchet(
    counts: dict[str, dict[str, int]], baseline_path: Path = BASELINE_FILE
) -> list[str]:
    if not baseline_path.exists():
        return [
            f"{baseline_path.name} absent — le générer : "
            "uv run python scripts/lint_aides_data.py --update-baseline"
        ]
    baseline: dict[str, dict[str, int]] = json.loads(baseline_path.read_text(encoding="utf-8"))
    errors = []
    for slug, cur in sorted(counts.items()):
        base = baseline.get(slug, {"gates": 0, "sans_notes": 0})
        if cur["gates"] > base["gates"]:
            errors.append(
                f"{slug}: {cur['gates']} manual_check gate (plafond {base['gates']}) — "
                "retyper via l'arbre de TYPING.md, pas de nouveau manual_check gate"
            )
        if cur["sans_notes"] > base["sans_notes"]:
            errors.append(
                f"{slug}: {cur['sans_notes']} manual_check sans notes "
                f"(plafond {base['sans_notes']}) — notes obligatoires (pourquoi irréductible)"
            )
    return errors


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
        if fact.type in ENUM_FACT_TYPES:
            option_ids = {o.id for o in fact.options or []}
            vals = val if isinstance(val, list) else [val]
            bad = [v for v in vals if v not in option_ids]
            if bad:
                errors.append(f"{where}: valeur(s) hors options du fait : {bad}")
        if fact.type == "boolean" and not isinstance(val, bool):
            errors.append(f"{where}: un fait boolean se compare à true/false, reçu {val!r}")
    return errors


def check_field_predicate(where: str, field_path: str | None, predicate: Predicate) -> list[str]:
    errors: list[str] = []
    spec = FIELD_REGISTRY.get(field_path or "")
    if spec is None:
        errors.append(f"{where}: champ inconnu « {field_path} » (absent de FIELD_REGISTRY)")
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


# ---------------------------------------------------------------------------
# Quotes : la citation est-elle dans un snapshot archivé ?
# ---------------------------------------------------------------------------


def check_quotes(
    aide: Aide, documents: list[tuple[str, str, str]], illisibles: Sequence[str] = ()
) -> tuple[list[Citation], list[Citation], list[Citation]]:
    """(absentes, dégradées, hors portée) pour une aide, contre ses snapshots.

    Même définition que `veille_quotes_audit` — un seul verdict de ce qu'est
    une citation justifiée, sinon l'audit et le lint diraient deux choses
    différentes de la même donnée.

    « Hors portée » recouvre les deux cas où l'absence n'accuse pas la
    citation : aucun snapshot exploitable pour l'aide, ou un règlement PDF
    scanné dont `pdftotext` ne tire rien. Les imputer à la dette reviendrait à
    reprocher à une ingestion l'illisibilité de sa source.
    """
    citees = [c for c in aide.conditions if c.quote]
    if not documents:
        return [], [], [(aide.slug, c.id, c.quote or "") for c in citees]

    absentes: list[Citation] = []
    degradees: list[Citation] = []
    hors_portee: list[Citation] = []
    for cond in citees:
        _nom, match = find_quote_in_any(cond.quote or "", documents)  # type: ignore[arg-type]
        if not match.found:
            (hors_portee if illisibles else absentes).append((aide.slug, cond.id, cond.quote or ""))
        elif match.status != "exacte" or match.reconstitution:
            degradees.append((aide.slug, cond.id, cond.quote or ""))
    return absentes, degradees, hors_portee


def _extrait(quote: str, taille: int = 90) -> str:
    plat = " ".join(quote.split())
    return plat if len(plat) <= taille else plat[:taille] + "…"


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------


@dataclass
class RapportLint:
    """Ce que le lint a trouvé. `ok` seul décide du code de sortie."""

    erreurs: list[str] = field(default_factory=list)
    lignes: list[str] = field(default_factory=list)
    aides: list[Aide] = field(default_factory=list)
    quotes_absentes: list[Citation] = field(default_factory=list)
    quotes_degradees: list[Citation] = field(default_factory=list)
    quotes_hors_portee: list[Citation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erreurs

    def texte(self) -> str:
        sortie = list(self.lignes)
        if self.erreurs:
            sortie.append(f"\n✗ {len(self.erreurs)} erreur(s) :")
            sortie.extend(f"  - {e}" for e in self.erreurs)
        else:
            sortie.append("\n✓ lint OK")
        return "\n".join(sortie)


def lint(
    slugs: Sequence[str] = (),
    *,
    strict: bool = False,
    quotes: bool = False,
    ratchet: bool = True,
    aides_dir: Path = AIDES_DIR,
    facts_path: Path = FACTS_FILE,
    pending_path: Path = FACTS_PENDING_FILE,
    baseline_path: Path = BASELINE_FILE,
) -> RapportLint:
    """Lint du catalogue entier, ou des seuls `slugs` donnés.

    Les caches de `load_facts` / `load_pending_facts` sont vidés en entrée :
    l'agent d'ingestion appelle ce lint DANS le même processus, entre deux
    écritures de `facts_pending.yaml` — un fait qu'il vient de proposer doit
    être vu, sinon il se ferait refuser sa propre proposition.
    """
    load_facts.cache_clear()
    load_pending_facts.cache_clear()
    rapport = RapportLint()

    try:
        approved = load_facts(facts_path)
        pending = load_pending_facts(pending_path)
    except Exception as e:
        rapport.erreurs.append(f"facts.yaml / facts_pending.yaml invalide : {e}")
        return rapport

    collisions = sorted(set(approved) & set(pending))
    if collisions:
        rapport.erreurs.append(f"facts_pending.yaml: clé(s) déjà dans facts.yaml : {collisions}")
    # Les conditions sont validées contre l'union approuvés + pending : un fait
    # proposé est utilisable immédiatement par le typage, mais reste signalé
    # (bloquant en --strict, pour la CI) tant qu'il n'a pas été approuvé.
    facts = {**approved, **pending}
    rapport.erreurs.extend(check_facts(facts))

    global_mode = not slugs
    chemins = (
        sorted(aides_dir.glob("*.yaml"))
        if global_mode
        else [aides_dir / f"{s}.yaml" for s in slugs]
    )
    for path in chemins:
        if not path.exists():
            rapport.erreurs.append(f"{path.name}: fichier absent de {aides_dir}")
            continue
        try:
            aide = load_aide(path)
        except Exception as e:
            rapport.erreurs.append(f"{path.name}: {e}")
            continue
        rapport.aides.append(aide)
        rapport.erreurs.extend(check_aide(aide, facts))

    if global_mode:
        rapport.lignes.extend(_statistiques(rapport.aides, facts))
    else:
        rapport.lignes.append(f"aides   : {len(rapport.aides)} fichier(s) — {', '.join(slugs)}")
        kinds = Counter(c.kind for a in rapport.aides for c in a.conditions)
        if kinds:
            rapport.lignes.append(
                "conditions : "
                + ", ".join(f"{n} {kind}" for kind, n in sorted(kinds.items()))
                + f" ({sum(kinds.values())} au total)"
            )

    rapport.lignes.extend(_bloc_pending(rapport.aides, pending, strict, rapport))
    if quotes:
        _bloc_quotes(rapport, global_mode)

    mc_counts = manual_check_counts(rapport.aides)
    n_gates = sum(c["gates"] for c in mc_counts.values())
    n_sans_notes = sum(c["sans_notes"] for c in mc_counts.values())
    n_aides_gates = sum(1 for c in mc_counts.values() if c["gates"])
    rapport.lignes.append(
        f"manual_check : {n_gates} gate(s) sur {n_aides_gates} aide(s) — objectif zéro ; "
        f"{n_sans_notes} sans notes (ratchet : {baseline_path.name})"
    )
    if ratchet:
        rapport.erreurs.extend(check_manual_check_ratchet(mc_counts, baseline_path))

    if global_mode:
        rapport.lignes.extend(_bloc_calendrier(rapport.aides))
    return rapport


def _statistiques(aides: list[Aide], facts: dict[str, FactDef]) -> list[str]:
    """Le tableau de bord du catalogue — seulement en mode global.

    En mono-slug ces chiffres seraient trompeurs (« 2 faits utilisés sur 239 »)
    et noieraient les trois lignes qui comptent.
    """
    lignes: list[str] = []
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

    lignes.append(f"aides   : {len(aides)} fichiers valides")
    lignes.append(f"faits   : {len(facts)} dans l'ontologie, {len(fact_usage)} utilisés")
    lignes.append(
        f"conditions : {n_cond} au total — typées {n_typed} ({n_typed * 100 // max(n_cond, 1)} %)"
    )
    for kind, n in kinds.most_common():
        lignes.append(f"  {kind:<14} {n}")
    if fact_usage:
        lignes.append("faits les plus référencés :")
        for fact_id, n in fact_usage.most_common(10):
            lignes.append(f"  {fact_id:<32} {n} condition(s)")
    unused = sorted(set(facts) - set(fact_usage))
    if unused:
        lignes.append(f"faits non référencés ({len(unused)}) : {', '.join(unused)}")

    # Dette de provenance : conditions opposables à une source mais sans quote.
    # Non bloquant pendant la transition (les conditions venues des seeds n'ont
    # pas de source) ; toute aide ré-ingérée depuis sa source doit être à zéro.
    evaluables = [c for a in aides for c in a.conditions if c.kind in EVALUABLE_KINDS]
    sans_quote = sum(1 for c in evaluables if not c.quote)
    if evaluables:
        lignes.append(
            f"quotes : {len(evaluables) - sans_quote}/{len(evaluables)} conditions "
            f"évaluables sourcées — dette : {sans_quote}"
        )

    sans_raison = sum(1 for a in aides if not a.raison)
    if sans_raison:
        lignes.append(f"raison : {sans_raison} aide(s) sans finalité — valeur en base préservée")

    # Couverture du rattachement au référentiel de pièces : le mapping est
    # incrémental (scripts/map_pieces.py), ce chiffre suit sa progression.
    total_pieces = sum(len(a.documents_requis) for a in aides)
    rattachees = sum(1 for a in aides for d in a.documents_requis if d.piece_id is not None)
    if total_pieces:
        pct = round(100 * rattachees / total_pieces)
        lignes.append(f"pièces rattachées au référentiel : {rattachees}/{total_pieces} ({pct} %)")
    return lignes


def _bloc_pending(
    aides: list[Aide], pending: dict[str, FactDef], strict: bool, rapport: RapportLint
) -> list[str]:
    if not pending:
        return []
    refs = [
        f"{a.slug} / {c.id} → {ref}"
        for a in aides
        for c in a.conditions
        for ref in [c.fact, c.applies_if.fact if c.applies_if else None]
        if ref in pending
    ]
    lignes = [
        f"⏳ faits en attente d'approbation ({len(pending)}) : {', '.join(sorted(pending))}",
        *(f"   {ref}" for ref in refs),
    ]
    if strict:
        rapport.erreurs.append(
            f"--strict : {len(pending)} fait(s) non approuvé(s) dans facts_pending.yaml "
            "— approuver (déplacer vers facts.yaml) avant merge"
        )
    return lignes


def _bloc_quotes(rapport: RapportLint, global_mode: bool) -> None:
    """Vérifie chaque citation contre les snapshots, et range le verdict.

    En mono-slug l'absence est une ERREUR : l'aide vient d'être écrite depuis
    sa source, une citation qu'on ne retrouve pas y a donc été inventée ou
    recopiée de travers, et c'est précisément ce que le contrat d'ingestion
    interdit. En global c'est une information — la dette héritée des seeds
    (~6 % du corpus) ne peut pas casser la CI.
    """
    sans_snapshot: list[str] = []
    pdf_illisibles: list[tuple[str, str]] = []
    for aide in rapport.aides:
        documents, illisibles, _provenance = load_baselines(aide.slug)
        absentes, degradees, hors_portee = check_quotes(aide, documents, illisibles)
        rapport.quotes_absentes.extend(absentes)
        rapport.quotes_degradees.extend(degradees)
        rapport.quotes_hors_portee.extend(hors_portee)
        if hors_portee and not documents:
            sans_snapshot.append(aide.slug)
        elif illisibles:
            pdf_illisibles.append((aide.slug, ", ".join(illisibles)))

    citees = sum(1 for a in rapport.aides for c in a.conditions if c.quote)
    n_abs = len(rapport.quotes_absentes)
    rapport.lignes.append(
        f"quotes vérifiées : {citees} citation(s) — {n_abs} introuvable(s), "
        f"{len(rapport.quotes_degradees)} retrouvée(s) après normalisation, "
        f"{len(rapport.quotes_hors_portee)} hors portée (aucun snapshot, ou PDF illisible)"
    )

    if global_mode:
        for slug, cond_id, quote in rapport.quotes_absentes[:20]:
            rapport.lignes.append(f"  introuvable : {slug} / {cond_id} — « {_extrait(quote)} »")
        if n_abs > 20:
            rapport.lignes.append(f"  … et {n_abs - 20} autre(s)")
        return

    for slug, cond_id, quote in rapport.quotes_absentes:
        rapport.erreurs.append(
            f"{slug} / {cond_id}: quote introuvable dans les snapshots de "
            f"data/sources/{slug}/ — « {_extrait(quote)} »"
        )
    # Une aide qu'on vient d'ingérer DOIT avoir archivé sa source : sans
    # snapshot, aucune de ses citations n'est opposable et la review humaine
    # n'a rien à relire.
    for slug in sans_snapshot:
        rapport.erreurs.append(
            f"{slug}: citations présentes mais aucun snapshot exploitable dans "
            f"data/sources/{slug}/ — snapshoter la source avant de citer"
        )
    for slug, illisibles in pdf_illisibles:
        rapport.lignes.append(f"  {slug}: citations non vérifiables — PDF illisible ({illisibles})")


def _bloc_calendrier(aides: list[Aide]) -> list[str]:
    """Dette de calendrier : sans `permanent` ni aucune date structurée, la
    disponibilité (« maintenant » / « bientôt ») est indéterminable et l'aide
    est réputée ouverte par défaut. Non bloquant, même en --strict : 22
    fichiers sont dans ce cas et l'information n'est pas toujours sourçable."""
    sans_calendrier = sorted(
        a.slug
        for a in aides
        if not a.calendrier.permanent
        and not a.calendrier.date_ouverture
        and not a.calendrier.date_limite
    )
    if not sans_calendrier:
        return []
    return [
        f"calendrier : {len(sans_calendrier)} aide(s) non permanentes sans date "
        f"d'ouverture ni date limite — disponibilité indéterminable, réputée ouverte :",
        *(f"  {slug}" for slug in sans_calendrier),
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lint_aides_data.py",
        description="Lint des données d'aides. Sans slug : tout le catalogue.",
    )
    parser.add_argument("slugs", nargs="*", help="n'auditer que ces aides (mode strict sur elles)")
    parser.add_argument(
        "--strict", action="store_true", help="échoue si des faits attendent une approbation"
    )
    parser.add_argument(
        "--quotes",
        action="store_true",
        help="vérifie chaque citation contre les snapshots de data/sources/",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="réécrit le ratchet manual_check depuis l'état courant (à relire au diff)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.update_baseline and args.slugs:
        # Le baseline est un plafond GLOBAL : le réécrire depuis un
        # sous-ensemble effacerait la dette de toutes les aides non citées.
        print("✗ --update-baseline porte sur tout le catalogue : ne pas passer de slug")
        return 2

    # Chemins passés explicitement, et lus dans les globales du module au
    # moment de l'appel : les valeurs par défaut de `lint()` sont figées à la
    # définition de la fonction, donc invisibles à un `mock.patch.object` — ce
    # qui rendrait les tests inopérants sur `main()`.
    rapport = lint(
        args.slugs,
        strict=args.strict,
        quotes=args.quotes,
        ratchet=not args.update_baseline,
        aides_dir=AIDES_DIR,
        facts_path=FACTS_FILE,
        pending_path=FACTS_PENDING_FILE,
        baseline_path=BASELINE_FILE,
    )
    print(rapport.texte())

    if args.update_baseline:
        counts = manual_check_counts(rapport.aides)
        BASELINE_FILE.write_text(
            json.dumps(counts, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"baseline réécrit : {BASELINE_FILE.name} ({len(counts)} aide(s)) — à relire au diff")
    return 0 if rapport.ok else 1


if __name__ == "__main__":
    sys.exit(main())
