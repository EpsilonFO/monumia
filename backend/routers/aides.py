from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import Client

from db import get_supabase, get_current_user_id
from matching_engine import run_diagnostic

router = APIRouter(prefix="/aides", tags=["aides"])

COLUMNS = "*"


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

def _get_all_aides(supabase: Client) -> list[dict]:
    result = supabase.table("aides").select(COLUMNS).execute()
    return result.data or []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def list_aides(
    categorie: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    supabase: Client = Depends(get_supabase),
):
    query = supabase.table("aides").select(COLUMNS).order("nom")

    if categorie:
        query = query.eq("categorie", categorie)

    aides = query.execute().data or []

    # Text search in Python (nom, nomCourt, description, organisme)
    if q:
        q_lower = q.lower()
        aides = [
            a for a in aides
            if q_lower in (a.get("nom") or "").lower()
            or q_lower in (a.get("nom_court") or "").lower()
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
    return result.data


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

    # Fetch all aides
    aides = _get_all_aides(supabase)

    return run_diagnostic(
        monument=monument,
        user=user,
        aides=aides,
        mode_projet=body.mode_projet,
        travaux_filtres=body.travaux_filtres,
    )
