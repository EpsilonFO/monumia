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
  - ratchet des `manual_check` : aucune aide ne peut dépasser son compte de
    `manual_check` gate ni de `manual_check` sans notes enregistré dans
    data/manual_check_baseline.json — objectif zéro gate à terme

Run (exit 1 si erreur — branchable en CI / pre-commit) :
    cd backend && uv run python scripts/lint_aides_data.py
Après un batch de résorption relu, abaisser le plafond :
    uv run python scripts/lint_aides_data.py --update-baseline
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aides_schema import (
    AIDES_DIR,
    FIELD_REGISTRY,
    OPS_BY_FIELD_TYPE,
    Aide,
    FactDef,
    Predicate,
    # Remontée dans aides_schema (second usager au runtime : /admin). Réimportée
    # ici parce que `veille_apply` et `veille_typage` l'importent DU LINT.
    check_fact_predicate,
    evaluate_predicate,
    load_aide,
    load_facts,
    load_pending_facts,
    predicate_leaves,
)
from eligibility_engine import _normalize_answer, deduire_faits_des_faits
from labels import DEPARTEMENT_LABELS, REGION_LABELS

# `help` NOMINATIF : marqueurs de financeur et de territoire. Un fait cité par
# plusieurs aides dont l'aide contextuelle nomme un seul financeur fait croire
# que la question ne concerne que celui-là — c'est le retour du testeur du
# 2026-09-16 sur `budget_projet_mediation` et `appellation_musee_de_france`,
# dont le `help` nommait un autre financeur que l'aide qui posait la question.
# Les libellés de territoire viennent du référentiel, pas d'une liste à tenir.
MOTIFS_NOMINATIFS = re.compile(
    "|".join(
        [
            r"\bR[ée]gion\b",
            r"\bD[ée]partement\b",
            r"\bConseil d[ée]partemental\b",
            r"\bFondation\b",
            r"\bAcad[ée]mie\b",
            r"\bInstitut de France\b",
            r"\bDRAC\b",
            r"\bGIP\b",
            r"\bFEDER\b",
            r"\bVMF\b",
            r"\bREMPART\b",
            r"\bDemeure Historique\b",
            *(re.escape(nom) for nom in {**REGION_LABELS, **DEPARTEMENT_LABELS}.values()),
        ]
    )
)

# Kinds dont la condition est opposable à une source : la quote y est attendue
# à terme (les conditions issues des seeds legacy n'en ont pas encore).
EVALUABLE_KINDS = ("auto", "user_fact", "discretionary", "manual_check")

# Ratchet de la dette `manual_check` : {slug: {"gates": n, "sans_notes": m}}.
# Un manual_check + gate rend l'aide indécidable (toujours « À confirmer »,
# sans question posée) : chaque compte ne peut que baisser, une aide nouvelle
# part de zéro. Le fichier ne se réécrit que via --update-baseline, après
# relecture (le diff git du baseline EST la revue de la dette).
BASELINE_FILE = Path(__file__).resolve().parent.parent / "data" / "manual_check_baseline.json"


