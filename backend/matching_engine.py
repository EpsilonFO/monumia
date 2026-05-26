"""
Matching engine v2 — uses normalised aides_v2 tables.

Three-phase approach:
  1. SQL pre-filter via prefiltrer_aides() → candidate aide UUIDs (source of truth for eligibility)
  2. Python builds human-readable criteria labels for display (does NOT re-check eligibility)
  3. LLM fine-matching on conditions_eligibilite_detail for nuanced rules
"""

import asyncio
import json
import logging
import os
from datetime import datetime

from mistralai.client import Mistral
from supabase import Client

from labels import (
    ALLOWED_INCERTITUDE_CATEGORIES,
    DEPARTEMENT_LABELS,
    ETAT_LABELS,
    OWNERSHIP_LABELS,
    PROTECTION_LABELS,
    REGION_LABELS,
    TRAVAUX_LABELS,
)
from prompts.matching import render_prompt_eligibility, render_prompt_qcm

logger = logging.getLogger(__name__)


def _label(mapping: dict, value: str | None) -> str:
    if value is None:
        return ""
    return mapping.get(value, value)


def _labels(mapping: dict, values: list) -> str:
    return ", ".join(_label(mapping, v) for v in values)


def _resolve_population(supabase: Client, code_insee: str | None, user: dict) -> int | None:
    """Return the commune's population if the user is a commune, else None."""
    if not code_insee or user.get("segment") != "commune":
        return None
    result = (
        supabase.table("communes")
        .select("population")
        .eq("code_insee", code_insee)
        .single()
        .execute()
    )
    return result.data.get("population") if result.data else None


# ---------------------------------------------------------------------------
# Phase 1: SQL pre-filter
# ---------------------------------------------------------------------------


def prefiltrer_aides(
    supabase: Client,
    monument: dict,
    user: dict,
    travaux_filtres: list[str] | None = None,
) -> list[str]:
    """Call the prefiltrer_aides SQL function and return matching aide UUIDs."""
    travaux = travaux_filtres or monument.get("travaux_envisages") or []

    # Resolve code_insee: fallback from commune name if empty
    code_insee = monument.get("code_insee") or ""
    if not code_insee and monument.get("commune"):
        commune_lookup = (
            supabase.table("communes")
            .select("code_insee, population")
            .eq("nom_commune", monument["commune"])
            .limit(1)
            .execute()
        )
        if commune_lookup.data:
            code_insee = commune_lookup.data[0].get("code_insee", "")

    # Department code: prefer the value enriched from communes (`departement_num`),
    # fall back to extracting it from code_insee (handles Corsica 2A/2B and DOM
    # codes 971–976) when the monument hasn't been enriched yet.
    departement_code = monument.get("departement_num")
    if not departement_code and code_insee:
        if code_insee[:2] in ("2A", "2B"):
            departement_code = code_insee[:2]
        elif code_insee[:3] in ("971", "972", "973", "974", "975", "976"):
            departement_code = code_insee[:3]
        else:
            departement_code = code_insee[:2]

    population = _resolve_population(supabase, code_insee, user)

    params = {
        "p_protection": monument.get("protection"),
        "p_proprietaire": monument.get("proprietaire"),
        "p_travaux": travaux if travaux else None,
        "p_region": monument.get("region"),
        "p_departement": departement_code,
        "p_population": population,
        "p_etat_conservation": monument.get("etat_conservation"),
    }
    logger.debug(
        "[SQL] RPC prefiltrer_aides → params: %s",
        json.dumps(params, ensure_ascii=False, default=str),
    )

    result = supabase.rpc("prefiltrer_aides", params).execute()

    return [row["aide_id"] for row in (result.data or [])]


# ---------------------------------------------------------------------------
# Phase 2: Build human-readable criteria labels (display only, no re-filtering)
# ---------------------------------------------------------------------------


# table → (code column, aide_v2 dict key receiving the list of codes)
_JOIN_TABLES = {
    "aides_protections": ("protection_code", "protections"),
    "aides_proprietaires": ("proprietaire_code", "proprietaires"),
    "aides_travaux": ("travaux_code", "travaux"),
    "aides_regions": ("region_code", "regions"),
    "aides_departements": ("departement_code", "departements"),
    "aides_etats_conservation": ("etat_conservation_code", "etats_conservation"),
}


