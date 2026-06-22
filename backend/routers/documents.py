import contextlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from db import get_current_user_id, get_supabase
from services.project_access import (
    allowed_visibilities,
    can_delete_document,
    can_edit_visibility,
    can_view_document,
    get_project_role,
    require_project_access,
    role_at_least,
)

router = APIRouter(prefix="/documents", tags=["documents"])

COLUMNS = "*"

STORAGE_BUCKET = "documents"
SIGNED_URL_EXPIRY = 7 * 24 * 60 * 60  # 7 jours, en secondes


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
    visibility: str | None = None
    allowed_user_ids: list[str] = []


class UpdateDocumentRequest(BaseModel):
    nom: str | None = None
    type: str | None = None
    tags: list[str] | None = None
    date_document: str | None = None
    description: str | None = None
    visibility: str | None = None
    allowed_user_ids: list[str] | None = None


class AddToProjectsRequest(BaseModel):
    monument_ids: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_document_any(supabase: Client, document_id: str) -> dict:
    result = supabase.table("documents").select(COLUMNS).eq("id", document_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Document introuvable")
    return result.data


def _require_document_read(supabase: Client, document_id: str, user_id: str) -> dict:
    """Lecture : l'auteur du document, ou tout membre d'un de ses projets."""
    doc = _get_document_any(supabase, document_id)
    if doc.get("user_id") == user_id:
        return doc
    for mid in doc.get("monument_ids") or []:
        if get_project_role(supabase, mid, user_id) is not None:
            return doc
    raise HTTPException(status_code=404, detail="Document introuvable")


def _require_document_view(supabase: Client, document_id: str, user_id: str) -> dict:
    """Consultation : l'auteur, le chef de projet, ou selon la visibilité du document.

    Renvoie 404 (et non 403) pour ne pas révéler l'existence d'un document masqué.
    """
    doc = _get_document_any(supabase, document_id)
    role = _highest_project_role(supabase, doc.get("monument_ids"), user_id)
    if can_view_document(
        visibility=doc.get("visibility") or "team",
        allowed_user_ids=doc.get("allowed_user_ids") or [],
        uploader_id=doc.get("user_id"),
        viewer_id=user_id,
        viewer_role=role,
    ):
        return doc
    raise HTTPException(status_code=404, detail="Document introuvable")


def _highest_project_role(supabase: Client, monument_ids: list | None, user_id: str) -> str | None:
    """Rôle le plus élevé de l'utilisateur parmi les projets du document."""
    best = None
    for mid in monument_ids or []:
        r = get_project_role(supabase, mid, user_id)
        if r is not None and (best is None or role_at_least(r, best)):
            best = r
    return best


def _resolve_visibility(
    requested: str | None,
    allowed_user_ids: list[str],
    role: str | None,
    *,
    has_project: bool,
) -> tuple[str, list[str]]:
    """Normalise/valide la visibilité demandée selon le rôle de l'auteur.

    Document sans projet → 'team' (pas de contexte de partage). Sinon défaut
    'team' pour un responsable, 'responsables' pour un collaborateur. La liste
    `allowed_user_ids` n'est conservée que pour 'custom'.
    """
    if not has_project:
        return "team", []
    visibility = requested or ("team" if role_at_least(role, "co_owner") else "responsables")
    if visibility not in allowed_visibilities(role):
        raise HTTPException(status_code=422, detail="Visibilité non autorisée pour votre rôle")
    return visibility, (list(allowed_user_ids) if visibility == "custom" else [])


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _should_auto_trash(monument_ids: list | None, dossiers_utilises: list | None) -> bool:
    """Vrai si le document n'a plus AUCUN projet ni dossier → il part en corbeille."""
    return not (monument_ids or []) and not (dossiers_utilises or [])


def _best_role(monument_ids: list | None, my_roles: dict[str, str]) -> str | None:
    """Meilleur rôle du viewer parmi les projets du document (None si aucun)."""
    best = None
    for mid in monument_ids or []:
        r = my_roles.get(mid)
        if r is not None and (best is None or role_at_least(r, best)):
            best = r
    return best


def _filter_visible(rows: list[dict], user_id: str, my_roles: dict[str, str]) -> list[dict]:
    """Ne garde que les documents que `user_id` a le droit de voir (règle existante)."""
    return [
        r
        for r in rows
        if can_view_document(
            visibility=r.get("visibility") or "team",
            allowed_user_ids=r.get("allowed_user_ids") or [],
            uploader_id=r.get("user_id"),
            viewer_id=user_id,
            viewer_role=_best_role(r.get("monument_ids"), my_roles),
        )
    ]


def _my_project_roles(supabase: Client, user_id: str) -> dict[str, str]:
    """Tous mes projets → mon rôle (owner gagne sur une éventuelle ligne membre)."""
    roles: dict[str, str] = {}
    members = (
        supabase.table("project_members")
        .select("monument_id, role")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    for m in members:
        roles[m["monument_id"]] = m["role"]
    owned = (
        supabase.table("monuments").select("id").eq("user_id", user_id).execute().data or []
    )
    for o in owned:
        roles[o["id"]] = "owner"
    return roles


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
def list_documents(
    monument_id: str | None = Query(None),
    type: str | None = Query(None),
    trashed: bool = Query(False),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    if monument_id:
        role = require_project_access(supabase, monument_id, user_id, "member")
        query = (
            supabase.table("documents")
            .select(COLUMNS)
            .contains("monument_ids", [monument_id])
            .order("date_upload", desc=True)
        )
        if type:
            query = query.eq("type", type)
        rows = query.execute().data or []
        return [
            r
            for r in rows
            if can_view_document(
                visibility=r.get("visibility") or "team",
                allowed_user_ids=r.get("allowed_user_ids") or [],
                uploader_id=r.get("user_id"),
                viewer_id=user_id,
                viewer_role=role,
            )
        ]

    # Vue « Mes documents » : tout ce que je peux voir (mes uploads + les documents
    # des projets où je suis membre, filtrés par les droits de consultation).
    my_roles = _my_project_roles(supabase, user_id)

    if trashed:
        # Corbeille personnelle : uniquement MES documents jetés.
        query = (
            supabase.table("documents")
            .select(COLUMNS)
            .eq("user_id", user_id)
            .not_.is_("trashed_at", "null")
        )
        if type:
            query = query.eq("type", type)
        return query.order("date_upload", desc=True).execute().data or []

    query = supabase.table("documents").select(COLUMNS).is_("trashed_at", "null")
    my_ids = list(my_roles.keys())
    if my_ids:
        ids_literal = ",".join(my_ids)
        query = query.or_(f"user_id.eq.{user_id},monument_ids.ov.{{{ids_literal}}}")
    else:
        query = query.eq("user_id", user_id)
    if type:
        query = query.eq("type", type)
    rows = query.order("date_upload", desc=True).execute().data or []
    return _filter_visible(rows, user_id, my_roles)


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

    # Accès (membre suffit pour déposer) + rôle le plus élevé parmi les projets.
    top_role = None
    for mid in monument_ids:
        r = require_project_access(supabase, mid, user_id, "member")
        if top_role is None or role_at_least(r, top_role):
            top_role = r

    visibility, allowed_ids = _resolve_visibility(
        body.visibility, body.allowed_user_ids, top_role, has_project=bool(monument_ids)
    )

    # The client uploads to <user_id>/... in storage, then submits the path here.
    safe_path = _validate_storage_path(body.url, user_id)

    payload = body.model_dump(
        exclude_none=True, exclude={"monument_id", "url", "visibility", "allowed_user_ids"}
    )
    row = {
        **payload,
        "url": safe_path,
        "monument_ids": monument_ids,
        "user_id": user_id,
        "dossiers_utilises": [],
        "visibility": visibility,
        "allowed_user_ids": allowed_ids,
    }

    result = supabase.table("documents").insert(row).execute()
    return result.data[0]


@router.get("/{document_id}")
def get_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    return _require_document_view(supabase, document_id, user_id)


@router.get("/{document_id}/signed-url")
def get_document_signed_url(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """URL signée pour consulter un document.

    La signature est faite côté serveur avec le client service-role : elle
    contourne la RLS storage (restreinte au dossier du dépositaire) afin que
    *tout membre* d'un projet du document — pas seulement son auteur — puisse le
    consulter. L'accès est contrôlé au niveau applicatif par _require_document_view.
    """
    doc = _require_document_view(supabase, document_id, user_id)
    storage_path = doc.get("url") or ""
    if not storage_path or "://" in storage_path:
        raise HTTPException(status_code=400, detail="Chemin de fichier invalide")
    try:
        res = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
            storage_path, SIGNED_URL_EXPIRY
        )
    except Exception as exc:  # storage3 lève sur erreur HTTP
        raise HTTPException(
            status_code=502, detail="Impossible de générer le lien du document"
        ) from exc
    signed = res.get("signedURL") or res.get("signedUrl")
    if not signed:
        raise HTTPException(status_code=502, detail="Lien du document indisponible")
    return {"signed_url": signed}


@router.patch("/{document_id}")
def update_document(
    document_id: str,
    body: UpdateDocumentRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    doc = _get_document_any(supabase, document_id)
    role = _highest_project_role(supabase, doc.get("monument_ids"), user_id)
    is_uploader = doc.get("user_id") == user_id
    if not can_edit_visibility(role, is_uploader=is_uploader):
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas modifier ce document")

    updates = body.model_dump(exclude_none=True)

    # Visibilité : valider selon le rôle, et purger la liste hors mode 'custom'.
    if "visibility" in updates or "allowed_user_ids" in updates:
        new_vis = updates.get("visibility", doc.get("visibility") or "team")
        if new_vis not in allowed_visibilities(role):
            raise HTTPException(status_code=422, detail="Visibilité non autorisée pour votre rôle")
        updates["visibility"] = new_vis
        updates["allowed_user_ids"] = (
            updates.get("allowed_user_ids", doc.get("allowed_user_ids") or [])
            if new_vis == "custom"
            else []
        )

    if not updates:
        return doc

    result = supabase.table("documents").update(updates).eq("id", document_id).execute()
    return result.data[0]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    doc = _get_document_any(supabase, document_id)
    uploader_id = doc.get("user_id")
    is_uploader = uploader_id == user_id

    # Suppression autorisée à l'auteur du document, ou à un owner/co_owner d'un de
    # ses projets (mêmes droits que la modification). Un simple membre ne peut
    # supprimer que ses propres documents. La consultation reste ouverte à tous.
    role = _highest_project_role(supabase, doc.get("monument_ids"), user_id)
    if not can_delete_document(role, is_uploader=is_uploader):
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas supprimer ce document")

    # Le fichier est stocké sous "<uploader_id>/..." — valider contre l'auteur, pas l'appelant.
    storage_path = doc.get("url", "") or ""
    safe_path = None
    if (
        uploader_id
        and storage_path.startswith(f"{uploader_id}/")
        and ".." not in storage_path.split("/")
    ):
        safe_path = storage_path
    if safe_path:
        with contextlib.suppress(Exception):
            supabase.storage.from_(STORAGE_BUCKET).remove([safe_path])

    supabase.table("documents").delete().eq("id", document_id).execute()


@router.post("/{document_id}/link/{dossier_id}", status_code=status.HTTP_204_NO_CONTENT)
def link_to_dossier(
    document_id: str,
    dossier_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    doc = _require_document_view(supabase, document_id, user_id)

    dossier = (
        supabase.table("dossiers")
        .select("id, monument_id")
        .eq("id", dossier_id)
        .maybe_single()
        .execute()
    )
    if not dossier or not dossier.data:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    # Tout membre du projet peut rattacher au dossier un document qu'il peut consulter
    # (le sien, typiquement) — le dépôt de pièces n'est pas réservé aux chefs.
    require_project_access(supabase, dossier.data["monument_id"], user_id, "member")

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
    doc = _require_document_read(supabase, document_id, user_id)

    dossier = (
        supabase.table("dossiers")
        .select("id, monument_id")
        .eq("id", dossier_id)
        .maybe_single()
        .execute()
    )
    if dossier and dossier.data:
        # Retirer une pièce d'un dossier suit la règle de suppression des documents :
        # l'auteur de la pièce, ou un chef de projet / adjoint.
        role = get_project_role(supabase, dossier.data["monument_id"], user_id)
        if not can_delete_document(role, is_uploader=(doc.get("user_id") == user_id)):
            raise HTTPException(
                status_code=403, detail="Vous ne pouvez pas retirer cette pièce du dossier"
            )

    dossiers: list = doc.get("dossiers_utilises") or []
    updated = [d for d in dossiers if d != dossier_id]

    patch: dict = {"dossiers_utilises": updated}
    if _should_auto_trash(doc.get("monument_ids"), updated):
        patch["trashed_at"] = _now_iso()
    supabase.table("documents").update(patch).eq("id", document_id).execute()


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

    # Accès partagé : seul quelqu'un pouvant consulter le document peut le repartager.
    source = _require_document_view(supabase, document_id, user_id)

    # Tout membre d'un projet cible peut y associer le document (modèle lien, pas de copie).
    for mid in body.monument_ids:
        require_project_access(supabase, mid, user_id, "member")

    merged = _merge_monument_ids(source.get("monument_ids") or [], body.monument_ids)
    result = (
        supabase.table("documents").update({"monument_ids": merged}).eq("id", document_id).execute()
    )
    return result.data[0]


@router.post("/{document_id}/trash")
def trash_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Mettre un document à la corbeille : le détacher de tous ses projets/dossiers
    et poser `trashed_at`. Récupérable via /restore, supprimable définitivement via DELETE."""
    doc = _get_document_any(supabase, document_id)
    role = _highest_project_role(supabase, doc.get("monument_ids"), user_id)
    if not can_delete_document(role, is_uploader=(doc.get("user_id") == user_id)):
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas supprimer ce document")
    patch = {"monument_ids": [], "dossiers_utilises": [], "trashed_at": _now_iso()}
    result = supabase.table("documents").update(patch).eq("id", document_id).execute()
    return result.data[0]


@router.post("/{document_id}/restore")
def restore_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
):
    """Restaurer un document de la corbeille (revient en « Sans projet »)."""
    doc = _get_document_any(supabase, document_id)
    if doc.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Seul l'auteur peut restaurer ce document")
    result = (
        supabase.table("documents").update({"trashed_at": None}).eq("id", document_id).execute()
    )
    return result.data[0]
