import logging
import traceback
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import Client

from aides_schema import load_all_aides, load_facts, load_pending_facts
from db import get_current_user_id, get_supabase
from eligibility_engine import aide_display_dict, run_deterministic_diagnostic
from matching_engine import _build_criteria_labels, fetch_aides_with_joins, run_diagnostic
from routers.monuments import _enrich_monument
from services.project_access import require_project_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aides", tags=["aides"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DiagnosticRequest(BaseModel):
    monument_id: str
    mode_projet: bool = False
    travaux_filtres: list[str] | None = None
    skip_qcm: bool = False


class UpdateQcmAnswersRequest(BaseModel):
    qcm_answers: dict[str, str]


class DeterministicDiagnosticRequest(BaseModel):
    monument_id: str
    # Réponses déjà connues (fact_key → valeur). Optionnel : le front résout
    # aussi les éliminations côté client via eliminationsParOption.
    answers: dict[str, object] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Map DB snake_case columns → frontend camelCase keys
_AIDE_KEY_MAP = {
    "nom_court": "nomCourt",
    "description_longue": "descriptionLongue",
    "montant_max": "montantMax",
    "taux_max": "tauxMax",
    "montant_min": "montantMin",
    "commune_max_population": "communeMaxPopulation",
    "cofinancement_requis": "cofinancementRequis",
    "architecte_requis": "architecteRequis",
    "conditions_eligibilite_detail": "conditionsEligibiliteDetail",
    "demarche_description": "demarcheDescription",
    "documents_requis": "documentsRequis",
    "delai_instruction": "delaiInstruction",
    "date_ouverture": "dateOuverture",
    "date_limite": "dateLimite",
    "url_officielle": "urlOfficielle",
    "formulaire_url": "formulaireUrl",
    "base_ttc": "baseTTC",
    "created_at": "createdAt",
    "updated_at": "updatedAt",
}


def _to_camel(aide: dict) -> dict:
    """Convert a DB aide row (snake_case) to frontend shape (camelCase)."""
    out = {}
    for k, v in aide.items():
        out[_AIDE_KEY_MAP.get(k, k)] = v
    return out


_DIAGNOSTIC_BUCKETS = (
    "aidesEligibles",
    "aidesPotentiellementEligibles",
    "aidesAtteignables",
    "aidesNonEligibles",
)


def _camelise_diagnostic(result: dict) -> dict:
    """Convert aide objects inside diagnostic results to camelCase."""
    for bucket in _DIAGNOSTIC_BUCKETS:
        for match in result.get(bucket, []):
            match["aide"] = _to_camel(match["aide"])
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
def list_aides(
    categorie: str | None = Query(None),
    q: str | None = Query(None),
    supabase: Client = Depends(get_supabase),
):
    query = supabase.table("aides_v3").select("*").order("nom")

    if categorie:
        query = query.eq("categorie", categorie)

    aides = query.execute().data or []
    aides = [_to_camel(a) for a in aides]

    if q:
        q_lower = q.lower()
        aides = [
            a
            for a in aides
            if q_lower in (a.get("nom") or "").lower()
            or q_lower in (a.get("nomCourt") or "").lower()
            or q_lower in (a.get("description") or "").lower()
            or q_lower in (a.get("organisme") or "").lower()
        ]

    return aides


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


@router.get("/{aide_id}")
def get_aide(
    aide_id: str,
    supabase: Client = Depends(get_supabase),
):
    """Récupère une aide par id.

    Le moteur déterministe identifie les aides par leur slug (il lit les YAML,
    pas la base). Donc `aide_id` peut être un UUID (aide en base) ou un slug
    (aide servie depuis les YAML). On résout dans cet ordre : UUID en base,
    puis YAML par slug — la même source que le diagnostic, donc l'affichage
    reste cohérent même si le loader n'a pas (encore) poussé l'aide en base.
    """
    if _is_uuid(aide_id):
        result = supabase.table("aides_v3").select("*").eq("id", aide_id).maybe_single().execute()
        if result and result.data:
            return _to_camel(result.data)

    aide = load_all_aides().get(aide_id)
    if aide:
        return _to_camel(aide_display_dict(aide))

    raise HTTPException(status_code=404, detail="Aide introuvable")


