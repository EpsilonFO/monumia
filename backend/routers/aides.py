from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import Client

from db import get_supabase, get_current_user_id
from matching_engine import run_diagnostic, fetch_aides_with_joins, _check_eligibility
from routers.monuments import _enrich_monument

router = APIRouter(prefix="/aides", tags=["aides"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DiagnosticRequest(BaseModel):
    monument_id: str
    mode_projet: bool = False
    travaux_filtres: Optional[list[str]] = None


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


def _camelise_diagnostic(result: dict) -> dict:
    """Convert aide objects inside diagnostic results to camelCase."""
    for match in result.get("aidesEligibles", []):
        match["aide"] = _to_camel(match["aide"])
    for match in result.get("aidesPotentiellementEligibles", []):
        match["aide"] = _to_camel(match["aide"])
    for match in result.get("aidesNonEligibles", []):
        match["aide"] = _to_camel(match["aide"])
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
def list_aides(
    categorie: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    supabase: Client = Depends(get_supabase),
):
    query = supabase.table("aides_v2").select("*").order("nom")

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


@router.get("/{aide_id}")
def get_aide(
    aide_id: str,
    supabase: Client = Depends(get_supabase),
):
    result = supabase.table("aides_v2").select("*").eq("id", aide_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Aide introuvable")
    return _to_camel(result.data)


@router.post("/diagnostic")
def diagnostic(
    body: DiagnosticRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    # Fetch monument (must belong to user)
    monument_result = (
        supabase.table("monuments")
        .select("*")
        .eq("id", body.monument_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not monument_result.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    monument = _enrich_monument(supabase, monument_result.data)

    # Fetch user profile
    user_result = (
        supabase.table("users").select("*").eq("id", user_id).single().execute()
    )
    if not user_result.data:
        raise HTTPException(status_code=404, detail="Profil utilisateur introuvable")
    user = user_result.data

    result = run_diagnostic(
        supabase=supabase,
        monument=monument,
        user=user,
        mode_projet=body.mode_projet,
        travaux_filtres=body.travaux_filtres,
    )

    # Persist diagnostic to DB
    row = {
        "monument_id": body.monument_id,
        "user_id": user_id,
        "mode_projet": body.mode_projet,
        "travaux_filtres": body.travaux_filtres,
        "total_aides_analysees": result["totalAidesAnalysees"],
        "aides_eligibles_count": len(result["aidesEligibles"]),
        "aides_potentiellement_eligibles_count": len(
            result["aidesPotentiellementEligibles"]
        ),
        "aides_non_eligibles_count": len(result["aidesNonEligibles"]),
        "montant_potentiel_total": result.get("montantPotentielTotal"),
        "aides_eligibles_ids": [m["aide"]["id"] for m in result["aidesEligibles"]],
        "aides_potentiellement_eligibles_ids": [
            m["aide"]["id"] for m in result["aidesPotentiellementEligibles"]
        ],
        "aides_non_eligibles_ids": [
            m["aide"]["id"] for m in result["aidesNonEligibles"]
        ],
    }
    insert_result = supabase.table("diagnostics").insert(row).execute()
    if insert_result.data:
        result["id"] = insert_result.data[0]["id"]

    return _camelise_diagnostic(result)


@router.get("/diagnostics/{monument_id}")
def list_diagnostics(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Return all diagnostics for a monument, most recent first.
    Recomputes eligibility criteria from current aide + monument data."""
    diag_result = (
        supabase.table("diagnostics")
        .select("*")
        .eq("monument_id", monument_id)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    diagnostics = diag_result.data or []
    if not diagnostics:
        return []

    # Fetch monument & user for re-running eligibility checks
    monument_result = (
        supabase.table("monuments")
        .select("*")
        .eq("id", monument_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    monument = (
        _enrich_monument(supabase, monument_result.data)
        if monument_result.data
        else None
    )
    user_result = (
        supabase.table("users").select("*").eq("id", user_id).single().execute()
    )
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

    # Resolve population once
    population = None
    code_insee = monument.get("code_insee") if monument else None
    if code_insee and user and user.get("segment") == "commune":
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
        _camelise_diagnostic(
            _hydrate_diagnostic(d, aides_by_id, monument, user, population)
        )
        for d in diagnostics
    ]


def _hydrate_diagnostic(
    row: dict, aides_by_id: dict, monument: dict, user: dict, population: Optional[int]
) -> dict:
    """Reconstruct full diagnostic by joining aide IDs and recomputing criteria."""
    mode_projet = row.get("mode_projet", False)
    travaux_filtres = row.get("travaux_filtres") or []

    def _build_match(aide_id: str) -> dict | None:
        aide = aides_by_id.get(aide_id)
        if not aide:
            return None
        return _check_eligibility(
            aide, monument, user, mode_projet, travaux_filtres, population
        )

    aides_eligibles = [
        m
        for aid in (row.get("aides_eligibles_ids") or [])
        if (m := _build_match(aid)) is not None
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
    }
