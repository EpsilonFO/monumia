import contextlib

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase

router = APIRouter(prefix="/documents", tags=["documents"])

COLUMNS = "*"

STORAGE_BUCKET = "documents"


def _validate_storage_path(path: str, user_id: str) -> str:
    """Ensure a document storage path is scoped to the calling user's folder.

    The frontend stores files at "<user_id>/<random>.<ext>" and sends the
    relative path. Reject anything else: full URLs, traversal, or other users.
    """
    if not path or not isinstance(path, str):
        raise HTTPException(status_code=400, detail="Chemin de fichier invalide")
    if "://" in path or path.startswith("/") or ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Chemin de fichier invalide")
    expected_prefix = f"{user_id}/"
    if not path.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="Chemin de fichier non autorisé")
    return path


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


class AddToProjectsRequest(BaseModel):
    monument_ids: list[str]


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


def _merge_monument_ids(existing: list[str], new: list[str]) -> list[str]:
    """Return the existing project ids plus any new ones, order-preserving, no dupes.

    Adding a document to a project associates the *same* document with another
    project — it never creates a copy — so we just grow its monument_ids array.
    """
    merged = list(existing)
    for mid in new:
        if mid not in merged:
            merged.append(mid)
    return merged


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
            supabase.table("monuments").select("id").eq("id", mid).eq("user_id", user_id).execute()
        )
        if not check.data:
            raise HTTPException(
                status_code=403, detail=f"Monument {mid} introuvable ou non autorisé"
            )

    # The client uploads to <user_id>/... in storage, then submits the path here.
    # Reject anything that isn't strictly scoped to the caller's folder so we
    # never store a path that points at another user's files.
    safe_path = _validate_storage_path(body.url, user_id)

    payload = body.model_dump(exclude_none=True, exclude={"monument_id", "url"})
    row = {
        **payload,
        "url": safe_path,
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

    # Delete file from Supabase Storage. The stored path was validated to
    # begin with "<user_id>/" at upload time; re-validate before calling
    # remove() so a tampered row can never delete another user's files.
    storage_path = doc.get("url", "") or ""
    try:
        safe_path = _validate_storage_path(storage_path, user_id)
    except HTTPException:
        safe_path = None

    if safe_path:
        with contextlib.suppress(Exception):
            supabase.storage.from_(STORAGE_BUCKET).remove([safe_path])  # best-effort

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
        supabase.table("documents").update({"dossiers_utilises": dossiers}).eq(
            "id", document_id
        ).execute()


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

    supabase.table("documents").update({"dossiers_utilises": updated}).eq(
        "id", document_id
    ).execute()


@router.post("/{document_id}/projects")
def add_document_to_projects(
    document_id: str,
    body: AddToProjectsRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Associate an existing document with one or more additional projects.

    This appends to the document's monument_ids array — the same file and row
    are shared across projects. No copy of the file or the row is ever made.
    """
    if not body.monument_ids:
        raise HTTPException(status_code=400, detail="Aucun projet cible fourni")

    source = _get_document_or_404(supabase, document_id, user_id)

    # Validate ownership of every target project before linking anything.
    for mid in body.monument_ids:
        check = (
            supabase.table("monuments").select("id").eq("id", mid).eq("user_id", user_id).execute()
        )
        if not check.data:
            raise HTTPException(status_code=403, detail=f"Projet {mid} introuvable ou non autorisé")

    merged = _merge_monument_ids(source.get("monument_ids") or [], body.monument_ids)
    result = (
        supabase.table("documents").update({"monument_ids": merged}).eq("id", document_id).execute()
    )
    return result.data[0]
