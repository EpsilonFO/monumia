import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase

router = APIRouter(prefix="/monuments", tags=["monuments"])

COLUMNS = "*"


def _to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def _snake_row(data: dict) -> dict:
    """Recursively convert all dict keys from camelCase to snake_case."""
    return {_to_snake(k): v for k, v in data.items()}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class Coordonnees(BaseModel):
    lat: float
    lng: float


class MonumentPhoto(BaseModel):
    id: str
    url: str
    legende: str
    type: str  # 'facade' | 'interieur' | 'detail' | 'aerien' | 'degradation' | 'autre'
    datePhoto: str | None = None


class CreateMonumentRequest(BaseModel):
    nom: str
    denomination: str
    codePostal: str | None = None
    commune: str
    codeInsee: str
    departement: str
    region: str
    referenceMerimee: str | None = None
    coordonnees: Coordonnees | None = None

    protection: str
    dateProtection: str | None = None
    typeProtection: str | None = None
    proprietaire: str
    affectataire: str | None = None

    siecleConstruction: str | None = None
    periodeConstruction: list[str] | None = None
    superficie: float | None = None
    materiaux: list[str] | None = None
    typeCouverture: str | None = None
    nombreNiveaux: int | None = None
    descriptionGenerale: str | None = None

    etatConservation: str
    travauxEnvisages: list[str] | None = None
    urgenceTravaux: str | None = None
    diagnosticRealise: bool | None = None
    derniersTravaux: str | None = None
    descriptionEtat: str | None = None


class UpdateMonumentRequest(BaseModel):
    nom: str | None = None
    denomination: str | None = None
    adresse: str | None = None
    codePostal: str | None = None
    commune: str | None = None
    codeInsee: str | None = None
    departement: str | None = None
    region: str | None = None
    referenceMerimee: str | None = None
    coordonnees: Coordonnees | None = None

    protection: str | None = None
    dateProtection: str | None = None
    typeProtection: str | None = None
    proprietaire: str | None = None
    affectataire: str | None = None

    siecleConstruction: str | None = None
    periodeConstruction: list[str] | None = None
    superficie: float | None = None
    materiaux: list[str] | None = None
    typeCouverture: str | None = None
    nombreNiveaux: int | None = None
    descriptionGenerale: str | None = None

    etatConservation: str | None = None
    travauxEnvisages: list[str] | None = None
    urgenceTravaux: str | None = None
    diagnosticRealise: bool | None = None
    derniersTravaux: str | None = None
    descriptionEtat: str | None = None
    completionPercentage: int | None = None


class AddPhotoRequest(BaseModel):
    url: str
    legende: str
    type: str
    datePhoto: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_monument_or_404(supabase: Client, monument_id: str, user_id: str) -> dict:
    result = (
        supabase.table("monuments")
        .select(COLUMNS)
        .eq("id", monument_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Monument introuvable")
    return result.data


def _compute_completion(monument: dict) -> int:
    """Recompute completionPercentage based on filled fields."""
    steps = [
        # Step 1 — Identification
        all([monument.get("nom"), monument.get("denomination"),
             monument.get("commune"), monument.get("region")]),
        # Step 2 — Legal
        all([monument.get("protection"), monument.get("proprietaire")]),
        # Step 3 — Physical
        any([monument.get("siecle_construction"), monument.get("superficie"),
             monument.get("description_generale")]),
        # Step 4 — State
        bool(monument.get("etat_conservation")),
        # Step 5 — Photos
        bool(monument.get("photos")),
    ]
    return int(sum(steps) / len(steps) * 100)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def list_monuments(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    result = (
        supabase.table("monuments")
        .select(COLUMNS)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.post("", status_code=status.HTTP_201_CREATED)
def create_monument(
    body: CreateMonumentRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    data = _snake_row(body.model_dump(exclude_none=True))

    row = {
        **data,
        "user_id": user_id,
        "photos": [],
        "completion_percentage": 0,
    }

    result = supabase.table("monuments").insert(row).execute()
    monument = result.data[0]

    # Compute and persist completion
    pct = _compute_completion(monument)
    supabase.table("monuments").update({"completion_percentage": pct}).eq("id", monument["id"]).execute()
    monument["completion_percentage"] = pct

    return monument


@router.get("/{monument_id}")
def get_monument(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    return _get_monument_or_404(supabase, monument_id, user_id)


@router.patch("/{monument_id}")
def update_monument(
    monument_id: str,
    body: UpdateMonumentRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _get_monument_or_404(supabase, monument_id, user_id)

    updates = _snake_row(body.model_dump(exclude_none=True))
    if not updates:
        return _get_monument_or_404(supabase, monument_id, user_id)

    result = supabase.table("monuments").update(updates).eq("id", monument_id).execute()
    monument = result.data[0]

    # Recompute completion
    pct = _compute_completion(monument)
    supabase.table("monuments").update({"completion_percentage": pct}).eq("id", monument_id).execute()
    monument["completion_percentage"] = pct

    return monument


@router.delete("/{monument_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_monument(
    monument_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _get_monument_or_404(supabase, monument_id, user_id)
    supabase.table("monuments").delete().eq("id", monument_id).execute()


@router.post("/{monument_id}/photos", status_code=status.HTTP_201_CREATED)
def add_photo(
    monument_id: str,
    body: AddPhotoRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    monument = _get_monument_or_404(supabase, monument_id, user_id)

    import uuid
    new_photo = {
        "id": str(uuid.uuid4()),
        "url": body.url,
        "legende": body.legende,
        "type": body.type,
        **({"datePhoto": body.datePhoto} if body.datePhoto else {}),
    }

    photos: list = monument.get("photos") or []
    photos.append(new_photo)

    supabase.table("monuments").update({"photos": photos}).eq("id", monument_id).execute()
    return new_photo


@router.delete("/{monument_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_photo(
    monument_id: str,
    photo_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    monument = _get_monument_or_404(supabase, monument_id, user_id)

    photos: list = monument.get("photos") or []
    updated = [p for p in photos if p["id"] != photo_id]

    if len(updated) == len(photos):
        raise HTTPException(status_code=404, detail="Photo introuvable")

    supabase.table("monuments").update({"photos": updated}).eq("id", monument_id).execute()
