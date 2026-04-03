
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase

router = APIRouter(prefix="/documents", tags=["documents"])

COLUMNS = "*"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateDocumentRequest(BaseModel):
    nom: str
    nom_fichier: str
    type: str
    tags: list[str] = []
    taille_fichier: int
    mime_type: str
    url: str
    monument_ids: list[str] = []
    # Backward compat: accept single monument_id and convert to monument_ids
    monument_id: str | None = None
    date_document: str | None = None
    description: str | None = None


class UpdateDocumentRequest(BaseModel):
    nom: str | None = None
    type: str | None = None
    tags: list[str] | None = None
    date_document: str | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_document_or_404(supabase: Client, document_id: str, user_id: str) -> dict:
    result = (
        supabase.table("documents")
        .select(COLUMNS)
        .eq("id", document_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Document introuvable")
    return result.data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def list_documents(
    monument_id: str | None = Query(None),
    type: str | None = Query(None),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    query = (
        supabase.table("documents")
        .select(COLUMNS)
        .eq("user_id", user_id)
        .order("date_upload", desc=True)
    )
    if monument_id:
        query = query.contains("monument_ids", [monument_id])
    if type:
        query = query.eq("type", type)

    return query.execute().data


@router.post("", status_code=status.HTTP_201_CREATED)
def create_document(
    body: CreateDocumentRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    # Merge monument_id (single, backward compat) into monument_ids
    monument_ids = list(body.monument_ids)
    if body.monument_id and body.monument_id not in monument_ids:
        monument_ids.append(body.monument_id)

    # Validate monument ownership for all referenced monuments
    for mid in monument_ids:
        check = (
            supabase.table("monuments")
            .select("id")
            .eq("id", mid)
            .eq("user_id", user_id)
            .execute()
        )
        if not check.data:
            raise HTTPException(status_code=403, detail=f"Monument {mid} introuvable ou non autorisé")

    row = {
        **body.model_dump(exclude_none=True, exclude={"monument_id"}),
        "monument_ids": monument_ids,
        "user_id": user_id,
        "dossiers_utilises": [],
    }

    result = supabase.table("documents").insert(row).execute()
    return result.data[0]


@router.get("/{document_id}")
def get_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    return _get_document_or_404(supabase, document_id, user_id)


@router.patch("/{document_id}")
def update_document(
    document_id: str,
    body: UpdateDocumentRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    _get_document_or_404(supabase, document_id, user_id)

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _get_document_or_404(supabase, document_id, user_id)

    result = supabase.table("documents").update(updates).eq("id", document_id).execute()
    return result.data[0]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    doc = _get_document_or_404(supabase, document_id, user_id)

    # Delete file from Supabase Storage
    storage_path = doc.get("url", "")
    if storage_path:
        # Strip any full URL prefix to get the relative path
        marker = "/storage/v1/object/public/documents/"
        idx = storage_path.find(marker)
        if idx != -1:
            storage_path = storage_path[idx + len(marker):]
        import contextlib
        with contextlib.suppress(Exception):
            supabase.storage.from_("documents").remove([storage_path])  # best-effort

    supabase.table("documents").delete().eq("id", document_id).execute()


@router.post("/{document_id}/link/{dossier_id}", status_code=status.HTTP_204_NO_CONTENT)
def link_to_dossier(
    document_id: str,
    dossier_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    doc = _get_document_or_404(supabase, document_id, user_id)

    # Validate dossier ownership
    check = (
        supabase.table("dossiers")
        .select("id")
        .eq("id", dossier_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not check.data:
        raise HTTPException(status_code=403, detail="Dossier introuvable ou non autorisé")

    dossiers: list = doc.get("dossiers_utilises") or []
    if dossier_id not in dossiers:
        dossiers.append(dossier_id)
        supabase.table("documents").update({"dossiers_utilises": dossiers}).eq("id", document_id).execute()


@router.delete("/{document_id}/link/{dossier_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_from_dossier(
    document_id: str,
    dossier_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    doc = _get_document_or_404(supabase, document_id, user_id)

    dossiers: list = doc.get("dossiers_utilises") or []
    updated = [d for d in dossiers if d != dossier_id]

    supabase.table("documents").update({"dossiers_utilises": updated}).eq("id", document_id).execute()
