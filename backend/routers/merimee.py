from fastapi import APIRouter, Depends, Query
from supabase import Client

from db import get_supabase

router = APIRouter(prefix="/merimee", tags=["merimee"])

COLUMNS = "reference,region,commune_forme_index,departement_en_lettres,typologie_de_la_protection,titre_editorial_de_la_notice"


SEARCHABLE_FIELDS = [
    "titre_editorial_de_la_notice",
    "commune_forme_index",
    "departement_en_lettres",
    "reference",
    "region",
    "typologie_de_la_protection",
]


def _row_matches_token(row: dict, token: str) -> bool:
    token_lower = token.lower()
    return any(
        token_lower in (row.get(field) or "").lower()
        for field in SEARCHABLE_FIELDS
    )


@router.get("/search")
def search(
    q: str = Query(..., min_length=2),
    supabase: Client = Depends(get_supabase),
):
    tokens = [t for t in q.split() if t]

    # Build an OR filter on the first token to let Supabase/Postgres do
    # the heavy lifting, then filter remaining tokens in Python.
    first = tokens[0]
    or_filter = ",".join(
        f"{field}.ilike.%{first}%"
        for field in SEARCHABLE_FIELDS
    )

    response = (
        supabase.table("merimee_buildings")
        .select(COLUMNS)
        .or_(or_filter)
        .limit(200)
        .execute()
    )

    results = response.data
    for token in tokens[1:]:
        results = [row for row in results if _row_matches_token(row, token)]

    return results[:20]


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
