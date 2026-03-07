from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from db import get_supabase, get_current_user_id

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
    monument_id: Optional[str] = None
    date_document: Optional[str] = None
    description: Optional[str] = None


class UpdateDocumentRequest(BaseModel):
    nom: Optional[str] = None
    type: Optional[str] = None
    tags: Optional[list[str]] = None
    date_document: Optional[str] = None
    description: Optional[str] = None


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
    monument_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
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
        query = query.eq("monument_id", monument_id)
    if type:
        query = query.eq("type", type)

    return query.execute().data


@router.post("", status_code=status.HTTP_201_CREATED)
def create_document(
    body: CreateDocumentRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    # Validate monument ownership if provided
    if body.monument_id:
        check = (
            supabase.table("monuments")
            .select("id")
            .eq("id", body.monument_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not check.data:
            raise HTTPException(status_code=403, detail="Monument introuvable ou non autorisé")

    row = {
        **body.model_dump(exclude_none=True),
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
    _get_document_or_404(supabase, document_id, user_id)
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
