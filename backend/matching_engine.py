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
import re
from datetime import datetime

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
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


# Concurrency cap for outbound LLM calls. We routinely fan out one call
# per candidate aide (often 30–80 aides), and two simultaneous diagnostics
# would double that. The semaphore is process-wide and shared between the
# eligibility (Phase 3) calls — the QCM call is a single request and not
# affected. 8 was picked as a compromise: high enough to keep p95 latency
# from blowing up, low enough to stay well below the provider's tier rate
# limit and to avoid 429s under burst.
def _env_int(name: str, default: int) -> int:
    """Read an int env var, falling back to `default` if unset or non-numeric.

    Avoids a hard crash at import time when the operator typos the value
    (e.g. LLM_MAX_CONCURRENCY=abc) — we log and keep the default instead.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("[CONFIG] %s=%r non numérique — valeur par défaut %d", name, raw, default)
        return default


_LLM_MAX_CONCURRENCY = _env_int("LLM_MAX_CONCURRENCY", 8)
_llm_semaphore: asyncio.Semaphore | None = None
_llm_client: AsyncOpenAI | None = None

# Model routing (DeepSeek V4, called via its OpenAI-compatible API).
#   - Eligibility is a high-volume fan-out (one call per candidate aide), so it
#     uses a NON-reasoning model: reasoning tokens × 30–80 calls would blow up
#     latency and output cost for little gain on a grounded classification task.
#   - QCM is a single call doing hard combinatorial reasoning
#     (eliminationsParOption / MECE / monotonie), so it uses the reasoning model.
# All three are env-overridable: point DEEPSEEK_BASE_URL at any OpenAI-compatible
# host (an EU / zero-retention provider, OpenRouter, Together…) and pin specific
# model ids without touching code. Defaults follow DeepSeek's official API
# aliases (`deepseek-chat` = non-reasoning, `deepseek-reasoner` = reasoning).
_DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
_MODEL_ELIGIBILITY = os.environ.get("DEEPSEEK_MODEL_ELIGIBILITY", "deepseek-chat")
_MODEL_QCM = os.environ.get("DEEPSEEK_MODEL_QCM", "deepseek-reasoner")


def _get_llm_semaphore() -> asyncio.Semaphore:
    """Lazy semaphore creation bound to the active event loop."""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(_LLM_MAX_CONCURRENCY)
    return _llm_semaphore


def _get_llm_client(api_key: str) -> AsyncOpenAI:
    """Return a process-wide OpenAI-compatible client (DeepSeek), created on first use.

    The client is cheap to reuse but not free to build — fanning out one
    eligibility call per candidate aide (30–80 in a gather) would otherwise
    spin up that many short-lived clients per diagnostic.

    `base_url` defaults to DeepSeek's official API but is env-overridable so the
    same code can target any OpenAI-compatible host. `max_retries=0` because this
    module implements its own retry/backoff loop below — letting the SDK retry
    on top would compound the waits and blur the permanent/transient distinction.
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(api_key=api_key, base_url=_DEEPSEEK_BASE_URL, max_retries=0)
    return _llm_client


# Per-call timeout for the eligibility (Phase 3) LLM call. Without it, a hung
# TCP connection would block the aide for the full retry/backoff window and
# stall the whole diagnostic — Phase 4 already has this guard, Phase 3 didn't.
_ELIGIBILITY_TIMEOUT_S = 60


def _is_permanent_llm_error(exc: Exception) -> bool:
    """True if an API status error indicates a non-retriable condition.

    Retriable: 429 (rate-limited) and 5xx (server-side hiccup).
    Permanent: 4xx other than 429 — authentication (401/403), malformed
    request (400), not-found (404), payload too large (413), etc. Retrying
    these just wastes 6+ seconds of backoff before failing the same way.
    """
    if not isinstance(exc, APIStatusError):
        return False
    status = exc.status_code
    if not isinstance(status, int):
        return False
    return 400 <= status < 500 and status != 429


def _is_transient_network_error(exc: Exception) -> bool:
    """True if the error looks like a transient I/O failure worth retrying."""
    return isinstance(
        exc,
        (
            TimeoutError,
            asyncio.TimeoutError,
            APIConnectionError,  # openai SDK: connection reset / DNS / refused
            APITimeoutError,  # openai SDK: request timed out (subclass of the above)
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.RemoteProtocolError,
            ConnectionError,
        ),
    )


def _label(mapping: dict, value: str | None) -> str:
    if value is None:
        return ""
    return mapping.get(value, value)


def _labels(mapping: dict, values: list) -> str:
    return ", ".join(_label(mapping, v) for v in values)


