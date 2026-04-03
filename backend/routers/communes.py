from fastapi import APIRouter, Depends, Query
from supabase import Client

from db import get_supabase

router = APIRouter(prefix="/communes", tags=["communes"])


@router.get("/search")
def search_communes(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, le=50),
    supabase: Client = Depends(get_supabase),
):
    """Search communes by name prefix (case-insensitive)."""
    result = (
        supabase.table("communes")
        .select(
            "code_insee, nom_commune, departement, departement_num, region, code_postal, arrondissement, population"
        )
        .ilike("nom_commune", f"{q}%")
        .order("nom_commune")
        .limit(limit)
        .execute()
    )

    rows = []
    for r in result.data:
        rows.append(
            {
                "codeInsee": r["code_insee"],
                "nom": r["nom_commune"],
                "departement": r["departement"],
                "codeDepartement": r["departement_num"],
                "region": r["region"],
                "codePostal": r.get("code_postal"),
                "arrondissement": r.get("arrondissement"),
                "population": r.get("population"),
            }
        )
    return rows
