import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase

router = APIRouter(prefix="/monuments", tags=["monuments"])

COLUMNS = "*"


def _to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _snake_row(data: dict) -> dict:
    """Recursively convert all dict keys from camelCase to snake_case."""
    return {_to_snake(k): v for k, v in data.items()}


def _normalize_commune(name: str) -> str:
    """Lowercase and strip accents from a commune name."""
    nfkd = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return without_accents.lower()


def _validate_photo_storage_path(path: str, user_id: str) -> str:
    """Photo URLs are storage paths scoped to the caller's folder.

    The frontend uploads photos to the same private "documents" bucket under
    "<user_id>/...". Reject anything else so a tampered client can't reference
    another user's storage objects.
    """
    if not path or not isinstance(path, str):
        raise HTTPException(status_code=400, detail="URL de photo invalide")
    if "://" in path or path.startswith("/") or ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="URL de photo invalide")
    if not path.startswith(f"{user_id}/"):
        raise HTTPException(status_code=403, detail="URL de photo non autorisée")
    return path


def _try_resolve_code_insee(
    supabase: Client,
    commune_name: str | None,
    historical_code: str | None = None,
) -> str | None:
    """Resolve a commune to a currently-active code_insee, or None if unresolvable.

    Cascade:
      1. If historical_code is an active commune, use it.
      2. If historical_code maps to a current commune via communes_historique, use that.
      3. Match commune_name against communes.nom_commune_matching.
    """
    if historical_code:
        direct = (
            supabase.table("communes")
            .select("code_insee")
            .eq("code_insee", historical_code)
            .limit(1)
            .execute()
        )
        if direct.data:
            return direct.data[0]["code_insee"]

        mapped = (
            supabase.table("communes_historique")
            .select("nouveau_code_insee")
            .eq("ancien_code_insee", historical_code)
            .limit(1)
            .execute()
        )
        if mapped.data:
            return mapped.data[0]["nouveau_code_insee"]

    if commune_name:
        normalized = _normalize_commune(commune_name)
        by_name = (
            supabase.table("communes")
            .select("code_insee")
            .eq("nom_commune_matching", normalized)
            .limit(1)
            .execute()
        )
        if by_name.data:
            return by_name.data[0]["code_insee"]

    return None


def _resolve_code_insee(
    supabase: Client,
    commune_name: str,
    historical_code: str | None = None,
) -> str:
    """Resolve a commune name to a current code_insee, or raise 400."""
    code = _try_resolve_code_insee(supabase, commune_name, historical_code)
    if code is None:
        raise HTTPException(
            status_code=400,
            detail=f"Commune introuvable : '{commune_name}'",
        )
    return code


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MonumentPhoto(BaseModel):
    id: str
    url: str
    legende: str
    type: str  # 'facade' | 'interieur' | 'detail' | 'aerien' | 'degradation' | 'autre'
    datePhoto: str | None = None


class CreateMonumentRequest(BaseModel):
    # NOTE: only fields backed by a real `monuments` column belong here. Ten
    # per-attribute columns (affectataire, periode_construction, superficie,
    # materiaux, type_couverture, nombre_niveaux, urgence_travaux,
    # diagnostic_realise, derniers_travaux, description_etat) were dropped by
    # migration 20260516174303 and now live inside the `questionnaire` JSONB.
    # Pydantic ignores any such extra keys the client still sends, so they never
    # reach the insert (which PostgREST would otherwise reject with PGRST204).
    nom: str
    commune: str  # Used to resolve code_insee, not stored in DB
    codeInsee: str | None = None
    referenceMerimee: str | None = None

    protection: str
    dateProtection: str | None = None
    typeProtection: str | None = None
    proprietaire: str

    siecleConstruction: str | None = None
    descriptionGenerale: str | None = None

    etatConservation: str
    travauxEnvisages: list[str] | None = None

    questionnaire: dict | None = None


class UpdateMonumentRequest(BaseModel):
    # See CreateMonumentRequest: fields must map to a real `monuments` column.
    # The dropped per-attribute columns (and `adresse`, which never existed) are
    # intentionally absent; extra keys from the client are ignored.
    nom: str | None = None
    commune: str | None = None  # Used to resolve code_insee, not stored in DB
    codeInsee: str | None = None
    referenceMerimee: str | None = None

    protection: str | None = None
    dateProtection: str | None = None
    typeProtection: str | None = None
    proprietaire: str | None = None

    siecleConstruction: str | None = None
    descriptionGenerale: str | None = None

    etatConservation: str | None = None
    travauxEnvisages: list[str] | None = None
    completionPercentage: int | None = None

    questionnaire: dict | None = None


