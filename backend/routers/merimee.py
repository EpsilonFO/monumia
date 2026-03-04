from fastapi import APIRouter, Depends, Query
from supabase import Client

from db import get_supabase

router = APIRouter(prefix="/merimee", tags=["merimee"])

COLUMNS = "reference,region,commune_forme_index,departement_en_lettres,typologie_de_la_protection,titre_editorial_de_la_notice"


@router.get("/search")
def search(
    q: str = Query(..., min_length=2),
    supabase: Client = Depends(get_supabase),
):
    response = (
        supabase.table("merimee_buildings")
        .select(COLUMNS)
        .or_(
            f"titre_editorial_de_la_notice.ilike.%{q}%,"
            f"commune_forme_index.ilike.%{q}%,"
            f"reference.ilike.%{q}%"
        )
        .limit(20)
        .execute()
    )
    return response.data


@router.get("/{reference}")
def get_by_reference(
    reference: str,
    supabase: Client = Depends(get_supabase),
):
    response = (
        supabase.table("merimee_buildings")
        .select(COLUMNS)
        .eq("reference", reference)
        .single()
        .execute()
    )
    return response.data