@router.post("/diagnostic")
async def diagnostic(
    body: DiagnosticRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    # Fetch monument (must belong to user)
    require_project_access(supabase, body.monument_id, user_id, "co_owner")
    monument_result = (
        supabase.table("monuments").select("*").eq("id", body.monument_id).single().execute()
    )
    if not monument_result.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    monument = _enrich_monument(supabase, monument_result.data)

    # Fetch user profile
    user_result = supabase.table("users").select("*").eq("id", user_id).single().execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="Profil utilisateur introuvable")
    user = user_result.data

    try:
        result = await run_diagnostic(
            supabase=supabase,
            monument=monument,
            user=user,
            mode_projet=body.mode_projet,
            travaux_filtres=body.travaux_filtres,
            skip_qcm=body.skip_qcm,
        )
    except Exception as exc:
        logger.error("run_diagnostic crashed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erreur matching engine : {exc}") from exc

    # Capture LLM evaluations per aide so they can be re-hydrated on reload
    # without re-running Mistral. Keyed by aide id.
    llm_evaluations: dict[str, dict] = {}
    for bucket in ("aidesEligibles", "aidesPotentiellementEligibles", "aidesNonEligibles"):
        for match in result.get(bucket, []):
            evaluation = match.get("llmEvaluation")
            if evaluation:
                llm_evaluations[match["aide"]["id"]] = evaluation

    # Persist diagnostic to DB
    row = {
        "monument_id": body.monument_id,
        "user_id": user_id,
        "mode_projet": body.mode_projet,
        "travaux_filtres": body.travaux_filtres,
        "total_aides_analysees": result["totalAidesAnalysees"],
        "aides_eligibles_count": len(result["aidesEligibles"]),
        "aides_potentiellement_eligibles_count": len(result["aidesPotentiellementEligibles"]),
        "aides_non_eligibles_count": len(result["aidesNonEligibles"]),
        "montant_potentiel_total": result.get("montantPotentielTotal"),
        "aides_eligibles_ids": [m["aide"]["id"] for m in result["aidesEligibles"]],
        "aides_potentiellement_eligibles_ids": [
            m["aide"]["id"] for m in result["aidesPotentiellementEligibles"]
        ],
        "aides_non_eligibles_ids": [m["aide"]["id"] for m in result["aidesNonEligibles"]],
        "qcm_questions": result.get("qcmQuestions") or [],
        "qcm_answers": {},
        "llm_evaluations": llm_evaluations,
    }
    insert_result = supabase.table("diagnostics").insert(row).execute()
    if insert_result.data:
        result["id"] = insert_result.data[0]["id"]
    result["qcmAnswers"] = {}

    return _camelise_diagnostic(result)


def _resolve_population(supabase: Client, code_insee: str | None) -> int | None:
    if not code_insee:
        return None
    r = (
        supabase.table("communes")
        .select("population")
        .eq("code_insee", code_insee)
        .limit(1)
        .execute()
    )
    return r.data[0].get("population") if r.data else None


