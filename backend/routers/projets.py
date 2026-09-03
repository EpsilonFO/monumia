"""Projets de travaux — les chantiers d'un monument.

Un monument porte N projets. Chacun a son cadrage (`travaux_envisages`), son
questionnaire, sa clôture, sa propre équipe et ses propres documents ; le
monument garde ce qui décrit le bien (protection, propriétaire, état sanitaire)
et porte le paywall.

Toute réponse porte `my_role` : le rôle EFFECTIF de l'appelant sur ce projet
(cf. `get_projet_role`), et non son rôle sur le monument. C'est lui que le front
consulte — un collaborateur invité sur le seul chantier n'a aucun rôle sur le
monument, mais bien un rôle ici.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase
from services import quotas
from services.project_access import (
    get_projet_role,
    projet_role_depuis,
    projet_roles_propres,
    require_monument_read,
    require_project_access,
    require_projet_access,
)

# Router sans prefix : ses routes vivent sous deux racines (`/monuments/{id}/projets`
# pour la collection, `/projets/{id}` pour l'unité), les chemins sont donc complets.
router = APIRouter(tags=["projets"])

COLUMNS = "*"


class CreateProjetRequest(BaseModel):
    titre: str | None = None
    # Liste vide AUTORISÉE : c'est l'option « Pas encore déterminé » du wizard.
    # Le hard_filter travaux du moteur est fail-open sur liste vide — exiger au
    # moins un type masquerait des aides faute de donnée.
    travauxEnvisages: list[str] = []
    questionnaire: dict | None = None


class UpdateProjetRequest(BaseModel):
    titre: str | None = None
    travauxEnvisages: list[str] | None = None
    questionnaire: dict | None = None


def _row_from(body: CreateProjetRequest | UpdateProjetRequest) -> dict:
    """Corps de requête → colonnes. Jamais de `user_id` : il est immuable
    (trigger `lock_owner`), un PATCH qui le porterait ferait échouer l'update."""
    data = body.model_dump(exclude_none=True)
    row: dict = {}
    if "titre" in data:
        row["titre"] = data["titre"]
    if "travauxEnvisages" in data:
        row["travaux_envisages"] = data["travauxEnvisages"]
    if "questionnaire" in data:
        row["questionnaire"] = data["questionnaire"]
    return row


@router.get("/monuments/{monument_id}/projets")
def list_projets(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Les projets du monument que l'appelant a le droit de voir.

    L'équipe du monument les voit tous. Un collaborateur invité sur un seul
    chantier ne voit que le sien : le filtre est posé ICI, côté serveur — masquer
    les autres à l'affichage laisserait fuiter leur existence dans la réponse.
    """
    monument_role = require_monument_read(supabase, monument_id, user_id)
    # Deux requêtes en tout, quel que soit le nombre de projets : le rôle sur le
    # monument vaut pour tous, et les appartenances propres tiennent en une lecture.
    roles_propres = projet_roles_propres(supabase, user_id)

    query = supabase.table("projets").select(COLUMNS).eq("monument_id", monument_id)
    if monument_role is None:
        if not roles_propres:
            return []
        query = query.in_("id", list(roles_propres))

    rows = query.order("created_at", desc=True).execute().data or []
    for row in rows:
        row["my_role"] = projet_role_depuis(row, monument_role, roles_propres, user_id)
    return rows


@router.post("/monuments/{monument_id}/projets", status_code=status.HTTP_201_CREATED)
def create_projet(
    monument_id: str,
    body: CreateProjetRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_project_access(supabase, monument_id, user_id, "co_owner")
    # Plafond de projets de l'offre qui gouverne le bien. Avant l'insertion :
    # un projet créé puis refusé laisserait un chantier fantôme.
    quotas.verifier_creation_projet(supabase, monument_id, user_id)
    row = {
        **_row_from(body),
        "monument_id": monument_id,
        "user_id": user_id,
        # `travaux_envisages` est NOT NULL : exclude_none l'aurait laissé de côté
        # si le client ne l'envoie pas, la valeur par défaut du modèle le pose.
        "travaux_envisages": body.travauxEnvisages,
    }
    result = supabase.table("projets").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Échec de la création du projet")
    # Le créateur est co_owner du chantier via son rôle sur le monument : pas de
    # ligne `projet_members` à poser, `get_projet_role` la déduit.
    created = result.data[0]
    created["my_role"] = get_projet_role(supabase, created, user_id)
    return created


@router.get("/projets/{projet_id}")
def get_projet(
    projet_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    projet, role = require_projet_access(supabase, projet_id, user_id, "member")
    projet["my_role"] = role
    return projet


@router.patch("/projets/{projet_id}")
def update_projet(
    projet_id: str,
    body: UpdateProjetRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    projet, role = require_projet_access(supabase, projet_id, user_id, "co_owner")
    updates = _row_from(body)
    if not updates:
        projet["my_role"] = role
        return projet
    result = supabase.table("projets").update(updates).eq("id", projet_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    updated = result.data[0]
    updated["my_role"] = role
    return updated


@router.delete("/projets/{projet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_projet(
    projet_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    projet, _ = require_projet_access(supabase, projet_id, user_id, "co_owner")
    quotas.verifier_suppression_projet(supabase, projet["monument_id"], user_id)
    # Les dossiers et suivis du projet tombent en cascade (FK on delete cascade).
    supabase.table("projets").delete().eq("id", projet_id).execute()


@router.post("/projets/{projet_id}/cloture")
def cloturer_projet(
    projet_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _, role = require_projet_access(supabase, projet_id, user_id, "co_owner")
    result = (
        supabase.table("projets")
        .update({"cloture_at": datetime.now(UTC).isoformat()})
        .eq("id", projet_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    return {**result.data[0], "my_role": role}


@router.post("/projets/{projet_id}/reouverture")
def rouvrir_projet(
    projet_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _, role = require_projet_access(supabase, projet_id, user_id, "co_owner")
    result = supabase.table("projets").update({"cloture_at": None}).eq("id", projet_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    return {**result.data[0], "my_role": role}