def _resolve_population(supabase: Client, code_insee: str | None) -> int | None:
    """Return the commune's population if we know its INSEE code.

    Resolved unconditionally — the SQL pre-filter applies `commune_max_population`
    to any aide that sets it, regardless of the requesting user's segment. A
    propriétaire privé in a 200k-hab commune must still be excluded from a
    "communes ≤ 5000 hab." aide.
    """
    if not code_insee:
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
) -> tuple[list[str], int | None]:
    """Call the prefiltrer_aides SQL function.

    Returns `(matching aide UUIDs, resolved commune population)`. The population
    is resolved here (against the fallback-resolved `code_insee`) and handed back
    so the caller can reuse it for labels/profile without a second lookup.
    """
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

    population = _resolve_population(supabase, code_insee)

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

    return [row["aide_id"] for row in (result.data or [])], population


# ---------------------------------------------------------------------------
# Phase 2: Build human-readable criteria labels (display only, no re-filtering)
# ---------------------------------------------------------------------------


# Criteria arrays live directly on aides_v2 since the join tables were folded in.
# Kept as a constant so callers can still iterate (e.g. to zero-out missing keys).
_CRITERIA_ARRAY_KEYS = (
    "protections",
    "proprietaires",
    "travaux",
    "regions",
    "departements",
    "etats_conservation",
)


