from fastapi import APIRouter, Depends, Query
from supabase import Client

from db import get_supabase

router = APIRouter(prefix="/merimee", tags=["merimee"])

COLUMNS = "reference,region,commune_forme_index,departement_en_lettres,typologie_de_la_protection,titre_editorial_de_la_notice,denomination_de_l_edifice,statut_juridique_de_l_edifice,siecle_de_la_campagne_principale_de_construction,format_abrege_du_siecle_de_construction,type_de_couverture,materiaux_de_la_couverture,materiaux_du_gros_oeuvre,date_et_typologie_de_la_protection,precision_de_la_protection"

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


@router.get("/{reference}")
def get_by_reference(
    reference: str,
    supabase: Client = Depends(get_supabase),
):
    response = supabase.table("merimee_buildings").select(COLUMNS).eq("reference", reference).single().execute()
    return response.data
