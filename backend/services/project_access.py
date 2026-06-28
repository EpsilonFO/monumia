"""Contrôle d'accès aux projets partagés (monuments).

Les fonctions `role_at_least` et `can_delete_document` sont PURES (testées
unitairement). `get_project_role` et `require_project_access` font la requête
Supabase et s'appuient dessus.
"""

from fastapi import HTTPException
from supabase import Client

Role = str  # "owner" | "co_owner" | "member"

_ROLE_RANK: dict[str, int] = {"member": 1, "co_owner": 2, "owner": 3}


def role_at_least(role: Role | None, minimum: Role) -> bool:
    """True si `role` est au moins aussi élevé que `minimum` dans la hiérarchie."""
    if role is None:
        return False
    return _ROLE_RANK.get(role, 0) >= _ROLE_RANK[minimum]


def can_delete_document(role: Role | None, *, is_uploader: bool) -> bool:
    """Un document est supprimable par son auteur, ou par un owner/co_owner."""
    if is_uploader:
        return True
    return role_at_least(role, "co_owner")


def can_view_document(
    *,
    visibility: str,
    allowed_user_ids: list[str],
    uploader_id: str | None,
    viewer_id: str,
    viewer_role: Role | None,
) -> bool:
    """Qui peut consulter un document.

    L'auteur et le chef de projet (owner) voient toujours. Un non-membre ne voit
    jamais (hormis auteur/owner). Sinon, selon la visibilité : 'team' → tout
    membre ; 'responsables' → owner/co_owner ; 'custom' → uniquement les
    user_id explicitement autorisés (qui doivent rester membres du projet).
    """
    if uploader_id is not None and viewer_id == uploader_id:
        return True
    if viewer_role == "owner":
        return True
    if viewer_role is None:
        return False
    if viewer_id in allowed_user_ids:
        return True
    if visibility == "team":
        return True
    if visibility == "responsables":
        return role_at_least(viewer_role, "co_owner")
    return False


def allowed_visibilities(role: Role | None) -> set[str]:
    """Visibilités qu'un utilisateur de ce rôle a le droit de poser sur un document.

    Un collaborateur ne peut pas rendre un document visible par « toute l'équipe ».
    """
    if role_at_least(role, "co_owner"):
        return {"team", "responsables", "custom"}
    return {"responsables", "custom"}


def can_edit_visibility(role: Role | None, *, is_uploader: bool) -> bool:
    """Changer la visibilité : l'auteur, ou un owner/co_owner du projet."""
    return can_delete_document(role, is_uploader=is_uploader)


def can_modify_document(
    *,
    visibility: str,
    allowed_user_ids: list[str],
    uploader_id: str | None,
    viewer_id: str,
    viewer_role: Role | None,
) -> bool:
    """Modifier / supprimer / déplacer / repartager un document.

    Prérequis ABSOLU : pouvoir le consulter. Un adjoint (co_owner) exclu d'un
    document « personnes choisies » ne peut donc rien en faire — ni le voir, ni
    le supprimer, ni le remplacer. Pour qui peut le voir, les droits sont ceux
    de la suppression : l'auteur, ou un owner/co_owner du projet.
    """
    if not can_view_document(
        visibility=visibility,
        allowed_user_ids=allowed_user_ids,
        uploader_id=uploader_id,
        viewer_id=viewer_id,
        viewer_role=viewer_role,
    ):
        return False
    is_uploader = uploader_id is not None and viewer_id == uploader_id
    return can_delete_document(viewer_role, is_uploader=is_uploader)


def get_project_role(supabase: Client, monument_id: str, user_id: str) -> Role | None:
    """Rôle de l'utilisateur sur le projet, ou None s'il n'est pas membre."""
    result = (
        supabase.table("project_members")
        .select("role")
        .eq("monument_id", monument_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if result and result.data:
        return result.data["role"]

    # Défense en profondeur : le `user_id` du monument est le propriétaire
    # authoritatif et immuable (cf. trigger prevent_owner_change). Même si la ligne
    # d'appartenance 'owner' manque (donnée non rétro-remplie, création hors flux
    # normal…), le propriétaire ne doit jamais perdre l'accès à SON projet.
    owner = (
        supabase.table("monuments")
        .select("id")
        .eq("id", monument_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if owner and owner.data:
        return "owner"
    return None


def require_project_access(
    supabase: Client, monument_id: str, user_id: str, minimum: Role = "member"
) -> Role:
    """Vérifie l'accès et renvoie le rôle, sinon lève 403/404."""
    role = get_project_role(supabase, monument_id, user_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Projet introuvable ou accès refusé")
    if not role_at_least(role, minimum):
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
    return role
