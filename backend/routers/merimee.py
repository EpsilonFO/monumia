from fastapi import APIRouter, Depends, Query
from supabase import Client

from db import get_supabase

router = APIRouter(prefix="/merimee", tags=["merimee"])

COLUMNS = "reference,region,commune_forme_index,departement_en_lettres,typologie_de_la_protection,titre_editorial_de_la_notice,denomination_de_l_edifice,statut_juridique_de_l_edifice,siecle_de_la_campagne_principale_de_construction,format_abrege_du_siecle_de_construction,type_de_couverture,materiaux_de_la_couverture,materiaux_du_gros_oeuvre,date_et_typologie_de_la_protection,precision_de_la_protection,cog_insee_lors_de_la_protection"


@router.get("/search")
def search(
    q: str = Query(..., min_length=2),
    supabase: Client = Depends(get_supabase),
):
    tokens = [t for t in q.split() if t]

    response = supabase.rpc(
        "search_merimee",
        {"tokens": tokens},
    ).execute()

    return response.data[:20]


def _resolve_commune_actuelle(
    supabase: Client, historical_code: str | None, commune_forme_index: str | None
) -> str | None:
    """Return the current commune name if it differs from the historical one, else None."""
    if not historical_code:
        return None

    direct = (
        supabase.table("communes")
        .select("nom_commune")
        .eq("code_insee", historical_code)
        .limit(1)
        .execute()
    )
    if direct.data:
        current = direct.data[0]["nom_commune"]
        if (commune_forme_index or "").strip().lower() != current.strip().lower():
            return current
        return None

    mapped = (
        supabase.table("communes_historique")
        .select("nouveau_code_insee")
        .eq("ancien_code_insee", historical_code)
        .limit(1)
        .execute()
    )
    if not mapped.data:
        return None

    current_row = (
        supabase.table("communes")
        .select("nom_commune")
        .eq("code_insee", mapped.data[0]["nouveau_code_insee"])
        .limit(1)
        .execute()
    )
    return current_row.data[0]["nom_commune"] if current_row.data else None


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
    record = response.data or {}
    record["commune_actuelle"] = _resolve_commune_actuelle(
        supabase,
        record.get("cog_insee_lors_de_la_protection"),
        record.get("commune_forme_index"),
    )
    return record
