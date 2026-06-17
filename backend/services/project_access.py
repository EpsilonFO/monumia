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
