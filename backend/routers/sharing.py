"""Partage d'un monument : membres et invitations.

L'équipe se constitue au niveau du MONUMENT et vaut pour tous ses projets de
travaux — un projet n'a pas de partage propre.
"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from supabase import Client

from config import request_app_origin
from db import get_current_user_id, get_supabase
from services import quotas
from services.email_service import date_fr, send_invitation_email
from services.invitations import generate_invite_token, invitation_expiry_iso
from services.project_access import require_project_access

router = APIRouter(prefix="/projects", tags=["sharing"])


class InviteRequest(BaseModel):
    email: str
    message: str | None = None


def _member_out(member: dict, profile: dict | None) -> dict:
    profile = profile or {}
    return {
        "user_id": member["user_id"],
        "role": member["role"],
        "prenom": profile.get("prenom", ""),
        "nom": profile.get("nom", ""),
        "email": profile.get("email", ""),
        "metier": profile.get("metier"),
        "telephone": profile.get("telephone"),
        "joined_at": member["joined_at"],
    }


def _monument_or_404(supabase: Client, monument_id: str) -> dict:
    res = (
        supabase.table("monuments")
        .select("id, nom, user_id")
        .eq("id", monument_id)
        .maybe_single()
        .execute()
    )
    if not res or not res.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    return res.data


@router.get("/{monument_id}/members")
def list_members(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "member")

    members = (
        supabase.table("project_members").select("*").eq("monument_id", monument_id).execute().data
    )
    user_ids = [m["user_id"] for m in members]
    profiles = {}
    if user_ids:
        rows = (
            supabase.table("users")
            .select("id, prenom, nom, email, metier, telephone")
            .in_("id", user_ids)
            .execute()
            .data
        )
        profiles = {r["id"]: r for r in rows}

    invitations = (
        supabase.table("project_invitations")
        .select("id, email, status, created_at, expires_at")
        .eq("monument_id", monument_id)
        .eq("status", "pending")
        .execute()
        .data
    )
    return {
        "members": [_member_out(m, profiles.get(m["user_id"])) for m in members],
        "invitations": invitations,
    }


@router.post("/{monument_id}/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(
    monument_id: str,
    body: InviteRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "co_owner")
    quotas.verifier_invitation(supabase, monument_id, user_id)
    monument = _monument_or_404(supabase, monument_id)
    email = body.email.strip().lower()

    existing_user = supabase.table("users").select("id").eq("email", email).maybe_single().execute()
    if existing_user and existing_user.data:
        already = (
            supabase.table("project_members")
            .select("id")
            .eq("monument_id", monument_id)
            .eq("user_id", existing_user.data["id"])
            .execute()
        )
        if already.data:
            raise HTTPException(
                status_code=409, detail="Cette personne est déjà membre de ce monument"
            )

    token = generate_invite_token()
    expires_at = invitation_expiry_iso(datetime.now(UTC))
    row = {
        "monument_id": monument_id,
        "email": email,
        "token": token,
        "invited_by": user_id,
        "status": "pending",
        "expires_at": expires_at,
    }
    supabase.table("project_invitations").delete().eq("monument_id", monument_id).eq(
        "email", email
    ).neq("status", "accepted").execute()
    created = supabase.table("project_invitations").insert(row).execute().data[0]

    inviter = (
        supabase.table("users")
        .select("prenom, nom, email")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    inviter_nom = (
        f"{inviter.data['prenom']} {inviter.data['nom']}"
        if inviter and inviter.data
        else "Un membre"
    )
    # Le lien suit l'environnement d'où part l'invitation : envoyée depuis la
    # beta, elle renvoie sur la beta — sinon le destinataire atterrit en
    # production, où le jeton n'existe pas (« Invitation introuvable »).
    send_invitation_email(
        to_email=email,
        inviter_nom=inviter_nom,
        monument_nom=monument["nom"],
        invite_url=f"{request_app_origin(request)}/invitation/{token}",
        expires_label=date_fr(date.fromisoformat(expires_at[:10])),
        inviter_email=inviter.data.get("email") if inviter and inviter.data else None,
    )
    return {
        "id": created["id"],
        "email": created["email"],
        "status": created["status"],
        "created_at": created["created_at"],
        "expires_at": created["expires_at"],
    }


@router.delete("/{monument_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    monument_id: str,
    invitation_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "co_owner")
    supabase.table("project_invitations").update({"status": "revoked"}).eq("id", invitation_id).eq(
        "monument_id", monument_id
    ).execute()


@router.post("/{monument_id}/members/{target_user_id}/promote")
def promote_member(
    monument_id: str,
    target_user_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "co_owner")
    target_role = _require_target_member(supabase, monument_id, target_user_id)
    if target_role == "owner":
        raise HTTPException(status_code=403, detail="Impossible de modifier le chef de projet")
    supabase.table("project_members").update({"role": "co_owner"}).eq(
        "monument_id", monument_id
    ).eq("user_id", target_user_id).execute()
    return _fetch_member(supabase, monument_id, target_user_id)


@router.post("/{monument_id}/members/{target_user_id}/demote")
def demote_member(
    monument_id: str,
    target_user_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "co_owner")
    target_role = _require_target_member(supabase, monument_id, target_user_id)
    if target_role == "owner":
        raise HTTPException(status_code=403, detail="Impossible de modifier le chef de projet")
    supabase.table("project_members").update({"role": "member"}).eq("monument_id", monument_id).eq(
        "user_id", target_user_id
    ).execute()
    return _fetch_member(supabase, monument_id, target_user_id)


@router.delete("/{monument_id}/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    monument_id: str,
    target_user_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "co_owner")
    target_role = _require_target_member(supabase, monument_id, target_user_id)
    if target_role == "owner":
        raise HTTPException(status_code=403, detail="Impossible de retirer le chef de projet")
    supabase.table("project_members").delete().eq("monument_id", monument_id).eq(
        "user_id", target_user_id
    ).execute()


@router.post("/{monument_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_project(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    role = require_project_access(supabase, monument_id, user_id, "member")
    if role == "owner":
        raise HTTPException(
            status_code=403,
            detail="Le chef de projet ne peut pas quitter le monument ; supprimez-le.",
        )
    supabase.table("project_members").delete().eq("monument_id", monument_id).eq(
        "user_id", user_id
    ).execute()


def _require_target_member(supabase: Client, monument_id: str, target_user_id: str) -> str:
    res = (
        supabase.table("project_members")
        .select("role")
        .eq("monument_id", monument_id)
        .eq("user_id", target_user_id)
        .maybe_single()
        .execute()
    )
    if not res or not res.data:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    return res.data["role"]


def _fetch_member(supabase: Client, monument_id: str, target_user_id: str) -> dict:
    member = (
        supabase.table("project_members")
        .select("*")
        .eq("monument_id", monument_id)
        .eq("user_id", target_user_id)
        .single()
        .execute()
        .data
    )
    profile = (
        supabase.table("users")
        .select("id, prenom, nom, email, metier, telephone")
        .eq("id", target_user_id)
        .maybe_single()
        .execute()
    )
    return _member_out(member, profile.data if profile else None)
