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
    categorie: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
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

    return run_diagnostic(
        monument=monument,
        user=user,
        aides=aides,
        mode_projet=body.mode_projet,
        travaux_filtres=body.travaux_filtres,
    )