def manual_check_counts(aides: list[Aide]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for aide in aides:
        mc = [c for c in aide.conditions if c.kind == "manual_check"]
        gates = sum(1 for c in mc if c.effect == "gate")
        sans_notes = sum(1 for c in mc if not (c.notes or "").strip())
        if gates or sans_notes:
            counts[aide.slug] = {"gates": gates, "sans_notes": sans_notes}
    return counts


def check_manual_check_ratchet(counts: dict[str, dict[str, int]]) -> list[str]:
    if not BASELINE_FILE.exists():
        return [
            f"{BASELINE_FILE.name} absent — le générer : "
            "uv run python scripts/lint_aides_data.py --update-baseline"
        ]
    baseline: dict[str, dict[str, int]] = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
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


def check_field_predicate(where: str, field: str | None, predicate: Predicate) -> list[str]:
    errors: list[str] = []
    spec = FIELD_REGISTRY.get(field or "")
    if spec is None:
        errors.append(f"{where}: champ inconnu « {field} » (absent de FIELD_REGISTRY)")
        return errors
    allowed_ops = OPS_BY_FIELD_TYPE[spec["type"]]
    values = spec.get("values")
    for op, val in predicate_leaves(predicate.root):
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


def check_hors_gate(aide: Aide, facts: dict[str, FactDef]) -> list[str]:
    """Aucun gate, aucun périmètre sur un fait marqué `hors_gate`.

    Miroir, côté pipeline, du test de corpus
    `test_corpus_autofinancement_ne_gate_plus_nulle_part` : l'agent d'ingestion
    voit le lint, jamais pytest.
    """
    conseil = "typer manual_check + info (TYPING, « manual_check + effect: info »)"
    erreurs: list[str] = []

    def _hors_gate(fact: str | None) -> bool:
        return bool(fact) and fact in facts and facts[fact].hors_gate

    if aide.applies_if and _hors_gate(aide.applies_if.fact):
        erreurs.append(
            f"{aide.slug} / applies_if: fait « {aide.applies_if.fact} » hors_gate — {conseil}"
        )
    for cond in aide.conditions:
        where = f"{aide.slug} / {cond.id}"
        if cond.effect == "gate" and _hors_gate(cond.fact):
            erreurs.append(
                f"{where}: gate sur le fait « {cond.fact} » marqué hors_gate — {conseil}"
            )
        if cond.applies_if and _hors_gate(cond.applies_if.fact):
            erreurs.append(
                f"{where}: applies_if sur le fait « {cond.applies_if.fact} » hors_gate — {conseil}"
            )
    return erreurs


# Marqueur de lien d'auteur — `[[fait]]`. Il n'a jamais été rendu : le front
# affiche `question` et `help` tels quels, crochets compris. Le lecteur d'un
# `help` est l'UTILISATEUR ; un renvoi vers une autre question s'écrit en
# français (« la question sur le statut juridique du porteur »). Les
# commentaires YAML, eux, restent libres : ils ne sortent jamais du fichier.
LIEN_AUTEUR = "[["


def check_facts(facts: dict[str, FactDef]) -> list[str]:
    erreurs = [
        f"facts.yaml / {key}: auto_source « {f.auto_source} » absent de FIELD_REGISTRY"
        for key, f in facts.items()
        if f.auto_source and f.auto_source not in FIELD_REGISTRY
    ]
    erreurs += [
        f"facts.yaml / {key}: `{champ}` contient un lien d'auteur `[[…]]`, rendu brut à "
        f"l'écran — le réécrire en français"
        for key, f in facts.items()
        for champ in ("question", "help")
        if LIEN_AUTEUR in (getattr(f, champ, None) or "")
    ]
    erreurs += [
        f"facts.yaml / {key} / option {o.id}: `label` contient un lien d'auteur `[[…]]`"
        for key, f in facts.items()
        for o in f.options or []
        if LIEN_AUTEUR in o.label
    ]
    erreurs.extend(check_pertinent_si(facts))
    return erreurs


def check_pertinent_si(facts: dict[str, FactDef]) -> list[str]:
    """La dépendance intrinsèque d'un fait : cible, prédicat, et pas de chaîne.

    Le prédicat est validé par `check_fact_predicate`, la MÊME fonction que les
    conditions d'aides et l'administration du catalogue : une clause qui
    citerait une option inexistante ne serait jamais vraie, et la question
    qu'elle gouverne ne serait plus jamais posée — un fait tu, pas une erreur.

    La chaîne est limitée à UN niveau parce que `build_questions` suppose une
    seule passerelle (`_depends_on` ne projette qu'un `showForOptionIds`) : une
    question branchée sur une question elle-même branchée resterait invisible.
    """
    erreurs: list[str] = []
    for key, f in facts.items():
        clause = f.pertinent_si
        if clause is None:
            continue
        ou = f"facts.yaml / {key} (pertinent_si)"
        if clause.fact == key:
            erreurs.append(f"{ou}: un fait ne peut pas dépendre de lui-même")
            continue
        cible = facts.get(clause.fact or "")
        if cible is None:
            erreurs.append(f"{ou}: fait cible inconnu « {clause.fact} »")
            continue
        erreurs.extend(check_fact_predicate(ou, clause.fact, clause.predicate, facts))
        if cible.pertinent_si is not None:
            erreurs.append(
                f"{ou}: la cible « {clause.fact} » porte elle-même un `pertinent_si` — "
                "chaîne limitée à un niveau (le questionnaire ne sait rendre qu'une "
                "passerelle)"
            )
    return erreurs


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
        errors.extend(check_hors_gate(aide, facts))

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

    # Couverture du rattachement au référentiel de pièces : le mapping est
    # incrémental (scripts/map_pieces.py), ce chiffre suit sa progression.
    total_pieces = sum(len(a.documents_requis) for a in aides)
    rattachees = sum(1 for a in aides for d in a.documents_requis if d.piece_id is not None)
    if total_pieces:
        pct = round(100 * rattachees / total_pieces)
        print(f"pièces rattachées au référentiel : {rattachees}/{total_pieces} ({pct} %)")

    # Dette manual_check : gates (indécidables, objectif zéro) et absence de notes.
    mc_counts = manual_check_counts(aides)
    n_gates = sum(c["gates"] for c in mc_counts.values())
    n_sans_notes = sum(c["sans_notes"] for c in mc_counts.values())
    n_aides_gates = sum(1 for c in mc_counts.values() if c["gates"])
    print(
        f"manual_check : {n_gates} gate(s) sur {n_aides_gates} aide(s) — objectif zéro ; "
        f"{n_sans_notes} sans notes (ratchet : {BASELINE_FILE.name})"
    )
    if "--update-baseline" in sys.argv:
        BASELINE_FILE.write_text(
            json.dumps(mc_counts, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"baseline réécrit : {BASELINE_FILE.name} ({len(mc_counts)} aide(s)) — à relire au diff"
        )
    else:
        errors.extend(check_manual_check_ratchet(mc_counts))

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

    # `applies_if` de condition qui RÉPÈTE le `pertinent_si` de son fait : la
    # clause est déjà reportée par le moteur, la recopier est du bruit. Non
    # bloquant — c'est un guide pour la migration éditoriale, et une clause
    # propre reste toujours légitime (elle est plus spécifique).
    redondantes = sorted(
        f"{a.slug} / {c.id} ({c.fact})"
        for a in aides
        for c in a.conditions
        if c.fact
        and c.applies_if
        and (pertinent := (facts[c.fact].pertinent_si if c.fact in facts else None))
        and c.applies_if.fact == pertinent.fact
        and c.applies_if.predicate.root == pertinent.predicate.root
    )
    if redondantes:
        print(
            f"pertinent_si : {len(redondantes)} condition(s) dont l'`applies_if` répète la "
            f"dépendance déjà déclarée sur le fait — retirable :"
        )
        for ligne in redondantes:
            print(f"  {ligne}")

    # COHÉRENCE entre `raison` et « aucun travaux » : une aide ne porte
    # `valorisation_rayonnement` que si elle finance une action SANS chantier
    # (cf. data/TYPING.md, § `raison`). Le moteur sait le vérifier — si un de
    # ses gates est réfuté par « ce projet ne comporte pas de travaux », elle ne
    # le fait pas. C'est le filtre strict posé sur la DONNÉE plutôt qu'au
    # runtime : un tag faux se voit ici au lieu de se payer en aides hors sujet
    # et en questions de chantier dans un projet d'animation.
    #
    # Non bloquant : neuf aides restent dans ce cas pour une dette de TYPAGE
    # (plancher de dépenses posé sur `budget_travaux_estime`, gate `acheves`
    # appliqué à un prix d'action), qui se corrige en rouvrant la source. Le
    # ratchet, lui, vit dans
    # `tests/test_eligibility_engine.py::TestProjetSansTravaux`.
    sans_travaux = deduire_faits_des_faits({"etat_travaux": "aucun"}, facts)
    incoherentes = []
    for aide in aides:
        if "valorisation_rayonnement" not in aide.raison:
            continue
        refutes = sorted(
            {
                f"{c.id} ({c.fact})"
                for c in aide.conditions
                if c.kind == "user_fact"
                and c.effect == "gate"
                and c.fact in sans_travaux
                and c.predicate is not None
                and evaluate_predicate(
                    c.predicate.root,
                    _normalize_answer(facts.get(c.fact), sans_travaux[c.fact]),
                )
                is False
            }
        )
        if refutes:
            incoherentes.append(f"{aide.slug} — {', '.join(refutes)}")
    if incoherentes:
        print(
            f"raison : {len(incoherentes)} aide(s) `valorisation_rayonnement` qu'un projet SANS "
            f"TRAVAUX ne peut pas obtenir (tag faux, ou condition trop large) :"
        )
        for ligne in sorted(incoherentes):
            print(f"  {ligne}")

    # Dette de familles : une aide « faire vivre le lieu » sans famille passe
    # tous les cadrages (fail-open par aide) et se présente donc à un projet de
    # spectacles comme à un projet d'hébergement. Non bloquant : le backfill est
    # éditorial et se relit par lots (cf. scripts/proposer_familles.py).
    sans_famille = sorted(
        a.slug for a in aides if "valorisation_rayonnement" in a.raison and not a.familles
    )
    if sans_famille:
        print(
            f"familles : {len(sans_famille)} aide(s) `valorisation_rayonnement` sans famille "
            f"— elles se présentent à tous les projets « faire vivre le lieu » :"
        )
        for slug in sans_famille:
            print(f"  {slug}")

    # `help` NOMINATIF sur un fait PARTAGÉ : la question est posée pour plusieurs
    # aides, et son aide contextuelle n'en nomme qu'une — le lecteur croit que la
    # question ne concerne que ce financeur-là, ou ce territoire-là. Le contexte
    # par aide se donne au complément (`contexteAide`) et sur la fiche, pas dans
    # le `help`. Non bloquant : la réécriture est éditoriale et se fait par lots.
    # Un marqueur que la QUESTION nomme déjà est intrinsèque au fait (« avez-vous
    # obtenu une subvention de l'État (DRAC) ? ») : ce n'est pas le contexte
    # d'une aide parmi d'autres, et le signaler ne serait que du bruit.
    nominatifs = sorted(
        f"{key} ({fact_usage[key]} aides) : {', '.join(sorted(noms))}"
        for key, f in facts.items()
        if fact_usage.get(key, 0) >= 2
        and f.help
        and (
            noms := set(MOTIFS_NOMINATIFS.findall(f.help))
            - set(MOTIFS_NOMINATIFS.findall(f.question or ""))
        )
    )
    if nominatifs:
        print(
            f"help nominatif : {len(nominatifs)} fait(s) partagé(s) par au moins deux aides "
            f"dont le `help` nomme un financeur ou un territoire :"
        )
        for ligne in nominatifs:
            print(f"  {ligne}")

    if errors:
        print(f"\n✗ {len(errors)} erreur(s) :")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("\n✓ lint OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