def fetch_aides_with_joins(supabase: Client, aide_ids: list[str]) -> list[dict]:
    """Fetch aides by id. Criteria arrays are columns on aides_v2 — no extra joins."""
    if not aide_ids:
        return []

    aides_result = supabase.table("aides_v2").select("*").in_("id", aide_ids).execute()
    aides = aides_result.data or []

    # Guarantee list-typed keys even on rows where the array column came back null.
    for aide in aides:
        for key in _CRITERIA_ARRAY_KEYS:
            if aide.get(key) is None:
                aide[key] = []

    return aides


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
        (
            "protections",
            "protection",
            PROTECTION_LABELS,
            "Protection",
            "Protection requise",
            "Tous niveaux de protection",
        ),
        (
            "proprietaires",
            "proprietaire",
            OWNERSHIP_LABELS,
            "Type de propriétaire",
            "Propriétaire éligible",
            "Tous types de propriétaires",
        ),
        ("regions", "region", REGION_LABELS, "Région", "Région requise", "Toute la France"),
        (
            "etats_conservation",
            "etat_conservation",
            ETAT_LABELS,
            "État de conservation",
            "État requis",
            None,
        ),
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
    # Applied regardless of user.segment — the SQL filter does the same.
    max_pop = aide.get("commune_max_population")
    if max_pop is not None and population:
        if population <= max_pop:
            criteres_remplis.append(f"Commune ≤ {max_pop:,} hab. ({population} hab.)")
        else:
            criteres_non_remplis.append(f"Réservé aux communes ≤ {max_pop:,} hab.")

    # `eligible` is intentionally NOT set here — it is the SQL pre-filter's job
    # to decide. The caller (run_diagnostic) overrides this field based on
    # whether the aide came back from prefiltrer_aides(). Computing it here
    # would create two sources of truth that can silently diverge.
    # `raisonIneligibilite` is offered as a display hint for non-candidates;
    # the caller decides whether to surface it (it's meaningless for an aide
    # the SQL filter accepted).
    return {
        "aide": aide,
        "criteresRemplis": criteres_remplis,
        "criteresNonRemplis": criteres_non_remplis,
        "raisonIneligibilite": criteres_non_remplis[0] if criteres_non_remplis else None,
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
    # Référence Mérimée volontairement omise du profil envoyé au LLM : elle
    # n'apporte rien au raisonnement d'éligibilité (qui s'appuie sur protection,
    # type de propriétaire, localisation, travaux, état) et c'est un identifiant
    # pointant vers une fiche publique nominative — inutile de l'exposer au
    # fournisseur LLM.
    return "\n".join(lines)


async def _llm_evaluate_eligibility(
    prompt: str,
    aide_nom: str,
) -> dict:
    """Call the LLM to evaluate fine eligibility with a rendered prompt.

    Returns {"explication_globale": str, "evaluations": list[dict]}.
    On error/missing key, returns empty evaluations — callers treat that as
    "no LLM input" and keep the aide eligible without QCM questions.

    Error handling:
      - Per-call timeout (_ELIGIBILITY_TIMEOUT_S) so a hung connection doesn't
        block the whole diagnostic.
      - Transient errors (5xx, 429, timeout, connection reset) → retried with
        exponential backoff up to 3 attempts.
      - Permanent errors (4xx other than 429: bad key, malformed prompt) →
        failed fast on attempt 1; retrying wastes time and pollutes logs.
      - JSON decode errors → one repair attempt that re-injects the broken
        output and asks the model to return valid JSON. If repair fails,
        give up (further attempts converge on the same broken output).
      - Outbound concurrency is bounded by `_llm_semaphore` to avoid 429s
        when a diagnostic fans out across dozens of aides.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        logger.warning("[LLM] DEEPSEEK_API_KEY absent — évaluation ignorée")
        return {
            "explication_globale": "Évaluation LLM indisponible",
            "evaluations": [],
        }

    client = _get_llm_client(api_key)
    semaphore = _get_llm_semaphore()

    async def _call(repair_with: str | None = None) -> str:
        """One round-trip to the LLM; if `repair_with` is set, ask for a JSON fix."""
        messages: list[dict] = [{"role": "user", "content": prompt}]
        if repair_with is not None:
            messages.append({"role": "assistant", "content": repair_with})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Ta réponse précédente n'est pas un JSON valide. "
                        "Renvoie exactement la même évaluation, mais en JSON strict, "
                        "sans aucun texte hors du bloc JSON."
                    ),
                }
            )
        async with semaphore:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=_MODEL_ELIGIBILITY,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0,
                ),
                timeout=_ELIGIBILITY_TIMEOUT_S,
            )
        return response.choices[0].message.content

    logger.info("[LLM] Appel LLM pour « %s »...", aide_nom)
    last_error: Exception | None = None
    broken_content: str | None = None
    json_repair_used = False
    content: str | None = None

    for attempt in range(3):
        try:
            content = await _call(repair_with=broken_content if json_repair_used else None)
            return json.loads(content)

        except json.JSONDecodeError as e:
            last_error = e
            if not json_repair_used:
                json_repair_used = True
                broken_content = content
                logger.warning(
                    "[LLM] JSON invalide pour « %s » — tentative de réparation",
                    aide_nom,
                )
                continue  # immediate repair retry, no backoff
            logger.error(
                "[LLM] JSON invalide même après réparation pour « %s » — abandon",
                aide_nom,
            )
            break

        except APIStatusError as e:
            last_error = e
            if _is_permanent_llm_error(e):
                logger.error(
                    "[LLM] Erreur permanente LLM pour « %s » (HTTP %s) — pas de retry",
                    aide_nom,
                    e.status_code,
                )
                break
            if attempt < 2:
                wait = 2**attempt
                logger.warning(
                    "[LLM] Tentative %d/3 échouée pour « %s » (HTTP %s), retry dans %ds",
                    attempt + 1,
                    aide_nom,
                    getattr(e, "status_code", "?"),
                    wait,
                )
                await asyncio.sleep(wait)

        except Exception as e:
            last_error = e
            if not _is_transient_network_error(e):
                # Unknown error class — log loudly and stop retrying. Better to
                # surface an LLM-down banner than to mask a programmer bug
                # (e.g. AttributeError) behind 3× backoff.
                logger.error(
                    "[LLM] Erreur non-transitoire pour « %s » (%s: %s) — pas de retry",
                    aide_nom,
                    type(e).__name__,
                    e,
                )
                break
            if attempt < 2:
                wait = 2**attempt
                logger.warning(
                    "[LLM] Tentative %d/3 réseau pour « %s » (%s), retry dans %ds",
                    attempt + 1,
                    aide_nom,
                    e,
                    wait,
                )
                await asyncio.sleep(wait)

    logger.error("LLM evaluation failed for aide '%s': %s", aide_nom, last_error)
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


def _is_blockquote_line(line: str) -> bool:
    """True if `line` is a markdown blockquote marker (>) and not inline text.

    Matches `>` followed by whitespace or end-of-line — the markdown convention.
    Rejects inline uses like "Surface > 50 m²" which would otherwise be mistaken
    for a bullet and silently shift every downstream alignment.
    """
    stripped = line.lstrip()
    if not stripped.startswith(">"):
        return False
    rest = stripped[1:]
    return rest == "" or rest[0] in (" ", "\t")


def _is_dash_bullet_line(line: str) -> bool:
    """True if `line` starts with `- ` (or just `-` alone)."""
    stripped = line.lstrip()
    if not stripped.startswith("-"):
        return False
    rest = stripped[1:]
    return rest == "" or rest[0] in (" ", "\t")


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
    if any(_is_blockquote_line(line) for line in lines):
        bullets: list[str] = []
        current: list[str] = []
        for raw in lines:
            if _is_blockquote_line(raw):
                stripped = raw.lstrip()
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
    if any(_is_dash_bullet_line(line) for line in lines):
        return [line.lstrip()[1:].strip() for line in lines if _is_dash_bullet_line(line)]

    # Fallback: split on blank lines.
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        return paragraphs

    return [text.strip()]


def _index_evaluations_by_bullet(raw_list: list) -> dict[int, dict]:
    """Build a {bullet_index → eval dict} map from the LLM's raw output.

    Aligning by an explicit 1-based `bullet_index` (rather than by position in
    the array) is the only way to detect silent omissions: if the LLM skips
    bullet #3 and only emits N-1 evaluations, positional zip() would attribute
    eval #4's verdict to bullet #3 and shift everything downstream. With an
    explicit index, the missing bullet falls through to the fail-closed
    `incertitude` branch.

    - Invalid / non-integer indices are ignored.
    - Out-of-range indices are ignored (logged).
    - Duplicate indices: the first wins (logged).
    """
    by_index: dict[int, dict] = {}
    for raw_eval in raw_list:
        if not isinstance(raw_eval, dict):
            continue
        idx = raw_eval.get("bullet_index")
        if not isinstance(idx, int) or idx < 1:
            continue
        if idx in by_index:
            logger.warning("[LLM] bullet_index %d en doublon — première occurrence conservée", idx)
            continue
        by_index[idx] = raw_eval
    return by_index


def _normalize_evaluations(raw: list, bullets: list[str]) -> list[dict]:
    """Align LLM evaluations to the source bullets and coerce invalid values.

    Alignment strategy:
      1. Primary: use `bullet_index` (1-based) when the LLM emits it — robust
         to omissions, reorderings, and partial responses.
      2. Fallback: if NONE of the LLM evaluations carry a usable bullet_index
         (e.g. older prompt/model), fall back to positional alignment. This
         keeps the engine working through a prompt-template transition.

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

    by_index = _index_evaluations_by_bullet(raw_list)
    use_index_alignment = bool(by_index)
    if not use_index_alignment and raw_list:
        logger.warning("[LLM] Aucun bullet_index dans la réponse — fallback alignement positionnel")

    for i, bullet in enumerate(bullets):
        bullet_idx = i + 1  # 1-based
        if use_index_alignment:
            raw_eval = by_index.get(bullet_idx, {})
            has_eval = bool(raw_eval)
        else:
            has_eval = i < len(raw_list) and isinstance(raw_list[i], dict)
            raw_eval = raw_list[i] if has_eval else {}

        verdict = str(raw_eval.get("verdict") or "").strip().lower()
        if verdict not in {"oui", "non", "incertitude"}:
            if not has_eval:
                logger.warning(
                    "[LLM] Évaluation manquante pour le critère #%d — fail-closed en « incertitude »",
                    bullet_idx,
                )
            else:
                logger.warning(
                    "[LLM] Verdict invalide « %s » sur le critère #%d — fail-closed en « incertitude »",
                    verdict or "(vide)",
                    bullet_idx,
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

    # Hallucinations: indices out of range when aligning by index, or extras
    # past the bullet count when aligning positionally.
    if use_index_alignment:
        out_of_range = [idx for idx in by_index if idx > len(bullets)]
        if out_of_range:
            logger.warning(
                "[LLM] %d bullet_index hors plage [1..%d] — ignorés : %s",
                len(out_of_range),
                len(bullets),
                sorted(out_of_range),
            )
    elif len(raw_list) > len(bullets):
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

        # Derive incertitudes as a filtered view of the SAME dict refs, so that a
        # later clarified=True mutation (the clarification primitive
        # _auto_clarify_incertitudes, gated on explicit answers) stays consistent
        # with the evaluations array, which is what the frontend renders.
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

    For each category, collect deduplicated "sources": one entry per unique
    `critere` (the verbatim bullet text from the aide's eligibility conditions),
    with the list of aide names/ids sharing it. The QCM generator anchors its
    questions on `critere`, which is the source of truth — `detail` is the
    eligibility LLM's paraphrase and may be vague (qcm.j2:14-15).

    Dedup is keyed on `critere` ALONE (not the `(critere, detail)` pair): two
    aides requiring the same thing must collapse into one source even when the
    LLM paraphrased `detail` differently, otherwise each paraphrase spawns a
    distinct source, the per-category source cap is hit faster, and aides get
    silently stripped from `eliminationsParOption`. A representative `detail`
    (the most frequently observed paraphrase) is kept for display only.
    """
    from collections import defaultdict

    # category → {aideIds: set, sources_by_key: {critere: {aide_noms, aide_ids, details}}}
    def _new_source() -> dict:
        return {"aide_noms": set(), "aide_ids": set(), "details": defaultdict(int)}

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
            src = groups[cat]["sources_by_key"][critere]
            src["aide_noms"].add(aide_nom)
            src["aide_ids"].add(aide_id)
            if detail:
                src["details"][detail] += 1

    # Sort categories by nb of aides impacted (most first).
    # Per category, keep the most-impactful unique sources to bound payload size
    # while still surfacing enough distinct thresholds for the LLM to build a
    # correct eliminationsParOption mapping (cap raised from 3 to 8 because
    # under-cap source variety silently strips aides from the per-option map).
    aggregated = []
    for cat, data in sorted(groups.items(), key=lambda x: len(x[1]["aideIds"]), reverse=True):
        sources_sorted = sorted(
            data["sources_by_key"].items(),
            key=lambda item: len(item[1]["aide_ids"]),
            reverse=True,
        )[:8]
        sources = []
        for critere, src in sources_sorted:
            # Representative detail: the most frequently observed paraphrase for
            # this critere. Insertion order (Python ≥3.7 dict) breaks ties, so
            # the first-seen paraphrase wins. Display only — the LLM anchors on
            # `critere`.
            detail = max(src["details"], key=src["details"].get) if src["details"] else ""
            sources.append(
                {
                    # critere is the verbatim source of truth — cap large but generously.
                    "critere": (critere or "")[:1000],
                    # detail is the LLM paraphrase, kept short.
                    "detail": (detail or "")[:200],
                    # Sample of aide names for LLM context (display only).
                    "aides": sorted(src["aide_noms"])[:5],
                    # Full list of aide IDs sharing this critere — feeds eliminationsParOption.
                    # Required so the LLM can map each aide to the option(s) that eliminate
                    # it based on this source's threshold (instead of guessing).
                    "aideIds": sorted(src["aide_ids"]),
                }
            )
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
    """Drop the category-level aideIds before sending to the LLM.

    Only the top-level `aideIds` list is removed — we remap questions back to
    aides via `categorie` post-response, so the LLM never needs it. The
    per-source aideIds inside `sources` are kept on purpose: §3.1 relies on them
    for fine-grained, per-condition elimination (eliminationsParOption).
    """
    return [
        {"categorie": g["categorie"], "nbAides": g["nbAides"], "sources": g["sources"]}
        for g in aggregated
    ]


def _auto_clarify_incertitudes(
    eligible_results: list[dict],
    categories_to_clarify: set[str],
) -> int:
    """Mark every pending incertitude whose category is in the set as clarified.

    This is the clarification *primitive*. A category is only ever a legitimate
    input here when the user gave an explicit answer for it (FIX 1 + FIX 5): the
    conservative policy forbids clarifying categories the LLM merely skipped or
    silently forgot, because that promotes aides nobody verified and inflates
    montantPotentielTotal. At diagnostic-generation time there is no user answer
    yet, so `generate_qcm_questions` intentionally calls this with no skip/oubli
    categories; answer-driven clarification is applied later (frontend) once the
    user responds. Returns the number of incertitudes flipped.
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


def _count_incertitudes_in_categories(
    eligible_results: list[dict],
    categories: set[str],
) -> int:
    """Count pending incertitudes whose category is in the set (read-only).

    Mirror of `_auto_clarify_incertitudes` without the mutation — used to log how
    many incertitudes are *kept* potential (oubli/skip) under the conservative
    policy where only an explicit user answer clarifies.
    """
    if not categories:
        return 0
    n = 0
    for result in eligible_results:
        llm_eval = result.get("llmEvaluation") or {}
        for inc in llm_eval.get("incertitudes", []):
            if (
                isinstance(inc, dict)
                and inc.get("categorie") in categories
                and not inc.get("clarified")
            ):
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


_NUM_RE = re.compile(r"\d+")


def _option_threshold_key(option: dict) -> tuple[int, ...] | None:
    """Return an ordering key for a numeric-threshold option, else None.

    Reads the option id first (the prompt emits numeric ids like 'lt40',
    '40_59', '60_79', 'ge80'), falling back to the label. Categorical options
    and the 'skip'/'none' escape hatches contain no digits → None → left
    untouched by the monotonicity repair. The key is the tuple of integers
    found, which orders tranches the intuitive way:
    (40,) < (40, 59) < (60, 79) < (80,).
    """
    if not isinstance(option, dict):
        return None
    oid = str(option.get("id") or "")
    nums = _NUM_RE.findall(oid)
    if not nums:
        nums = _NUM_RE.findall(str(option.get("label") or ""))
    if not nums:
        return None
    return tuple(int(n) for n in nums)


def _repair_monotonic_eliminations(
    clean_elim: dict[str, list[str]],
    options: list[dict],
    categorie: str | None,
) -> dict[str, list[str]]:
    """Force nested-decreasing monotonicity on ordered-threshold questions (FIX 2).

    For a question whose options encode an ordered numeric scale ('<40', '40-59',
    '60-79', '>=80'), the eliminated-aide sets must nest:
        elim(<40) ⊇ elim(40-59) ⊇ elim(60-79) ⊇ elim(>=80).
    An aide that is impossible above a threshold is also impossible below it, so
    any aide eliminated at a higher tranche must be eliminated at every lower one.
    When it is not, the LLM mis-counted; we REPAIR (never drop) by giving each
    tranche the union of its own eliminations and those of all higher tranches.

    Categorical / enumerated questions (options without a numeric order, or with
    ambiguous duplicate keys) are returned unchanged. Each reintegration is logged
    as a WARNING so the LLM's arithmetic errors stay visible.
    """
    # Keep only options that carry a numeric threshold key.
    keyed: dict[str, tuple[int, ...]] = {}
    for o in options:
        if not isinstance(o, dict):
            continue
        oid = o.get("id")
        if not oid or oid == "skip":
            continue
        key = _option_threshold_key(o)
        if key is not None:
            keyed[oid] = key

    # Need ≥2 tranches with DISTINCT keys to establish an order; otherwise the
    # question is categorical or the order is ambiguous — don't guess.
    if len(keyed) < 2 or len(set(keyed.values())) != len(keyed):
        return clean_elim

    ordered = sorted(keyed, key=lambda oid: keyed[oid])  # ascending threshold

    # Accumulate from the highest threshold down to the lowest: every lower
    # tranche inherits the eliminations of all higher tranches.
    cumulative: set[str] = set()
    repaired: dict[str, set[str]] = {}
    for oid in reversed(ordered):
        cumulative = cumulative | set(clean_elim.get(oid, []))
        repaired[oid] = set(cumulative)

    out = dict(clean_elim)
    for oid in ordered:
        added = repaired[oid] - set(clean_elim.get(oid, []))
        if added:
            logger.warning(
                "[QCM] Monotonie réparée (catégorie « %s », option « %s ») : "
                "%d aide(s) réintégrée(s) : %s",
                categorie,
                oid,
                len(added),
                sorted(added),
            )
        if repaired[oid]:
            out[oid] = sorted(repaired[oid])
    return out


def _process_qcm_response(
    parsed: dict,
    aide_ids_by_category: dict[str, list[str]],
    eligible_results: list[dict],
) -> list[dict]:
    """Validate, remap, sanitize and bucket a parsed QCM LLM response.

    Pure transformation (no network). Returns the list of clean questions.
    Extracting this from `generate_qcm_questions` makes the validation, the
    monotonicity repair (FIX 2) and the conservative clarification policy
    (FIX 1 + FIX 5) unit-testable without an LLM round-trip.
    """
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
            logger.warning("[QCM] Question ignorée: catégorie « %s » inconnue ou sans aides", cat)
            continue
        qid = q.get("id")
        qtext = q.get("question")
        options = q.get("options")
        if not (qid and qtext and isinstance(options, list)):
            logger.warning("[QCM] Question malformée ignorée: %s", q)
            continue
        q["aideIds"] = mapped_ids
        valid_ids = set(mapped_ids)
        option_ids = {o.get("id") for o in options if isinstance(o, dict) and o.get("id")}

        # Sanitize fine-grained eliminationsParOption: keep only known options
        # and aide IDs from this category's pool. The LLM has the
        # (critere, aideIds) pairs in its payload, so any aide ID outside the
        # pool is a hallucination — drop it rather than eliminate aides based on
        # guessed IDs.
        raw_elim = q.get("eliminationsParOption")
        clean_elim: dict[str, list[str]] = {}
        if isinstance(raw_elim, dict):
            for opt_id, aide_list in raw_elim.items():
                if opt_id == "skip":
                    continue
                if opt_id not in option_ids:
                    logger.warning(
                        "[QCM] eliminationsParOption: option « %s » inconnue (catégorie « %s »)",
                        opt_id,
                        cat,
                    )
                    continue
                if not isinstance(aide_list, list):
                    continue
                valid = [aid for aid in aide_list if isinstance(aid, str) and aid in valid_ids]
                dropped = len(aide_list) - len(valid)
                if dropped:
                    logger.warning(
                        "[QCM] %d aide ID(s) hallucinée(s) droppée(s) "
                        "(catégorie « %s », option « %s »)",
                        dropped,
                        cat,
                        opt_id,
                    )
                if valid:
                    clean_elim[opt_id] = sorted(set(valid))

        # Sanitize coarse eliminatingOptionIds: only options that exist and
        # aren't "skip".
        raw_coarse = q.get("eliminatingOptionIds") or []
        clean_coarse = (
            [
                opt_id
                for opt_id in raw_coarse
                if isinstance(opt_id, str) and opt_id in option_ids and opt_id != "skip"
            ]
            if isinstance(raw_coarse, list)
            else []
        )

        # If the LLM only gave coarse data, expand to fine-grained using the full
        # aide pool. This preserves intent but logs a warning: the coarse path
        # over-rejects when a category aggregates aides at different thresholds
        # (the very bug we're fixing). The prompt asks for fine-grained
        # explicitly, so this branch should be rare and indicates the LLM ignored
        # instructions.
        if clean_coarse and not clean_elim:
            logger.warning(
                "[QCM] Catégorie « %s » : seul eliminatingOptionIds fourni — "
                "expansion coarse (risque sur-élimination si seuils mixtes)",
                cat,
            )
            clean_elim = {opt_id: sorted(valid_ids) for opt_id in clean_coarse}

        # FIX 2: enforce nested-decreasing monotonicity for ordered-threshold
        # questions (no-op for categorical / enumerated ones).
        clean_elim = _repair_monotonic_eliminations(clean_elim, options, cat)

        q["eliminationsParOption"] = clean_elim
        q["eliminatingOptionIds"] = clean_coarse
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
            logger.info(
                "[QCM] Catégorie « %s » skippée par le LLM : %s "
                "(NON promue — politique conservatrice FIX 5)",
                cat,
                raison,
            )
        else:
            logger.warning("[QCM] Catégorie skippée « %s » absente du payload — ignorée", cat)

    # Categories the LLM silently dropped (neither asked nor explicitly skipped).
    silently_missed = input_categories - covered - claimed_skipped
    for cat in silently_missed:
        logger.warning(
            "[QCM] Catégorie « %s » oubliée par le LLM — incertitude(s) maintenue(s) potentielle(s)",
            cat,
        )

    # FIX 1 + FIX 5 (politique conservatrice) : seule une réponse explicite de
    # l'utilisateur marque clarified=True. NI les catégories skippées par le LLM
    # NI celles silencieusement oubliées ne sont clarifiées ici — sinon on
    # promeut des aides que personne n'a vérifiées, gonflant montantPotentielTotal.
    # On NE touche donc PAS aux incertitudes : elles restent pending, leurs aides
    # restent en aidesPotentiellementEligibles jusqu'à réponse explicite (la
    # clarification answer-driven est appliquée plus tard, côté frontend).
    n_kept_skipped = _count_incertitudes_in_categories(eligible_results, claimed_skipped)
    n_kept_missed = _count_incertitudes_in_categories(eligible_results, silently_missed)

    logger.info(
        "→ %d question(s) QCM (brut: %d) — maintenues potentielles : "
        "skip LLM %d cat./%d incertitude(s), oubli LLM %d cat./%d incertitude(s) ; "
        "aucune auto-clarification (politique conservatrice)",
        len(questions),
        len(raw_questions),
        len(claimed_skipped),
        n_kept_skipped,
        len(silently_missed),
        n_kept_missed,
    )
    for q in questions:
        logger.info(
            "  ? [%s] %s (%d aide(s))",
            q.get("categorie", "?"),
            (q.get("question") or "")[:80],
            len(q.get("aideIds", [])),
        )

    return questions


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

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        logger.warning("DEEPSEEK_API_KEY not set, skipping QCM generation")
        return []

    client = _get_llm_client(api_key)

    # Build a compact payload (no category-level aideIds) for the LLM — we remap
    # questions back to aides from categorie after.
    compact_payload = _compact_for_llm(aggregated)
    aide_ids_by_category = {g["categorie"]: g["aideIds"] for g in aggregated}

    prompt = render_prompt_qcm(
        max_questions=MAX_QCM_QUESTIONS,
        monument_profile=monument_profile,
        incertitudes_json=json.dumps(compact_payload, ensure_ascii=False, indent=2),
    )
    logger.info("[QCM] Prompt construit (%d caractères), appel LLM...", len(prompt))

    QCM_TIMEOUT_S = 300

    async def _call(repair_with: str | None = None) -> str:
        """One round-trip to the LLM; if `repair_with` is set, ask for a JSON fix."""
        messages: list[dict] = [{"role": "user", "content": prompt}]
        if repair_with is not None:
            messages.append({"role": "assistant", "content": repair_with})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Ta réponse précédente n'est pas un JSON valide. "
                        "Renvoie exactement les mêmes questions, mais en JSON strict, "
                        "sans aucun texte hors du bloc JSON."
                    ),
                }
            )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=_MODEL_QCM,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            ),
            timeout=QCM_TIMEOUT_S,
        )
        return response.choices[0].message.content

    last_error = None
    json_repair_used = False
    broken_content: str | None = None
    content: str | None = None
    for attempt in range(3):
        try:
            logger.info("[QCM] Tentative %d/3 (timeout %ds)...", attempt + 1, QCM_TIMEOUT_S)
            content = await _call(repair_with=broken_content if json_repair_used else None)
            logger.info("[QCM] Réponse reçue (%d caractères)", len(content or ""))
            parsed = json.loads(content)
            return _process_qcm_response(parsed, aide_ids_by_category, eligible_results)
        except json.JSONDecodeError as e:
            last_error = e
            if not json_repair_used:
                json_repair_used = True
                broken_content = content
                logger.warning(
                    "[QCM] JSON invalide (tentative %d/3) — tentative de réparation", attempt + 1
                )
                continue  # immediate repair retry, no backoff
            logger.error("[QCM] JSON invalide même après réparation — abandon")
            break
        except APIStatusError as e:
            last_error = e
            if _is_permanent_llm_error(e):
                logger.error(
                    "[QCM] Erreur permanente LLM (HTTP %s) — pas de retry",
                    e.status_code,
                )
                break
            if attempt < 2:
                wait = 2**attempt
                logger.warning(
                    "[QCM] Tentative %d/3 échouée (HTTP %s), retry dans %ds",
                    attempt + 1,
                    getattr(e, "status_code", "?"),
                    wait,
                )
                await asyncio.sleep(wait)
        except Exception as e:
            last_error = e
            if not _is_transient_network_error(e):
                logger.error(
                    "[QCM] Erreur non-transitoire (%s: %s) — pas de retry",
                    type(e).__name__,
                    e,
                )
                break
            if attempt < 2:
                wait = 2**attempt
                logger.warning(
                    "[QCM] Tentative %d/3 réseau (%s), retry dans %ds", attempt + 1, e, wait
                )
                await asyncio.sleep(wait)
    logger.error(f"QCM generation failed: {last_error}")
    return []


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _should_generate_qcm(all_with_incertitudes: list, skip_qcm: bool) -> bool:
    """QCM runs only when there is at least one incertitude and the caller did
    not opt out via skip_qcm."""
    return bool(all_with_incertitudes) and not skip_qcm


