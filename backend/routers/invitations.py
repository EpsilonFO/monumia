"""Aperçu et acceptation d'une invitation par token.

Une invitation vise soit le MONUMENT (`projet_id` nul → `project_members`, accès
à tout le bien), soit UN PROJET de travaux (`projet_id` renseigné →
`projet_members`, accès au seul chantier). Le token ne dit pas laquelle : c'est
la colonne qui tranche, à l'acceptation comme à l'aperçu.
"""

import contextlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from db import get_current_user_id, get_supabase
from services.invitations import invitation_destinee_a, is_invitation_acceptable

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
    """Aperçu non authentifié : nom du monument, invitant, statut."""
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
    # Portée : le destinataire doit savoir avant d'accepter s'il rejoint le
    # monument entier ou un seul chantier.
    projet_titre = None
    if inv.get("projet_id"):
        projet = (
            supabase.table("projets")
            .select("titre, travaux_envisages")
            .eq("id", inv["projet_id"])
            .maybe_single()
            .execute()
        )
        row = (projet.data if projet else None) or {}
        projet_titre = row.get("titre") or "Projet de travaux"

    return {
        "monument_id": inv["monument_id"],
        "projet_id": inv.get("projet_id"),
        "projet_titre": projet_titre,
        "email": inv["email"],
        "monument_nom": monument.data["nom"] if monument and monument.data else "Monument",
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
    """Rattache l'utilisateur connecté, au monument ou au seul projet visé."""
    inv = _invitation_by_token(supabase, token)
    projet_id = inv.get("projet_id")

    # Déjà membre : on ne rejoue pas l'invitation, on renvoie la destination.
    if projet_id:
        already = (
            supabase.table("projet_members")
            .select("id")
            .eq("projet_id", projet_id)
            .eq("user_id", user_id)
            .execute()
        )
    else:
        already = (
            supabase.table("project_members")
            .select("id")
            .eq("monument_id", inv["monument_id"])
            .eq("user_id", user_id)
            .execute()
        )
    if already.data:
        return {"monument_id": inv["monument_id"], "projet_id": projet_id}

    if not is_invitation_acceptable(inv["status"], inv["expires_at"]):
        raise HTTPException(status_code=410, detail="Cette invitation n'est plus valide")

    # Le jeton ne suffit pas : l'invitation n'ouvre l'équipe qu'au compte dont
    # l'adresse est celle à qui elle a été envoyée. Le front prévient avant le
    # clic (même comparaison), ce refus tient la porte s'il est contourné.
    compte = supabase.table("users").select("email").eq("id", user_id).maybe_single().execute()
    email_compte = compte.data.get("email") if compte and compte.data else None
    if not invitation_destinee_a(inv["email"], email_compte):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Cette invitation a été envoyée à {inv['email']}. "
                "Connectez-vous avec cette adresse pour la rejoindre."
            ),
        )

    if projet_id:
        supabase.table("projet_members").insert(
            {
                "projet_id": projet_id,
                "user_id": user_id,
                "role": "member",
                "invited_by": inv["invited_by"],
            }
        ).execute()
    else:
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
                "message": (
                    f"{nom} a rejoint votre projet de travaux."
                    if projet_id
                    else f"{nom} a rejoint votre monument."
                ),
            }
        ).execute()

    return {"monument_id": inv["monument_id"], "projet_id": projet_id}
