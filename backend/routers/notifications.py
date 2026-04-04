from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from db import get_supabase, get_current_user_id

router = APIRouter(prefix="/notifications", tags=["notifications"])

COLUMNS = "*"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LienVers(BaseModel):
    type: str  # 'aide' | 'dossier' | 'monument' | 'document'
    id: str


class CreateNotificationRequest(BaseModel):
    type: str  # 'urgent' | 'opportunite' | 'info'
    categorie: str  # 'deadline_proche' | 'nouvelle_aide' | ...
    titre: str
    message: str
    lien_vers: Optional[LienVers] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_notification_or_404(supabase: Client, notification_id: str, user_id: str) -> dict:
    result = (
        supabase.table("notifications")
        .select(COLUMNS)
        .eq("id", notification_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Notification introuvable")
    return result.data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
def list_notifications(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    result = (
        supabase.table("notifications")
        .select(COLUMNS)
        .eq("user_id", user_id)
        .order("date_creation", desc=True)
        .execute()
    )
    return result.data


@router.post("", status_code=status.HTTP_201_CREATED)
def create_notification(
    body: CreateNotificationRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    row = {
        "user_id": user_id,
        "type": body.type,
        "categorie": body.categorie,
        "titre": body.titre,
        "message": body.message,
        "lue": False,
        "lien_vers": body.lien_vers.model_dump() if body.lien_vers else None,
    }
    result = supabase.table("notifications").insert(row).execute()
    return result.data[0]


@router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_as_read(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _get_notification_or_404(supabase, notification_id, user_id)
    supabase.table("notifications").update({"lue": True}).eq("id", notification_id).execute()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_as_read(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    supabase.table("notifications").update({"lue": True}).eq("user_id", user_id).execute()


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _get_notification_or_404(supabase, notification_id, user_id)
    supabase.table("notifications").delete().eq("id", notification_id).execute()
