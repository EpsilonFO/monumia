from fastapi import APIRouter, Depends, Query
from supabase import Client

from db import get_current_user_id, get_supabase

router = APIRouter(prefix="/templates", tags=["templates"])

# Map DB snake_case columns → frontend camelCase keys
_TEMPLATE_KEY_MAP = {
    "type_document": "typeDocument",
    "categories_aide": "categoriesAide",
    "fichier_url": "fichierUrl",
    "nom_fichier": "nomFichier",
    "mime_type": "mimeType",
    "taille_fichier": "tailleFichier",
    "source_url": "sourceUrl",
    "created_at": "createdAt",
    "updated_at": "updatedAt",
}


def _to_camel(row: dict) -> dict:
    """Convert a DB template row (snake_case) to frontend shape (camelCase)."""
    return {_TEMPLATE_KEY_MAP.get(k, k): v for k, v in row.items()}


@router.get("")
def list_templates(
    categorie: str | None = Query(None),
    type: str | None = Query(None),
    _user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """List the Monumia template library.

    Fine-grained filtering and full-text search are done client-side (the
    dataset is small and referential); we expose a couple of cheap server
    filters for convenience.
    """
    query = supabase.table("templates").select("*").order("nom")

    if type:
        query = query.eq("type_document", type)
    if categorie:
        # Templates tagged with this aide category OR generic (no category).
        query = query.contains("categories_aide", [categorie])

    rows = query.execute().data or []
    return [_to_camel(r) for r in rows]
