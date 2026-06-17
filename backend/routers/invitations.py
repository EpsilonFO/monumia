"""Aperçu et acceptation d'une invitation par token."""

import contextlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from db import get_current_user_id, get_supabase
from services.invitations import is_invitation_acceptable

router = APIRouter(prefix="/invitations", tags=["invitations"])


def _invitation_by_token(supabase: Client, token: str) -> dict:
    res = (
        supabase.table("project_invitations")
        .select("*")
        .eq("token", token)
        .maybe_single()
        .execute()
    )
    if not res or not res.data:
        raise HTTPException(status_code=404, detail="Invitation introuvable")
    return res.data


@router.get("/{token}")
def preview_invitation(token: str, supabase: Client = Depends(get_supabase)):
    """Aperçu non authentifié : nom du projet, invitant, statut."""
    inv = _invitation_by_token(supabase, token)

    monument = (
        supabase.table("monuments")
        .select("id, nom")
        .eq("id", inv["monument_id"])
        .maybe_single()
        .execute()
    )
    inviter = (
        supabase.table("users")
        .select("prenom, nom")
        .eq("id", inv["invited_by"])
        .maybe_single()
        .execute()
    )
    inviter_nom = (
        f"{inviter.data['prenom']} {inviter.data['nom']}"
        if inviter and inviter.data
        else "Un membre"
    )
    return {
        "monument_id": inv["monument_id"],
        "email": inv["email"],
        "monument_nom": monument.data["nom"] if monument and monument.data else "Projet",
        "inviter_nom": inviter_nom,
        "expires_at": inv["expires_at"],
        "status": inv["status"],
        "already_member": False,
    }


@router.post("/{token}/accept")
def accept_invitation(
    token: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Rattache l'utilisateur connecté au projet comme membre."""
    inv = _invitation_by_token(supabase, token)

    already = (
        supabase.table("project_members")
        .select("id")
        .eq("monument_id", inv["monument_id"])
        .eq("user_id", user_id)
        .execute()
    )
    if already.data:
        return {"monument_id": inv["monument_id"]}

    if not is_invitation_acceptable(inv["status"], inv["expires_at"]):
        raise HTTPException(status_code=410, detail="Cette invitation n'est plus valide")

    supabase.table("project_members").insert(
        {
            "monument_id": inv["monument_id"],
            "user_id": user_id,
            "role": "member",
            "invited_by": inv["invited_by"],
        }
    ).execute()
    supabase.table("project_invitations").update(
        {
            "status": "accepted",
            "accepted_at": datetime.now(UTC).isoformat(),
            "accepted_by": user_id,
        }
    ).eq("id", inv["id"]).execute()

    accepter = (
        supabase.table("users").select("prenom, nom").eq("id", user_id).maybe_single().execute()
    )
    nom = (
        f"{accepter.data['prenom']} {accepter.data['nom']}"
        if accepter and accepter.data
        else "Un collaborateur"
    )
    with contextlib.suppress(Exception):
        supabase.table("notifications").insert(
            {
                "user_id": inv["invited_by"],
                "type": "info",
                "categorie": "collaborateur",
                "titre": "Nouveau membre",
                "message": f"{nom} a rejoint votre projet.",
            }
        ).execute()

    return {"monument_id": inv["monument_id"]}
