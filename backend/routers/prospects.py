from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase

router = APIRouter(prefix="/prospects", tags=["prospects"])

COLUMNS = "*, monuments(*)"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateProspectRequest(BaseModel):
    monument_id: str

    contact_nom: str | None = None
    contact_email: str | None = None
    contact_telephone: str | None = None
    contact_fonction: str | None = None

    statut: str | None = "a_contacter"
    priorite: str | None = "moyenne"
    date_prochain_contact: str | None = None
    notes: str | None = None

    financement_identifie: bool | None = False
    aides_matchees: list[str] | None = None
    total_financement_potentiel: float | None = None
    taux_couverture_estime: float | None = None
    montant_travaux: float | None = None


class UpdateProspectRequest(BaseModel):
    contact_nom: str | None = None
    contact_email: str | None = None
    contact_telephone: str | None = None
    contact_fonction: str | None = None

    priorite: str | None = None
    date_prochain_contact: str | None = None
    notes: str | None = None

    financement_identifie: bool | None = None
    aides_matchees: list[str] | None = None
    total_financement_potentiel: float | None = None
    taux_couverture_estime: float | None = None
    montant_travaux: float | None = None


class UpdateStatutRequest(BaseModel):
    statut: str  # 'a_contacter' | 'contacte' | 'en_discussion' | 'devis_envoye' | 'gagne' | 'perdu'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_prospect_or_404(supabase: Client, prospect_id: str, user_id: str) -> dict:
    result = (
        supabase.table("prospects").select(COLUMNS).eq("id", prospect_id).eq("btp_user_id", user_id).single().execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Prospect introuvable")
    return result.data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
def list_prospects(
    statut: str | None = None,
    priorite: str | None = None,
    q: str | None = None,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    query = supabase.table("prospects").select(COLUMNS).eq("btp_user_id", user_id).order("updated_at", desc=True)
    if statut:
        query = query.eq("statut", statut)
    if priorite:
        query = query.eq("priorite", priorite)

    result = query.execute()
    data = result.data or []

    if q:
        q_lower = q.lower()
        data = [
            p
            for p in data
            if q_lower in (p.get("contact_nom") or "").lower()
            or q_lower in ((p.get("monuments") or {}).get("nom") or "").lower()
            or q_lower in (p.get("commune") or "").lower()
            or q_lower in ((p.get("monuments") or {}).get("proprietaire") or "").lower()
        ]

    return data


@router.post("", status_code=status.HTTP_201_CREATED)
def create_prospect(
    body: CreateProspectRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    row = body.model_dump(exclude_none=True)
    row["btp_user_id"] = user_id
    result = supabase.table("prospects").insert(row).execute()
    return result.data[0]


@router.get("/{prospect_id}")
def get_prospect(
    prospect_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    return _get_prospect_or_404(supabase, prospect_id, user_id)


@router.patch("/{prospect_id}")
def update_prospect(
    prospect_id: str,
    body: UpdateProspectRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _get_prospect_or_404(supabase, prospect_id, user_id)

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _get_prospect_or_404(supabase, prospect_id, user_id)

    result = supabase.table("prospects").update(updates).eq("id", prospect_id).execute()
    return result.data[0]


@router.patch("/{prospect_id}/statut")
def update_statut(
    prospect_id: str,
    body: UpdateStatutRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    valid_statuts = {
        "a_contacter",
        "contacte",
        "en_discussion",
        "devis_envoye",
        "gagne",
        "perdu",
    }
    if body.statut not in valid_statuts:
        raise HTTPException(
            status_code=400,
            detail=f"Statut invalide. Valeurs acceptées: {', '.join(valid_statuts)}",
        )

    _get_prospect_or_404(supabase, prospect_id, user_id)
    result = (
        supabase.table("prospects").update({"statut": body.statut}).eq("id", prospect_id).execute()
    )
    return result.data[0]


@router.delete("/{prospect_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prospect(
    prospect_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _get_prospect_or_404(supabase, prospect_id, user_id)
    supabase.table("prospects").delete().eq("id", prospect_id).execute()