def fetch_aides_with_joins(supabase: Client, aide_ids: list[str]) -> list[dict]:
    """Fetch multiple aides with their join data. Batch queries per join table."""
    if not aide_ids:
        return []

    aides_result = supabase.table("aides_v2").select("*").in_("id", aide_ids).execute()
    aides_by_id = {a["id"]: a for a in (aides_result.data or [])}

    for aide in aides_by_id.values():
        for _, aide_key in _JOIN_TABLES.values():
            aide[aide_key] = []

    for table_name, (code_col, aide_key) in _JOIN_TABLES.items():
        rows = (
            supabase.table(table_name)
            .select(f"aide_id, {code_col}")
            .in_("aide_id", aide_ids)
            .execute()
        ).data or []
        for row in rows:
            aid = aides_by_id.get(row["aide_id"])
            if aid:
                aid[aide_key].append(row[code_col])

    return list(aides_by_id.values())


def _build_criteria_labels(
    aide: dict,
    monument: dict,
    user: dict,
    mode_projet: bool,
    travaux_filtres: list[str],
    population: int | None = None,
) -> dict:
    """Build human-readable criteria match/mismatch lists for a single aide.

    This does NOT determine eligibility — that is done by the SQL pre-filter.
    The aide dict must already contain join data (protections, proprietaires, etc.)
    as populated by fetch_aides_with_joins().
    """
    criteres_remplis: list[str] = []
    criteres_non_remplis: list[str] = []

    # Simple membership checks (aide restricts to a list → check monument matches one).
    # (aide_key, monument_field, mapping, ok_prefix, required_prefix, fallback)
    # `fallback` is added to criteres_remplis when the aide imposes no restriction;
    # None means stay silent (état de conservation has no "all states" message).
    simple_checks = [
        ("protections", "protection", PROTECTION_LABELS,
         "Protection", "Protection requise", "Tous niveaux de protection"),
        ("proprietaires", "proprietaire", OWNERSHIP_LABELS,
         "Type de propriétaire", "Propriétaire éligible", "Tous types de propriétaires"),
        ("regions", "region", REGION_LABELS,
         "Région", "Région requise", "Toute la France"),
        ("etats_conservation", "etat_conservation", ETAT_LABELS,
         "État de conservation", "État requis", None),
    ]
    for aide_key, monument_field, mapping, ok_prefix, required_prefix, fallback in simple_checks:
        aide_values = aide.get(aide_key) or []
        if not aide_values:
            if fallback:
                criteres_remplis.append(fallback)
            continue
        monument_value = monument.get(monument_field)
        if monument_value in aide_values:
            criteres_remplis.append(f"{ok_prefix} : {_label(mapping, monument_value)}")
        else:
            criteres_non_remplis.append(f"{required_prefix} : {_labels(mapping, aide_values)}")

    # Travaux : has its own monument-value resolution (mode_projet override).
    travaux_eligibles = aide.get("travaux") or []
    if travaux_eligibles:
        travaux_to_check = (
            travaux_filtres
            if (mode_projet and travaux_filtres)
            else (monument.get("travaux_envisages") or [])
        )
        if not travaux_to_check:
            criteres_remplis.append("Types de travaux : non spécifiés (compatible)")
        elif any(t in travaux_eligibles for t in travaux_to_check):
            criteres_remplis.append("Types de travaux compatibles")
        else:
            criteres_non_remplis.append(
                f"Travaux éligibles : {_labels(TRAVAUX_LABELS, travaux_eligibles)}"
            )
    else:
        criteres_remplis.append("Tous types de travaux")

    # Département : compare on the numeric INSEE code (matches aides_departements.departement_code).
    # `monument["departement"]` holds the human label (e.g. "Paris") for display only.
    departements = aide.get("departements") or []
    if departements:
        dep_code = monument.get("departement_num")
        if dep_code and dep_code in departements:
            criteres_remplis.append(
                f"Département : {monument.get('departement') or _label(DEPARTEMENT_LABELS, dep_code)} ({dep_code})"
            )
        else:
            criteres_non_remplis.append(
                f"Département requis : {_labels(DEPARTEMENT_LABELS, departements)}"
            )

    # Population : threshold comparison rather than membership.
    max_pop = aide.get("commune_max_population")
    if max_pop is not None and user.get("segment") == "commune" and population:
        if population <= max_pop:
            criteres_remplis.append(f"Commune ≤ {max_pop:,} hab. ({population} hab.)")
        else:
            criteres_non_remplis.append(f"Réservé aux communes ≤ {max_pop:,} hab.")

    eligible = len(criteres_non_remplis) == 0

    return {
        "aide": aide,
        "eligible": eligible,
        "criteresRemplis": criteres_remplis,
        "criteresNonRemplis": criteres_non_remplis,
        "raisonIneligibilite": criteres_non_remplis[0] if not eligible else None,
    }


