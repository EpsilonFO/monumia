
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase
from matching_engine import _check_eligibility, run_diagnostic

router = APIRouter(prefix="/aides", tags=["aides"])

COLUMNS = "*"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DiagnosticRequest(BaseModel):
    monument_id: str
    mode_projet: bool = False
    travaux_filtres: list[str] | None = None


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


def _get_all_aides(supabase: Client) -> list[dict]:
    result = supabase.table("aides").select(COLUMNS).execute()
    return result.data or []


def _get_all_aides_camel(supabase: Client) -> list[dict]:
    return [_to_camel(a) for a in _get_all_aides(supabase)]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def list_aides(
    categorie: str | None = Query(None),
    q: str | None = Query(None),
    supabase: Client = Depends(get_supabase),
):
    query = supabase.table("aides").select(COLUMNS).order("nom")

    if categorie:
        query = query.eq("categorie", categorie)

    aides = query.execute().data or []
    aides = [_to_camel(a) for a in aides]

    # Text search in Python (nom, nomCourt, description, organisme)
    if q:
        q_lower = q.lower()
        aides = [
            a for a in aides
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
    result = (
        supabase.table("aides")
        .select(COLUMNS)
        .eq("id", aide_id)
        .single()
        .execute()
    )
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
    monument = monument_result.data

    # Fetch user profile
    user_result = (
        supabase.table("users")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not user_result.data:
        raise HTTPException(status_code=404, detail="Profil utilisateur introuvable")
    user = user_result.data

    # Fetch all aides (camelCase for matching engine + response)
    aides = _get_all_aides_camel(supabase)

    result = run_diagnostic(
        monument=monument,
        user=user,
        aides=aides,
        mode_projet=body.mode_projet,
        travaux_filtres=body.travaux_filtres,
    )

    # Persist diagnostic to DB — only aide IDs, criteria are recomputed at read time
    row = {
        "monument_id": body.monument_id,
        "user_id": user_id,
        "mode_projet": body.mode_projet,
        "travaux_filtres": body.travaux_filtres,
        "total_aides_analysees": result["totalAidesAnalysees"],
        "aides_eligibles_count": len(result["aidesEligibles"]),
        "aides_non_eligibles_count": len(result["aidesNonEligibles"]),
        "montant_potentiel_total": result.get("montantPotentielTotal"),
        "aides_eligibles_ids": [m["aide"]["uuid"] for m in result["aidesEligibles"]],
        "aides_non_eligibles_ids": [m["aide"]["uuid"] for m in result["aidesNonEligibles"]],
    }
    insert_result = supabase.table("diagnostics").insert(row).execute()
    if insert_result.data:
        result["id"] = insert_result.data[0]["id"]

    return result


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
    monument = monument_result.data
    user_result = (
        supabase.table("users")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
    )
    user = user_result.data

    # Build aide lookup keyed by uuid (fetched once)
    aides_by_id = {a["uuid"]: a for a in _get_all_aides_camel(supabase)}

    return [
        _hydrate_diagnostic(d, aides_by_id, monument, user)
        for d in diagnostics
    ]


def _hydrate_diagnostic(row: dict, aides_by_id: dict, monument: dict, user: dict) -> dict:
    """Reconstruct full AideDiagnosticResult by joining aide IDs and recomputing criteria."""
    mode_projet = row.get("mode_projet", False)
    travaux_filtres = row.get("travaux_filtres") or []

    def _build_match(aide_id: str) -> dict | None:
        aide = aides_by_id.get(aide_id)
        if not aide:
            return None
        return _check_eligibility(aide, monument, user, mode_projet, travaux_filtres)

    aides_eligibles = [
        m for aid in (row.get("aides_eligibles_ids") or [])
        if (m := _build_match(aid)) is not None
    ]
    aides_non_eligibles = [
        m for aid in (row.get("aides_non_eligibles_ids") or [])
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
        "aidesNonEligibles": aides_non_eligibles,
        "montantPotentielTotal": (
            float(row["montant_potentiel_total"])
            if row.get("montant_potentiel_total") is not None
            else None
        ),
    }
