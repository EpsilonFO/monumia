"""Équipe d'un PROJET de travaux : membres et invitations.

Pendant de `sharing.py`, un cran plus bas. La différence n'est pas cosmétique :
un membre inscrit ici ne voit QUE ce chantier — pas les autres projets du
monument, pas ses documents, pas son équipe. C'est ce qu'on vend quand on
invite un couvreur sur la seule toiture.

L'échelle de rôles n'a que deux barreaux (`co_owner`, `member`) : la propriété
appartient au monument, un projet n'a pas d'`owner` propre. Le chef de projet du
monument est co_owner de chaque chantier sans figurer dans `projet_members` —
d'où la distinction, dans les listes ci-dessous, entre les membres hérités du
monument et ceux invités sur le seul projet.
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
from services.project_access import require_projet_access

router = APIRouter(prefix="/projets", tags=["sharing"])

PROJET_ROLES = ("co_owner", "member")


class InviteRequest(BaseModel):
    email: str
    message: str | None = None


def _member_out(member: dict, profile: dict | None, *, source: str) -> dict:
    """Un membre tel que l'affiche le panneau d'équipe.

    `source` dit d'où vient le droit : « monument » (hérité de l'équipe du bien,
    non modifiable ici) ou « projet » (invité sur ce chantier). Sans ça, l'UI
    proposerait de retirer du chantier quelqu'un qui y accède par le monument —
    un bouton qui ne pourrait rien faire.
    """
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
        "source": source,
    }


def _profiles(supabase: Client, user_ids: list[str]) -> dict[str, dict]:
    if not user_ids:
        return {}
    rows = (
        supabase.table("users")
        .select("id, prenom, nom, email, metier, telephone")
        .in_("id", user_ids)
        .execute()
        .data
    ) or []
    return {r["id"]: r for r in rows}


def _monument_or_404(supabase: Client, monument_id: str) -> dict:
    res = (
        supabase.table("monuments").select("id, nom").eq("id", monument_id).maybe_single().execute()
    )
    if not res or not res.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    return res.data


@router.get("/{projet_id}/members")
def list_members(
    projet_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Qui travaille sur ce chantier : l'équipe du monument, puis les invités du projet."""
    projet, _ = require_projet_access(supabase, projet_id, user_id, "member")

    herites = (
        supabase.table("project_members")
        .select("user_id, role, joined_at")
        .eq("monument_id", projet["monument_id"])
        .execute()
        .data
    ) or []
    propres = (
        supabase.table("projet_members")
        .select("user_id, role, joined_at")
        .eq("projet_id", projet_id)
        .execute()
        .data
    ) or []

    # Quelqu'un peut être dans les deux (membre du monument ET invité ici) : le
    # droit hérité prime pour l'affichage, il est plus large et non révocable ici.
    herites_ids = {m["user_id"] for m in herites}
    propres = [m for m in propres if m["user_id"] not in herites_ids]

    profiles = _profiles(supabase, [m["user_id"] for m in herites + propres])
    invitations = (
        supabase.table("project_invitations")
        .select("id, email, status, created_at, expires_at")
        .eq("projet_id", projet_id)
        .eq("status", "pending")
        .execute()
        .data
    ) or []

    return {
        "members": [
            *(_member_out(m, profiles.get(m["user_id"]), source="monument") for m in herites),
            *(_member_out(m, profiles.get(m["user_id"]), source="projet") for m in propres),
        ],
        "invitations": invitations,
    }


