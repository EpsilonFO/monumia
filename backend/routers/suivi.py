"""Suivi du statut des aides d'un PROJET de travaux.

Le suivi vit au grain projet depuis l'inversion de hiérarchie : deux chantiers
d'un même monument peuvent candidater à la même aide et avoir chacun leur
avancement. `monument_id` reste écrit sur la ligne (dénormalisé) pour les
gardes et les requêtes batch du dashboard.

La clôture du projet a déménagé dans `routers/projets.py`, avec le reste du
cycle de vie d'un projet.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase
from services import aides_fermees
from services.project_access import require_projet_access
from services.suivi_service import SuiviValidationError, apply_statut_change

router = APIRouter(prefix="/projets", tags=["suivi"])


class UpsertSuiviRequest(BaseModel):
    statut: str
    montant_obtenu: float | None = None
    motif_refus_code: str | None = None
    motif_refus_detail: str | None = None
    note: str | None = None


def _assert_dossier_exists(supabase: Client, projet_id: str, aide_id: str) -> None:
    """Le suivi ne vit que là où un dossier existe pour l'aide dans ce projet —
    on refuse de créer/modifier un suivi orphelin (données propres pour analyse).

    Pas de filtre `user_id` : le dossier appartient au projet, pas à celui qui
    l'a créé. Un adjoint doit pouvoir suivre l'aide dont le chef a ouvert le
    dossier — l'accès est déjà tranché par `require_projet_access`.
    """
    result = (
        supabase.table("dossiers")
        .select("id")
        .eq("projet_id", projet_id)
        .eq("aide_id", aide_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=409,
            detail="Aucun dossier pour cette aide ; créez le dossier avant de la suivre.",
        )


@router.get("/{projet_id}/aide-suivis")
def list_aide_suivis(
    projet_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_projet_access(supabase, projet_id, user_id, "member")
    result = supabase.table("aide_suivis").select("*").eq("projet_id", projet_id).execute()
    return aides_fermees.filtrer_suivis(supabase, user_id, result.data or [])


@router.put("/{projet_id}/aides/{aide_id}/suivi")
def upsert_aide_suivi(
    projet_id: str,
    aide_id: str,
    body: UpsertSuiviRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    projet, _ = require_projet_access(supabase, projet_id, user_id, "co_owner")
    _assert_dossier_exists(supabase, projet_id, aide_id)

    existing_result = (
        supabase.table("aide_suivis")
        .select("*")
        .eq("projet_id", projet_id)
        .eq("aide_id", aide_id)
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

    row = {
        **fields,
        "projet_id": projet_id,
        # Dénormalisé : le dashboard charge les suivis par lot de monuments.
        "monument_id": projet["monument_id"],
        "aide_id": aide_id,
        "user_id": user_id,
    }
    result = supabase.table("aide_suivis").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Échec de l'enregistrement du suivi")
    return result.data[0]


@router.delete(
    "/{projet_id}/aides/{aide_id}/suivi",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_aide_suivi(
    projet_id: str,
    aide_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    require_projet_access(supabase, projet_id, user_id, "co_owner")
    supabase.table("aide_suivis").delete().eq("projet_id", projet_id).eq(
        "aide_id", aide_id
    ).execute()
