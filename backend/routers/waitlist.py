from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from supabase import Client

from db import get_supabase

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


class WaitlistRequest(BaseModel):
    email: EmailStr
    source: str | None = None


@router.post("", status_code=201)
def join_waitlist(
    body: WaitlistRequest,
    supabase: Client = Depends(get_supabase),
):
    """Inscription publique à la liste d'attente du lancement.

    Endpoint non authentifié, appelé par la landing. Idempotent : un e-mail
    déjà présent n'est pas dupliqué et ne renvoie pas d'erreur.
    """
    email = str(body.email).strip().lower()
    row = {"email": email, "source": (body.source or "landing").strip()[:64]}
    try:
        supabase.table("waitlist_emails").upsert(
            row, on_conflict="email", ignore_duplicates=True
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Enregistrement impossible") from e
    return {"ok": True}
