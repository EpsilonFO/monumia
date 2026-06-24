from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase
from services.suivi_service import SuiviValidationError, apply_statut_change

router = APIRouter(prefix="/monuments", tags=["suivi"])


class UpsertSuiviRequest(BaseModel):
    statut: str
    montant_obtenu: float | None = None
    motif_refus_code: str | None = None
    motif_refus_detail: str | None = None
    note: str | None = None


def _assert_monument_owner(supabase: Client, monument_id: str, user_id: str) -> None:
    result = (
        supabase.table("monuments")
        .select("id")
        .eq("id", monument_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Projet introuvable")


def _assert_dossier_exists(supabase: Client, monument_id: str, aide_id: str, user_id: str) -> None:
    """Le suivi ne vit que là où un dossier existe pour l'aide dans ce projet —
    on refuse de créer/modifier un suivi orphelin (données propres pour analyse)."""
    result = (
        supabase.table("dossiers")
        .select("id")
        .eq("monument_id", monument_id)
        .eq("aide_id", aide_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=409,
            detail="Aucun dossier pour cette aide ; créez le dossier avant de la suivre.",
        )


@router.get("/{monument_id}/aide-suivis")
def list_aide_suivis(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _assert_monument_owner(supabase, monument_id, user_id)
    result = (
        supabase.table("aide_suivis")
        .select("*")
        .eq("monument_id", monument_id)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data


@router.put("/{monument_id}/aides/{aide_id}/suivi")
def upsert_aide_suivi(
    monument_id: str,
    aide_id: str,
    body: UpsertSuiviRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _assert_monument_owner(supabase, monument_id, user_id)
    _assert_dossier_exists(supabase, monument_id, aide_id, user_id)

    existing_result = (
        supabase.table("aide_suivis")
        .select("*")
        .eq("monument_id", monument_id)
        .eq("aide_id", aide_id)
        .eq("user_id", user_id)
        .execute()
    )
    existing = existing_result.data[0] if existing_result.data else None

    try:
        fields = apply_statut_change(existing, body.model_dump())
    except SuiviValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    if existing:
        result = supabase.table("aide_suivis").update(fields).eq("id", existing["id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Suivi introuvable")
        return result.data[0]

    row = {**fields, "monument_id": monument_id, "aide_id": aide_id, "user_id": user_id}
    result = supabase.table("aide_suivis").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Échec de l'enregistrement du suivi")
    return result.data[0]


@router.delete(
    "/{monument_id}/aides/{aide_id}/suivi",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_aide_suivi(
    monument_id: str,
    aide_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _assert_monument_owner(supabase, monument_id, user_id)
    supabase.table("aide_suivis").delete().eq("monument_id", monument_id).eq("aide_id", aide_id).eq(
        "user_id", user_id
    ).execute()


@router.post("/{monument_id}/cloture")
def cloturer_projet(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _assert_monument_owner(supabase, monument_id, user_id)
    result = (
        supabase.table("monuments")
        .update({"cloture_at": datetime.now(UTC).isoformat()})
        .eq("id", monument_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    return result.data[0]


@router.post("/{monument_id}/reouverture")
def rouvrir_projet(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _assert_monument_owner(supabase, monument_id, user_id)
    result = (
        supabase.table("monuments")
        .update({"cloture_at": None})
        .eq("id", monument_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    return result.data[0]