@router.post("/diagnostic-deterministe")
def diagnostic_deterministe(
    body: DeterministicDiagnosticRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Diagnostic 100 % déterministe (aucun LLM), sur les aides « engine-ready »
    (zéro condition untyped), conditions lues depuis les YAML typés.

    Non persisté (les aideIds sont des slugs, pas des UUID) : le résultat est
    rendu directement, le QCM se résout côté client via eliminationsParOption.
    """
    # Accès projet partagé : un collaborateur (membre) doit pouvoir lancer le
    # diagnostic, pas seulement le propriétaire — d'où require_project_access
    # plutôt qu'un filtre user_id (qui renverrait 404 aux collaborateurs).
    require_project_access(supabase, body.monument_id, user_id, "member")
    monument_result = (
        supabase.table("monuments").select("*").eq("id", body.monument_id).single().execute()
    )
    if not monument_result.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    monument = _enrich_monument(supabase, monument_result.data)
    population = _resolve_population(supabase, monument.get("code_insee"))

    aides = load_all_aides()
    facts = {**load_facts(), **load_pending_facts()}

    try:
        result = run_deterministic_diagnostic(
            aides=aides,
            facts=facts,
            monument=monument,
            population=population,
            answers=body.answers,
        )
    except Exception as exc:
        logger.error("run_deterministic_diagnostic crashed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erreur moteur déterministe : {exc}") from exc

    result["qcmAnswers"] = body.answers or {}
    return _camelise_diagnostic(result)


@router.patch("/diagnostics/by-id/{diagnostic_id}/qcm-answers")
def update_qcm_answers(
    diagnostic_id: str,
    body: UpdateQcmAnswersRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Persist the user's QCM answers so the post-QCM filtering survives a reload."""
    existing = (
        supabase.table("diagnostics")
        .select("id, monument_id")
        .eq("id", diagnostic_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Diagnostic introuvable")
    require_project_access(supabase, existing.data["monument_id"], user_id, "co_owner")

    supabase.table("diagnostics").update({"qcm_answers": body.qcm_answers}).eq(
        "id", diagnostic_id
    ).execute()
    return {"id": diagnostic_id, "qcmAnswers": body.qcm_answers}


@router.get("/diagnostics/{monument_id}")
def list_diagnostics(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Return all diagnostics for a monument, most recent first.
    Recomputes eligibility criteria from current aide + monument data."""
    require_project_access(supabase, monument_id, user_id, "member")
    diag_result = (
        supabase.table("diagnostics")
        .select("*")
        .eq("monument_id", monument_id)
        .order("created_at", desc=True)
        .execute()
    )
    diagnostics = diag_result.data or []
    if not diagnostics:
        return []

    # Fetch monument & user for re-running eligibility checks
    monument_result = (
        supabase.table("monuments").select("*").eq("id", monument_id).single().execute()
    )
    monument = monument_result.data
    user_result = supabase.table("users").select("*").eq("id", user_id).single().execute()
    user = user_result.data

    # Collect all aide UUIDs referenced across diagnostics
    all_aide_ids = set()
    for d in diagnostics:
        all_aide_ids.update(d.get("aides_eligibles_ids") or [])
        all_aide_ids.update(d.get("aides_potentiellement_eligibles_ids") or [])
        all_aide_ids.update(d.get("aides_non_eligibles_ids") or [])

    # Fetch all referenced aides with joins in one batch
    aides_list = fetch_aides_with_joins(supabase, list(all_aide_ids))
    aides_by_id = {a["id"]: a for a in aides_list}

    # Resolve population once. Applied to any monument with a code_insee —
    # population-capped aides exclude propriétaires privés in oversized communes
    # too, so the segment of the requesting user is irrelevant here.
    population = None
    code_insee = monument.get("code_insee") if monument else None
    if code_insee:
        commune_result = (
            supabase.table("communes")
            .select("population")
            .eq("code_insee", code_insee)
            .single()
            .execute()
        )
        if commune_result.data:
            population = commune_result.data.get("population")

    return [
        _camelise_diagnostic(_hydrate_diagnostic(d, aides_by_id, monument, user, population))
        for d in diagnostics
    ]


def _hydrate_diagnostic(
    row: dict, aides_by_id: dict, monument: dict, user: dict, population: int | None
) -> dict:
    """Reconstruct full diagnostic by joining aide IDs and recomputing criteria.

    `llm_evaluations` (captured at diagnostic time) are re-attached so the
    frontend can mark incertitudes as clarified after a page reload, without
    needing to re-run the LLM.
    """
    mode_projet = row.get("mode_projet", False)
    travaux_filtres = row.get("travaux_filtres") or []
    llm_evaluations = row.get("llm_evaluations") or {}

    def _build_match(aide_id: str) -> dict | None:
        aide = aides_by_id.get(aide_id)
        if not aide:
            return None
        match = _build_criteria_labels(
            aide, monument, user, mode_projet, travaux_filtres, population
        )
        evaluation = llm_evaluations.get(aide_id)
        if evaluation:
            match["llmEvaluation"] = evaluation
        return match

    aides_eligibles = [
        m for aid in (row.get("aides_eligibles_ids") or []) if (m := _build_match(aid)) is not None
    ]
    aides_potentiellement_eligibles = [
        m
        for aid in (row.get("aides_potentiellement_eligibles_ids") or [])
        if (m := _build_match(aid)) is not None
    ]
    aides_non_eligibles = [
        m
        for aid in (row.get("aides_non_eligibles_ids") or [])
        if (m := _build_match(aid)) is not None
    ]

    return {
        "id": row["id"],
        "monumentId": row["monument_id"],
        "timestamp": row["created_at"],
        "modeProjet": mode_projet,
        "travauxFiltres": row.get("travaux_filtres"),
        "totalAidesAnalysees": row["total_aides_analysees"],
        "aidesEligibles": aides_eligibles,
        "aidesPotentiellementEligibles": aides_potentiellement_eligibles,
        "aidesNonEligibles": aides_non_eligibles,
        "montantPotentielTotal": (
            float(row["montant_potentiel_total"])
            if row.get("montant_potentiel_total") is not None
            else None
        ),
        "qcmQuestions": row.get("qcm_questions") or [],
        "qcmAnswers": row.get("qcm_answers") or {},
    }