@router.post("/{projet_id}/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(
    projet_id: str,
    body: InviteRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    projet, _ = require_projet_access(supabase, projet_id, user_id, "co_owner")
    quotas.verifier_invitation(supabase, projet["monument_id"], user_id)
    monument = _monument_or_404(supabase, projet["monument_id"])
    email = body.email.strip().lower()

    existing_user = supabase.table("users").select("id").eq("email", email).maybe_single().execute()
    if existing_user and existing_user.data:
        cible = existing_user.data["id"]
        deja_projet = (
            supabase.table("projet_members")
            .select("id")
            .eq("projet_id", projet_id)
            .eq("user_id", cible)
            .execute()
        )
        if deja_projet.data:
            raise HTTPException(
                status_code=409, detail="Cette personne est déjà membre de ce projet"
            )
        # Membre du monument : elle a DÉJÀ accès à ce chantier. L'inviter ici ne
        # lui ajouterait rien et créerait une ligne trompeuse.
        deja_monument = (
            supabase.table("project_members")
            .select("id")
            .eq("monument_id", projet["monument_id"])
            .eq("user_id", cible)
            .execute()
        )
        if deja_monument.data:
            raise HTTPException(
                status_code=409,
                detail="Cette personne fait partie de l'équipe du monument : "
                "elle a déjà accès à ce projet.",
            )

    token = generate_invite_token()
    expires_at = invitation_expiry_iso(datetime.now(UTC))
    supabase.table("project_invitations").delete().eq("projet_id", projet_id).eq(
        "email", email
    ).neq("status", "accepted").execute()
    created = (
        supabase.table("project_invitations")
        .insert(
            {
                # `monument_id` reste renseigné : il nomme le bien dans l'e-mail
                # et sur la page d'acceptation, qui n'est pas authentifiée.
                "monument_id": projet["monument_id"],
                "projet_id": projet_id,
                "email": email,
                "token": token,
                "invited_by": user_id,
                "status": "pending",
                "expires_at": expires_at,
            }
        )
        .execute()
        .data[0]
    )

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
    send_invitation_email(
        to_email=email,
        inviter_nom=inviter_nom,
        monument_nom=monument["nom"],
        invite_url=f"{request_app_origin(request)}/invitation/{token}",
        expires_label=date_fr(date.fromisoformat(expires_at[:10])),
        inviter_email=inviter.data.get("email") if inviter and inviter.data else None,
        projet_titre=projet.get("titre"),
    )
    return {
        "id": created["id"],
        "email": created["email"],
        "status": created["status"],
        "created_at": created["created_at"],
        "expires_at": created["expires_at"],
    }


@router.delete("/{projet_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    projet_id: str,
    invitation_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_projet_access(supabase, projet_id, user_id, "co_owner")
    supabase.table("project_invitations").update({"status": "revoked"}).eq("id", invitation_id).eq(
        "projet_id", projet_id
    ).execute()


def _require_target_projet_member(supabase: Client, projet_id: str, target_user_id: str) -> str:
    """Le membre visé doit avoir une appartenance PROPRE au projet.

    Un membre hérité du monument n'est pas modifiable ici : son droit vient d'un
    cran au-dessus, et le retirer du chantier ne le lui ôterait pas.
    """
    res = (
        supabase.table("projet_members")
        .select("role")
        .eq("projet_id", projet_id)
        .eq("user_id", target_user_id)
        .maybe_single()
        .execute()
    )
    if not res or not res.data:
        raise HTTPException(
            status_code=404,
            detail="Cette personne n'a pas d'accès propre à ce projet ; "
            "son rôle se gère depuis l'équipe du monument.",
        )
    return res.data["role"]


def _fetch_member(supabase: Client, projet_id: str, target_user_id: str) -> dict:
    member = (
        supabase.table("projet_members")
        .select("user_id, role, joined_at")
        .eq("projet_id", projet_id)
        .eq("user_id", target_user_id)
        .single()
        .execute()
        .data
    )
    return _member_out(
        member, _profiles(supabase, [target_user_id]).get(target_user_id), source="projet"
    )


@router.post("/{projet_id}/members/{target_user_id}/promote")
def promote_member(
    projet_id: str,
    target_user_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_projet_access(supabase, projet_id, user_id, "co_owner")
    _require_target_projet_member(supabase, projet_id, target_user_id)
    supabase.table("projet_members").update({"role": "co_owner"}).eq("projet_id", projet_id).eq(
        "user_id", target_user_id
    ).execute()
    return _fetch_member(supabase, projet_id, target_user_id)


@router.post("/{projet_id}/members/{target_user_id}/demote")
def demote_member(
    projet_id: str,
    target_user_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_projet_access(supabase, projet_id, user_id, "co_owner")
    _require_target_projet_member(supabase, projet_id, target_user_id)
    supabase.table("projet_members").update({"role": "member"}).eq("projet_id", projet_id).eq(
        "user_id", target_user_id
    ).execute()
    return _fetch_member(supabase, projet_id, target_user_id)


@router.delete("/{projet_id}/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    projet_id: str,
    target_user_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_projet_access(supabase, projet_id, user_id, "co_owner")
    _require_target_projet_member(supabase, projet_id, target_user_id)
    supabase.table("projet_members").delete().eq("projet_id", projet_id).eq(
        "user_id", target_user_id
    ).execute()


@router.post("/{projet_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_projet(
    projet_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_projet_access(supabase, projet_id, user_id, "member")
    # Sans ligne propre, l'accès vient du monument : c'est de là qu'il faut partir.
    _require_target_projet_member(supabase, projet_id, user_id)
    supabase.table("projet_members").delete().eq("projet_id", projet_id).eq(
        "user_id", user_id
    ).execute()