async def run_diagnostic(
    supabase: Client,
    monument: dict,
    user: dict,
    mode_projet: bool = False,
    travaux_filtres: list[str] | None = None,
    skip_qcm: bool = False,
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

    # Phase 1: SQL pre-filter (also resolves the commune population, reused below)
    candidate_ids, population = prefiltrer_aides(supabase, monument, user, ctx_travaux or None)
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

    # Candidates from SQL are eligible — just build labels for display.
    # The SQL pre-filter is the single source of truth for eligibility; the
    # labels are display only. If the Python labels disagree with the SQL
    # verdict, log it — it points to a bug in the label builder (e.g. a
    # missing join column, a mapping drift) but does not override the verdict.
    eligible_results = [
        _build_criteria_labels(a, monument, user, mode_projet, ctx_travaux, population)
        for a in candidate_aides
    ]
    for r in eligible_results:
        if r["criteresNonRemplis"]:
            logger.warning(
                "[LABEL DRIFT] aide %s passed SQL pre-filter but labels show unmet criteria: %s",
                r["aide"].get("nom_court") or r["aide"].get("nom"),
                r["criteresNonRemplis"],
            )
        r["eligible"] = True
        r["raisonIneligibilite"] = None

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

    # Phase 4: Generate QCM questions from incertitudes. FIX 1 + FIX 5: the QCM
    # generation NO LONGER auto-clarifies incertitudes for categories the LLM
    # skipped or silently forgot — only an explicit user answer (applied later)
    # may clarify one. So at generation time no incertitude flips to clarified.
    qcm_questions = []
    all_with_incertitudes = still_eligible + potentially_eligible
    if _should_generate_qcm(all_with_incertitudes, skip_qcm):
        qcm_questions = await generate_qcm_questions(all_with_incertitudes, monument_profile)

    # Re-bucket: promote only aides whose incertitudes are ALL clarified. Under
    # the conservative policy that means clarified by an explicit user answer —
    # at diagnostic-generation time there is none yet, so this promotes nothing
    # and aides with unanswered incertitudes (including LLM-skipped or
    # silently-missed categories) stay potential, out of montantPotentielTotal.
    promoted = [r for r in potentially_eligible if _all_incertitudes_clarified(r)]
    maintained = len(potentially_eligible) - len(promoted)
    if promoted:
        promoted_ids = {r["aide"]["id"] for r in promoted}
        still_eligible.extend(promoted)
        potentially_eligible = [
            r for r in potentially_eligible if r["aide"]["id"] not in promoted_ids
        ]
        logger.info("→ %d aide(s) promue(s) (réponse explicite)", len(promoted))
    if maintained:
        logger.info(
            "→ %d aide(s) maintenue(s) potentielle(s) "
            "(incertitude(s) non répondue(s) : oubli/skip LLM)",
            maintained,
        )

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