# ---------------------------------------------------------------------------
# Phase 3: LLM fine-matching on conditions_eligibilite_detail
# ---------------------------------------------------------------------------


def _build_monument_profile(monument: dict, population: int | None) -> str:
    """Build a human-readable text description of the monument for the LLM."""
    lines = []
    lines.append(f"Nom : {monument.get('nom', 'Non renseigné')}")
    lines.append(f"Protection : {_label(PROTECTION_LABELS, monument.get('protection', ''))}")
    lines.append(f"Propriétaire : {_label(OWNERSHIP_LABELS, monument.get('proprietaire', ''))}")
    lines.append(f"Commune : {monument.get('commune', 'Non renseigné')}")
    lines.append(f"Code INSEE : {monument.get('code_insee', 'Non renseigné')}")
    dep_label = monument.get("departement") or _label(
        DEPARTEMENT_LABELS, monument.get("departement_num")
    )
    dep_num = monument.get("departement_num")
    if dep_label and dep_num:
        lines.append(f"Département : {dep_label} ({dep_num})")
    else:
        lines.append(f"Département : {dep_label or dep_num or 'Non renseigné'}")
    region_display = monument.get("region_label") or _label(REGION_LABELS, monument.get("region"))
    lines.append(f"Région : {region_display or 'Non renseigné'}")
    if population is not None:
        lines.append(f"Population commune : {population} habitants")
    lines.append(
        f"État de conservation : {_label(ETAT_LABELS, monument.get('etat_conservation', ''))}"
    )
    travaux = monument.get("travaux_envisages") or []
    if travaux:
        lines.append(f"Travaux envisagés : {_labels(TRAVAUX_LABELS, travaux)}")
    if monument.get("siecle_construction"):
        lines.append(f"Siècle de construction : {monument['siecle_construction']}")
    if monument.get("reference_merimee"):
        lines.append(f"Référence Mérimée : {monument['reference_merimee']}")
    return "\n".join(lines)