class AddPhotoRequest(BaseModel):
    url: str
    legende: str
    type: str
    datePhoto: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enrich_monument(supabase: Client, monument: dict) -> dict:
    """Join commune data (commune, departement, region) via code_insee.

    `region` is stored as the kebab-case code (e.g. "ile-de-france") so it
    matches both `aides_v2.regions` (used by the SQL pre-filter) and the
    frontend `Region` type. The INSEE display label (e.g. "Île-de-France")
    is exposed separately as `region_label`.
    """
    code_insee = monument.get("code_insee")
    if not code_insee:
        return monument

    result = (
        supabase.table("communes")
        .select("nom_commune, departement, departement_num, region, region_code")
        .eq("code_insee", code_insee)
        .limit(1)
        .execute()
    )
    if result.data:
        row = result.data[0]
        monument["commune"] = row["nom_commune"]
        monument["departement"] = row["departement"]
        monument["departement_num"] = row["departement_num"]
        monument["region"] = row.get("region_code")
        monument["region_label"] = row.get("region")
    return monument


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
    return _enrich_monument(supabase, result.data)


def _compute_completion(monument: dict) -> int:
    """Recompute completionPercentage based on filled fields."""
    steps = [
        # Step 1 — Identification
        all(
            [
                monument.get("nom"),
                monument.get("code_insee"),
            ]
        ),
        # Step 2 — Legal
        all([monument.get("protection"), monument.get("proprietaire")]),
        # Step 3 — Physical
        any(
            [
                monument.get("siecle_construction"),
                monument.get("description_generale"),
            ]
        ),
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

    # Batch-enrich with commune data
    monuments = result.data or []
    code_insees = list({m["code_insee"] for m in monuments if m.get("code_insee")})
    if code_insees:
        communes_result = (
            supabase.table("communes")
            .select("code_insee, nom_commune, departement, departement_num, region, region_code")
            .in_("code_insee", code_insees)
            .execute()
        )
        communes_by_code = {c["code_insee"]: c for c in (communes_result.data or [])}
        for m in monuments:
            commune_data = communes_by_code.get(m.get("code_insee"))
            if commune_data:
                m["commune"] = commune_data["nom_commune"]
                m["departement"] = commune_data["departement"]
                m["departement_num"] = commune_data["departement_num"]
                m["region"] = commune_data.get("region_code")
                m["region_label"] = commune_data.get("region")

    return monuments


@router.post("", status_code=status.HTTP_201_CREATED)
def create_monument(
    body: CreateMonumentRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    data = _snake_row(body.model_dump(exclude_none=True))

    # Resolve code_insee from commune name, falling back to the historical INSEE
    # code (e.g. Mérimée's cog_insee_lors_de_la_protection) via communes_historique.
    data["code_insee"] = _resolve_code_insee(supabase, body.commune, historical_code=body.codeInsee)

    # Remove fields not stored in monuments table
    for key in ("commune", "departement", "region", "coordonnees"):
        data.pop(key, None)

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
    supabase.table("monuments").update({"completion_percentage": pct}).eq(
        "id", monument["id"]
    ).execute()
    monument["completion_percentage"] = pct

    return _enrich_monument(supabase, monument)


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

    # Re-resolve code_insee when commune changes
    if body.commune is not None:
        updates["code_insee"] = _resolve_code_insee(
            supabase, body.commune, historical_code=body.codeInsee
        )

    # Remove fields not stored in monuments table
    for key in ("commune", "departement", "region", "coordonnees"):
        updates.pop(key, None)

    if not updates:
        return _get_monument_or_404(supabase, monument_id, user_id)

    result = supabase.table("monuments").update(updates).eq("id", monument_id).execute()
    monument = result.data[0]

    # Recompute completion
    pct = _compute_completion(monument)
    supabase.table("monuments").update({"completion_percentage": pct}).eq(
        "id", monument_id
    ).execute()
    monument["completion_percentage"] = pct

    return _enrich_monument(supabase, monument)


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

    safe_url = _validate_photo_storage_path(body.url, user_id)

    import uuid

    new_photo = {
        "id": str(uuid.uuid4()),
        "url": safe_url,
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