async def _llm_evaluate_eligibility(
    prompt: str,
    aide_nom: str,
) -> dict:
    """Call Mistral to evaluate fine eligibility with a rendered prompt.

    Returns {"explication_globale": str, "evaluations": list[dict]}.
    On error/missing key, returns empty evaluations — callers treat that as
    "no LLM input" and keep the aide eligible without QCM questions.
    """
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        logger.warning("[LLM] MISTRAL_API_KEY absent — évaluation ignorée")
        return {
            "explication_globale": "Évaluation LLM indisponible",
            "evaluations": [],
        }

    client = Mistral(api_key=api_key)

    logger.info("[LLM] Appel Mistral pour « %s »...", aide_nom)
    last_error = None
    for attempt in range(3):
        try:
            response = await client.chat.complete_async(
                model="mistral-medium-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )
            choice = response.choices[0]
            content = choice.message.content
            result = json.loads(content)
            return result
        except Exception as e:
            last_error = e
            if attempt < 2:
                wait = 2**attempt
                logger.warning(
                    "[LLM] Tentative %d/3 échouée pour « %s » (%s), retry dans %ds",
                    attempt + 1,
                    aide_nom,
                    e,
                    wait,
                )
                await asyncio.sleep(wait)
    logger.error(f"LLM evaluation failed for aide '{aide_nom}' after 3 attempts: {last_error}")
    return {
        "explication_globale": f"Erreur LLM : {last_error}",
        "evaluations": [],
    }


def _llm_log(aide_nom: str, evaluations: list[dict], explication_globale: str) -> None:
    """Log per-bullet evaluations via the application logger."""
    has_non = any(e.get("verdict") == "non" for e in evaluations)
    n_incertitudes = sum(1 for e in evaluations if e.get("verdict") == "incertitude")
    icon = "✗" if has_non else ("?" if n_incertitudes else "✓")

    logger.info(
        "%s %s | %d critère(s) | incertitudes=%d",
        icon,
        aide_nom,
        len(evaluations),
        n_incertitudes,
    )
    logger.info("   synthèse : %s", explication_globale)
    for i, e in enumerate(evaluations, 1):
        verdict = e.get("verdict", "?")
        logger.info("   %d. [%s] %s", i, verdict, e.get("critere", "")[:80])


def _parse_bullets(text: str) -> list[str]:
    """Split a conditions_eligibilite_detail string into a list of bullets.

    Supports two formats:
    - New: each bullet is a paragraph prefixed with '>' (markdown quote style).
    - Legacy: lines prefixed with '-'.
    Falls back to blank-line-separated paragraphs, then to a single bullet.
    """
    if not text or not text.strip():
        return []

    lines = text.split("\n")

    # New format: '>'-prefixed bullets. Consecutive '>' lines (or a single
    # blank line between two '>' blocks) merge into one bullet.
    if any(line.lstrip().startswith(">") for line in lines):
        bullets: list[str] = []
        current: list[str] = []
        for raw in lines:
            stripped = raw.lstrip()
            if stripped.startswith(">"):
                current.append(stripped[1:].strip())
            else:
                if current:
                    merged = " ".join(p for p in current if p)
                    if merged:
                        bullets.append(merged)
                    current = []
        if current:
            merged = " ".join(p for p in current if p)
            if merged:
                bullets.append(merged)
        return bullets

    # Legacy format: '-'-prefixed lines (each line is its own bullet).
    if any(line.lstrip().startswith("-") for line in lines):
        return [line.lstrip()[1:].strip() for line in lines if line.lstrip().startswith("-")]

    # Fallback: split on blank lines.
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        return paragraphs

    return [text.strip()]


def _normalize_evaluations(raw: list, bullets: list[str]) -> list[dict]:
    """Align LLM evaluations to the source bullets and coerce invalid values.

    Fail-closed policy: any bullet for which we can't extract a valid verdict
    (LLM returned nothing, returned an unknown value, or returned malformed
    output) becomes an `incertitude` with categorie='autre'. Defaulting to
    'oui' on missing/malformed output would silently mark aides as eligible
    based on LLM bugs — surfacing them as QCM questions lets the user (or
    an audit) catch the issue downstream.

    - Drops extras the LLM hallucinated beyond the bullet count.
    - Coerces unknown categories to 'autre' with a warning.
    - The 'critere' field is taken from the input bullet (verbatim), never
      from the LLM response — we never trust the LLM to re-quote correctly.
    """
    out: list[dict] = []
    raw_list = list(raw) if isinstance(raw, list) else []

    for i, bullet in enumerate(bullets):
        has_eval = i < len(raw_list) and isinstance(raw_list[i], dict)
        raw_eval = raw_list[i] if has_eval else {}

        verdict = str(raw_eval.get("verdict") or "").strip().lower()
        if verdict not in {"oui", "non", "incertitude"}:
            if not has_eval:
                logger.warning(
                    "[LLM] Évaluation manquante pour le critère #%d — fail-closed en « incertitude »",
                    i + 1,
                )
            else:
                logger.warning(
                    "[LLM] Verdict invalide « %s » sur le critère #%d — fail-closed en « incertitude »",
                    verdict or "(vide)",
                    i + 1,
                )
            verdict = "incertitude"

        explication = str(raw_eval.get("explication") or "").strip()

        evaluation: dict = {
            "critere": bullet,
            "verdict": verdict,
            "explication": explication,
        }

        if verdict == "incertitude":
            cat = str(raw_eval.get("categorie") or "").strip().lower()
            if cat not in ALLOWED_INCERTITUDE_CATEGORIES:
                if cat:
                    logger.warning("[LLM] Catégorie inconnue « %s » remappée en « autre »", cat)
                cat = "autre"
            evaluation["categorie"] = cat
            # When the LLM provided no usable explication (fail-closed branch),
            # the bullet text is the best fallback for the QCM step to anchor on.
            evaluation["detail"] = explication or bullet
            evaluation["clarified"] = False

        out.append(evaluation)

    if len(raw_list) > len(bullets):
        logger.warning(
            "[LLM] %d évaluation(s) hallucinée(s) au-delà de %d critère(s) — droppées",
            len(raw_list) - len(bullets),
            len(bullets),
        )

    return out


async def _run_llm_phase(
    eligible_results: list[dict],
    monument_profile: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Run per-bullet LLM evaluation on eligible aides with conditions detail.

    Returns (still_eligible, potentially_eligible, downgraded):
    - still_eligible: all verdicts 'oui' (no QCM needed)
    - potentially_eligible: at least one 'incertitude' verdict (feeds QCM)
    - downgraded: at least one 'non' verdict (aide is refused)
    """
    still_eligible: list[dict] = []
    potentially_eligible: list[dict] = []
    downgraded: list[dict] = []

    # Pre-parse bullets so we can skip the LLM for aides with no parseable content.
    to_evaluate: list[tuple[dict, list[str]]] = []
    for result in eligible_results:
        conditions = result["aide"].get("conditions_eligibilite_detail")
        bullets = _parse_bullets(conditions) if conditions else []
        if bullets:
            to_evaluate.append((result, bullets))
        else:
            still_eligible.append(result)

    if not to_evaluate:
        return still_eligible, potentially_eligible, downgraded

    llm_results = await asyncio.gather(
        *(
            _llm_evaluate_eligibility(
                prompt=render_prompt_eligibility(
                    monument_profile=monument_profile,
                    aide_nom=result["aide"].get("nom", ""),
                    bullets=bullets,
                ),
                aide_nom=result["aide"].get("nom", ""),
            )
            for result, bullets in to_evaluate
        )
    )

    for (result, bullets), llm_result in zip(to_evaluate, llm_results, strict=True):
        aide = result["aide"]
        explication_globale = str(llm_result.get("explication_globale") or "").strip()

        evaluations = _normalize_evaluations(llm_result.get("evaluations") or [], bullets)
        _llm_log(aide.get("nom", ""), evaluations, explication_globale)

        # Derive incertitudes as a filtered view of the SAME dict refs.
        # Mutations done by _auto_clarify_incertitudes (clarified=True) propagate
        # to the evaluations array, which is what the frontend renders.
        incertitudes = [e for e in evaluations if e["verdict"] == "incertitude"]

        result["llmEvaluation"] = {
            "explication": explication_globale,
            "evaluations": evaluations,
            "incertitudes": incertitudes,
        }

        has_non = any(e["verdict"] == "non" for e in evaluations)
        if has_non:
            first_non = next(e for e in evaluations if e["verdict"] == "non")
            raison = first_non["explication"] or first_non["critere"]
            result["eligible"] = False
            result["criteresNonRemplis"].append(f"Critère détaillé : {raison}")
            result["raisonIneligibilite"] = result["raisonIneligibilite"] or raison
            downgraded.append(result)
        elif incertitudes:
            potentially_eligible.append(result)
        else:
            still_eligible.append(result)

    return still_eligible, potentially_eligible, downgraded


# ---------------------------------------------------------------------------
# Phase 4: Generate QCM questions from incertitudes
# ---------------------------------------------------------------------------

MAX_QCM_QUESTIONS = 50


def _normalize_incertitude(inc: str | dict) -> dict:
    """Normalise an incertitude to {categorie, detail, [critere]} format.

    - Legacy plain-string → wrapped under "autre".
    - Dict with unknown category → coerced to "autre" (logs a warning).
    - `critere` (verbatim source bullet, from the new per-bullet evaluations
      schema) is preserved when present — the QCM generator feeds on it.
    """
    if isinstance(inc, dict) and "categorie" in inc:
        cat = str(inc.get("categorie") or "").strip().lower()
        if cat not in ALLOWED_INCERTITUDE_CATEGORIES:
            logger.warning("[LLM] Catégorie inconnue « %s » remappée vers « autre »", cat)
            cat = "autre"
        out = {"categorie": cat, "detail": inc.get("detail", "")}
        if inc.get("critere"):
            out["critere"] = inc["critere"]
        return out
    # Legacy plain-string fallback
    text = inc if isinstance(inc, str) else str(inc)
    return {"categorie": "autre", "detail": text}


def _aggregate_incertitudes(eligible_results: list[dict]) -> list[dict]:
    """Aggregate incertitudes by category across all aides.

    For each category, collect deduplicated "sources" : one entry per unique
    (critere, detail) pair, with the list of aide names sharing it. The QCM
    generator anchors its questions on `critere` (the verbatim bullet text
    from the aide's eligibility conditions), which is the source of truth —
    `detail` is the eligibility LLM's paraphrase and may be vague.
    """
    from collections import defaultdict

    # category → {aideIds: set, sources_by_key: {(critere, detail): {aide_noms: set, aide_ids: set}}}
    def _new_source() -> dict:
        return {"aide_noms": set(), "aide_ids": set()}

    groups: dict[str, dict] = defaultdict(
        lambda: {"aideIds": set(), "sources_by_key": defaultdict(_new_source)}
    )

    for result in eligible_results:
        llm_eval = result.get("llmEvaluation")
        if not llm_eval:
            continue
        aide_id = result["aide"]["id"]
        aide_nom = result["aide"].get("nom_court") or result["aide"].get("nom", "")
        for inc in llm_eval.get("incertitudes", []):
            normalized = _normalize_incertitude(inc)
            cat = normalized["categorie"]
            detail = normalized.get("detail", "") or ""
            critere = normalized.get("critere", "") or ""

            groups[cat]["aideIds"].add(aide_id)
            key = (critere, detail)
            src = groups[cat]["sources_by_key"][key]
            src["aide_noms"].add(aide_nom)
            src["aide_ids"].add(aide_id)

    # Sort categories by nb of aides impacted (most first).
    # Per category, keep the 3 most-impactful unique sources to bound payload size.
    aggregated = []
    for cat, data in sorted(groups.items(), key=lambda x: len(x[1]["aideIds"]), reverse=True):
        sources_sorted = sorted(
            data["sources_by_key"].items(),
            key=lambda item: len(item[1]["aide_ids"]),
            reverse=True,
        )[:3]
        sources = [
            {
                # critere is the verbatim source of truth — cap large but generously.
                "critere": (critere or "")[:1000],
                # detail is the LLM paraphrase, kept short.
                "detail": (detail or "")[:200],
                # List a handful of impacted aides so the LLM has context.
                "aides": sorted(src["aide_noms"])[:5],
            }
            for (critere, detail), src in sources_sorted
        ]
        aggregated.append(
            {
                "categorie": cat,
                "aideIds": sorted(data["aideIds"]),
                "nbAides": len(data["aideIds"]),
                "sources": sources,
            }
        )

    return aggregated


def _compact_for_llm(aggregated: list[dict]) -> list[dict]:
    """Strip aideIds before sending to LLM — we remap them back post-response via categorie."""
    return [
        {"categorie": g["categorie"], "nbAides": g["nbAides"], "sources": g["sources"]}
        for g in aggregated
    ]


def _auto_clarify_incertitudes(
    eligible_results: list[dict],
    categories_to_clarify: set[str],
) -> int:
    """Mark every incertitude whose category is in the set as clarified=True.

    Used after QCM generation to close the categories the LLM either explicitly
    skipped (deemed redundant with profile) or silently forgot. Without this,
    any uncovered category leaves its incertitudes pending forever and the aide
    is stuck in potentiellement_eligible regardless of the QCM answers.
    """
    if not categories_to_clarify:
        return 0
    n = 0
    for result in eligible_results:
        llm_eval = result.get("llmEvaluation") or {}
        for inc in llm_eval.get("incertitudes", []):
            if (
                isinstance(inc, dict)
                and inc.get("categorie") in categories_to_clarify
                and not inc.get("clarified")
            ):
                inc["clarified"] = True
                n += 1
    return n


def _all_incertitudes_clarified(result: dict) -> bool:
    llm_eval = result.get("llmEvaluation") or {}
    incertitudes = llm_eval.get("incertitudes") or []
    if not incertitudes:
        return True
    for inc in incertitudes:
        if isinstance(inc, str):
            return False
        if not inc.get("clarified"):
            return False
    return True


async def generate_qcm_questions(
    eligible_results: list[dict],
    monument_profile: str = "",
) -> list[dict]:
    """Collect incertitudes from eligible aides, aggregate by category, and generate QCM."""
    aggregated = _aggregate_incertitudes(eligible_results)

    if not aggregated:
        return []

    total_raw = sum(
        len(inc)
        for r in eligible_results
        if (e := r.get("llmEvaluation"))
        for inc in [e.get("incertitudes", [])]
    )

    logger.info("─" * 60)
    logger.info(
        "PHASE 4 — Génération QCM (%d incertitude(s) brutes → %d catégorie(s) agrégée(s))",
        total_raw,
        len(aggregated),
    )
    for g in aggregated:
        first_source = g["sources"][0] if g.get("sources") else {}
        preview = first_source.get("critere") or first_source.get("detail") or ""
        logger.info("  • %s — %d aide(s) : %s", g["categorie"], g["nbAides"], preview[:80])
    logger.info("─" * 60)

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        logger.warning("MISTRAL_API_KEY not set, skipping QCM generation")
        return []

    client = Mistral(api_key=api_key)

    # Build a compact payload (no aideIds) for the LLM — we remap them from categorie after.
    compact_payload = _compact_for_llm(aggregated)
    aide_ids_by_category = {g["categorie"]: g["aideIds"] for g in aggregated}

    prompt = render_prompt_qcm(
        max_questions=MAX_QCM_QUESTIONS,
        monument_profile=monument_profile,
        incertitudes_json=json.dumps(compact_payload, ensure_ascii=False, indent=2),
    )
    logger.info("[QCM] Prompt construit (%d caractères), appel Mistral...", len(prompt))

    QCM_TIMEOUT_S = 90
    last_error = None
    for attempt in range(3):
        try:
            logger.info("[QCM] Tentative %d/3 (timeout %ds)...", attempt + 1, QCM_TIMEOUT_S)
            response = await asyncio.wait_for(
                client.chat.complete_async(
                    model="mistral-large-latest",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0,
                ),
                timeout=QCM_TIMEOUT_S,
            )
            content = response.choices[0].message.content
            logger.info("[QCM] Réponse reçue (%d caractères)", len(content or ""))
            parsed = json.loads(content)
            raw_questions = parsed.get("questions", [])
            raw_skipped = parsed.get("categoriesSkippees", [])

            input_categories = set(aide_ids_by_category.keys())

            # Validate, remap aideIds, and sanitize in a single pass.
            questions = []
            for q in raw_questions:
                if not isinstance(q, dict):
                    continue
                cat = q.get("categorie")
                mapped_ids = aide_ids_by_category.get(cat)
                if not mapped_ids:
                    logger.warning(
                        "[QCM] Question ignorée: catégorie « %s » inconnue ou sans aides", cat
                    )
                    continue
                qid = q.get("id")
                qtext = q.get("question")
                options = q.get("options")
                if not (qid and qtext and isinstance(options, list)):
                    logger.warning("[QCM] Question malformée ignorée: %s", q)
                    continue
                q["aideIds"] = mapped_ids
                q.setdefault("eliminatingOptionIds", [])
                if "eliminationsParOption" in q and not isinstance(
                    q["eliminationsParOption"], dict
                ):
                    q["eliminationsParOption"] = {}
                questions.append(q)

            covered = {q.get("categorie") for q in questions}

            # Categories the LLM explicitly chose to skip, with a stated reason.
            claimed_skipped: set[str] = set()
            for entry in raw_skipped:
                if not isinstance(entry, dict):
                    continue
                cat = entry.get("categorie")
                raison = entry.get("raison", "")
                if cat in input_categories:
                    claimed_skipped.add(cat)
                    logger.info("[QCM] Catégorie « %s » skippée volontairement : %s", cat, raison)
                else:
                    logger.warning(
                        "[QCM] Catégorie skippée « %s » absente du payload — ignorée", cat
                    )

            # Categories the LLM silently dropped (neither asked nor explicitly skipped).
            # These would otherwise leave incertitudes pending forever.
            silently_missed = input_categories - covered - claimed_skipped
            for cat in silently_missed:
                logger.warning(
                    "[QCM] Catégorie « %s » oubliée par le LLM (auto-clarification serveur)",
                    cat,
                )

            auto_clarified_categories = claimed_skipped | silently_missed
            n_marked = _auto_clarify_incertitudes(eligible_results, auto_clarified_categories)

            logger.info(
                "→ %d question(s) QCM (brut: %d) — skip explicite: %d, oublis: %d, auto-clarifiées: %d incertitude(s)",
                len(questions),
                len(raw_questions),
                len(claimed_skipped),
                len(silently_missed),
                n_marked,
            )
            for q in questions:
                logger.info(
                    "  ? [%s] %s (%d aide(s))",
                    q.get("categorie", "?"),
                    (q.get("question") or "")[:80],
                    len(q.get("aideIds", [])),
                )

            return questions
        except TimeoutError as e:
            last_error = e
            logger.warning("[QCM] Tentative %d/3 timeout après %ds", attempt + 1, QCM_TIMEOUT_S)
            if attempt < 2:
                await asyncio.sleep(2**attempt)
        except Exception as e:
            last_error = e
            if attempt < 2:
                wait = 2**attempt
                logger.warning(
                    "[QCM] Tentative %d/3 échouée (%s), retry dans %ds", attempt + 1, e, wait
                )
                await asyncio.sleep(wait)
    logger.error(f"QCM generation failed after 3 attempts: {last_error}")
    return []


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_diagnostic(
    supabase: Client,
    monument: dict,
    user: dict,
    mode_projet: bool = False,
    travaux_filtres: list[str] | None = None,
) -> dict:
    """Run a full diagnostic: SQL pre-filter → criteria check → LLM fine-matching."""
    ctx_travaux = travaux_filtres or []

    logger.info(
        "DIAGNOSTIC %s | protection=%s proprietaire=%s region=%s dept=%s travaux=[%s] mode_projet=%s",
        monument.get("nom", "?"),
        monument.get("protection"),
        monument.get("proprietaire"),
        monument.get("region"),
        monument.get("departement_num"),
        ",".join(ctx_travaux or monument.get("travaux_envisages") or []) or "—",
        mode_projet,
    )

    # Phase 1: SQL pre-filter
    candidate_ids = prefiltrer_aides(supabase, monument, user, ctx_travaux or None)
    all_aide_ids = [a["id"] for a in (supabase.table("aides_v2").select("id").execute()).data or []]
    non_candidate_ids = [aid for aid in all_aide_ids if aid not in candidate_ids]
    logger.info(
        "PHASE 1 — pré-filtre SQL : %d candidate(s) / %d exclue(s) sur %d",
        len(candidate_ids),
        len(non_candidate_ids),
        len(all_aide_ids),
    )

    candidate_aides = fetch_aides_with_joins(supabase, candidate_ids)
    non_candidate_aides = fetch_aides_with_joins(supabase, non_candidate_ids)

    population = _resolve_population(supabase, monument.get("code_insee"), user)

    # Candidates from SQL are eligible — just build labels for display
    eligible_results = [
        _build_criteria_labels(a, monument, user, mode_projet, ctx_travaux, population)
        for a in candidate_aides
    ]
    for r in eligible_results:
        r["eligible"] = True

    # Non-candidates are ineligible — build labels to show why
    non_eligible_results = [
        _build_criteria_labels(a, monument, user, mode_projet, ctx_travaux, population)
        for a in non_candidate_aides
    ]
    for r in non_eligible_results:
        r["eligible"] = False

    logger.info("PHASE 2 — évaluation LLM sur %d aide(s)", len(eligible_results))
    monument_profile = _build_monument_profile(monument, population)

    still_eligible, potentially_eligible, downgraded = await _run_llm_phase(
        eligible_results, monument_profile
    )
    non_eligible_results.extend(downgraded)

    for r in still_eligible:
        logger.info("  ✓ %s", r["aide"].get("nom_court") or r["aide"].get("nom"))
    for r in potentially_eligible:
        logger.info("  ? %s", r["aide"].get("nom_court") or r["aide"].get("nom"))
    for r in downgraded:
        logger.info("  ✗ %s", r["aide"].get("nom_court") or r["aide"].get("nom"))

    # Phase 4: Generate QCM questions from incertitudes (mutates llmEvaluation
    # in place: incertitudes covered by neither a question nor an explicit skip
    # get marked clarified=true server-side).
    qcm_questions = []
    all_with_incertitudes = still_eligible + potentially_eligible
    if all_with_incertitudes:
        qcm_questions = await generate_qcm_questions(all_with_incertitudes, monument_profile)

    # Re-bucket after auto-clarification: promote any potentiellement_éligible
    # whose incertitudes are now all clarified to still_eligible.
    promoted = [r for r in potentially_eligible if _all_incertitudes_clarified(r)]
    if promoted:
        promoted_ids = {r["aide"]["id"] for r in promoted}
        still_eligible.extend(promoted)
        potentially_eligible = [
            r for r in potentially_eligible if r["aide"]["id"] not in promoted_ids
        ]
        logger.info("→ %d aide(s) promue(s) via auto-clarification", len(promoted))

    montant_total = sum(
        r["aide"].get("montant_max") or 0 for r in still_eligible if r["aide"].get("montant_max")
    )

    logger.info(
        "RÉSULTAT %s | éligibles=%d potentiels=%d non=%d montant=%s",
        monument.get("nom", "?"),
        len(still_eligible),
        len(potentially_eligible),
        len(non_eligible_results),
        f"{montant_total:,} €" if montant_total else "—",
    )

    return {
        "monumentId": monument["id"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "totalAidesAnalysees": len(all_aide_ids),
        "aidesEligibles": still_eligible,
        "aidesPotentiellementEligibles": potentially_eligible,
        "aidesNonEligibles": non_eligible_results,
        "montantPotentielTotal": montant_total if montant_total > 0 else None,
        "qcmQuestions": qcm_questions,
    }
